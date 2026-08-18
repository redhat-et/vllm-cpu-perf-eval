"""Dependency installation helpers for cpueval."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.table import Table

from cpueval.paths import get_ansible_dir

SYSTEM_PACKAGES = ["ansible-core", "python3-pip", "git"]

# Status values: True = pass (green ✓), None = skipped (yellow ~), False = fail (red ✗)
_StepResult = Tuple[Optional[bool], str]


def _requirements_path():
    return get_ansible_dir() / "requirements.yml"


def _run_streaming(cmd: List[str], timeout: int) -> Tuple[bool, str]:
    """Print cmd, stream stdout/stderr to the terminal, return (ok, detail)."""
    console = Console()
    console.print(f"[dim]Running:[/dim] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, timeout=timeout)
        if result.returncode == 0:
            return True, "done"
        return False, f"exited {result.returncode} — see output above"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except Exception as e:
        return False, str(e)


def install_system_deps(dry_run: bool = False) -> _StepResult:
    """Install system packages via dnf (RHEL/Fedora only).

    Returns True on success, None when dnf is absent (soft-skip), False on error.
    """
    if not shutil.which("dnf"):
        return None, (
            "dnf not found — skipping (not a RHEL/Fedora system).\n"
            "         On macOS: brew install ansible\n"
            "         On Ubuntu/Debian: sudo apt install -y ansible-core python3-pip git"
        )

    cmd = ["sudo", "dnf", "install", "-y"] + SYSTEM_PACKAGES
    if dry_run:
        return True, f"[dry-run] would run: {' '.join(cmd)}"

    ok, detail = _run_streaming(cmd, timeout=300)
    if ok:
        return True, f"installed: {', '.join(SYSTEM_PACKAGES)}"
    return False, detail


def install_ansible_collections(dry_run: bool = False) -> _StepResult:
    """Install Ansible collections from requirements.yml.

    Returns True on success, False on error.
    """
    req = _requirements_path()
    if not req.exists():
        return False, f"requirements.yml not found: {req}"

    cmd = ["ansible-galaxy", "collection", "install", "-r", str(req)]
    if dry_run:
        return True, f"[dry-run] would run: {' '.join(cmd)}"

    if not shutil.which("ansible-galaxy"):
        return False, (
            "ansible-galaxy not found in PATH — "
            "install ansible-core first (brew/apt/dnf), "
            "then re-run: ./cpueval install --skip-system-deps"
        )

    ok, detail = _run_streaming(cmd, timeout=300)
    if ok:
        return True, "collections installed"
    return False, detail


def _enable_dot_slash_completion(path: Path, prog_name: str) -> None:
    """Register ./prog_name so tab-complete works without putting the repo on PATH.

    Typer's installer only registers the bare command name. Bash already invokes
    $1 (the command being completed); zsh hardcodes prog_name, so we point it
    at ${words[1]} as well.
    """
    text = path.read_text()
    dot = f"./{prog_name}"
    if dot not in text:
        text = re.sub(
            rf"(complete\b[^\n]*\s)({re.escape(prog_name)})(\s*)$",
            rf"\1\2 {dot}\3",
            text,
            count=1,
            flags=re.M,
        )
        text = re.sub(
            rf"^(#compdef\s+)({re.escape(prog_name)})(\s*)$",
            rf"\1\2 {dot}\3",
            text,
            count=1,
            flags=re.M,
        )
        text = re.sub(
            rf"(^compdef\s+\S+\s+)({re.escape(prog_name)})(\s*)$",
            rf"\1\2 {dot}\3",
            text,
            count=1,
            flags=re.M,
        )
    # zsh script invokes the hardcoded binary; use the command being completed
    # so ./cpueval works even when cpueval is not on PATH.
    text = text.replace(
        f"=complete_zsh {prog_name}",
        '=complete_zsh "${words[1]}"',
    )
    path.write_text(text)


def install_shell_completion(dry_run: bool = False) -> _StepResult:
    """Install bash/zsh tab completion for cpueval and ./cpueval.

    Uses the same helper as ``cpueval --install-completion``, then registers
    ``./cpueval`` so completion works from the repo launcher without PATH.
    Unknown shells and detection failures are a soft-skip (do not fail install).
    """
    try:
        import shellingham
        from typer._completion_shared import install as typer_install
    except ImportError as e:
        return False, f"completion helpers not available: {e}"

    try:
        shell, _ = shellingham.detect_shell()
    except Exception:
        return None, (
            "could not detect shell — "
            "run ./cpueval --install-completion from bash/zsh"
        )

    if shell not in ("bash", "zsh"):
        return None, f"{shell} is not supported (bash/zsh only) — skipped"

    if dry_run:
        return True, (
            f"[dry-run] would install {shell} completion for cpueval and ./cpueval"
        )

    try:
        installed_shell, path = typer_install(shell=shell, prog_name="cpueval")
        _enable_dot_slash_completion(path, "cpueval")
        return True, (
            f"{installed_shell} completion at {path} "
            f"(includes ./cpueval) — restart shell: exec {installed_shell}"
        )
    except Exception as e:
        return False, str(e)


def run_install(
    skip_system_deps: bool = False,
    skip_collections: bool = False,
    skip_completion: bool = False,
    dry_run: bool = False,
) -> int:
    """Run the full install sequence.

    Returns:
        Exit code (0 = all enabled steps succeeded or soft-skipped)
    """
    console = Console()
    prefix = "[dim][dry-run][/dim] " if dry_run else ""
    console.print(f"\n[bold cyan]{prefix}cpueval install[/bold cyan]\n")

    steps: List[Tuple[str, object]] = []
    if not skip_system_deps:
        steps.append(("System packages (dnf)", lambda: install_system_deps(dry_run)))
    if not skip_collections:
        steps.append(("Ansible collections", lambda: install_ansible_collections(dry_run)))
    if not skip_completion:
        steps.append(("Shell completion", lambda: install_shell_completion(dry_run)))

    if not steps:
        console.print("[yellow]Nothing to install (all steps skipped).[/yellow]\n")
        return 0

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Step", style="dim", width=28)
    table.add_column("Status", width=12)
    table.add_column("Details")

    rows = []
    any_failed = False
    completion_ready = False
    for step_name, step_fn in steps:
        ok, details = step_fn()
        if ok is False:
            any_failed = True
            symbol, color = "✗", "red"
        elif ok is None:
            symbol, color = "~", "yellow"
        else:
            symbol, color = "✓", "green"
            if step_name == "Shell completion":
                completion_ready = True
        rows.append((step_name, f"[{color}]{symbol}[/{color}]", details))

    console.print()  # blank line after streamed subprocess output
    for row in rows:
        table.add_row(*row)
    console.print(table)

    if not any_failed:
        console.print("\n[green]✓ Install complete[/green]\n")
        if not dry_run:
            console.print("Next step: verify with [bold]cpueval doctor[/bold]")
            if completion_ready:
                console.print(
                    "Enable tab completion in this shell with "
                    "[bold]exec bash[/bold] or [bold]exec zsh[/bold], "
                    "then try [bold]./cpueval <TAB>[/bold]"
                )
            console.print()
        return 0

    console.print("\n[red]✗ Some steps failed — see output above for details[/red]\n")
    return 1
