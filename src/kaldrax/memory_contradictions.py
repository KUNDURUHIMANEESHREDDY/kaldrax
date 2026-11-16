"""Explainable contradiction-candidate detection for engineering memories.

This module detects review candidates, not truth. It combines opposition
vocabularies, subject overlap, optional local embedding similarity, and
environment scoping. A human still resolves every candidate.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")
_NEGATIONS = {"not", "never", "no", "without", "avoid", "deny", "denied"}
_LABELS = {"decision", "pattern", "lesson", "rule", "policy", "note"}

# Each dimension contains two mutually exclusive groups.
_OPPOSITION_DIMENSIONS: dict[str, tuple[set[str], set[str]]] = {
    "availability": ({"enable", "enabled", "allow", "allowed", "permit", "permitted", "available"}, {"disable", "disabled", "deny", "denied", "forbid", "forbidden", "unavailable"}),
    "visibility": ({"public", "exposed", "external"}, {"private", "internal", "hidden"}),
    "location": ({"local", "localhost", "on_premise"}, {"remote", "cloud", "hosted"}),
    "connectivity": ({"online", "connected"}, {"offline", "disconnected"}),
    "execution": ({"sync", "synchronous", "blocking"}, {"async", "asynchronous", "nonblocking"}),
    "mutability": ({"mutable", "writable", "changeable"}, {"immutable", "readonly", "read_only"}),
    "retention": ({"retain", "keep", "preserve", "persist"}, {"delete", "discard", "remove", "expire"}),
    "membership": ({"include", "included", "include_all"}, {"exclude", "excluded", "omit"}),
    "obligation": ({"required", "mandatory", "must"}, {"optional", "recommended", "may"}),
    "operation": ({"accept", "accepted", "pass", "passed", "success"}, {"reject", "rejected", "fail", "failed", "failure"}),
    "automation": ({"automatic", "automatically", "auto"}, {"manual", "manually"}),
    "transport_security": ({"encrypted", "encrypt", "tls", "https"}, {"plaintext", "unencrypted", "cleartext", "http"}),
    "strictness": ({"strict", "deny_by_default", "fail_closed"}, {"permissive", "allow_by_default", "fail_open"}),
}

_ENVIRONMENTS = {
    "production", "prod", "staging", "stage", "development", "dev",
    "testing", "test", "qa", "preview",
}


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.casefold()))


def _subject(text: str, cue_tokens: set[str]) -> set[str]:
    return _tokens(text) - _NEGATIONS - _LABELS - cue_tokens


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _cosine(left: Iterable[float], right: Iterable[float]) -> float | None:
    a, b = list(left), list(right)
    if not a or len(a) != len(b):
        return None
    if not all(math.isfinite(value) for value in (*a, *b)):
        return None
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return None
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _opposition(left: set[str], right: set[str]) -> list[str]:
    findings: list[str] = []
    for dimension, (first, second) in _OPPOSITION_DIMENSIONS.items():
        left_first, left_second = bool(left & first), bool(left & second)
        right_first, right_second = bool(right & first), bool(right & second)
        if (left_first and right_second) or (left_second and right_first):
            findings.append(dimension)
    if bool(left & _NEGATIONS) != bool(right & _NEGATIONS):
        findings.append("negation")
    return findings


def find_contradiction_candidates(
    records: list[Any], *, embedder: Any | None = None,
) -> list[tuple[Any, Any, str]]:
    """Return candidate record pairs and explainable similarity diagnostics.

    Records need only expose id, content, and agent_id. Embeddings are computed
    in one batch; a provider failure degrades to lexical subject similarity.
    """
    token_sets = [_tokens(record.content) for record in records]
    cue_tokens = set().union(_NEGATIONS, _LABELS, *(
        first | second for first, second in _OPPOSITION_DIMENSIONS.values()
    ))
    subjects = [_subject(record.content, cue_tokens) for record in records]

    vectors: list[list[float]] | None = None
    if embedder is not None and records:
        try:
            response = embedder.embed([record.content for record in records])
            if len(response) == len(records):
                candidate_vectors = [[float(value) for value in vector] for vector in response]
                if candidate_vectors and all(
                    vector and all(math.isfinite(value) for value in vector)
                    for vector in candidate_vectors
                ):
                    vectors = candidate_vectors
        except Exception:
            vectors = None

    candidates: list[tuple[Any, Any, str]] = []
    for left_index, left in enumerate(records):
        for right_index in range(left_index + 1, len(records)):
            right = records[right_index]
            if left.agent_id is not None and right.agent_id is not None and left.agent_id != right.agent_id:
                continue

            oppositions = _opposition(token_sets[left_index], token_sets[right_index])
            if not oppositions:
                continue

            left_env = subjects[left_index] & _ENVIRONMENTS
            right_env = subjects[right_index] & _ENVIRONMENTS
            if left_env and right_env and left_env.isdisjoint(right_env):
                continue

            lexical = _jaccard(subjects[left_index], subjects[right_index])
            semantic = None
            if vectors is not None:
                semantic = _cosine(vectors[left_index], vectors[right_index])
            if lexical < 0.42 and (semantic is None or semantic < 0.84):
                continue

            evidence = ", ".join(sorted(set(oppositions)))
            semantic_text = "unavailable" if semantic is None else f"{semantic:.2f}"
            reason = (
                f"Possible contradiction dimensions: {evidence}; "
                f"subject Jaccard={lexical:.2f}; semantic similarity={semantic_text}. "
                "Heuristic candidate only; inspect scope and evidence before resolving."
            )
            candidates.append((left, right, reason))
    return candidates
