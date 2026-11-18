"""Docker execution for bounded repository workspaces."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from .sandbox import SandboxExecutionError, SandboxResult, SandboxRunner


@dataclass(frozen=True)
class WorkspaceVerificationSuiteResult:
    """Combined test-suite and source-compilation evidence for a full repository run."""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    output_truncated: bool
    container_image: str
    cancelled: bool
    test_count: int
    steps: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class WorkspaceSandboxRunner(SandboxRunner):
    """Execute a Python module against a disposable copy of a staged repository.

    The mounted workspace is writable because test tools may create temporary files,
    but it is always a private copy. The operator's checkout is never mounted.
    """

    MAX_WORKSPACE_FILES = 5_000
    MAX_WORKSPACE_FILE_BYTES = 20_000_000
    MAX_WORKSPACE_BYTES = 100_000_000
    MAX_OUTPUT_BYTES = 1_000_000
    MAX_SUITE_OUTPUT_BYTES = 1_000_000
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
                if size > self.MAX_WORKSPACE_FILE_BYTES:
                    raise ValueError(
                        f"sandbox file exceeds the {self.MAX_WORKSPACE_FILE_BYTES}-byte limit: {relative}"
                    )
                count += 1
                total += size
                if count > self.MAX_WORKSPACE_FILES:
                    raise ValueError("sandbox workspace exceeds the 300-file limit")
                if total > self.MAX_WORKSPACE_BYTES:
                    raise ValueError("sandbox workspace exceeds the 5 MB limit")
                target = target_dir / name
                shutil.copyfile(item, target)
                target.chmod(0o755 if os.access(item, os.X_OK) else 0o644)

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

    def preflight_full_suite(self) -> dict[str, str]:
        """Confirm Docker, the local image, and pytest availability without pulling or networking."""
        docker = self._check_docker()
        try:
            inspected = self._run(
                [docker, "image", "inspect", "--format", "{{.Id}}", self.image],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise SandboxExecutionError("Unable to inspect the configured local verification image") from None
        if inspected.returncode != 0 or not str(inspected.stdout).strip():
            raise SandboxExecutionError(
                "configured verification image is not available locally; build or pull it before running KALDRAX"
            )
        probe = [
            docker, "run", "--rm", "--pull=never",
            "--network", "none",
            "--memory", "128m", "--memory-swap", "128m",
            "--cpus", "0.25", "--pids-limit", "16",
            "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16m",
            "--entrypoint", "python",
            self.image, "-B", "-c", "import pytest",
        ]
        try:
            checked = self._run(
                probe, capture_output=True, text=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise SandboxExecutionError("Unable to verify pytest availability in the configured image") from None
        if checked.returncode != 0:
            raise SandboxExecutionError(
                "configured verification image does not provide an importable pytest installation"
            )
        return {
            "image": self.image,
            "image_id": str(inspected.stdout).strip(),
            "pytest": "available",
            "pull_policy": "never",
            "network": "none",
        }

    def run_workspace_full_suite(
        self,
        workspace: Path | str,
        *,
        timeout_seconds: int = 120,
        cancel_file: Path | str | None = None,
    ) -> WorkspaceVerificationSuiteResult:
        """Run the complete configured pytest suite and compile all Python source/tests.

        The commands and discovery roots are fixed so callers cannot accidentally
        report a passing subset as a full-repository verification.
        """
        if not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        started = time.monotonic()
        specifications = (
            {
                "name": "full_test_suite",
                "module": "pytest",
                "module_args": ("-q",),
            },
            {
                "name": "source_and_test_compilation",
                "module": "compileall",
                "module_args": ("-q", "."),
            },
        )
        steps: list[dict[str, object]] = []
        for specification in specifications:
            elapsed = time.monotonic() - started
            remaining = timeout_seconds - int(elapsed)
            if remaining < 1:
                steps.append({
                    "name": specification["name"],
                    "module": specification["module"],
                    "module_args": list(specification["module_args"]),
                    "status": "not_run_timeout_budget",
                })
                continue
            result = self.run_workspace(
                workspace,
                module=specification["module"],
                module_args=specification["module_args"],
                timeout_seconds=max(1, min(120, remaining)),
                cancel_file=cancel_file,
            )
            combined_output = result.stdout + "\n" + result.stderr
            test_count = None
            if specification["name"] == "full_test_suite":
                match = re.search(r"(?m)(\d+)\s+passed\b", combined_output)
                test_count = int(match.group(1)) if match else 0
            steps.append({
                "name": specification["name"],
                "module": specification["module"],
                "module_args": list(specification["module_args"]),
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "timed_out": result.timed_out,
                "output_truncated": result.output_truncated,
                "cancelled": result.cancelled,
                "test_count": test_count,
                "container_image": result.container_image,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "status": (
                    "passed"
                    if result.exit_code == 0 and not result.timed_out
                    and not result.output_truncated
                    and (
                        specification["name"] != "full_test_suite"
                        or (test_count is not None and test_count > 0)
                    )
                    else "failed"
                ),
            })
            if result.cancelled:
                break

        stdout_parts = [
            f"=== {step['name']} ===\n{step.get('stdout', '')}"
            for step in steps if step.get("stdout")
        ]
        stderr_parts = [
            f"=== {step['name']} ===\n{step.get('stderr', '')}"
            for step in steps if step.get("stderr")
        ]
        stdout = "\n".join(stdout_parts)
        stderr = "\n".join(stderr_parts)
        truncated = any(bool(step.get("output_truncated")) for step in steps)
        if len(stdout.encode("utf-8")) > self.MAX_SUITE_OUTPUT_BYTES:
            stdout = stdout.encode("utf-8")[:self.MAX_SUITE_OUTPUT_BYTES].decode("utf-8", errors="replace")
            truncated = True
        if len(stderr.encode("utf-8")) > self.MAX_SUITE_OUTPUT_BYTES:
            stderr = stderr.encode("utf-8")[:self.MAX_SUITE_OUTPUT_BYTES].decode("utf-8", errors="replace")
            truncated = True

        timed_out = any(bool(step.get("timed_out")) for step in steps)
        cancelled = any(bool(step.get("cancelled")) for step in steps)
        test_count = next(
            (int(step["test_count"]) for step in steps if step.get("name") == "full_test_suite"
             and isinstance(step.get("test_count"), int)),
            0,
        )
        passed = (
            len(steps) == len(specifications)
            and all(step.get("status") == "passed" for step in steps)
            and test_count > 0
        )
        first_failure = next(
            (step for step in steps if step.get("status") != "passed"),
            None,
        )
        failure_code = (
            int(first_failure["exit_code"])
            if first_failure is not None and isinstance(first_failure.get("exit_code"), int)
            else 124 if timed_out else 130 if cancelled else 1
        )
        exit_code = 0 if passed else (failure_code if failure_code != 0 else 1)
        image = next(
            (str(step["container_image"]) for step in steps if step.get("container_image")),
            self.image,
        )
        return WorkspaceVerificationSuiteResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=int((time.monotonic() - started) * 1000),
            timed_out=timed_out,
            output_truncated=truncated,
            container_image=image,
            cancelled=cancelled,
            test_count=test_count,
            steps=tuple(steps),
        )

