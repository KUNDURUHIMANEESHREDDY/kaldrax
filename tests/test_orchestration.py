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


def test_decomposer_uses_repository_context_and_emits_topological_plan():
    repository_context = {
        "files": [
            {"path": "config/settings.py", "imports": [], "exports": ["JWT_SECRET"]},
            {"path": "models/user.py", "imports": [], "exports": ["User"]},
            {"path": "auth/jwt.py", "imports": ["config.settings"], "exports": ["create_token"]},
            {"path": "routes/auth.py", "imports": ["auth.jwt", "models.user"], "exports": ["login"]},
            {"path": "tests/test_auth.py", "imports": ["routes.auth"], "exports": []},
        ],
        "dependencies": [
            {"source": "auth/jwt.py", "target": "config/settings.py"},
            {"source": "routes/auth.py", "target": "auth/jwt.py"},
            {"source": "routes/auth.py", "target": "models/user.py"},
            {"source": "tests/test_auth.py", "target": "routes/auth.py"},
        ],
        "test_files": ["tests/test_auth.py", "tests/test_middleware.py"],
    }
    planner = Planner(json.dumps({"tasks": [
        {
            "id": "add-auth-tests", "phase": "tests",
            "description": "Add JWT route and middleware regression tests",
            "file_scope": ["tests/test_auth.py", "tests/test_middleware.py"],
            "depends_on": ["wire-api"],
            "acceptance_criteria": ["Authentication behavior is covered"],
        },
        {
            "id": "wire-api", "phase": "api",
            "description": "Add auth routes and request middleware",
            "file_scope": ["routes/auth.py", "middleware/auth.py"],
            "depends_on": ["implement-security", "add-user-model"],
            "acceptance_criteria": ["Protected routes validate bearer tokens"],
        },
        {
            "id": "implement-security", "phase": "security",
            "description": "Implement JWT signing and password hashing",
            "file_scope": ["auth/jwt.py", "auth/passwords.py"],
            "depends_on": ["configure-jwt"],
            "acceptance_criteria": ["Tokens are signed and passwords are hashed"],
        },
        {
            "id": "add-user-model", "phase": "data",
            "description": "Add the user model and persistence fields",
            "file_scope": ["models/user.py"],
            "depends_on": [],
            "acceptance_criteria": ["Users have stable identity and password hash fields"],
        },
        {
            "id": "configure-jwt", "phase": "configuration",
            "description": "Add JWT key, algorithm and expiry settings",
            "file_scope": ["config/settings.py"],
            "depends_on": [],
            "acceptance_criteria": ["JWT settings are loaded from configuration"],
        },
    ]}))
    graph = TaskDecomposer(planner).decompose(
        "Add JWT authentication to the API",
        repository_context=repository_context,
    )
    assert planner.prompts[0][1]["repository_context"] == repository_context
    assert planner.prompts[0][1]["constraints"]["file_scope_required_for_every_task"] is True
    assert [[node.id for node in wave] for wave in graph.execution_waves] == [
        ["add-user-model", "configure-jwt"],
        ["implement-security"],
        ["wire-api"],
        ["add-auth-tests"],
    ]
    assert [node.id for node in graph.execution_order] == [
        "add-user-model", "configure-jwt", "implement-security", "wire-api", "add-auth-tests",
    ]
    assert graph.execution_order[2].file_scope == ("auth/jwt.py", "auth/passwords.py")


def test_decomposer_requires_phase_and_file_scope_for_repository_plans():
    planner = Planner(json.dumps({"tasks": [{
        "id": "configure", "description": "Add config", "depends_on": [],
        "acceptance_criteria": ["Configuration works"],
    }]}))
    with pytest.raises(TaskGraphError, match="phase and repository file_scope"):
        TaskDecomposer(planner).decompose("Add config", repository_context={"files": []})


@pytest.mark.parametrize("file_scope", [
    ("../outside.py",), ("/etc/passwd",), (".git/config",), (".",),
    (r"src\\outside.py",), (".env",), (".env.production",),
])
def test_task_node_rejects_unsafe_file_scope(file_scope):
    with pytest.raises(TaskGraphError, match="unsafe repository path"):
        TaskNode("unsafe", "Unsafe file scope", file_scope=file_scope)


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


