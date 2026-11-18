"""Bounded, secret-aware Git workspace snapshots and transactional patch staging."""
from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
from uuid import uuid4
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator


class WorkspaceError(RuntimeError):
    """The target repository or proposed patch violates workspace policy."""


@dataclass(frozen=True)
class WorkspaceFile:
    path: str
    content: str


@dataclass(frozen=True)
class WorkspaceSnapshot:
    root: Path
    head: str
    files: tuple[WorkspaceFile, ...]
    omitted_paths: tuple[str, ...]
    total_bytes: int
    submodule_paths: tuple[str, ...] = ()

    def to_manifest(self) -> dict[str, object]:
        return {
            "repository_name": self.root.name,
            "base_commit": self.head,
            "files": [{"path": item.path, "characters": len(item.content)} for item in self.files],
            "omitted_paths": list(self.omitted_paths),
            "snapshot_bytes": self.total_bytes,
            "submodule_paths": list(self.submodule_paths),
            "notice": "Omitted paths are not available to the agent; do not assume their contents.",
        }

    def to_prompt(self) -> dict[str, object]:
        return {
            **self.to_manifest(),
            "files": [{"path": item.path, "content": item.content} for item in self.files],
        }


class RepositoryWorkspace:
    """Capture a clean Git checkout, stage a patch in isolation, and apply on success."""

    MAX_FILES = 240
    MAX_FILE_BYTES = 48_000
    MAX_TOTAL_BYTES = 45_000
    MAX_PATCH_BYTES = 750_000
    EXCLUDED_DIRS = {
        ".git", ".kaldrax", ".venv", "venv", "env", "node_modules",
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        ".tox", "dist", "build", "coverage", ".next", ".turbo",
        ".aws", ".ssh", ".docker", ".kube", "secrets", "credentials", "certs", "certificates",
    }
    PRIVATE_SUFFIXES = {
        ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx",
        ".token", ".secret", ".pypirc", ".tfstate", ".tfstate.backup",
    }
    PRIVATE_NAMES = {
        ".env", ".netrc", ".npmrc", ".pypirc", "credentials", "credentials.json",
        "token.json", "auth.json", "client_secret.json", "id_rsa", "id_ed25519",
        "service-account.json", "service-account-credentials.json", "known_hosts",
    }

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise WorkspaceError("workspace must be a directory")
        top = self._git(["rev-parse", "--show-toplevel"]).strip()
        if Path(top).resolve() != self.root:
            raise WorkspaceError("workspace must be the Git repository root")

    def _git(self, args: list[str], *, input_text: str | None = None) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), *args],
                input=input_text.encode("utf-8") if input_text is not None else None,
                capture_output=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkspaceError(f"Git command unavailable: {type(exc).__name__}") from None
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            message = stderr or stdout or "Git command failed"
            raise WorkspaceError(message[:1000])
        return result.stdout.decode("utf-8", errors="replace")

    def _assert_clean(self) -> None:
        status = self._git(["status", "--porcelain", "--untracked-files=all"])
        if status.strip():
            raise WorkspaceError(
                "workspace has uncommitted or untracked files; commit or move them before an engineering run"
            )

    @staticmethod
    def _is_private(path: str) -> bool:
        parts = tuple(part.casefold() for part in PurePosixPath(path).parts)
        name = parts[-1] if parts else ""
        if name in {".git", ".kaldrax"}:
            return True
        if any(part in {
            ".git", ".kaldrax", ".aws", ".ssh", ".docker", ".kube",
            "secrets", "credentials", "certs", "certificates",
        } for part in parts[:-1]):
            return True
        if name in RepositoryWorkspace.PRIVATE_NAMES:
            return True
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            return True
        return PurePosixPath(name).suffix in RepositoryWorkspace.PRIVATE_SUFFIXES

    def checkpoint_binding(self) -> dict[str, str]:
        """Return the canonical repository root and full HEAD for safe checkpoint resume."""
        self._assert_clean()
        head = self._git(["rev-parse", "HEAD"]).strip()
        if len(head) not in {40, 64} or any(char not in "0123456789abcdefABCDEF" for char in head):
            raise WorkspaceError("Git returned an invalid repository HEAD")
        return {"root": str(self.root), "head": head}

    def capture(self) -> WorkspaceSnapshot:
        self._assert_clean()
        head = self._git(["rev-parse", "HEAD"]).strip()
        candidates: list[tuple[int, str, Path, bytes]] = []
        omitted: list[str] = []
        staged_index = self._git(["ls-files", "--stage"])
        submodules = tuple(sorted({
            line.split("\t", 1)[1]
            for line in staged_index.splitlines()
            if line.startswith("160000 ") and "\t" in line
        }))
        priority = {
            "src": 0, "app": 0, "lib": 0, "tests": 0, "test": 0,
            "packages": 1, "config": 1, "scripts": 1,
            "docs": 3, "benchmarks": 4, "examples": 4,
        }
        for current, dirs, names in os.walk(self.root, followlinks=False):
            current_path = Path(current)
            current_relative = current_path.relative_to(self.root).as_posix()
            skipped_dirs = [
                name for name in dirs
                if name.casefold() in self.EXCLUDED_DIRS
                or (current_path / name).is_symlink()
                or (f"{current_relative}/{name}" if current_relative != "." else name) in submodules
            ]
            omitted.extend((current_path / name).relative_to(self.root).as_posix() for name in skipped_dirs)
            dirs[:] = sorted(
                (name for name in dirs
                 if name.casefold() not in self.EXCLUDED_DIRS
                 and not (current_path / name).is_symlink()
                 and (f"{current_relative}/{name}" if current_relative != "." else name) not in submodules),
                key=lambda name: (priority.get(name.casefold(), 2), name.casefold()),
            )
            for name in names:
                path = current_path / name
                relative = path.relative_to(self.root).as_posix()
                if self._is_private(relative):
                    omitted.append(relative)
                    continue
                if path.is_symlink() or not path.is_file():
                    omitted.append(relative)
                    continue
                try:
                    size = path.stat().st_size
                    if size > self.MAX_FILE_BYTES:
                        omitted.append(relative)
                        continue
                    raw = path.read_bytes()
                    raw.decode("utf-8")
                except (OSError, UnicodeDecodeError):
                    omitted.append(relative)
                    continue
                first = PurePosixPath(relative).parts[0].casefold()
                file_priority = priority.get(first, 2)
                if first == "src" and relative.endswith(".py"):
                    file_priority = 0
                elif first == "tests":
                    file_priority = 0
                elif relative.casefold().endswith((".py", ".toml", ".yaml", ".yml", ".json")):
                    file_priority = min(file_priority, 1)
                candidates.append((file_priority, relative, path, raw))

        files: list[WorkspaceFile] = []
        total = 0
        for _, relative, path, raw in sorted(candidates, key=lambda item: (item[0], item[1].casefold())):
            if len(files) >= self.MAX_FILES or total + len(raw) > self.MAX_TOTAL_BYTES:
                omitted.append(relative)
                continue
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                omitted.append(relative)
                continue
            files.append(WorkspaceFile(relative, content))
            total += len(raw)
        return WorkspaceSnapshot(
            root=self.root, head=head, files=tuple(files),
            omitted_paths=tuple(sorted(set(omitted))), total_bytes=total,
            submodule_paths=submodules,
        )

    @classmethod
    def changed_paths(cls, patch: str) -> tuple[str, ...]:
        if not isinstance(patch, str) or not patch.strip():
            raise WorkspaceError("builder patch must be a non-empty unified Git diff")
        if len(patch.encode("utf-8")) > cls.MAX_PATCH_BYTES:
            raise WorkspaceError("builder patch exceeds the 750 KB limit")
        forbidden_markers = (
            "GIT binary patch", "Binary files ", "Submodule ",
            "old mode ", "new mode ", "rename from ", "rename to ",
        )
        if any(marker in patch for marker in forbidden_markers):
            raise WorkspaceError("binary patches, renames, submodules, and mode changes are not supported")
        changed: set[str] = set()
        current_old: str | None = None
        current_new: str | None = None
        seen_old = False
        seen_new = False

        def finish_section() -> None:
            if current_old is not None and (not seen_old or not seen_new):
                raise WorkspaceError("each patch section must include matching --- and +++ file headers")

        for line in patch.splitlines():
            if line.startswith("diff --git "):
                finish_section()
                parts = line.split()
                if len(parts) != 4 or not parts[2].startswith("a/") or not parts[3].startswith("b/"):
                    raise WorkspaceError("patch contains an unsupported or quoted diff path")
                current_old, current_new = parts[2][2:], parts[3][2:]
                cls._validate_path(current_old)
                cls._validate_path(current_new)
                changed.update((current_old, current_new))
                seen_old = seen_new = False
                continue
            if line.startswith("--- "):
                if current_old is None or seen_old:
                    raise WorkspaceError("patch contains an unexpected old-file header")
                token = line[4:].split("\t", 1)[0]
                actual = None if token == "/dev/null" else token[2:] if token.startswith("a/") else None
                if actual is not None:
                    cls._validate_path(actual)
                if token != "/dev/null" and actual != current_old:
                    raise WorkspaceError("patch old-file header does not match its diff path")
                seen_old = True
            elif line.startswith("+++ "):
                if current_new is None or not seen_old or seen_new:
                    raise WorkspaceError("patch contains an unexpected new-file header")
                token = line[4:].split("\t", 1)[0]
                actual = None if token == "/dev/null" else token[2:] if token.startswith("b/") else None
                if actual is not None:
                    cls._validate_path(actual)
                if token != "/dev/null" and actual != current_new:
                    raise WorkspaceError("patch new-file header does not match its diff path")
                seen_new = True
        finish_section()
        if current_old is None:
            raise WorkspaceError("patch must contain at least one 'diff --git' section")
        return tuple(sorted(changed))

    @staticmethod
    def _validate_path(path: str) -> None:
        candidate = PurePosixPath(path)
        if (
            not path or "\\" in path or "\x00" in path or ":" in path
            or candidate.is_absolute() or any(part in {"", ".", ".."} for part in path.split("/"))
        ):
            raise WorkspaceError("patch contains an unsafe path")
        if any(part.casefold() in RepositoryWorkspace.EXCLUDED_DIRS for part in candidate.parts):
            raise WorkspaceError("patch cannot modify Git metadata, runtime state, or excluded dependency/build paths")
        if RepositoryWorkspace._is_private(path):
            raise WorkspaceError("patch cannot modify private environment or credential files")

    @contextmanager
    def staged_patch(
        self, snapshot: WorkspaceSnapshot, patch: str,
    ) -> Iterator[tuple[Path, tuple[str, ...]]]:
        if snapshot.root != self.root:
            raise WorkspaceError("snapshot belongs to a different repository")
        changed = self.changed_paths(patch)
        if any(
            path == submodule or path.startswith(f"{submodule}/")
            for path in changed for submodule in snapshot.submodule_paths
        ):
            raise WorkspaceError("patch cannot modify Git submodule contents")
        with tempfile.TemporaryDirectory(prefix="kaldrax-stage-") as temporary:
            stage = Path(temporary) / "workspace"
            stage.mkdir()
            for item in snapshot.files:
                destination = stage / item.path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(item.content, encoding="utf-8", newline="")
            self._run_git_in(stage, ["init", "--quiet"])
            self._run_git_in(stage, ["add", "--all"])
            self._run_git_in(
                stage, ["apply", "--check", "--whitespace=error-all", "-"], input_text=patch,
            )
            self._run_git_in(
                stage, ["apply", "--whitespace=error-all", "-"], input_text=patch,
            )
            yield stage, changed

    @staticmethod
    def _run_git_in(path: Path, args: list[str], *, input_text: str | None = None) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), *args],
                input=input_text.encode("utf-8") if input_text is not None else None,
                capture_output=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkspaceError(f"Git staging failed: {type(exc).__name__}") from None
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            message = stderr or stdout or "Git staging failed"
            raise WorkspaceError(message[:1000])
        return result.stdout.decode("utf-8", errors="replace")

    def apply_patch(self, snapshot: WorkspaceSnapshot, patch: str) -> tuple[str, ...]:
        changed = self.changed_paths(patch)
        if snapshot.root != self.root:
            raise WorkspaceError("snapshot belongs to a different repository")
        if any(
            path == submodule or path.startswith(f"{submodule}/")
            for path in changed for submodule in snapshot.submodule_paths
        ):
            raise WorkspaceError("patch cannot modify Git submodule contents")
        self._assert_clean()
        current_head = self._git(["rev-parse", "HEAD"]).strip()
        if current_head != snapshot.head:
            raise WorkspaceError("repository HEAD changed during the engineering run; refusing to apply stale patch")
        for relative in changed:
            parts = PurePosixPath(relative).parts
            for length in range(1, len(parts) + 1):
                target = self.root.joinpath(*parts[:length])
                if target.is_symlink():
                    raise WorkspaceError(f"refusing to modify a symlink path component: {relative}")
        self._git(["apply", "--check", "--whitespace=error-all", "-"], input_text=patch)
        self._git(["apply", "--whitespace=error-all", "-"], input_text=patch)
        try:
            self._git(["diff", "--check"])
        except WorkspaceError:
            self._git(["apply", "--reverse", "-"], input_text=patch)
            raise
        return changed

    TEXT_SUFFIXES = {
        ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
        ".html", ".css", ".scss", ".json", ".jsonc", ".toml", ".yaml",
        ".yml", ".md", ".mdx", ".txt", ".rst", ".sh", ".ps1", ".bat",
        ".cmd", ".rs", ".go", ".java", ".kt", ".c", ".h", ".cpp", ".hpp",
        ".cs", ".sql", ".xml", ".ini", ".cfg", ".conf", ".gitignore",
        ".dockerignore", ".editorconfig", ".properties",
    }
    MAX_DESKTOP_FILE_BYTES = 1_000_000

    def status(self) -> dict[str, object]:
        raw = self._git(["status", "--porcelain=v1", "--untracked-files=all"])
        changes: list[dict[str, str]] = []
        for line in raw.splitlines():
            if len(line) < 4:
                continue
            code = line[:2].strip() or "??"
            relative = line[3:].strip()
            if " -> " in relative:
                relative = relative.rsplit(" -> ", 1)[-1]
            changes.append({"code": code, "path": relative.strip('"')})
        branch = self._git(["branch", "--show-current"]).strip()
        head = self._git(["rev-parse", "--short", "HEAD"]).strip()
        return {
            "root": str(self.root),
            "branch": branch or f"detached@{head}",
            "head": head,
            "clean": not raw.strip(),
            "status": raw,
            "changes": changes,
        }

    def _safe_target(self, relative_path: str, *, allow_missing: bool) -> tuple[str, Path]:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise WorkspaceError("repository-relative path is required")
        self._validate_path(relative_path)
        parts = PurePosixPath(relative_path).parts
        target = self.root.joinpath(*parts)
        current = self.root
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise WorkspaceError("refusing to access a symlink path component")
        try:
            resolved = target.resolve(strict=not allow_missing)
        except OSError as exc:
            raise WorkspaceError(f"repository path cannot be resolved: {type(exc).__name__}") from None
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise WorkspaceError("repository path resolves outside the selected worktree") from None
        return PurePosixPath(*parts).as_posix(), target

    def list_files(self, directory: str = ".", *, limit: int = 300) -> list[dict[str, object]]:
        if not 1 <= limit <= 500:
            raise WorkspaceError("file limit must be between 1 and 500")
        if directory in {"", "."}:
            base = self.root
        else:
            _, base = self._safe_target(directory, allow_missing=False)
        if not base.is_dir() or base.is_symlink():
            raise WorkspaceError("selected repository directory does not exist")
        files: list[dict[str, object]] = []
        for current, dirs, names in os.walk(base, followlinks=False):
            current_path = Path(current)
            dirs[:] = sorted(
                name for name in dirs
                if name.casefold() not in self.EXCLUDED_DIRS
                and not (current_path / name).is_symlink()
            )
            for name in sorted(names, key=str.casefold):
                item = current_path / name
                if item.is_symlink() or not item.is_file():
                    continue
                relative = item.relative_to(self.root).as_posix()
                if self._is_private(relative) or item.suffix.casefold() not in self.TEXT_SUFFIXES:
                    continue
                size = item.stat().st_size
                if size > self.MAX_DESKTOP_FILE_BYTES:
                    continue
                files.append({"path": relative, "size": size})
                if len(files) >= limit:
                    return sorted(files, key=lambda value: str(value["path"]).casefold())
        return sorted(files, key=lambda value: str(value["path"]).casefold())

    def read_file(self, relative_path: str) -> dict[str, object]:
        relative, target = self._safe_target(relative_path, allow_missing=False)
        if not target.is_file():
            raise WorkspaceError("selected repository path is not a file")
        size = target.stat().st_size
        if size > self.MAX_DESKTOP_FILE_BYTES:
            raise WorkspaceError("file exceeds the 1 MB desktop inspection limit")
        try:
            raw = target.read_bytes()
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise WorkspaceError("file is not valid UTF-8 text") from None
        return {
            "path": relative,
            "content": content,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        }

    def apply_file(
        self,
        relative_path: str,
        content: str,
        *,
        expected_sha256: str | None,
    ) -> dict[str, object]:
        relative, target = self._safe_target(relative_path, allow_missing=True)
        if not isinstance(content, str):
            raise WorkspaceError("edited content must be text")
        raw = content.encode("utf-8")
        if len(raw) > self.MAX_DESKTOP_FILE_BYTES:
            raise WorkspaceError("edited file exceeds the 1 MB limit")
        existed = target.exists()
        if existed:
            if not target.is_file():
                raise WorkspaceError("selected repository path is not a regular file")
            if not expected_sha256:
                raise WorkspaceError("an expected SHA-256 is required before replacing an existing file")
            old_raw = target.read_bytes()
            old_sha = hashlib.sha256(old_raw).hexdigest()
            if old_sha.casefold() != expected_sha256.casefold():
                raise WorkspaceError("file changed since it was read; refresh before applying edits")
            try:
                old_text = old_raw.decode("utf-8")
            except UnicodeDecodeError:
                raise WorkspaceError("existing file is not valid UTF-8 text") from None
            old_mode = stat.S_IMODE(target.stat().st_mode)
        else:
            if expected_sha256:
                raise WorkspaceError("file no longer exists; refresh before applying edits")
            old_raw = b""
            old_text = ""
            old_sha = None
            old_mode = 0o644

        target.parent.mkdir(parents=True, exist_ok=True)
        current = self.root
        for part in PurePosixPath(relative).parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise WorkspaceError("refusing to write through a symlink path component")

        backup_path: Path | None = None
        if existed:
            runtime_root = self.root / ".kaldrax"
            if runtime_root.is_symlink() or (runtime_root.exists() and not runtime_root.is_dir()):
                raise WorkspaceError("refusing to write backups through an unsafe .kaldrax runtime path")
            backup_parent = runtime_root / "desktop-backups"
            if backup_parent.is_symlink() or (backup_parent.exists() and not backup_parent.is_dir()):
                raise WorkspaceError("refusing to write backups through an unsafe desktop-backups path")
            backup_root = backup_parent / uuid4().hex
            backup_path = backup_root / Path(*PurePosixPath(relative).parts)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup_path)

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".kaldrax-edit-", suffix=".tmp",
                dir=target.parent, delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary_path, old_mode)
            os.replace(temporary_path, target)
            temporary_path = None
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

        new_sha = hashlib.sha256(raw).hexdigest()
        diff = "".join(difflib.unified_diff(
            old_text.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{relative}" if existed else "/dev/null",
            tofile=f"b/{relative}",
        ))
        return {
            "path": relative,
            "created": not existed,
            "old_sha256": old_sha,
            "new_sha256": new_sha,
            "backup_path": str(backup_path) if backup_path else None,
            "diff": diff,
            "size": len(raw),
        }
