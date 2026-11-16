"""Aggregate memory evaluation reports and evidence-backed release gates."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from .memory_annotation import assess_dataset_review
from .memory_benchmark_comparison import run_retrieval_comparison
from .memory_contradiction_quality import run_contradiction_benchmark

DEFAULT_RETRIEVAL_DATASET = Path("benchmarks/memory_retrieval_kaldrax_v1.json")
DEFAULT_CONTRADICTION_DATASET = Path("benchmarks/memory_contradictions_v1.json")
DEFAULT_EXTRACTION_DATASET = Path("benchmarks/memory_extraction_v1.json")
DEFAULT_THRESHOLDS = Path("benchmarks/memory_release_thresholds_v1.json")
DEFAULT_APPROVAL = Path("benchmarks/memory_quality_review_v1.json")


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_json(path: str | Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f"cannot read {label}") from None
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _revision() -> str | None:
    configured = os.getenv("GITHUB_SHA", "").strip()
    if configured:
        return configured
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False, capture_output=True, text=True, timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _dataset_summary(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    privacy = data.get("privacy_screening")
    approval = data.get("dataset_approval")
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "name": str(data.get("name", path.stem)),
        "provenance": data.get("provenance", "unspecified"),
        "annotation_status": data.get("annotation_status", "unspecified"),
        "privacy_status": privacy.get("status") if isinstance(privacy, dict) else None,
        "dataset_approval_status": approval.get("status") if isinstance(approval, dict) else None,
    }


def _validated_case_ids(cases: list[Any], label: str) -> list[str]:
    """Return complete ordered case IDs, rejecting missing or duplicate identities."""
    identifiers: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f"every {label} case must be an object")
        identifier = case.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"every {label} case requires a non-empty id")
        identifiers.append(identifier)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{label} case IDs must be unique")
    return identifiers


def create_quality_review_approval(
    *,
    retrieval_dataset: str | Path = DEFAULT_RETRIEVAL_DATASET,
    contradiction_dataset: str | Path = DEFAULT_CONTRADICTION_DATASET,
    extraction_dataset: str | Path = DEFAULT_EXTRACTION_DATASET,
    approval_path: str | Path = DEFAULT_APPROVAL,
    reviewer: str,
    contradiction_labels_reviewed: bool,
    extraction_labels_reviewed: bool,
) -> dict[str, Any]:
    """Create a write-once attestation bound to exact benchmark file hashes."""
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewer identity is required")
    if not contradiction_labels_reviewed or not extraction_labels_reviewed:
        raise ValueError("both contradiction and extraction labels must be explicitly reviewed")

    _read_json(retrieval_dataset, "retrieval dataset")
    contradictions = _read_json(contradiction_dataset, "contradiction dataset")
    extraction = _read_json(extraction_dataset, "extraction dataset")
    contradiction_cases = contradictions.get("cases")
    extraction_cases = extraction.get("cases")
    if not isinstance(contradiction_cases, list) or not contradiction_cases:
        raise ValueError("contradiction dataset must contain cases")
    if not isinstance(extraction_cases, list) or not extraction_cases:
        raise ValueError("extraction dataset must contain cases")
    contradiction_ids = _validated_case_ids(contradiction_cases, "contradiction")
    extraction_ids = _validated_case_ids(extraction_cases, "extraction")
    for case in contradiction_cases:
        if not isinstance(case.get("expected_conflict"), bool):
            raise ValueError("every contradiction case must have a boolean expected_conflict label")
    for case in extraction_cases:
        if not isinstance(case.get("expected"), list):
            raise ValueError("every extraction case must have an expected claims list")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "reviewer": reviewer.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "label_reviews": {
            "contradiction": {
                "status": "approved",
                "case_ids": contradiction_ids,
            },
            "extraction": {
                "status": "approved",
                "case_ids": extraction_ids,
            },
        },
        "datasets": {
            "retrieval": {"path": str(retrieval_dataset), "sha256": _sha256(retrieval_dataset)},
            "contradiction": {"path": str(contradiction_dataset), "sha256": _sha256(contradiction_dataset)},
            "extraction": {"path": str(extraction_dataset), "sha256": _sha256(extraction_dataset)},
        },
        "note": (
            "Human attestation that every expected contradiction label and every "
            "expected extraction claim was inspected against its source case."
        ),
    }
    manifest["integrity"] = {
        "algorithm": "sha256",
        "scope": "canonical-json-excluding-integrity",
        "digest": hashlib.sha256(_canonical_bytes(manifest)).hexdigest(),
    }

    destination = Path(approval_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError:
        raise ValueError(
            f"review approval is write-once and already exists: {destination}; "
            "choose a new versioned approval path after re-review"
        ) from None
    return manifest


def assess_quality_review_approval(
    approval_path: str | Path,
    *,
    retrieval_dataset: str | Path,
    contradiction_dataset: str | Path,
    extraction_dataset: str | Path,
) -> dict[str, Any]:
    """Validate the human attestation, its integrity, and all bound source hashes."""
    path = Path(approval_path)
    if not path.is_file():
        return {
            "status": "missing",
            "validated": False,
            "blocking_reasons": [f"human label-review approval is missing: {path}"],
        }
    try:
        manifest = _read_json(path, "quality review approval")
    except ValueError as exc:
        return {"status": "invalid", "validated": False, "blocking_reasons": [str(exc)]}

    blockers: list[str] = []
    if manifest.get("schema_version") != 1:
        blockers.append("quality review approval has an unsupported schema version")
    if not isinstance(manifest.get("reviewer"), str) or not manifest.get("reviewer", "").strip():
        blockers.append("quality review approval lacks reviewer identity")
    reviewed_at = manifest.get("reviewed_at")
    if not isinstance(reviewed_at, str):
        blockers.append("quality review approval lacks a review timestamp")
    else:
        try:
            parsed_reviewed_at = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            if parsed_reviewed_at.tzinfo is None or parsed_reviewed_at.utcoffset() is None:
                raise ValueError("review timestamp must include a timezone")
        except ValueError:
            blockers.append("quality review approval timestamp is invalid")

    label_reviews = manifest.get("label_reviews")
    for name in ("contradiction", "extraction"):
        item = label_reviews.get(name) if isinstance(label_reviews, dict) else None
        if not isinstance(item, dict) or item.get("status") != "approved" or not item.get("case_ids"):
            blockers.append(f"{name} labels are not approved in the review manifest")

    integrity = manifest.get("integrity")
    payload = dict(manifest)
    payload.pop("integrity", None)
    expected_digest = integrity.get("digest") if isinstance(integrity, dict) else None
    if (
        not isinstance(integrity, dict)
        or integrity.get("algorithm") != "sha256"
        or integrity.get("scope") != "canonical-json-excluding-integrity"
        or not isinstance(expected_digest, str)
        or hashlib.sha256(_canonical_bytes(payload)).hexdigest() != expected_digest
    ):
        blockers.append("quality review approval integrity check failed")

    expected_files = {
        "retrieval": Path(retrieval_dataset),
        "contradiction": Path(contradiction_dataset),
        "extraction": Path(extraction_dataset),
    }
    recorded_files = manifest.get("datasets")
    for name, source in expected_files.items():
        recorded = recorded_files.get(name) if isinstance(recorded_files, dict) else None
        try:
            actual_hash = _sha256(source)
        except OSError:
            actual_hash = None
        if not isinstance(recorded, dict) or recorded.get("sha256") != actual_hash:
            blockers.append(f"{name} dataset changed or does not match the reviewed file hash")
            continue
        if name in {"contradiction", "extraction"}:
            try:
                source_data = _read_json(source, f"{name} dataset")
                cases = source_data.get("cases")
                if not isinstance(cases, list) or not cases:
                    raise ValueError("dataset has no cases")
                expected_ids = _validated_case_ids(cases, name)
            except ValueError:
                blockers.append(f"{name} dataset case identities are invalid")
                continue
            review_item = label_reviews.get(name) if isinstance(label_reviews, dict) else None
            reviewed_ids = review_item.get("case_ids") if isinstance(review_item, dict) else None
            if reviewed_ids != expected_ids:
                blockers.append(
                    f"{name} review does not cover the exact ordered case IDs in the dataset"
                )

    return {
        "status": "validated" if not blockers else "invalid",
        "validated": not blockers,
        "reviewer": manifest.get("reviewer"),
        "reviewed_at": reviewed_at,
        "blocking_reasons": blockers,
        "datasets": manifest.get("datasets", {}),
    }


def _metric_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    observed: Any,
    threshold: Any,
    operator: str = ">=",
) -> None:
    valid_observed = (
        isinstance(observed, (int, float))
        and not isinstance(observed, bool)
        and math.isfinite(float(observed))
    )
    valid_threshold = (
        isinstance(threshold, (int, float))
        and not isinstance(threshold, bool)
        and math.isfinite(float(threshold))
    )
    passed = bool(valid_observed and valid_threshold) and (
        float(observed) >= float(threshold)
        if operator == ">="
        else float(observed) <= float(threshold)
    )
    checks.append({
        "name": name,
        "observed": observed,
        "operator": operator,
        "threshold": threshold,
        "passed": passed,
    })


def _threshold_checks(
    thresholds: dict[str, Any],
    profile: str,
    retrieval: dict[str, Any],
    contradiction: dict[str, Any],
    extraction: dict[str, Any],
    extraction_dataset: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    configured = thresholds.get(profile)
    if not isinstance(configured, dict):
        raise ValueError(f"threshold configuration requires a {profile} object")
    checks: list[dict[str, Any]] = []
    lexical = retrieval.get("lexical") if isinstance(retrieval.get("lexical"), dict) else {}
    for metric, minimum in configured.get("retrieval", {}).items():
        _metric_check(
            checks, name=f"retrieval.lexical.{metric}",
            observed=lexical.get(metric), threshold=minimum,
        )
    for metric, minimum in configured.get("contradiction", {}).items():
        _metric_check(
            checks, name=f"contradiction.{metric}",
            observed=contradiction.get(metric), threshold=minimum,
        )

    if profile == "release":
        contradiction_cases = contradiction.get("cases", [])
        contradiction_cases = contradiction_cases if isinstance(contradiction_cases, list) else []
        extraction_metrics = (
            extraction.get("metrics") if isinstance(extraction.get("metrics"), dict) else {}
        )
        calibration = extraction_metrics.get("confidence_calibration")
        calibration = calibration if isinstance(calibration, dict) else {}
        expected_claim_count = sum(
            len(case.get("expected", []))
            for case in (extraction_dataset or {}).get("cases", [])
            if isinstance(case, dict) and isinstance(case.get("expected"), list)
        )
        extraction_cases = (extraction_dataset or {}).get("cases", [])
        extraction_cases = extraction_cases if isinstance(extraction_cases, list) else []
        sample_sizes = {
            "retrieval_queries": lexical.get("query_count"),
            "contradiction_cases": contradiction.get("case_count"),
            "contradiction_positive_cases": sum(
                case.get("expected_conflict") is True for case in contradiction_cases
                if isinstance(case, dict)
            ),
            "contradiction_negative_cases": sum(
                case.get("expected_conflict") is False for case in contradiction_cases
                if isinstance(case, dict)
            ),
            "extraction_cases": len(extraction_cases),
            "extraction_expected_claims": expected_claim_count,
            "extraction_confidence_samples": calibration.get("sample_count"),
        }
        for sample_name, minimum in configured.get("minimum_sample_sizes", {}).items():
            _metric_check(
                checks,
                name=f"sample_size.{sample_name}",
                observed=sample_sizes.get(sample_name),
                threshold=minimum,
            )

        hybrid = retrieval.get("hybrid") if isinstance(retrieval.get("hybrid"), dict) else {}
        for metric, minimum in configured.get("hybrid", {}).items():
            if metric == "minimum_ndcg_delta":
                deltas = retrieval.get("deltas")
                observed = deltas.get("ndcg_at_k") if isinstance(deltas, dict) else None
                check_name = "retrieval.hybrid.ndcg_delta"
            else:
                observed = hybrid.get(metric)
                check_name = f"retrieval.hybrid.{metric}"
            _metric_check(checks, name=check_name, observed=observed, threshold=minimum)

        for metric, minimum in configured.get("extraction", {}).items():
            _metric_check(
                checks, name=f"extraction.{metric}",
                observed=extraction_metrics.get(metric), threshold=minimum,
            )
        for metric, maximum in configured.get("calibration", {}).items():
            _metric_check(
                checks, name=f"extraction.confidence_calibration.{metric}",
                observed=calibration.get(metric), threshold=maximum, operator="<=",
            )
    return checks


def build_memory_evaluation_report(
    *,
    retrieval_dataset: str | Path = DEFAULT_RETRIEVAL_DATASET,
    contradiction_dataset: str | Path = DEFAULT_CONTRADICTION_DATASET,
    extraction_dataset: str | Path = DEFAULT_EXTRACTION_DATASET,
    thresholds_path: str | Path = DEFAULT_THRESHOLDS,
    approval_path: str | Path = DEFAULT_APPROVAL,
    embedder: Any | None = None,
    extraction_result: dict[str, Any] | None = None,
    k: int = 3,
    profile: str = "ci",
    revision: str | None = None,
) -> dict[str, Any]:
    """Run offline suites and evaluate CI or strict release requirements."""
    if profile not in {"ci", "release"}:
        raise ValueError("profile must be 'ci' or 'release'")
    if k < 1:
        raise ValueError("k must be at least 1")

    retrieval_path = Path(retrieval_dataset)
    contradiction_path = Path(contradiction_dataset)
    extraction_path = Path(extraction_dataset)
    threshold_path = Path(thresholds_path)
    retrieval_data = _read_json(retrieval_path, "retrieval dataset")
    contradiction_data = _read_json(contradiction_path, "contradiction dataset")
    extraction_data = _read_json(extraction_path, "extraction dataset")
    threshold_data = _read_json(threshold_path, "memory release thresholds")

    retrieval = run_retrieval_comparison(retrieval_path, embedder=embedder, k=k)
    contradiction = run_contradiction_benchmark(contradiction_path)
    extraction = extraction_result or {
        "status": "not_run", "reason": "live extraction was not requested",
    }
    summaries = {
        "retrieval": _dataset_summary(retrieval_path, retrieval_data),
        "contradiction": _dataset_summary(contradiction_path, contradiction_data),
        "extraction": _dataset_summary(extraction_path, extraction_data),
        "thresholds": {
            "path": str(threshold_path), "sha256": _sha256(threshold_path),
            "name": "memory_release_thresholds",
        },
    }

    retrieval_reviewed = assess_dataset_review(retrieval_data)
    approval = assess_quality_review_approval(
        approval_path,
        retrieval_dataset=retrieval_path,
        contradiction_dataset=contradiction_path,
        extraction_dataset=extraction_path,
    )

    release_blockers: list[str] = []
    if not retrieval_reviewed.get("validated"):
        release_blockers.extend(
            f"retrieval review: {reason}"
            for reason in retrieval_reviewed.get("blocking_reasons", [])
        )
    if retrieval.get("comparison_status") != "compared":
        release_blockers.append(
            "a real local embedding run is required; lexical-only is not release evidence"
        )
    if not approval.get("validated"):
        release_blockers.extend(
            f"label review: {reason}" for reason in approval.get("blocking_reasons", [])
        )
    if extraction.get("status") != "completed":
        release_blockers.append("a successful live memory extraction benchmark is required")

    ci_checks = _threshold_checks(
        threshold_data, "ci", retrieval, contradiction, extraction,
    )
    release_checks = _threshold_checks(
        threshold_data, "release", retrieval, contradiction, extraction,
        extraction_dataset=extraction_data,
    )
    release_blockers.extend(
        f"threshold failed: {check['name']} observed {check['observed']!r} "
        f"{check['operator']} {check['threshold']!r}"
        for check in release_checks if not check["passed"]
    )
    release_ready = not release_blockers
    active_checks = ci_checks if profile == "ci" else release_checks
    passed = all(check["passed"] for check in active_checks) and (
        profile != "release" or release_ready
    )

    return {
        "schema_version": 1,
        "profile": profile,
        "status": "passed" if passed else "blocked",
        "passed": passed,
        "release_ready": release_ready,
        "release_readiness": {
            "ready": release_ready,
            "blocking_reasons": release_blockers,
            "retrieval_review": retrieval_reviewed,
            "human_label_review": approval,
        },
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reproducibility": {
            "repository_revision": revision or _revision(),
            "python_version": platform.python_version(),
            "thresholds_sha256": summaries["thresholds"]["sha256"],
            "embedding_model": (
                getattr(embedder, "model_id", None)
                if retrieval.get("comparison_status") == "compared" else None
            ),
            "extraction_model": os.getenv("KALDRAX_MODEL") or None,
        },
        "datasets": summaries,
        "retrieval_comparison": retrieval,
        "contradiction": contradiction,
        "extraction": extraction,
        "checks": active_checks,
        "ci_checks": ci_checks,
        "release_checks": release_checks,
    }


def render_memory_evaluation_markdown(report: dict[str, Any]) -> str:
    """Render a compact operator-facing view of the full JSON evidence report."""
    lines = [
        "# KALDRAX Memory Evaluation",
        "",
        f"**Profile:** {report.get('profile', 'unknown')}",
        f"**Result:** {str(report.get('status', 'unknown')).upper()}",
        f"**Release ready:** {'yes' if report.get('release_ready') else 'no'}",
        f"**Repository revision:** {report.get('reproducibility', {}).get('repository_revision') or 'unavailable'}",
        "",
        "## Dataset provenance",
        "",
        "| Dataset | SHA-256 | Provenance | Annotation | Privacy |",
        "|---|---|---|---|---|",
    ]
    for name in ("retrieval", "contradiction", "extraction"):
        item = report.get("datasets", {}).get(name, {})
        lines.append(
            f"| {name} | `{item.get('sha256', 'missing')}` | "
            f"{item.get('provenance', 'unspecified')} | "
            f"{item.get('annotation_status', 'unspecified')} | "
            f"{item.get('privacy_status') or 'not recorded'} |"
        )

    retrieval = report.get("retrieval_comparison", {})
    lexical = retrieval.get("lexical", {}) if isinstance(retrieval, dict) else {}
    hybrid = retrieval.get("hybrid", {}) if isinstance(retrieval, dict) else {}
    lines.extend([
        "",
        "## Retrieval",
        "",
        f"Comparison status: **{retrieval.get('comparison_status', 'unavailable')}**",
        "",
        "| Metric | Lexical | Hybrid |",
        "|---|---:|---:|",
    ])
    for metric in (
        "recall_at_k", "precision_at_k", "ndcg_at_k",
        "mean_reciprocal_rank", "top1_accuracy",
    ):
        left = lexical.get(metric, "not measured")
        right = hybrid.get(metric, "not measured") if isinstance(hybrid, dict) else "not measured"
        lines.append(f"| {metric} | {left} | {right} |")

    contradiction = report.get("contradiction", {})
    lines.extend([
        "",
        "## Contradiction detection",
        "",
        f"Cases: {contradiction.get('case_count', 0)} · "
        f"Precision: {contradiction.get('precision')} · "
        f"Recall: {contradiction.get('recall')} · F1: {contradiction.get('f1')}",
        "",
        "## Extraction and confidence calibration",
        "",
    ])
    extraction = report.get("extraction", {})
    metrics = extraction.get("metrics", {}) if isinstance(extraction, dict) else {}
    lines.append(f"Live run status: **{extraction.get('status', 'not_run')}**")
    if metrics:
        lines.append(
            f"Cases: {metrics.get('case_count')} · Precision: {metrics.get('precision')} · "
            f"Recall: {metrics.get('recall')} · F1: {metrics.get('f1')} · "
            f"Evidence validity: {metrics.get('evidence_valid_rate')}"
        )
        calibration = metrics.get("confidence_calibration", {})
        lines.append(
            f"Brier: {calibration.get('brier_score')} · "
            f"Expected calibration error: {calibration.get('expected_calibration_error')}"
        )

    lines.extend([
        "",
        "## Active threshold checks",
        "",
        "| Check | Observed | Requirement | Result |",
        "|---|---:|---:|---|",
    ])
    for check in report.get("checks", []):
        result = "PASS" if check.get("passed") else "FAIL"
        lines.append(
            f"| {check.get('name')} | {check.get('observed')} | "
            f"{check.get('operator')} {check.get('threshold')} | {result} |"
        )

    blockers = report.get("release_readiness", {}).get("blocking_reasons", [])
    lines.extend(["", "## Release blockers", ""])
    if blockers:
        lines.extend(f"- {reason}" for reason in blockers)
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)


def write_memory_evaluation_report(
    report: dict[str, Any],
    *,
    json_path: str | Path,
    markdown_path: str | Path | None = None,
) -> None:
    """Write JSON evidence and an optional Markdown summary."""
    destination = Path(json_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    if markdown_path is not None:
        markdown_destination = Path(markdown_path)
        markdown_destination.parent.mkdir(parents=True, exist_ok=True)
        markdown_destination.write_text(
            render_memory_evaluation_markdown(report), encoding="utf-8",
        )
