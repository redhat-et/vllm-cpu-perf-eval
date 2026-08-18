"""Unit tests for cpueval install module."""

import subprocess
import sys
from unittest.mock import MagicMock, patch

from cpueval.install import (
    ANSIBLE_PACKAGE,
    DNF_BASE_PACKAGES,
    PIP_ANSIBLE_SPEC,
    SYSTEM_PACKAGES,
    _enable_dot_slash_completion,
    install_ansible_collections,
    install_shell_completion,
    install_system_deps,
    run_install,
)


def _disable_venv_ansible(monkeypatch):
    """Keep tests from picking up a real ansible-galaxy next to sys.executable."""
    monkeypatch.setattr("cpueval.install._venv_bin", lambda name: None)


def _patch_which(monkeypatch, *, dnf=True, sudo=True):
    """PATH stub that reveals ansible-galaxy after a successful ansible-core install."""
    state = {"galaxy": False}

    def which(name):
        if name in {"ansible-galaxy", "ansible-playbook"}:
            return f"/usr/bin/{name}" if state["galaxy"] else None
        if name == "dnf" and dnf:
            return "/usr/bin/dnf"
        if name == "sudo" and sudo:
            return "/usr/bin/sudo"
        return None

    monkeypatch.setattr("shutil.which", which)
    _disable_venv_ansible(monkeypatch)
    return state


def _run_installing_ansible(
    state, *, dnf_base_rc=0, dnf_ansible_rc=0, pip_rc=0, timeout=False
):
    """subprocess.run stub: mark galaxy installed after a successful dnf/pip ansible-core."""

    def run(cmd, **kwargs):
        if timeout:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)
        result = MagicMock()
        is_pip = "pip" in cmd
        is_dnf_ansible = (not is_pip) and ANSIBLE_PACKAGE in cmd
        if is_pip:
            result.returncode = pip_rc
        elif is_dnf_ansible:
            result.returncode = dnf_ansible_rc
        else:
            result.returncode = dnf_base_rc
        if result.returncode == 0 and (is_pip or is_dnf_ansible):
            state["galaxy"] = True
        return result

    return run


# ---------------------------------------------------------------------------
# install_system_deps
# ---------------------------------------------------------------------------

def test_install_system_deps_dry_run_no_subprocess(monkeypatch):
    """Dry-run returns True without running any subprocess."""
    _patch_which(monkeypatch)
    with patch("subprocess.run") as mock_run:
        ok, msg = install_system_deps(dry_run=True)
    assert ok is True
    assert "dry-run" in msg
    mock_run.assert_not_called()


def test_install_system_deps_dry_run_includes_packages(monkeypatch):
    """Dry-run message lists dnf packages and the pip ansible-core fallback."""
    _patch_which(monkeypatch)
    _, msg = install_system_deps(dry_run=True)
    for pkg in SYSTEM_PACKAGES:
        assert pkg in msg
    assert "pip install" in msg
    assert PIP_ANSIBLE_SPEC in msg


def test_install_system_deps_no_dnf_uses_pip(monkeypatch):
    """Without dnf, ansible-core is installed via pip into the venv."""
    state = _patch_which(monkeypatch, dnf=False)
    with patch(
        "subprocess.run", side_effect=_run_installing_ansible(state)
    ) as mock_run:
        ok, msg = install_system_deps()
    assert ok is True
    assert "pip" in msg
    pip_cmd = mock_run.call_args[0][0]
    assert pip_cmd == [sys.executable, "-m", "pip", "install", PIP_ANSIBLE_SPEC]


def test_install_system_deps_no_dnf_pip_failure_hints_brew_apt(monkeypatch):
    """If pip cannot install ansible-core, the error mentions brew/apt."""
    state = _patch_which(monkeypatch, dnf=False)
    with patch("subprocess.run", side_effect=_run_installing_ansible(state, pip_rc=1)):
        ok, msg = install_system_deps()
    assert ok is False
    assert "brew" in msg
    assert "apt" in msg


def test_install_system_deps_success(monkeypatch):
    """Returns True when dnf ansible-core succeeds (no pip fallback)."""
    state = _patch_which(monkeypatch)
    with patch("subprocess.run", side_effect=_run_installing_ansible(state)) as mock_run:
        ok, msg = install_system_deps()
    assert ok is True
    assert "dnf: ansible-core" in msg
    pip_cmds = [c[0][0] for c in mock_run.call_args_list if "pip" in c[0][0]]
    assert not pip_cmds


