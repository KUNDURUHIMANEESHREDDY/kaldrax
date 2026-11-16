import json

import pytest

from kaldrax.embeddings import EmbeddingError, OllamaEmbeddingProvider
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


def test_ollama_embedding_provider_uses_local_embed_api_and_batches_inputs():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["payload"] = json.loads(request.data)
        return FakeResponse(json.dumps({
            "embeddings": [[0.1, 0.2], [0.3, 0.4]]
        }).encode())

    provider = OllamaEmbeddingProvider(
        model="embeddinggemma", base_url="http://localhost:11434", timeout=9, opener=opener,
    )
    vectors = provider.embed(["first document", "second document"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert provider.model_id == "ollama:embeddinggemma"
    assert seen["url"] == "http://localhost:11434/api/embed"
    assert seen["timeout"] == 9
    assert seen["payload"]["input"] == ["first document", "second document"]


def test_ollama_embedding_provider_rejects_remote_endpoints():
    with pytest.raises(ValueError, match="loopback"):
        OllamaEmbeddingProvider(base_url="https://remote.example/api")


def test_ollama_embedding_provider_validates_dimension_and_numeric_values():
    provider = OllamaEmbeddingProvider(opener=lambda *_args, **_kwargs: FakeResponse(
        b'{"embeddings":[[0.1,0.2],[0.3]]}'
    ))
    with pytest.raises(EmbeddingError, match="dimensions"):
        provider.embed(["a", "b"])

    invalid = OllamaEmbeddingProvider(opener=lambda *_args, **_kwargs: FakeResponse(
        b'{"embeddings":[[NaN]]}'
    ))
    with pytest.raises(EmbeddingError):
        invalid.embed(["a"])


def test_ollama_embedding_provider_requires_one_vector_per_input():
    provider = OllamaEmbeddingProvider(opener=lambda *_args, **_kwargs: FakeResponse(
        b'{"embeddings":[]}'
    ))
    with pytest.raises(EmbeddingError, match="one embedding"):
        provider.embed(["one"])


class AlwaysFailingEmbedder:
    model_id = "unavailable"

    def embed(self, texts):
        raise RuntimeError("local embedding service is unavailable")


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
