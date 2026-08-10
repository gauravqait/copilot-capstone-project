"""Integration tests for scripts/validate_docs.py.

Verifies that the validation stage:
- Passes when generated documentation is well-formed
- Fails and exits non-zero when a secret pattern is present
- Fails when file content is empty or too short
- Writes validation-result.json with the correct schema
- Passes gracefully when there are no generated files
"""

import json
import shutil
import pytest

from tests.integration.conftest import run_script, PROJECT_ROOT


FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def _setup_doc_generation_json(gen_dir, files: list) -> None:
    payload = {"status": "generated", "files": [str(f) for f in files]}
    (gen_dir / "doc-generation.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


@pytest.mark.integration
def test_validate_docs_passes_with_valid_content(workspace):
    """Validation passes for a well-formed markdown file."""
    doc = workspace["out"] / "README.generated.md"
    doc.write_text(
        "# Generated README\n\nThis file was generated.\nIt has enough content.\n",
        encoding="utf-8",
    )
    _setup_doc_generation_json(workspace["gen"], [doc])
    result = run_script("validate_docs.py")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "passed"
    assert data["issues"] == []


@pytest.mark.integration
def test_validate_docs_fails_with_secret_pattern(workspace):
    """Validation fails when a file contains a GitHub PAT-style token."""
    doc = workspace["out"] / "leaky.md"
    # ghp_ followed by exactly 36 alphanumeric chars triggers the regex
    doc.write_text(
        "# Doc\n\nghp_abcdefghijklmnopqrstuvwxyz1234567890\n\nContent.\n",
        encoding="utf-8",
    )
    _setup_doc_generation_json(workspace["gen"], [doc])
    result = run_script("validate_docs.py")
    assert result.returncode == 1
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert any("secret" in issue.lower() for issue in data["issues"])


@pytest.mark.integration
def test_validate_docs_fails_empty_file(workspace):
    """Validation fails when a listed file has empty content."""
    doc = workspace["out"] / "empty.md"
    doc.write_text("", encoding="utf-8")
    _setup_doc_generation_json(workspace["gen"], [doc])
    result = run_script("validate_docs.py")
    assert result.returncode == 1
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed"


@pytest.mark.integration
def test_validate_docs_fails_insufficient_content(workspace):
    """Validation fails when file has fewer than 3 lines."""
    doc = workspace["out"] / "short.md"
    doc.write_text("# Title\n", encoding="utf-8")  # only 1 line
    _setup_doc_generation_json(workspace["gen"], [doc])
    result = run_script("validate_docs.py")
    assert result.returncode == 1
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed"


@pytest.mark.integration
def test_validate_docs_skips_cleanly_with_no_generation(workspace):
    """Validation exits 0 and passes when no doc-generation.json is present."""
    # workspace is clean – no doc-generation.json
    result = run_script("validate_docs.py")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "passed"


@pytest.mark.integration
def test_validate_docs_output_schema(workspace):
    """validation-result.json contains all required top-level keys."""
    doc = workspace["out"] / "README.generated.md"
    doc.write_text(
        "# Generated README\n\nThis file was generated.\nIt has enough content.\n",
        encoding="utf-8",
    )
    _setup_doc_generation_json(workspace["gen"], [doc])
    run_script("validate_docs.py")
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert "status" in data
    assert "issues" in data
    assert "checks" in data
    assert "markdown_validation" in data["checks"]
    assert "secret_scan" in data["checks"]


@pytest.mark.integration
def test_validate_docs_uses_fixture_sample_doc(workspace):
    """The sample_doc.md fixture passes validation without issues."""
    doc = workspace["out"] / "sample.md"
    shutil.copy(FIXTURES_DIR / "sample_doc.md", doc)
    _setup_doc_generation_json(workspace["gen"], [doc])
    result = run_script("validate_docs.py")
    assert result.returncode == 0
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "passed"


@pytest.mark.integration
def test_validate_docs_detects_fixture_with_secret(workspace):
    """The doc_with_secret.md fixture is correctly flagged by validation."""
    doc = workspace["out"] / "secret.md"
    shutil.copy(FIXTURES_DIR / "doc_with_secret.md", doc)
    _setup_doc_generation_json(workspace["gen"], [doc])
    result = run_script("validate_docs.py")
    assert result.returncode == 1
    data = json.loads((workspace["gen"] / "validation-result.json").read_text(encoding="utf-8"))
    assert data["status"] == "failed"
