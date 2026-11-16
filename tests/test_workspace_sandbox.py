import io
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

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
