import json
import threading
import time

import pytest

from kaldrax.orchestration import (
    CheckpointStore,
    RetryPolicy,
    RetryableTaskError,
    TaskDecomposer,
    TaskGraph,
    TaskGraphError,
    TaskGraphScheduler,
    TaskNode,
    TaskState,
)


class Planner:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def complete(self, *, system_prompt, user_prompt):
        self.prompts.append((system_prompt, json.loads(user_prompt)))
        return self.response


def test_decomposer_builds_valid_dependency_graph():
    planner = Planner(json.dumps({"tasks": [
        {"id": "api", "description": "Build API", "depends_on": [], "acceptance_criteria": ["API works"]},
        {"id": "ui", "description": "Build UI", "depends_on": [], "acceptance_criteria": ["UI works"]},
        {"id": "integration", "description": "Integrate", "depends_on": ["api", "ui"], "acceptance_criteria": ["Flow works"]},
    ]}))
    graph = TaskDecomposer(planner).decompose("Build product", ("working product",))
    assert len(graph.tasks) == 3
    assert graph.tasks[2].depends_on == ("api", "ui")
    assert planner.prompts[0][1]["constraints"]["independent_work_should_be_parallel"] is True


@pytest.mark.parametrize("tasks", [
    [{"id": "a", "description": "A", "depends_on": ["missing"]}],
    [
        {"id": "a", "description": "A", "depends_on": ["b"]},
        {"id": "b", "description": "B", "depends_on": ["a"]},
    ],
    [{"id": "a", "description": "A"}, {"id": "a", "description": "duplicate"}],
])
def test_graph_rejects_invalid_dependency_structures(tasks):
    with pytest.raises(TaskGraphError):
        TaskGraph("objective", tuple(
            TaskNode(row["id"], row["description"], tuple(row.get("depends_on", ())))
            for row in tasks
        ))


def test_decomposer_rejects_malformed_planner_output():
    with pytest.raises(TaskGraphError):
        TaskDecomposer(Planner('{"tasks":"not a list"}')).decompose("Build")


def test_independent_tasks_run_in_parallel_and_join_after_dependencies():
    graph = TaskGraph("build", (
        TaskNode("a", "A"),
        TaskNode("b", "B"),
        TaskNode("join", "Join", ("a", "b")),
    ))
    active = 0
    peak = 0
    lock = threading.Lock()

    def execute(task):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.04)
        with lock:
            active -= 1
        return f"done:{task.id}"

    report = TaskGraphScheduler(max_workers=2).run(graph, execute)
    assert report.passed
    assert peak == 2
    assert report.outputs["join"] == "done:join"


def test_failure_blocks_descendants_but_not_independent_work():
    graph = TaskGraph("build", (
        TaskNode("bad", "Fails"),
        TaskNode("dependent", "Needs bad", ("bad",)),
        TaskNode("independent", "Still runs"),
    ))
    report = TaskGraphScheduler().run(
        graph,
        lambda task: (_ for _ in ()).throw(ValueError("invalid")) if task.id == "bad" else "ok",
    )
    assert report.states == {
        "bad": TaskState.FAILED.value,
        "dependent": TaskState.BLOCKED.value,
        "independent": TaskState.SUCCEEDED.value,
    }


def test_transient_failure_retries_with_backoff_and_then_succeeds():
    graph = TaskGraph("build", (TaskNode("a", "A"),))
    calls = []
    delays = []

    def execute(task):
        calls.append(task.id)
        if len(calls) == 1:
            raise RetryableTaskError("temporary provider outage")
        return "recovered"

    report = TaskGraphScheduler(
        retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.1),
        sleep=delays.append,
    ).run(graph, execute)
    assert report.passed
    assert report.attempts["a"] == 2
    assert delays == [0.1]
    assert any(event["event"] == "task_retry_scheduled" for event in report.events)


def test_permanent_failure_escalates_without_retry():
    graph = TaskGraph("build", (TaskNode("a", "A"),))
    escalations = []
    report = TaskGraphScheduler().run(
        graph,
        lambda task: (_ for _ in ()).throw(ValueError("bad input")),
        escalate=lambda task, error: escalations.append((task.id, str(error))),
    )
    assert report.states["a"] == TaskState.FAILED.value
    assert report.attempts["a"] == 1
    assert escalations == [("a", "bad input")]
    assert any(event["event"] == "task_escalated" for event in report.events)


def test_checkpoint_resumes_successful_work_without_reexecuting(tmp_path):
    graph = TaskGraph("build", (
        TaskNode("a", "A"),
        TaskNode("b", "B", ("a",)),
    ))
    store = CheckpointStore(tmp_path / "run.json")
    first_calls = []
    first = TaskGraphScheduler().run(
        graph,
        lambda task: first_calls.append(task.id) or "a-result",
        checkpoint_store=store,
    )
    assert first.passed
    second_calls = []
    second = TaskGraphScheduler().run(
        graph,
        lambda task: second_calls.append(task.id) or "new-result",
        checkpoint_store=store,
    )
    assert first_calls == ["a", "b"]
    assert second_calls == []
    assert second.outputs == {"a": "a-result", "b": "a-result"}


def test_checkpoint_is_bound_to_exact_graph(tmp_path):
    store = CheckpointStore(tmp_path / "run.json")
    graph = TaskGraph("build", (TaskNode("a", "A"),))
    TaskGraphScheduler().run(graph, lambda task: "ok", checkpoint_store=store)
    changed = TaskGraph("build changed", (TaskNode("a", "A"),))
    with pytest.raises(TaskGraphError, match="does not match"):
        store.load(changed)


def test_resume_can_explicitly_retry_failed_nodes(tmp_path):
    graph = TaskGraph("build", (TaskNode("a", "A"),))
    store = CheckpointStore(tmp_path / "run.json")
    TaskGraphScheduler().run(
        graph, lambda task: (_ for _ in ()).throw(ValueError("no")),
        checkpoint_store=store,
    )
    retried = TaskGraphScheduler().run(
        graph, lambda task: "fixed",
        checkpoint_store=store, retry_failed=True,
    )
    assert retried.passed
    assert retried.outputs["a"] == "fixed"


def test_decomposer_rejects_string_instead_of_dependency_array():
    planner = Planner(json.dumps({"tasks": [
        {"id": "a", "description": "A", "depends_on": "other"}
    ]}))
    with pytest.raises(TaskGraphError):
        TaskDecomposer(planner).decompose("Build")


def test_checkpointed_running_task_resumes_with_remaining_attempt_budget(tmp_path):
    from kaldrax.orchestration import ExecutionCheckpoint, NodeCheckpoint

    graph = TaskGraph("build", (TaskNode("a", "A"),))
    store = CheckpointStore(tmp_path / "run.json")
    store.save(ExecutionCheckpoint(
        1, graph.fingerprint(),
        {"a": NodeCheckpoint(state=TaskState.RUNNING, attempts=1)},
        [],
    ))
    report = TaskGraphScheduler(
        retry_policy=RetryPolicy(max_attempts=2),
    ).run(graph, lambda task: "resumed", checkpoint_store=store)
    assert report.passed
    assert report.attempts["a"] == 2
