import pytest

from kaldrax.cli import main


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
