"""Bounded recursive execution loop."""
import json
from pathlib import Path
from .evaluation import CriteriaEvaluator
from .execution import Executor
from .models import RunReport, RunStatus, Task

class RecursiveEngine:
    """Execute, independently evaluate, feed failures back, and stop safely."""

    def __init__(self, executor: Executor, evaluator: CriteriaEvaluator | None = None,
                 artifact_dir: Path | None = None) -> None:
        self.executor = executor
        self.evaluator = evaluator or CriteriaEvaluator()
        self.artifact_dir = artifact_dir

    def run(self, task: Task) -> RunReport:
        report = RunReport.new(task.objective)
        report.add_event("run_started", "Execution started.")
        feedback: tuple[str, ...] = ()
        for iteration in range(1, task.max_iterations + 1):
            report.iterations = iteration
            report.add_event("iteration_started", f"Iteration {iteration} started.")
            try:
                candidate = self.executor.execute(task, feedback, iteration)
            except Exception as exc:
                report.status = RunStatus.FAILED
                report.add_event("executor_error", f"Executor failed: {type(exc).__name__}: {exc}")
                break

            if not isinstance(candidate, str) or not candidate.strip():
                candidate = ""
                report.add_event("executor_warning", "Executor returned an empty or invalid candidate.")
            evaluation = self.evaluator.evaluate(task, candidate)
            report.evaluations.append(evaluation)
            report.final_output = candidate
            if evaluation.passed:
                report.add_event("evaluation_passed", f"All {len(evaluation.satisfied)} criteria satisfied.")
                report.status = RunStatus.PASSED
                report.add_event("run_completed", "Independent evaluation passed.")
                break
            report.add_event("evaluation_failed", f"Missing criteria: {', '.join(evaluation.missing)}")
            feedback = evaluation.missing
        else:
            report.status = RunStatus.LIMIT_REACHED
            report.add_event("iteration_limit_reached", f"No passing candidate after {task.max_iterations} iterations.")
        report.add_event("run_finished", f"Run finished with status: {report.status.value}.")
        self._persist(report)
        return report

    def _persist(self, report: RunReport) -> None:
        if self.artifact_dir is None:
            return
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / f"{report.run_id}.json"
        path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
