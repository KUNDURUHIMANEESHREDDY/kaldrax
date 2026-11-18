import json
import subprocess

from kaldrax.engineering import RepositoryTeamCoordinator
from kaldrax.evaluation import CriteriaEvaluator
from kaldrax.models import RunStatus, Task
from kaldrax.sandbox import SandboxResult
from kaldrax.workspace import RepositoryWorkspace


PATCH = """diff --git a/csv_reader.py b/csv_reader.py
--- a/csv_reader.py
+++ b/csv_reader.py
@@ -1,2 +1,6 @@
+import csv
+import io
+
 def parse_rows(source: str) -> list[list[str]]:
-    return [line.split(",") for line in source.splitlines() if line.strip()]
+    rows = csv.reader(io.StringIO(source, newline=""))
+    return [row for row in rows if row and any(field.strip() for field in row)]
"""


class FixedClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def complete(self, *, system_prompt, user_prompt):
        self.prompts.append((system_prompt, json.loads(user_prompt)))
        if "repository implementation agent" in system_prompt:
            return json.dumps({
                "summary": "Use csv.reader to preserve quoted commas and ignore blank CSV rows.",
                "patch": PATCH,
            })
        if "independent repository reviewer" in system_prompt:
            return json.dumps({"approved": True, "findings": [], "summary": "Patch and tests are sound."})
        return self.response


class SuccessfulSandbox:
    def __init__(self, exit_code=0):
        self.exit_code = exit_code
        self.calls = []

    def run_workspace(self, workspace, *, module, module_args, timeout_seconds):
        self.calls.append((workspace, module, module_args, timeout_seconds))
        return SandboxResult(
            exit_code=self.exit_code, stdout="Ran 2 tests in 0.001s\nOK", stderr="", duration_ms=12,
            timed_out=False, output_truncated=False, container_image="fake:latest",
        )


def init_csv_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "csv_reader.py").write_text(
        'def parse_rows(source: str) -> list[list[str]]:\n'
        '    return [line.split(",") for line in source.splitlines() if line.strip()]\n',
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_csv_reader.py").write_text(
        "import unittest\nfrom csv_reader import parse_rows\n\n"
        "class CsvReaderTests(unittest.TestCase):\n"
        "    def test_quoted_commas_are_preserved(self):\n"
        "        self.assertEqual(parse_rows('name,note\\nAda,\\\"hello, world\\\"'), "
        "[['name', 'note'], ['Ada', 'hello, world']])\n\n"
        "    def test_blank_rows_are_ignored(self):\n"
        "        self.assertEqual(parse_rows('a,b\\n\\n , \\n1,2'), [['a', 'b'], ['1', '2']])\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "kaldrax@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "KALDRAX Tests"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "--all"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)


def make_coordinator(root, sandbox, artifacts=None, *, allowed_paths=None):
    task = Task(
        "Fix CSV parsing for quoted fields and empty rows",
        ("csv.reader", "any(field.strip() for field in row)", "Sandbox verification exit code: 0"),
        project_id="csv-import",
    )
    return RepositoryTeamCoordinator(
        planner=FixedClient("Inspect the parser and its unit tests."),
        builder=FixedClient("unused"),
        reviewer=FixedClient("unused"),
        evaluator=CriteriaEvaluator(),
        workspace_root=root,
        sandbox=sandbox,
        verify_module="unittest",
        verify_args=("discover", "-s", "tests", "-v"),
        max_cycles=1,
        artifact_dir=artifacts,
        allowed_paths=allowed_paths,
    ), task


def test_repository_team_stages_tests_reviews_and_applies_only_on_request(tmp_path):
    root = tmp_path / "repo"
    init_csv_repo(root)
    sandbox = SuccessfulSandbox()
    coordinator, task = make_coordinator(root, sandbox, tmp_path / "artifacts")

    report = coordinator.run(task, apply_changes=True)

    assert report.status is RunStatus.PASSED
    assert report.applied is True
    assert report.reviewer_approved is True
    assert report.verification["exit_code"] == 0
    assert report.evaluation.passed
    assert sandbox.calls[0][1] == "unittest"
    assert "csv.reader" in (root / "csv_reader.py").read_text(encoding="utf-8")
    assert (tmp_path / "artifacts" / f"repo-team-{report.run_id}.json").exists()


def test_repository_team_never_applies_patch_when_sandbox_fails(tmp_path):
    root = tmp_path / "repo"
    init_csv_repo(root)
    coordinator, task = make_coordinator(root, SuccessfulSandbox(exit_code=1))

    report = coordinator.run(task, apply_changes=True)

    assert report.status is RunStatus.LIMIT_REACHED
    assert report.applied is False
    assert "line.split" in (root / "csv_reader.py").read_text(encoding="utf-8")


def test_dry_run_verifies_without_modifying_repository(tmp_path):
    root = tmp_path / "repo"
    init_csv_repo(root)
    coordinator, task = make_coordinator(root, SuccessfulSandbox())

    report = coordinator.run(task, apply_changes=False)

    assert report.status is RunStatus.PASSED
    assert report.applied is False
    assert "line.split" in (root / "csv_reader.py").read_text(encoding="utf-8")


