import io
import json
from urllib.error import HTTPError

import pytest

from kaldrax.execution import LLMExecutor
from kaldrax.llm import LLMProviderError, OpenAICompatibleClient
from kaldrax.models import Task


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


def test_openai_compatible_client_sends_auth_model_and_messages():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["timeout"] = timeout
        seen["payload"] = json.loads(request.data)
        return FakeResponse(json.dumps({"choices": [{"message": {"content": "candidate"}}]}).encode())

    client = OpenAICompatibleClient(
        api_key="secret", model="executor-model", base_url="https://example.test/v1",
        timeout=12, max_tokens=500, opener=opener,
    )
    assert client.complete(system_prompt="system", user_prompt="user") == "candidate"
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["authorization"] == "Bearer secret"
    assert seen["timeout"] == 12
    assert seen["payload"]["model"] == "executor-model"
    assert seen["payload"]["max_completion_tokens"] == 500
    assert seen["payload"]["messages"][1]["content"] == "user"


def test_openai_compatible_client_supports_keyless_loopback_ollama():
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["payload"] = json.loads(request.data)
        return FakeResponse(json.dumps({
            "choices": [{"message": {"content": "local candidate"}}]
        }).encode())

    client = OpenAICompatibleClient(
        api_key="", model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1", token_parameter="max_tokens",
        opener=opener,
    )
    assert client.complete(system_prompt="system", user_prompt="user") == "local candidate"
    assert seen["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert seen["authorization"] is None
    assert seen["payload"]["max_tokens"] == 2048


def test_openai_compatible_client_allows_only_loopback_http():
    for url in (
        "http://example.test/v1",
        "http://192.168.1.20:11434/v1",
        "http://127.0.0.1:bad/v1",
    ):
        with pytest.raises(ValueError):
            OpenAICompatibleClient(api_key="secret", model="model", base_url=url)

    for url in (
        "http://localhost:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://[::1]:11434/v1",
    ):
        client = OpenAICompatibleClient(
            api_key="", model="local-model", base_url=url,
            opener=lambda *_args, **_kwargs: FakeResponse(
                b'{"choices":[{"message":{"content":"ok"}}]}'
            ),
        )
        assert client.complete(system_prompt="s", user_prompt="u") == "ok"


def test_openai_compatible_client_requires_key_for_https():
    with pytest.raises(ValueError, match="api_key"):
        OpenAICompatibleClient(api_key="", model="model")


def test_openai_compatible_client_rejects_invalid_response():
    client = OpenAICompatibleClient(
        api_key="secret", model="model", opener=lambda *_args, **_kwargs: FakeResponse(b"{}")
    )
    with pytest.raises(LLMProviderError, match="invalid chat-completions"):
        client.complete(system_prompt="s", user_prompt="u")


def test_client_validates_configuration():
    with pytest.raises(ValueError):
        OpenAICompatibleClient(api_key="", model="model")
    with pytest.raises(ValueError):
        OpenAICompatibleClient(api_key="key", model="model", timeout=0)
    for base_url in (
        "http://api.example/v1",
        "https://user:password@api.example/v1",
        "https://api.example/v1?token=secret",
        "https://api.example/v1#fragment",
    ):
        with pytest.raises(ValueError, match="HTTPS"):
            OpenAICompatibleClient(api_key="key", model="model", base_url=base_url)


class FakeChatClient:
    def __init__(self, output):
        self.output = output
        self.prompts = None

    def complete(self, *, system_prompt, user_prompt):
        self.prompts = (system_prompt, user_prompt)
        return self.output


def test_llm_executor_passes_task_and_retry_feedback_as_json():
    client = FakeChatClient("implementation candidate")
    executor = LLMExecutor(client)
    task = Task("Implement feature", ("unit tests", "documentation"), max_iterations=4)
    result = executor.execute(task, ("documentation",), 2)
    assert result == "implementation candidate"
    prompt = json.loads(client.prompts[1])
    assert prompt["objective"] == "Implement feature"
    assert prompt["acceptance_criteria"] == ["unit tests", "documentation"]
    assert prompt["previous_evaluation_feedback"] == ["documentation"]
    assert prompt["iteration"] == 2


def test_provider_error_redacts_api_key():
    def opener(*_args, **_kwargs):
        raise HTTPError(
            "https://provider.test", 401, "unauthorized", {},
            io.BytesIO(b"credential secret was rejected"),
        )

    client = OpenAICompatibleClient(api_key="secret", model="model", opener=opener)
    with pytest.raises(LLMProviderError) as exc:
        client.complete(system_prompt="s", user_prompt="u")
    assert "401" in str(exc.value)
    assert "secret" not in str(exc.value)
    assert "[REDACTED]" in str(exc.value)


def test_client_rejects_oversized_response():
    client = OpenAICompatibleClient(
        api_key="secret", model="model",
        opener=lambda *_args, **_kwargs: FakeResponse(b"x" * (4 * 1024 * 1024 + 1)),
    )
    with pytest.raises(LLMProviderError, match="4 MiB"):
        client.complete(system_prompt="s", user_prompt="u")


def test_client_rejects_empty_completion():
    body = json.dumps({"choices": [{"message": {"content": " "}}]}).encode()
    client = OpenAICompatibleClient(
        api_key="secret", model="model",
        opener=lambda *_args, **_kwargs: FakeResponse(body),
    )
    with pytest.raises(LLMProviderError, match="empty"):
        client.complete(system_prompt="s", user_prompt="u")


def test_client_supports_legacy_token_parameter_for_compatible_endpoints():
    seen = {}

    def opener(request, timeout):
        seen.update(json.loads(request.data))
        return FakeResponse(json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())

    client = OpenAICompatibleClient(
        api_key="secret", model="model", token_parameter="max_tokens", opener=opener
    )
    assert client.complete(system_prompt="s", user_prompt="u") == "ok"
    assert seen["max_tokens"] == 2048
    assert "max_completion_tokens" not in seen


def test_client_shares_a_run_budget_and_uses_remaining_completion_ceiling():
    from kaldrax.budgets import BudgetExceeded, RunBudget

    calls = []
    def opener(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload)
        response = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }
        return FakeResponse(json.dumps(response).encode())

    budget = RunBudget(
        max_calls=1, max_input_tokens=1000, max_output_tokens=5, max_total_tokens=1005,
    )
    client = OpenAICompatibleClient(
        api_key="secret", model="model", max_tokens=20, opener=opener, budget=budget,
    )
    result = client.complete_with_usage(system_prompt="s", user_prompt="u")
    assert result.content == "ok"
    assert result.usage.prompt_tokens == 3
    assert result.usage.completion_tokens == 2
    assert calls[0]["max_completion_tokens"] == 5
    assert budget.snapshot().total_tokens == 5
    with pytest.raises(BudgetExceeded):
        client.complete(system_prompt="s", user_prompt="u")
    assert len(calls) == 1


