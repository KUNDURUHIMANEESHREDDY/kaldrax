"""Safe, non-destructive migration of local KALDRAX state."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def _copy_regular_file(source: Path, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return False
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.migration-tmp")
    try:
        shutil.copy2(source, temporary, follow_symlinks=False)
        if temporary.is_symlink():
            return False
        if destination.exists():
            return False
        temporary.rename(destination)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _backup_sqlite_database(source: Path, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return False
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.migration-tmp")
    source_uri = source.resolve().as_uri() + "?mode=ro"
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(source_uri, uri=True, timeout=30)
        destination_connection = sqlite3.connect(temporary, timeout=30)
        source_connection.backup(destination_connection)
        destination_connection.execute("PRAGMA journal_mode=DELETE")
        destination_connection.commit()
        destination_connection.close()
        destination_connection = None
        source_connection.close()
        source_connection = None
        if destination.exists():
            return False
        temporary.rename(destination)
        return True
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
        temporary.unlink(missing_ok=True)


def migrate_state_directory(source_dir: Path | str, destination_dir: Path | str) -> dict[str, object]:
    """Copy a legacy state tree once; never remove or overwrite source/user data.

    SQLite memory state is migrated through SQLite's backup API so committed WAL
    transactions are included in a consistent snapshot. Symlinks and special
    files are skipped rather than followed.
    """
    source_input = Path(source_dir).expanduser()
    if source_input.is_symlink():
        raise ValueError("legacy state source must not be a symlink")
    source = source_input.resolve()
    destination = Path(destination_dir).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("source and destination state directories must be separate, non-nested paths")

    source_key = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:16]
    marker = destination / f".legacy-migration-{source_key}.json"
    if marker.is_file():
        return {
            "status": "already_migrated",
            "source": str(source),
            "destination": str(destination),
            "files_copied": 0,
            "bytes_copied": 0,
            "symlinks_skipped": 0,
        }
    if not source.exists():
        return {
            "status": "no_legacy_data",
            "source": str(source),
            "destination": str(destination),
            "files_copied": 0,
            "bytes_copied": 0,
            "symlinks_skipped": 0,
        }
    if not source.is_dir():
        raise ValueError("legacy state source must be a directory")

    files_copied = 0
    bytes_copied = 0
    symlinks_skipped = 0
    database_source = source / "memory.sqlite3"
    database_destination = destination / "memory.sqlite3"
    if database_source.is_file() and not database_source.is_symlink():
        if _backup_sqlite_database(database_source, database_destination):
            files_copied += 1
            bytes_copied += database_source.stat().st_size

    sqlite_sidecars = {
        "memory.sqlite3",
        "memory.sqlite3-wal",
        "memory.sqlite3-shm",
        "memory.sqlite3-journal",
    }
    for current, directories, filenames in os.walk(source, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in directories:
            candidate = current_path / name
            try:
                info = candidate.lstat()
            except OSError:
                symlinks_skipped += 1
                continue
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                symlinks_skipped += 1
                continue
            kept_directories.append(name)
        directories[:] = kept_directories

        for name in filenames:
            candidate = current_path / name
            relative = candidate.relative_to(source)
            if relative.name in sqlite_sidecars:
                continue
            try:
                info = candidate.lstat()
            except OSError:
                symlinks_skipped += 1
                continue
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                symlinks_skipped += 1
                continue
            target = destination / relative
            try:
                copied = _copy_regular_file(candidate, target)
            except OSError as exc:
                raise RuntimeError(
                    f"could not migrate {relative.as_posix()}: {type(exc).__name__}"
                ) from None
            if copied:
                files_copied += 1
                bytes_copied += info.st_size

    result: dict[str, object] = {
        "status": "migrated",
        "source": str(source),
        "destination": str(destination),
        "files_copied": files_copied,
        "bytes_copied": bytes_copied,
        "symlinks_skipped": symlinks_skipped,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary_marker = marker.with_name(f".{marker.name}.{uuid4().hex}.tmp")
    try:
        temporary_marker.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        temporary_marker.replace(marker)
    finally:
        temporary_marker.unlink(missing_ok=True)
    return result
