from __future__ import annotations

import json

import pytest

from kaldrax.live_validation import MeasuredChatClient, run_live_validation


def test_measured_client_records_latency_usage_and_failure():
    class Usage:
        prompt_tokens = 7
        completion_tokens = 3
        estimated = False

    class Result:
        content = "provider response"
        usage = Usage()

    class Client:
        def complete_with_usage(self, **kwargs):
            return Result()

    measured = MeasuredChatClient("builder", "test-model", Client())
    assert measured.complete(system_prompt="s", user_prompt="u") == "provider response"
    assert measured.calls[0]["role"] == "builder"
    assert measured.calls[0]["status"] == "passed"
    assert measured.calls[0]["prompt_tokens"] == 7
    assert measured.calls[0]["completion_tokens"] == 3
    assert measured.calls[0]["latency_ms"] >= 0

    class BrokenClient:
        def complete(self, **kwargs):
            raise TimeoutError("private provider detail")

    broken = MeasuredChatClient("reviewer", "test-model", BrokenClient())
    with pytest.raises(TimeoutError):
        broken.complete(system_prompt="s", user_prompt="u")
    assert broken.calls[0]["status"] == "failed"
    assert broken.calls[0]["error_type"] == "TimeoutError"
    assert "private provider detail" not in json.dumps(broken.calls)


def test_live_validation_fails_closed_without_credentials(tmp_path, monkeypatch):
    for key in (
        "KALDRAX_API_KEY", "KALDRAX_PLANNER_MODEL", "KALDRAX_MODEL",
        "KALDRAX_REVIEWER_MODEL", "KALDRAX_EVALUATOR_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)

    code, report = run_live_validation(artifacts=tmp_path)

    assert code == 2
    assert report["status"] == "blocked"
    assert report["checks"]["provider_configuration"]["status"] == "blocked"
    assert report["checks"]["memory_retrieval"]["status"] == "passed"
    assert set(report["checks"]["provider_configuration"]["missing"]) == {
        "KALDRAX_API_KEY", "KALDRAX_PLANNER_MODEL", "KALDRAX_MODEL",
        "KALDRAX_REVIEWER_MODEL", "KALDRAX_EVALUATOR_MODEL",
    }
    artifact = tmp_path / report["artifact"].split("\\")[-1]
    assert artifact.exists()
    saved = json.loads(artifact.read_text(encoding="utf-8"))
    assert saved["status"] == "blocked"
    assert "replace-me" not in json.dumps(saved)


def test_live_validation_rejects_duplicate_role_models(tmp_path, monkeypatch):
    monkeypatch.setenv("KALDRAX_API_KEY", "not-written-to-report")
    for key in (
        "KALDRAX_PLANNER_MODEL", "KALDRAX_MODEL",
        "KALDRAX_REVIEWER_MODEL", "KALDRAX_EVALUATOR_MODEL",
    ):
        monkeypatch.setenv(key, "same-model")

    code, report = run_live_validation(artifacts=tmp_path)

    assert code == 1
    assert report["status"] == "failed"
    assert report["checks"]["provider_configuration"]["status"] == "failed"
    serialized = json.dumps(report)
    assert "not-written-to-report" not in serialized


@pytest.mark.skipif(
    __import__("os").getenv("KALDRAX_RUN_DOCKER_INTEGRATION") != "1",
    reason="set KALDRAX_RUN_DOCKER_INTEGRATION=1 to run the full Docker-backed validation harness",
)
def test_live_validation_runs_full_team_workflow_with_fake_provider_and_docker(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    import shutil

    if not shutil.which("docker"):
        pytest.skip("Docker CLI is unavailable")

    monkeypatch.setenv("KALDRAX_API_KEY", "test-only-secret")
    monkeypatch.setenv("KALDRAX_PLANNER_MODEL", "planner-test")
    monkeypatch.setenv("KALDRAX_MODEL", "builder-test")
    monkeypatch.setenv("KALDRAX_REVIEWER_MODEL", "reviewer-test")
    monkeypatch.setenv("KALDRAX_EVALUATOR_MODEL", "evaluator-test")

    patch = (
        "diff --git a/src/operations.py b/src/operations.py\n"
        "--- a/src/operations.py\n"
        "+++ b/src/operations.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def subtract(left: int, right: int) -> int:\n"
        "-    raise NotImplementedError\n"
        "+    return left - right\n"
    )

    class FakeProvider:
        def __init__(self, *, model, **kwargs):
            self.model = model

        def complete_with_usage(self, *, system_prompt, user_prompt):
            if "repository planning agent" in system_prompt:
                content = "Inspect operations.py, implement subtraction, and run its tests."
            elif "repository implementation agent" in system_prompt:
                content = json.dumps({"summary": "Implemented subtraction.", "patch": patch})
            elif "independent repository reviewer" in system_prompt:
                content = json.dumps({"approved": True, "findings": [], "summary": "Patch is correct."})
            elif "independent acceptance evaluator" in system_prompt:
                criteria = [
                    "The patch implements subtraction as left minus right.",
                    "The Docker verification output reports Ran 2 tests.",
                ]
                content = json.dumps({"criteria": [
                    {"criterion": criteria[0], "passed": True, "evidence": "+    return left - right"},
                    {"criterion": criteria[1], "passed": True, "evidence": "Ran 2 tests"},
                ]})
            else:
                raise AssertionError("unexpected provider role")
            return SimpleNamespace(
                content=content,
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=8, estimated=False),
            )

    monkeypatch.setattr("kaldrax.live_validation.OpenAICompatibleClient", FakeProvider)
    code, report = run_live_validation(artifacts=tmp_path, timeout_seconds=30)

    assert code == 0
    assert report["status"] == "passed"
    assert report["checks"]["docker"]["status"] == "passed"
    assert report["checks"]["memory_retrieval"]["status"] == "passed"
    assert report["checks"]["repository_team"]["status"] == "passed"
    assert report["checks"]["repository_team"]["applied_to_disposable_git_fixture"] is True
    assert {call["role"] for call in report["provider_calls"]} == {
        "planner", "builder", "reviewer", "evaluator",
    }
    assert all(call["status"] == "passed" for call in report["provider_calls"])
    assert report["token_usage"]["prompt_tokens"] > 0
    assert report["token_usage"]["completion_tokens"] > 0
    assert "test-only-secret" not in json.dumps(report)
    assert __import__("pathlib").Path(report["artifact"]).exists()
