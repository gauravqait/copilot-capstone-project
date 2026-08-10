"""Top-level pytest configuration: ensures the project root is on sys.path
for all test modules and sets the working directory to the project root."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent


def pytest_configure(config):
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def set_project_cwd(monkeypatch):
    """Run every test with CWD set to the project root."""
    monkeypatch.chdir(PROJECT_ROOT)
