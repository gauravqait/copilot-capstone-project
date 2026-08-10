"""Integration tests for scripts/create_pr.py in dry-run mode.

Verifies that the PR-creation stage:
- Exits 0 in dry-run mode without making any git or API calls
- Writes pr-result.json with status=dry_run when docs/output exists
- Writes pr-result.json with status=skipped when docs/output is absent
- Includes dry_run=True and a would-be branch name in the dry-run result
- Fails with a non-zero exit code in normal mode without credentials
"""

import json
import subprocess
import sys
import pytest

from tests.integration.conftest import base_env, PROJECT_ROOT


def run_create_pr(pr_result_path, env_overrides=None):
    env = base_env(**(env_overrides or {}))
    env["PR_RESULT_PATH"] = str(pr_result_path)
    return subprocess.run(
        [sys.executable, "scripts/create_pr.py"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


@pytest.mark.integration
def test_create_pr_dry_run_exits_zero_with_output_dir(workspace, tmp_path):
    """Dry-run exits 0 when docs/output exists."""
    # Place a file in docs/output so output_dir.exists() is True
    doc = workspace["out"] / "README.generated.md"
    doc.write_text("# Generated README\n\nContent here.\n", encoding="utf-8")

    pr_result_path = tmp_path / "pr-result.json"
    result = run_create_pr(pr_result_path, {"DRY_RUN": "true"})
    assert result.returncode == 0, f"stderr: {result.stderr}"


@pytest.mark.integration
def test_create_pr_dry_run_writes_dry_run_status(workspace, tmp_path):
    """Dry-run writes pr-result.json with status=dry_run."""
    doc = workspace["out"] / "doc.md"
    doc.write_text("# Doc\n\nContent.\n", encoding="utf-8")

    pr_result_path = tmp_path / "pr-result.json"
    run_create_pr(pr_result_path, {"DRY_RUN": "true"})

    assert pr_result_path.exists()
    data = json.loads(pr_result_path.read_text(encoding="utf-8"))
    assert data["status"] == "dry_run"
    assert data.get("dry_run") is True


@pytest.mark.integration
def test_create_pr_dry_run_includes_branch_name(workspace, tmp_path):
    """Dry-run result includes the branch name that would have been created."""
    doc = workspace["out"] / "doc.md"
    doc.write_text("# Doc\n\nContent.\n", encoding="utf-8")

    pr_result_path = tmp_path / "pr-result.json"
    run_create_pr(pr_result_path, {"DRY_RUN": "true"})

    data = json.loads(pr_result_path.read_text(encoding="utf-8"))
    assert "branch" in data
    assert data["branch"].startswith("docs-generated-")


@pytest.mark.integration
def test_create_pr_dry_run_skips_when_no_output_dir(workspace, tmp_path):
    """Dry-run writes status=skipped when docs/output does not exist."""
    # Remove the output directory entirely
    workspace["out"].rmdir()

    pr_result_path = tmp_path / "pr-result.json"
    result = run_create_pr(pr_result_path, {"DRY_RUN": "true"})
    assert result.returncode == 0, f"stderr: {result.stderr}"

    data = json.loads(pr_result_path.read_text(encoding="utf-8"))
    assert data["status"] == "skipped"
    assert data.get("dry_run") is True


@pytest.mark.integration
def test_create_pr_dry_run_result_stdout_is_json(workspace, tmp_path):
    """Dry-run stdout is valid JSON."""
    doc = workspace["out"] / "doc.md"
    doc.write_text("# Doc\n\nContent.\n", encoding="utf-8")

    pr_result_path = tmp_path / "pr-result.json"
    result = run_create_pr(pr_result_path, {"DRY_RUN": "true"})
    data = json.loads(result.stdout)
    assert "status" in data


@pytest.mark.integration
def test_create_pr_normal_mode_fails_without_token(workspace, tmp_path):
    """Normal mode (DRY_RUN=false) fails without a real GITHUB_TOKEN."""
    pr_result_path = tmp_path / "pr-result.json"
    result = run_create_pr(
        pr_result_path,
        {
            "DRY_RUN": "false",
            "GITHUB_TOKEN": "",
            "GITHUB_REPOSITORY": "",
        },
    )
    # Should exit non-zero because credentials are missing
    assert result.returncode != 0
