import io
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from kaldrax.sandbox import SandboxRunner, SandboxUnavailableError


class FakeProcess:
    def __init__(self, *, stdout=b"ok", stderr=b"", timeout=False):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.timeout = timeout
        self.killed = False

    def wait(self, timeout=None):
        if self.timeout and not self.killed:
            raise subprocess.TimeoutExpired("docker run", timeout)
        return -9 if self.killed else 0

    def kill(self):
        self.killed = True


def test_sandbox_command_uses_isolation_limits_and_only_temp_workspace(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    commands = []

    def run_factory(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="25.0", stderr="")

    process = FakeProcess(stdout=b"program output")

    def popen_factory(command, **kwargs):
        commands.append(command)
        return process

    result = SandboxRunner(
        workspace_root=tmp_path, popen_factory=popen_factory, run_factory=run_factory
    ).run_python("print('hello')")

    command = commands[-1]
    assert "--pull=never" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--user") + 1] == "65534:65534"
    assert command[command.index("--pids-limit") + 1] == "64"
    mounts = [item for item in command if item.startswith("type=bind,source=")]
    assert len(mounts) == 1 and "target=/workspace" in mounts[0]
    assert command[-3:] == ["python", "-I", "/workspace/main.py"]
    assert result.stdout == "program output"
    assert result.exit_code == 0


def test_sandbox_times_out_and_kills_container(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/docker")
    calls = []

    def run_factory(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    process = FakeProcess(timeout=True)
    result = SandboxRunner(
        workspace_root=tmp_path,
        popen_factory=lambda command, **kwargs: process,
        run_factory=run_factory,
    ).run_python("while True: pass", timeout_seconds=1)
    assert result.timed_out
    assert result.exit_code == 124
    assert process.killed
    assert any(command[1] == "kill" for command in calls)


def test_sandbox_rejects_out_of_policy_input_before_invoking_docker(tmp_path):
    runner = SandboxRunner(workspace_root=tmp_path)
    with pytest.raises(ValueError, match="timeout_seconds"):
        runner.run_python("print(1)", timeout_seconds=0)
    with pytest.raises(ValueError, match="1 MB"):
        runner.run_python("x" * (runner.MAX_SOURCE_BYTES + 1))


def test_sandbox_reports_missing_docker(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(SandboxUnavailableError, match="not found"):
        SandboxRunner(workspace_root=tmp_path).run_python("print(1)")


def test_sandbox_cancel_file_stops_named_container(monkeypatch, tmp_path):
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/docker")
    cancel_file = tmp_path / "cancel.signal"
    commands = []

    def run_factory(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    class CancelOnWait(FakeProcess):
        def __init__(self):
            super().__init__(timeout=False)
            self.first = True

        def wait(self, timeout=None):
            if self.first:
                self.first = False
                cancel_file.write_text("cancel", encoding="utf-8")
                raise subprocess.TimeoutExpired("docker run", timeout)
            return super().wait(timeout)

    process = CancelOnWait()
    result = SandboxRunner(
        workspace_root=tmp_path,
        popen_factory=lambda command, **kwargs: process,
        run_factory=run_factory,
    ).run_python("while True: pass", timeout_seconds=10, cancel_file=cancel_file)

    assert result.cancelled is True
    assert result.timed_out is False
    assert result.exit_code == 130
    assert process.killed is True
    assert any(command[1] == "kill" for command in commands)
