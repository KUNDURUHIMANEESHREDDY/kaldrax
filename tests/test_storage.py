import sqlite3
from pathlib import Path

import pytest

from kaldrax.storage import migrate_state_directory


def test_migrate_copies_files_and_consistent_sqlite_snapshot_without_deleting_source(tmp_path: Path):
    source = tmp_path / "checkout" / ".kaldrax"
    destination = tmp_path / "app-data" / ".kaldrax"
    source.mkdir(parents=True)
    (source / "runs").mkdir()
    (source / "runs" / "run-1.json").write_text('{"run_id":"run-1"}', encoding="utf-8")
    connection = sqlite3.connect(source / "memory.sqlite3")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT NOT NULL)")
    connection.execute("INSERT INTO memories VALUES ('m-1', 'committed in WAL')")
    connection.commit()

    result = migrate_state_directory(source, destination)

    assert result["status"] == "migrated"
    assert result["files_copied"] == 2
    assert (source / "runs" / "run-1.json").is_file()
    assert (source / "memory.sqlite3").is_file()
    assert (destination / "runs" / "run-1.json").read_text(encoding="utf-8") == '{"run_id":"run-1"}'
    migrated = sqlite3.connect(destination / "memory.sqlite3")
    assert migrated.execute("SELECT content FROM memories WHERE id='m-1'").fetchone() == ("committed in WAL",)
    migrated.close()
    connection.close()


def test_migration_is_idempotent_and_does_not_overwrite_existing_user_data(tmp_path: Path):
    source = tmp_path / "legacy"
    destination = tmp_path / "app-data"
    source.mkdir()
    destination.mkdir()
    (source / "settings.json").write_text('{"from":"legacy"}', encoding="utf-8")
    (destination / "settings.json").write_text('{"from":"new"}', encoding="utf-8")

    first = migrate_state_directory(source, destination)
    second = migrate_state_directory(source, destination)

    assert first["status"] == "migrated"
    assert first["files_copied"] == 0
    assert second["status"] == "already_migrated"
    assert (destination / "settings.json").read_text(encoding="utf-8") == '{"from":"new"}'
    assert (source / "settings.json").read_text(encoding="utf-8") == '{"from":"legacy"}'


def test_migration_skips_symlinks_and_rejects_nested_paths(tmp_path: Path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    external = tmp_path / "private.txt"
    external.write_text("do not follow", encoding="utf-8")
    try:
        (source / "private-link.txt").symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted on this platform")

    result = migrate_state_directory(source, destination)
    assert result["symlinks_skipped"] == 1
    assert not (destination / "private-link.txt").exists()
    with pytest.raises(ValueError, match="separate, non-nested"):
        migrate_state_directory(source, source / "nested")


def test_missing_legacy_state_is_a_non_error(tmp_path: Path):
    destination = tmp_path / "app-data"
    result = migrate_state_directory(tmp_path / "missing", destination)
    assert result["status"] == "no_legacy_data"
    assert destination.is_dir()
