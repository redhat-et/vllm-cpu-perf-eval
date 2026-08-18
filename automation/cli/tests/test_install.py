"""Unit tests for cpueval install module."""

import subprocess
from unittest.mock import MagicMock, patch

from cpueval.install import (
    SYSTEM_PACKAGES,
    _enable_dot_slash_completion,
    install_ansible_collections,
    install_shell_completion,
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
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        install_system_deps()
    cmd = mock_run.call_args[0][0]
    assert cmd[:4] == ["sudo", "dnf", "install", "-y"]
    for pkg in SYSTEM_PACKAGES:
        assert pkg in cmd


def test_install_system_deps_root_omits_sudo(monkeypatch):
    """Containers running as root must not require sudo."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/dnf")
    monkeypatch.setattr("os.geteuid", lambda: 0)
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        install_system_deps()
    cmd = mock_run.call_args[0][0]
    assert cmd[:3] == ["dnf", "install", "-y"]
    assert "sudo" not in cmd


def test_install_system_deps_no_sudo_binary_omits_sudo(monkeypatch):
    """If sudo is not installed, run dnf directly (root UBI images)."""
    monkeypatch.setattr("os.geteuid", lambda: 1000)

    def which(name):
        if name == "dnf":
            return "/usr/bin/dnf"
        return None

    monkeypatch.setattr("shutil.which", which)
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        install_system_deps()
    cmd = mock_run.call_args[0][0]
    assert cmd[:3] == ["dnf", "install", "-y"]
    assert "sudo" not in cmd


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
    """Missing ansible-galaxy message mentions the correct recovery flag."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: None)
    _, msg = install_ansible_collections()
    assert "ansible-core" in msg
    assert "--skip-system-deps" in msg


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
         patch("cpueval.install.install_ansible_collections") as mock_col, \
         patch("cpueval.install.install_shell_completion") as mock_comp:
        code = run_install(
            skip_system_deps=True, skip_collections=True, skip_completion=True
        )
    assert code == 0
    mock_sys.assert_not_called()
    mock_col.assert_not_called()
    mock_comp.assert_not_called()


def test_run_install_all_pass_returns_zero():
    """All steps succeeding returns exit code 0."""
    with patch("cpueval.install.install_system_deps", return_value=(True, "ok")), \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")), \
         patch("cpueval.install.install_shell_completion", return_value=(True, "ok")):
        code = run_install()
    assert code == 0


def test_run_install_skipped_step_returns_zero():
    """A skipped (None) step does not cause a non-zero exit."""
    with patch("cpueval.install.install_system_deps", return_value=(None, "skipping")), \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")), \
         patch("cpueval.install.install_shell_completion", return_value=(True, "ok")):
        code = run_install()
    assert code == 0


def test_run_install_one_failure_returns_one():
    """Any failing step returns exit code 1."""
    with patch("cpueval.install.install_system_deps", return_value=(False, "dnf error")), \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")), \
         patch("cpueval.install.install_shell_completion", return_value=(True, "ok")):
        code = run_install()
    assert code == 1


def test_run_install_skip_system_deps_only_calls_collections():
    """--skip-system-deps skips dnf but still installs collections."""
    with patch("cpueval.install.install_system_deps") as mock_sys, \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")), \
         patch("cpueval.install.install_shell_completion", return_value=(True, "ok")):
        run_install(skip_system_deps=True)
    mock_sys.assert_not_called()


def test_run_install_skip_collections_only_calls_system_deps():
    """--skip-collections skips galaxy but still installs system packages."""
    with patch("cpueval.install.install_system_deps", return_value=(True, "ok")), \
         patch("cpueval.install.install_ansible_collections") as mock_col, \
         patch("cpueval.install.install_shell_completion", return_value=(True, "ok")):
        run_install(skip_collections=True)
    mock_col.assert_not_called()


def test_run_install_skip_completion_does_not_call_completion():
    """--skip-completion skips shell completion setup."""
    with patch("cpueval.install.install_system_deps", return_value=(True, "ok")), \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "ok")), \
         patch("cpueval.install.install_shell_completion") as mock_comp:
        run_install(skip_completion=True)
    mock_comp.assert_not_called()


def test_run_install_skip_deps_still_installs_completion():
    """Skipping dnf and galaxy still sets up tab completion."""
    with patch("cpueval.install.install_system_deps") as mock_sys, \
         patch("cpueval.install.install_ansible_collections") as mock_col, \
         patch("cpueval.install.install_shell_completion", return_value=(True, "ok")) as mock_comp:
        code = run_install(skip_system_deps=True, skip_collections=True)
    assert code == 0
    mock_sys.assert_not_called()
    mock_col.assert_not_called()
    mock_comp.assert_called_once_with(False)


