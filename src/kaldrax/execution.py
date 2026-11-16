"""Executor port, offline example, and LLM-backed implementation."""
import json
from typing import Protocol

from .llm import ChatClient
from .models import Task


class Executor(Protocol):
    def execute(self, task: Task, feedback: tuple[str, ...], iteration: int) -> str:
        """Produce one candidate artifact."""


class ExampleExecutor:
    """Deterministic offline executor used by the demo and tests."""

    def execute(self, task: Task, feedback: tuple[str, ...], iteration: int) -> str:
        if iteration == 1:
            return f"Initial draft for: {task.objective}"
        included = "\n".join(f"- {criterion}" for criterion in task.acceptance_criteria)
        return f"Revised deliverable for: {task.objective}\n{included}"


class LLMExecutor:
    """Ask a configured chat model to produce one candidate per iteration."""

    def __init__(self, client: ChatClient) -> None:
        self.client = client

    def execute(self, task: Task, feedback: tuple[str, ...], iteration: int) -> str:
        system_prompt = (
            "You are the artifact-producing executor in KALDRAX. Produce the requested "
            "engineering artifact, not a report about what you would do. Address every "
            "acceptance criterion. Treat feedback as correction guidance. Do not claim "
            "that commands, tests, deployments, or external actions ran unless their "
            "results are included in the supplied context. Return the candidate only."
        )
        user_prompt = json.dumps(
            {
                "objective": task.objective,
                "acceptance_criteria": list(task.acceptance_criteria),
                "iteration": iteration,
                "max_iterations": task.max_iterations,
                "previous_evaluation_feedback": list(feedback),
            },
            ensure_ascii=False,
            indent=2,
        )
        return self.client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
