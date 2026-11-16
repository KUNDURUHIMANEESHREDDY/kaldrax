"""KALDRAX command-line interface."""
import argparse
import json
import os
from pathlib import Path

from .embeddings import OllamaEmbeddingProvider
from .engine import RecursiveEngine
from .evaluation import LLMEvaluator
from .execution import ExampleExecutor, LLMExecutor
from .llm import OpenAICompatibleClient
from .memory import MemoryReviewConflict, SQLiteMemoryStore
from .memory_benchmarks import run_retrieval_benchmark
from .memory_intelligence import LLMMemoryExtractor
from .models import Task


def _memory_path(args: argparse.Namespace) -> Path:
    return args.memory_db or Path(".kaldrax/memory.sqlite3")


def _embedding_provider() -> OllamaEmbeddingProvider | None:
    model = os.getenv("KALDRAX_EMBEDDING_MODEL", "").strip()
    if not model:
        return None
    return OllamaEmbeddingProvider(
        model=model,
        base_url=os.getenv("KALDRAX_OLLAMA_URL", "http://127.0.0.1:11434"),
        timeout=float(os.getenv("KALDRAX_EMBEDDING_TIMEOUT_SECONDS", "30")),
    )


def _memory_store(path: Path) -> SQLiteMemoryStore:
    return SQLiteMemoryStore(path, embedder=_embedding_provider())


