"""Reproducible retrieval metrics for a small local memory corpus."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingProvider
from .memory import MemoryRecord, MemoryType, SQLiteMemoryStore


def run_retrieval_benchmark(
    dataset_path: str | Path, *, embedder: EmbeddingProvider | None = None, k: int = 3,
) -> dict[str, Any]:
    if k < 1:
        raise ValueError("k must be at least 1")
    try:
        dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read retrieval benchmark dataset: {type(exc).__name__}") from None
    if not isinstance(dataset, dict) or not isinstance(dataset.get("memories"), list) or not isinstance(dataset.get("queries"), list):
        raise ValueError("benchmark dataset requires memories and queries arrays")

    with tempfile.TemporaryDirectory(prefix="kaldrax-memory-benchmark-") as directory:
        store = SQLiteMemoryStore(Path(directory) / "benchmark.sqlite3", embedder=embedder)
        try:
            for item in dataset["memories"]:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("content"), str):
                    raise ValueError("each benchmark memory requires string id and content")
                record = MemoryRecord.create(
                    project_id="benchmark",
                    memory_type=MemoryType.SEMANTIC,
                    content=item["content"],
                    summary=str(item.get("summary", "")),
                    tags=tuple(item.get("tags", [])) + (f"benchmark-id:{item['id']}",),
                    metadata={"benchmark_fixture": True},
                    expires_at=None,
                )
                store.save(record)

            case_results: list[dict[str, Any]] = []
            recall_values: list[float] = []
            reciprocal_ranks: list[float] = []
            top1_values: list[float] = []
            for case in dataset["queries"]:
                if not isinstance(case, dict) or not isinstance(case.get("query"), str) or not isinstance(case.get("relevant"), list):
                    raise ValueError("each benchmark query requires a query string and relevant ID list")
                relevant = set(case["relevant"])
                if not relevant:
                    raise ValueError("benchmark query relevant IDs cannot be empty")
                matches = store.search(case["query"], project_id="benchmark", limit=k)
                ranked = [
                    next((tag.split(":", 1)[1] for tag in match.record.tags if tag.startswith("benchmark-id:")), "")
                    for match in matches
                ]
                hits = [identifier for identifier in ranked if identifier in relevant]
                recall = len(set(hits)) / len(relevant)
                reciprocal_rank = next((1.0 / index for index, identifier in enumerate(ranked, 1) if identifier in relevant), 0.0)
                top1 = 1.0 if ranked and ranked[0] in relevant else 0.0
                recall_values.append(recall)
                reciprocal_ranks.append(reciprocal_rank)
                top1_values.append(top1)
                case_results.append({
                    "query": case["query"],
                    "relevant": sorted(relevant),
                    "ranked": ranked,
                    "recall_at_k": round(recall, 4),
                    "reciprocal_rank": round(reciprocal_rank, 4),
                })
            count = len(case_results)
            return {
                "dataset": str(dataset_path),
                "memory_count": len(dataset["memories"]),
                "query_count": count,
                "k": k,
                "retrieval_mode": "hybrid" if embedder is not None else "lexical",
                "recall_at_k": round(sum(recall_values) / count, 4) if count else 0.0,
                "mean_reciprocal_rank": round(sum(reciprocal_ranks) / count, 4) if count else 0.0,
                "top1_accuracy": round(sum(top1_values) / count, 4) if count else 0.0,
                "cases": case_results,
            }
        finally:
            store.close()
