import io
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from kaldrax.sandbox import SandboxResult
from kaldrax.workspace_sandbox import WorkspaceSandboxRunner


class FakeProcess:
    def __init__(self):
        self.stdout = io.BytesIO(b"Ran 2 tests\nOK\n")
        self.stderr = io.BytesIO()
    def wait(self, timeout=None):
        return 0
    def kill(self):
        raise AssertionError("unexpected kill")


def test_workspace_sandbox_runs_only_a_disposable_secret_filtered_copy(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (source / ".env").write_text("TOKEN=private\n", encoding="utf-8")
    (source / ".aws").mkdir()
    (source / ".aws" / "credentials").write_text("secret\n", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/docker")
    commands = []
    def run_factory(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="25.0", stderr="")
    observed = {}
    def popen_factory(command, **kwargs):
        commands.append(command)
        mount = next(item for item in command if item.startswith("type=bind,source="))
        disposable = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
        observed["mount"] = disposable
        observed["files"] = sorted(p.relative_to(disposable).as_posix() for p in disposable.rglob("*"))
        return FakeProcess()
    result = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox", popen_factory=popen_factory, run_factory=run_factory,
    ).run_workspace(source, module="unittest", module_args=("discover", "-s", "tests"))
    command = commands[-1]
    assert result.exit_code == 0
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--user") + 1] == "65534:65534"
    assert command[-7:] == ["python", "-B", "-m", "unittest", "discover", "-s", "tests"]
    assert observed["mount"] != source
    assert "app.py" in observed["files"]
    assert ".env" not in observed["files"]
    assert not any(path.startswith(".aws/") for path in observed["files"])
    assert (source / ".env").exists()
    assert result.container_image == "python:3.13-slim"


def test_workspace_sandbox_rejects_unapproved_python_modules_before_docker(tmp_path):
    runner = WorkspaceSandboxRunner(workspace_root=tmp_path / "sandbox")
    with pytest.raises(ValueError, match="module must be one of"):
        runner.run_workspace(tmp_path, module="pip")


def test_workspace_sandbox_accepts_a_configured_pre_pulled_image(tmp_path):
    runner = WorkspaceSandboxRunner(workspace_root=tmp_path, image="registry.example.test/tools/python:3.13")
    assert runner.image == "registry.example.test/tools/python:3.13"
    with pytest.raises(ValueError, match="valid Docker image"):
        WorkspaceSandboxRunner(workspace_root=tmp_path, image="--privileged")


def test_full_repository_suite_runs_all_fixed_ci_and_desktop_stages(tmp_path):
    class RecordingRunner(WorkspaceSandboxRunner):
        def __init__(self):
            super().__init__(workspace_root=tmp_path / "sandbox")
            self.calls = []

        def run_workspace(self, workspace, *, module, module_args, timeout_seconds, cancel_file=None, **kwargs):
            self.calls.append((module, module_args, timeout_seconds, cancel_file, kwargs))
            stdout = (
                "9 passed, 2 skipped in 0.31s\n" if module == "pytest311"
                else "10 passed, 1 skipped in 0.31s\n" if module == "pytest"
                else ""
            )
            return SandboxResult(
                exit_code=0, stdout=stdout, stderr="", duration_ms=20,
                timed_out=False, output_truncated=False,
                container_image="kaldrax-verification:full",
            )

    runner = RecordingRunner()
    runner._full_suite_preflight = {
        "image": "kaldrax-verification:full",
        "image_id": "sha256:full-image",
        "python_3_11": "3.11.8",
        "python_3_13": "3.13.1",
        "pytest": "available_on_both_python_runtimes",
        "node": "v24.2.0",
        "npm": "10.8.2",
        "desktop_dependencies": "prebuilt",
        "pull_policy": "never",
        "network": "none",
    }
    result = runner.run_workspace_full_suite(tmp_path, timeout_seconds=120)

    assert result.preflight == runner._full_suite_preflight
    assert result.exit_code == 0
    assert result.test_counts == {"3.11": 9, "3.13": 10}
    assert result.test_count == 19
    assert [step["name"] for step in result.steps] == [
        "python_3_11_full_test_suite",
        "python_3_11_deterministic_ci_quality",
        "python_3_11_source_compilation",
        "python_3_13_full_test_suite",
        "python_3_13_deterministic_ci_quality",
        "python_3_13_source_compilation",
        "desktop_lint_and_production_build",
    ]
    assert [call[0] for call in runner.calls] == [
        "pytest311", "ci-quality311", "compileall311",
        "pytest", "ci-quality", "compileall", "desktop",
    ]
    assert runner.calls[0][0:2] == ("pytest311", ("-q",))
    assert runner.calls[2][0:2] == ("compileall311", ("-q", "."))
    assert runner.calls[5][0:2] == ("compileall", ("-q", "."))
    assert runner.calls[6][0:2] == ("desktop", ())
    assert runner.calls[1][4]["memory_mb"] == 512
    assert runner.calls[1][4]["cpu_count"] == 1.0
    assert runner.calls[6][4]["memory_mb"] == 1024
    assert runner.calls[6][4]["cpu_count"] == 2.0
    assert runner.calls[6][4]["pids_limit"] == 128
    assert all(call[2] <= 120 for call in runner.calls)
    assert all(call[3] is None for call in runner.calls)
    assert all(step["status"] == "passed" for step in result.steps)


def test_full_repository_suite_rejects_zero_passed_tests_on_either_python_runtime(tmp_path):
    class EmptySuiteRunner(WorkspaceSandboxRunner):
        def __init__(self):
            super().__init__(workspace_root=tmp_path / "sandbox")
            self.calls = []

        def run_workspace(self, workspace, *, module, module_args, timeout_seconds, cancel_file=None, **kwargs):
            self.calls.append(module)
            stdout = "4 skipped in 0.01s\n" if module in {"pytest311", "pytest"} else ""
            return SandboxResult(
                exit_code=0, stdout=stdout, stderr="", duration_ms=10,
                timed_out=False, output_truncated=False, container_image="kaldrax-verification:full",
            )

    runner = EmptySuiteRunner()
    result = runner.run_workspace_full_suite(tmp_path, timeout_seconds=120)

    assert runner.calls == [
        "pytest311", "ci-quality311", "compileall311",
        "pytest", "ci-quality", "compileall", "desktop",
    ]
    assert result.test_count == 0
    assert result.test_counts == {"3.11": 0, "3.13": 0}
    assert result.exit_code != 0
    assert result.steps[0]["status"] == "failed"
    assert result.steps[3]["status"] == "failed"
    assert result.steps[1]["status"] == "passed"
    assert result.steps[2]["status"] == "passed"
    assert result.steps[4]["status"] == "passed"
    assert result.steps[5]["status"] == "passed"


def test_full_repository_suite_keeps_python_test_failures_and_runs_remaining_gates(tmp_path):
    class FailingTestsRunner(WorkspaceSandboxRunner):
        def __init__(self):
            super().__init__(workspace_root=tmp_path / "sandbox")
            self.calls = []

        def run_workspace(self, workspace, *, module, module_args, timeout_seconds, cancel_file=None, **kwargs):
            self.calls.append(module)
            if module in {"pytest311", "pytest"}:
                return SandboxResult(
                    exit_code=1, stdout="2 failed, 7 passed\n", stderr="",
                    duration_ms=25, timed_out=False, output_truncated=False,
                    container_image="kaldrax-verification:full",
                )
            return SandboxResult(
                exit_code=0, stdout="", stderr="", duration_ms=5,
                timed_out=False, output_truncated=False, container_image="kaldrax-verification:full",
            )

    runner = FailingTestsRunner()
    result = runner.run_workspace_full_suite(tmp_path, timeout_seconds=120)

    assert runner.calls == [
        "pytest311", "ci-quality311", "compileall311",
        "pytest", "ci-quality", "compileall", "desktop",
    ]
    assert result.exit_code == 1
    assert result.test_count == 14
    assert result.test_counts == {"3.11": 7, "3.13": 7}
    assert result.steps[0]["status"] == "failed"
    assert result.steps[3]["status"] == "failed"
    assert result.steps[1]["status"] == "passed"
    assert result.steps[2]["status"] == "passed"
    assert result.steps[4]["status"] == "passed"
    assert result.steps[5]["status"] == "passed"


def test_full_suite_preflight_requires_local_python_node_image_and_pytest_without_pulling(monkeypatch, tmp_path):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    calls = []

    def run_factory(command, **kwargs):
        calls.append(command)
        if command[1] == "info":
            return SimpleNamespace(returncode=0, stdout="29.0", stderr="")
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="sha256:local-image", stderr="")
        if command[1] == "run":
            return SimpleNamespace(returncode=0, stdout="python313=3.13.1\npython311=3.11.8\nv24.2.0\n10.8.2\n", stderr="")
        raise AssertionError(command)

    runner = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox",
        image="kaldrax-verification:full",
        run_factory=run_factory,
    )
    evidence = runner.preflight_full_suite()
    assert evidence == {
        "image": "kaldrax-verification:full",
        "image_id": "sha256:local-image",
        "python_3_13": "3.13.1",
        "python_3_11": "3.11.8",
        "pytest": "available_on_both_python_runtimes",
        "node": "v24.2.0",
        "npm": "10.8.2",
        "desktop_dependencies": "prebuilt",
        "pull_policy": "never",
        "network": "none",
    }
    assert [call[1] for call in calls] == ["info", "image", "run"]
    probe = calls[-1]
    assert "--pull=never" in probe
    assert probe[probe.index("--network") + 1] == "none"
    assert probe[probe.index("--entrypoint") + 1] == "/bin/sh"
    assert probe[-2] == "-c"
    assert "import pytest" in probe[-1]
    assert "node --version" in probe[-1]
    assert "/opt/kaldrax-deps/desktop/node_modules" in probe[-1]
    assert runner._full_suite_preflight == evidence


