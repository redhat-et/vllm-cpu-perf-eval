#!/usr/bin/env python3
"""Shared fixtures for integration tests."""
import pytest
import subprocess
import shutil
import tempfile
import time
from pathlib import Path


# ============================================================================
# Path Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def repo_root():
    """Get repository root directory."""
    return Path(__file__).parent.parent.parent.parent.parent.parent


@pytest.fixture(scope="session")
def ansible_dir(repo_root):
    """Get Ansible playbooks directory."""
    return repo_root / "automation" / "test-execution" / "ansible"


@pytest.fixture(scope="session")
def models_dir(repo_root):
    """Get models directory."""
    return repo_root / "models"


@pytest.fixture(scope="session")
def tests_dir(repo_root):
    """Get integration tests directory."""
    return repo_root / "automation" / "test-execution" / "ansible" / "tests" / "integration"


# ============================================================================
# Container Runtime Fixtures
# ============================================================================

def _get_container_runtime():
    """Get available container runtime (podman or docker)."""
    for cmd in ["podman", "docker"]:
        if shutil.which(cmd):
            return cmd
    return None


@pytest.fixture(scope="session")
def container_runtime():
    """Get container runtime command."""
    runtime = _get_container_runtime()
    if not runtime:
        pytest.skip("No container runtime (podman/docker) available")
    return runtime


@pytest.fixture
def cleanup_containers(container_runtime):
    """Ensure test containers are cleaned up after test."""
    containers = []

    def _register(container_id):
        """Register a container for cleanup."""
        containers.append(container_id)
        return container_id

    yield _register

    # Cleanup
    for container_id in containers:
        try:
            subprocess.run(
                [container_runtime, "stop", "-t", "2", container_id],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                [container_runtime, "rm", "-f", container_id],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass


# ============================================================================
# Ansible Fixtures
# ============================================================================

@pytest.fixture
def ansible_inventory(ansible_dir, tmp_path):
    """Provide minimal test inventory."""
    inventory_content = """[benchmark_hosts]
localhost ansible_connection=local

[benchmark_hosts:vars]
ansible_python_interpreter=/usr/bin/python3
"""
    inventory_file = tmp_path / "inventory.ini"
    inventory_file.write_text(inventory_content)
    return inventory_file


@pytest.fixture
def ansible_runner(ansible_dir, ansible_inventory):
    """Provide helper to run Ansible playbooks."""
    def _run_playbook(playbook_name, extra_vars=None, check=False):
        """
        Run an Ansible playbook.

        Args:
            playbook_name: Playbook filename (e.g., "health-check.yml")
            extra_vars: Dict of extra variables to pass
            check: Run in check mode

        Returns:
            subprocess.CompletedProcess
        """
        playbook_path = ansible_dir / playbook_name
        if not playbook_path.exists():
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        cmd = [
            "ansible-playbook",
            "-i", str(ansible_inventory),
            str(playbook_path),
        ]

        if check:
            cmd.append("--check")

        if extra_vars:
            for key, value in extra_vars.items():
                cmd.extend(["-e", f"{key}={value}"])

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

    return _run_playbook


# ============================================================================
# Results & Cleanup Fixtures
# ============================================================================

@pytest.fixture
def temp_results_dir(tmp_path):
    """Create temporary results directory."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    return results_dir


@pytest.fixture
def cleanup_results():
    """Track and cleanup result directories."""
    dirs = []

    def _register(result_dir):
        """Register a results directory for cleanup."""
        dirs.append(Path(result_dir))
        return result_dir

    yield _register

    # Cleanup
    for result_dir in dirs:
        if result_dir.exists():
            shutil.rmtree(result_dir, ignore_errors=True)


# ============================================================================
# Model & Config Fixtures
# ============================================================================

@pytest.fixture
def minimal_vllm_config():
    """Provide minimal vLLM server configuration."""
    return {
        "model": "facebook/opt-125m",
        "dtype": "float32",
        "max_model_len": 1024,
        "enforce_eager": True,
        "disable_log_stats": False,
    }


@pytest.fixture
def minimal_benchmark_config():
    """Provide minimal benchmark configuration."""
    return {
        "warmup": 5,
        "max_requests": 20,
        "input_tokens": 128,
        "output_tokens": 64,
    }


# ============================================================================
# NUMA Topology Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def numa_topology():
    """Get actual NUMA topology from system."""
    try:
        result = subprocess.run(
            ["lscpu", "-e=CPU,NODE,CORE"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        # Parse to count NUMA nodes
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        nodes = set()
        for line in lines:
            parts = line.split()
            if len(parts) >= 2:
                nodes.add(int(parts[1]))

        return {
            "node_count": len(nodes),
            "nodes": sorted(nodes),
            "lscpu_output": result.stdout,
        }
    except Exception:
        return None


@pytest.fixture
def skip_if_single_numa(numa_topology):
    """Skip test if system has only one NUMA node."""
    if not numa_topology or numa_topology["node_count"] < 2:
        pytest.skip("Test requires multi-NUMA system")


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def wait_for_port():
    """Helper to wait for a port to be available."""
    def _wait(port, host="localhost", timeout=30):
        """
        Wait for a port to accept connections.

        Args:
            port: Port number
            host: Hostname (default: localhost)
            timeout: Timeout in seconds

        Returns:
            bool: True if port is available, False on timeout
        """
        import socket
        start = time.time()
        while time.time() - start < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect((host, port))
                sock.close()
                return True
            except (socket.error, ConnectionRefusedError):
                time.sleep(0.5)
        return False

    return _wait


@pytest.fixture
def wait_for_health():
    """Helper to wait for HTTP health endpoint."""
    def _wait(url, timeout=60):
        """
        Wait for HTTP endpoint to return 200.

        Args:
            url: Health check URL
            timeout: Timeout in seconds

        Returns:
            bool: True if healthy, False on timeout
        """
        import urllib.request
        import urllib.error

        start = time.time()
        while time.time() - start < timeout:
            try:
                response = urllib.request.urlopen(url, timeout=2)
                if response.status == 200:
                    return True
            except (urllib.error.URLError, TimeoutError):
                time.sleep(1)
        return False

    return _wait
