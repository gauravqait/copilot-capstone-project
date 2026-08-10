#!/usr/bin/env python3
"""This file is responsible for checking the quality of the generated documentation."""
"""It performs validation checks on the generated markdown files and scans for potential secrets in the content."""
"""checks: “Is the documentation good enough?”"""
"""validate_docs.py = quality check [i.e A file can be “well written” but still unsafe.]"""

import json
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import audit


def load_generation_result() -> dict:
    path = Path("docs/generated/doc-generation.json")
    if not path.exists():
        return {"status": "skipped", "files": []}
    return json.loads(path.read_text(encoding="utf-8"))


def validate_markdown_files(files: List[str]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            issues.append(f"Missing file: {file_path}")
            continue

        content = path.read_text(encoding="utf-8")
        if not content.strip():
            issues.append(f"Empty content: {file_path}")
        if "TODO" in content.upper():
            issues.append(f"Placeholder content found in {file_path}")
        if len(content.splitlines()) < 3:
            issues.append(f"Insufficient content in {file_path}")

    return len(issues) == 0, issues


def validate_secret_scan(files: List[str]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    sensitive_patterns = [
        r"ghp_[A-Za-z0-9]{36}",
        r"github_pat_[A-Za-z0-9_]+",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z\-_]{35}",
    ]

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in sensitive_patterns:
            if re.search(pattern, content):
                issues.append(f"Potential secret detected in {file_path}")

    return len(issues) == 0, issues


def main() -> None:
    start = time.time()
    result = load_generation_result()
    files = result.get("files", [])

    markdown_ok, markdown_issues = validate_markdown_files(files)
    secrets_ok, secret_issues = validate_secret_scan(files)

    issues = markdown_issues + secret_issues
    passed = markdown_ok and secrets_ok

    output = {
        "status": "passed" if passed else "failed",
        "generated_files": files,
        "issues": issues,
        "checks": {
            "markdown_validation": markdown_ok,
            "secret_scan": secrets_ok,
        },
    }

    output_path = Path("docs/generated/validation-result.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    elapsed_ms = int((time.time() - start) * 1000)
    status = "passed" if passed else "failed"
    audit.append_event(audit.event_for_step("validate_docs", status, {"duration_ms": elapsed_ms, "issues": issues}))

    if not passed:
        print(json.dumps(output, indent=2), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
