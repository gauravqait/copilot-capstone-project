"""Integration tests for scripts/notify.py.

Verifies that the notification stage:
- Exits 0 for pr_ready when pr-result.json has status=dry_run
- Exits 0 for pr_ready when pr-result.json has status=skipped
- Exits 0 for pr_ready when pr-result.json is missing (dry-run mode)
- Exits 0 for pr_ready when pr-result.json is missing (normal mode)
- Does not raise for workflow_success / workflow_failure events (env is set)

API calls are expected to fail with a fake token; the tests assert on
exit behaviour BEFORE the API is reached wherever possible.
"""

import json
import subprocess
import sys
import pytest

from tests.integration.conftest import base_env, PROJECT_ROOT


def run_notify(event: str, pr_result_path=None, env_overrides=None):
    env = base_env(**(env_overrides or {}))
    cmd = [sys.executable, "scripts/notify.py", event]
    if pr_result_path is not None:
        cmd += ["--pr-result", str(pr_result_path)]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


@pytest.mark.integration
def test_notify_pr_ready_dry_run_status(workspace, tmp_path):
    """pr_ready exits 0 without calling the API when status=dry_run."""
    pr_result_path = tmp_path / "pr-result.json"
    pr_result_path.write_text(
        json.dumps({"status": "dry_run", "dry_run": True}), encoding="utf-8"
    )
    result = run_notify("pr_ready", pr_result_path, {"DRY_RUN": "true"})
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "dry" in result.stdout.lower()


@pytest.mark.integration
def test_notify_pr_ready_skipped_status(workspace, tmp_path):
    """pr_ready exits 0 without calling the API when status=skipped."""
    pr_result_path = tmp_path / "pr-result.json"
    pr_result_path.write_text(json.dumps({"status": "skipped"}), encoding="utf-8")
    result = run_notify("pr_ready", pr_result_path, {"DRY_RUN": "false"})
    assert result.returncode == 0, f"stderr: {result.stderr}"


@pytest.mark.integration
def test_notify_pr_ready_missing_file_dry_run(workspace, tmp_path):
    """Missing pr-result.json in dry-run mode exits 0 gracefully."""
    pr_result_path = tmp_path / "nonexistent.json"
    result = run_notify("pr_ready", pr_result_path, {"DRY_RUN": "true"})
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "not found" in result.stdout.lower() or "skipped" in result.stdout.lower()


@pytest.mark.integration
def test_notify_pr_ready_missing_file_normal_mode(workspace, tmp_path):
    """Missing pr-result.json in normal mode exits 0 gracefully (returns None)."""
    pr_result_path = tmp_path / "nonexistent.json"
    result = run_notify("pr_ready", pr_result_path, {"DRY_RUN": "false"})
    assert result.returncode == 0, f"stderr: {result.stderr}"


@pytest.mark.integration
@pytest.mark.skip(reason="workflow_success always calls the GitHub Checks API; requires a real GITHUB_TOKEN")
def test_notify_workflow_success_dry_run_appends_suffix(workspace, tmp_path):
    """workflow_success in dry-run mode appends a dry-run note to the summary.

    Skipped in local / CI-without-token environments because the event
    unconditionally calls the GitHub Checks API before returning.
    """
    result = run_notify("workflow_success", env_overrides={"DRY_RUN": "true"})
    assert result.returncode == 0


@pytest.mark.integration
@pytest.mark.skip(reason="workflow_failure always calls the GitHub Checks API; requires a real GITHUB_TOKEN")
def test_notify_workflow_failure_does_not_crash(workspace):
    """workflow_failure runs without a Python-level traceback.

    Skipped in local / CI-without-token environments because the event
    unconditionally calls the GitHub Checks API before returning.
    """
    result = run_notify("workflow_failure", env_overrides={"DRY_RUN": "false"})
    assert result.returncode == 0
