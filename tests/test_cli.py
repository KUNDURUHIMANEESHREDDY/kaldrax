import json

import pytest

from kaldrax.cli import main
from kaldrax.memory import MemoryRecord, MemoryStatus, MemoryType, SQLiteMemoryStore


def test_run_requires_executor_and_evaluator_models(monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "run", "--objective", "Build feature", "--criterion", "tests pass"
    ])
    monkeypatch.setenv("KALDRAX_API_KEY", "secret")
    monkeypatch.setenv("KALDRAX_MODEL", "executor-model")
    monkeypatch.delenv("KALDRAX_EVALUATOR_MODEL", raising=False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_run_requires_separate_evaluator_model(monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "run", "--objective", "Build feature", "--criterion", "tests pass"
    ])
    monkeypatch.setenv("KALDRAX_API_KEY", "secret")
    monkeypatch.setenv("KALDRAX_MODEL", "same-model")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "SAME-MODEL")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_demo_uses_persistent_project_memory(tmp_path, monkeypatch, capsys):
    database = tmp_path / "memory.sqlite3"
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "demo", "--artifacts", str(tmp_path / "runs"),
        "--memory-db", str(database), "--project", "cli-project",
    ])
    assert main() == 0
    report = json.loads(capsys.readouterr().out)
    assert any(event["event_type"] == "memory_saved" for event in report["events"])
    store = SQLiteMemoryStore(database)
    assert store.count(project_id="cli-project") == 1
    store.close()


def test_memory_search_can_include_pending_records(tmp_path, monkeypatch, capsys):
    database = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(database)
    store.save(MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC,
        content="Lesson: inspect pending deployment decisions",
        status=MemoryStatus.PENDING,
    ))
    store.close()
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "memory", "search", "--query", "pending deployment",
        "--project", "p", "--include-pending", "--memory-db", str(database),
    ])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result[0]["status"] == "pending"


def test_memory_review_command_approves_pending_record(tmp_path, monkeypatch, capsys):
    database = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(database)
    record = MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC,
        content="Lesson: keep local project memory encrypted",
        status=MemoryStatus.PENDING,
    )
    store.save(record)
    store.close()
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "memory", "review", "--id", record.id,
        "--decision", "approve", "--reviewer", "operator",
        "--memory-db", str(database),
    ])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "active"
    assert result["metadata"]["reviewed_by"] == "operator"


def test_memory_conflict_cli_exposes_unresolved_pairs(tmp_path, monkeypatch, capsys):
    database = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(database)
    store.save(MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC,
        content="Rule: deploy the production release immediately",
    ))
    store.save(MemoryRecord.create(
        project_id="p", memory_type=MemoryType.SEMANTIC,
        content="Rule: do not deploy the production release immediately",
        status=MemoryStatus.PENDING,
    ))
    store.close()
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "memory", "conflicts", "--project", "p",
        "--memory-db", str(database),
    ])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result) == 1
    assert result[0]["status"] == "open"


def test_memory_benchmark_cli_runs_without_external_services(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["kaldrax", "memory", "benchmark"])
    monkeypatch.delenv("KALDRAX_EMBEDDING_MODEL", raising=False)
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["retrieval_mode"] == "lexical"
    assert result["query_count"] == 5
