"""Stable domain models for a bounded KALDRAX run."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class RunStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    LIMIT_REACHED = "limit_reached"


@dataclass(frozen=True)
class Task:
    objective: str
    acceptance_criteria: tuple[str, ...]
    max_iterations: int = 3

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("objective must not be empty")
        if not self.acceptance_criteria or any(not c.strip() for c in self.acceptance_criteria):
            raise ValueError("non-empty acceptance criteria are required")
        if len(set(self.acceptance_criteria)) != len(self.acceptance_criteria):
            raise ValueError("acceptance criteria must be unique")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")


@dataclass(frozen=True)
class CriterionEvidence:
    criterion: str
    quote: str


@dataclass(frozen=True)
class Evaluation:
    passed: bool
    satisfied: tuple[str, ...]
    missing: tuple[str, ...]
    evaluator: str = "deterministic-criteria-v2"
    evidence: tuple[CriterionEvidence, ...] = ()


@dataclass(frozen=True)
class RunEvent:
    sequence: int
    event_type: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RunReport:
    run_id: str
    objective: str
    status: RunStatus
    iterations: int
    final_output: str
    evaluations: list[Evaluation]
    events: list[RunEvent]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def new(cls, objective: str) -> "RunReport":
        return cls(str(uuid4()), objective, RunStatus.FAILED, 0, "", [], [])

    def add_event(self, event_type: str, message: str) -> None:
        self.events.append(RunEvent(len(self.events) + 1, event_type, message))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data
