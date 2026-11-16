import json

from kaldrax.memory_benchmarks import run_retrieval_benchmark


class FakeEmbedder:
    model_id = "fake-semantic-v1"

    @staticmethod
    def _group(text):
        value = text.casefold()
        if "project identifier" in value or "cross-project" in value or "another project's" in value:
            return [1.0, 0.0, 0.0]
        if "sqlite" in value or "database" in value or "restarts" in value:
            return [0.0, 1.0, 0.0]
        if "iteration" in value or "retry" in value or "runaway" in value or "forever" in value:
            return [0.0, 0.0, 1.0]
        if "credential" in value or "api key" in value or "secret" in value:
            return [1.0, 1.0, 0.0]
        return [0.0, 1.0, 1.0]

    def embed(self, texts):
        return [self._group(text) for text in texts]


def test_retrieval_benchmark_reports_recall_mrr_and_top1(tmp_path):
    from pathlib import Path

    dataset = Path(__file__).parents[1] / "benchmarks" / "memory_retrieval.json"
    result = run_retrieval_benchmark(dataset, embedder=FakeEmbedder(), k=3)
    assert result["retrieval_mode"] == "hybrid"
    assert result["query_count"] == 5
    assert result["recall_at_k"] == 1.0
    assert result["mean_reciprocal_rank"] == 1.0
    assert result["top1_accuracy"] == 1.0


def test_benchmark_rejects_empty_relevant_sets(tmp_path):
    dataset = tmp_path / "invalid.json"
    dataset.write_text(json.dumps({
        "memories": [{"id": "one", "content": "one item"}],
        "queries": [{"query": "find", "relevant": []}],
    }))
    import pytest
    with pytest.raises(ValueError, match="cannot be empty"):
        run_retrieval_benchmark(dataset)

def test_engineering_benchmark_covers_a_broad_annotated_workload():
    from pathlib import Path

    dataset = Path(__file__).parents[1] / "benchmarks" / "memory_retrieval_engineering_v2.json"
    result = run_retrieval_benchmark(dataset, k=3)
    assert result["dataset_provenance"] == "synthetic_curated"
    assert result["memory_count"] >= 35
    assert result["query_count"] >= 40
    assert len(result["by_category"]) >= 10
    assert "precision_at_k" in result
    assert "ndcg_at_k" in result
    assert result["retrieval_mode"] == "lexical"


def test_benchmark_rejects_relevance_ids_not_in_the_corpus(tmp_path):
    import pytest

    dataset = tmp_path / "unknown-id.json"
    dataset.write_text(json.dumps({
        "memories": [{"id": "known", "content": "Known memory"}],
        "queries": [{"query": "find known memory", "relevant": ["missing"]}],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown memory IDs"):
        run_retrieval_benchmark(dataset)

def test_retrieval_benchmark_falls_back_when_local_embedder_fails():
    from pathlib import Path

    class BrokenEmbedder:
        model_id = "unavailable-local-model"

        def embed(self, texts):
            raise RuntimeError("Ollama offline")

    dataset = Path(__file__).parents[1] / "benchmarks" / "memory_retrieval_engineering_v2.json"
    result = run_retrieval_benchmark(dataset, embedder=BrokenEmbedder(), k=3)
    assert result["retrieval_mode"] == "lexical"
    assert result["embedding_model"] is None
    assert result["embedding_error"] == "RuntimeError"
    assert result["query_count"] == 42

def test_retrieval_benchmark_batches_fixture_embedding_index():
    from pathlib import Path

    class CountingEmbedder:
        model_id = "counting-test"

        def __init__(self):
            self.batch_sizes = []

        def embed(self, texts):
            self.batch_sizes.append(len(texts))
            return [[1.0, 0.0] for _ in texts]

    embedder = CountingEmbedder()
    dataset = Path(__file__).parents[1] / "benchmarks" / "memory_retrieval_engineering_v2.json"
    result = run_retrieval_benchmark(dataset, embedder=embedder, k=1)
    assert result["retrieval_mode"] == "hybrid"
    assert embedder.batch_sizes[:2] == [32, 8]
    assert len(embedder.batch_sizes) == 2 + result["query_count"]
