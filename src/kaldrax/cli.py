"""KALDRAX command-line interface."""
import argparse
import json
import os
from pathlib import Path

from .agents import MultiAgentCoordinator
from .benchmark import load_cases, run_benchmark
from .budgets import RunBudget
from .sandbox import SandboxRunner

from .embeddings import OllamaEmbeddingProvider
from .engine import RecursiveEngine
from .evaluation import CriteriaEvaluator, LLMEvaluator
from .execution import ExampleExecutor, LLMExecutor
from .llm import OpenAICompatibleClient
from .memory import MemoryReviewConflict, SQLiteMemoryStore
from .memory_benchmarks import run_retrieval_benchmark
from .memory_quality import run_extraction_benchmark
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




def _budget_from_env() -> RunBudget:
    max_cost = os.getenv("KALDRAX_MAX_RUN_COST_USD")
    input_rate = os.getenv("KALDRAX_INPUT_COST_PER_MILLION_USD")
    output_rate = os.getenv("KALDRAX_OUTPUT_COST_PER_MILLION_USD")
    return RunBudget(
        max_calls=int(os.getenv("KALDRAX_MAX_PROVIDER_CALLS", "20")),
        max_input_tokens=int(os.getenv("KALDRAX_MAX_RUN_INPUT_TOKENS", "60000")),
        max_output_tokens=int(os.getenv("KALDRAX_MAX_RUN_OUTPUT_TOKENS", "12000")),
        max_total_tokens=int(os.getenv("KALDRAX_MAX_RUN_TOTAL_TOKENS", "72000")),
        max_duration_seconds=float(os.getenv("KALDRAX_MAX_RUN_DURATION_SECONDS", "600")),
        max_cost_usd=float(max_cost) if max_cost else None,
        input_cost_per_million_usd=float(input_rate) if input_rate else None,
        output_cost_per_million_usd=float(output_rate) if output_rate else None,
    )


def _client(model: str, budget: RunBudget) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        api_key=os.getenv("KALDRAX_API_KEY", ""),
        model=model,
        base_url=os.getenv("KALDRAX_BASE_URL") or "https://api.openai.com/v1",
        timeout=float(os.getenv("KALDRAX_TIMEOUT_SECONDS", "60")),
        max_tokens=int(os.getenv("KALDRAX_MAX_TOKENS", "2048")),
        token_parameter=os.getenv("KALDRAX_TOKEN_PARAMETER", "max_completion_tokens"),
        budget=budget,
    )


def _require_provider() -> tuple[str, str, str]:
    api_key = os.getenv("KALDRAX_API_KEY", "")
    executor_model = os.getenv("KALDRAX_MODEL", "")
    evaluator_model = os.getenv("KALDRAX_EVALUATOR_MODEL", "")
    if not api_key:
        raise ValueError("KALDRAX_API_KEY is required")
    if not executor_model:
        raise ValueError("KALDRAX_MODEL is required")
    if not evaluator_model:
        raise ValueError("KALDRAX_EVALUATOR_MODEL is required")
    if executor_model.casefold() == evaluator_model.casefold():
        raise ValueError("KALDRAX_EVALUATOR_MODEL must differ from KALDRAX_MODEL")
    return api_key, executor_model, evaluator_model


def _provider_check() -> int:
    _, executor_model, evaluator_model = _require_provider()
    budget = _budget_from_env()
    executor = _client(executor_model, budget)
    evaluator_client = _client(evaluator_model, budget)
    completion = executor.complete_with_usage(
        system_prompt="You are performing a provider connectivity smoke test.",
        user_prompt="Reply with exactly this token and no punctuation: KALDRAX_PROVIDER_OK",
    )
    executor_ok = completion.content.strip() == "KALDRAX_PROVIDER_OK"
    criterion = "The KALDRAX provider health check completed."
    evaluation = LLMEvaluator(evaluator_client).evaluate(
        Task("Validate provider evaluator response", (criterion,)),
        criterion,
    )
    payload = {
        "executor_model": executor_model,
        "evaluator_model": evaluator_model,
        "executor_smoke_passed": executor_ok,
        "evaluator_schema_and_evidence_passed": evaluation.passed,
        "evaluator_missing": list(evaluation.missing),
        "executor_usage": {
            "prompt_tokens": completion.usage.prompt_tokens,
            "completion_tokens": completion.usage.completion_tokens,
            "estimated": completion.usage.estimated,
        },
        "budget": budget.snapshot().to_dict(),
    }
    print(json.dumps(payload, indent=2))
    return 0 if executor_ok and evaluation.passed else 1


