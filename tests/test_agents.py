import json

from kaldrax.agents import MultiAgentCoordinator
from kaldrax.evaluation import CriteriaEvaluator
from kaldrax.memory import SQLiteMemoryStore
from kaldrax.models import RunStatus, Task


class SequenceClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def complete(self, *, system_prompt, user_prompt):
        self.prompts.append((system_prompt, json.loads(user_prompt)))
        return self.responses.pop(0)


def test_team_pass_requires_reviewer_and_independent_evaluator(tmp_path):
    planner = SequenceClient("1. Define approach. 2. Verify output.")
    builder = SequenceClient("The implementation is complete.")
    reviewer = SequenceClient(json.dumps({
        "approved": True, "findings": [], "summary": "No blocking findings."
    }))
    report = MultiAgentCoordinator(
        planner=planner, builder=builder, reviewer=reviewer,
        evaluator=CriteriaEvaluator(), artifact_dir=tmp_path,
    ).run(Task("Complete implementation", ("implementation is complete",), project_id="p"))

    assert report.status is RunStatus.PASSED
    assert report.cycles == 1
    assert [step.role for step in report.trace] == ["planner", "builder", "reviewer"]
    assert report.evaluation.passed
    assert (tmp_path / f"team-{report.run_id}.json").exists()


def test_team_retries_on_reviewer_feedback_before_final_pass():
    planner = SequenceClient("Implementation plan")
    builder = SequenceClient("incomplete draft", "required output is complete")
    reviewer = SequenceClient(
        json.dumps({"approved": False, "findings": ["Add required output"], "summary": "Incomplete"}),
        json.dumps({"approved": True, "findings": [], "summary": "Looks correct"}),
    )
    report = MultiAgentCoordinator(
        planner=planner, builder=builder, reviewer=reviewer,
        evaluator=CriteriaEvaluator(), max_cycles=2,
    ).run(Task("Build feature", ("required output is complete",)))

    assert report.status is RunStatus.PASSED
    assert report.cycles == 2
    assert report.cycle_results[0].reviewer_approved is False
    assert "Add required output" in builder.prompts[1][1]["review_feedback"]


def test_team_does_not_pass_when_reviewer_rejects_even_if_evaluator_passes():
    planner = SequenceClient("Implementation plan")
    builder = SequenceClient("required output is complete")
    reviewer = SequenceClient(json.dumps({
        "approved": False, "findings": ["Security review incomplete"], "summary": "Not approved"
    }))
    report = MultiAgentCoordinator(
        planner=planner, builder=builder, reviewer=reviewer,
        evaluator=CriteriaEvaluator(), max_cycles=1,
    ).run(Task("Build feature", ("required output is complete",)))
    assert report.status is RunStatus.LIMIT_REACHED
    assert report.cycle_results[0].evaluation_passed is True


def test_team_memory_is_agent_scoped(tmp_path):
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    planner = SequenceClient("Plan")
    builder = SequenceClient("required output is complete")
    reviewer = SequenceClient(json.dumps({"approved": True, "findings": []}))
    report = MultiAgentCoordinator(
        planner=planner, builder=builder, reviewer=reviewer,
        evaluator=CriteriaEvaluator(), memory_store=store,
    ).run(Task("Build feature", ("required output is complete",), project_id="p"))
    assert report.status is RunStatus.PASSED
    planner_memory = store.search("Build feature", project_id="p", agent_id="team:planner")
    builder_memory = store.search("Build feature", project_id="p", agent_id="team:builder")
    assert planner_memory and planner_memory[0].record.agent_id == "team:planner"
    assert builder_memory and builder_memory[0].record.agent_id == "team:builder"
    store.close()


def test_team_progress_sink_reports_each_role():
    progress = []
    report = MultiAgentCoordinator(
        planner=SequenceClient("Plan"),
        builder=SequenceClient("required output is complete"),
        reviewer=SequenceClient(json.dumps({"approved": True, "findings": []})),
        evaluator=CriteriaEvaluator(),
        progress_sink=progress.append,
    ).run(Task("Build feature", ("required output is complete",)))
    types = [event["event_type"] for event in progress]
    assert report.status is RunStatus.PASSED
    assert "planner_completed" in types
    assert "builder_completed" in types
    assert "reviewer_completed" in types
    assert types[-1] == "team_run_passed"
