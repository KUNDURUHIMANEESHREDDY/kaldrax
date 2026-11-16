import json
import pytest
from kaldrax.engine import RecursiveEngine
from kaldrax.evaluation import CriteriaEvaluator
from kaldrax.execution import ExampleExecutor
from kaldrax.models import RunStatus, Task

class AlwaysIncompleteExecutor:
    def execute(self, task, feedback, iteration):
        return "still incomplete"

def test_engine_retries_with_feedback_and_persists_report(tmp_path):
    task = Task("Write a delivery summary", ("Scope", "Verification"), max_iterations=3)
    report = RecursiveEngine(ExampleExecutor(), artifact_dir=tmp_path).run(task)
    assert report.status is RunStatus.PASSED
    assert report.iterations == 2
    assert report.evaluations[0].missing == ("Scope", "Verification")
    assert report.evaluations[1].passed
    saved = json.loads((tmp_path / f"{report.run_id}.json").read_text())
    assert saved["status"] == "passed"
    assert saved["events"][-1]["event_type"] == "run_finished"

def test_engine_stops_at_iteration_limit():
    task = Task("Do work", ("verifiable result",), max_iterations=2)
    report = RecursiveEngine(AlwaysIncompleteExecutor()).run(task)
    assert report.status is RunStatus.LIMIT_REACHED
    assert report.iterations == 2
    assert len(report.evaluations) == 2

def test_evaluator_is_case_insensitive_and_independent():
    task = Task("Create output", ("Acceptance",))
    result = CriteriaEvaluator().evaluate(task, "acceptance achieved")
    assert result.passed
    assert result.satisfied == ("Acceptance",)

def test_task_rejects_invalid_contracts():
    with pytest.raises(ValueError):
        Task(" ", ("criterion",))
    with pytest.raises(ValueError):
        Task("objective", ())
    with pytest.raises(ValueError):
        Task("objective", ("criterion",), max_iterations=0)

class ExplodingExecutor:
    def execute(self, task, feedback, iteration):
        raise RuntimeError("provider unavailable")

def test_executor_error_is_reported_and_persisted(tmp_path):
    task = Task("Do work", ("result",), max_iterations=3)
    report = RecursiveEngine(ExplodingExecutor(), artifact_dir=tmp_path).run(task)
    assert report.status is RunStatus.FAILED
    assert report.iterations == 1
    assert report.events[-2].event_type == "executor_error"
    assert json.loads((tmp_path / f"{report.run_id}.json").read_text())["status"] == "failed"
