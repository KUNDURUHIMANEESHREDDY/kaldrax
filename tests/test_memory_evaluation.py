import hashlib
import json

from kaldrax.memory_evaluation import (
    assess_quality_review_approval,
    build_memory_evaluation_report,
    create_quality_review_approval,
    render_memory_evaluation_markdown,
)


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def _thresholds(path, *, retrieval_floor=0.0, contradiction_floor=0.0):
    return _write_json(path, {
        "schema_version": 1,
        "ci": {
            "retrieval": {
                "recall_at_k": retrieval_floor,
                "ndcg_at_k": retrieval_floor,
                "mean_reciprocal_rank": retrieval_floor,
                "top1_accuracy": retrieval_floor,
            },
            "contradiction": {"f1": contradiction_floor},
        },
        "release": {
            "retrieval": {
                "recall_at_k": 0.0,
                "ndcg_at_k": 0.0,
                "mean_reciprocal_rank": 0.0,
                "top1_accuracy": 0.0,
            },
            "hybrid": {"ndcg_at_k": 0.0, "minimum_ndcg_delta": -1.0},
            "contradiction": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
            "extraction": {
                "precision": 0.0, "recall": 0.0, "f1": 0.0, "evidence_valid_rate": 0.0,
            },
            "calibration": {
                "max_brier_score": 1.0, "max_expected_calibration_error": 1.0,
            },
            "minimum_sample_sizes": {
                "retrieval_queries": 2,
                "contradiction_cases": 3,
                "contradiction_positive_cases": 2,
                "contradiction_negative_cases": 2,
                "extraction_cases": 2,
                "extraction_expected_claims": 2,
                "extraction_confidence_samples": 1,
            },
        },
    })


def _datasets(tmp_path):
    retrieval = _write_json(tmp_path / "retrieval.json", {
        "name": "retrieval-fixture",
        "provenance": "synthetic_curated",
        "annotation_status": "assistant_proposed_pending_human_review",
        "privacy_screening": {"status": "pending_operator_signoff"},
        "memories": [{"id": "m1", "content": "SQLite stores durable project memory."}],
        "queries": [{
            "id": "q1", "query": "Where is project memory stored?", "relevant": ["m1"],
        }],
    })
    contradiction = _write_json(tmp_path / "contradiction.json", {
        "name": "contradiction-fixture",
        "provenance": "synthetic_curated",
        "annotation_status": "human_reviewed",
        "dataset_approval": {"status": "approved", "reviewer": "reviewer-1", "reviewed_at": "2026-11-16T00:00:00Z"},
        "cases": [
            {
                "id": "positive",
                "annotation_status": "human_reviewed", "review_status": "approved", "reviewer": "reviewer-1", "reviewed_at": "2026-11-16T00:00:00Z",
                "left": "Rule: allow worker agents to access shared project artifacts",
                "right": "Rule: deny worker agents access to shared project artifacts",
                "expected_conflict": True,
            },
            {
                "id": "negative",
                "annotation_status": "human_reviewed", "review_status": "approved", "reviewer": "reviewer-1", "reviewed_at": "2026-11-16T00:00:00Z",
                "left": "Rule: enable local cache invalidation for user profiles",
                "right": "Rule: disable remote email delivery for notifications",
                "expected_conflict": False,
            },
        ],
    })
    extraction = _write_json(tmp_path / "extraction.json", {
        "name": "extraction-fixture",
        "provenance": "synthetic_curated",
        "annotation_status": "human_reviewed",
        "dataset_approval": {"status": "approved", "reviewer": "reviewer-1", "reviewed_at": "2026-11-16T00:00:00Z"},
        "cases": [{
            "id": "case-one",
            "annotation_status": "human_reviewed", "review_status": "approved", "reviewer": "reviewer-1", "reviewed_at": "2026-11-16T00:00:00Z",
            "objective": "Extract a durable fact",
            "candidate": "SQLite stores durable project memory.",
            "expected": [{"match_terms": ["sqlite", "memory"]}],
        }],
    })
    return retrieval, contradiction, extraction