def test_full_suite_preflight_fails_when_image_is_not_pulled(monkeypatch, tmp_path):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    calls = []

    def run_factory(command, **kwargs):
        calls.append(command)
        if command[1] == "info":
            return SimpleNamespace(returncode=0, stdout="29.0", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="No such image")

    runner = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox",
        image="registry.example.test/kaldrax-verify:missing",
        run_factory=run_factory,
    )
    with pytest.raises(RuntimeError, match="not available locally"):
        runner.preflight_full_suite()
    assert [call[1] for call in calls] == ["info", "image"]


def test_full_suite_preflight_fails_when_pytest_is_missing_from_image(monkeypatch, tmp_path):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    calls = []

    def run_factory(command, **kwargs):
        calls.append(command)
        if command[1] == "info":
            return SimpleNamespace(returncode=0, stdout="29.0", stderr="")
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="sha256:local-image", stderr="")
        return SimpleNamespace(returncode=1, stdout="", stderr="ModuleNotFoundError: pytest")

    runner = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox",
        image="kaldrax-verification:no-pytest",
        run_factory=run_factory,
    )
    with pytest.raises(RuntimeError, match="must provide pytest, Node.js"):
        runner.preflight_full_suite()
    assert [call[1] for call in calls] == ["info", "image", "run"]

