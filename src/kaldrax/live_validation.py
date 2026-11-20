"""Credential-gated, end-to-end live provider validation for KALDRAX."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .budgets import RunBudget
from .engineering import RepositoryTeamCoordinator
from .evaluation import LLMEvaluator
from .embeddings import HostedEmbeddingProvider
from .llm import OpenAICompatibleClient
from .memory import MemoryRecord, MemoryType, SQLiteMemoryStore
from .models import Task
from .workspace_sandbox import WorkspaceSandboxRunner


class MeasuredChatClient:
    """ChatClient adapter that records timing, failures and provider token usage."""

    def __init__(self, role: str, model: str, client: OpenAICompatibleClient) -> None:
        self.role = role
        self.model = model
        self.client = client
        self.calls: list[dict[str, Any]] = []
        self._lock = Lock()

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        started = time.perf_counter()
        call: dict[str, Any] = {
            "role": self.role, "model": self.model, "status": "failed",
            "latency_ms": 0, "prompt_tokens": None, "completion_tokens": None,
            "usage_estimated": None,
        }
        try:
            if hasattr(self.client, "complete_with_usage"):
                result = self.client.complete_with_usage(
                    system_prompt=system_prompt, user_prompt=user_prompt
                )
                content = result.content
                usage = result.usage
                call.update({
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "usage_estimated": usage.estimated,
                })
            else:
                content = self.client.complete(
                    system_prompt=system_prompt, user_prompt=user_prompt
                )
            if not isinstance(content, str) or not content.strip():
                raise ValueError("provider returned an empty completion")
            call["status"] = "passed"
            return content
        except Exception as exc:
            call["error_type"] = type(exc).__name__
            raise
        finally:
            call["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            with self._lock:
                self.calls.append(call)


def _git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        timeout=30, check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "git command failed")[:500])


def _make_fixture(root: Path) -> None:
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "operations.py").write_text(
        "def subtract(left: int, right: int) -> int:\n"
        "    raise NotImplementedError\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_operations.py").write_text(
        "import unittest\n"
        "from src.operations import subtract\n\n"
        "class SubtractTests(unittest.TestCase):\n"
        "    def test_positive_result(self):\n"
        "        self.assertEqual(subtract(9, 4), 5)\n\n"
        "    def test_negative_result(self):\n"
        "        self.assertEqual(subtract(4, 9), -5)\n",
        encoding="utf-8",
    )
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "KALDRAX Validation")
    _git(root, "config", "user.email", "validation@kaldrax.invalid")
    _git(root, "add", "src/operations.py", "tests/test_operations.py")
    _git(root, "commit", "-qm", "Create live validation fixture")


def _save_report(report: dict[str, Any], artifacts: Path) -> Path:
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / f"live-validation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    report["artifact"] = str(path)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def _check_docker(report: dict[str, Any]) -> bool:
    docker = shutil.which("docker")
    if not docker:
        report["checks"]["docker"] = {"status": "blocked", "reason": "Docker CLI not found."}
        return False
    try:
        result = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is None or result.returncode or not result.stdout.strip():
        report["checks"]["docker"] = {
            "status": "blocked", "reason": "Docker daemon is not reachable.",
        }
        return False
    report["checks"]["docker"] = {
        "status": "passed", "server_version": result.stdout.strip(),
    }
    return True


def _check_memory(report: dict[str, Any], artifacts: Path) -> bool:
    embedding_model = os.getenv("KALDRAX_EMBEDDING_MODEL", "").strip()
    embedding_api_key = (
        os.getenv("KALDRAX_EMBEDDING_API_KEY", "").strip()
        or os.getenv("KALDRAX_API_KEY", "").strip()
    )
    embedding_base_url = (
        os.getenv("KALDRAX_EMBEDDING_BASE_URL")
        or os.getenv("KALDRAX_BASE_URL")
        or "https://api.openai.com/v1"
    )
    embedder = (
        HostedEmbeddingProvider(
            api_key=embedding_api_key,
            model=embedding_model,
            base_url=embedding_base_url,
            timeout=float(os.getenv("KALDRAX_EMBEDDING_TIMEOUT_SECONDS", "30")),
        )
        if embedding_model else None
    )
    with tempfile.TemporaryDirectory(prefix="kaldrax-memory-check-", dir=artifacts) as folder:
        memory = SQLiteMemoryStore(Path(folder) / "memory.sqlite3", embedder=embedder)
        try:
            record = MemoryRecord.create(
                project_id="kaldrax-live-validation",
                memory_type=MemoryType.SEMANTIC,
                content="Validation invariant: generated patches must pass isolated Docker tests before application.",
                summary="Docker verification is required before applying repository patches.",
                tags=("validation", "docker", "patch-safety"),
            )
            memory.save(record)
            matches = memory.search(
                "Docker tests before applying repository patches",
                project_id="kaldrax-live-validation", limit=3,
            )
            isolated = memory.search(
                "Docker tests before applying repository patches",
                project_id="different-project", limit=3,
            )
            semantic_ready = (
                embedder is None
                or (
                    memory.last_embedding_error is None
                    and bool(matches)
                    and matches[0].semantic_score is not None
                )
            )
            passed = bool(
                matches and matches[0].record.id == record.id and not isolated
                and semantic_ready
            )
            report["checks"]["memory_retrieval"] = {
                "status": "passed" if passed else "failed",
                "retrieval_method": matches[0].retrieval_method if matches else None,
                "project_isolation_passed": not isolated,
                "matched_record": bool(matches and matches[0].record.id == record.id),
                "embedding_model": embedding_model or None,
                "semantic_retrieval_passed": semantic_ready,
                "embedding_error_type": memory.last_embedding_error,
            }
            return passed
        finally:
            memory.close()


def run_live_validation(*, artifacts: Path, timeout_seconds: int = 90) -> tuple[int, dict[str, Any]]:
    """Run one bounded real-provider repository task against a disposable Git fixture."""
    started = time.perf_counter()
    artifacts.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked",
        "checks": {},
        "provider_calls": [],
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "estimated_calls": 0},
        "verification": None,
        "failures": [],
        "notes": [
            "Repository changes are applied only to a disposable temporary Git fixture.",
            "Provider prompts, completions, API keys and environment values are never written to this report.",
        ],
    }

    try:
        docker_ready = _check_docker(report)
    except Exception as exc:
        docker_ready = False
        report["checks"]["docker"] = {"status": "failed", "error_type": type(exc).__name__}
    try:
        memory_ready = _check_memory(report, artifacts)
    except Exception as exc:
        memory_ready = False
        report["checks"]["memory_retrieval"] = {"status": "failed", "error_type": type(exc).__name__}

    role_env = {
        "planner": "KALDRAX_PLANNER_MODEL",
        "builder": "KALDRAX_MODEL",
        "reviewer": "KALDRAX_REVIEWER_MODEL",
        "evaluator": "KALDRAX_EVALUATOR_MODEL",
    }
    api_key = os.getenv("KALDRAX_API_KEY", "").strip()
    models = {role: os.getenv(variable, "").strip() for role, variable in role_env.items()}
    missing = (["KALDRAX_API_KEY"] if not api_key else []) + [
        variable for role, variable in role_env.items() if not models[role]
    ]
    if missing:
        report["checks"]["provider_configuration"] = {
            "status": "blocked", "missing": missing,
        }
        report["failures"].append("Live provider credentials/model configuration is incomplete.")
        report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        report["artifact"] = str(_save_report(report, artifacts))
        return 2, report
    if len({value.casefold() for value in models.values()}) != len(models):
        report["status"] = "failed"
        report["checks"]["provider_configuration"] = {
            "status": "failed", "reason": "All four role model identifiers must be distinct.",
        }
        report["failures"].append("Planner, builder, reviewer and evaluator model identifiers must differ.")
        report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        report["artifact"] = str(_save_report(report, artifacts))
        return 1, report

    report["checks"]["provider_configuration"] = {
        "status": "passed", "provider_base_url": os.getenv(
            "KALDRAX_BASE_URL", "https://api.openai.com/v1"
        ),
        "models": models,
    }

    if not docker_ready:
        report["failures"].append("Docker is required for isolated repository verification.")
        report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        report["artifact"] = str(_save_report(report, artifacts))
        return 2, report
    if not memory_ready:
        report["failures"].append("Memory retrieval preflight failed.")
        report["status"] = "failed"
        report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        report["artifact"] = str(_save_report(report, artifacts))
        return 1, report

    budget = RunBudget(
        max_calls=int(os.getenv("KALDRAX_MAX_PROVIDER_CALLS", "20")),
        max_input_tokens=int(os.getenv("KALDRAX_MAX_RUN_INPUT_TOKENS", "60000")),
        max_output_tokens=int(os.getenv("KALDRAX_MAX_RUN_OUTPUT_TOKENS", "12000")),
        max_total_tokens=int(os.getenv("KALDRAX_MAX_RUN_TOTAL_TOKENS", "72000")),
        max_duration_seconds=float(os.getenv("KALDRAX_MAX_RUN_DURATION_SECONDS", "600")),
        max_cost_usd=float(os.environ["KALDRAX_MAX_RUN_COST_USD"]) if os.getenv("KALDRAX_MAX_RUN_COST_USD") else None,
        input_cost_per_million_usd=float(os.environ["KALDRAX_INPUT_COST_PER_MILLION_USD"]) if os.getenv("KALDRAX_INPUT_COST_PER_MILLION_USD") else None,
        output_cost_per_million_usd=float(os.environ["KALDRAX_OUTPUT_COST_PER_MILLION_USD"]) if os.getenv("KALDRAX_OUTPUT_COST_PER_MILLION_USD") else None,
    )
    base_url = os.getenv("KALDRAX_BASE_URL") or "https://api.openai.com/v1"
    clients: dict[str, MeasuredChatClient] = {}
    try:
        for role, model in models.items():
            raw = OpenAICompatibleClient(
                api_key=api_key, model=model, base_url=base_url,
                timeout=float(os.getenv("KALDRAX_TIMEOUT_SECONDS", "60")),
                max_tokens=int(os.getenv("KALDRAX_MAX_TOKENS", "2048")),
                token_parameter=os.getenv("KALDRAX_TOKEN_PARAMETER", "max_completion_tokens"),
                budget=budget,
            )
            clients[role] = MeasuredChatClient(role, model, raw)

        with tempfile.TemporaryDirectory(prefix="kaldrax-live-validation-") as folder:
            fixture = Path(folder) / "fixture"
            fixture.mkdir()
            _make_fixture(fixture)
            task = Task(
                objective=(
                    "Implement src/operations.py subtract(left, right) so it returns "
                    "left minus right. Do not change the tests."
                ),
                acceptance_criteria=(
                    "The patch implements subtraction as left minus right.",
                    "The Docker verification output reports Ran 2 tests.",
                ),
                project_id="kaldrax-live-validation",
            )
            team = RepositoryTeamCoordinator(
                planner=clients["planner"], builder=clients["builder"],
                reviewer=clients["reviewer"],
                evaluator=LLMEvaluator(clients["evaluator"]),
                workspace_root=fixture,
                sandbox=WorkspaceSandboxRunner(),
                verify_module="unittest",
                verify_args=("discover", "-s", "tests", "-v"),
                timeout_seconds=timeout_seconds,
                max_cycles=1,
                budget=budget,
            ).run(task, apply_changes=True)
            verification = team.verification or {}
            report["verification"] = verification
            report["checks"]["repository_team"] = {
                "status": "passed" if (
                    team.status.value == "passed" and team.applied
                    and team.reviewer_approved and team.evaluation is not None
                    and team.evaluation.passed
                ) else "failed",
                "run_status": team.status.value,
                "applied_to_disposable_git_fixture": team.applied,
                "changed_files": team.changed_files,
                "reviewer_approved": team.reviewer_approved,
                "independent_evaluator_passed": bool(team.evaluation and team.evaluation.passed),
                "cycles": team.cycles,
                "events": team.events,
            }
            if report["checks"]["repository_team"]["status"] != "passed":
                report["failures"].append("Live repository Team Run did not pass every acceptance gate.")

    except Exception as exc:
        report["failures"].append(f"Live validation raised {type(exc).__name__}: {str(exc)[:300]}")
        report["checks"].setdefault("execution", {"status": "failed", "error_type": type(exc).__name__})
    finally:
        calls = [call for client in clients.values() for call in client.calls]
        report["provider_calls"] = calls
        report["token_usage"] = {
            "prompt_tokens": sum(call.get("prompt_tokens") or 0 for call in calls),
            "completion_tokens": sum(call.get("completion_tokens") or 0 for call in calls),
            "estimated_calls": sum(call.get("usage_estimated") is True for call in calls),
            "calls": len(calls),
        }
        report["budget"] = budget.snapshot().to_dict()

    checks = report["checks"]
    required = ("provider_configuration", "docker", "memory_retrieval", "repository_team")
    report["status"] = (
        "passed" if all(checks.get(name, {}).get("status") == "passed" for name in required)
        else "failed"
    )
    report["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    report["artifact"] = str(_save_report(report, artifacts))
    return (0 if report["status"] == "passed" else 1), report
