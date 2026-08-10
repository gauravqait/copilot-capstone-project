"""Shared fixtures for integration tests.

Each test that uses the ``workspace`` fixture receives isolated
``docs/generated`` and ``docs/output`` directories: existing files are
saved before the test and restored after, so tests cannot interfere with
each other or with repository artifacts.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers available to test modules via import
# ---------------------------------------------------------------------------

def base_env(**overrides) -> dict:
    """Return a subprocess environment with safe defaults for integration tests."""
    env = {
        **os.environ,
        "AUDIT_LOG_PATH": str(PROJECT_ROOT / "docs" / "generated" / "audit-log.ndjson"),
        "WORKFLOW_RUN_ID": "integration-test-run",
        # Fake GitHub env vars – prevent accidental real API calls
        "GITHUB_TOKEN": "integration-test-token",
        "GITHUB_REPOSITORY": "test-owner/test-repo",
        "GITHUB_SHA": "0000000000000000000000000000000000000000",
        "GITHUB_RUN_ID": "0",
        "GITHUB_SERVER_URL": "https://github.com",
        # Default to dry-run off; individual tests override as needed
        "DRY_RUN": "false",
    }
    env.update(overrides)
    return env


def run_script(script_name: str, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    """Run a project script as a subprocess from the project root."""
    env = base_env(**(env_overrides or {}))
    return subprocess.run(
        [sys.executable, f"scripts/{script_name}"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def workspace():
    """Provide isolated docs/generated and docs/output directories.

    Saves all existing files before the test and restores them after,
    regardless of test outcome.
    """
    gen_dir = PROJECT_ROOT / "docs" / "generated"
    out_dir = PROJECT_ROOT / "docs" / "output"

    for directory in (gen_dir, out_dir):
        directory.mkdir(parents=True, exist_ok=True)

    # Save current state
    saved_gen = {f.name: f.read_bytes() for f in gen_dir.iterdir() if f.is_file()}
    saved_out = {f.name: f.read_bytes() for f in out_dir.iterdir() if f.is_file()}

    # Clear dirs so each test starts clean
    for f in gen_dir.iterdir():
        if f.is_file():
            f.unlink()
    for f in out_dir.iterdir():
        if f.is_file():
            f.unlink()

    yield {"gen": gen_dir, "out": out_dir, "root": PROJECT_ROOT}

    # Remove test-created files (guard against the directory being deleted by the test itself)
    for directory in (gen_dir, out_dir):
        if directory.exists():
            for f in directory.iterdir():
                if f.is_file():
                    f.unlink()
        else:
            directory.mkdir(parents=True, exist_ok=True)

    # Restore saved files
    for name, content in saved_gen.items():
        (gen_dir / name).write_bytes(content)
    for name, content in saved_out.items():
        (out_dir / name).write_bytes(content)