def test_run_install_dry_run_passes_flag():
    """dry_run=True propagates to individual install functions."""
    with patch("cpueval.install.install_system_deps", return_value=(True, "[dry-run] ...")) as mock_sys, \
         patch("cpueval.install.install_ansible_collections", return_value=(True, "[dry-run] ...")) as mock_col, \
         patch("cpueval.install.install_shell_completion", return_value=(True, "[dry-run] ...")) as mock_comp:
        run_install(dry_run=True)
    mock_sys.assert_called_once_with(True)
    mock_col.assert_called_once_with(True)
    mock_comp.assert_called_once_with(True)


def test_run_install_dry_run_succeeds_without_ansible_galaxy(tmp_path, monkeypatch):
    """dry_run=True completes the full install preview even when ansible-galaxy is absent."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: None)
    with patch("cpueval.install.install_shell_completion", return_value=(True, "[dry-run] ...")):
        code = run_install(dry_run=True)
    assert code == 0


# ---------------------------------------------------------------------------
# shell completion
# ---------------------------------------------------------------------------

_BASH_SCRIPT = """\
_cpueval_completion() {
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \\
                   COMP_CWORD=$COMP_CWORD \\
                   _CPUEVAL_COMPLETE=complete_bash $1 ) )
    return 0
}

complete -o default -F _cpueval_completion cpueval
"""

_ZSH_SCRIPT = """\
#compdef cpueval

_cpueval_completion() {
    eval $(env _TYPER_COMPLETE_ARGS="${words[1,$CURRENT]}" _CPUEVAL_COMPLETE=complete_zsh cpueval)
}

compdef _cpueval_completion cpueval
"""


def test_enable_dot_slash_completion_bash(tmp_path):
    """Bash complete line also registers ./cpueval."""
    path = tmp_path / "cpueval.sh"
    path.write_text(_BASH_SCRIPT)
    _enable_dot_slash_completion(path, "cpueval")
    text = path.read_text()
    assert "complete -o default -F _cpueval_completion cpueval ./cpueval" in text


def test_enable_dot_slash_completion_bash_idempotent(tmp_path):
    """Running the patch twice does not duplicate ./cpueval."""
    path = tmp_path / "cpueval.sh"
    path.write_text(_BASH_SCRIPT)
    _enable_dot_slash_completion(path, "cpueval")
    _enable_dot_slash_completion(path, "cpueval")
    assert path.read_text().count("./cpueval") == 1


def test_enable_dot_slash_completion_zsh(tmp_path):
    """Zsh registers ./cpueval and invokes the command being completed."""
    path = tmp_path / "_cpueval"
    path.write_text(_ZSH_SCRIPT)
    _enable_dot_slash_completion(path, "cpueval")
    text = path.read_text()
    assert "#compdef cpueval ./cpueval" in text
    assert "compdef _cpueval_completion cpueval ./cpueval" in text
    assert "${words[1]}" in text
    assert "=complete_zsh cpueval" not in text


def test_install_shell_completion_dry_run_no_write(monkeypatch):
    """Dry-run reports the plan without calling Typer's installer."""
    monkeypatch.setattr(
        "shellingham.detect_shell", lambda: ("bash", "/bin/bash")
    )
    with patch("typer._completion_shared.install") as mock_install:
        ok, msg = install_shell_completion(dry_run=True)
    assert ok is True
    assert "dry-run" in msg
    assert "./cpueval" in msg
    mock_install.assert_not_called()


def test_install_shell_completion_unknown_shell_skips(monkeypatch):
    """Unsupported shells are a soft-skip, not a failure."""
    monkeypatch.setattr(
        "shellingham.detect_shell", lambda: ("fish", "/usr/bin/fish")
    )
    ok, msg = install_shell_completion()
    assert ok is None
    assert "fish" in msg


def test_install_shell_completion_detect_failure_skips(monkeypatch):
    """A detection error is a soft-skip with a recovery hint."""
    def _raise():
        raise RuntimeError("no shell")

    monkeypatch.setattr("shellingham.detect_shell", _raise)
    ok, msg = install_shell_completion()
    assert ok is None
    assert "--install-completion" in msg


def test_install_shell_completion_success_patches_script(tmp_path, monkeypatch):
    """Successful install writes Typer's script then registers ./cpueval."""
    script = tmp_path / "cpueval.sh"
    script.write_text(_BASH_SCRIPT)

    monkeypatch.setattr(
        "shellingham.detect_shell", lambda: ("bash", "/bin/bash")
    )

    def fake_install(shell=None, prog_name=None, complete_var=None):
        return shell, script

    monkeypatch.setattr("typer._completion_shared.install", fake_install)
    ok, msg = install_shell_completion()
    assert ok is True
    assert "bash" in msg
    assert "./cpueval" in script.read_text()
    assert "exec bash" in msg