def test_scheduler_respects_topological_order_when_plan_lists_consumers_first():
    graph = TaskGraph("auth", (
        TaskNode("tests", "Verify authentication", ("api",)),
        TaskNode("api", "Add routes and middleware", ("security",)),
        TaskNode("security", "Implement JWT helpers", ("config",)),
        TaskNode("config", "Add JWT settings"),
    ))
    started = []
    report = TaskGraphScheduler(max_workers=4).run(
        graph,
        lambda node: started.append(node.id) or f"completed:{node.id}",
    )
    assert report.passed
    assert started == ["config", "security", "api", "tests"]


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



def test_cli_orchestration_requires_final_reviewer_and_independent_evaluator(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    import kaldrax.cli as cli
    from kaldrax.budgets import RunBudget

    class RoleClient:
        def __init__(self, role):
            self.role = role
            self.calls = 0

        def complete(self, *, system_prompt, user_prompt):
            self.calls += 1
            if self.role == "planner":
                return json.dumps({"tasks": [{
                    "id": "core", "description": "Implement core",
                    "depends_on": [], "acceptance_criteria": ["alpha delivered"],
                }]})
            if self.role == "builder":
                return "alpha delivered"
            if self.role == "reviewer":
                return json.dumps({
                    "approved": True, "findings": [], "summary": "Aggregate is sound.",
                })
            if self.role == "evaluator":
                return json.dumps({"criteria": [{
                    "criterion": "alpha delivered", "passed": True,
                    "evidence": "alpha delivered",
                }]})
            raise AssertionError(self.role)

    clients = {role: RoleClient(role) for role in ("planner", "builder", "reviewer", "evaluator")}
    monkeypatch.setenv("KALDRAX_API_KEY", "test-key")
    monkeypatch.setenv("KALDRAX_PLANNER_MODEL", "planner-model")
    monkeypatch.setenv("KALDRAX_MODEL", "builder-model")
    monkeypatch.setenv("KALDRAX_REVIEWER_MODEL", "reviewer-model")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "evaluator-model")
    monkeypatch.setattr(cli, "_budget_from_env", RunBudget)
    monkeypatch.setattr(cli, "_client", lambda model, budget: clients[model.removesuffix("-model")])

    args = SimpleNamespace(
        objective="Build core", criterion=["alpha delivered"],
        max_workers=2, max_attempts=2, checkpoint=tmp_path / "checkpoint.json",
        fresh=True, retry_failed=False, progress_jsonl=None,
        artifact=tmp_path / "report.json",
    )
    assert cli._orchestrate(args) == 0
    report = json.loads(args.artifact.read_text(encoding="utf-8"))
    assert report["task_graph_passed"] is True
    assert report["reviewer_approved"] is True
    assert report["evaluation"]["passed"] is True
    assert report["passed"] is True
    assert clients["reviewer"].calls == 1
    assert clients["evaluator"].calls == 1
    assert "final_review_completed" in [event["event"] for event in report["events"]]
    capsys.readouterr()



