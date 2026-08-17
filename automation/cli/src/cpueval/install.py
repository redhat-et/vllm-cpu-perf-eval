"""Dependency installation helpers for cpueval."""

import shutil
import subprocess
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


def run_install(
    skip_system_deps: bool = False,
    skip_collections: bool = False,
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

    if not steps:
        console.print("[yellow]Nothing to install (all steps skipped).[/yellow]\n")
        return 0

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Step", style="dim", width=28)
    table.add_column("Status", width=12)
    table.add_column("Details")

    rows = []
    any_failed = False
    for step_name, step_fn in steps:
        ok, details = step_fn()
        if ok is False:
            any_failed = True
            symbol, color = "✗", "red"
        elif ok is None:
            symbol, color = "~", "yellow"
        else:
            symbol, color = "✓", "green"
        rows.append((step_name, f"[{color}]{symbol}[/{color}]", details))

    console.print()  # blank line after streamed subprocess output
    for row in rows:
        table.add_row(*row)
    console.print(table)

    if not any_failed:
        console.print("\n[green]✓ Install complete[/green]\n")
        if not dry_run:
            console.print("Next step: verify with [bold]cpueval doctor[/bold]\n")
        return 0

    console.print("\n[red]✗ Some steps failed — see output above for details[/red]\n")
    return 1
