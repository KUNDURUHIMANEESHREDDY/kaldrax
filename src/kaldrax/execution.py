"""Executor port and deterministic offline example."""
from typing import Protocol
from .models import Task

class Executor(Protocol):
    def execute(self, task: Task, feedback: tuple[str, ...], iteration: int) -> str:
        """Produce one candidate artifact."""

class ExampleExecutor:
    def execute(self, task: Task, feedback: tuple[str, ...], iteration: int) -> str:
        if iteration == 1:
            return f"Initial draft for: {task.objective}"
        included = "\n".join(f"- {criterion}" for criterion in task.acceptance_criteria)
        return f"Revised deliverable for: {task.objective}\n{included}"
