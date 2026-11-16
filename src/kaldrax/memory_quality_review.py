"""Interactive, resumable human review for contradiction and extraction labels."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f"cannot read {label}: {path}") from None
    if not isinstance(value, dict) or not isinstance(value.get("cases"), list) or not value["cases"]:
        raise ValueError(f"{label} must be a JSON object with a non-empty cases array")
    ids = [case.get("id") if isinstance(case, dict) else None for case in value["cases"]]
    if any(not isinstance(item, str) or not item.strip() for item in ids) or len(ids) != len(set(ids)):
        raise ValueError(f"{label} requires unique, non-empty case IDs")
    return value, raw


def _save_session(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = handle.name
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _valid_expected(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, dict)
        and isinstance(item.get("match_terms"), list)
        and bool(item["match_terms"])
        and all(isinstance(term, str) and term.strip() for term in item["match_terms"])
        for item in value
    )


def _write_export(data: dict[str, Any], cases: list[dict[str, Any]], *,
                  source_hash: str, reviewer: str, destination: Path) -> Path:
    payload = json.loads(json.dumps(data))
    payload["cases"] = cases
    payload["annotation_status"] = "human_reviewed"
    payload["dataset_approval"] = {
        "status": "approved", "reviewer": reviewer,
        "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    payload["review_provenance"] = {"source_sha256": source_hash, "reviewer": reviewer}
    payload.pop("integrity", None)
    payload["integrity"] = {
        "algorithm": "sha256",
        "scope": "canonical-json-excluding-integrity",
        "digest": _digest(payload),
    }
    destination.mkdir(parents=True, exist_ok=True)
    name = str(payload.get("name", "benchmark")).lower().replace(" ", "-")
    output = destination / f"{name}-reviewed-{payload['integrity']['digest'][:12]}.json"
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        with output.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
    except FileExistsError:
        if output.read_text(encoding="utf-8") != encoded:
            raise ValueError(f"refusing to overwrite reviewed export: {output}") from None
    return output


def run_quality_label_review(
    contradiction_path: str | Path,
    extraction_path: str | Path,
    *,
    reviewer: str,
    session_path: str | Path = ".kaldrax/memory-quality-review.session.json",
    export_dir: str | Path = "benchmarks/reviewed",
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Review every label, persist progress, and export only after explicit approvals."""
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer identity is required")
    read_input, write_output = input_fn or input, output_fn or print
    contradiction_file, extraction_file = Path(contradiction_path), Path(extraction_path)
    contradiction, contradiction_raw = _read(contradiction_file, "contradiction dataset")
    extraction, extraction_raw = _read(extraction_file, "extraction dataset")
    source_hashes = {
        "contradiction": hashlib.sha256(contradiction_raw).hexdigest(),
        "extraction": hashlib.sha256(extraction_raw).hexdigest(),
    }
    path = Path(session_path)
    if path.exists():
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ValueError("review session is unreadable") from None
        if session.get("schema_version") != 1 or session.get("source_hashes") != source_hashes:
            raise ValueError("source datasets changed since review began; preserve the old session and start a new one")
    else:
        session = {
            "schema_version": 1, "reviewer": reviewer, "source_hashes": source_hashes,
            "contradiction": {}, "extraction": {},
        }
    if session.get("reviewer") != reviewer:
        raise ValueError("review session belongs to a different reviewer identity")

    for kind, dataset in (("contradiction", contradiction), ("extraction", extraction)):
        decisions = session[kind]
        for case in dataset["cases"]:
            case_id = case["id"]
            if case_id in decisions:
                continue
            write_output(f"\n{kind}: {case_id}")
            if kind == "contradiction":
                write_output(f"LEFT: {case.get('left')}\nRIGHT: {case.get('right')}")
                write_output(f"Proposed expected_conflict: {case.get('expected_conflict')}")
                action = read_input("[a] accept / [t] toggle true-false / [q] quit: ").strip().lower()
                if action == "q":
                    _save_session(path, session)
                    return {"status": "incomplete", "session": str(path), "reviewed": {
                        key: len(value) for key, value in session.items() if key in ("contradiction", "extraction")
                    }}
                if action not in ("a", "t") or not isinstance(case.get("expected_conflict"), bool):
                    raise ValueError(f"invalid decision for contradiction case {case_id}")
                label = case["expected_conflict"] if action == "a" else not case["expected_conflict"]
                decisions[case_id] = {"expected_conflict": label, "review_status": "approved" if action == "a" else "modified"}
            else:
                write_output(f"Objective: {case.get('objective')}\nCandidate: {case.get('candidate')}")
                write_output(f"Proposed expected claims: {json.dumps(case.get('expected'), ensure_ascii=False)}")
                action = read_input("[a] accept / [e] edit expected claims JSON / [q] quit: ").strip().lower()
                if action == "q":
                    _save_session(path, session)
                    return {"status": "incomplete", "session": str(path), "reviewed": {
                        key: len(value) for key, value in session.items() if key in ("contradiction", "extraction")
                    }}
                if action == "a":
                    expected = case.get("expected")
                    review_status = "approved"
                elif action == "e":
                    try:
                        expected = json.loads(read_input("Replacement expected claims JSON: "))
                    except json.JSONDecodeError:
                        raise ValueError(f"invalid JSON for extraction case {case_id}") from None
                    if not _valid_expected(expected):
                        raise ValueError(f"invalid expected claims for extraction case {case_id}")
                    review_status = "modified"
                else:
                    raise ValueError(f"invalid decision for extraction case {case_id}")
                if not _valid_expected(expected):
                    raise ValueError(f"invalid proposed expected claims for extraction case {case_id}")
                decisions[case_id] = {"expected": expected, "review_status": review_status}
            decisions[case_id]["reviewer"] = reviewer
            decisions[case_id]["reviewed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            _save_session(path, session)

    for kind, dataset in (("contradiction", contradiction), ("extraction", extraction)):
        if len(session[kind]) != len(dataset["cases"]):
            return {"status": "incomplete", "session": str(path)}
        write_output(f"All {kind} cases reviewed. This is a separate dataset-level approval.")
        if read_input(f"Type APPROVE {kind.upper()} to export: ").strip() != f"APPROVE {kind.upper()}":
            return {"status": "approval_pending", "session": str(path)}

    exports: dict[str, str] = {}
    for kind, dataset in (("contradiction", contradiction), ("extraction", extraction)):
        reviewed_cases = []
        for case in dataset["cases"]:
            reviewed = dict(case)
            decision = session[kind][case["id"]]
            if kind == "contradiction":
                reviewed["expected_conflict"] = decision["expected_conflict"]
            else:
                reviewed["expected"] = decision["expected"]
            reviewed.update({
                "annotation_status": "human_reviewed",
                "review_status": decision["review_status"],
                "reviewer": decision["reviewer"],
                "reviewed_at": decision["reviewed_at"],
            })
            reviewed_cases.append(reviewed)
        output = _write_export(
            dataset, reviewed_cases, source_hash=source_hashes[kind],
            reviewer=reviewer, destination=Path(export_dir),
        )
        exports[kind] = str(output)
    return {"status": "complete", "reviewer": reviewer, "exports": exports, "session": str(path)}
