#!/usr/bin/env python3
"""Integration tests for container operations."""
import pytest
import time
from .helpers.container_helper import (
    run_container,
    get_container_status,
    get_container_logs,
    stop_container,
    remove_container,
)


@pytest.mark.integration
@pytest.mark.requires_container
class TestContainerLifecycle:
    """Test basic container lifecycle operations."""

    def test_container_start_and_stop(self, container_runtime, cleanup_containers):
        """Test starting and stopping a simple container."""
        # Start a simple container
        result = run_container(
            runtime=container_runtime,
            image="busybox:latest",
            name="test-busybox",
            command=["sleep", "60"],
        )

        assert result.returncode == 0, f"Container start failed: {result.stderr}"
        container_id = result.stdout.strip()
        assert container_id, "No container ID returned"

        cleanup_containers(container_id)

        # Verify container is running
        status = get_container_status(container_runtime, container_id)
        assert status == "running", f"Container not running: {status}"

        # Stop container
        stopped = stop_container(container_runtime, container_id, timeout=5)
        assert stopped, "Failed to stop container"

        # Verify stopped
        status = get_container_status(container_runtime, container_id)
        assert status in ["exited", "stopped"], f"Container still running: {status}"

    def test_container_with_cpu_affinity(self, container_runtime, cleanup_containers):
        """Test container with CPU affinity settings."""
        result = run_container(
            runtime=container_runtime,
            image="busybox:latest",
            name="test-cpu-affinity",
            cpuset_cpus="0-3",
            command=["sleep", "30"],
        )

        assert result.returncode == 0, f"Container start failed: {result.stderr}"
        container_id = result.stdout.strip()
        cleanup_containers(container_id)

        status = get_container_status(container_runtime, container_id)
        assert status == "running"

    @pytest.mark.skipif(True, reason="NUMA affinity test requires multi-NUMA system")
    def test_container_with_numa_affinity(
        self,
        container_runtime,
        cleanup_containers,
        numa_topology,
        skip_if_single_numa,
    ):
        """Test container with NUMA memory affinity."""
        result = run_container(
            runtime=container_runtime,
            image="busybox:latest",
            name="test-numa-affinity",
            cpuset_cpus="0-3",
            cpuset_mems="0",
            command=["sleep", "30"],
        )

        assert result.returncode == 0, f"Container start failed: {result.stderr}"
        container_id = result.stdout.strip()
        cleanup_containers(container_id)

        status = get_container_status(container_runtime, container_id)
        assert status == "running"

    def test_container_environment_variables(self, container_runtime, cleanup_containers):
        """Test container with environment variables."""
        result = run_container(
            runtime=container_runtime,
            image="busybox:latest",
            name="test-env",
            env={"TEST_VAR": "test_value", "FOO": "bar"},
            command=["sh", "-c", "echo $TEST_VAR && sleep 5"],
        )

        assert result.returncode == 0, f"Container start failed: {result.stderr}"
        container_id = result.stdout.strip()
        cleanup_containers(container_id)

        # Wait a moment for container to execute
        time.sleep(2)

        # Check logs for environment variable
        logs = get_container_logs(container_runtime, container_id)
        assert "test_value" in logs, "Environment variable not set correctly"


@pytest.mark.integration
@pytest.mark.requires_container
@pytest.mark.slow
class TestVllmContainer:
    """Test vLLM container operations (slower tests)."""

    @pytest.mark.skipif(True, reason="Requires vLLM image - enable for full integration tests")
    def test_vllm_container_health_check(
        self,
        container_runtime,
        cleanup_containers,
        minimal_vllm_config,
        wait_for_port,
        wait_for_health,
    ):
        """Test vLLM container starts and responds to health checks."""
        # Start vLLM container
        result = run_container(
            runtime=container_runtime,
            image="vllm/vllm-openai:latest",
            name="test-vllm-server",
            ports={8000: 8000},
            env={
                "MODEL": minimal_vllm_config["model"],
                "DTYPE": minimal_vllm_config["dtype"],
                "MAX_MODEL_LEN": str(minimal_vllm_config["max_model_len"]),
            },
        )

        if result.returncode != 0:
            pytest.skip(f"vLLM container failed to start: {result.stderr}")

        container_id = result.stdout.strip()
        cleanup_containers(container_id)

        # Wait for port to be available
        port_ready = wait_for_port(8000, timeout=120)
        assert port_ready, "vLLM server port not available"

        # Wait for health endpoint
        health_ready = wait_for_health("http://localhost:8000/health", timeout=120)
        assert health_ready, "vLLM server health check failed"


@pytest.mark.integration
@pytest.mark.requires_container
class TestContainerCleanup:
    """Test container cleanup operations."""

    def test_force_remove_running_container(self, container_runtime):
        """Test force removal of running container."""
        # Start container
        result = run_container(
            runtime=container_runtime,
            image="busybox:latest",
            name="test-cleanup",
            command=["sleep", "60"],
        )

        container_id = result.stdout.strip()

        # Force remove without stopping
        removed = remove_container(container_runtime, container_id, force=True)
        assert removed, "Failed to force remove container"

        # Verify removed
        status = get_container_status(container_runtime, container_id)
        assert status is None, "Container still exists after removal"
