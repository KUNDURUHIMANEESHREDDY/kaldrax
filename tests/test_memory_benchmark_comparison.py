import json
from pathlib import Path

from kaldrax.cli import main
from kaldrax.memory_benchmark_comparison import run_retrieval_comparison


class MeaningEmbedder:
    model_id = "test-meaning-v1"

    def embed(self, texts):
        vectors = []
        for text in texts:
            value = text.casefold()
            if "sqlite" in value or "project knowledge" in value or "stored knowledge" in value:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors


def _dataset(path):
    path.write_text(json.dumps({
        "name": "comparison-test",
        "provenance": "public_repository_snapshot",
        "annotation_status": "assistant_proposed_pending_human_review",
        "source_revision": "test-revision",
        "privacy_screening": {"status": "pending_operator_signoff"},
        "memories": [
            {
                "id": "sqlite-memory",
                "content": "SQLite stores durable project knowledge in a local database.",
                "source": {"path": "README.md", "anchor": "memory"},
            },
            {
                "id": "restart-procedure",
                "content": "Kubernetes nodes restart after infrastructure failures.",
                "source": {"path": "docs/operations.md", "anchor": "restart"},
            },
        ],
        "queries": [{
            "id": "q1",
            "category": "Persistence",
            "query": "How is stored project knowledge retained across a restart?",
            "relevant": ["sqlite-memory"],
            "annotation_status": "assistant_proposed_pending_human_review",
        }],
    }), encoding="utf-8")


def test_comparison_reports_lexical_baseline_when_embeddings_unconfigured(tmp_path):
    dataset = tmp_path / "dataset.json"
    _dataset(dataset)

    report = run_retrieval_comparison(dataset, k=1)

    assert report["comparison_status"] == "lexical_only"
    assert report["hybrid"] is None
    assert report["deltas"] is None
    assert report["lexical"]["retrieval_mode"] == "lexical"
    assert report["annotation_status"] == "assistant_proposed_pending_human_review"
    assert report["privacy_screening_status"] == "pending_operator_signoff"


def test_comparison_reports_paired_hybrid_deltas(tmp_path):
    dataset = tmp_path / "dataset.json"
    _dataset(dataset)

    report = run_retrieval_comparison(
        dataset, embedder=MeaningEmbedder(), k=1,
    )

    assert report["comparison_status"] == "compared"
    assert report["lexical"]["retrieval_mode"] == "lexical"
    assert report["hybrid"]["retrieval_mode"] == "hybrid"
    assert set(report["deltas"]) == {
        "recall_at_k", "precision_at_k", "ndcg_at_k",
        "mean_reciprocal_rank", "top1_accuracy",
    }
    assert report["paired_query_results"][0]["id"] == "q1"
    assert set(report["paired_ndcg_outcomes"]) == {
        "hybrid_better", "tie", "hybrid_worse",
    }


def test_comparison_does_not_mislabel_failed_embeddings_as_hybrid(tmp_path):
    dataset = tmp_path / "dataset.json"
    _dataset(dataset)

    class BrokenEmbedder:
        model_id = "broken"

        def embed(self, texts):
            raise RuntimeError("Ollama unavailable")

    report = run_retrieval_comparison(dataset, embedder=BrokenEmbedder())

    assert report["comparison_status"] == "embedding_unavailable"
    assert report["hybrid"] is None
    assert report["deltas"] is None
    assert report["embedding_error"] == "RuntimeError"


def test_repository_corpus_is_source_backed_and_explicitly_unreviewed():
    root = Path(__file__).parents[1]
    dataset = json.loads(
        (root / "benchmarks" / "memory_retrieval_kaldrax_v1.json").read_text(encoding="utf-8")
    )

    assert dataset["provenance"] == "public_repository_snapshot"
    assert dataset["annotation_status"] == "assistant_proposed_pending_human_review"
    assert dataset["privacy_screening"]["status"] == "pending_operator_signoff"
    assert len(dataset["memories"]) >= 30
    assert len(dataset["queries"]) >= 30
    assert all(
        (root / item["source"]["path"]).is_file()
        for item in dataset["memories"]
    )
    assert all(
        item["annotation_status"] == "assistant_proposed_pending_human_review"
        and item["reviewer"] is None
        for item in dataset["queries"]
    )


def test_benchmark_compare_cli_emits_lexical_baseline(tmp_path, monkeypatch, capsys):
    dataset = tmp_path / "dataset.json"
    _dataset(dataset)
    monkeypatch.delenv("KALDRAX_EMBEDDING_MODEL", raising=False)
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "memory", "benchmark-compare", "--dataset", str(dataset), "--k", "1",
    ])

    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["comparison_status"] == "lexical_only"
    assert result["lexical"]["query_count"] == 1
