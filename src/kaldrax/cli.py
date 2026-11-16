"""KALDRAX command-line interface."""
import argparse
import json
import os
from pathlib import Path

from .engine import RecursiveEngine
from .evaluation import LLMEvaluator
from .execution import ExampleExecutor, LLMExecutor
from .llm import OpenAICompatibleClient
from .models import Task


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
    task = Task(args.objective, tuple(args.criterion), args.max_iterations)
    report = RecursiveEngine(
        LLMExecutor(executor_client),
        evaluator=LLMEvaluator(evaluator_client),
        artifact_dir=args.artifacts,
    ).run(task)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.status.value == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="kaldrax", description="KALDRAX engineering harness")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="run the offline recursive-loop demonstration")
    demo.add_argument("--artifacts", type=Path, default=Path(".kaldrax/runs"))

    run = commands.add_parser("run", help="run an LLM-backed task with a separate model evaluator")
    run.add_argument("--objective", required=True)
    run.add_argument("--criterion", action="append", required=True, help="acceptance criterion; repeat for multiple")
    run.add_argument("--max-iterations", type=int, default=3)
    run.add_argument("--artifacts", type=Path, default=Path(".kaldrax/runs"))

    args = parser.parse_args()
    if args.command == "demo":
        task = Task("Produce a minimal project delivery summary",
                    ("Scope", "Verification", "Known limitations"), max_iterations=3)
        report = RecursiveEngine(ExampleExecutor(), artifact_dir=args.artifacts).run(task)
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.status.value == "passed" else 1
    if args.command == "run":
        try:
            return _run_llm(args)
        except (ValueError, TypeError) as exc:
            parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
