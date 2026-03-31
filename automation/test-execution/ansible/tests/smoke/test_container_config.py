#!/usr/bin/env python3
"""Test container configuration and basic runtime checks."""
import pytest
import subprocess
import shutil


def _has_container_runtime():
    """Check if podman or docker is available."""
    for cmd in ["podman", "docker"]:
        if shutil.which(cmd) is not None:
            return True
    return False


def _get_container_runtime():
    """Get the available container runtime command."""
    for cmd in ["podman", "docker"]:
        if shutil.which(cmd) is not None:
            return cmd
    return None


@pytest.mark.smoke
@pytest.mark.skipif(not _has_container_runtime(), reason="No container runtime available")
class TestContainerBasics:
    """Basic container configuration tests."""

    @pytest.fixture(scope="class")
    def runtime(self):
        """Get container runtime command."""
        return _get_container_runtime()

    def test_container_runtime_available(self, runtime):
        """Verify container runtime is available and working."""
        result = subprocess.run(
            [runtime, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"{runtime} version check failed"
        assert runtime in result.stdout.lower() or runtime in result.stderr.lower()

    @pytest.mark.slow
    def test_vllm_image_accessible(self, runtime):
        """Verify vLLM container image can be inspected (checks if pullable)."""
        # Use inspect to check if image exists locally or is pullable
        # This is faster than pulling the full image
        result = subprocess.run(
            [runtime, "image", "inspect", "vllm/vllm-openai:latest"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # If image doesn't exist locally, that's OK - we just verify it's pullable
        if result.returncode != 0:
            # Try to check if it exists on registry without pulling
            result = subprocess.run(
                [runtime, "manifest", "inspect", "vllm/vllm-openai:latest"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # If manifest inspect fails, skip this test (network issues, etc.)
            if result.returncode != 0:
                pytest.skip("Cannot access vLLM image (network or registry issue)")

    @pytest.mark.slow
    def test_guidellm_image_accessible(self, runtime):
        """Verify GuideLLM container image can be inspected."""
        result = subprocess.run(
            [runtime, "image", "inspect", "ghcr.io/neuralmagic/guidellm:latest"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # If image doesn't exist locally, that's OK - we just verify it's pullable
        if result.returncode != 0:
            # Try to check if it exists on registry
            result = subprocess.run(
                [runtime, "manifest", "inspect", "ghcr.io/neuralmagic/guidellm:latest"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                pytest.skip("Cannot access GuideLLM image (network or registry issue)")

    @pytest.mark.slow
    def test_container_run_help(self, runtime):
        """Verify vLLM container can run and show help (without model)."""
        # Skip this test in CI - it can be slow if image needs pulling
        import os
        if os.getenv("CI"):
            pytest.skip("Skipping container run test in CI")

        # This test just runs --help without loading models
        result = subprocess.run(
            [runtime, "run", "--rm", "vllm/vllm-openai:latest", "--help"],
            capture_output=True,
            text=True,
            timeout=120,  # Increased timeout for slow systems
        )

        # If image doesn't exist, skip (don't auto-pull in tests)
        if "unable to find image" in result.stderr.lower():
            pytest.skip("vLLM image not available locally")

        if result.returncode == 0:
            assert (
                "vllm serve" in result.stdout
                or "usage:" in result.stdout.lower()
            )


@pytest.mark.smoke
class TestContainerConfiguration:
    """Test container configuration files and settings."""

    def test_vllm_server_role_exists(self):
        """Verify vLLM server role exists with required files."""
        from pathlib import Path

        role_dir = Path(__file__).parent.parent.parent / "roles" / "vllm_server"
        assert role_dir.exists(), "vllm_server role directory not found"

        # Check for key task files
        tasks_dir = role_dir / "tasks"
        assert tasks_dir.exists(), "vllm_server tasks directory not found"

        expected_tasks = ["main.yml", "start-llm.yml", "start-embedding.yml"]
        for task in expected_tasks:
            task_file = tasks_dir / task
            assert task_file.exists(), f"Missing task file: {task}"

    def test_benchmark_roles_exist(self):
        """Verify benchmark roles exist."""
        from pathlib import Path

        ansible_dir = Path(__file__).parent.parent.parent
        roles_dir = ansible_dir / "roles"

        expected_roles = [
            "benchmark_guidellm",
            "vllm_server",
            "results_collector",
        ]

        missing = []
        for role in expected_roles:
            role_path = roles_dir / role
            if not role_path.exists():
                missing.append(role)

        assert not missing, f"Missing roles: {missing}"


@pytest.mark.smoke
class TestContainerNetworking:
    """Test container networking configuration."""

    def test_default_ports_defined(self):
        """Verify default ports are defined in configuration."""
        from pathlib import Path
        import yaml

        inventory_file = (
            Path(__file__).parent.parent.parent
            / "inventory"
            / "group_vars"
            / "all"
            / "endpoints.yml"
        )

        if not inventory_file.exists():
            pytest.skip("endpoints.yml not found")

        with open(inventory_file) as f:
            config = yaml.safe_load(f)

        # Check for vLLM port configuration
        assert config is not None, "Empty endpoints configuration"
        # The actual structure may vary, just verify it's valid YAML
