"""Bounded recursive execution loop with persistent project memory."""
import json
from pathlib import Path

from .evaluation import CriteriaEvaluator, Evaluator
from .execution import Executor
from .memory import MemoryRecord, MemoryStore, MemoryType, WorkingMemory, extract_reusable_knowledge
from .memory_intelligence import KnowledgeExtractor
from .models import RunReport, RunStatus, Task


class RecursiveEngine:
    """Execute, independently evaluate, retrieve context, learn, and stop safely."""

    def __init__(
        self, executor: Executor, evaluator: Evaluator | None = None,
        artifact_dir: Path | None = None, memory_store: MemoryStore | None = None,
        memory_limit: int = 5, agent_id: str | None = None,
        knowledge_extractor: KnowledgeExtractor | None = None,
    ) -> None:
        if memory_limit < 1:
            raise ValueError("memory_limit must be at least 1")
        self.executor = executor
        self.evaluator = evaluator or CriteriaEvaluator()
        self.artifact_dir = artifact_dir
        self.memory_store = memory_store
        self.memory_limit = memory_limit
        self.agent_id = agent_id
        self.knowledge_extractor = knowledge_extractor

    def run(self, task: Task) -> RunReport:
        report = RunReport.new(task.objective)
        report.add_event("run_started", "Execution started.")
        working_memory = WorkingMemory(run_id=report.run_id, project_id=task.project_id)
        if self.memory_store is not None:
            try:
                query = " ".join((task.objective, *task.acceptance_criteria))
                working_memory.retrieved_memories = tuple(self.memory_store.search(
                    query, project_id=task.project_id, limit=self.memory_limit, agent_id=self.agent_id,
                ))
                identifiers = ", ".join(match.record.id for match in working_memory.retrieved_memories)
                report.add_event(
                    "memory_retrieved",
                    f"Retrieved {len(working_memory.retrieved_memories)} approved memories: {identifiers}",
                )
            except Exception as exc:
                report.add_event("memory_read_error", f"Memory retrieval unavailable: {type(exc).__name__}.")

        for iteration in range(1, task.max_iterations + 1):
            report.iterations = iteration
            working_memory.iteration = iteration
            if iteration > 1:
                working_memory.previous_candidate = working_memory.current_candidate
            report.add_event("iteration_started", f"Iteration {iteration} started.")
            try:
                execute_with_memory = getattr(self.executor, "execute_with_memory", None)
                if callable(execute_with_memory):
                    candidate = execute_with_memory(task, working_memory)
                else:
                    candidate = self.executor.execute(task, working_memory.feedback, iteration)
            except Exception as exc:
                report.status = RunStatus.FAILED
                report.add_event("executor_error", f"Executor failed: {type(exc).__name__}: {exc}")
                break

            if not isinstance(candidate, str) or not candidate.strip():
                candidate = ""
                report.add_event("executor_warning", "Executor returned an empty or invalid candidate.")
            report.final_output = candidate
            working_memory.current_candidate = candidate
            try:
                evaluation = self.evaluator.evaluate(task, candidate)
            except Exception as exc:
                report.status = RunStatus.FAILED
                report.add_event("evaluator_error", f"Evaluator failed: {type(exc).__name__}: {exc}")
                break

            report.evaluations.append(evaluation)
            if evaluation.passed:
                report.add_event("evaluation_passed", f"All {len(evaluation.satisfied)} criteria satisfied.")
                report.status = RunStatus.PASSED
                report.add_event("run_completed", "Independent evaluation passed.")
                break
            report.add_event("evaluation_failed", f"Missing criteria: {', '.join(evaluation.missing)}")
            working_memory.feedback = evaluation.missing
        else:
            report.status = RunStatus.LIMIT_REACHED
            report.add_event("iteration_limit_reached", f"No passing candidate after {task.max_iterations} iterations.")

        self._remember(task, report)
        report.add_event("run_finished", f"Run finished with status: {report.status.value}.")
        self._persist(report)
        return report

    def _remember(self, task: Task, report: RunReport) -> None:
        if self.memory_store is None:
            return
        event_sequences = tuple(event.sequence for event in report.events)
        episode = MemoryRecord.create(
            project_id=task.project_id,
            memory_type=MemoryType.EPISODIC,
            content=(
                f"Objective: {task.objective}\nStatus: {report.status.value}\n"
                f"Acceptance criteria: {', '.join(task.acceptance_criteria)}\n"
                f"Iterations: {report.iterations}\nFinal output:\n{report.final_output}"
            ),
            summary=f"{report.status.value}: {task.objective}",
            source_run_id=report.run_id,
            source_event_sequences=event_sequences,
            agent_id=self.agent_id,
            tags=("run", report.status.value),
            confidence=0.95,
            metadata={
                "iterations": report.iterations,
                "evaluation_count": len(report.evaluations),
                "missing_criteria": list(report.evaluations[-1].missing) if report.evaluations else [],
            },
        )
        try:
            self.memory_store.save(episode)
            extracted = 0
            if report.status is RunStatus.PASSED:
                if self.knowledge_extractor is not None:
                    lessons = self.knowledge_extractor.extract(
                        task, report.final_output, source_run_id=report.run_id,
                        source_event_sequences=event_sequences, agent_id=self.agent_id,
                    )
                else:
                    lessons = extract_reusable_knowledge(
                        project_id=task.project_id,
                        source_run_id=report.run_id,
                        source_event_sequences=event_sequences,
                        candidate=report.final_output,
                        agent_id=self.agent_id,
                    )
                for lesson in lessons:
                    self.memory_store.save(lesson)
                    extracted += 1
            report.add_event(
                "memory_saved",
                f"Run episode stored; {extracted} semantic memories queued for approval.",
            )
        except Exception as exc:
            report.add_event("memory_write_error", f"Memory persistence or extraction unavailable: {type(exc).__name__}.")

    def _persist(self, report: RunReport) -> None:
        if self.artifact_dir is None:
            return
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / f"{report.run_id}.json"
        path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
