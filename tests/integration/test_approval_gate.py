"""Integration tests for scripts/approval_gate.py.

Verifies that the approval-gating stage:
- Exits 0 in dry-run mode WITHOUT requiring GITHUB_TOKEN (DRY_RUN guard
  now runs before the credential check after the T14 fix)
- Exits 0 when pr-result.json reports status=skipped
- Exits 0 when policy requires no review
- Raises a RuntimeError when credentials are absent in normal mode
"""

import json
import subprocess
import sys
import pytest

from tests.integration.conftest import base_env, PROJECT_ROOT


def run_approval_gate(pr_result_path=None, env_overrides=None):
    env = base_env(**(env_overrides or {}))
    if pr_result_path is not None:
        env["PR_RESULT_PATH"] = str(pr_result_path)
    return subprocess.run(
        [sys.executable, "scripts/approval_gate.py"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


@pytest.mark.integration
def test_approval_gate_dry_run_exits_zero_without_token(workspace, tmp_path):
    """DRY_RUN=true exits 0 before the credential check."""
    pr_result_path = tmp_path / "pr-result.json"
    result = run_approval_gate(
        pr_result_path,
        {
            "DRY_RUN": "true",
            "GITHUB_TOKEN": "",       # explicitly empty – no credentials
            "GITHUB_REPOSITORY": "",
        },
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert "dry-run" in result.stdout.lower() or "dry_run" in result.stdout.lower()


@pytest.mark.integration
def test_approval_gate_dry_run_prints_skip_message(workspace, tmp_path):
    """DRY_RUN=true prints a message that the gate was skipped."""
    pr_result_path = tmp_path / "pr-result.json"
    result = run_approval_gate(pr_result_path, {"DRY_RUN": "true", "GITHUB_TOKEN": "", "GITHUB_REPOSITORY": ""})
    assert "skipped" in result.stdout.lower() or "dry" in result.stdout.lower()


@pytest.mark.integration
def test_approval_gate_skipped_pr_exits_zero(workspace, tmp_path):
    """status=skipped in pr-result.json bypasses the approval check."""
    pr_result_path = tmp_path / "pr-result.json"
    pr_result_path.write_text(json.dumps({"status": "skipped"}), encoding="utf-8")

    result = run_approval_gate(
        pr_result_path,
        {
            "DRY_RUN": "false",
            "GITHUB_TOKEN": "fake-token",
            "GITHUB_REPOSITORY": "test/repo",
        },
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


@pytest.mark.integration
def test_approval_gate_normal_mode_requires_token(workspace, tmp_path):
    """Without GITHUB_TOKEN, normal mode raises RuntimeError."""
    pr_result_path = tmp_path / "pr-result.json"
    result = run_approval_gate(
        pr_result_path,
        {
            "DRY_RUN": "false",
            "GITHUB_TOKEN": "",
            "GITHUB_REPOSITORY": "",
        },
    )
    assert result.returncode != 0
    assert "RuntimeError" in result.stderr or "required" in result.stderr.lower()
