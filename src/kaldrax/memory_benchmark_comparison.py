"""Paired lexical-versus-hybrid retrieval benchmark comparisons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .embeddings import EmbeddingProvider
from .memory_benchmarks import run_retrieval_benchmark

_METRICS = (
    "recall_at_k",
    "precision_at_k",
    "ndcg_at_k",
    "mean_reciprocal_rank",
    "top1_accuracy",
)


def run_retrieval_comparison(
    dataset_path: str | Path,
    *,
    embedder: EmbeddingProvider | None = None,
    k: int = 3,
) -> dict[str, Any]:
    """Compare lexical and hybrid ranking on exactly the same judged queries.

    The lexical baseline always runs. Hybrid deltas are emitted only after
    embedding indexing and query-time embedding both succeed. If embeddings
    are absent or fail, the report says so rather than presenting a lexical
    fallback as an independent hybrid measurement.
    """
    lexical = run_retrieval_benchmark(dataset_path, k=k)
    base: dict[str, Any] = {
        "dataset": lexical["dataset"],
        "dataset_name": lexical["dataset_name"],
        "dataset_provenance": lexical["dataset_provenance"],
        "annotation_status": lexical.get("annotation_status", "unspecified"),
        "benchmark_validation": lexical.get("benchmark_validation"),
        "source_revision": lexical.get("source_revision"),
        "privacy_screening_status": lexical.get("privacy_screening_status"),
        "k": k,
        "comparison_status": "lexical_only",
        "lexical": lexical,
        "hybrid": None,
        "deltas": None,
        "by_category_delta": None,
        "paired_query_results": [],
        "interpretation": (
            "Hybrid deltas are descriptive paired differences on this dataset; "
            "they are not statistical significance or production guarantees."
        ),
    }
    if embedder is None:
        base["reason"] = "No local embedding provider is configured."
        return base

    hybrid = run_retrieval_benchmark(dataset_path, embedder=embedder, k=k)
    if hybrid["retrieval_mode"] != "hybrid":
        base["comparison_status"] = "embedding_unavailable"
        base["reason"] = "The embedding provider failed; no hybrid comparison was produced."
        base["embedding_error"] = hybrid.get("embedding_error") or "unknown"
        return base

    deltas = {
        metric: round(float(hybrid[metric]) - float(lexical[metric]), 4)
        for metric in _METRICS
    }
    lexical_cases = {case["id"]: case for case in lexical["cases"]}
    hybrid_cases = {case["id"]: case for case in hybrid["cases"]}
    paired: list[dict[str, Any]] = []
    for case_id, lexical_case in lexical_cases.items():
        hybrid_case = hybrid_cases[case_id]
        paired.append({
            "id": case_id,
            "category": lexical_case["category"],
            "lexical_ndcg_at_k": lexical_case["ndcg_at_k"],
            "hybrid_ndcg_at_k": hybrid_case["ndcg_at_k"],
            "ndcg_delta": round(
                float(hybrid_case["ndcg_at_k"]) - float(lexical_case["ndcg_at_k"]), 4
            ),
            "lexical_top1": lexical_case["top1_accuracy"],
            "hybrid_top1": hybrid_case["top1_accuracy"],
        })

    by_category_delta: dict[str, dict[str, float]] = {}
    for category in sorted(set(lexical["by_category"]) & set(hybrid["by_category"])):
        by_category_delta[category] = {
            metric: round(
                float(hybrid["by_category"][category][metric])
                - float(lexical["by_category"][category][metric]),
                4,
            )
            for metric in ("recall_at_k", "ndcg_at_k", "reciprocal_rank", "top1_accuracy")
        }

    ndcg_deltas = [float(case["ndcg_delta"]) for case in paired]
    base.update({
        "comparison_status": "compared",
        "hybrid": hybrid,
        "deltas": deltas,
        "by_category_delta": by_category_delta,
        "paired_query_results": paired,
        "paired_ndcg_outcomes": {
            "hybrid_better": sum(delta > 0 for delta in ndcg_deltas),
            "tie": sum(delta == 0 for delta in ndcg_deltas),
            "hybrid_worse": sum(delta < 0 for delta in ndcg_deltas),
        },
    })
    return base
