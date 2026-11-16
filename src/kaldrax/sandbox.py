"""Docker-backed sandbox for executing untrusted Python source with hard limits."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


class SandboxUnavailableError(RuntimeError):
    """Docker CLI/daemon is not available."""


class SandboxExecutionError(RuntimeError):
    """Sandbox configuration or execution failed."""


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    output_truncated: bool
    container_image: str
    cancelled: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SandboxRunner:
    """Run one Python file inside a disposable, network-isolated Docker container.

    Only a private temporary workspace is mounted read/write. The container root
    filesystem is read-only; Linux capabilities are dropped; the process runs as
    an unprivileged UID with memory, CPU, PID, wall-time, and output limits.
    """

    IMAGE = "python:3.13-slim"
    MAX_SOURCE_BYTES = 1_000_000
    MAX_OUTPUT_BYTES = 1_000_000

    def __init__(
        self,
        *,
        workspace_root: Path | str = ".kaldrax/sandbox",
        popen_factory=subprocess.Popen,
        run_factory=subprocess.run,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self._popen = popen_factory
        self._run = run_factory

    @staticmethod
    def _drain(stream, buffer: bytearray, limit: int, truncated: list[bool]) -> None:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            remaining = limit - len(buffer)
            if remaining > 0:
                buffer.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated[0] = True

    def _check_docker(self) -> str:
        docker = shutil.which("docker")
        if not docker:
            raise SandboxUnavailableError("Docker CLI was not found on PATH")
        try:
            result = self._run(
                [docker, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise SandboxUnavailableError("Docker daemon is unavailable") from None
        if result.returncode != 0:
            raise SandboxUnavailableError("Docker daemon is unavailable")
        return docker

    def run_python(
        self,
        source: str,
        *,
        timeout_seconds: int = 15,
        memory_mb: int = 256,
        cpu_count: float = 1.0,
        pids_limit: int = 64,
        cancel_file: Path | str | None = None,
    ) -> SandboxResult:
        if not isinstance(source, str):
            raise ValueError("source must be text")
        if len(source.encode("utf-8")) > self.MAX_SOURCE_BYTES:
            raise ValueError("source exceeds the 1 MB sandbox limit")
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
        name = f"kaldrax-sandbox-{uuid4().hex[:12]}"
        started = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="run-", dir=self.workspace_root) as folder:
            workdir = Path(folder)
            workdir.chmod(0o755)
            source_path = str(workdir.resolve())
            if "," in source_path:
                raise ValueError("sandbox workspace path cannot contain commas")
            script = workdir / "main.py"
            script.write_text(source, encoding="utf-8")
            script.chmod(0o644)
            command = [
                docker, "run", "--rm", "--pull=never", "--name", name,
                "--network", "none",
                "--memory", f"{memory_mb}m", "--memory-swap", f"{memory_mb}m",
                "--cpus", str(cpu_count), "--pids-limit", str(pids_limit),
                "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--user", "65534:65534",
                "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "--mount", f"type=bind,source={source_path},target=/workspace",
                "--workdir", "/workspace",
                "--env", "HOME=/tmp",
                "--env", "PYTHONDONTWRITEBYTECODE=1",
                self.IMAGE, "python", "-I", "/workspace/main.py",
            ]
            try:
                process = self._popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except OSError as exc:
                raise SandboxUnavailableError(f"Unable to start Docker: {type(exc).__name__}") from None

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
                            [docker, "kill", name],
                            capture_output=True, text=True, timeout=5, check=False,
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
                            [docker, "kill", name],
                            capture_output=True, text=True, timeout=5, check=False,
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
            output_truncated = stdout_truncated[0] or stderr_truncated[0]
            if output_truncated:
                marker = b"\n[output truncated at 1 MB]"
                if len(stdout_buffer) < self.MAX_OUTPUT_BYTES:
                    stdout_buffer.extend(marker[: self.MAX_OUTPUT_BYTES - len(stdout_buffer)])
                else:
                    stderr_buffer.extend(marker[: max(0, self.MAX_OUTPUT_BYTES - len(stderr_buffer))])
            return SandboxResult(
                exit_code=int(exit_code),
                stdout=stdout_buffer.decode("utf-8", errors="replace"),
                stderr=stderr_buffer.decode("utf-8", errors="replace"),
                duration_ms=duration_ms,
                timed_out=timed_out,
                output_truncated=output_truncated,
                container_image=self.IMAGE,
                cancelled=cancelled,
            )
