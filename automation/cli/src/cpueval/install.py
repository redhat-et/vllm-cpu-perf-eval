"""Dependency installation helpers for cpueval."""

import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.table import Table

from cpueval.paths import get_ansible_dir

SYSTEM_PACKAGES = ["ansible-core", "python3-pip", "git"]


def _requirements_path() -> Path:
    return get_ansible_dir() / "requirements.yml"


def install_system_deps(dry_run: bool = False) -> Tuple[bool, str]:
    """Install system packages via dnf (RHEL/Fedora only)."""
    if not shutil.which("dnf"):
        return True, "dnf not found — skipping (not a RHEL/Fedora system)"

    cmd = ["sudo", "dnf", "install", "-y"] + SYSTEM_PACKAGES
    if dry_run:
        return True, f"[dry-run] would run: {' '.join(cmd)}"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return True, f"installed: {', '.join(SYSTEM_PACKAGES)}"
        return False, result.stderr.strip() or result.stdout.strip() or "dnf failed"
    except subprocess.TimeoutExpired:
        return False, "dnf timed out"
    except Exception as e:
        return False, str(e)


def install_ansible_collections(dry_run: bool = False) -> Tuple[bool, str]:
    """Install Ansible collections from requirements.yml."""
    req = _requirements_path()
    if not req.exists():
        return False, f"requirements.yml not found: {req}"

    if not shutil.which("ansible-galaxy"):
        return False, "ansible-galaxy not found in PATH"

    cmd = ["ansible-galaxy", "collection", "install", "-r", str(req)]
    if dry_run:
        return True, f"[dry-run] would run: {' '.join(cmd)}"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, "collections installed"
        return False, result.stderr.strip() or result.stdout.strip() or "ansible-galaxy failed"
    except subprocess.TimeoutExpired:
        return False, "ansible-galaxy timed out"
    except Exception as e:
        return False, str(e)


def run_install(
    skip_system_deps: bool = False,
    skip_collections: bool = False,
    dry_run: bool = False,
) -> int:
    """Run the full install sequence.

    Returns:
        Exit code (0 = all enabled steps succeeded)
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

    all_passed = True
    for step_name, step_fn in steps:
        passed, details = step_fn()
        all_passed = all_passed and passed
        status_symbol = "✓" if passed else "✗"
        status_color = "green" if passed else "red"
        table.add_row(
            step_name,
            f"[{status_color}]{status_symbol}[/{status_color}]",
            details,
        )

    console.print(table)

    if all_passed:
        console.print("\n[green]✓ Install complete[/green]\n")
        if not dry_run:
            console.print("Next step: verify with [bold]cpueval doctor[/bold]\n")
        return 0

    console.print("\n[red]✗ Some steps failed[/red]\n")
    return 1
