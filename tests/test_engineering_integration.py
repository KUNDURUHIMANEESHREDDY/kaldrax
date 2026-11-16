"""Docker-backed integration: repair an actual failing CSV parser project."""
import os

import pytest

from test_engineering import init_csv_repo, make_coordinator, SuccessfulSandbox
from kaldrax.engineering import RepositoryTeamCoordinator
from kaldrax.evaluation import CriteriaEvaluator
from kaldrax.models import RunStatus, Task
from kaldrax.workspace_sandbox import WorkspaceSandboxRunner


@pytest.mark.skipif(
    os.getenv("KALDRAX_RUN_DOCKER_INTEGRATION") != "1",
    reason="set KALDRAX_RUN_DOCKER_INTEGRATION=1 when Docker is available",
)
def test_actual_repository_patch_test_review_apply_cycle_runs_in_docker(tmp_path):
    root = tmp_path / "csv-project"
    init_csv_repo(root)
    task = Task(
        "Fix CSV parsing so quoted commas are preserved and blank rows are ignored",
        ("csv.reader", "any(field.strip() for field in row)", "Sandbox verification exit code: 0"),
        project_id="csv-import-integration",
    )
    helper, _ = make_coordinator(root, SuccessfulSandbox())
    coordinator = RepositoryTeamCoordinator(
        planner=helper.planner,
        builder=helper.builder,
        reviewer=helper.reviewer,
        evaluator=CriteriaEvaluator(),
        workspace_root=root,
        sandbox=WorkspaceSandboxRunner(workspace_root=tmp_path / "sandbox"),
        verify_module="unittest",
        verify_args=("discover", "-s", "tests", "-v"),
        timeout_seconds=30,
        max_cycles=1,
    )

    report = coordinator.run(task, apply_changes=True)

    assert report.status is RunStatus.PASSED
    assert report.applied is True
    assert report.verification["exit_code"] == 0
    combined_output = report.verification["stdout"] + report.verification["stderr"]
    assert "test_quoted_commas_are_preserved" in combined_output
    assert "test_blank_rows_are_ignored" in combined_output
    assert "csv.reader" in (root / "csv_reader.py").read_text(encoding="utf-8")
