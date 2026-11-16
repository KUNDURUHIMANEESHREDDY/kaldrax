import json
import pytest
from kaldrax.cli import main
from kaldrax.memory import MemoryRecord, MemoryType, SQLiteMemoryStore


def test_run_requires_executor_and_evaluator_models(monkeypatch):
    monkeypatch.setattr("sys.argv", ["kaldrax", "run", "--objective", "Build feature", "--criterion", "tests pass"])
    monkeypatch.setenv("KALDRAX_API_KEY", "secret")
    monkeypatch.setenv("KALDRAX_MODEL", "executor-model")
    monkeypatch.delenv("KALDRAX_EVALUATOR_MODEL", raising=False)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_run_requires_separate_evaluator_model(monkeypatch):
    monkeypatch.setattr("sys.argv", ["kaldrax", "run", "--objective", "Build feature", "--criterion", "tests pass"])
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


def test_memory_search_and_consolidate_commands(tmp_path, monkeypatch, capsys):
    database = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(database)
    for index in range(2):
        store.save(MemoryRecord.create(
            project_id="p", memory_type=MemoryType.SEMANTIC,
            content="Lesson: use deterministic memory retrieval", source_run_id=f"run-{index}",
        ))
    store.close()

    monkeypatch.setattr("sys.argv", [
        "kaldrax", "memory", "search", "--query", "deterministic retrieval",
        "--project", "p", "--memory-db", str(database),
    ])
    assert main() == 0
    assert len(json.loads(capsys.readouterr().out)) == 2

    monkeypatch.setattr("sys.argv", [
        "kaldrax", "memory", "consolidate", "--project", "p", "--memory-db", str(database),
    ])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["duplicates_removed"] == 1
    assert result["remaining"] == 1
