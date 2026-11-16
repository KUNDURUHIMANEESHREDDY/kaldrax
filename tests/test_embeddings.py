import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from kaldrax.embeddings import EmbeddingError, HostedEmbeddingProvider
from kaldrax.memory import MemoryRecord, MemoryType, SQLiteMemoryStore


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.body[:limit]


def test_hosted_embedding_provider_sends_authenticated_batch_and_orders_vectors():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["authorization"] = request.get_header("Authorization")
        seen["payload"] = json.loads(request.data)
        return FakeResponse(json.dumps({
            "data": [
                {"index": 1, "embedding": [0.3, 0.4]},
                {"index": 0, "embedding": [0.1, 0.2]},
            ],
        }).encode())

    provider = HostedEmbeddingProvider(
        api_key="test-secret",
        model="text-embedding-3-small",
        base_url="https://api.example/v1/",
        timeout=9,
        opener=opener,
    )
    vectors = provider.embed(["first document", "second document"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert provider.model_id == "api.example/v1:text-embedding-3-small"
    assert seen["url"] == "https://api.example/v1/embeddings"
    assert seen["timeout"] == 9
    assert seen["authorization"] == "Bearer test-secret"
    assert seen["payload"] == {
        "model": "text-embedding-3-small",
        "input": ["first document", "second document"],
        "encoding_format": "float",
    }


def test_hosted_embedding_provider_rejects_non_https_and_credentialed_urls():
    for base_url in (
        "http://api.example/v1",
        "https://user:password@api.example/v1",
        "https://api.example/v1?token=secret",
        "https://api.example/v1#fragment",
    ):
        with pytest.raises(ValueError, match="HTTPS"):
            HostedEmbeddingProvider(api_key="key", model="model", base_url=base_url)


def test_hosted_embedding_provider_skips_empty_batches_and_rejects_blank_inputs():
    calls = []
    provider = HostedEmbeddingProvider(
        api_key="key",
        model="model",
        opener=lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    assert provider.embed([]) == []
    assert calls == []
    with pytest.raises(ValueError, match="non-empty"):
        provider.embed(["valid", "  "])


def test_hosted_embedding_provider_validates_dimensions_and_numeric_values():
    provider = HostedEmbeddingProvider(
        api_key="key",
        model="model",
        opener=lambda *_args, **_kwargs: FakeResponse(
            b'{"data":[{"index":0,"embedding":[0.1,0.2]},{"index":1,"embedding":[0.3]}]}'
        ),
    )
    with pytest.raises(EmbeddingError, match="dimensions"):
        provider.embed(["a", "b"])

    invalid = HostedEmbeddingProvider(
        api_key="key",
        model="model",
        opener=lambda *_args, **_kwargs: FakeResponse(
            b'{"data":[{"index":0,"embedding":[NaN]}]}'
        ),
    )
    with pytest.raises(EmbeddingError, match="finite"):
        invalid.embed(["a"])


def test_hosted_embedding_provider_requires_complete_unique_indices():
    duplicate = HostedEmbeddingProvider(
        api_key="key",
        model="model",
        opener=lambda *_args, **_kwargs: FakeResponse(
            b'{"data":[{"index":0,"embedding":[0.1]},{"index":0,"embedding":[0.2]}]}'
        ),
    )
    with pytest.raises(EmbeddingError, match="duplicate"):
        duplicate.embed(["a", "b"])


def test_hosted_embedding_provider_redacts_api_key_from_http_errors():
    def fail(*_args, **_kwargs):
        raise HTTPError(
            "https://api.example/embeddings",
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"error":"invalid key test-secret"}'),
        )

    provider = HostedEmbeddingProvider(api_key="test-secret", model="model", opener=fail)
    with pytest.raises(EmbeddingError) as exc:
        provider.embed(["private memory"])
    assert "401" in str(exc.value)
    assert "test-secret" not in str(exc.value)
    assert "[REDACTED]" in str(exc.value)


class AlwaysFailingEmbedder:
    model_id = "unavailable"

    def embed(self, texts):
        raise RuntimeError("hosted embedding API is unavailable")


def test_embedding_failure_falls_back_to_lexical_retrieval(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3", embedder=AlwaysFailingEmbedder())
    store.save(MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC,
        content="Lesson: keep local memory persistence durable",
    ))
    matches = store.search("local memory persistence", project_id="p")
    assert len(matches) == 1
    assert matches[0].retrieval_method == "lexical"
    assert store.last_embedding_error == "RuntimeError"
    store.close()


class StaticEmbedder:
    model_id = "static-v1"

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_existing_memories_can_be_reindexed_and_semantically_retrieved(tmp_path):
    database = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(database)
    store.save(MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC,
        content="The CPython interpreter executes bytecode for the application runtime.",
    ))
    store.close()

    indexed = SQLiteMemoryStore(database, embedder=StaticEmbedder())
    assert indexed.reindex_embeddings("p") == 1
    matches = indexed.search("python execution engine", project_id="p")
    assert matches
    assert matches[0].retrieval_method == "semantic"
    assert matches[0].semantic_score == 1.0
    indexed.close()
