"""Docker execution for bounded repository workspaces."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

from .sandbox import SandboxExecutionError, SandboxResult, SandboxRunner


class WorkspaceSandboxRunner(SandboxRunner):
    """Execute a Python module against a disposable copy of a staged repository.

    The mounted workspace is writable because test tools may create temporary files,
    but it is always a private copy. The operator's checkout is never mounted.
    """

    MAX_WORKSPACE_FILES = 300
    MAX_WORKSPACE_BYTES = 5_000_000
    MAX_OUTPUT_BYTES = 1_000_000
    EXCLUDED_DIRS = {
        ".git", ".kaldrax", ".venv", "venv", "env", "node_modules",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".tox", "dist", "build", "coverage", ".next", ".turbo",
        ".aws", ".ssh", ".docker", ".kube", "secrets", "credentials", "certs", "certificates",
    }
    ALLOWED_MODULES = {"compileall", "unittest", "pytest"}

    def __init__(self, *, image: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        selected = image or self.IMAGE
        if not isinstance(selected, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9./:_@-]{0,255}", selected):
            raise ValueError("sandbox image must be a valid Docker image reference")
        self.image = selected

    def _copy_workspace(self, source: Path, destination: Path) -> None:
        if not source.is_dir():
            raise ValueError("workspace must be a directory")
        total = 0
        count = 0
        destination.mkdir(parents=True)
        for current, dirs, names in os.walk(source, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(
                name for name in dirs
                if name.casefold() not in self.EXCLUDED_DIRS
                and not (current_path / name).is_symlink()
            )
            relative_dir = current_path.relative_to(source)
            target_dir = destination / relative_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_dir.chmod(0o777)
            for name in sorted(names):
                item = current_path / name
                relative = item.relative_to(source).as_posix()
                if item.is_symlink():
                    raise ValueError(f"sandbox workspace cannot contain symlinks: {relative}")
                if item.name == ".env" or (item.name.startswith(".env.") and item.name != ".env.example"):
                    continue
                if item.name.casefold() in {
                    ".netrc", ".npmrc", ".pypirc", "credentials", "credentials.json",
                    "token.json", "auth.json", "client_secret.json", "id_rsa", "id_ed25519",
                    "service-account.json", "service-account-credentials.json", "known_hosts",
                }:
                    continue
                if item.suffix.casefold() in {
                    ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx",
                    ".token", ".secret", ".pypirc", ".tfstate", ".tfstate.backup",
                }:
                    continue
                if not item.is_file():
                    continue
                size = item.stat().st_size
                count += 1
                total += size
                if count > self.MAX_WORKSPACE_FILES:
                    raise ValueError("sandbox workspace exceeds the 300-file limit")
                if total > self.MAX_WORKSPACE_BYTES:
                    raise ValueError("sandbox workspace exceeds the 5 MB limit")
                target = target_dir / name
                shutil.copyfile(item, target)
                target.chmod(0o644)

    def run_workspace(
        self,
        workspace: Path | str,
        *,
        module: str = "unittest",
        module_args: tuple[str, ...] = ("discover", "-s", "tests", "-v"),
        timeout_seconds: int = 120,
        memory_mb: int = 512,
        cpu_count: float = 1.0,
        pids_limit: int = 128,
        cancel_file: Path | str | None = None,
    ) -> SandboxResult:
        if module not in self.ALLOWED_MODULES:
            raise ValueError(f"module must be one of: {', '.join(sorted(self.ALLOWED_MODULES))}")
        if len(module_args) > 30 or any(
            not isinstance(item, str) or "\x00" in item or len(item) > 500
            for item in module_args
        ):
            raise ValueError("verification arguments are invalid or exceed the size limit")
        if not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        if not 64 <= memory_mb <= 1024:
            raise ValueError("memory_mb must be between 64 and 1024")
        if not 0.25 <= cpu_count <= 2.0:
            raise ValueError("cpu_count must be between 0.25 and 2.0")
        if not 16 <= pids_limit <= 128:
            raise ValueError("pids_limit must be between 16 and 128")

        docker = self._check_docker()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        source = Path(workspace).expanduser().resolve(strict=True)
        if "," in str(source):
            raise ValueError("sandbox workspace path cannot contain commas")
        name = f"kaldrax-workspace-{uuid4().hex[:12]}"
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="workspace-", dir=self.workspace_root) as folder:
            disposable = Path(folder) / "project"
            self._copy_workspace(source, disposable)
            command = [
                docker, "run", "--rm", "--pull=never", "--name", name,
                "--network", "none",
                "--memory", f"{memory_mb}m", "--memory-swap", f"{memory_mb}m",
                "--cpus", str(cpu_count), "--pids-limit", str(pids_limit),
                "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--user", "65534:65534",
                "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=128m",
                "--mount", f"type=bind,source={disposable.resolve()},target=/workspace",
                "--workdir", "/workspace",
                "--env", "HOME=/tmp",
                "--env", "PYTHONDONTWRITEBYTECODE=1",
                "--env", "PYTHONPATH=/workspace/src:/workspace",
                self.image, "python", "-B", "-m", module, *module_args,
            ]
            try:
                process = self._popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except OSError as exc:
                raise SandboxExecutionError(
                    f"Unable to start Docker workspace execution: {type(exc).__name__}"
                ) from None

            stdout_buffer = bytearray()
            stderr_buffer = bytearray()
            stdout_truncated = [False]
            stderr_truncated = [False]
            readers = [
                threading.Thread(
                    target=self._drain,
                    args=(process.stdout, stdout_buffer, self.MAX_OUTPUT_BYTES, stdout_truncated),
                    daemon=True,
                ),
                threading.Thread(
                    target=self._drain,
                    args=(process.stderr, stderr_buffer, self.MAX_OUTPUT_BYTES, stderr_truncated),
                    daemon=True,
                ),
            ]
            for reader in readers:
                reader.start()
            timed_out = False
            cancelled = False
            deadline = time.monotonic() + timeout_seconds
            cancel_path = Path(cancel_file) if cancel_file is not None else None
            while True:
                if cancel_path is not None and cancel_path.exists():
                    cancelled = True
                    process.kill()
                    process.wait()
                    try:
                        self._run(
                            [docker, "kill", name], capture_output=True, text=True,
                            timeout=5, check=False,
                        )
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                    exit_code = 130
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    process.kill()
                    process.wait()
                    try:
                        self._run(
                            [docker, "kill", name], capture_output=True, text=True,
                            timeout=5, check=False,
                        )
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                    exit_code = 124
                    break
                try:
                    exit_code = process.wait(timeout=min(0.2, remaining))
                    break
                except subprocess.TimeoutExpired:
                    time.sleep(min(0.05, remaining))
            for reader in readers:
                reader.join(timeout=2)
            duration_ms = int((time.monotonic() - started) * 1000)
            truncated = stdout_truncated[0] or stderr_truncated[0]
            if truncated:
                marker = b"\n[output truncated at 1 MB]"
                target = stdout_buffer if len(stdout_buffer) < self.MAX_OUTPUT_BYTES else stderr_buffer
                target.extend(marker[: max(0, self.MAX_OUTPUT_BYTES - len(target))])
            return SandboxResult(
                exit_code=int(exit_code),
                stdout=stdout_buffer.decode("utf-8", errors="replace"),
                stderr=stderr_buffer.decode("utf-8", errors="replace"),
                duration_ms=duration_ms,
                timed_out=timed_out,
                output_truncated=truncated,
                container_image=self.image,
                cancelled=cancelled,
            )