def test_ci_report_aggregates_benchmark_metrics_and_keeps_review_state_visible(tmp_path):
    retrieval, contradiction, extraction = _datasets(tmp_path)
    thresholds = _thresholds(tmp_path / "thresholds.json")
    report = build_memory_evaluation_report(
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
        thresholds_path=thresholds,
        approval_path=tmp_path / "missing-approval.json",
        profile="ci",
        k=1,
    )

    assert report["passed"] is True
    assert report["release_ready"] is False
    assert report["retrieval_comparison"]["lexical"]["query_count"] == 1
    assert report["contradiction"]["case_count"] == 2
    assert report["extraction"]["status"] == "not_run"
    assert report["datasets"]["retrieval"]["sha256"]
    assert report["release_readiness"]["retrieval_review"]["validated"] is False
    assert any("hybrid" in item for item in report["release_readiness"]["blocking_reasons"])
    assert any(
        check["name"] == "sample_size.contradiction_cases" and not check["passed"]
        for check in report["release_checks"]
    )


def test_ci_threshold_failure_blocks_report(tmp_path):
    retrieval, contradiction, extraction = _datasets(tmp_path)
    thresholds = _thresholds(
        tmp_path / "thresholds.json", retrieval_floor=1.01, contradiction_floor=1.01,
    )
    report = build_memory_evaluation_report(
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
        thresholds_path=thresholds,
        approval_path=tmp_path / "missing-approval.json",
        profile="ci",
        k=1,
    )
    assert report["passed"] is False
    assert any(not item["passed"] for item in report["checks"])


def test_label_review_approval_is_hash_bound_and_write_once(tmp_path):
    retrieval, contradiction, extraction = _datasets(tmp_path)
    approval_path = tmp_path / "approval.json"
    manifest = create_quality_review_approval(
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
        approval_path=approval_path,
        reviewer="reviewer-1",
        contradiction_labels_reviewed=True,
        extraction_labels_reviewed=True,
    )
    assert manifest["reviewer"] == "reviewer-1"
    assessment = assess_quality_review_approval(
        approval_path,
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
    )
    assert assessment["validated"] is True

    with open(contradiction, "a", encoding="utf-8") as handle:
        handle.write("\n")
    changed = assess_quality_review_approval(
        approval_path,
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
    )
    assert changed["validated"] is False
    assert any("contradiction dataset changed" in reason for reason in changed["blocking_reasons"])

    try:
        create_quality_review_approval(
            retrieval_dataset=retrieval,
            contradiction_dataset=contradiction,
            extraction_dataset=extraction,
            approval_path=approval_path,
            reviewer="reviewer-2",
            contradiction_labels_reviewed=True,
            extraction_labels_reviewed=True,
        )
    except ValueError as exc:
        assert "write-once" in str(exc)
    else:
        raise AssertionError("an existing approval must not be overwritten")


def test_label_review_must_cover_every_case_even_with_recomputed_digest(tmp_path):
    retrieval, contradiction, extraction = _datasets(tmp_path)
    approval_path = tmp_path / "approval.json"
    create_quality_review_approval(
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
        approval_path=approval_path,
        reviewer="reviewer-1",
        contradiction_labels_reviewed=True,
        extraction_labels_reviewed=True,
    )
    manifest = json.loads(approval_path.read_text(encoding="utf-8"))
    manifest["label_reviews"]["contradiction"]["case_ids"] = ["positive"]
    payload = dict(manifest)
    payload.pop("integrity", None)
    manifest["integrity"]["digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    approval_path.write_text(json.dumps(manifest), encoding="utf-8")

    assessment = assess_quality_review_approval(
        approval_path,
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
    )
    assert assessment["validated"] is False
    assert any(
        "exact ordered case IDs" in reason
        for reason in assessment["blocking_reasons"]
    )


def test_markdown_summary_includes_metric_table_and_release_blockers(tmp_path):
    retrieval, contradiction, extraction = _datasets(tmp_path)
    thresholds = _thresholds(tmp_path / "thresholds.json")
    report = build_memory_evaluation_report(
        retrieval_dataset=retrieval,
        contradiction_dataset=contradiction,
        extraction_dataset=extraction,
        thresholds_path=thresholds,
        approval_path=tmp_path / "missing-approval.json",
        profile="ci",
        k=1,
    )
    markdown = render_memory_evaluation_markdown(report)
    assert "# KALDRAX Memory Evaluation" in markdown
    assert "Contradiction detection" in markdown
    assert "Release blockers" in markdown