def _run_llm(args: argparse.Namespace) -> int:
    api_key = os.getenv("KALDRAX_API_KEY", "")
    executor_model = os.getenv("KALDRAX_MODEL", "")
    evaluator_model = os.getenv("KALDRAX_EVALUATOR_MODEL", "")
    if not api_key:
        raise ValueError("KALDRAX_API_KEY is required for 'kaldrax run'")
    if not executor_model:
        raise ValueError("KALDRAX_MODEL is required for 'kaldrax run'")
    if not evaluator_model:
        raise ValueError("KALDRAX_EVALUATOR_MODEL is required for 'kaldrax run'")
    if executor_model.casefold() == evaluator_model.casefold():
        raise ValueError("KALDRAX_EVALUATOR_MODEL must differ from KALDRAX_MODEL")

    base_url = os.getenv("KALDRAX_BASE_URL", "https://api.openai.com/v1")
    timeout = float(os.getenv("KALDRAX_TIMEOUT_SECONDS", "60"))
    max_tokens = int(os.getenv("KALDRAX_MAX_TOKENS", "2048"))
    token_parameter = os.getenv("KALDRAX_TOKEN_PARAMETER", "max_completion_tokens")
    executor_client = OpenAICompatibleClient(
        api_key=api_key, model=executor_model, base_url=base_url,
        timeout=timeout, max_tokens=max_tokens, token_parameter=token_parameter,
    )
    evaluator_client = OpenAICompatibleClient(
        api_key=api_key, model=evaluator_model, base_url=base_url,
        timeout=timeout, max_tokens=max_tokens, token_parameter=token_parameter,
    )
    task = Task(
        args.objective, tuple(args.criterion), args.max_iterations, project_id=args.project,
    )
    memory = _memory_store(_memory_path(args))
    try:
        report = RecursiveEngine(
            LLMExecutor(executor_client),
            evaluator=LLMEvaluator(evaluator_client),
            artifact_dir=args.artifacts,
            memory_store=memory,
            agent_id=args.agent,
            knowledge_extractor=LLMMemoryExtractor(executor_client),
            memory_limit=args.memory_limit,
        ).run(task)
    finally:
        memory.close()
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.status.value == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="kaldrax", description="KALDRAX engineering harness")
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="run the offline recursive-loop demonstration")
    demo.add_argument("--artifacts", type=Path, default=Path(".kaldrax/runs"))
    demo.add_argument("--memory-db", type=Path, default=None)
    demo.add_argument("--project", default="default")

    run = commands.add_parser("run", help="run an LLM-backed task with a separate model evaluator")
    run.add_argument("--objective", required=True)
    run.add_argument("--criterion", action="append", required=True, help="acceptance criterion; repeat for multiple")
    run.add_argument("--max-iterations", type=int, default=3)
    run.add_argument("--artifacts", type=Path, default=Path(".kaldrax/runs"))
    run.add_argument("--memory-db", type=Path, default=None)
    run.add_argument("--project", default="default", help="memory isolation key for this project")
    run.add_argument("--agent", default=None, help="optional agent namespace; project-shared memory remains visible")
    run.add_argument("--memory-limit", type=int, default=5)

    memory = commands.add_parser("memory", help="inspect or maintain persistent project memory")
    memory_actions = memory.add_subparsers(dest="memory_action", required=True)

    search = memory_actions.add_parser("search", help="retrieve approved memories in one project")
    search.add_argument("--query", required=True)
    search.add_argument("--project", default="default")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--agent", default=None)
    search.add_argument("--include-pending", action="store_true")
    search.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    review = memory_actions.add_parser("review", help="approve or reject a pending semantic memory")
    review.add_argument("--id", required=True)
    review.add_argument("--decision", required=True, choices=("approve", "reject"))
    review.add_argument("--reviewer", default="local-user")
    review.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    conflicts = memory_actions.add_parser("conflicts", help="detect and list possible semantic contradictions")
    conflicts.add_argument("--project", required=True)
    conflicts.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    resolve = memory_actions.add_parser("resolve-conflict", help="keep one side of a reviewed contradiction")
    resolve.add_argument("--conflict-id", required=True)
    resolve.add_argument("--keep-memory-id", required=True)
    resolve.add_argument("--reviewer", default="local-user")
    resolve.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    expire = memory_actions.add_parser("expire", help="mark expired records inactive")
    expire.add_argument("--project", default=None)
    expire.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    reindex = memory_actions.add_parser("reindex", help="create or refresh local embeddings")
    reindex.add_argument("--project", default=None)
    reindex.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    consolidate = memory_actions.add_parser("consolidate", help="merge exact duplicate memories")
    consolidate.add_argument("--project", default=None)
    consolidate.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    benchmark = memory_actions.add_parser("benchmark", help="measure retrieval quality on the bundled benchmark corpus")
    benchmark.add_argument("--dataset", type=Path, default=Path("benchmarks/memory_retrieval.json"))
    benchmark.add_argument("--k", type=int, default=3)

    args = parser.parse_args()
    if args.command == "demo":
        task = Task(
            "Produce a minimal project delivery summary",
            ("Scope", "Verification", "Known limitations"),
            project_id=args.project,
        )
        memory = _memory_store(_memory_path(args))
        try:
            report = RecursiveEngine(
                ExampleExecutor(), artifact_dir=args.artifacts, memory_store=memory,
            ).run(task)
        finally:
            memory.close()
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.status.value == "passed" else 1

    if args.command == "run":
        try:
            return _run_llm(args)
        except (ValueError, TypeError) as exc:
            parser.error(str(exc))

    if args.command == "memory":
        if args.memory_action == "benchmark":
            try:
                result = run_retrieval_benchmark(
                    args.dataset, embedder=_embedding_provider(), k=args.k,
                )
            except (ValueError, TypeError) as exc:
                parser.error(str(exc))
            print(json.dumps(result, indent=2))
            return 0

        memory_store = _memory_store(args.memory_db)
        try:
            if args.memory_action == "search":
                matches = memory_store.search(
                    args.query, project_id=args.project, limit=args.limit,
                    agent_id=args.agent, include_pending=args.include_pending,
                )
                print(json.dumps([{
                    "id": match.record.id,
                    "type": match.record.memory_type.value,
                    "status": match.record.status.value,
                    "confidence": match.record.confidence,
                    "expires_at": match.record.expires_at,
                    "score": round(match.score, 5),
                    "lexical_score": round(match.lexical_score, 5),
                    "semantic_score": None if match.semantic_score is None else round(match.semantic_score, 5),
                    "freshness_score": round(match.freshness_score, 5),
                    "retrieval_method": match.retrieval_method,
                    "summary": match.record.summary,
                    "content": match.record.content,
                    "source_run_id": match.record.source_run_id,
                    "source_event_sequences": list(match.record.source_event_sequences),
                    "agent_id": match.record.agent_id,
                    "tags": list(match.record.tags),
                    "metadata": match.record.metadata,
                } for match in matches], indent=2))
                return 0

            if args.memory_action == "review":
                try:
                    record = memory_store.review(args.id, args.decision, args.reviewer)
                except MemoryReviewConflict as exc:
                    print(json.dumps({"error": str(exc), "conflict_ids": exc.conflict_ids}, indent=2))
                    return 2
                print(json.dumps({
                    "id": record.id, "status": record.status.value,
                    "confidence": record.confidence, "verified_at": record.verified_at,
                    "expires_at": record.expires_at, "metadata": record.metadata,
                }, indent=2))
                return 0

            if args.memory_action == "conflicts":
                memory_store.detect_conflicts(args.project)
                print(json.dumps([{
                    "id": item.id, "left_memory_id": item.left_memory_id,
                    "right_memory_id": item.right_memory_id, "reason": item.reason,
                    "status": item.status, "created_at": item.created_at,
                } for item in memory_store.list_conflicts(args.project)], indent=2))
                return 0

            if args.memory_action == "resolve-conflict":
                item = memory_store.resolve_conflict(
                    args.conflict_id, args.keep_memory_id, args.reviewer,
                )
                print(json.dumps({
                    "id": item.id, "status": item.status,
                    "resolution": item.resolution,
                }, indent=2))
                return 0

            if args.memory_action == "expire":
                print(json.dumps({
                    "expired": memory_store.expire_stale(args.project),
                    "remaining": memory_store.count(project_id=args.project),
                }, indent=2))
                return 0

            if args.memory_action == "reindex":
                try:
                    updated = memory_store.reindex_embeddings(args.project)
                except (ValueError, RuntimeError) as exc:
                    parser.error(str(exc))
                print(json.dumps({"embeddings_updated": updated}, indent=2))
                return 0

            if args.memory_action == "consolidate":
                removed = memory_store.consolidate(args.project)
                print(json.dumps({
                    "duplicates_removed": removed,
                    "remaining": memory_store.count(project_id=args.project),
                }, indent=2))
                return 0
        finally:
            memory_store.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
