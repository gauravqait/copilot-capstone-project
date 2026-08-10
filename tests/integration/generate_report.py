#!/usr/bin/env python3
"""Generate a JSON integration report from pytest JUnit XML output.

Usage:
    python tests/integration/generate_report.py [--xml PATH] [--out PATH]

Reads the JUnit XML produced by pytest --junit-xml and writes:
- docs/generated/integration-report.json   (machine-readable)

Exits 1 if any tests failed or errored.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_XML = PROJECT_ROOT / "docs" / "generated" / "integration-test-results.xml"
DEFAULT_OUT = PROJECT_ROOT / "docs" / "generated" / "integration-report.json"


def parse_junit_xml(xml_path: Path) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Support both <testsuites> and bare <testsuite> root elements
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    else:
        suites = [root]

    tests = []
    total = failures = errors = skipped = 0

    for suite in suites:
        for case in suite.findall("testcase"):
            classname = case.get("classname", "")
            name = case.get("name", "")
            duration = round(float(case.get("time", "0")), 3)

            failure_el = case.find("failure")
            error_el = case.find("error")
            skip_el = case.find("skipped")

            if failure_el is not None:
                status = "failed"
                message = failure_el.get("message", failure_el.text or "")
                failures += 1
            elif error_el is not None:
                status = "error"
                message = error_el.get("message", error_el.text or "")
                errors += 1
            elif skip_el is not None:
                status = "skipped"
                message = skip_el.get("message", "")
                skipped += 1
            else:
                status = "passed"
                message = ""

            total += 1
            tests.append(
                {
                    "classname": classname,
                    "name": name,
                    "status": status,
                    "duration_sec": duration,
                    "message": message,
                }
            )

    passed = total - failures - errors - skipped
    pass_rate = round(passed / total * 100, 1) if total > 0 else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
            "pass_rate": pass_rate,
        },
        "tests": tests,
    }


def print_summary(report: dict) -> None:
    s = report["summary"]
    width = 40
    print("=" * width)
    print("  Integration Test Report")
    print("=" * width)
    print(f"  Total   : {s['total']}")
    print(f"  Passed  : {s['passed']}")
    print(f"  Failed  : {s['failed']}")
    print(f"  Errors  : {s['errors']}")
    print(f"  Skipped : {s['skipped']}")
    print(f"  Pass rate: {s['pass_rate']}%")
    print("=" * width)

    if s["failed"] or s["errors"]:
        print("\nFailed / Errored tests:")
        for t in report["tests"]:
            if t["status"] in ("failed", "error"):
                print(f"  [{t['status'].upper()}] {t['classname']}::{t['name']}")
                if t["message"]:
                    first_line = t["message"].splitlines()[0]
                    print(f"         {first_line}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate integration test report")
    parser.add_argument(
        "--xml",
        default=str(DEFAULT_XML),
        help="Path to pytest JUnit XML file",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help="Path to write the JSON report",
    )
    args = parser.parse_args()

    xml_path = Path(args.xml)
    if not xml_path.exists():
        print(
            f"ERROR: JUnit XML not found at {xml_path}\n"
            "Run pytest with --junit-xml=<path> first.",
            file=sys.stderr,
        )
        sys.exit(1)

    report = parse_junit_xml(xml_path)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {out_path}")

    print_summary(report)

    s = report["summary"]
    if s["failed"] > 0 or s["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
