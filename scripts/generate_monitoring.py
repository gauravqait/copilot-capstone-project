#!/usr/bin/env python3
"""Aggregate audit NDJSON into monitoring-friendly metrics JSON."""

import json
from collections import defaultdict
from pathlib import Path


AUDIT_LOG = Path("docs/generated/audit-log.ndjson")
METRICS_OUT = Path("docs/generated/monitoring-metrics.json")


def main() -> None:
    metrics = {
        "total_events": 0,
        "by_step": {},
        "last_event": None,
    }

    if not AUDIT_LOG.exists():
        METRICS_OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(json.dumps(metrics, indent=2))
        return

    counts = defaultdict(lambda: {"ok": 0, "failed": 0, "other": 0, "total": 0})

    with AUDIT_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            metrics["total_events"] += 1
            step = ev.get("step", "unknown")
            status = ev.get("status", "other")
            bucket = "other"
            if status.lower() in ("passed", "ok", "completed", "success"):
                bucket = "ok"
            elif status.lower() in ("failed", "error"):
                bucket = "failed"
            counts[step][bucket] += 1
            counts[step]["total"] += 1
            metrics["last_event"] = ev

    metrics["by_step"] = counts
    METRICS_OUT.parent.mkdir(parents=True, exist_ok=True)
    METRICS_OUT.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
