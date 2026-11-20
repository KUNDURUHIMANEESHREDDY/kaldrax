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


def _load_structured_session(
    contradiction_path: str | Path,
    extraction_path: str | Path,
    *,
    reviewer: str,
    session_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer identity is required")
    contradiction, contradiction_raw = _read(Path(contradiction_path), "contradiction dataset")
    extraction, extraction_raw = _read(Path(extraction_path), "extraction dataset")
    source_hashes = {
        "contradiction": hashlib.sha256(contradiction_raw).hexdigest(),
        "extraction": hashlib.sha256(extraction_raw).hexdigest(),
    }
    path = Path(session_path)
    if path.exists():
        try:
            session = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("review session is unreadable") from None
        if (
            not isinstance(session, dict)
            or session.get("schema_version") != 1
            or session.get("source_hashes") != source_hashes
        ):
            raise ValueError(
                "source datasets changed since review began; preserve the old session and start a new one"
            )
        if session.get("reviewer") != reviewer:
            raise ValueError("review session belongs to a different reviewer identity")
    else:
        session = {
            "schema_version": 1,
            "reviewer": reviewer,
            "source_hashes": source_hashes,
            "contradiction": {},
            "extraction": {},
        }

    for kind, dataset in (("contradiction", contradiction), ("extraction", extraction)):
        decisions = session.setdefault(kind, {})
        if not isinstance(decisions, dict):
            raise ValueError(f"review session {kind} decisions are invalid")
        case_ids = {case["id"] for case in dataset["cases"]}
        if set(decisions) - case_ids:
            raise ValueError(f"review session contains unknown {kind} case IDs")
    approvals = session.setdefault("approvals", {})
    exports = session.setdefault("exports", {})
    if not isinstance(approvals, dict) or not isinstance(exports, dict):
        raise ValueError("review session approval/export metadata is invalid")
    for kind in ("contradiction", "extraction"):
        approvals.setdefault(kind, {"status": "pending", "reviewer": None, "reviewed_at": None})
        if not isinstance(approvals[kind], dict):
            raise ValueError(f"review session {kind} approval is invalid")
        if kind in exports and not isinstance(exports[kind], str):
            raise ValueError(f"review session {kind} export path is invalid")
    _save_session(path, session)
    return contradiction, extraction, session, path


def _structured_quality_state(
    contradiction: dict[str, Any],
    extraction: dict[str, Any],
    session: dict[str, Any],
    path: Path,
) -> dict[str, Any]:
    datasets: dict[str, Any] = {}
    for kind, source in (("contradiction", contradiction), ("extraction", extraction)):
        cases = []
        decisions = session[kind]
        for case in source["cases"]:
            decision = decisions.get(case["id"])
            reviewed = isinstance(decision, dict)
            item = {
                "id": case["id"],
                "category": case.get("category", "uncategorized"),
                "reviewed": reviewed,
                "review_status": decision.get("review_status") if reviewed else "pending",
                "reviewer": decision.get("reviewer") if reviewed else None,
                "reviewed_at": decision.get("reviewed_at") if reviewed else None,
                "note": decision.get("note") if reviewed else None,
            }
            if kind == "contradiction":
                item.update({
                    "left": case.get("left", ""),
                    "right": case.get("right", ""),
                    "proposed_expected_conflict": case.get("expected_conflict"),
                    "expected_conflict": (
                        decision.get("expected_conflict") if reviewed
                        else case.get("expected_conflict")
                    ),
                })
            else:
                item.update({
                    "objective": case.get("objective", ""),
                    "candidate": case.get("candidate", ""),
                    "proposed_expected": case.get("expected", []),
                    "expected": decision.get("expected") if reviewed else case.get("expected", []),
                })
            cases.append(item)
        approval = dict(session["approvals"][kind])
        export_path = session["exports"].get(kind)
        datasets[kind] = {
            "name": source.get("name", kind),
            "version": source.get("version"),
            "total": len(source["cases"]),
            "reviewed": len(decisions),
            "review_ready": len(decisions) == len(source["cases"]),
            "approval": approval,
            "export_path": export_path,
            "cases": cases,
        }
    complete = all(
        datasets[kind]["approval"].get("status") == "approved"
        and datasets[kind]["export_path"]
        for kind in ("contradiction", "extraction")
    )
    return {
        "reviewer": session["reviewer"],
        "session_path": str(path),
        "source_hashes": dict(session["source_hashes"]),
        "contradiction": datasets["contradiction"],
        "extraction": datasets["extraction"],
        "status": "validated_exported" if complete else "review_pending",
    }


def get_quality_review_state(
    contradiction_path: str | Path,
    extraction_path: str | Path,
    *,
    reviewer: str,
    session_path: str | Path = ".kaldrax/memory-quality-review.desktop.session.json",
) -> dict[str, Any]:
    """Return resumable, source-hash-bound review state for desktop/API clients."""
    contradiction, extraction, session, path = _load_structured_session(
        contradiction_path, extraction_path, reviewer=reviewer, session_path=session_path,
    )
    return _structured_quality_state(contradiction, extraction, session, path)


def update_quality_review(
    contradiction_path: str | Path,
    extraction_path: str | Path,
    *,
    reviewer: str,
    action: str,
    kind: str,
    session_path: str | Path = ".kaldrax/memory-quality-review.desktop.session.json",
    export_dir: str | Path = ".kaldrax/memory-quality-exports",
    case_id: str | None = None,
    decision: str | None = None,
    expected_conflict: bool | None = None,
    expected_claims: Any = None,
    note: str | None = None,
    confirmation: str | None = None,
    approval: str | None = None,
) -> dict[str, Any]:
    """Record one explicit label or dataset-approval decision and export only after approval."""
    if kind not in {"contradiction", "extraction"}:
        raise ValueError("kind must be contradiction or extraction")
    contradiction, extraction, session, path = _load_structured_session(
        contradiction_path, extraction_path, reviewer=reviewer, session_path=session_path,
    )
    source = contradiction if kind == "contradiction" else extraction

    if action == "case":
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("case_id is required")
        case = next((item for item in source["cases"] if item["id"] == case_id), None)
        if case is None:
            raise ValueError(f"unknown {kind} case ID: {case_id}")
        if decision not in {"approve", "modify"}:
            raise ValueError("case decision must be approve or modify")
        if kind == "contradiction":
            proposed = case.get("expected_conflict")
            if not isinstance(proposed, bool):
                raise ValueError(f"contradiction case {case_id} has no boolean expected_conflict label")
            if decision == "modify" and not isinstance(expected_conflict, bool):
                raise ValueError("modified contradiction labels must be boolean")
            label = expected_conflict if decision == "modify" else proposed
            reviewed = {"expected_conflict": label}
        else:
            proposed = case.get("expected")
            if not _valid_expected(proposed):
                raise ValueError(f"extraction case {case_id} has invalid proposed expected claims")
            if decision == "modify" and not _valid_expected(expected_claims):
                raise ValueError("modified expected claims must be a non-empty list of match_terms objects")
            reviewed = {"expected": expected_claims if decision == "modify" else proposed}
        reviewed.update({
            "review_status": "modified" if decision == "modify" else "approved",
            "reviewer": reviewer.strip(),
            "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "note": note.strip() if isinstance(note, str) and note.strip() else None,
        })
        session[kind][case_id] = reviewed
        session["approvals"][kind] = {"status": "pending", "reviewer": None, "reviewed_at": None}
        session["exports"].pop(kind, None)
        _save_session(path, session)
    elif action == "dataset-approval":
        if approval not in {"approve", "reject"}:
            raise ValueError("dataset approval must be approve or reject")
        if approval == "approve":
            case_ids = {item["id"] for item in source["cases"]}
            if set(session[kind]) != case_ids:
                raise ValueError(f"all {kind} cases must be reviewed before dataset approval")
            required_confirmation = f"APPROVE {kind.upper()}"
            if confirmation != required_confirmation:
                raise ValueError(f"type {required_confirmation} to confirm this dataset approval")
            reviewed_cases = []
            for case in source["cases"]:
                reviewed = dict(case)
                reviewed.update(session[kind][case["id"]])
                reviewed.update({
                    "annotation_status": "human_reviewed",
                    "review_status": session[kind][case["id"]]["review_status"],
                    "reviewer": session[kind][case["id"]]["reviewer"],
                    "reviewed_at": session[kind][case["id"]]["reviewed_at"],
                })
                reviewed_cases.append(reviewed)
            export_path = _write_export(
                source, reviewed_cases,
                source_hash=session["source_hashes"][kind],
                reviewer=reviewer.strip(),
                destination=Path(export_dir),
            )
            session["approvals"][kind] = {
                "status": "approved",
                "reviewer": reviewer.strip(),
                "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            session["exports"][kind] = str(export_path)
        else:
            session["approvals"][kind] = {
                "status": "rejected",
                "reviewer": reviewer.strip(),
                "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            session["exports"].pop(kind, None)
        _save_session(path, session)
    else:
        raise ValueError("action must be case or dataset-approval")

    return _structured_quality_state(contradiction, extraction, session, path)


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
