import json

import pytest

from kaldrax.evaluation import CriteriaEvaluator, EvaluationError, LLMEvaluator
from kaldrax.models import Task


def test_deterministic_evaluator_uses_whole_phrase_boundaries_and_records_quote():
    task = Task("Check candidate", ("test", "deployment summary"))
    result = CriteriaEvaluator().evaluate(task, "The test passed. Deployment   summary follows.")
    assert result.passed
    assert result.satisfied == ("test", "deployment summary")
    assert result.evidence[0].quote == "test"


def test_deterministic_evaluator_does_not_accept_substrings():
    task = Task("Check candidate", ("test",))
    result = CriteriaEvaluator().evaluate(task, "The latest tests passed.")
    assert not result.passed
    assert result.missing == ("test",)


class FakeChatClient:
    def __init__(self, output):
        self.output = output
        self.prompts = None

    def complete(self, *, system_prompt, user_prompt):
        self.prompts = (system_prompt, user_prompt)
        return self.output


def test_llm_evaluator_requires_verbatim_evidence_and_derives_overall_pass():
    task = Task("Implement feature", ("unit tests pass", "docs updated"))
    payload = {
        "criteria": [
            {"criterion": "unit tests pass", "passed": True, "evidence": "All unit tests pass."},
            {"criterion": "docs updated", "passed": True, "evidence": "Documentation updated."},
        ]
    }
    result = LLMEvaluator(FakeChatClient(json.dumps(payload))).evaluate(
        task, "All unit tests pass. Documentation updated."
    )
    assert result.passed
    assert result.missing == ()
    assert len(result.evidence) == 2


def test_llm_evaluator_rejects_fabricated_quotes_even_when_judge_says_pass():
    task = Task("Implement feature", ("unit tests pass",))
    payload = {"criteria": [{"criterion": "unit tests pass", "passed": True, "evidence": "Tests ran successfully."}]}
    result = LLMEvaluator(FakeChatClient(json.dumps(payload))).evaluate(task, "No test output was provided.")
    assert not result.passed
    assert result.missing == ("unit tests pass",)
    assert result.evidence == ()


@pytest.mark.parametrize("payload", [
    "not json",
    json.dumps({"result": []}),
    json.dumps({"criteria": [{"criterion": "other", "passed": True, "evidence": "x"}]}),
    json.dumps({"criteria": [{"criterion": "a", "passed": True, "evidence": "a"}, {"criterion": "a", "passed": True, "evidence": "a"}]}),
    json.dumps({"criteria": []}),
])
def test_llm_evaluator_rejects_malformed_or_incomplete_contracts(payload):
    task = Task("Check", ("a",))
    with pytest.raises(EvaluationError):
        LLMEvaluator(FakeChatClient(payload)).evaluate(task, "a")
