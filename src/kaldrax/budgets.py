"""Shared, enforceable budgets for provider calls in one KALDRAX run."""
from __future__ import annotations

import math
import threading
from dataclasses import asdict, dataclass
from uuid import uuid4


class BudgetExceeded(RuntimeError):
    """Raised before a provider request when its reservation exceeds the run budget."""


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: str
    input_tokens_reserved: int
    output_tokens_reserved: int
    cost_usd_reserved: float


@dataclass(frozen=True)
class BudgetSnapshot:
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    max_calls: int
    max_input_tokens: int
    max_output_tokens: int
    max_total_tokens: int
    max_cost_usd: float | None
    cost_is_estimated: bool

    def to_dict(self) -> dict[str, int | float | bool | None]:
        return asdict(self)


class RunBudget:
    """A thread-safe ledger shared by all models/agents in one run.

    Before sending a request, KALDRAX reserves a conservative prompt-token
    estimate (UTF-8 byte count) and the requested completion ceiling. Provider
    usage replaces the estimate when returned. Missing usage remains estimated.
    Cost enforcement is enabled only when both model rates are configured.
    """

    def __init__(
        self,
        *,
        max_calls: int = 20,
        max_input_tokens: int = 60_000,
        max_output_tokens: int = 12_000,
        max_total_tokens: int = 72_000,
        max_cost_usd: float | None = None,
        input_cost_per_million_usd: float | None = None,
        output_cost_per_million_usd: float | None = None,
    ) -> None:
        limits = (max_calls, max_input_tokens, max_output_tokens, max_total_tokens)
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in limits):
            raise ValueError("all token and call budgets must be positive")
        if max_total_tokens < 2:
            raise ValueError("max_total_tokens must be at least 2")
        if max_cost_usd is not None:
            if not math.isfinite(max_cost_usd) or max_cost_usd <= 0:
                raise ValueError("max_cost_usd must be positive")
            if input_cost_per_million_usd is None or output_cost_per_million_usd is None:
                raise ValueError("cost budget requires input and output model rates")
        for rate in (input_cost_per_million_usd, output_cost_per_million_usd):
            if rate is not None and (not math.isfinite(rate) or rate < 0):
                raise ValueError("model token rates cannot be negative")

        self.max_calls = max_calls
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.max_total_tokens = max_total_tokens
        self.max_cost_usd = max_cost_usd
        self.input_rate = input_cost_per_million_usd
        self.output_rate = output_cost_per_million_usd

        self._calls = 0
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost_usd = 0.0
        self._reserved_input = 0
        self._reserved_output = 0
        self._reserved_cost = 0.0
        self._reservations: dict[str, BudgetReservation] = {}
        self._lock = threading.Lock()

    def reserve(self, prompt_bytes: int, requested_output_tokens: int) -> BudgetReservation:
        if (not isinstance(prompt_bytes, int) or isinstance(prompt_bytes, bool)
                or not isinstance(requested_output_tokens, int) or isinstance(requested_output_tokens, bool)
                or prompt_bytes < 0 or requested_output_tokens < 1):
            raise ValueError("prompt size must be non-negative and output limit positive")
        # Byte count is deliberately conservative and avoids an unconfigured tokenizer.
        estimated_input = max(1, prompt_bytes)
        with self._lock:
            if self._calls >= self.max_calls:
                raise BudgetExceeded(f"provider call budget exhausted ({self.max_calls})")
            input_remaining = self.max_input_tokens - self._input_tokens - self._reserved_input
            total_remaining = (
                self.max_total_tokens - self._input_tokens - self._output_tokens
                - self._reserved_input - self._reserved_output
            )
            output_remaining = self.max_output_tokens - self._output_tokens - self._reserved_output
            if estimated_input > input_remaining or estimated_input >= total_remaining:
                raise BudgetExceeded("prompt exceeds the remaining run input/total token budget")
            output_reserved = min(requested_output_tokens, output_remaining, total_remaining - estimated_input)
            if output_reserved < 1:
                raise BudgetExceeded("no completion tokens remain in the run budget")

            cost_reserved = 0.0
            if self.max_cost_usd is not None:
                cost_reserved = (
                    estimated_input * float(self.input_rate)
                    + output_reserved * float(self.output_rate)
                ) / 1_000_000
                if self._cost_usd + self._reserved_cost + cost_reserved > self.max_cost_usd:
                    raise BudgetExceeded("request would exceed the configured monetary budget")

            reservation = BudgetReservation(
                str(uuid4()), estimated_input, output_reserved, cost_reserved
            )
            self._calls += 1
            self._reserved_input += estimated_input
            self._reserved_output += output_reserved
            self._reserved_cost += cost_reserved
            self._reservations[reservation.reservation_id] = reservation
            return reservation

    def settle(
        self,
        reservation: BudgetReservation,
        *,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        completion_bytes: int = 0,
    ) -> None:
        with self._lock:
            current = self._reservations.pop(reservation.reservation_id, None)
            if current is None:
                return
            self._reserved_input -= current.input_tokens_reserved
            self._reserved_output -= current.output_tokens_reserved
            self._reserved_cost -= current.cost_usd_reserved

            actual_input = current.input_tokens_reserved if prompt_tokens is None else prompt_tokens
            actual_output = max(0, completion_bytes) if completion_tokens is None else completion_tokens
            if actual_input < 0 or actual_output < 0:
                raise ValueError("provider usage cannot be negative")
            self._input_tokens += actual_input
            self._output_tokens += actual_output
            if self.max_cost_usd is not None:
                self._cost_usd += (
                    actual_input * float(self.input_rate)
                    + actual_output * float(self.output_rate)
                ) / 1_000_000

            violations = []
            if self._input_tokens > self.max_input_tokens:
                violations.append("input-token")
            if self._output_tokens > self.max_output_tokens:
                violations.append("output-token")
            if self._input_tokens + self._output_tokens > self.max_total_tokens:
                violations.append("total-token")
            if self.max_cost_usd is not None and self._cost_usd > self.max_cost_usd:
                violations.append("monetary")
            if violations:
                raise BudgetExceeded(
                    "provider-reported usage exceeded run budget after the request: "
                    + ", ".join(violations)
                )

    def record_failed_request(self, reservation: BudgetReservation) -> None:
        """Release output reservation but conservatively count prompt bytes for attempted calls."""
        self.settle(reservation, completion_tokens=0)

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            return BudgetSnapshot(
                calls=self._calls,
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                total_tokens=self._input_tokens + self._output_tokens,
                estimated_cost_usd=round(self._cost_usd, 8),
                max_calls=self.max_calls,
                max_input_tokens=self.max_input_tokens,
                max_output_tokens=self.max_output_tokens,
                max_total_tokens=self.max_total_tokens,
                max_cost_usd=self.max_cost_usd,
                cost_is_estimated=self.max_cost_usd is not None,
            )
