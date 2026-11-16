import json

import pytest

from kaldrax.memory_annotation import (
    assess_dataset_review,
    export_approved_dataset,
    run_annotation_review,
    verify_dataset_integrity,
)
from kaldrax.memory_benchmarks import run_retrieval_benchmark


def _dataset(path):
    path.write_text(json.dumps({
        "name": "annotation-test",
        "provenance": "public_repository_snapshot",
        "source_revision": "source-revision-1",
        "privacy_screening": {
            "scope": "Public repository files listed in the dataset.",
            "status": "pending_operator_signoff",
            "note": "Review source paths and copied content.",
        },
        "annotation_status": "assistant_proposed_pending_human_review",
        "memories": [
            {"id": "one", "category": "Architecture", "content": "SQLite stores durable project memory.", "summary": "SQLite persistence", "source": {"path": "README.md", "anchor": "memory"}},
            {"id": "two", "category": "Operations", "content": "Docker runs untrusted Python with network disabled.", "summary": "Isolated Docker execution", "source": {"path": "docs/ARCHITECTURE.md", "anchor": "sandbox"}},
        ],
        "queries": [{
            "id": "q-memory",
            "category": "Persistence",
            "query": "Where does KALDRAX persist project memory?",
            "relevant": ["one"],
            "rationale": "Assistant-proposed source match.",
            "annotation_status": "assistant_proposed_pending_human_review",
            "reviewer": None,
        }],
    }), encoding="utf-8")


def _inputs(values):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_human_review_and_privacy_are_separate_gates_and_export_is_immutable(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    result = run_annotation_review(
        source,
        reviewer="reviewer-a",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        version="1.0.0",
        input_fn=_inputs(["e", "two", "The query is about the runtime sandbox.", "a", "s"]),
        output_fn=lambda _line: None,
    )

    assert result["query_status_counts"] == {"modified": 1}
    assert result["dataset_approval_status"] == "approved"
    assert result["privacy_approval_status"] == "pending"
    assert result["export_path"] is None

    session = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert session["queries"]["q-memory"]["reviewer"] == "reviewer-a"
    assert session["queries"]["q-memory"]["reviewed_at"].endswith("Z")
    assert session["dataset_approval"]["status"] == "approved"
    assert session["privacy_screening"]["status"] == "pending"

    second = run_annotation_review(
        source,
        reviewer="privacy-reviewer",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        version="1.0.0",
        input_fn=_inputs(["s", "a", "APPROVE"]),
        output_fn=lambda _line: None,
    )
    assert second["benchmark_status"] == "validated_exported"
    export_path = second["export_path"]
    assert export_path is not None

    exported = json.loads(open(export_path, encoding="utf-8").read())
    assert exported["queries"][0]["relevant"] == ["two"]
    assert exported["queries"][0]["review_status"] == "modified"
    assert exported["queries"][0]["reviewer"] == "reviewer-a"
    assert exported["dataset_approval"]["reviewer"] == "reviewer-a"
    assert exported["privacy_screening"]["reviewer"] == "privacy-reviewer"
    assert verify_dataset_integrity(exported) is True
    assert assess_dataset_review(exported)["validated"] is True

    source_dataset = json.loads(source.read_text(encoding="utf-8"))
    completed_session = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    repeated_path = export_approved_dataset(
        source_dataset,
        completed_session,
        export_dir=tmp_path / "exports",
        version="1.0.0",
    )
    original_bytes = open(export_path, "rb").read()
    assert str(repeated_path) == export_path
    assert repeated_path.read_bytes() == original_bytes


def test_rejected_query_blocks_dataset_approval_and_export(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    result = run_annotation_review(
        source,
        reviewer="reviewer-a",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        input_fn=_inputs(["r", "Incorrect proposed label.", "s"]),
        output_fn=lambda _line: None,
    )
    assert result["query_status_counts"] == {"rejected": 1}
    assert result["dataset_approval_status"] == "pending"
    assert result["export_path"] is None
    assert not list((tmp_path / "exports").glob("*.json"))


def test_unreviewed_dataset_is_exploratory_not_validated(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    result = run_retrieval_benchmark(source, k=1)
    assert result["benchmark_validation"]["status"] == "exploratory_only"
    assert result["benchmark_validation"]["validated"] is False
    assert result["benchmark_validation"]["blocking_reasons"]


def test_tampered_export_fails_integrity_assessment(tmp_path):
    source = tmp_path / "dataset.json"
    _dataset(source)
    run_annotation_review(
        source,
        reviewer="reviewer-a",
        session_path=tmp_path / "session.json",
        export_dir=tmp_path / "exports",
        input_fn=_inputs(["a", "a", "a", "APPROVE"]),
        output_fn=lambda _line: None,
    )
    export_path = next((tmp_path / "exports").glob("*.json"))
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert assess_dataset_review(exported)["validated"] is True
    exported["queries"][0]["query"] = "tampered query"
    assert assess_dataset_review(exported)["validated"] is False