def test_cli_orchestration_passes_task_outputs_through_repository_patch_and_apply(
    tmp_path, monkeypatch, capsys,
):
    import subprocess
    from types import SimpleNamespace

    import kaldrax.cli as cli
    from kaldrax.budgets import RunBudget
    from kaldrax.sandbox import SandboxResult

    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "operations.py").write_text(
        "def subtract(left: int, right: int) -> int:\n"
        "    raise NotImplementedError\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_operations.py").write_text(
        "import unittest\n"
        "from src.operations import subtract\n\n"
        "class SubtractTests(unittest.TestCase):\n"
        "    def test_subtract(self):\n"
        "        self.assertEqual(subtract(9, 4), 5)\n",
        encoding="utf-8",
    )

    def git(*args):
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True, capture_output=True, text=True,
        )

    git("init", "-q")
    git("config", "user.name", "KALDRAX Tests")
    git("config", "user.email", "tests@kaldrax.invalid")
    git("add", "--all")
    git("commit", "-qm", "baseline")

    patch = """diff --git a/src/operations.py b/src/operations.py
--- a/src/operations.py
+++ b/src/operations.py
@@ -1,2 +1,2 @@
 def subtract(left: int, right: int) -> int:
-    raise NotImplementedError
+    return left - right
"""

    class RoleClient:
        def __init__(self, role):
            self.role = role
            self.calls = []

        def complete(self, *, system_prompt, user_prompt):
            payload = json.loads(user_prompt)
            self.calls.append((system_prompt, payload))
            if self.role == "planner":
                if "task decomposition planner" in system_prompt:
                    assert payload["repository_context"] is not None
                    assert any(
                        edge["target"] == "src/operations.py"
                        for edge in payload["repository_context"]["dependencies"]
                    )
                    return json.dumps({"tasks": [{
                        "id": "implement-subtract",
                        "phase": "implementation",
                        "description": "Implement integer subtraction",
                        "file_scope": ["src/operations.py", "tests/test_operations.py"],
                        "depends_on": [],
                        "acceptance_criteria": ["subtraction is implemented"],
                    }]})
                assert "task_graph_context" in payload
                return "Inspect the subtraction module and produce the safe patch."
            if self.role == "builder":
                if "focused KALDRAX implementation worker" in system_prompt:
                    assert payload["phase"] == "implementation"
                    assert payload["file_scope"] == ["src/operations.py", "tests/test_operations.py"]
                    assert payload["allowed_paths"] == payload["file_scope"]
                    assert any(
                        edge["target"] == "src/operations.py"
                        for edge in payload["repository_context"]["dependencies"]
                    )
                    return "Deliverable: implement subtract(left, right)."
                assert payload["task_graph_context"]["task_outputs"]["implement-subtract"]
                return json.dumps({
                    "summary": "Implement integer subtraction instead of raising NotImplementedError.",
                    "patch": patch,
                })
            if self.role == "reviewer":
                assert payload["task_graph_context"]["tasks"][0]["id"] == "implement-subtract"
                assert "patch" in payload
                return json.dumps({
                    "approved": True,
                    "findings": [],
                    "summary": "Patch implements the task-graph deliverable.",
                })
            if self.role == "evaluator":
                candidate = payload["candidate"]
                return json.dumps({"criteria": [{
                    "criterion": criterion,
                    "passed": criterion in candidate,
                    "evidence": criterion if criterion in candidate else "",
                } for criterion in payload["acceptance_criteria"]]})
            raise AssertionError(self.role)

    clients = {
        role: RoleClient(role)
        for role in ("planner", "builder", "reviewer", "evaluator")
    }

    class SuccessfulSandbox:
        def __init__(self, **kwargs):
            self.calls = []

        def run_workspace(self, workspace, *, module, module_args, timeout_seconds):
            self.calls.append((workspace, module, module_args, timeout_seconds))
            staged_source = (workspace / "src" / "operations.py").read_text(encoding="utf-8")
            assert "return left - right" in staged_source
            return SandboxResult(
                exit_code=0,
                stdout="Ran 1 test in 0.001s\nOK",
                stderr="",
                duration_ms=10,
                timed_out=False,
                output_truncated=False,
                container_image="fake:latest",
            )

    monkeypatch.setenv("KALDRAX_API_KEY", "test-key")
    monkeypatch.setenv("KALDRAX_PLANNER_MODEL", "planner-model")
    monkeypatch.setenv("KALDRAX_MODEL", "builder-model")
    monkeypatch.setenv("KALDRAX_REVIEWER_MODEL", "reviewer-model")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "evaluator-model")
    monkeypatch.setattr(cli, "_budget_from_env", RunBudget)
    monkeypatch.setattr(
        cli, "_client",
        lambda model, budget: clients[model.removesuffix("-model")],
    )
    monkeypatch.setattr(cli, "WorkspaceSandboxRunner", SuccessfulSandbox)

    artifact = tmp_path / "runs" / "orchestration.json"
    args = SimpleNamespace(
        objective="Implement subtraction in the repository",
        criterion=["Sandbox verification exit code: 0"],
        max_workers=2,
        max_attempts=2,
        checkpoint=tmp_path / "checkpoint.json",
        fresh=True,
        retry_failed=False,
        progress_jsonl=None,
        artifact=artifact,
        workspace=root,
        apply=True,
        max_cycles=1,
        verify_module="unittest",
        verify_arg=None,
        sandbox_timeout=30,
        sandbox_workspace_root=tmp_path / "sandbox",
    )

    assert cli._orchestrate(args) == 0
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["task_graph_passed"] is True
    assert payload["execution_order"] == ["implement-subtract"]
    assert payload["execution_waves"] == [["implement-subtract"]]
    assert payload["tasks"][0]["file_scope"] == ["src/operations.py", "tests/test_operations.py"]
    assert payload["repository"]["status"] == "passed"
    assert payload["repository"]["reviewer_approved"] is True
    assert payload["repository"]["verification"]["exit_code"] == 0
    assert payload["applied"] is True
    assert payload["passed"] is True
    assert "return left - right" in (root / "src" / "operations.py").read_text(encoding="utf-8")
    assert any("repository_patch_gate_completed" == item["event"] for item in payload["events"])
    capsys.readouterr()


