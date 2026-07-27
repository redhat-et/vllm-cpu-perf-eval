"""System health checks for cpueval."""

import os
import shutil
import subprocess
from typing import Tuple

from rich.console import Console
from rich.table import Table

from cpueval.paths import get_ansible_dir, get_inventory_path


def check_ansible_playbook() -> Tuple[bool, str]:
    """Check if ansible-playbook is available."""
    if shutil.which("ansible-playbook"):
        try:
            result = subprocess.run(
                ["ansible-playbook", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version = result.stdout.split("\n")[0] if result.returncode == 0 else "unknown"
            return True, version
        except Exception as e:
            return False, str(e)
    return False, "ansible-playbook not found in PATH"


def check_ansible_collections() -> Tuple[bool, str]:
    """Check if required Ansible collections are installed."""
    try:
        result = subprocess.run(
            ["ansible-galaxy", "collection", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if "containers.podman" in result.stdout:
            return True, "containers.podman installed"
        return False, "containers.podman collection not found"
    except Exception as e:
        return False, f"Failed to check collections: {e}"


def check_env_vars() -> Tuple[bool, str]:
    """Check required environment variables for managed mode."""
    required_managed = ["DUT_HOSTNAME", "LOADGEN_HOSTNAME"]
    optional = ["ANSIBLE_SSH_USER", "ANSIBLE_SSH_KEY", "HF_TOKEN"]

    missing = [var for var in required_managed if not os.getenv(var)]

    mode = os.getenv("VLLM_ENDPOINT_MODE", "managed")

    if mode == "external":
        # External mode needs VLLM_ENDPOINT_URL instead
        if not os.getenv("VLLM_ENDPOINT_URL"):
            return False, "VLLM_ENDPOINT_URL required for external mode"
        return True, "external mode configured"

    if missing:
        return False, f"Missing: {', '.join(missing)}"

    warnings = []
    if not os.getenv("HF_TOKEN"):
        warnings.append("HF_TOKEN not set (may be needed for gated models)")

    if warnings:
        return True, f"OK (warnings: {'; '.join(warnings)})"

    return True, "all required vars set"


def check_inventory() -> Tuple[bool, str]:
    """Check if Ansible inventory exists."""
    inventory = get_inventory_path()
    if inventory.exists():
        return True, str(inventory)
    return False, f"Inventory not found: {inventory}"


def ping_hosts(skip_dut_in_external: bool = False) -> Tuple[bool, str]:
    """Ping Ansible hosts to verify connectivity.

    Args:
        skip_dut_in_external: Skip DUT ping in external mode
    """
    mode = os.getenv("VLLM_ENDPOINT_MODE", "managed")

    # In external mode, DUT may not be accessible
    if mode == "external" and skip_dut_in_external:
        return True, "Skipped in external mode (soft-OK)"

    try:
        result = subprocess.run(
            [
                "ansible",
                "-i",
                str(get_inventory_path()),
                "all",
                "-m",
                "ping",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=get_ansible_dir(),
        )

        if result.returncode == 0:
            # Count successful pings
            success_count = result.stdout.count('"ping": "pong"')
            return True, f"{success_count} host(s) reachable"
        else:
            return False, "Some hosts unreachable"
    except subprocess.TimeoutExpired:
        return False, "Ping timeout"
    except Exception as e:
        return False, str(e)


def run_doctor(no_ping: bool = False) -> int:
    """Run system health checks.

    Args:
        no_ping: Skip host ping check

    Returns:
        Exit code (0 = all checks passed)
    """
    console = Console()

    console.print("\n[bold cyan]cpueval system health check[/bold cyan]\n")

    checks = [
        ("ansible-playbook", check_ansible_playbook),
        ("Ansible collections", check_ansible_collections),
        ("Inventory file", check_inventory),
        ("Environment vars", check_env_vars),
    ]

    if not no_ping:
        mode = os.getenv("VLLM_ENDPOINT_MODE", "managed")
        skip_dut = mode == "external"
        checks.append(
            (
                "Host connectivity",
                lambda: ping_hosts(skip_dut_in_external=skip_dut),
            )
        )

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Check", style="dim", width=20)
    table.add_column("Status", width=12)
    table.add_column("Details")

    all_passed = True

    for check_name, check_func in checks:
        passed, details = check_func()
        all_passed = all_passed and passed

        status_emoji = "✓" if passed else "✗"
        status_color = "green" if passed else "red"

        table.add_row(
            check_name,
            f"[{status_color}]{status_emoji}[/{status_color}]",
            details,
        )

    console.print(table)

    if all_passed:
        console.print("\n[green]✓ All checks passed[/green]\n")
        return 0
    else:
        console.print("\n[red]✗ Some checks failed[/red]\n")
        console.print("[yellow]Tip:[/yellow] Set required environment variables:")
        console.print("  export DUT_HOSTNAME=<dut-host>")
        console.print("  export LOADGEN_HOSTNAME=<loadgen-host>")
        console.print("  export HF_TOKEN=<token>  # for gated models")
        console.print("\nFor external mode:")
        console.print("  export VLLM_ENDPOINT_MODE=external")
        console.print("  export VLLM_ENDPOINT_URL=http://host:8000\n")
        return 1
