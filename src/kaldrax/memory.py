"""Project-scoped persistent memory with traceable run provenance.

SQLite persistence and deterministic lexical retrieval use only the standard
library. Retrieval is not embedding-based semantic similarity.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Protocol
from uuid import uuid4


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    @classmethod
    def create(
        cls, *, project_id: str, memory_type: MemoryType, content: str,
        summary: str = "", source_run_id: str | None = None,
        source_event_sequences: Iterable[int] = (), agent_id: str | None = None,
        tags: Iterable[str] = (), metadata: dict[str, Any] | None = None,
    ) -> "MemoryRecord":
        return cls(
            id=str(uuid4()), project_id=project_id, memory_type=memory_type,
            content=content, summary=summary, source_run_id=source_run_id,
            source_event_sequences=tuple(source_event_sequences), agent_id=agent_id,
            tags=tuple(tags), metadata=dict(metadata or {}),
        )


@dataclass(frozen=True)
class MemoryMatch:
    record: MemoryRecord
    score: float


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
    "into", "its", "our", "that", "the", "their", "then", "there",
    "these", "this", "those", "through", "with", "will", "would", "your",
}


def _tokens(value: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(value.casefold()) if token not in _STOP_WORDS]


def _normalize_content(value: str) -> str:
    return " ".join(_tokens(value))


class SQLiteMemoryStore:
    """SQLite-backed memory; all queries are constrained to a project.

    A record with no agent_id is shared by the whole project. Agent-specific
    searches see their own records plus project-shared records.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
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
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_project_type ON memories(project_id, memory_type)"
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_project_agent ON memories(project_id, agent_id)"
        )
        self._connection.commit()

    def save(self, record: MemoryRecord) -> None:
        with self._connection:
            self._connection.execute(
                """INSERT INTO memories (
                    id, project_id, memory_type, content, summary, source_run_id,
                    source_event_sequences, agent_id, tags, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    content=excluded.content, summary=excluded.summary,
                    metadata=excluded.metadata, tags=excluded.tags""",
                (
                    record.id, record.project_id, record.memory_type.value,
                    record.content, record.summary, record.source_run_id,
                    json.dumps(record.source_event_sequences), record.agent_id,
                    json.dumps(record.tags), json.dumps(record.metadata, sort_keys=True),
                    record.created_at,
                ),
            )

    def search(
        self, query: str, *, project_id: str, limit: int = 5,
        memory_types: tuple[MemoryType, ...] = (MemoryType.EPISODIC, MemoryType.SEMANTIC),
        agent_id: str | None = None,
    ) -> list[MemoryMatch]:
        if not project_id.strip():
            raise ValueError("project_id must not be empty")
        if limit < 1:
            raise ValueError("limit must be at least 1")
        query_terms = set(_tokens(query))
        if not query_terms or not memory_types:
            return []
        placeholders = ",".join("?" for _ in memory_types)
        sql = f"SELECT * FROM memories WHERE project_id = ? AND memory_type IN ({placeholders})"
        params: list[Any] = [project_id, *(kind.value for kind in memory_types)]
        if agent_id is not None:
            sql += " AND (agent_id IS NULL OR agent_id = ?)"
            params.append(agent_id)
        rows = self._connection.execute(sql, params).fetchall()
        matches: list[MemoryMatch] = []
        for row in rows:
            record = self._from_row(row)
            terms = _tokens(" ".join((record.content, record.summary, *record.tags)))
            counts: dict[str, int] = {}
            for term in terms:
                counts[term] = counts.get(term, 0) + 1
            overlap = query_terms.intersection(counts)
            if not overlap:
                continue
            weighted = sum(1.0 + math.log(counts[term]) for term in overlap)
            score = weighted / math.sqrt(max(len(terms), 1))
            matches.append(MemoryMatch(record, score))
        matches.sort(key=lambda item: (item.score, item.record.created_at), reverse=True)
        return matches[:limit]

    def consolidate(self, project_id: str | None = None) -> int:
        """Merge exact normalized duplicates and retain all contributing run IDs."""
        if project_id is None:
            rows = self._connection.execute("SELECT * FROM memories ORDER BY created_at, id").fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM memories WHERE project_id = ? ORDER BY created_at, id", (project_id,)
            ).fetchall()
        groups: dict[tuple[str, str, str, str], list[MemoryRecord]] = {}
        for row in rows:
            record = self._from_row(row)
            fingerprint = _normalize_content(record.content)
            if fingerprint:
                groups.setdefault((record.project_id, record.memory_type.value, record.agent_id or "", fingerprint), []).append(record)
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
                self._connection.execute(
                    "UPDATE memories SET metadata = ?, tags = ? WHERE id = ?",
                    (json.dumps(metadata, sort_keys=True), json.dumps(consolidated_tags), canonical.id),
                )
                duplicate_ids = [record.id for record in records[1:]]
                self._connection.executemany(
                    "DELETE FROM memories WHERE id = ?", ((identifier,) for identifier in duplicate_ids)
                )
                removed += len(duplicate_ids)
        return removed

    def count(self, *, project_id: str | None = None) -> int:
        if project_id is None:
            row = self._connection.execute("SELECT COUNT(*) AS count FROM memories").fetchone()
        else:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM memories WHERE project_id = ?", (project_id,)
            ).fetchone()
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
        )


def extract_reusable_knowledge(
    *, project_id: str, source_run_id: str, source_event_sequences: Iterable[int],
    candidate: str, agent_id: str | None = None,
) -> list[MemoryRecord]:
    """Extract only explicitly marked lessons; never infer or hallucinate facts.

    Recognized line prefixes: Decision:, Pattern:, Lesson:, and Rule:.
    """
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
            metadata={"extraction_method": "explicit_marker_v1"},
        ))
    return records
