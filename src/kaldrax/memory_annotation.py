"""Human review, privacy approval, and immutable exports for retrieval benchmarks."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SESSION_SCHEMA_VERSION = 1
_REVIEWED_QUERY_STATES = {"approved", "modified"}
_VERSION_RE = re.compile(r"^[0-9]+[.][0-9]+[.][0-9]+$")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _canonical_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def verify_dataset_integrity(dataset: dict[str, Any]) -> bool:
    integrity = dataset.get("integrity")
    if not isinstance(integrity, dict):
        return False
    if integrity.get("algorithm") != "sha256":
        return False
    if integrity.get("scope") != "canonical-json-excluding-integrity":
        return False
    expected = integrity.get("digest")
    if not isinstance(expected, str) or len(expected) != 64:
        return False
    payload = dict(dataset)
    payload.pop("integrity", None)
    return _canonical_sha256(payload) == expected


def assess_dataset_review(dataset: dict[str, Any]) -> dict[str, Any]:
    """Return whether a dataset is eligible to be described as human-validated."""
    blockers: list[str] = []
    if dataset.get("annotation_status") != "human_reviewed":
        blockers.append("dataset relevance labels have not been marked human-reviewed")

    approval = dataset.get("dataset_approval")
    if not isinstance(approval, dict) or approval.get("status") != "approved":
        blockers.append("dataset-level annotation approval is missing")
    elif not approval.get("reviewer") or not approval.get("reviewed_at"):
        blockers.append("dataset-level approval lacks reviewer provenance")

    privacy = dataset.get("privacy_screening")
    if not isinstance(privacy, dict) or privacy.get("status") != "approved":
        blockers.append("privacy screening has not been approved")
    elif not privacy.get("reviewer") or not privacy.get("reviewed_at"):
        blockers.append("privacy approval lacks reviewer provenance")

    memories = dataset.get("memories")
    memory_ids = {
        item.get("id") for item in memories
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    } if isinstance(memories, list) else set()
    queries = dataset.get("queries")
    if not isinstance(queries, list) or not queries:
        blockers.append("dataset has no query judgments")
    else:
        for query in queries:
            if not isinstance(query, dict):
                blockers.append("dataset contains a malformed query judgment")
                continue
            query_id = str(query.get("id", "<unknown>"))
            if query.get("annotation_status") != "human_reviewed":
                blockers.append(f"query {query_id} is not human-reviewed")
            if query.get("review_status") not in _REVIEWED_QUERY_STATES:
                blockers.append(f"query {query_id} has no accepted review decision")
            if not query.get("reviewer") or not query.get("reviewed_at"):
                blockers.append(f"query {query_id} lacks reviewer provenance")
            relevant = query.get("relevant")
            if (
                not isinstance(relevant, list) or not relevant
                or any(not isinstance(identifier, str) or identifier not in memory_ids for identifier in relevant)
            ):
                blockers.append(f"query {query_id} has an empty or invalid relevance judgment")

    if not verify_dataset_integrity(dataset):
        blockers.append("dataset integrity digest is missing or invalid")

    return {
        "status": "validated" if not blockers else "exploratory_only",
        "validated": not blockers,
        "blocking_reasons": blockers,
    }


def _read_dataset(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        dataset = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read annotation dataset: {type(exc).__name__}") from None
    if not isinstance(dataset, dict):
        raise ValueError("annotation dataset must be a JSON object")
    memories = dataset.get("memories")
    queries = dataset.get("queries")
    if not isinstance(memories, list) or not memories:
        raise ValueError("annotation dataset requires a non-empty memories array")
    if not isinstance(queries, list) or not queries:
        raise ValueError("annotation dataset requires a non-empty queries array")

    memory_ids: set[str] = set()
    for memory in memories:
        if (
            not isinstance(memory, dict)
            or not isinstance(memory.get("id"), str) or not memory["id"].strip()
            or not isinstance(memory.get("content"), str) or not memory["content"].strip()
        ):
            raise ValueError("each memory requires non-empty id and content strings")
        if memory["id"] in memory_ids:
            raise ValueError(f"duplicate memory id: {memory['id']}")
        memory_ids.add(memory["id"])

    query_ids: set[str] = set()
    for query in queries:
        if (
            not isinstance(query, dict)
            or not isinstance(query.get("id"), str) or not query["id"].strip()
            or not isinstance(query.get("query"), str) or not query["query"].strip()
        ):
            raise ValueError("each query requires non-empty id and query strings")
        if query["id"] in query_ids:
            raise ValueError(f"duplicate query id: {query['id']}")
        query_ids.add(query["id"])
        relevant = query.get("relevant")
        if not isinstance(relevant, list) or not relevant:
            raise ValueError(f"query {query['id']} requires a non-empty proposed relevant-ID list")
        if any(not isinstance(identifier, str) or identifier not in memory_ids for identifier in relevant):
            raise ValueError(f"query {query['id']} references an unknown memory ID")
    return dataset, raw


def _new_session(dataset: dict[str, Any], source_path: Path, raw: bytes) -> dict[str, Any]:
    privacy = dataset.get("privacy_screening")
    privacy_scope = privacy.get("scope", "") if isinstance(privacy, dict) else ""
    privacy_note = privacy.get("note", "") if isinstance(privacy, dict) else ""
    return {
        "schema_version": _SESSION_SCHEMA_VERSION,
        "dataset_name": str(dataset.get("name", source_path.stem)),
        "source_dataset": str(source_path),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_revision": dataset.get("source_revision"),
        "started_at": _now(),
        "updated_at": _now(),
        "dataset_approval": {
            "status": "pending", "reviewer": None, "reviewed_at": None,
        },
        "privacy_screening": {
            "status": "pending", "scope": str(privacy_scope), "note": str(privacy_note),
            "reviewer": None, "reviewed_at": None,
        },
        "queries": {
            query["id"]: {
                "status": "pending",
                "proposed_relevant": list(query["relevant"]),
                "relevant": list(query["relevant"]),
                "rationale": str(query.get("rationale", "")),
                "reviewer": None,
                "reviewed_at": None,
                "review_note": None,
            }
            for query in dataset["queries"]
        },
    }


def _load_session(
    dataset: dict[str, Any], source_path: Path, raw: bytes, session_path: Path,
) -> dict[str, Any]:
    if not session_path.exists():
        return _new_session(dataset, source_path, raw)
    try:
        session = json.loads(session_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError(f"review session is unreadable: {session_path}") from None
    if not isinstance(session, dict) or session.get("schema_version") != _SESSION_SCHEMA_VERSION:
        raise ValueError("review session has an unsupported schema version")
    digest = hashlib.sha256(raw).hexdigest()
    if session.get("source_sha256") != digest:
        raise ValueError(
            "source dataset changed since this review session began; preserve the session and "
            "start a new review session for the updated dataset"
        )
    expected_ids = {query["id"] for query in dataset["queries"]}
    session_queries = session.get("queries")
    if not isinstance(session_queries, dict) or set(session_queries) != expected_ids:
        raise ValueError("review session query IDs do not match the source dataset")
    return session


def _save_session(path: Path, session: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = _now()
    payload = json.dumps(session, ensure_ascii=False, indent=2) + "\n"
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _review_ready(session: dict[str, Any]) -> bool:
    return all(
        isinstance(item, dict) and item.get("status") in _REVIEWED_QUERY_STATES
        and bool(item.get("reviewer")) and bool(item.get("reviewed_at"))
        for item in session.get("queries", {}).values()
    )


def export_approved_dataset(
    dataset: dict[str, Any], session: dict[str, Any], *,
    export_dir: str | Path, version: str = "1.0.0",
) -> Path:
    """Write a hash-addressed, write-once benchmark export."""
    if not _VERSION_RE.fullmatch(version):
        raise ValueError("dataset version must use numeric MAJOR.MINOR.PATCH form")
    if not _review_ready(session):
        raise ValueError("every query must have an approved or modified human review")
    if session.get("dataset_approval", {}).get("status") != "approved":
        raise ValueError("dataset-level annotation approval is required")
    if session.get("privacy_screening", {}).get("status") != "approved":
        raise ValueError("separate privacy-screening approval is required")

    payload = json.loads(json.dumps(dataset))
    reviewed_queries = session["queries"]
    for query in payload["queries"]:
        review = reviewed_queries[query["id"]]
        query["proposed_relevant"] = list(review["proposed_relevant"])
        query["relevant"] = list(review["relevant"])
        query["annotation_status"] = "human_reviewed"
        query["review_status"] = review["status"]
        query["reviewer"] = review["reviewer"]
        query["reviewed_at"] = review["reviewed_at"]
        if review.get("review_note"):
            query["review_note"] = review["review_note"]

    approval = dict(session["dataset_approval"])
    privacy = dict(payload.get("privacy_screening", {}))
    privacy.update(session["privacy_screening"])
    privacy["status"] = "approved"
    payload["privacy_screening"] = privacy
    payload["annotation_status"] = "human_reviewed"
    payload["dataset_approval"] = approval
    payload["reviewer"] = approval["reviewer"]
    payload["review_provenance"] = {
        "source_dataset": session["source_dataset"],
        "source_sha256": session["source_sha256"],
        "source_revision": session.get("source_revision"),
        "session_schema_version": _SESSION_SCHEMA_VERSION,
        "reviewers": sorted({
            item["reviewer"] for item in reviewed_queries.values() if item.get("reviewer")
        }),
    }
    payload["version"] = version
    payload.pop("integrity", None)
    payload["integrity"] = {
        "algorithm": "sha256",
        "scope": "canonical-json-excluding-integrity",
        "digest": _canonical_sha256(payload),
    }
    assessment = assess_dataset_review(payload)
    if not assessment["validated"]:
        raise ValueError("review export failed validation: " + "; ".join(assessment["blocking_reasons"]))

    slug = re.sub(r"[^a-z0-9]+", "-", str(payload.get("name", "benchmark")).casefold()).strip("-")
    digest = payload["integrity"]["digest"]
    destination = Path(export_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / f"{slug or 'benchmark'}-v{version}-{digest[:12]}.json"
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        with output_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    except FileExistsError:
        if output_path.read_text(encoding="utf-8") != encoded:
            raise ValueError(f"refusing to overwrite immutable benchmark export: {output_path}") from None
    return output_path


def run_annotation_review(
    dataset_path: str | Path, *, reviewer: str,
    session_path: str | Path | None = None,
    export_dir: str | Path = ".kaldrax/benchmark-exports",
    version: str = "1.0.0",
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run a resumable terminal review of labels and privacy scope."""
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer identity must be non-empty")
    if not _VERSION_RE.fullmatch(version):
        raise ValueError("dataset version must use numeric MAJOR.MINOR.PATCH form")
    read_input = input_fn or input
    write_output = output_fn or print

    source_path = Path(dataset_path)
    dataset, raw = _read_dataset(source_path)
    review_path = Path(session_path) if session_path else (
        Path(".kaldrax") / "benchmark-reviews" / f"{source_path.stem}.review.json"
    )
    session = _load_session(dataset, source_path, raw, review_path)
    memory_by_id = {item["id"]: item for item in dataset["memories"]}

    write_output(
        f"Dataset: {dataset.get('name', source_path.stem)} | "
        f"source revision: {dataset.get('source_revision', 'unspecified')}"
    )
    write_output("Candidate memory index (use these exact IDs when editing relevance labels):")
    for memory in dataset["memories"]:
        source = memory.get("source") or {}
        location = f"{source.get('path', 'no source path')}#{source.get('anchor', '')}".rstrip("#")
        summary = str(memory.get("summary") or memory["content"]).replace("\n", " ")
        write_output(f"- {memory['id']} [{memory.get('category', 'uncategorized')}] {location}: {summary}")

    stopped = False
    for query in dataset["queries"]:
        state = session["queries"][query["id"]]
        write_output("")
        write_output(
            f"[{query['id']}] {query.get('category', 'uncategorized')} "
            f"| current review: {state.get('status', 'pending')}"
        )
        write_output(f"Query: {query['query']}")
        write_output("Proposed/current relevant memories:")
        selected = state.get("relevant") or state.get("proposed_relevant", [])
        for identifier in selected:
            memory = memory_by_id[identifier]
            source = memory.get("source") or {}
            write_output(
                f"  - {identifier}: {memory['content']} "
                f"(source: {source.get('path', 'unspecified')}#{source.get('anchor', '')})"
            )
        action = read_input(
            "Decision [a]pprove current / [r]eject / [e]dit IDs / [s]kip / [q]uit: "
        ).strip().casefold()
        if action == "q":
            stopped = True
            break
        if action == "s" or not action:
            continue
        if action == "a":
            state["relevant"] = list(state.get("relevant") or state["proposed_relevant"])
            state["status"] = "approved"
            state["review_note"] = None
        elif action == "r":
            state["relevant"] = []
            state["status"] = "rejected"
            state["review_note"] = read_input("Reason for rejecting this relevance proposal: ").strip()
        elif action == "e":
            raw_ids = read_input("Correct relevant memory IDs (comma-separated): ").strip()
            selected_ids = [part.strip() for part in raw_ids.split(",") if part.strip()]
            if not selected_ids or len(selected_ids) != len(set(selected_ids)):
                raise ValueError("edited relevance labels must contain unique, non-empty memory IDs")
            unknown = sorted(set(selected_ids) - set(memory_by_id))
            if unknown:
                raise ValueError(f"edited relevance labels contain unknown memory IDs: {unknown}")
            state["relevant"] = selected_ids
            state["status"] = "modified"
            state["review_note"] = read_input("Optional rationale for the modification: ").strip() or None
        else:
            write_output("Unrecognized action; this query remains unchanged.")
            continue
        state["reviewer"] = reviewer
        state["reviewed_at"] = _now()
        session["dataset_approval"] = {
            "status": "pending", "reviewer": None, "reviewed_at": None,
        }
        _save_session(review_path, session)

    if not stopped and _review_ready(session):
        approval_status = session.get("dataset_approval", {}).get("status")
        if approval_status != "approved":
            write_output("")
            decision = read_input(
                "All query labels are reviewed. Dataset annotation approval "
                "[a]pprove / [r]eject / [s]kip: "
            ).strip().casefold()
            if decision == "a":
                session["dataset_approval"] = {
                    "status": "approved", "reviewer": reviewer, "reviewed_at": _now(),
                }
            elif decision == "r":
                session["dataset_approval"] = {
                    "status": "rejected", "reviewer": reviewer, "reviewed_at": _now(),
                }
            _save_session(review_path, session)

    if not stopped and session.get("privacy_screening", {}).get("status") != "approved":
        privacy = session["privacy_screening"]
        write_output("")
        write_output("Privacy scope is a separate approval and does not follow from label approval.")
        write_output(f"Declared scope: {privacy.get('scope') or 'No scope description provided.'}")
        source_paths = sorted({
            str((item.get("source") or {}).get("path", ""))
            for item in dataset["memories"]
            if (item.get("source") or {}).get("path")
        })
        write_output("Source paths to inspect:")
        for path in source_paths:
            write_output(f"- {path}")
        decision = read_input(
            "Privacy screening [a]pprove / [r]eject / [s]kip: "
        ).strip().casefold()
        if decision == "a":
            confirmation = read_input(
                "Confirm you reviewed the source scope and displayed memory content by typing APPROVE: "
            ).strip()
            if confirmation == "APPROVE":
                privacy.update({
                    "status": "approved", "reviewer": reviewer, "reviewed_at": _now(),
                })
        elif decision == "r":
            privacy.update({
                "status": "rejected", "reviewer": reviewer, "reviewed_at": _now(),
            })
        _save_session(review_path, session)

    export_path: Path | None = None
    ready = (
        not stopped and _review_ready(session)
        and session.get("dataset_approval", {}).get("status") == "approved"
        and session.get("privacy_screening", {}).get("status") == "approved"
    )
    if ready:
        export_path = export_approved_dataset(
            dataset, session, export_dir=export_dir, version=version,
        )

    statuses: dict[str, int] = {}
    for state in session["queries"].values():
        key = str(state.get("status", "pending"))
        statuses[key] = statuses.get(key, 0) + 1
    return {
        "dataset_name": session["dataset_name"],
        "session_path": str(review_path),
        "query_status_counts": statuses,
        "dataset_approval_status": session["dataset_approval"]["status"],
        "privacy_approval_status": session["privacy_screening"]["status"],
        "export_path": str(export_path) if export_path else None,
        "benchmark_status": "validated_exported" if export_path else "not_exported",
        "stopped_early": stopped,
    }
