"""Project-scoped persistent memory with hybrid retrieval and review controls."""
from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Protocol
from uuid import uuid4

from .embeddings import EmbeddingProvider


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    CONTESTED = "contested"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    project_id: str
    memory_type: MemoryType
    content: str
    summary: str
    source_run_id: str | None
    source_event_sequences: tuple[int, ...] = ()
    agent_id: str | None = None
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    confidence: float = 0.7
    status: MemoryStatus = MemoryStatus.ACTIVE
    verified_at: str | None = None
    expires_at: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("memory id must not be empty")
        if not self.project_id.strip():
            raise ValueError("project_id must not be empty")
        if not self.content.strip():
            raise ValueError("memory content must not be empty")
        if any(sequence < 1 for sequence in self.source_event_sequences):
            raise ValueError("source event sequences must be positive")
        if self.agent_id is not None and not self.agent_id.strip():
            raise ValueError("agent_id must not be empty when provided")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("memory confidence must be between 0 and 1")

    @classmethod
    def create(
        cls, *, project_id: str, memory_type: MemoryType, content: str,
        summary: str = "", source_run_id: str | None = None,
        source_event_sequences: Iterable[int] = (), agent_id: str | None = None,
        tags: Iterable[str] = (), metadata: dict[str, Any] | None = None,
        confidence: float = 0.7, status: MemoryStatus = MemoryStatus.ACTIVE,
        verified_at: str | None = None, expires_at: str | None = None,
    ) -> "MemoryRecord":
        return cls(
            id=str(uuid4()), project_id=project_id, memory_type=memory_type,
            content=content, summary=summary, source_run_id=source_run_id,
            source_event_sequences=tuple(source_event_sequences), agent_id=agent_id,
            tags=tuple(tags), metadata=dict(metadata or {}), confidence=confidence,
            status=status, verified_at=verified_at, expires_at=expires_at,
        )


@dataclass(frozen=True)
class MemoryMatch:
    record: MemoryRecord
    score: float
    lexical_score: float = 0.0
    semantic_score: float | None = None
    freshness_score: float = 1.0
    retrieval_method: str = "lexical"


@dataclass(frozen=True)
class MemoryConflict:
    id: str
    project_id: str
    left_memory_id: str
    right_memory_id: str
    reason: str
    status: str
    created_at: str
    resolution: str | None = None


class MemoryReviewConflict(RuntimeError):
    """A proposed approval conflicts with existing project knowledge."""

    def __init__(self, conflict_ids: list[str]) -> None:
        self.conflict_ids = conflict_ids
        super().__init__(
            "memory cannot be approved until its open contradiction is resolved: "
            + ", ".join(conflict_ids)
        )


@dataclass
class WorkingMemory:
    """Ephemeral context scoped to one run; never persisted as project knowledge."""
    run_id: str
    project_id: str
    retrieved_memories: tuple[MemoryMatch, ...] = ()
    feedback: tuple[str, ...] = ()
    iteration: int = 0
    previous_candidate: str = ""
    current_candidate: str = ""


class MemoryStore(Protocol):
    def save(self, record: MemoryRecord) -> None: ...
    def search(
        self, query: str, *, project_id: str, limit: int = 5,
        memory_types: tuple[MemoryType, ...] = (MemoryType.EPISODIC, MemoryType.SEMANTIC),
        agent_id: str | None = None,
    ) -> list[MemoryMatch]: ...
    def consolidate(self, project_id: str | None = None) -> int: ...


_TOKEN_RE = re.compile(r"[a-z0-9_]{2,}")
_STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "but", "for", "from",
    "into", "its", "our", "that", "the", "their", "then", "there", "these",
    "this", "those", "through", "with", "will", "would", "your", "do", "does",
    "did", "must", "should", "can", "could",
}
_NEGATIONS = {"not", "never", "no", "without", "avoid", "disable", "disabled", "deny", "denied", "disallow", "forbid"}
_LABELS = {"decision", "pattern", "lesson", "rule", "policy", "note"}


def _tokens(value: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(value.casefold()) if token not in _STOP_WORDS]


def _normalize_content(value: str) -> str:
    return " ".join(_tokens(value))


def _memory_text(record: MemoryRecord) -> str:
    return " ".join((record.content, record.summary, *record.tags))


def _cosine(left: list[float], right: list[float]) -> float | None:
    if not left or len(left) != len(right):
        return None
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return None
    return dot / (left_norm * right_norm)