def _benchmark_evaluator(args: argparse.Namespace) -> int:
    cases = load_cases(args.fixture)
    budget = None
    if args.mode == "llm":
        if not os.getenv("KALDRAX_API_KEY", "").strip():
            raise ValueError("KALDRAX_API_KEY is required for an LLM evaluator benchmark")
        evaluator_model = os.getenv("KALDRAX_EVALUATOR_MODEL", "").strip()
        if not evaluator_model:
            raise ValueError("KALDRAX_EVALUATOR_MODEL is required for an LLM evaluator benchmark")
        budget = _budget_from_env()
        evaluator = LLMEvaluator(_client(evaluator_model, budget))
    else:
        evaluator = CriteriaEvaluator()
    report = run_benchmark(evaluator, cases)
    payload = report.to_dict()
    payload["evaluator_mode"] = args.mode
    if budget is not None:
        payload["budget"] = budget.snapshot().to_dict()
    print(json.dumps(payload, indent=2))
    return 0 if report.accuracy >= args.min_accuracy and report.errors == 0 else 1


def _team(args: argparse.Namespace) -> int:
    _, builder_model, evaluator_model = _require_provider()
    planner_model = os.getenv("KALDRAX_PLANNER_MODEL", "")
    reviewer_model = os.getenv("KALDRAX_REVIEWER_MODEL", "")
    models = [planner_model, builder_model, reviewer_model, evaluator_model]
    if any(not model.strip() for model in models):
        raise ValueError(
            "team requires KALDRAX_PLANNER_MODEL, KALDRAX_MODEL, "
            "KALDRAX_REVIEWER_MODEL, and KALDRAX_EVALUATOR_MODEL"
        )
    if len({model.casefold() for model in models}) != 4:
        raise ValueError("planner, builder, reviewer, and evaluator model identifiers must all differ")

    budget = _budget_from_env()
    memory = _memory_store(_memory_path(args))
    try:
        report = MultiAgentCoordinator(
            planner=_client(planner_model, budget),
            builder=_client(builder_model, budget),
            reviewer=_client(reviewer_model, budget),
            evaluator=LLMEvaluator(_client(evaluator_model, budget)),
            max_cycles=args.max_cycles,
            memory_store=memory,
            agent_namespace=args.agent_namespace,
            budget=budget,
            artifact_dir=args.artifacts,
        ).run(Task(args.objective, tuple(args.criterion), project_id=args.project))
    finally:
        memory.close()
    payload = report.to_dict()
    print(json.dumps(payload, indent=2))
    return 0 if report.status.value == "passed" else 1



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

    budget = _budget_from_env()
    executor_client = _client(executor_model, budget)
    evaluator_client = _client(evaluator_model, budget)
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
    payload = report.to_dict()
    payload["budget"] = budget.snapshot().to_dict()
    if args.artifacts is not None:
        (args.artifacts / f"{report.run_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
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

    benchmark = memory_actions.add_parser("benchmark", help="measure retrieval quality on an annotated engineering corpus")
    benchmark.add_argument("--dataset", type=Path, default=Path("benchmarks/memory_retrieval_engineering_v2.json"))
    benchmark.add_argument("--k", type=int, default=3)

    extraction_benchmark = memory_actions.add_parser(
        "extraction-benchmark", help="evaluate extraction quality and confidence calibration using the configured LLM",
    )
    extraction_benchmark.add_argument("--dataset", type=Path, default=Path("benchmarks/memory_extraction_v1.json"))
    extraction_benchmark.add_argument("--max-memories", type=int, default=8)


    provider = commands.add_parser("provider-check", help="smoke-test configured executor and evaluator models")
    benchmark_eval = commands.add_parser("benchmark-evaluator", help="measure evaluator behavior against a regression fixture")
    benchmark_eval.add_argument("--mode", choices=("deterministic", "llm"), default="deterministic")
    benchmark_eval.add_argument("--fixture", type=Path, default=Path(__file__).parent / "data" / "evaluator_cases.json")
    benchmark_eval.add_argument("--min-accuracy", type=float, default=0.80)

    team = commands.add_parser("team", help="run a bounded planner-builder-reviewer workflow")
    team.add_argument("--objective", required=True)
    team.add_argument("--criterion", action="append", required=True)
    team.add_argument("--project", default="default")
    team.add_argument("--agent-namespace", default="team")
    team.add_argument("--max-cycles", type=int, default=2)
    team.add_argument("--artifacts", type=Path, default=Path(".kaldrax/runs"))
    team.add_argument("--memory-db", type=Path, default=None)

    sandbox = commands.add_parser("sandbox", help="execute untrusted Python inside a Docker sandbox")
    sandbox_actions = sandbox.add_subparsers(dest="sandbox_action", required=True)
    sandbox_run = sandbox_actions.add_parser("run-python", help="run a Python file in a disposable container")
    sandbox_run.add_argument("file", type=Path)
    sandbox_run.add_argument("--timeout", type=int, default=15)
    sandbox_run.add_argument("--memory-mb", type=int, default=256)
    sandbox_run.add_argument("--cpu-count", type=float, default=1.0)
    sandbox_run.add_argument("--pids-limit", type=int, default=64)
    sandbox_run.add_argument("--workspace-root", type=Path, default=Path(".kaldrax/sandbox"))

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
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            parser.error(str(exc))


    if args.command == "provider-check":
        try:
            return _provider_check()
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            parser.error(str(exc))

    if args.command == "benchmark-evaluator":
        if not 0.0 <= args.min_accuracy <= 1.0:
            parser.error("--min-accuracy must be between 0 and 1")
        try:
            return _benchmark_evaluator(args)
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            parser.error(str(exc))

    if args.command == "team":
        if not 1 <= args.max_cycles <= 5:
            parser.error("--max-cycles must be between 1 and 5")
        try:
            return _team(args)
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            parser.error(str(exc))

    if args.command == "sandbox" and args.sandbox_action == "run-python":
        try:
            if args.file.stat().st_size > SandboxRunner.MAX_SOURCE_BYTES:
                parser.error("source exceeds the 1 MB sandbox limit")
            source = args.file.read_text(encoding="utf-8")
            result = SandboxRunner(workspace_root=args.workspace_root).run_python(
                source, timeout_seconds=args.timeout, memory_mb=args.memory_mb,
                cpu_count=args.cpu_count, pids_limit=args.pids_limit,
            )
            print(json.dumps(result.to_dict(), indent=2))
            return 1 if result.timed_out or result.exit_code != 0 else 0
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            parser.error(str(exc))

    if args.command == "memory":
        if args.memory_action == "benchmark":
            try:
                result = run_retrieval_benchmark(
                    args.dataset, embedder=_embedding_provider(), k=args.k,
                )
            except (ValueError, TypeError, RuntimeError, OSError) as exc:
                parser.error(str(exc))
            print(json.dumps(result, indent=2))
            return 0

        if args.memory_action == "extraction-benchmark":
            api_key = os.getenv("KALDRAX_API_KEY", "").strip()
            model = os.getenv("KALDRAX_MODEL", "").strip()
            if not api_key or not model:
                parser.error("KALDRAX_API_KEY and KALDRAX_MODEL are required for extraction benchmarking")
            try:
                budget = _budget_from_env()
                extractor = LLMMemoryExtractor(
                    _client(model, budget), max_memories=args.max_memories,
                )
                result = run_extraction_benchmark(args.dataset, extractor=extractor)
                result["budget"] = budget.snapshot().to_dict()
            except (ValueError, TypeError, RuntimeError, OSError) as exc:
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
