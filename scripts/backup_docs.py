#!/usr/bin/env python3
"""Create and restore backups of generated documentation artifacts."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import audit


def list_output_files(output_dir: Path) -> List[Path]:
    if not output_dir.exists():
        return []
    return sorted([path for path in output_dir.iterdir() if path.is_file()])


def backup_docs(output_dir: Path, backup_root: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)

    files_to_backup = list_output_files(output_dir)
    if not files_to_backup:
        return {
            "status": "skipped",
            "reason": "No documentation files found to backup",
            "backup_dir": None,
        }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_dir = backup_root / f"backup-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    copied_files: List[str] = []
    for source_path in files_to_backup:
        destination_path = backup_dir / source_path.name
        shutil.copy2(source_path, destination_path)
        copied_files.append(source_path.name)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(output_dir),
        "backup_dir": str(backup_dir),
        "files": copied_files,
    }
    manifest_path = backup_dir / "backup-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    latest_manifest_path = backup_root / "latest-backup.json"
    latest_manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    result = {
        "status": "created",
        "backup_dir": str(backup_dir),
        "files": copied_files,
        "manifest": str(manifest_path),
    }
    audit.append_event(audit.event_for_step("backup_docs", "passed", {"result": result}))
    return result


def rollback_docs(output_dir: Path, backup_root: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)

    backup_dirs = sorted(
        [path for path in backup_root.iterdir() if path.is_dir() and path.name.startswith("backup-")],
        key=lambda path: path.name,
    )
    if not backup_dirs:
        return {
            "status": "skipped",
            "reason": "No backups available for rollback",
            "restored_files": [],
        }

    latest_backup = backup_dirs[-1]
    manifest_path = latest_backup / "backup-manifest.json"
    if not manifest_path.exists():
        result = {
            "status": "failed",
            "reason": "Latest backup manifest missing",
            "restored_files": [],
        }
        audit.append_event(audit.event_for_step("backup_docs_rollback", "failed", {"result": result}))
        return result

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored_files: List[str] = []
    for file_name in manifest.get("files", []):
        source_path = latest_backup / file_name
        if not source_path.exists():
            continue
        destination_path = output_dir / file_name
        shutil.copy2(source_path, destination_path)
        restored_files.append(file_name)

    result = {
        "status": "restored",
        "backup_dir": str(latest_backup),
        "restored_files": restored_files,
        "manifest": str(manifest_path),
    }
    audit.append_event(audit.event_for_step("backup_docs_rollback", "passed", {"result": result}))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage documentation backups")
    parser.add_argument("command", choices=["backup", "rollback"], help="backup or rollback")
    parser.add_argument("--output-dir", default="docs/output", help="Directory containing generated documentation")
    parser.add_argument("--backup-root", default="docs/backups", help="Directory where backups are stored")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    backup_root = Path(args.backup_root)

    if args.command == "backup":
        result = backup_docs(output_dir, backup_root)
    else:
        result = rollback_docs(output_dir, backup_root)

    print(json.dumps(result, indent=2))
    if result.get("status") == "failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
