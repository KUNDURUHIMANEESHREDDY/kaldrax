"""Evaluator benchmark runner and quality metrics."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .evaluation import Evaluator
from .models import Task


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    criterion: str
    candidate: str
    expected_pass: bool


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    expected_pass: bool
    predicted_pass: bool
    correct: bool
    error: str | None = None


@dataclass(frozen=True)
class BenchmarkReport:
    total: int
    correct: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    errors: int
    cases: tuple[BenchmarkCaseResult, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_cases(path: Path | str) -> list[BenchmarkCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("benchmark fixture must be a non-empty JSON array")
    cases: list[BenchmarkCase] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each benchmark case must be a JSON object")
        case_id = item.get("id")
        criterion = item.get("criterion")
        candidate = item.get("candidate")
        expected = item.get("expected_pass")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError("benchmark case IDs must be non-empty and unique")
        if not isinstance(criterion, str) or not criterion.strip():
            raise ValueError(f"benchmark case {case_id} has an invalid criterion")
        if not isinstance(candidate, str):
            raise ValueError(f"benchmark case {case_id} candidate must be text")
        if not isinstance(expected, bool):
            raise ValueError(f"benchmark case {case_id} expected_pass must be boolean")
        seen.add(case_id)
        cases.append(BenchmarkCase(case_id, criterion, candidate, expected))
    return cases


def run_benchmark(evaluator: Evaluator, cases: Iterable[BenchmarkCase]) -> BenchmarkReport:
    results: list[BenchmarkCaseResult] = []
    tp = fp = tn = fn = 0
    for case in cases:
        error = None
        try:
            task = Task(f"Benchmark criterion: {case.criterion}", (case.criterion,), max_iterations=1)
            predicted = bool(evaluator.evaluate(task, case.candidate).passed)
        except Exception as exc:
            predicted = False
            error = f"{type(exc).__name__}: {exc}"
        correct = error is None and predicted is case.expected_pass
        if error is not None:
            pass
        elif case.expected_pass and predicted:
            tp += 1
        elif not case.expected_pass and predicted:
            fp += 1
        elif not case.expected_pass and not predicted:
            tn += 1
        else:
            fn += 1
        results.append(BenchmarkCaseResult(case.case_id, case.expected_pass, predicted, correct, error))

    total = len(results)
    if total == 0:
        raise ValueError("at least one benchmark case is required")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    correct_count = tp + tn
    return BenchmarkReport(
        total=total,
        correct=correct_count,
        accuracy=correct_count / total,
        precision=precision,
        recall=recall,
        f1=f1,
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        errors=sum(result.error is not None for result in results),
        cases=tuple(results),
    )
