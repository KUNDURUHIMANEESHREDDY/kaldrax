"""Small OpenAI-compatible chat-completions client using the standard library."""
from __future__ import annotations

import json
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class ChatClient(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return one text completion for the supplied messages."""


class LLMProviderError(RuntimeError):
    """A provider request failed or returned an unusable response."""


class OpenAICompatibleClient:
    """Minimal chat-completions adapter; no provider SDK is required."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        max_tokens: int = 2048,
        token_parameter: str = "max_completion_tokens",
        opener: Callable[..., object] = urlopen,
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        if not model.strip():
            raise ValueError("model must not be empty")
        if not base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must be an HTTP(S) URL")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        if token_parameter not in {"max_completion_tokens", "max_tokens"}:
            raise ValueError("token_parameter must be max_completion_tokens or max_tokens")
        self._api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.token_parameter = token_parameter
        self._opener = opener

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                self.token_parameter: self.max_tokens,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.timeout) as response:  # type: ignore[attr-defined]
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            detail = detail.replace(self._api_key, "[REDACTED]").strip()
            if len(detail) > 500:
                detail = detail[:500] + "…"
            suffix = f": {detail}" if detail else ""
            raise LLMProviderError(f"Provider returned HTTP {exc.code}{suffix}") from None
        except (TimeoutError, URLError, OSError) as exc:
            raise LLMProviderError(f"Provider request failed: {type(exc).__name__}") from None

        if len(raw) > _MAX_RESPONSE_BYTES:
            raise LLMProviderError("Provider response exceeded the 4 MiB safety limit")
        try:
            data = json.loads(raw.decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            raise LLMProviderError("Provider returned an invalid chat-completions response") from None
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("Provider returned an empty or non-text completion")
        return content.strip()
