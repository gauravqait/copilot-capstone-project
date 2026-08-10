#!/usr/bin/env python3
"""Simple structured audit logging for the documentation-sync workflow.

This module appends newline-delimited JSON (NDJSON) events to
`docs/generated/audit-log.ndjson` and exposes a helper to produce
monitoring-friendly summary files.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


AUDIT_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "docs/generated/audit-log.ndjson"))
AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_event(event: Dict[str, Any]) -> None:
    payload = dict(event)
    payload.setdefault("timestamp", _now_iso())
    # Ensure run_id exists
    payload.setdefault("run_id", os.environ.get("WORKFLOW_RUN_ID", "manual"))
    # Write NDJSON line
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")


def event_for_step(step: str, status: str, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    ev = {"step": step, "status": status}
    if details:
        ev["details"] = details
    return ev