def test_cli_orchestration_refuses_apply_without_workspace(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import kaldrax.cli as cli

    monkeypatch.setenv("KALDRAX_API_KEY", "test-key")
    monkeypatch.setenv("KALDRAX_PLANNER_MODEL", "planner-model")
    monkeypatch.setenv("KALDRAX_MODEL", "builder-model")
    monkeypatch.setenv("KALDRAX_REVIEWER_MODEL", "reviewer-model")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "evaluator-model")
    args = SimpleNamespace(
        objective="Build", criterion=["works"], apply=True, workspace=None,
    )
    with pytest.raises(ValueError, match="--apply requires --workspace"):
        cli._orchestrate(args)



def test_cli_orchestration_rejects_dirty_workspace_before_provider_calls(tmp_path, monkeypatch):
    import subprocess
    from types import SimpleNamespace

    import kaldrax.cli as cli

    root = tmp_path / "dirty-repo"
    root.mkdir()
    tracked = root / "README.md"
    tracked.write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "KALDRAX Tests"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "tests@kaldrax.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
    tracked.write_text("uncommitted edit\n", encoding="utf-8")

    monkeypatch.setattr(
        cli, "_client",
        lambda *args, **kwargs: pytest.fail("provider clients must not be created for a dirty workspace"),
    )
    args = SimpleNamespace(workspace=root, apply=False)
    with pytest.raises(ValueError, match="workspace must be clean"):
        cli._orchestrate(args)

def test_repository_checkpoint_is_bound_to_canonical_root_and_full_head(tmp_path):
    graph = TaskGraph("build", (TaskNode("a", "A"),))
    checkpoint_path = tmp_path / "run.json"
    root = tmp_path / "repo"
    other_root = tmp_path / "other-repo"
    root.mkdir()
    other_root.mkdir()
    original = {
        "root": str(root.resolve()),
        "head": "a" * 40,
    }
    store = CheckpointStore(checkpoint_path, repository_binding=original)

    report = TaskGraphScheduler().run(
        graph, lambda task: "completed", checkpoint_store=store,
    )
    assert report.passed
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert payload["repository_binding"] == original
    assert CheckpointStore(
        checkpoint_path, repository_binding=original,
    ).load(graph) is not None

    changed_head = {**original, "head": "b" * 40}
    with pytest.raises(TaskGraphError, match="repository root or HEAD changed"):
        CheckpointStore(
            checkpoint_path, repository_binding=changed_head,
        ).load(graph)

    changed_root = {**original, "root": str(other_root.resolve())}
    with pytest.raises(TaskGraphError, match="repository root or HEAD changed"):
        CheckpointStore(
            checkpoint_path, repository_binding=changed_root,
        ).load(graph)

    with pytest.raises(TaskGraphError, match="repository root or HEAD changed"):
        CheckpointStore(checkpoint_path).load(graph)


def test_unbound_legacy_checkpoint_remains_loadable(tmp_path):
    graph = TaskGraph("build", (TaskNode("a", "A"),))
    checkpoint_path = tmp_path / "legacy.json"
    store = CheckpointStore(checkpoint_path)
    TaskGraphScheduler().run(
        graph, lambda task: "completed", checkpoint_store=store,
    )

    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    payload.pop("repository_binding", None)
    checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")

    assert CheckpointStore(checkpoint_path).load(graph) is not None
