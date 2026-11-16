"""Local embedding providers for project-memory retrieval."""
from __future__ import annotations

import ipaddress
import json
import math
from typing import Callable, Protocol
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class EmbeddingError(RuntimeError):
    """An embedding provider failed or returned invalid vectors."""


class EmbeddingProvider(Protocol):
    model_id: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one finite, non-empty vector for every input text."""


class OllamaEmbeddingProvider:
    """Use a locally hosted Ollama embedding model through POST /api/embed.

    The endpoint is intentionally restricted to loopback addresses. KALDRAX
    v1 is local-first; this adapter must not silently send project memory to
    a remote embedding service.
    """

    def __init__(
        self,
        model: str = "embeddinggemma",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 30.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        if not model.strip():
            raise ValueError("embedding model must not be empty")
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Ollama base_url must be an HTTP(S) URL")
        host = parsed.hostname.casefold()
        is_loopback = host == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError:
                is_loopback = False
        if not is_loopback:
            raise ValueError("Ollama embedding endpoint must use localhost or a loopback IP")
        if timeout <= 0:
            raise ValueError("embedding timeout must be greater than zero")
        self.model = model
        self.model_id = f"ollama:{model}"
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("embedding inputs must be non-empty strings")
        payload = json.dumps({
            "model": self.model,
            "input": texts,
            "truncate": True,
        }).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout) as response:  # type: ignore[attr-defined]
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except (TimeoutError, URLError, OSError) as exc:
            raise EmbeddingError(f"Ollama embedding request failed: {type(exc).__name__}") from None
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise EmbeddingError("Ollama embedding response exceeded the 4 MiB safety limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
            vectors = payload["embeddings"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            raise EmbeddingError("Ollama returned an invalid embedding response") from None
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingError("Ollama must return one embedding for each input")
        validated: list[list[float]] = []
        dimensions: int | None = None
        for vector in vectors:
            if not isinstance(vector, list) or not vector:
                raise EmbeddingError("Ollama returned an empty or invalid vector")
            values: list[float] = []
            for value in vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise EmbeddingError("Embedding values must be numeric")
                number = float(value)
                if not math.isfinite(number):
                    raise EmbeddingError("Embedding values must be finite")
                values.append(number)
            if dimensions is None:
                dimensions = len(values)
            elif len(values) != dimensions:
                raise EmbeddingError("Embedding dimensions differ within one response")
            validated.append(values)
        return validated
