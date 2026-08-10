"""Integration tests for scripts/detect_changes.py.

Verifies that the change-detection stage:
- Runs without errors
- Writes change-detection.json with the required schema
- Correctly reports zero changes when diffing HEAD against HEAD
- Marks should_generate_docs=False when no relevant files changed
"""

import json
import pytest

from tests.integration.conftest import run_script


@pytest.mark.integration
def test_detect_changes_exits_zero(workspace):
    """detect_changes.py exits 0 under normal conditions."""
    result = run_script("detect_changes.py", {"BASE_REF": "HEAD"})
    assert result.returncode == 0, f"stderr: {result.stderr}"


@pytest.mark.integration
def test_detect_changes_creates_output_file(workspace):
    """detect_changes.py writes change-detection.json to docs/generated/."""
    run_script("detect_changes.py", {"BASE_REF": "HEAD"})
    output_file = workspace["gen"] / "change-detection.json"
    assert output_file.exists(), "change-detection.json was not created"


@pytest.mark.integration
def test_detect_changes_output_schema(workspace):
    """change-detection.json contains all required top-level keys."""
    run_script("detect_changes.py", {"BASE_REF": "HEAD"})
    data = json.loads((workspace["gen"] / "change-detection.json").read_text(encoding="utf-8"))
    assert "base_ref" in data
    assert "changed_files" in data
    assert "should_generate_docs" in data
    assert "changed_count" in data
    assert isinstance(data["changed_files"], list)
    assert isinstance(data["should_generate_docs"], bool)


@pytest.mark.integration
def test_detect_changes_head_to_head_has_no_diff(workspace):
    """Diffing HEAD against HEAD always produces zero changed files."""
    run_script("detect_changes.py", {"BASE_REF": "HEAD"})
    data = json.loads((workspace["gen"] / "change-detection.json").read_text(encoding="utf-8"))
    assert data["changed_files"] == []
    assert data["changed_count"] == 0


@pytest.mark.integration
def test_detect_changes_no_diff_means_skip_generation(workspace):
    """Zero changed files implies should_generate_docs is False."""
    run_script("detect_changes.py", {"BASE_REF": "HEAD"})
    data = json.loads((workspace["gen"] / "change-detection.json").read_text(encoding="utf-8"))
    if data["changed_files"] == []:
        assert data["should_generate_docs"] is False


@pytest.mark.integration
def test_detect_changes_stdout_is_valid_json(workspace):
    """stdout of detect_changes.py is valid JSON matching the output file."""
    result = run_script("detect_changes.py", {"BASE_REF": "HEAD"})
    stdout_data = json.loads(result.stdout)
    file_data = json.loads((workspace["gen"] / "change-detection.json").read_text(encoding="utf-8"))
    assert stdout_data["changed_count"] == file_data["changed_count"]
    assert stdout_data["should_generate_docs"] == file_data["should_generate_docs"]
