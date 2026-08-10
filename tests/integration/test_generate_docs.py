"""Integration tests for scripts/generate_docs.py.

Verifies that the documentation-generation stage:
- Skips gracefully when should_generate_docs is False
- Creates all three expected output files when changes are present
- Writes doc-generation.json with the correct schema
- Handles a missing change-detection.json without crashing
"""

import json
import pytest

from tests.integration.conftest import run_script, PROJECT_ROOT


FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def _write_change_context(gen_dir, should_generate: bool) -> None:
    payload = {
        "base_ref": "HEAD",
        "changed_files": ["scripts/detect_changes.py"] if should_generate else [],
        "should_generate_docs": should_generate,
        "changed_count": 1 if should_generate else 0,
    }
    (gen_dir / "change-detection.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


@pytest.mark.integration
def test_generate_docs_skips_when_no_changes(workspace):
    """generate_docs.py exits 0 and reports status=skipped when no changes."""
    _write_change_context(workspace["gen"], should_generate=False)
    result = run_script("generate_docs.py")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads((workspace["gen"] / "doc-generation.json").read_text(encoding="utf-8"))
    assert data["status"] == "skipped"


@pytest.mark.integration
def test_generate_docs_creates_three_artifacts(workspace):
    """generate_docs.py produces README, API, and ARCHITECTURE files."""
    _write_change_context(workspace["gen"], should_generate=True)
    result = run_script("generate_docs.py")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert (workspace["out"] / "README.generated.md").exists()
    assert (workspace["out"] / "API.generated.md").exists()
    assert (workspace["out"] / "ARCHITECTURE.generated.md").exists()


@pytest.mark.integration
def test_generate_docs_writes_generation_json(workspace):
    """generate_docs.py writes doc-generation.json with status=generated."""
    _write_change_context(workspace["gen"], should_generate=True)
    run_script("generate_docs.py")
    data = json.loads((workspace["gen"] / "doc-generation.json").read_text(encoding="utf-8"))
    assert data["status"] == "generated"
    assert "files" in data
    assert len(data["files"]) == 3
    assert "timestamp" in data


@pytest.mark.integration
def test_generate_docs_files_list_matches_disk(workspace):
    """Files listed in doc-generation.json all exist on disk."""
    _write_change_context(workspace["gen"], should_generate=True)
    run_script("generate_docs.py")
    data = json.loads((workspace["gen"] / "doc-generation.json").read_text(encoding="utf-8"))
    for file_path in data["files"]:
        # Resolve relative paths against the project root to avoid CWD ambiguity
        from pathlib import Path
        abs_path = PROJECT_ROOT / Path(file_path)
        assert abs_path.exists(), f"Listed file missing on disk: {file_path}"


@pytest.mark.integration
def test_generate_docs_missing_context_file(workspace):
    """generate_docs.py exits 0 and skips when change-detection.json is absent."""
    # workspace starts clean – no change-detection.json
    result = run_script("generate_docs.py")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads((workspace["gen"] / "doc-generation.json").read_text(encoding="utf-8"))
    assert data["status"] == "skipped"
