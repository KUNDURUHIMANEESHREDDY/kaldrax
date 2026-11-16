"""Hosted embedding providers for project-memory retrieval."""
from __future__ import annotations

import json
import math
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class EmbeddingError(RuntimeError):
    """An embedding provider failed or returned invalid vectors."""


class EmbeddingProvider(Protocol):
    model_id: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one finite, non-empty vector for every input text."""


class HostedEmbeddingProvider:
    """Call an HTTPS OpenAI-compatible embedding API without a provider SDK."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        opener: Callable[..., object] = urlopen,
    ) -> None:
        if not api_key.strip():
            raise ValueError("embedding api_key must not be empty")
        if not model.strip():
            raise ValueError("embedding model must not be empty")
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("embedding base_url must be an HTTPS URL without credentials, query, or fragment")
        if timeout <= 0:
            raise ValueError("embedding timeout must be greater than zero")
        self._api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.model_id = f"{parsed.netloc}{parsed.path.rstrip('/')}:{self.model}"
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
            "encoding_format": "float",
        }).encode("utf-8")
        request = Request(
            f"{self.base_url}/embeddings",
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
            raise EmbeddingError(f"Embedding provider returned HTTP {exc.code}{suffix}") from None
        except (TimeoutError, URLError, OSError) as exc:
            raise EmbeddingError(f"Embedding provider request failed: {type(exc).__name__}") from None
        except Exception as exc:
            raise EmbeddingError(f"Embedding provider request failed: {type(exc).__name__}") from None

        if len(raw) > _MAX_RESPONSE_BYTES:
            raise EmbeddingError("Embedding provider response exceeded the 4 MiB safety limit")
        try:
            data = json.loads(raw.decode("utf-8"))
            items = data["data"]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            raise EmbeddingError("Embedding provider returned an invalid response") from None
        if not isinstance(items, list) or len(items) != len(texts):
            raise EmbeddingError("Embedding provider must return one vector for each input")

        ordered: list[list[float] | None] = [None] * len(texts)
        for position, item in enumerate(items):
            if not isinstance(item, dict):
                raise EmbeddingError("Embedding provider returned an invalid data item")
            index = item.get("index", position)
            if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(texts):
                raise EmbeddingError("Embedding provider returned an invalid vector index")
            if ordered[index] is not None:
                raise EmbeddingError("Embedding provider returned a duplicate vector index")
            vector = item.get("embedding")
            if not isinstance(vector, list) or not vector:
                raise EmbeddingError("Embedding provider returned an empty or invalid vector")

            values: list[float] = []
            for value in vector:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise EmbeddingError("Embedding values must be numeric")
                number = float(value)
                if not math.isfinite(number):
                    raise EmbeddingError("Embedding values must be finite")
                values.append(number)
            ordered[index] = values

        if any(vector is None for vector in ordered):
            raise EmbeddingError("Embedding provider did not return every vector index")
        vectors = [vector for vector in ordered if vector is not None]
        dimensions = len(vectors[0])
        if any(len(vector) != dimensions for vector in vectors):
            raise EmbeddingError("Embedding dimensions differ within one response")
        return vectors
