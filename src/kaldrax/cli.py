"""KALDRAX command-line interface."""
import argparse
import json
from pathlib import Path
from .engine import RecursiveEngine
from .execution import ExampleExecutor
from .models import Task

def main() -> int:
    parser = argparse.ArgumentParser(prog="kaldrax", description="KALDRAX engineering harness")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="run the offline recursive-loop demonstration")
    demo.add_argument("--artifacts", type=Path, default=Path(".kaldrax/runs"))
    args = parser.parse_args()
    if args.command == "demo":
        task = Task("Produce a minimal project delivery summary",
                    ("Scope", "Verification", "Known limitations"), max_iterations=3)
        report = RecursiveEngine(ExampleExecutor(), artifact_dir=args.artifacts).run(task)
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.status.value == "passed" else 1
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