def test_repository_team_rejects_empty_unittest_discovery(tmp_path):
    root = tmp_path / "repo"
    init_csv_repo(root)
    class EmptySuiteSandbox(SuccessfulSandbox):
        def run_workspace(self, workspace, *, module, module_args, timeout_seconds):
            return SandboxResult(
                exit_code=0, stdout="Ran 0 tests in 0.001s\nOK", stderr="", duration_ms=10,
                timed_out=False, output_truncated=False, container_image="fake:latest",
            )
    coordinator, task = make_coordinator(root, EmptySuiteSandbox())
    report = coordinator.run(task, apply_changes=True)
    assert report.status is RunStatus.LIMIT_REACHED
    assert report.verification["test_count"] == 0
    assert report.applied is False
    assert "line.split" in (root / "csv_reader.py").read_text(encoding="utf-8")


def test_planner_is_told_it_only_receives_a_file_manifest(tmp_path):
    root = tmp_path / "repo"
    init_csv_repo(root)
    coordinator, task = make_coordinator(root, SuccessfulSandbox())

    report = coordinator.run(task, apply_changes=False)

    assert report.status is RunStatus.PASSED
    prompt, payload = coordinator.planner.prompts[0]
    assert "not source contents" in prompt
    assert all(set(item) == {"path", "characters"} for item in payload["workspace_manifest"]["files"])
    assert all("content" not in item for item in payload["workspace_manifest"]["files"])
    assert "repository_intelligence" in payload
    assert any(
        edge["target"] == "csv_reader.py"
        for edge in payload["repository_intelligence"]["dependencies"]
    )
    assert "dependencies" in coordinator.builder.prompts[0][1]["repository_intelligence"]
    review_payload = coordinator.reviewer.prompts[0][1]
    assert review_payload["repository_impact"]["changed_paths"] == ["csv_reader.py"]
    assert report.repository_intelligence["changed_paths"] == ["csv_reader.py"]
    assert report.repository_intelligence["relevant_tests"]["csv_reader.py"] == ["tests/test_csv_reader.py"]

def test_repository_team_cancellation_after_planner_stops_before_builder(tmp_path):
    root = tmp_path / "repo"
    init_csv_repo(root)
    sandbox = SuccessfulSandbox()
    coordinator, task = make_coordinator(root, sandbox)
    cancel_file = tmp_path / "cancel.flag"
    coordinator.cancel_file = cancel_file

    def cancel_after_planner(event):
        if event["event_type"] == "planner_completed":
            cancel_file.write_text("cancel", encoding="utf-8")

    coordinator.progress_sink = cancel_after_planner
    report = coordinator.run(task, apply_changes=True)

    assert report.cancelled is True
    assert report.status is RunStatus.FAILED
    assert report.events[-1] == "repository_team_run_cancelled"
    assert coordinator.builder.prompts == []
    assert sandbox.calls == []
    assert "line.split" in (root / "csv_reader.py").read_text(encoding="utf-8")

def test_repository_team_rejects_out_of_scope_patch_before_sandbox_or_review(tmp_path):
    root = tmp_path / "repo"
    init_csv_repo(root)
    sandbox = SuccessfulSandbox()

    unauthorized_patch = """diff --git a/csv_reader.py b/csv_reader.py
--- a/csv_reader.py
+++ b/csv_reader.py
@@ -1,2 +1,2 @@
 def parse_rows(source: str) -> list[list[str]]:
-    return [line.split(",") for line in source.splitlines() if line.strip()]
+    return []
diff --git a/docs/extra.md b/docs/extra.md
new file mode 100644
--- /dev/null
+++ b/docs/extra.md
@@ -0,0 +1 @@
+# outside scope
"""

    class OutOfScopeBuilder(FixedClient):
        def complete(self, *, system_prompt, user_prompt):
            self.prompts.append((system_prompt, json.loads(user_prompt)))
            if "repository implementation agent" in system_prompt:
                return json.dumps({
                    "summary": "Attempt to change a file outside the task scope.",
                    "patch": unauthorized_patch,
                })
            return self.response

    coordinator, task = make_coordinator(
        root, sandbox, allowed_paths=("csv_reader.py",),
    )
    coordinator.builder = OutOfScopeBuilder("unused")

    report = coordinator.run(task, apply_changes=True)

    assert report.status is RunStatus.LIMIT_REACHED
    assert report.applied is False
    assert report.allowed_paths == ["csv_reader.py"]
    assert report.changed_files == []
    assert sandbox.calls == []
    assert coordinator.reviewer.prompts == []
    assert any("task file_scope" in event for event in report.events)
    assert coordinator.builder.prompts[0][1]["allowed_paths"] == ["csv_reader.py"]
    assert not (root / "docs" / "extra.md").exists()
    assert "line.split" in (root / "csv_reader.py").read_text(encoding="utf-8")
