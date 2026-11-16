"""Reproducible retrieval metrics for annotated engineering-memory corpora."""
from __future__ import annotations

import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingProvider
from .memory import MemoryRecord, MemoryType, SQLiteMemoryStore


def _ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(
        (1.0 / math.log2(rank + 1))
        for rank, identifier in enumerate(ranked[:k], 1)
        if identifier in relevant
    )
    ideal_hits = min(len(relevant), k)
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_retrieval_benchmark(
    dataset_path: str | Path, *, embedder: EmbeddingProvider | None = None, k: int = 3,
) -> dict[str, Any]:
    """Measure retrieval without reading or mutating the operator's memory DB.

    Dataset IDs are unique and every relevance judgment must reference an
    included memory. Query categories are used for per-workload breakdowns.
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    try:
        dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read retrieval benchmark dataset: {type(exc).__name__}") from None
    if (
        not isinstance(dataset, dict)
        or not isinstance(dataset.get("memories"), list)
        or not isinstance(dataset.get("queries"), list)
    ):
        raise ValueError("benchmark dataset requires memories and queries arrays")
    if not dataset["memories"] or not dataset["queries"]:
        raise ValueError("benchmark dataset must contain memories and queries")

    memory_ids: set[str] = set()
    for item in dataset["memories"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str) or not item["id"].strip()
            or not isinstance(item.get("content"), str) or not item["content"].strip()
        ):
            raise ValueError("each benchmark memory requires non-empty string id and content")
        if item["id"] in memory_ids:
            raise ValueError(f"duplicate benchmark memory id: {item['id']}")
        memory_ids.add(item["id"])

    for case in dataset["queries"]:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("query"), str) or not case["query"].strip()
            or not isinstance(case.get("relevant"), list)
        ):
            raise ValueError("each benchmark query requires a non-empty query and relevant ID list")
        relevant = case["relevant"]
        if not relevant or any(not isinstance(identifier, str) for identifier in relevant):
            raise ValueError("benchmark query relevant IDs cannot be empty and must be strings")
        unknown = set(relevant) - memory_ids
        if unknown:
            raise ValueError(f"benchmark query references unknown memory IDs: {sorted(unknown)}")

    with tempfile.TemporaryDirectory(prefix="kaldrax-memory-benchmark-") as directory:
        store = SQLiteMemoryStore(Path(directory) / "benchmark.sqlite3")
        try:
            for item in dataset["memories"]:
                identifier = item["id"]
                record = MemoryRecord.create(
                    project_id="benchmark",
                    memory_type=MemoryType.SEMANTIC,
                    content=item["content"],
                    summary=str(item.get("summary", "")),
                    tags=tuple(item.get("tags", [])),
                    metadata={
                        "benchmark_fixture": True,
                        "benchmark_id": identifier,
                        "category": str(item.get("category", "uncategorized")),
                        "source": item.get("source"),
                    },
                    expires_at=None,
                )
                store.save(record)

            active_embedder = False
            embedding_error: str | None = None
            if embedder is not None:
                # Index the fixture in batches instead of one provider request
                # per record; this keeps local model overhead predictable.
                store.embedder = embedder
                try:
                    store.reindex_embeddings(project_id="benchmark", batch_size=32)
                    active_embedder = True
                except Exception as exc:
                    # A configured-but-unavailable local model must not make
                    # the offline regression benchmark unusable.
                    store.embedder = None
                    embedding_error = type(exc).__name__

            case_results: list[dict[str, Any]] = []
            by_category: dict[str, list[dict[str, float]]] = defaultdict(list)
            recall_values: list[float] = []
            precision_values: list[float] = []
            ndcg_values: list[float] = []
            reciprocal_ranks: list[float] = []
            top1_values: list[float] = []
            for case in dataset["queries"]:
                relevant = set(case["relevant"])
                matches = store.search(case["query"], project_id="benchmark", limit=k)
                ranked = [
                    str(match.record.metadata.get("benchmark_id", ""))
                    for match in matches
                ]
                hits = [identifier for identifier in ranked if identifier in relevant]
                recall = len(set(hits)) / len(relevant)
                precision = len(set(hits)) / k
                ndcg = _ndcg_at_k(ranked, relevant, k)
                reciprocal_rank = next(
                    (1.0 / index for index, identifier in enumerate(ranked, 1) if identifier in relevant),
                    0.0,
                )
                top1 = 1.0 if ranked and ranked[0] in relevant else 0.0
                category = str(case.get("category", "uncategorized"))
                recall_values.append(recall)
                precision_values.append(precision)
                ndcg_values.append(ndcg)
                reciprocal_ranks.append(reciprocal_rank)
                top1_values.append(top1)
                metrics = {
                    "recall_at_k": recall,
                    "precision_at_k": precision,
                    "ndcg_at_k": ndcg,
                    "reciprocal_rank": reciprocal_rank,
                    "top1_accuracy": top1,
                }
                by_category[category].append(metrics)
                case_results.append({
                    "id": str(case.get("id", f"query-{len(case_results) + 1}")),
                    "category": category,
                    "query": case["query"],
                    "annotation_status": str(case.get("annotation_status", dataset.get("annotation_status", "unspecified"))),
                    "annotation_rationale": str(case.get("rationale", "")),
                    "relevant": sorted(relevant),
                    "ranked": ranked,
                    "recall_at_k": round(recall, 4),
                    "precision_at_k": round(precision, 4),
                    "ndcg_at_k": round(ndcg, 4),
                    "reciprocal_rank": round(reciprocal_rank, 4),
                    "top1_accuracy": round(top1, 4),
                })
            count = len(case_results)
            return {
                "dataset": str(dataset_path),
                "dataset_name": str(dataset.get("name", Path(dataset_path).stem)),
                "dataset_provenance": str(dataset.get("provenance", "unspecified")),
                "source_repository": dataset.get("source_repository"),
                "source_revision": dataset.get("source_revision"),
                "annotation_status": str(dataset.get("annotation_status", "unspecified")),
                "privacy_screening_status": (
                    dataset.get("privacy_screening", {}).get("status")
                    if isinstance(dataset.get("privacy_screening"), dict) else None
                ),
                "memory_count": len(dataset["memories"]),
                "query_count": count,
                "categories": sorted(by_category),
                "k": k,
                "retrieval_mode": "hybrid" if active_embedder else "lexical",
                "embedding_model": getattr(embedder, "model_id", None) if active_embedder else None,
                "embedding_error": embedding_error,
                "recall_at_k": round(_mean(recall_values), 4),
                "precision_at_k": round(_mean(precision_values), 4),
                "ndcg_at_k": round(_mean(ndcg_values), 4),
                "mean_reciprocal_rank": round(_mean(reciprocal_ranks), 4),
                "top1_accuracy": round(_mean(top1_values), 4),
                "by_category": {
                    category: {
                        metric: round(_mean([case[metric] for case in cases]), 4)
                        for metric in (
                            "recall_at_k", "precision_at_k", "ndcg_at_k",
                            "reciprocal_rank", "top1_accuracy",
                        )
                    }
                    for category, cases in sorted(by_category.items())
                },
                "cases": case_results,
            }
        finally:
            store.close()
