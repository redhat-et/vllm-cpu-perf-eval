"""Unit tests for cpueval install module."""

import subprocess
from unittest.mock import MagicMock, patch

from cpueval.install import (
    SYSTEM_PACKAGES,
    install_ansible_collections,
    install_system_deps,
    run_install,
)


# ---------------------------------------------------------------------------
# install_system_deps
# ---------------------------------------------------------------------------

def test_install_system_deps_dry_run_no_subprocess(monkeypatch):
    """Dry-run returns True without running any subprocess."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dnf")
    with patch("subprocess.run") as mock_run:
        ok, msg = install_system_deps(dry_run=True)
    assert ok is True
    assert "dry-run" in msg
    mock_run.assert_not_called()


def test_install_system_deps_dry_run_includes_packages(monkeypatch):
    """Dry-run message lists all expected packages."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dnf")
    _, msg = install_system_deps(dry_run=True)
    for pkg in SYSTEM_PACKAGES:
        assert pkg in msg


def test_install_system_deps_no_dnf_skips(monkeypatch):
    """Returns None (soft-skip) with alternative install hints when dnf is absent."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    ok, msg = install_system_deps()
    assert ok is None
    assert "dnf not found" in msg
    assert "skipping" in msg


def test_install_system_deps_no_dnf_hints_brew_and_apt(monkeypatch):
    """Soft-skip message includes macOS and Ubuntu install one-liners."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    _, msg = install_system_deps()
    assert "brew" in msg
    assert "apt" in msg


def test_install_system_deps_success(monkeypatch):
    """Returns True when dnf exits 0."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dnf")
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result):
        ok, msg = install_system_deps()
    assert ok is True
    assert "installed" in msg


def test_install_system_deps_calls_sudo_dnf(monkeypatch):
    """Verifies subprocess is called with the expected sudo dnf command."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dnf")
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        install_system_deps()
    cmd = mock_run.call_args[0][0]
    assert cmd[:4] == ["sudo", "dnf", "install", "-y"]
    for pkg in SYSTEM_PACKAGES:
        assert pkg in cmd


def test_install_system_deps_failure(monkeypatch):
    """Returns False when dnf exits non-zero."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dnf")
    mock_result = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=mock_result):
        ok, msg = install_system_deps()
    assert ok is False
    assert "exited 1" in msg


def test_install_system_deps_timeout(monkeypatch):
    """Returns False when dnf times out."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dnf")
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="dnf", timeout=300)):
        ok, msg = install_system_deps()
    assert ok is False
    assert "timed out" in msg


# ---------------------------------------------------------------------------
# install_ansible_collections
# ---------------------------------------------------------------------------

def test_install_ansible_collections_dry_run_no_subprocess(tmp_path, monkeypatch):
    """Dry-run returns True without running any subprocess."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ansible-galaxy")
    with patch("subprocess.run") as mock_run:
        ok, msg = install_ansible_collections(dry_run=True)
    assert ok is True
    assert "dry-run" in msg
    mock_run.assert_not_called()


def test_install_ansible_collections_missing_requirements(monkeypatch, tmp_path):
    """Returns False when requirements.yml does not exist."""
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: tmp_path / "missing.yml")
    ok, msg = install_ansible_collections()
    assert ok is False
    assert "not found" in msg


def test_install_ansible_collections_no_ansible_galaxy(tmp_path, monkeypatch):
    """Returns False when ansible-galaxy is not in PATH."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: None)
    ok, msg = install_ansible_collections()
    assert ok is False
    assert "ansible-galaxy not found" in msg


def test_install_ansible_collections_no_galaxy_hints_install(tmp_path, monkeypatch):
    """Missing ansible-galaxy message mentions how to fix it."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: None)
    _, msg = install_ansible_collections()
    assert "ansible-core" in msg


def test_install_ansible_collections_success(tmp_path, monkeypatch):
    """Returns True when ansible-galaxy exits 0."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ansible-galaxy")
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result):
        ok, msg = install_ansible_collections()
    assert ok is True
    assert "installed" in msg


def test_install_ansible_collections_failure(tmp_path, monkeypatch):
    """Returns False when ansible-galaxy exits non-zero."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ansible-galaxy")
    mock_result = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=mock_result):
        ok, msg = install_ansible_collections()
    assert ok is False
    assert "exited 1" in msg


def test_install_ansible_collections_timeout(tmp_path, monkeypatch):
    """Returns False when ansible-galaxy times out."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ansible-galaxy")
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ansible-galaxy", timeout=300)):
        ok, msg = install_ansible_collections()
    assert ok is False
    assert "timed out" in msg


def test_install_ansible_collections_uses_300s_timeout(tmp_path, monkeypatch):
    """ansible-galaxy uses a 300s timeout to handle slow networks."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/ansible-galaxy")
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        install_ansible_collections()
    _, kwargs = mock_run.call_args
    assert kwargs.get("timeout") == 300


# ---------------------------------------------------------------------------
# run_install
# ---------------------------------------------------------------------------

def test_run_install_skip_all_returns_zero():
    """Skipping all steps returns exit code 0 without calling anything."""
    with patch("cpueval.install.install_system_deps") as mock_sys, \
         patch("cpueval.install.install_ansible_collections") as mock_col:
        code = run_install(skip_system_deps=True, skip_collections=True)
    assert code == 0
    mock_sys.assert_not_called()
    mock_col.assert_not_called()


def test_run_install_all_pass_returns_zero():
    """All steps succeeding returns exit code 0."""
    with patch("cpueval.install.install_system_deps", return_value=(True, "ok")), \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")):
        code = run_install()
    assert code == 0


def test_run_install_skipped_step_returns_zero():
    """A skipped (None) step does not cause a non-zero exit."""
    with patch("cpueval.install.install_system_deps", return_value=(None, "skipping")), \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")):
        code = run_install()
    assert code == 0


def test_run_install_one_failure_returns_one():
    """Any failing step returns exit code 1."""
    with patch("cpueval.install.install_system_deps", return_value=(False, "dnf error")), \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")):
        code = run_install()
    assert code == 1


def test_run_install_skip_system_deps_only_calls_collections():
    """--skip-system-deps skips dnf but still installs collections."""
    with patch("cpueval.install.install_system_deps") as mock_sys, \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")):
        run_install(skip_system_deps=True)
    mock_sys.assert_not_called()


def test_run_install_skip_collections_only_calls_system_deps():
    """--skip-collections skips galaxy but still installs system packages."""
    with patch("cpueval.install.install_system_deps", return_value=(True, "ok")), \
         patch("cpueval.install.install_ansible_collections") as mock_col:
        run_install(skip_collections=True)
    mock_col.assert_not_called()


def test_run_install_dry_run_passes_flag():
    """dry_run=True propagates to individual install functions."""
    with patch("cpueval.install.install_system_deps", return_value=(True, "[dry-run] ...")) as mock_sys, \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "[dry-run] ...")) as mock_col:
        run_install(dry_run=True)
    mock_sys.assert_called_once_with(True)
    mock_col.assert_called_once_with(True)
