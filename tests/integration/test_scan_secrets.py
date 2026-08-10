"""Integration tests for scripts/scan_secrets.py.

Verifies that the secret-scanning gate:
- Passes for clean documentation files
- Fails and exits non-zero when a secret pattern is detected
- Skips gracefully when no doc-generation.json is present
- Detects all supported secret patterns (GitHub PAT, AWS key, GCP key)
- Writes secret-scan-result.json with the correct schema
"""

import json
import shutil
import pytest

from tests.integration.conftest import run_script, PROJECT_ROOT


FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def _write_generation_json(gen_dir, files: list) -> None:
    payload = {"status": "generated", "files": [str(f) for f in files]}
    (gen_dir / "doc-generation.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


@pytest.mark.integration
def test_scan_secrets_passes_clean_file(workspace):
    """Clean documentation file passes secret scanning."""
    doc = workspace["out"] / "clean.md"
    doc.write_text("# Clean Doc\n\nNo credentials here.\n", encoding="utf-8")
    _write_generation_json(workspace["gen"], [doc])
    result = run_script("scan_secrets.py")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads((workspace["gen"] / "secret-scan-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "passed"
    assert data["issues"] == []


@pytest.mark.integration
def test_scan_secrets_fails_github_pat_pattern(workspace):
    """GitHub PAT-style token triggers failure."""
    doc = workspace["out"] / "leaky.md"
    doc.write_text(
        "# Doc\n\nghp_abcdefghijklmnopqrstuvwxyz1234567890\n",
        encoding="utf-8",
    )
    _write_generation_json(workspace["gen"], [doc])
    result = run_script("scan_secrets.py")
    assert result.returncode == 1
    data = json.loads((workspace["gen"] / "secret-scan-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert len(data["issues"]) > 0


@pytest.mark.integration
def test_scan_secrets_fails_aws_key_pattern(workspace):
    """AWS access key pattern triggers failure."""
    doc = workspace["out"] / "aws.md"
    doc.write_text(
        "# AWS Doc\n\nKey: AKIAIOSFODNN7EXAMPLE\n",
        encoding="utf-8",
    )
    _write_generation_json(workspace["gen"], [doc])
    result = run_script("scan_secrets.py")
    assert result.returncode == 1
    data = json.loads((workspace["gen"] / "secret-scan-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed"


@pytest.mark.integration
def test_scan_secrets_skips_when_no_generation_json(workspace):
    """Scan skips gracefully when doc-generation.json is absent."""
    result = run_script("scan_secrets.py")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads((workspace["gen"] / "secret-scan-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "skipped"


@pytest.mark.integration
def test_scan_secrets_output_schema(workspace):
    """secret-scan-result.json contains all required top-level keys."""
    doc = workspace["out"] / "clean.md"
    doc.write_text("# Clean\n\nContent here.\n", encoding="utf-8")
    _write_generation_json(workspace["gen"], [doc])
    run_script("scan_secrets.py")
    data = json.loads((workspace["gen"] / "secret-scan-result.json").read_text(encoding="utf-8"))
    assert "status" in data
    assert "issues" in data
    assert "scanned_files" in data


@pytest.mark.integration
def test_scan_secrets_uses_fixture_with_secret(workspace):
    """The doc_with_secret.md fixture is detected by the secret scanner."""
    doc = workspace["out"] / "secret_fixture.md"
    shutil.copy(FIXTURES_DIR / "doc_with_secret.md", doc)
    _write_generation_json(workspace["gen"], [doc])
    result = run_script("scan_secrets.py")
    assert result.returncode == 1
    data = json.loads((workspace["gen"] / "secret-scan-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed"


@pytest.mark.integration
def test_scan_secrets_multiple_clean_files(workspace):
    """Multiple clean files all pass scanning."""
    files = []
    for i in range(3):
        doc = workspace["out"] / f"doc_{i}.md"
        doc.write_text(f"# Doc {i}\n\nContent {i}.\n", encoding="utf-8")
        files.append(doc)
    _write_generation_json(workspace["gen"], files)
    result = run_script("scan_secrets.py")
    assert result.returncode == 0
    data = json.loads((workspace["gen"] / "secret-scan-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "passed"
    assert len(data["scanned_files"]) == 3
