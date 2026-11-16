import pytest

from kaldrax.budgets import BudgetExceeded, RunBudget


def test_run_budget_reserves_and_settles_actual_usage():
    budget = RunBudget(
        max_calls=2, max_input_tokens=100, max_output_tokens=40, max_total_tokens=120,
    )
    reservation = budget.reserve(prompt_bytes=20, requested_output_tokens=30)
    assert reservation.output_tokens_reserved == 30
    budget.settle(reservation, prompt_tokens=8, completion_tokens=12)
    snapshot = budget.snapshot()
    assert snapshot.calls == 1
    assert snapshot.input_tokens == 8
    assert snapshot.output_tokens == 12
    assert snapshot.total_tokens == 20


def test_run_budget_rejects_call_and_total_token_overruns():
    budget = RunBudget(
        max_calls=1, max_input_tokens=100, max_output_tokens=10, max_total_tokens=30,
    )
    reservation = budget.reserve(prompt_bytes=10, requested_output_tokens=100)
    assert reservation.output_tokens_reserved == 10
    budget.settle(reservation, prompt_tokens=10, completion_tokens=10)
    with pytest.raises(BudgetExceeded, match="call budget"):
        budget.reserve(prompt_bytes=1, requested_output_tokens=1)


def test_run_budget_clamps_completion_to_remaining_output_budget():
    budget = RunBudget(
        max_calls=3, max_input_tokens=100, max_output_tokens=12, max_total_tokens=100,
    )
    first = budget.reserve(prompt_bytes=2, requested_output_tokens=10)
    budget.settle(first, prompt_tokens=2, completion_tokens=8)
    second = budget.reserve(prompt_bytes=2, requested_output_tokens=10)
    assert second.output_tokens_reserved == 4
    budget.record_failed_request(second)
    assert budget.snapshot().calls == 2


def test_monetary_budget_requires_rates_and_preflights_max_completion_cost():
    with pytest.raises(ValueError, match="requires input and output"):
        RunBudget(max_cost_usd=0.10)

    budget = RunBudget(
        max_calls=2, max_input_tokens=100, max_output_tokens=100, max_total_tokens=200,
        max_cost_usd=0.00001,
        input_cost_per_million_usd=1,
        output_cost_per_million_usd=100,
    )
    with pytest.raises(BudgetExceeded, match="monetary"):
        budget.reserve(prompt_bytes=10, requested_output_tokens=100)


def test_run_budget_rejects_provider_usage_exceeding_reserved_limits():
    budget = RunBudget(
        max_calls=1, max_input_tokens=50, max_output_tokens=5, max_total_tokens=55,
    )
    reservation = budget.reserve(prompt_bytes=10, requested_output_tokens=5)
    with pytest.raises(BudgetExceeded, match="after the request"):
        budget.settle(reservation, prompt_tokens=10, completion_tokens=6)
