#!/usr/bin/env python3
"""Coordinate the core workflow execution steps for documentation generation."""
"""orchestrates the core workflow execution steps in sequence."""

import json
import os
import subprocess
import sys
from pathlib import Path


def run_backup_step() -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/backup_docs.py", "backup"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError("Backup step failed")
    return json.loads(result.stdout)


def run_step(command: list[str], description: str) -> None:
    print(f"Running: {description}")
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"{description} failed with exit code {result.returncode}")


def main() -> None:
    base_ref = os.environ.get("BASE_REF", "origin/main")
    os.environ["BASE_REF"] = base_ref

    workflow_dir = Path("docs/generated")
    workflow_dir.mkdir(parents=True, exist_ok=True)

    run_step([sys.executable, "scripts/detect_changes.py"], "Detecting changed files")
    run_step([sys.executable, "scripts/generate_docs.py"], "Generating documentation artifacts")
    run_step([sys.executable, "scripts/validate_docs.py"], "Validating generated documentation")
    run_step([sys.executable, "scripts/scan_secrets.py"], "Scanning generated documentation for secrets")
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


if __name__ == "__main__":
    main()
