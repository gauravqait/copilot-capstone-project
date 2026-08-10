"""Integration tests for scripts/backup_docs.py (backup and rollback).

Verifies that the backup stage:
- Creates a timestamped backup directory with a manifest
- Skips gracefully when docs/output is empty
- Restores files correctly from the most recent backup
- Reports the correct status in the result JSON
- Handles rollback when no backups exist
"""

import json
import subprocess
import sys
import pytest

from tests.integration.conftest import base_env, PROJECT_ROOT


def run_backup(output_dir, backup_root, command="backup", extra_env=None):
    env = base_env(**(extra_env or {}))
    return subprocess.run(
        [
            sys.executable,
            "scripts/backup_docs.py",
            command,
            "--output-dir", str(output_dir),
            "--backup-root", str(backup_root),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


@pytest.mark.integration
def test_backup_creates_backup_directory(workspace, tmp_path):
    """Backup creates a timestamped directory containing copied files."""
    backup_root = tmp_path / "backups"
    doc = workspace["out"] / "README.generated.md"
    doc.write_text("# Generated README\n\nContent here.\n", encoding="utf-8")

    result = run_backup(workspace["out"], backup_root)
    assert result.returncode == 0, f"stderr: {result.stderr}"

    backup_dirs = [
        d for d in backup_root.iterdir()
        if d.is_dir() and d.name.startswith("backup-")
    ]
    assert len(backup_dirs) == 1


@pytest.mark.integration
def test_backup_creates_manifest_file(workspace, tmp_path):
    """Backup writes a backup-manifest.json inside the backup directory."""
    backup_root = tmp_path / "backups"
    doc = workspace["out"] / "API.generated.md"
    doc.write_text("# Generated API\n\nContent here.\n", encoding="utf-8")

    run_backup(workspace["out"], backup_root)

    backup_dirs = list(backup_root.iterdir())
    backup_dir = next(d for d in backup_dirs if d.is_dir() and d.name.startswith("backup-"))
    manifest_path = backup_dir / "backup-manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert "created_at" in manifest
    assert "files" in manifest
    assert "backup_dir" in manifest
    assert "API.generated.md" in manifest["files"]


@pytest.mark.integration
def test_backup_creates_latest_backup_pointer(workspace, tmp_path):
    """Backup creates a latest-backup.json pointer in the backup root."""
    backup_root = tmp_path / "backups"
    doc = workspace["out"] / "doc.md"
    doc.write_text("# Doc\n\nContent here.\n", encoding="utf-8")

    run_backup(workspace["out"], backup_root)

    latest = backup_root / "latest-backup.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert "files" in data


@pytest.mark.integration
def test_backup_skips_when_output_is_empty(workspace, tmp_path):
    """Backup reports status=skipped when docs/output has no files."""
    backup_root = tmp_path / "backups"
    # output_dir is empty (workspace fixture ensures this)

    result = run_backup(workspace["out"], backup_root)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["status"] == "skipped"


@pytest.mark.integration
def test_rollback_restores_original_content(workspace, tmp_path):
    """Rollback restores the file content that was present at backup time."""
    backup_root = tmp_path / "backups"
    doc = workspace["out"] / "doc.md"
    original_content = "# Original\n\nOriginal content.\n"
    doc.write_text(original_content, encoding="utf-8")

    run_backup(workspace["out"], backup_root)

    # Simulate overwrite
    doc.write_text("# Modified\n\nModified content.\n", encoding="utf-8")

    result = run_backup(workspace["out"], backup_root, command="rollback")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert doc.read_text(encoding="utf-8") == original_content


@pytest.mark.integration
def test_rollback_reports_restored_status(workspace, tmp_path):
    """Rollback result JSON reports status=restored and lists the restored files."""
    backup_root = tmp_path / "backups"
    doc = workspace["out"] / "doc.md"
    doc.write_text("# Doc\n\nContent.\n", encoding="utf-8")

    run_backup(workspace["out"], backup_root)
    result = run_backup(workspace["out"], backup_root, command="rollback")
    data = json.loads(result.stdout)
    assert data["status"] == "restored"
    assert "doc.md" in data["restored_files"]


@pytest.mark.integration
def test_rollback_skips_when_no_backups_exist(workspace, tmp_path):
    """Rollback skips gracefully when no backup directories are found."""
    backup_root = tmp_path / "empty_backups"
    backup_root.mkdir()

    result = run_backup(workspace["out"], backup_root, command="rollback")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["status"] == "skipped"
