#!/usr/bin/env python3
"""Perform a basic secret-scanning gate over generated documentation artifacts."""
"""This file is responsible for checking the documentation for secrets."""
"""checks: “Does the documentation contain anything sensitive?"""
"""scan_secrets.py = security check [i.e A file can be “safe” but still poor quality.]"""

import json
import re
import sys
from pathlib import Path
from typing import List, Tuple


def scan_files(files: List[str]) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    patterns = [
        r"ghp_[A-Za-z0-9]{36}",
        r"github_pat_[A-Za-z0-9_]+",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z\-_]{35}",
    ]

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            issues.append(f"Missing file during secret scan: {file_path}")
            continue

        content = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            if re.search(pattern, content):
                issues.append(f"Potential secret detected in {file_path}")

    return len(issues) == 0, issues


def main() -> None:
    result_path = Path("docs/generated/doc-generation.json")
    if not result_path.exists():
        output = {"status": "skipped", "issues": ["No generation output detected"]}
        Path("docs/generated/secret-scan-result.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(output, indent=2))
        return

    result = json.loads(result_path.read_text(encoding="utf-8"))
    files = result.get("files", [])
    passed, issues = scan_files(files)

    output = {
        "status": "passed" if passed else "failed",
        "issues": issues,
        "scanned_files": files,
    }
    Path("docs/generated/secret-scan-result.json").write_text(json.dumps(output, indent=2), encoding="utf-8")

    if not passed:
        print(json.dumps(output, indent=2), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