def test_client_reports_estimated_usage_when_provider_omits_usage():
    from kaldrax.budgets import RunBudget

    body = json.dumps({"choices": [{"message": {"content": "answer"}}]}).encode()
    budget = RunBudget(
        max_calls=2, max_input_tokens=1000, max_output_tokens=100, max_total_tokens=1100,
    )
    client = OpenAICompatibleClient(
        api_key="key", model="model",
        opener=lambda *_args, **_kwargs: FakeResponse(body),
        budget=budget,
    )
    result = client.complete_with_usage(system_prompt="system", user_prompt="user")
    assert result.usage.estimated
    assert budget.snapshot().calls == 1
    assert budget.snapshot().total_tokens >= len("systemuser")


def test_provider_request_timeout_is_capped_by_remaining_run_deadline(monkeypatch):
    import json
    import kaldrax.budgets as budgets_module
    from kaldrax.budgets import RunBudget

    now = [100.0]
    monkeypatch.setattr(budgets_module.time, "monotonic", lambda: now[0])
    budget = RunBudget(max_duration_seconds=5.0)
    now[0] = 104.0
    observed = {}

    def opener(request, timeout):
        observed["timeout"] = timeout
        return FakeResponse(json.dumps({
            "choices": [{"message": {"content": "bounded"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        }).encode())

    client = OpenAICompatibleClient(
        api_key="secret",
        model="model",
        timeout=30,
        budget=budget,
        opener=opener,
    )
    assert client.complete(system_prompt="s", user_prompt="u") == "bounded"
    assert observed["timeout"] == 1.0
