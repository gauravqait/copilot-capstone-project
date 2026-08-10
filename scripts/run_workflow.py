#!/usr/bin/env python3
"""Coordinate the core workflow execution steps for documentation generation."""
"""orchestrates the core workflow execution steps in sequence."""

import json
import os
import subprocess
import sys
from pathlib import Path
import time
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import audit
def run_backup_step() -> dict:
    start = time.time()
    result = subprocess.run(
        [sys.executable, "scripts/backup_docs.py", "backup"],
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed_ms = int((time.time() - start) * 1000)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    status = "passed" if result.returncode == 0 else "failed"
    try:
        payload = json.loads(stdout) if stdout else {"status": status}
    except Exception:
        payload = {"status": status, "raw_stdout": stdout}

    audit.append_event(audit.event_for_step("backup_docs", status, {"duration_ms": elapsed_ms, "result": payload}))

    if result.returncode != 0:
        raise RuntimeError("Backup step failed")
    return payload


def run_step(command: list[str], step_name: str) -> None:
    print(f"Running: {step_name}")
    start = time.time()
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    elapsed_ms = int((time.time() - start) * 1000)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    status = "passed" if result.returncode == 0 else "failed"
    # Record audit event for this step
    try:
        details = json.loads(stdout) if stdout else {}
    except Exception:
        details = {"raw_stdout": stdout}
    audit.append_event(audit.event_for_step(step_name, status, {"duration_ms": elapsed_ms, "details": details}))

    if result.returncode != 0:
        raise RuntimeError(f"{step_name} failed with exit code {result.returncode}")


def main() -> None:
    base_ref = os.environ.get("BASE_REF", "origin/main")
    os.environ["BASE_REF"] = base_ref

    workflow_dir = Path("docs/generated")
    workflow_dir.mkdir(parents=True, exist_ok=True)

    # Set a workflow run id for audit events
    os.environ.setdefault("WORKFLOW_RUN_ID", datetime.utcnow().strftime("run-%Y%m%d%H%M%S"))

    try:
        run_step([sys.executable, "scripts/detect_changes.py"], "detect_changes")
        run_step([sys.executable, "scripts/generate_docs.py"], "generate_docs")
        run_step([sys.executable, "scripts/validate_docs.py"], "validate_docs")
        run_step([sys.executable, "scripts/scan_secrets.py"], "scan_secrets")
        backup_result = run_backup_step()

        summary = {
            "status": "completed",
            "base_ref": base_ref,
            "workflow_steps": [
                "detect_changes",
                "generate_docs",
                "validate_docs",
                "scan_secrets",
                "backup_docs",
            ],
            "backup": backup_result,
        }
        Path("docs/generated/workflow-summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
        audit.append_event(audit.event_for_step("workflow_summary", "passed", summary))
        # Generate monitoring metrics
        subprocess.run([sys.executable, "scripts/generate_monitoring.py"], check=False)
    except Exception as exc:
        err = {"error": str(exc)}
        audit.append_event(audit.event_for_step("workflow_summary", "failed", err))
        raise


if __name__ == "__main__":
    main()