def test_install_system_deps_calls_sudo_dnf(monkeypatch):
    """Verifies subprocess is called with the expected sudo dnf command."""
    state = _patch_which(monkeypatch, sudo=True)
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    with patch("subprocess.run", side_effect=_run_installing_ansible(state)) as mock_run:
        install_system_deps()
    cmd = mock_run.call_args_list[0][0][0]
    assert cmd[:4] == ["sudo", "dnf", "install", "-y"]
    for pkg in DNF_BASE_PACKAGES:
        assert pkg in cmd


def test_install_system_deps_root_omits_sudo(monkeypatch):
    """Containers running as root must not require sudo."""
    state = _patch_which(monkeypatch)
    monkeypatch.setattr("os.geteuid", lambda: 0)
    with patch("subprocess.run", side_effect=_run_installing_ansible(state)) as mock_run:
        install_system_deps()
    cmd = mock_run.call_args_list[0][0][0]
    assert cmd[:3] == ["dnf", "install", "-y"]
    assert "sudo" not in cmd


def test_install_system_deps_no_sudo_binary_omits_sudo(monkeypatch):
    """If sudo is not installed, run dnf directly (root UBI images)."""
    state = _patch_which(monkeypatch, sudo=False)
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    with patch("subprocess.run", side_effect=_run_installing_ansible(state)) as mock_run:
        install_system_deps()
    cmd = mock_run.call_args_list[0][0][0]
    assert cmd[:3] == ["dnf", "install", "-y"]
    assert "sudo" not in cmd


def test_install_system_deps_dnf_ansible_missing_falls_back_to_pip(monkeypatch):
    """UBI 9: dnf has no ansible-core, so pip install into the venv."""
    state = _patch_which(monkeypatch)
    monkeypatch.setattr("os.geteuid", lambda: 0)
    with patch(
        "subprocess.run",
        side_effect=_run_installing_ansible(state, dnf_ansible_rc=1),
    ) as mock_run:
        ok, msg = install_system_deps()
    assert ok is True
    assert "pip" in msg
    pip_cmds = [c[0][0] for c in mock_run.call_args_list if "pip" in c[0][0]]
    assert pip_cmds
    assert pip_cmds[0] == [sys.executable, "-m", "pip", "install", PIP_ANSIBLE_SPEC]


def test_install_system_deps_failure(monkeypatch):
    """Returns False when dnf and pip both fail."""
    state = _patch_which(monkeypatch)
    with patch(
        "subprocess.run",
        side_effect=_run_installing_ansible(state, dnf_base_rc=1, dnf_ansible_rc=1, pip_rc=1),
    ):
        ok, msg = install_system_deps()
    assert ok is False


def test_install_system_deps_timeout(monkeypatch):
    """Returns False when dnf times out."""
    _patch_which(monkeypatch)
    with patch(
        "subprocess.run",
        side_effect=_run_installing_ansible({"galaxy": False}, timeout=True),
    ):
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
    _disable_venv_ansible(monkeypatch)
    ok, msg = install_ansible_collections()
    assert ok is False
    assert "ansible-galaxy not found" in msg


def test_install_ansible_collections_no_galaxy_hints_install(tmp_path, monkeypatch):
    """Missing ansible-galaxy message mentions the correct recovery flag."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: None)
    _disable_venv_ansible(monkeypatch)
    _, msg = install_ansible_collections()
    assert "ansible-core" in msg
    assert "--skip-system-deps" in msg


def test_install_ansible_collections_uses_venv_galaxy(tmp_path, monkeypatch):
    """ansible-galaxy from the cpueval venv is used when it is not on PATH."""
    req = tmp_path / "requirements.yml"
    req.write_text("collections: []\n")
    monkeypatch.setattr("cpueval.install._requirements_path", lambda: req)
    monkeypatch.setattr("shutil.which", lambda _: None)
    monkeypatch.setattr(
        "cpueval.install._venv_bin",
        lambda name: f"/venv/bin/{name}" if name == "ansible-galaxy" else None,
    )
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        ok, msg = install_ansible_collections()
    assert ok is True
    assert mock_run.call_args[0][0][0] == "/venv/bin/ansible-galaxy"


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
    _disable_venv_ansible(monkeypatch)
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
