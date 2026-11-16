import json

from kaldrax.memory import MemoryRecord, MemoryType
from kaldrax.memory_quality import run_extraction_benchmark
from kaldrax.memory_intelligence import MemoryExtractionError


class FakeExtractor:
    def __init__(self, records):
        self.records = records

    def extract(self, task, candidate, *, source_run_id, source_event_sequences, agent_id=None):
        return self.records


def test_extraction_benchmark_scores_precision_recall_and_confidence(tmp_path):
    candidate = "SQLite durable storage uses WAL logging."
    dataset = tmp_path / "extraction.json"
    dataset.write_text(json.dumps({
        "name": "calibration-test",
        "cases": [{
            "id": "case-1",
            "objective": "Capture database facts",
            "candidate": candidate,
            "expected": [
                {"match_terms": ["sqlite", "durable"]},
                {"match_terms": ["wal", "logging"]},
            ],
        }],
    }), encoding="utf-8")
    predictions = [
        MemoryRecord.create(
            project_id="benchmark", memory_type=MemoryType.SEMANTIC,
            content="Decision: SQLite durable store", confidence=0.8,
            metadata={"evidence_quote": "SQLite durable storage"},
        ),
        MemoryRecord.create(
            project_id="benchmark", memory_type=MemoryType.SEMANTIC,
            content="Decision: PostgreSQL is hosted remotely", confidence=0.9,
            metadata={"evidence_quote": "made up evidence"},
        ),
    ]

    result = run_extraction_benchmark(dataset, extractor=FakeExtractor(predictions))
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["evidence_valid_rate"] == 0.5
    assert result["confidence_calibration"]["sample_count"] == 2
    assert result["confidence_calibration"]["brier_score"] == 0.425
    assert result["confidence_calibration"]["expected_calibration_error"] == 0.35


def test_extraction_benchmark_counts_extractor_failures_as_missed_claims(tmp_path):
    dataset = tmp_path / "extraction.json"
    dataset.write_text(json.dumps({
        "cases": [{
            "id": "broken",
            "objective": "Extract database rules",
            "candidate": "SQLite persists records.",
            "expected": [{"match_terms": ["sqlite", "records"]}],
        }],
    }), encoding="utf-8")

    class BrokenExtractor:
        def extract(self, *args, **kwargs):
            raise MemoryExtractionError("invalid model response")

    result = run_extraction_benchmark(dataset, extractor=BrokenExtractor())
    assert result["extraction_errors"] == 1
    assert result["false_negatives"] == 1
    assert result["recall"] == 0.0
    assert result["confidence_calibration"]["sample_count"] == 0
    assert result["evidence_valid_rate"] is None


def test_extraction_benchmark_validates_dataset_match_terms(tmp_path):
    dataset = tmp_path / "invalid.json"
    dataset.write_text(json.dumps({
        "cases": [{
            "id": "invalid", "objective": "Extract", "candidate": "Candidate text",
            "expected": [{"match_terms": []}],
        }],
    }), encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="match_terms"):
        run_extraction_benchmark(dataset, extractor=FakeExtractor([]))
