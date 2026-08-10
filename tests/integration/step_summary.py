#!/usr/bin/env python3
"""Print a Markdown summary table from the integration test report JSON.

Used by the GitHub Actions integration-test workflow to write a step
summary to GITHUB_STEP_SUMMARY without requiring heredoc syntax in YAML.

Usage:
    python tests/integration/step_summary.py >> "$GITHUB_STEP_SUMMARY"
"""

import json
import sys
from pathlib import Path

REPORT_PATH = Path("docs/generated/integration-report.json")


def main() -> None:
    if not REPORT_PATH.exists():
        print("Integration report not found; skipping summary.", file=sys.stderr)
        sys.exit(0)

    r = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    s = r["summary"]

    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Total  | {s['total']} |")
    print(f"| Passed | {s['passed']} |")
    print(f"| Failed | {s['failed']} |")
    print(f"| Skipped | {s['skipped']} |")
    print(f"| Pass rate | {s['pass_rate']}% |")


if __name__ == "__main__":
    main()
