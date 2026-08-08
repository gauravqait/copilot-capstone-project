#!/usr/bin/env python3
"""Detect which files have changed and determine whether documentation generation should run."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List


def get_changed_files(base_ref: str) -> List[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError as exc:
        print(f"Failed to detect changes: {exc}", file=sys.stderr)
        return []


def should_generate_docs(changed_files: List[str]) -> bool:
    if not changed_files:
        return False

    ignored_paths = {".github/workflows", "docs/backups", "docs/generated", "tests"}
    relevant_files = [
        path for path in changed_files if not any(path.startswith(prefix) for prefix in ignored_paths)
    ]
    return bool(relevant_files)


def main() -> None:
    base_ref = os.environ.get("BASE_REF", "origin/main")
    changed_files = get_changed_files(base_ref)
    should_run = should_generate_docs(changed_files)

    output = {
        "base_ref": base_ref,
        "changed_files": changed_files,
        "should_generate_docs": should_run,
        "changed_count": len(changed_files),
    }

    output_path = Path("docs/generated/change-detection.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
