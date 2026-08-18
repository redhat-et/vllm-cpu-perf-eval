"""Regression checks for the repo-root ./cpueval launcher."""

from pathlib import Path


def _launcher() -> str:
    # tests/ -> cli/ -> automation/ -> repo root
    return (Path(__file__).resolve().parents[3] / "cpueval").read_text()


def test_launcher_requires_python_310():
    """Launcher must refuse the RHEL 9 / UBI 9 default python3 (3.9)."""
    text = _launcher()
    assert "3, 10" in text
    assert "python3.12" in text
    assert "python3.11" in text
    assert "python3.10" in text


def test_launcher_bootstraps_python312_via_dnf():
    """On dnf hosts without 3.10+, first run installs python3.12."""
    text = _launcher()
    assert "dnf install -y python3.12" in text
    assert "microdnf install -y python3.12" in text
    assert "UBI 9" in text
    assert "_cpueval_pkg" in text
    assert "command -v sudo" in text
