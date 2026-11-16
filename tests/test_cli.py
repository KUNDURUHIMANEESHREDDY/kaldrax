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
    assert result["memory_count"] == 40
    assert result["query_count"] == 42
    assert "by_category" in result


def test_memory_extraction_benchmark_cli_uses_budgeted_provider_client(tmp_path, monkeypatch, capsys):
    dataset = tmp_path / "extract.json"
    dataset.write_text(json.dumps({
        "name": "cli-test",
        "cases": [{
            "id": "one",
            "objective": "Capture a durable fact",
            "candidate": "SQLite stores local memory.",
            "expected": [{"match_terms": ["sqlite", "memory"]}],
        }],
    }), encoding="utf-8")

    class FakeClient:
        def complete(self, *, system_prompt, user_prompt):
            return json.dumps({
                "memories": [{
                    "content": "Decision: SQLite stores memory",
                    "summary": "SQLite memory storage",
                    "evidence": "SQLite stores local memory.",
                    "confidence": 0.9,
                    "tags": ["storage"],
                }],
            })

    monkeypatch.setenv("KALDRAX_API_KEY", "test-key")
    monkeypatch.setenv("KALDRAX_MODEL", "extractor-model")
    budgets = []

    def fake_client(model, budget):
        assert model == "extractor-model"
        budgets.append(budget)
        return FakeClient()

    monkeypatch.setattr("kaldrax.cli._client", fake_client)
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "memory", "extraction-benchmark", "--dataset", str(dataset),
    ])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["dataset_name"] == "cli-test"
    assert result["precision"] == 1.0
    assert result["confidence_calibration"]["sample_count"] == 1
    assert result["evidence_valid_rate"] == 1.0
    assert len(budgets) == 1
    assert result["budget"]["provider_calls"] == 1

def test_provider_check_requires_real_credentials(monkeypatch):
    monkeypatch.delenv("KALDRAX_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["kaldrax", "provider-check"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_deterministic_evaluator_benchmark_cli_exposes_negation_false_positives(capsys, monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "benchmark-evaluator", "--mode", "deterministic", "--min-accuracy", "0.80"
    ])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] == 10
    assert payload["accuracy"] == 0.8
    assert payload["false_positive"] == 2
    assert payload["errors"] == 0


def test_team_requires_four_distinct_role_models(monkeypatch):
    monkeypatch.setenv("KALDRAX_API_KEY", "key")
    monkeypatch.setenv("KALDRAX_MODEL", "same")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "same")
    monkeypatch.setenv("KALDRAX_PLANNER_MODEL", "planner")
    monkeypatch.setenv("KALDRAX_REVIEWER_MODEL", "reviewer")
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "team", "--objective", "Build a feature", "--criterion", "output is complete"
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_sandbox_cli_rejects_invalid_limits_before_docker(tmp_path, monkeypatch):
    source = tmp_path / "hello.py"
    source.write_text("print('hello')", encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "kaldrax", "sandbox", "run-python", str(source), "--timeout", "0"
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_provider_check_exercises_both_roles_and_evidence_validation(monkeypatch, capsys):
    from types import SimpleNamespace

    monkeypatch.setenv("KALDRAX_API_KEY", "test-key")
    monkeypatch.setenv("KALDRAX_MODEL", "executor")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "judge")
    clients = {}

    class FakeClient:
        def __init__(self, model):
            self.model = model

        def complete_with_usage(self, *, system_prompt, user_prompt):
            return SimpleNamespace(
                content="KALDRAX_PROVIDER_OK",
                usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, estimated=False),
            )

        def complete(self, *, system_prompt, user_prompt):
            criterion = "The KALDRAX provider health check completed."
            return json.dumps({
                "criteria": [{
                    "criterion": criterion,
                    "passed": True,
                    "evidence": criterion,
                }]
            })

    def fake_client(model, budget):
        clients[model] = budget
        return FakeClient(model)

    monkeypatch.setattr("kaldrax.cli._client", fake_client)
    monkeypatch.setattr("sys.argv", ["kaldrax", "provider-check"])
    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["executor_smoke_passed"] is True
    assert payload["evaluator_schema_and_evidence_passed"] is True
    assert clients["executor"] is clients["judge"]


def test_run_budget_settings_are_shared_in_provider_clients(monkeypatch):
    monkeypatch.setenv("KALDRAX_API_KEY", "key")
    monkeypatch.setenv("KALDRAX_MODEL", "builder")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "judge")
    monkeypatch.setattr("kaldrax.cli._client", lambda model, budget: (model, budget))
    from kaldrax.cli import _budget_from_env, _client
    budget = _budget_from_env()
    assert _client("builder", budget)[1] is budget
    assert _client("judge", budget)[1] is budget
