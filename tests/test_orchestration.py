import json
import threading
import time

import pytest

from kaldrax.orchestration import (
    CheckpointStore,
    ExecutionCheckpoint,
    NodeCheckpoint,
    RetryPolicy,
    RetryableTaskError,
    TaskDecomposer,
    TaskGraph,
    TaskGraphError,
    TaskGraphReport,
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
                assert payload["task_graph_context"]["allowed_paths"] == [
                    "src/operations.py", "tests/test_operations.py",
                ]
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

def test_failure_diagnosis_requires_complete_structured_results():
    graph = TaskGraph("Build service", (
        TaskNode("base", "Build base"),
        TaskNode("implementation", "Implement service", ("base",)),
        TaskNode("integration", "Integrate service", ("implementation",)),
    ))
    report = TaskGraphReport(
        objective=graph.objective,
        states={
            "base": TaskState.SUCCEEDED.value,
            "implementation": TaskState.FAILED.value,
            "integration": TaskState.BLOCKED.value,
        },
        outputs={"base": "Base module is ready."},
        attempts={"base": 1, "implementation": 2, "integration": 0},
        errors={"implementation": "ValueError: unsupported input"},
        events=[],
    )
    planner = Planner(json.dumps({"diagnoses": [
        {
            "task_id": "implementation",
            "category": "implementation",
            "root_cause": "The implementation rejected a supported input shape.",
            "retryable": False,
            "operator_input_required": False,
            "repair_instruction": "Handle both supported input variants and add a regression case.",
        },
        {
            "task_id": "integration",
            "category": "dependency",
            "root_cause": "The implementation prerequisite failed.",
            "retryable": False,
            "operator_input_required": False,
            "repair_instruction": "Rewire integration to the repaired implementation task.",
        },
    ]}))

    diagnoses = TaskDecomposer(planner).diagnose_failures(graph, report)

    assert {item["task_id"] for item in diagnoses} == {"implementation", "integration"}
    assert diagnoses[1]["category"] == "dependency"
    assert planner.prompts[0][1]["successful_task_outputs"] == {"base": "Base module is ready."}

    invalid = TaskDecomposer(Planner(json.dumps({"diagnoses": [{
        "task_id": "implementation",
        "category": "implementation",
        "root_cause": "Only one task was diagnosed.",
        "retryable": True,
        "operator_input_required": False,
        "repair_instruction": "Retry.",
    }]})))
    with pytest.raises(TaskGraphError, match="failure diagnosis"):
        invalid.diagnose_failures(graph, report)


def test_replan_rewires_unfinished_work_and_keeps_successful_tasks_immutable():
    base = TaskNode(
        "base", "Create shared base", (),
        ("base module exists",), phase="foundation", file_scope=("src/base.py",),
    )
    failed = TaskNode(
        "failed", "Implement the first approach", ("base",),
        ("service works",), phase="implementation", file_scope=("src/service.py",),
    )
    blocked = TaskNode(
        "blocked", "Integrate the service", ("failed",),
        ("integration works",), phase="integration", file_scope=("src/integration.py",),
    )
    graph = TaskGraph("Build a service", (base, failed, blocked))
    report = TaskGraphReport(
        objective=graph.objective,
        states={
            "base": TaskState.SUCCEEDED.value,
            "failed": TaskState.FAILED.value,
            "blocked": TaskState.BLOCKED.value,
        },
        outputs={"base": "Base implementation is complete."},
        attempts={"base": 1, "failed": 3, "blocked": 0},
        errors={"failed": "ValueError: incompatible interface"},
        events=[],
    )
    repaired_payload = {
        "repair_summary": "Replace the incompatible implementation and rewire integration.",
        "retired_task_ids": ["failed"],
        "tasks": [
            {
                "id": "base", "description": "Create shared base", "depends_on": [],
                "acceptance_criteria": ["base module exists"],
                "phase": "foundation", "file_scope": ["src/base.py"],
            },
            {
                "id": "replacement", "description": "Implement service using the stable base interface",
                "depends_on": ["base"], "acceptance_criteria": ["service works"],
                "phase": "implementation", "file_scope": ["src/service.py"],
            },
            {
                "id": "blocked", "description": "Integrate the repaired service",
                "depends_on": ["replacement"], "acceptance_criteria": ["integration works"],
                "phase": "integration", "file_scope": ["src/integration.py"],
            },
        ],
    }
    planner = Planner(json.dumps(repaired_payload))

    repaired, retired, summary = TaskDecomposer(planner).replan(
        graph,
        report,
        [
            {
                "task_id": "failed", "category": "implementation",
                "root_cause": "The first interface was incompatible.",
                "retryable": False, "operator_input_required": False,
                "repair_instruction": "Replace it with an implementation using the base interface.",
            },
            {
                "task_id": "blocked", "category": "dependency",
                "root_cause": "The integration task depends on failed.",
                "retryable": False, "operator_input_required": False,
                "repair_instruction": "Depend on the replacement implementation.",
            },
        ],
        acceptance_criteria=("service works", "integration works"),
    )

    assert retired == ["failed"]
    assert summary.startswith("Replace")
    assert next(node for node in repaired.tasks if node.id == "base") == base
    assert next(node for node in repaired.tasks if node.id == "blocked").depends_on == ("replacement",)
    assert [node.id for node in repaired.execution_order] == ["base", "replacement", "blocked"]
    assert planner.prompts[0][1]["immutable_successful_tasks"][0]["output"] == "Base implementation is complete."


def test_replan_rejects_changes_to_successful_task_definition():
    base = TaskNode("base", "Completed base", (), ("base ready",))
    failed = TaskNode("failed", "Failed task")
    graph = TaskGraph("Build", (base, failed))
    report = TaskGraphReport(
        graph.objective,
        {"base": "succeeded", "failed": "failed"},
        {"base": "already done"},
        {"base": 1, "failed": 1},
        {"failed": "ValueError: failed"},
        [],
    )
    planner = Planner(json.dumps({
        "repair_summary": "Attempted to rename completed work.",
        "retired_task_ids": [],
        "tasks": [
            {"id": "base", "description": "Rebuild the base", "depends_on": [], "acceptance_criteria": ["base ready"]},
            {"id": "failed", "description": "Retry failed task", "depends_on": [], "acceptance_criteria": []},
        ],
    }))

    with pytest.raises(TaskGraphError, match="changed or removed successful task"):
        TaskDecomposer(planner).replan(
            graph, report,
            [{
                "task_id": "failed", "category": "implementation",
                "root_cause": "Failure", "retryable": True,
                "operator_input_required": False, "repair_instruction": "Retry with a fix.",
            }],
        )


def test_repaired_checkpoint_resumes_only_unfinished_work_and_persists_graph(tmp_path):
    initial = TaskGraph("Build", (
        TaskNode("base", "Build base"),
        TaskNode("broken", "Build broken module"),
    ))
    request_fingerprint = "a" * 64
    store = CheckpointStore(tmp_path / "recovery.json", request_fingerprint=request_fingerprint)
    first_calls = []

    def first_executor(task):
        first_calls.append(task.id)
        if task.id == "broken":
            raise ValueError("permanent implementation error")
        return "base-output"

    failed = TaskGraphScheduler(
        retry_policy=RetryPolicy(max_attempts=1),
    ).run(initial, first_executor, checkpoint_store=store)
    assert failed.states["base"] == TaskState.SUCCEEDED.value
    assert failed.states["broken"] == TaskState.FAILED.value

    repaired = TaskGraph("Build", (
        TaskNode("base", "Build base"),
        TaskNode("replacement", "Build corrected module", ("base",)),
    ))
    old_checkpoint = store.load(initial)
    assert old_checkpoint is not None
    seeded_nodes = {
        "base": NodeCheckpoint(
            state=TaskState.SUCCEEDED,
            attempts=old_checkpoint.nodes["base"].attempts,
            output=old_checkpoint.nodes["base"].output,
            total_attempts=old_checkpoint.nodes["base"].total_attempts,
        ),
        "replacement": NodeCheckpoint(
            state=TaskState.PENDING,
            total_attempts=0,
        ),
    }
    store.save(ExecutionCheckpoint(
        schema_version=1,
        graph_fingerprint=repaired.fingerprint(),
        nodes=seeded_nodes,
        events=old_checkpoint.events,
        graph=repaired,
        repair_history=[{"round": 1, "status": "replanned"}],
    ))
    second_calls = []
    resumed = TaskGraphScheduler(
        retry_policy=RetryPolicy(max_attempts=1),
    ).run(
        repaired,
        lambda task: second_calls.append(task.id) or "replacement-output",
        checkpoint_store=store,
    )

    assert first_calls == ["base", "broken"]
    assert second_calls == ["replacement"]
    assert resumed.passed
    assert resumed.outputs == {"base": "base-output", "replacement": "replacement-output"}
    assert resumed.attempts == {"base": 1, "replacement": 1}
    assert resumed.repair_history == [{"round": 1, "status": "replanned"}]

    loaded_graph, loaded_checkpoint = store.load_latest()
    assert loaded_graph.fingerprint() == repaired.fingerprint()
    assert loaded_checkpoint.nodes["base"].output == "base-output"


def test_cli_orchestration_repairs_failed_work_without_repeating_successful_tasks(
    tmp_path, monkeypatch, capsys,
):
    from types import SimpleNamespace

    import kaldrax.cli as cli
    from kaldrax.budgets import RunBudget

    initial_tasks = [
        {
            "id": "base", "description": "Create base component",
            "depends_on": [], "acceptance_criteria": ["base delivered"],
        },
        {
            "id": "fragile", "description": "Implement fragile component",
            "depends_on": [], "acceptance_criteria": ["fragile delivered after repair"],
        },
    ]
    repaired_tasks = [
        {
            "id": "base", "description": "Create base component",
            "depends_on": [], "acceptance_criteria": ["base delivered"],
        },
        {
            "id": "fragile", "description": "Implement component using the diagnosed input contract",
            "depends_on": [], "acceptance_criteria": ["fragile delivered after repair"],
        },
    ]

    class RoleClient:
        def __init__(self, role):
            self.role = role
            self.calls = []
            self.builder_calls = {}

        def complete(self, *, system_prompt, user_prompt):
            payload = json.loads(user_prompt)
            self.calls.append((system_prompt, payload))
            if self.role == "planner":
                if "dependency-aware task decomposition planner" in system_prompt:
                    return json.dumps({"tasks": initial_tasks})
                if "failure-diagnosis agent" in system_prompt:
                    return json.dumps({"diagnoses": [{
                        "task_id": "fragile",
                        "category": "implementation",
                        "root_cause": "The first implementation did not satisfy its contract.",
                        "retryable": False,
                        "operator_input_required": False,
                        "repair_instruction": "Revise the task implementation to honor the input contract.",
                    }]})
                if "bounded task-graph repair planner" in system_prompt:
                    return json.dumps({
                        "repair_summary": "Revise the failed implementation without touching completed work.",
                        "retired_task_ids": [],
                        "tasks": repaired_tasks,
                    })
                raise AssertionError(system_prompt)
            if self.role == "builder":
                if system_prompt.startswith("You are a focused KALDRAX implementation worker."):
                    task_id = payload["task_id"]
                    self.builder_calls[task_id] = self.builder_calls.get(task_id, 0) + 1
                    if task_id == "fragile" and self.builder_calls[task_id] == 1:
                        raise ValueError("initial implementation rejected an input")
                    if task_id == "base":
                        return "base delivered"
                    return "fragile delivered after repair"
            if self.role == "reviewer":
                return json.dumps({
                    "approved": True, "findings": [], "summary": "Repaired aggregate is sound.",
                })
            if self.role == "evaluator":
                criterion = "fragile delivered after repair"
                return json.dumps({"criteria": [{
                    "criterion": criterion,
                    "passed": criterion in payload["candidate"],
                    "evidence": criterion if criterion in payload["candidate"] else "",
                }]})
            raise AssertionError(self.role)

    clients = {
        role: RoleClient(role)
        for role in ("planner", "builder", "reviewer", "evaluator")
    }
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

    artifact = tmp_path / "runs" / "recovery.json"
    args = SimpleNamespace(
        objective="Build a reliable component",
        criterion=["fragile delivered after repair"],
        max_workers=1,
        max_attempts=1,
        max_replans=1,
        checkpoint=tmp_path / "checkpoint.json",
        fresh=True,
        retry_failed=False,
        progress_jsonl=None,
        artifact=artifact,
    )

    assert cli._orchestrate(args) == 0
    report = json.loads(artifact.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["states"] == {"base": "succeeded", "fragile": "succeeded"}
    assert report["attempts"] == {"base": 1, "fragile": 2}
    assert clients["builder"].builder_calls == {"base": 1, "fragile": 2}
    assert report["repair_history"][0]["status"] == "replanned"
    assert report["repair_history"][0]["preserved_successful_task_ids"] == ["base"]
    assert report["repair_history"][0]["reset_task_ids"] == ["fragile"]
    assert clients["reviewer"].calls
    assert clients["evaluator"].calls
    capsys.readouterr()
