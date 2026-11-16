"""Offline extraction-quality and confidence-calibration evaluation."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .memory_intelligence import KnowledgeExtractor, MemoryExtractionError
from .models import Task

_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")


def _normal_tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.casefold()))


def _maximum_matching(edges: list[list[int]], expected_count: int) -> dict[int, int]:
    """Return prediction-index -> expected-index using augmenting paths."""
    expected_to_prediction: dict[int, int] = {}

    def assign(prediction_index: int, visited: set[int]) -> bool:
        for expected_index in edges[prediction_index]:
            if expected_index in visited:
                continue
            visited.add(expected_index)
            previous = expected_to_prediction.get(expected_index)
            if previous is None or assign(previous, visited):
                expected_to_prediction[expected_index] = prediction_index
                return True
        return False

    for prediction_index in range(len(edges)):
        assign(prediction_index, set())
    return {
        prediction_index: expected_index
        for expected_index, prediction_index in expected_to_prediction.items()
    }


def _calibration(predictions: list[tuple[float, int]], bin_count: int = 5) -> dict[str, Any]:
    if not predictions:
        return {
            "sample_count": 0, "brier_score": None,
            "expected_calibration_error": None, "bins": [],
        }
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bin_count)]
    squared_errors: list[float] = []
    for confidence, correct in predictions:
        bounded = max(0.0, min(1.0, confidence))
        squared_errors.append((bounded - correct) ** 2)
        index = min(int(bounded * bin_count), bin_count - 1)
        buckets[index].append((bounded, correct))

    bins: list[dict[str, Any]] = []
    weighted_gap = 0.0
    total = len(predictions)
    for index, bucket in enumerate(buckets):
        if not bucket:
            continue
        mean_confidence = sum(item[0] for item in bucket) / len(bucket)
        accuracy = sum(item[1] for item in bucket) / len(bucket)
        gap = abs(mean_confidence - accuracy)
        weighted_gap += (len(bucket) / total) * gap
        bins.append({
            "lower_bound": round(index / bin_count, 2),
            "upper_bound": round((index + 1) / bin_count, 2),
            "count": len(bucket),
            "mean_confidence": round(mean_confidence, 4),
            "empirical_accuracy": round(accuracy, 4),
            "absolute_gap": round(gap, 4),
        })
    return {
        "sample_count": total,
        "brier_score": round(sum(squared_errors) / total, 4),
        "expected_calibration_error": round(weighted_gap, 4),
        "bins": bins,
    }


def run_extraction_benchmark(
    dataset_path: str | Path, *, extractor: KnowledgeExtractor,
) -> dict[str, Any]:
    """Run an injected extractor against annotated candidate/evidence cases.

    Each expected claim declares match_terms: all terms must appear in a
    predicted claim's content or summary for it to count as a match. This
    conservative, inspectable matcher avoids embedding/model dependencies.
    """
    try:
        dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read extraction benchmark dataset: {type(exc).__name__}") from None
    if not isinstance(dataset, dict) or not isinstance(dataset.get("cases"), list):
        raise ValueError("extraction benchmark dataset requires a cases array")

    case_results: list[dict[str, Any]] = []
    total_expected = 0
    total_predicted = 0
    total_matched = 0
    extraction_errors = 0
    evidence_valid = 0
    confidence_labels: list[tuple[float, int]] = []

    for case in dataset["cases"]:
        if not isinstance(case, dict):
            raise ValueError("each extraction benchmark case must be an object")
        case_id = case.get("id")
        objective = case.get("objective")
        candidate = case.get("candidate")
        expected = case.get("expected")
        if not all(isinstance(value, str) and value.strip() for value in (case_id, objective, candidate)):
            raise ValueError("each case requires non-empty id, objective, and candidate strings")
        if not isinstance(expected, list):
            raise ValueError(f"case {case_id} requires an expected array")
        gold_terms: list[set[str]] = []
        for item in expected:
            if not isinstance(item, dict) or not isinstance(item.get("match_terms"), list):
                raise ValueError(f"case {case_id} expected claims require match_terms")
            terms = item["match_terms"]
            if not terms or any(not isinstance(term, str) or not term.strip() for term in terms):
                raise ValueError(f"case {case_id} match_terms must contain non-empty strings")
            normalized = set().union(*(_normal_tokens(term) for term in terms))
            if not normalized:
                raise ValueError(f"case {case_id} contains empty normalized match_terms")
            gold_terms.append(normalized)

        task = Task(
            objective, ("Extract only durable facts supported by the candidate.",),
            project_id=str(case.get("project_id", "extraction-benchmark")),
        )
        try:
            records = extractor.extract(
                task, candidate, source_run_id=f"benchmark:{case_id}",
                source_event_sequences=(),
            )
        except MemoryExtractionError as exc:
            records = []
            extraction_errors += 1
            error_type = type(exc).__name__
        else:
            error_type = None
        if not isinstance(records, list):
            raise ValueError("extractor must return a list of memory records")

        prediction_tokens = [
            _normal_tokens(f"{record.content} {record.summary}")
            for record in records
        ]
        edges = [
            [index for index, required in enumerate(gold_terms) if required <= tokens]
            for tokens in prediction_tokens
        ]
        matched = _maximum_matching(edges, len(gold_terms))
        evidence_count = 0
        for prediction_index, record in enumerate(records):
            quote = record.metadata.get("evidence_quote")
            supported_quote = isinstance(quote, str) and bool(quote) and quote in candidate
            evidence_count += int(supported_quote)
            is_correct = int(prediction_index in matched)
            confidence_labels.append((float(record.confidence), is_correct))

        expected_count = len(expected)
        predicted_count = len(records)
        true_positives = len(matched)
        total_expected += expected_count
        total_predicted += predicted_count
        total_matched += true_positives
        evidence_valid += evidence_count
        precision = true_positives / predicted_count if predicted_count else (1.0 if not expected_count else 0.0)
        recall = true_positives / expected_count if expected_count else (1.0 if not predicted_count else 0.0)
        case_results.append({
            "id": case_id,
            "category": str(case.get("category", "uncategorized")),
            "expected": expected_count,
            "predicted": predicted_count,
            "matched": true_positives,
            "false_positives": predicted_count - true_positives,
            "false_negatives": expected_count - true_positives,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "evidence_valid": evidence_count,
            "extraction_error": error_type,
        })

    precision = total_matched / total_predicted if total_predicted else 0.0
    recall = total_matched / total_expected if total_expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    calibration = _calibration(confidence_labels)
    return {
        "dataset": str(dataset_path),
        "dataset_name": str(dataset.get("name", Path(dataset_path).stem)),
        "case_count": len(case_results),
        "expected_count": total_expected,
        "predicted_count": total_predicted,
        "true_positives": total_matched,
        "false_positives": total_predicted - total_matched,
        "false_negatives": total_expected - total_matched,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "evidence_valid_rate": round(evidence_valid / total_predicted, 4) if total_predicted else None,
        "extraction_errors": extraction_errors,
        "confidence_calibration": calibration,
        "calibration_interpretation": (
            "Brier score and expected calibration error are descriptive estimates "
            "over this annotated sample, not proof of population calibration."
        ),
        "cases": case_results,
    }