def _json_vector(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    try:
        values = json.loads(raw)
        if not isinstance(values, list) or not values:
            return None
        vector = [float(value) for value in values]
        return vector if all(math.isfinite(value) for value in vector) else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


class SQLiteMemoryStore:
    """SQLite-backed local memory with project and optional agent isolation.

    By default episodic records expire after 365 days and semantic records
    after 180 days. Approval refreshes the verification timestamp and expiry.
    A configured embedding provider enables hybrid retrieval; lexical search
    remains available when Ollama is absent or has not indexed older records.
    """

    DEFAULT_TTL_DAYS = {MemoryType.EPISODIC: 365, MemoryType.SEMANTIC: 180}

    def __init__(
        self,
        path: str | Path,
        embedder: EmbeddingProvider | None = None,
        ttl_days: dict[MemoryType, int | None] | None = None,
    ) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        self.ttl_days = dict(self.DEFAULT_TTL_DAYS)
        if ttl_days:
            self.ttl_days.update(ttl_days)
        if any(value is not None and value < 1 for value in self.ttl_days.values()):
            raise ValueError("memory TTL values must be positive or None")
        self.last_embedding_error: str | None = None
        self._connection = sqlite3.connect(str(path), timeout=10)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 10000")
        if str(path) != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                memory_type TEXT NOT NULL CHECK(memory_type IN ('episodic', 'semantic')),
                content TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_run_id TEXT,
                source_event_sequences TEXT NOT NULL,
                agent_id TEXT,
                tags TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        self._migrate_memory_columns()
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS memory_conflicts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                left_memory_id TEXT NOT NULL,
                right_memory_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                resolution TEXT,
                UNIQUE(left_memory_id, right_memory_id)
            )"""
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_project_type ON memories(project_id, memory_type)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_project_agent ON memories(project_id, agent_id)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_project_status ON memories(project_id, status)"
        )
        self._connection.commit()

    def _migrate_memory_columns(self) -> None:
        existing = {
            row["name"] for row in self._connection.execute("PRAGMA table_info(memories)").fetchall()
        }
        migrations = {
            "confidence": "REAL NOT NULL DEFAULT 0.7",
            "status": "TEXT NOT NULL DEFAULT 'active'",
            "verified_at": "TEXT",
            "expires_at": "TEXT",
            "embedding_json": "TEXT",
            "embedding_model": "TEXT",
            "updated_at": "TEXT",
        }
        for name, declaration in migrations.items():
            if name not in existing:
                self._connection.execute(f"ALTER TABLE memories ADD COLUMN {name} {declaration}")

    def _embedding_for(self, text: str) -> tuple[str, list[float]] | None:
        if self.embedder is None:
            return None
        try:
            vectors = self.embedder.embed([text])
            if len(vectors) != 1 or not vectors[0]:
                raise ValueError("embedding provider returned an invalid vector")
            vector = [float(value) for value in vectors[0]]
            if not all(math.isfinite(value) for value in vector):
                raise ValueError("embedding provider returned a non-finite vector")
            self.last_embedding_error = None
            return self.embedder.model_id, vector
        except Exception as exc:
            self.last_embedding_error = type(exc).__name__
            return None

    def save(self, record: MemoryRecord) -> None:
        now = datetime.now(timezone.utc)
        expires_at = record.expires_at
        if expires_at is None:
            ttl = self.ttl_days.get(record.memory_type)
            if ttl is not None:
                expires_at = (now + timedelta(days=ttl)).isoformat()
        embedding = self._embedding_for(_memory_text(record))
        model_id, vector = embedding if embedding else (None, None)
        with self._connection:
            self._connection.execute(
                """INSERT INTO memories (
                    id, project_id, memory_type, content, summary, source_run_id,
                    source_event_sequences, agent_id, tags, metadata, created_at,
                    confidence, status, verified_at, expires_at, embedding_json,
                    embedding_model, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content=excluded.content, summary=excluded.summary,
                    metadata=excluded.metadata, tags=excluded.tags,
                    confidence=excluded.confidence, status=excluded.status,
                    verified_at=excluded.verified_at, expires_at=excluded.expires_at,
                    embedding_json=COALESCE(excluded.embedding_json, memories.embedding_json),
                    embedding_model=COALESCE(excluded.embedding_model, memories.embedding_model),
                    updated_at=excluded.updated_at""",
                (
                    record.id, record.project_id, record.memory_type.value,
                    record.content, record.summary, record.source_run_id,
                    json.dumps(record.source_event_sequences), record.agent_id,
                    json.dumps(record.tags), json.dumps(record.metadata, sort_keys=True),
                    record.created_at, record.confidence, record.status.value,
                    record.verified_at, expires_at,
                    json.dumps(vector) if vector else None, model_id, now.isoformat(),
                ),
            )

    def get(self, memory_id: str) -> MemoryRecord | None:
        row = self._connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_records(
        self, *, project_id: str, statuses: tuple[MemoryStatus, ...] | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        sql = "SELECT * FROM memories WHERE project_id = ?"
        params: list[Any] = [project_id]
        if statuses:
            sql += " AND status IN (" + ",".join("?" for _ in statuses) + ")"
            params.extend(status.value for status in statuses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [self._from_row(row) for row in self._connection.execute(sql, params).fetchall()]

    def search(
        self, query: str, *, project_id: str, limit: int = 5,
        memory_types: tuple[MemoryType, ...] = (MemoryType.EPISODIC, MemoryType.SEMANTIC),
        agent_id: str | None = None, include_pending: bool = False,
        min_confidence: float = 0.0, semantic_weight: float = 0.65,
        freshness_half_life_days: float = 180.0,
    ) -> list[MemoryMatch]:
        if not project_id.strip():
            raise ValueError("project_id must not be empty")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1")
        if not 0.0 <= semantic_weight <= 1.0:
            raise ValueError("semantic_weight must be between 0 and 1")
        if freshness_half_life_days <= 0:
            raise ValueError("freshness_half_life_days must be positive")
        query_terms = set(_tokens(query))
        if not query_terms or not memory_types:
            return []
        placeholders = ",".join("?" for _ in memory_types)
        statuses = [MemoryStatus.ACTIVE.value]
        if include_pending:
            statuses.append(MemoryStatus.PENDING.value)
        status_placeholders = ",".join("?" for _ in statuses)
        sql = (
            f"SELECT * FROM memories WHERE project_id = ? AND memory_type IN ({placeholders}) "
            f"AND status IN ({status_placeholders})"
        )
        params: list[Any] = [project_id, *(kind.value for kind in memory_types), *statuses]
        if agent_id is not None:
            sql += " AND (agent_id IS NULL OR agent_id = ?)"
            params.append(agent_id)
        rows = self._connection.execute(sql, params).fetchall()

        query_vector: list[float] | None = None
        if self.embedder is not None:
            try:
                vectors = self.embedder.embed([query])
                if len(vectors) == 1:
                    query_vector = [float(value) for value in vectors[0]]
                    if not all(math.isfinite(value) for value in query_vector):
                        query_vector = None
                self.last_embedding_error = None
            except Exception as exc:
                self.last_embedding_error = type(exc).__name__

        now = datetime.now(timezone.utc)
        matches: list[MemoryMatch] = []
        for row in rows:
            record = self._from_row(row)
            if record.confidence < min_confidence:
                continue
            expiry = _parse_datetime(record.expires_at)
            if expiry is not None and expiry <= now:
                continue
            terms = _tokens(_memory_text(record))
            term_set = set(terms)
            lexical_score = len(query_terms.intersection(term_set)) / max(len(query_terms), 1)
            semantic_score: float | None = None
            if query_vector is not None and row["embedding_model"] == self.embedder.model_id:
                stored_vector = _json_vector(row["embedding_json"])
                if stored_vector is not None:
                    cosine = _cosine(query_vector, stored_vector)
                    if cosine is not None:
                        semantic_score = max(0.0, min(1.0, cosine))
            if semantic_score is not None:
                score = semantic_weight * semantic_score + (1.0 - semantic_weight) * lexical_score
                method = "hybrid" if lexical_score > 0 else "semantic"
            else:
                score = lexical_score
                method = "lexical"
            if lexical_score == 0 and (semantic_score is None or semantic_score < 0.25):
                continue
            reference = _parse_datetime(record.verified_at) or _parse_datetime(record.created_at) or now
            age_days = max(0.0, (now - reference).total_seconds() / 86400.0)
            freshness = math.exp(-math.log(2) * age_days / freshness_half_life_days)
            freshness_factor = 0.55 + (0.45 * freshness)
            confidence_factor = 0.5 + (0.5 * record.confidence)
            score *= freshness_factor * confidence_factor
            matches.append(MemoryMatch(
                record=record, score=score, lexical_score=lexical_score,
                semantic_score=semantic_score, freshness_score=freshness_factor,
                retrieval_method=method,
            ))
        matches.sort(key=lambda item: (item.score, item.record.created_at), reverse=True)
        return matches[:limit]

    def review(self, memory_id: str, decision: str, reviewer: str) -> MemoryRecord:
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        if not reviewer.strip():
            raise ValueError("reviewer must not be empty")
        record = self.get(memory_id)
        if record is None:
            raise KeyError(f"memory not found: {memory_id}")
        if record.status is not MemoryStatus.PENDING:
            raise ValueError("only pending memory records can be reviewed")
        if decision == "approve":
            conflicts = self.detect_conflicts(record.project_id)
            related = [
                conflict.id for conflict in conflicts
                if conflict.status == "open"
                and memory_id in {conflict.left_memory_id, conflict.right_memory_id}
            ]
            if related:
                raise MemoryReviewConflict(related)
        now = datetime.now(timezone.utc)
        status = MemoryStatus.ACTIVE if decision == "approve" else MemoryStatus.REJECTED
        confidence = max(record.confidence, 0.9) if decision == "approve" else min(record.confidence, 0.1)
        metadata = dict(record.metadata)
        metadata.update({"reviewed_by": reviewer, "review_decision": decision, "reviewed_at": now.isoformat()})
        ttl = self.ttl_days.get(record.memory_type)
        expires_at = (now + timedelta(days=ttl)).isoformat() if decision == "approve" and ttl else record.expires_at
        with self._connection:
            self._connection.execute(
                """UPDATE memories SET status = ?, confidence = ?, verified_at = ?,
                   expires_at = ?, metadata = ?, updated_at = ? WHERE id = ?""",
                (status.value, confidence, now.isoformat() if decision == "approve" else None,
                 expires_at, json.dumps(metadata, sort_keys=True), now.isoformat(), memory_id),
            )
        updated = self.get(memory_id)
        assert updated is not None
        return updated

    def detect_conflicts(self, project_id: str) -> list[MemoryConflict]:
        if not project_id.strip():
            raise ValueError("project_id must not be empty")
        rows = self._connection.execute(
            """SELECT * FROM memories WHERE project_id = ? AND memory_type = 'semantic'
               AND status IN ('active', 'pending')""",
            (project_id,),
        ).fetchall()
        records = [self._from_row(row) for row in rows]
        detected: list[MemoryConflict] = []
        for index, left in enumerate(records):
            left_tokens = _tokens(left.content)
            left_polarity = any(token in _NEGATIONS for token in left_tokens)
            left_subject = set(left_tokens) - _NEGATIONS - _LABELS
            if len(left_subject) < 3:
                continue
            for right in records[index + 1:]:
                if left.agent_id is not None and right.agent_id is not None and left.agent_id != right.agent_id:
                    continue
                right_tokens = _tokens(right.content)
                right_polarity = any(token in _NEGATIONS for token in right_tokens)
                if left_polarity == right_polarity:
                    continue
                right_subject = set(right_tokens) - _NEGATIONS - _LABELS
                if len(right_subject) < 3:
                    continue
                union = left_subject | right_subject
                similarity = len(left_subject & right_subject) / max(len(union), 1)
                if similarity < 0.85:
                    continue
                left_id, right_id = sorted((left.id, right.id))
                conflict_id = str(uuid4())
                reason = (
                    f"Explicit positive/negative polarity conflict; normalized subject similarity "
                    f"{similarity:.2f}. Review both statements before approval."
                )
                with self._connection:
                    self._connection.execute(
                        """INSERT OR IGNORE INTO memory_conflicts (
                            id, project_id, left_memory_id, right_memory_id, reason, status, created_at
                        ) VALUES (?, ?, ?, ?, ?, 'open', ?)""",
                        (conflict_id, project_id, left_id, right_id, reason, _utc_now()),
                    )
                row = self._connection.execute(
                    "SELECT * FROM memory_conflicts WHERE left_memory_id = ? AND right_memory_id = ?",
                    (left_id, right_id),
                ).fetchone()
                if row:
                    detected.append(self._conflict_from_row(row))
        return detected

    def list_conflicts(self, project_id: str, include_resolved: bool = False) -> list[MemoryConflict]:
        sql = "SELECT * FROM memory_conflicts WHERE project_id = ?"
        if not include_resolved:
            sql += " AND status = 'open'"
        sql += " ORDER BY created_at DESC"
        return [
            self._conflict_from_row(row)
            for row in self._connection.execute(sql, (project_id,)).fetchall()
        ]

    def resolve_conflict(self, conflict_id: str, keep_memory_id: str, reviewer: str) -> MemoryConflict:
        if not reviewer.strip():
            raise ValueError("reviewer must not be empty")
        row = self._connection.execute(
            "SELECT * FROM memory_conflicts WHERE id = ?", (conflict_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"memory conflict not found: {conflict_id}")
        conflict = self._conflict_from_row(row)
        if conflict.status != "open":
            raise ValueError("memory conflict is already resolved")
        if keep_memory_id not in {conflict.left_memory_id, conflict.right_memory_id}:
            raise ValueError("kept memory must be one of the conflicting records")
        remove_id = (
            conflict.right_memory_id if keep_memory_id == conflict.left_memory_id
            else conflict.left_memory_id
        )
        now = _utc_now()
        kept = self.get(keep_memory_id)
        removed = self.get(remove_id)
        if kept is None or removed is None:
            raise ValueError("conflict references a missing memory record")
        kept_metadata = dict(kept.metadata)
        kept_metadata.update({"reviewed_by": reviewer, "conflict_resolution": "kept", "verified_at": now})
        removed_metadata = dict(removed.metadata)
        removed_metadata.update({"reviewed_by": reviewer, "superseded_by": keep_memory_id})
        with self._connection:
            self._connection.execute(
                "UPDATE memories SET status = 'active', confidence = MAX(confidence, 0.9), verified_at = ?, metadata = ?, updated_at = ? WHERE id = ?",
                (now, json.dumps(kept_metadata, sort_keys=True), now, keep_memory_id),
            )
            self._connection.execute(
                "UPDATE memories SET status = 'superseded', metadata = ?, updated_at = ? WHERE id = ?",
                (json.dumps(removed_metadata, sort_keys=True), now, remove_id),
            )
            self._connection.execute(
                "UPDATE memory_conflicts SET status = 'resolved', resolution = ? WHERE id = ?",
                (f"kept={keep_memory_id}; superseded={remove_id}; reviewer={reviewer}", conflict_id),
            )
        resolved_row = self._connection.execute(
            "SELECT * FROM memory_conflicts WHERE id = ?", (conflict_id,)
        ).fetchone()
        assert resolved_row is not None
        return self._conflict_from_row(resolved_row)

    def expire_stale(self, project_id: str | None = None) -> int:
        now = _utc_now()
        sql = """UPDATE memories SET status = 'expired', updated_at = ?
                 WHERE status IN ('active', 'pending') AND expires_at IS NOT NULL AND expires_at <= ?"""
        params: list[Any] = [now, now]
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(project_id)
        with self._connection:
            cursor = self._connection.execute(sql, params)
        return int(cursor.rowcount)

    def reindex_embeddings(self, project_id: str | None = None, batch_size: int = 32) -> int:
        if self.embedder is None:
            raise ValueError("configure a local embedding provider before reindexing")
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        sql = "SELECT id, content, summary, tags FROM memories"
        params: list[Any] = []
        if project_id is not None:
            sql += " WHERE project_id = ?"
            params.append(project_id)
        sql += " AND (embedding_json IS NULL OR embedding_model != ?)" if " WHERE " in sql else " WHERE embedding_json IS NULL OR embedding_model != ?"
        params.append(self.embedder.model_id)
        rows = self._connection.execute(sql, params).fetchall()
        updated = 0
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset:offset + batch_size]
            texts = [
                " ".join((row["content"], row["summary"], *json.loads(row["tags"])))
                for row in batch
            ]
            vectors = self.embedder.embed(texts)
            if len(vectors) != len(batch):
                raise ValueError("embedding provider returned the wrong number of vectors")
            with self._connection:
                for row, vector in zip(batch, vectors):
                    values = [float(value) for value in vector]
                    if not values or not all(math.isfinite(value) for value in values):
                        raise ValueError("embedding provider returned an invalid vector")
                    self._connection.execute(
                        "UPDATE memories SET embedding_json = ?, embedding_model = ?, updated_at = ? WHERE id = ?",
                        (json.dumps(values), self.embedder.model_id, _utc_now(), row["id"]),
                    )
                    updated += 1
        return updated

    def consolidate(self, project_id: str | None = None) -> int:
        if project_id is None:
            rows = self._connection.execute("SELECT * FROM memories ORDER BY created_at, id").fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM memories WHERE project_id = ? ORDER BY created_at, id", (project_id,)
            ).fetchall()
        groups: dict[tuple[str, str, str, str, str], list[MemoryRecord]] = {}
        for row in rows:
            record = self._from_row(row)
            fingerprint = _normalize_content(record.content)
            if fingerprint:
                key = (
                    record.project_id, record.memory_type.value, record.agent_id or "",
                    record.status.value, fingerprint,
                )
                groups.setdefault(key, []).append(record)
        removed = 0
        with self._connection:
            for records in groups.values():
                if len(records) < 2:
                    continue
                canonical = records[0]
                metadata = dict(canonical.metadata)
                source_runs = set(metadata.get("consolidated_source_run_ids", []))
                source_events = set(metadata.get("consolidated_source_event_sequences", []))
                for record in records:
                    if record.source_run_id:
                        source_runs.add(record.source_run_id)
                    source_runs.update(record.metadata.get("consolidated_source_run_ids", []))
                    source_events.update(record.source_event_sequences)
                    source_events.update(record.metadata.get("consolidated_source_event_sequences", []))
                metadata["consolidated_source_run_ids"] = sorted(source_runs)
                metadata["consolidated_source_event_sequences"] = sorted(source_events)
                consolidated_tags = sorted({tag for record in records for tag in record.tags})
                max_confidence = max(record.confidence for record in records)
                self._connection.execute(
                    "UPDATE memories SET metadata = ?, tags = ?, confidence = ? WHERE id = ?",
                    (json.dumps(metadata, sort_keys=True), json.dumps(consolidated_tags), max_confidence, canonical.id),
                )
                duplicate_ids = [record.id for record in records[1:]]
                self._connection.executemany(
                    "DELETE FROM memories WHERE id = ?", ((identifier,) for identifier in duplicate_ids)
                )
                removed += len(duplicate_ids)
        return removed

    def count(self, *, project_id: str | None = None, status: MemoryStatus | None = None) -> int:
        sql = "SELECT COUNT(*) AS count FROM memories WHERE 1=1"
        params: list[Any] = []
        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(project_id)
        if status is not None:
            sql += " AND status = ?"
            params.append(status.value)
        row = self._connection.execute(sql, params).fetchone()
        return int(row["count"])

    def close(self) -> None:
        self._connection.close()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"], project_id=row["project_id"],
            memory_type=MemoryType(row["memory_type"]), content=row["content"],
            summary=row["summary"], source_run_id=row["source_run_id"],
            source_event_sequences=tuple(json.loads(row["source_event_sequences"])),
            agent_id=row["agent_id"], tags=tuple(json.loads(row["tags"])),
            metadata=json.loads(row["metadata"]), created_at=row["created_at"],
            confidence=float(row["confidence"]), status=MemoryStatus(row["status"]),
            verified_at=row["verified_at"], expires_at=row["expires_at"],
        )

    @staticmethod
    def _conflict_from_row(row: sqlite3.Row) -> MemoryConflict:
        return MemoryConflict(
            id=row["id"], project_id=row["project_id"],
            left_memory_id=row["left_memory_id"], right_memory_id=row["right_memory_id"],
            reason=row["reason"], status=row["status"], created_at=row["created_at"],
            resolution=row["resolution"],
        )


def extract_reusable_knowledge(
    *, project_id: str, source_run_id: str, source_event_sequences: Iterable[int],
    candidate: str, agent_id: str | None = None,
) -> list[MemoryRecord]:
    """Conservatively extract explicitly marked lessons for human approval."""
    prefixes = ("decision:", "pattern:", "lesson:", "rule:")
    records: list[MemoryRecord] = []
    seen: set[str] = set()
    for line in candidate.splitlines():
        statement = " ".join(line.strip().split())
        if not statement.casefold().startswith(prefixes):
            continue
        label, _, body = statement.partition(":")
        if not body.strip() or statement.casefold() in seen:
            continue
        seen.add(statement.casefold())
        content = f"{label.strip()}: {body.strip()}"
        records.append(MemoryRecord.create(
            project_id=project_id, memory_type=MemoryType.SEMANTIC,
            content=content, summary=body.strip(), source_run_id=source_run_id,
            source_event_sequences=source_event_sequences, agent_id=agent_id,
            tags=(label.casefold(), "extracted"),
            confidence=0.6, status=MemoryStatus.PENDING,
            metadata={"extraction_method": "explicit_marker_v2"},
        ))
    return records
