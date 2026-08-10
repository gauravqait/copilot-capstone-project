"""End-to-end integration tests for the full documentation-sync pipeline.

Uses scripts/run_workflow.py with DRY_RUN=true to exercise the complete
pipeline — change detection, doc generation, validation, secret scanning,
and backup — without pushing to GitHub.

Verifies:
- The workflow exits 0
- All required intermediate artifacts are produced
- workflow-summary.json reports status=completed and dry_run=True
- dry-run-report.json is written with dry_run=True
- The audit log receives entries for every executed step
"""

import json
import pytest

from tests.integration.conftest import run_script, PROJECT_ROOT


@pytest.mark.integration
def test_full_pipeline_dry_run_exits_zero(workspace):
    """run_workflow.py in dry-run mode completes without error."""
    result = run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    assert result.returncode == 0, (
        f"Pipeline failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.integration
def test_full_pipeline_creates_change_detection_artifact(workspace):
    """Pipeline produces docs/generated/change-detection.json."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    assert (workspace["gen"] / "change-detection.json").exists()


@pytest.mark.integration
def test_full_pipeline_creates_doc_generation_artifact(workspace):
    """Pipeline produces docs/generated/doc-generation.json."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    assert (workspace["gen"] / "doc-generation.json").exists()


@pytest.mark.integration
def test_full_pipeline_creates_workflow_summary(workspace):
    """Pipeline produces a valid workflow-summary.json."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    summary_path = workspace["gen"] / "workflow-summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary.get("dry_run") is True


@pytest.mark.integration
def test_full_pipeline_creates_dry_run_report(workspace):
    """Pipeline produces docs/generated/dry-run-report.json in dry-run mode."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    report_path = workspace["gen"] / "dry-run-report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report.get("dry_run") is True
    assert "message" in report
    assert "summary" in report


@pytest.mark.integration
def test_full_pipeline_dry_run_report_references_summary(workspace):
    """dry-run-report.json contains the workflow summary inline."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    report = json.loads(
        (workspace["gen"] / "dry-run-report.json").read_text(encoding="utf-8")
    )
    assert "summary" in report
    assert report["summary"]["status"] == "completed"


@pytest.mark.integration
def test_full_pipeline_workflow_summary_lists_all_steps(workspace):
    """workflow-summary.json lists all five pipeline steps."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    summary = json.loads(
        (workspace["gen"] / "workflow-summary.json").read_text(encoding="utf-8")
    )
    expected_steps = {
        "detect_changes",
        "generate_docs",
        "validate_docs",
        "scan_secrets",
        "backup_docs",
    }
    actual_steps = set(summary.get("workflow_steps", []))
    assert expected_steps == actual_steps


@pytest.mark.integration
def test_full_pipeline_produces_audit_log(workspace):
    """Pipeline writes at least one NDJSON entry to the audit log."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    audit_log = workspace["gen"] / "audit-log.ndjson"
    assert audit_log.exists(), "Audit log was not created"
    lines = [ln for ln in audit_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) > 0, "Audit log is empty"
    # Each line must be valid JSON with a 'step' field
    for line in lines:
        event = json.loads(line)
        assert "step" in event
        assert "status" in event


@pytest.mark.integration
def test_full_pipeline_audit_log_contains_expected_steps(workspace):
    """Audit log records events for detect_changes, generate_docs, and workflow_summary."""
    run_script("run_workflow.py", {"DRY_RUN": "true", "BASE_REF": "HEAD"})
    audit_log = workspace["gen"] / "audit-log.ndjson"
    events = [
        json.loads(ln)
        for ln in audit_log.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    recorded_steps = {e["step"] for e in events}
    for expected in ("detect_changes", "generate_docs", "workflow_summary"):
        assert expected in recorded_steps, f"Missing audit event for step: {expected}"


@pytest.mark.integration
def test_full_pipeline_normal_mode_exits_zero_when_no_changes(workspace):
    """Normal mode (DRY_RUN=false) completes without error when there are no git changes."""
    result = run_script("run_workflow.py", {"DRY_RUN": "false", "BASE_REF": "HEAD"})
    # The pipeline may fail at create_pr (no token), but run_workflow.py itself
    # only runs the core steps; it should still exit 0 unless a core step fails.
    assert result.returncode == 0, (
        f"Core pipeline failed unexpectedly.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
