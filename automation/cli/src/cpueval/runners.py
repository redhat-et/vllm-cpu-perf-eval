"""Runners for executing Ansible playbooks and bash scripts."""

import json
import subprocess
import sys
import shlex
import stat
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from cpueval.paths import get_ansible_dir, get_inventory_path, get_playbook_path, get_repo_root


def build_ansible_command(
    playbook: str,
    extra_vars: Dict[str, Any],
    ansible_args: List[str] = None,
) -> List[str]:
    """Build ansible-playbook command.

    Args:
        playbook: Playbook filename (e.g., 'llm-benchmark-concurrent-load.yml')
        extra_vars: Extra variables to pass with -e
        ansible_args: Additional raw ansible-playbook arguments

    Returns:
        Command as list of strings
    """
    cmd = [
        "ansible-playbook",
        "-i",
        str(get_inventory_path()),
        str(get_playbook_path(playbook)),
    ]

    # Add extra vars
    for key, value in extra_vars.items():
        # Handle complex types (lists, dicts) by JSON encoding
        if isinstance(value, (list, dict)):
            cmd.extend(["-e", f'{key}={json.dumps(value)}'])
        else:
            cmd.extend(["-e", f"{key}={value}"])

    # Add raw ansible args
    if ansible_args:
        cmd.extend(ansible_args)

    return cmd


def run_ansible(
    playbook: str,
    extra_vars: Dict[str, Any],
    ansible_args: List[str] = None,
    dry_run: bool = False,
) -> int:
    """Run an Ansible playbook.

    Args:
        playbook: Playbook filename
        extra_vars: Extra variables to pass
        ansible_args: Additional ansible-playbook arguments
        dry_run: If True, print command instead of running

    Returns:
        Exit code
    """
    cmd = build_ansible_command(playbook, extra_vars, ansible_args)

    if dry_run:
        print(shlex.join(cmd))
        return 0

    # Run from ansible directory
    return subprocess.run(
        cmd, cwd=get_ansible_dir(), stdout=sys.stdout, stderr=sys.stderr
    ).returncode


def build_script_command(
    script_path: str, args: List[str] = None
) -> List[str]:
    """Build script command.

    Args:
        script_path: Path to script relative to repo root
        args: Script arguments (can be a string if direct mode)

    Returns:
        Command as list of strings
    """
    cmd = [str(get_repo_root() / script_path)]

    if args:
        # If args is a single string with spaces, split it (for positional scripts)
        if isinstance(args, str):
            cmd.extend(args.split())
        elif isinstance(args, list):
            cmd.extend(args)

    return cmd


def run_script(
    script_path: str, args: List[str] = None, dry_run: bool = False
) -> int:
    """Run a bash script.

    Args:
        script_path: Path to script relative to repo root
        args: Script arguments
        dry_run: If True, print command instead of running

    Returns:
        Exit code
    """
    cmd = build_script_command(script_path, args)

    if dry_run:
        print(shlex.join(cmd))
        return 0

    # Make script executable if needed
    script_full_path = get_repo_root() / script_path
    if script_full_path.exists():
        import stat
        current_mode = script_full_path.stat().st_mode
        script_full_path.chmod(
            current_mode | stat.S_IXUSR | stat.S_IXGRP
        )

    return subprocess.run(
        cmd, cwd=get_repo_root(), stdout=sys.stdout, stderr=sys.stderr
    ).returncode


def load_profile(profile_name: str, profiles_dir: Path) -> Dict[str, Any]:
    """Load a CPU pinning profile from YAML.

    Args:
        profile_name: Profile name (without .yaml extension)
        profiles_dir: Directory containing profiles

    Returns:
        Profile extra vars as dict

    Raises:
        FileNotFoundError: If profile doesn't exist
        ValueError: If profile is invalid YAML
    """
    profile_path = profiles_dir / f"{profile_name}.yaml"

    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    try:
        with open(profile_path) as f:
            data = yaml.safe_load(f)
            return data or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid profile YAML: {e}")


def merge_extra_vars(
    suite_defaults: Dict[str, Any],
    profile_vars: Dict[str, Any],
    cli_vars: Dict[str, Any],
    extra_pairs: List[str],
    extra_vars_file: Optional[str],
) -> Dict[str, Any]:
    """Merge extra vars from multiple sources in precedence order.

    Precedence: suite defaults < profile < CLI flags < --extra < --extra-vars-file

    Args:
        suite_defaults: Default vars from suite YAML
        profile_vars: Vars from --profile
        cli_vars: Vars from CLI flags (--model, --cores, etc.)
        extra_pairs: KEY=VAL pairs from --extra
        extra_vars_file: Path to extra vars YAML/JSON file

    Returns:
        Merged extra vars dict

    Raises:
        FileNotFoundError: If extra_vars_file doesn't exist
        ValueError: If --extra pair is missing '='
    """
    result = {}

    # Start with suite defaults
    result.update(suite_defaults)

    # Apply profile
    result.update(profile_vars)

    # Apply CLI flags
    result.update(cli_vars)

    # Apply --extra pairs
    for pair in extra_pairs or []:
        if "=" not in pair:
            raise ValueError(
                f"Invalid --extra format: '{pair}' (expected KEY=VALUE)"
            )
        key, value = pair.split("=", 1)
        # Try to parse as JSON for complex types
        try:
            result[key] = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            result[key] = value

    # Apply extra vars file (highest precedence)
    if extra_vars_file:
        file_path = Path(extra_vars_file)
        if not file_path.exists():
            raise FileNotFoundError(
                f"Extra vars file not found: {extra_vars_file}"
            )

        with open(file_path) as f:
            if file_path.suffix == ".json":
                file_vars = json.load(f)
            else:
                file_vars = yaml.safe_load(f)

            # Validate it's a mapping
            if file_vars is not None and not isinstance(file_vars, dict):
                raise ValueError(
                    f"Extra vars file must contain a mapping, not {type(file_vars).__name__}"
                )

            result.update(file_vars or {})

    return result