def test_workspace_sandbox_runs_desktop_lint_and_build_as_fixed_offline_command(monkeypatch, tmp_path):
    import shutil

    source = tmp_path / "project"
    source.mkdir()
    (source / "desktop").mkdir()
    (source / "desktop" / "package.json").write_text('{"scripts": {}}\n', encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    commands = []

    def run_factory(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="29.0", stderr="")

    def popen_factory(command, **kwargs):
        commands.append(command)
        return FakeProcess()

    result = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox",
        image="kaldrax-verification:full",
        popen_factory=popen_factory,
        run_factory=run_factory,
    ).run_workspace(source, module="desktop", module_args=())

    command = commands[-1]
    assert result.exit_code == 0
    assert command[command.index("--network") + 1] == "none"
    assert command[-4] == "kaldrax-verification:full"
    assert command[-3] == "/bin/sh"
    assert command[-2:] == ["-c", WorkspaceSandboxRunner.DESKTOP_VERIFICATION_COMMAND]
    assert "sha256sum -c /opt/kaldrax-desktop-deps.sha256" in command[-1]
    assert "npm run lint" in command[-1]
    assert "npm run build" in command[-1]
    assert "--pull=never" in command

def test_full_suite_preflight_rejects_wrong_node_major(monkeypatch, tmp_path):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")

    def run_factory(command, **kwargs):
        if command[1] == "info":
            return SimpleNamespace(returncode=0, stdout="29.0", stderr="")
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="sha256:local-image", stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout="python313=3.13.1\npython311=3.11.8\nv22.0.0\n10.8.2\n",
            stderr="",
        )

    runner = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox",
        image="kaldrax-verification:old-node",
        run_factory=run_factory,
    )
    with pytest.raises(RuntimeError, match="requires Node.js 24"):
        runner.preflight_full_suite()

