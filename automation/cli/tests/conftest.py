"""Shared test configuration and helpers."""
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root directory."""
    # tests/conftest.py -> tests/ -> cli/ -> automation/ -> repo root
    return Path(__file__).resolve().parents[3]
