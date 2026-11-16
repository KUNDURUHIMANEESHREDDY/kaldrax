import json
from pathlib import Path

import pytest

from kaldrax.benchmark import BenchmarkCase, load_cases, run_benchmark
from kaldrax.evaluation import CriteriaEvaluator


def test_benchmark_measures_confusion_matrix():
    cases = [
        BenchmarkCase("tp", "must be present", "this must be present", True),
        BenchmarkCase("tn", "missing phrase", "nothing relevant", False),
        BenchmarkCase("fp", "test", "tests passed", False),
    ]
    result = run_benchmark(CriteriaEvaluator(), cases)
    assert result.total == 3
    assert result.correct == 2
    assert result.true_positive == 1
    assert result.true_negative == 1
    assert result.false_positive == 1
    assert result.false_negative == 0
    assert result.accuracy == pytest.approx(2 / 3)
    assert result.precision == pytest.approx(0.5)


def test_benchmark_loader_validates_fixture(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([
        {"id": "case-a", "criterion": "present", "candidate": "present", "expected_pass": True}
    ]))
    assert len(load_cases(path)) == 1
    path.write_text(json.dumps([
        {"id": "case-a", "criterion": "present", "candidate": "present", "expected_pass": "yes"}
    ]))
    with pytest.raises(ValueError, match="boolean"):
        load_cases(path)


def test_bundled_benchmark_exposes_negation_weakness():
    cases = load_cases(Path(__file__).parents[1] / "src" / "kaldrax" / "data" / "evaluator_cases.json")
    report = run_benchmark(CriteriaEvaluator(), cases)
    negated = next(case for case in report.cases if case.case_id == "negated-criterion")
    assert negated.predicted_pass is True
    assert negated.correct is False
    assert report.accuracy == pytest.approx(0.8)


def test_evaluator_errors_are_not_misclassified_as_true_negatives():
    class BrokenEvaluator:
        def evaluate(self, task, candidate):
            raise RuntimeError("judge unavailable")

    report = run_benchmark(BrokenEvaluator(), [
        BenchmarkCase("negative", "missing", "not here", False)
    ])
    assert report.errors == 1
    assert report.correct == 0
    assert report.true_negative == 0
