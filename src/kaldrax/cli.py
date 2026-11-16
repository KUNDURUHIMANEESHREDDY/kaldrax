"""KALDRAX command-line interface."""
import argparse
import json
import os
from pathlib import Path

from .engine import RecursiveEngine
from .evaluation import LLMEvaluator
from .execution import ExampleExecutor, LLMExecutor
from .llm import OpenAICompatibleClient
from .memory import SQLiteMemoryStore
from .models import Task


def _memory_path(args: argparse.Namespace) -> Path:
    return args.memory_db or Path(".kaldrax/memory.sqlite3")


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
    memory = SQLiteMemoryStore(_memory_path(args))
    try:
        report = RecursiveEngine(
            LLMExecutor(executor_client), evaluator=LLMEvaluator(evaluator_client),
            artifact_dir=args.artifacts, memory_store=memory, agent_id=args.agent,
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

    memory = commands.add_parser("memory", help="inspect or maintain persistent project memory")
    memory_actions = memory.add_subparsers(dest="memory_action", required=True)
    search_memory = memory_actions.add_parser("search", help="retrieve memories in one project")
    search_memory.add_argument("--query", required=True)
    search_memory.add_argument("--project", default="default")
    search_memory.add_argument("--limit", type=int, default=10)
    search_memory.add_argument("--agent", default=None)
    search_memory.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))
    consolidate_memory = memory_actions.add_parser("consolidate", help="merge exact duplicate memories")
    consolidate_memory.add_argument("--project", default=None)
    consolidate_memory.add_argument("--memory-db", type=Path, default=Path(".kaldrax/memory.sqlite3"))

    args = parser.parse_args()
    if args.command == "demo":
        task = Task(
            "Produce a minimal project delivery summary",
            ("Scope", "Verification", "Known limitations"),
            project_id=args.project,
        )
        memory = SQLiteMemoryStore(_memory_path(args))
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
        memory_store = SQLiteMemoryStore(args.memory_db)
        try:
            if args.memory_action == "search":
                matches = memory_store.search(
                    args.query, project_id=args.project, limit=args.limit, agent_id=args.agent,
                )
                print(json.dumps([{
                    "id": match.record.id,
                    "type": match.record.memory_type.value,
                    "score": round(match.score, 5),
                    "summary": match.record.summary,
                    "content": match.record.content,
                    "source_run_id": match.record.source_run_id,
                    "source_event_sequences": list(match.record.source_event_sequences),
                    "agent_id": match.record.agent_id,
                    "tags": list(match.record.tags),
                    "metadata": match.record.metadata,
                } for match in matches], indent=2))
                return 0
            if args.memory_action == "consolidate":
                removed = memory_store.consolidate(args.project)
                print(json.dumps({"duplicates_removed": removed, "remaining": memory_store.count(project_id=args.project)}, indent=2))
                return 0
        finally:
            memory_store.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