def test_full_repository_suite_rejects_desktop_build_failure(tmp_path):
    class FailingDesktopRunner(WorkspaceSandboxRunner):
        def __init__(self):
            super().__init__(workspace_root=tmp_path / "sandbox")
            self.calls = []

        def run_workspace(self, workspace, *, module, module_args, timeout_seconds, cancel_file=None, **kwargs):
            self.calls.append(module)
            if module in {"pytest311", "pytest"}:
                return SandboxResult(
                    exit_code=0, stdout="3 passed in 0.1s\n", stderr="",
                    duration_ms=10, timed_out=False, output_truncated=False,
                    container_image="kaldrax-verification:full",
                )
            if module == "desktop":
                return SandboxResult(
                    exit_code=2, stdout="", stderr="vite build failed",
                    duration_ms=15, timed_out=False, output_truncated=False,
                    container_image="kaldrax-verification:full",
                )
            return SandboxResult(
                exit_code=0, stdout="", stderr="", duration_ms=5,
                timed_out=False, output_truncated=False,
                container_image="kaldrax-verification:full",
            )

    runner = FailingDesktopRunner()
    result = runner.run_workspace_full_suite(tmp_path, timeout_seconds=120)

    assert runner.calls == [
        "pytest311", "ci-quality311", "compileall311",
        "pytest", "ci-quality", "compileall", "desktop",
    ]
    assert result.exit_code == 2
    assert result.test_counts == {"3.11": 3, "3.13": 3}
    assert all(step["status"] == "passed" for step in result.steps[:6])
    assert result.steps[6]["status"] == "failed"
    assert result.stderr.endswith("vite build failed")


def test_workspace_sandbox_runs_deterministic_ci_quality_checks_in_fixed_offline_script(monkeypatch, tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "src").mkdir()
    (source / "src" / "kaldrax").mkdir()
    (source / "src" / "kaldrax" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/docker")
    commands = []

    def run_factory(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="25.0", stderr="")

    def popen_factory(command, **kwargs):
        commands.append(command)
        return FakeProcess()

    result = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox",
        image="kaldrax-verification:full",
        popen_factory=popen_factory,
        run_factory=run_factory,
    ).run_workspace(source, module="ci-quality", module_args=())

    command = commands[-1]
    assert result.exit_code == 0
    assert command[command.index("--network") + 1] == "none"
    assert command[-4] == "kaldrax-verification:full"
    assert command[-3] == "/bin/sh"
    script = command[-1]
    assert "memory benchmark" in script
    assert "memory benchmark-compare" in script
    assert "benchmark-evaluator --mode deterministic --min-accuracy 0.80" in script
    assert "memory quality-report --profile ci" in script
    assert "--live-extraction" not in script
    assert "/tmp/kaldrax-memory-quality.json" in script

def test_full_suite_preflight_rejects_missing_python_311_runtime(monkeypatch, tmp_path):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")

    def run_factory(command, **kwargs):
        if command[1] == "info":
            return SimpleNamespace(returncode=0, stdout="29.0", stderr="")
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="sha256:local-image", stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout="python313=3.13.1\npython311=3.12.0\nv24.2.0\n10.8.2\n",
            stderr="",
        )

    runner = WorkspaceSandboxRunner(
        workspace_root=tmp_path / "sandbox",
        image="kaldrax-verification:missing-python311",
        run_factory=run_factory,
    )
    with pytest.raises(RuntimeError, match="requires the Python 3.11 CI runtime"):
        runner.preflight_full_suite()
