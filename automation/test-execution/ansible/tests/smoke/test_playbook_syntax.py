#!/usr/bin/env python3
"""Smoke tests for Ansible playbook syntax and configuration."""
import pytest
import yaml
from pathlib import Path
import subprocess

ANSIBLE_DIR = Path(__file__).parent.parent.parent


@pytest.mark.smoke
class TestPlaybookSyntax:
    """Validate Ansible playbook syntax."""

    def test_all_playbooks_valid_yaml(self):
        """All playbooks should be valid YAML."""
        playbooks = list(ANSIBLE_DIR.glob("*.yml"))
        assert len(playbooks) > 0, "No playbooks found"

        errors = []
        for playbook in playbooks:
            try:
                with open(playbook) as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                errors.append(f"{playbook.name}: {e}")

        assert not errors, f"YAML validation errors:\n" + "\n".join(errors)

    def test_ansible_syntax_check(self):
        """Run ansible-playbook --syntax-check on critical playbooks."""
        playbooks = [
            "llm-benchmark.yml",
            "llm-benchmark-concurrent-load.yml",
            "llm-benchmark-auto.yml",
            "start-vllm-server.yml",
            "health-check.yml",
            "setup-platform.yml",
            "embedding-benchmark.yml",
        ]

        errors = []
        for playbook in playbooks:
            playbook_path = ANSIBLE_DIR / playbook
            if not playbook_path.exists():
                errors.append(f"{playbook}: file not found")
                continue

            result = subprocess.run(
                ["ansible-playbook", "--syntax-check", str(playbook_path)],
                cwd=ANSIBLE_DIR,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append(
                    f"{playbook}: syntax check failed\n{result.stderr}"
                )

        assert not errors, f"Syntax check errors:\n" + "\n".join(errors)

    def test_inventory_files_valid_yaml(self):
        """All inventory files should be valid YAML."""
        inventory_dir = ANSIBLE_DIR / "inventory"
        inventory_files = [
            inventory_dir / "hosts.yml",
            inventory_dir / "group_vars" / "all" / "credentials.yml",
            inventory_dir / "group_vars" / "all" / "endpoints.yml",
            inventory_dir / "group_vars" / "all" / "test-workloads.yml",
            inventory_dir / "group_vars" / "all" / "hardware-profiles.yml",
            inventory_dir / "group_vars" / "all" / "infrastructure.yml",
            inventory_dir / "group_vars" / "all" / "benchmark-tools.yml",
            inventory_dir / "group_vars" / "dut" / "main.yml",
            inventory_dir / "group_vars" / "load_generator" / "main.yml",
        ]

        errors = []
        for inv_file in inventory_files:
            if not inv_file.exists():
                # Example files are OK to skip
                if "examples" not in str(inv_file):
                    errors.append(f"{inv_file.name}: file not found at {inv_file}")
                continue

            try:
                with open(inv_file) as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                errors.append(f"{inv_file.name}: {e}")

        assert not errors, f"Inventory YAML validation errors:\n" + "\n".join(errors)

    def test_role_defaults_valid_yaml(self):
        """All role defaults files should be valid YAML."""
        roles_dir = ANSIBLE_DIR / "roles"
        if not roles_dir.exists():
            pytest.skip("Roles directory not found")

        defaults_files = list(roles_dir.glob("*/defaults/main.yml"))
        assert len(defaults_files) > 0, "No role defaults files found"

        errors = []
        for defaults_file in defaults_files:
            try:
                with open(defaults_file) as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                errors.append(f"{defaults_file.parent.parent.name}: {e}")

        assert not errors, f"Role defaults YAML validation errors:\n" + "\n".join(errors)


@pytest.mark.smoke
class TestRoleStructure:
    """Validate Ansible role structure."""

    def test_all_roles_have_required_structure(self):
        """Each role should have expected directories."""
        roles_dir = ANSIBLE_DIR / "roles"
        if not roles_dir.exists():
            pytest.skip("Roles directory not found")

        roles = [d for d in roles_dir.iterdir() if d.is_dir()]
        assert len(roles) > 0, "No roles found"

        errors = []
        for role in roles:
            # At minimum, roles should have tasks directory
            # (defaults are optional, some roles have just tasks)
            has_tasks_dir = (role / "tasks").exists()

            if not has_tasks_dir:
                errors.append(
                    f"{role.name}: missing tasks directory"
                )

        assert not errors, f"Role structure errors:\n" + "\n".join(errors)


@pytest.mark.smoke
class TestFilterPlugins:
    """Validate custom Ansible filter plugins."""

    def test_filter_plugins_importable(self):
        """Filter plugins should be importable Python modules."""
        filter_plugins_dir = ANSIBLE_DIR / "filter_plugins"
        if not filter_plugins_dir.exists():
            pytest.skip("Filter plugins directory not found")

        filter_files = list(filter_plugins_dir.glob("*.py"))
        # Exclude __init__.py
        filter_files = [f for f in filter_files if f.name != "__init__.py"]

        assert len(filter_files) > 0, "No filter plugins found"

        errors = []
        for filter_file in filter_files:
            try:
                # Just check syntax by compiling
                with open(filter_file) as f:
                    compile(f.read(), filter_file, 'exec')
            except SyntaxError as e:
                errors.append(f"{filter_file.name}: {e}")

        assert not errors, f"Filter plugin syntax errors:\n" + "\n".join(errors)
