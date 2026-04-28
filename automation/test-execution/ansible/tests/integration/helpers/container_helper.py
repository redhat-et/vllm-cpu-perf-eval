#!/usr/bin/env python3
"""Helper functions for container operations in integration tests."""
import subprocess
import json
from typing import Optional, Dict, List


def run_container(
    runtime: str,
    image: str,
    name: Optional[str] = None,
    detach: bool = True,
    ports: Optional[Dict[int, int]] = None,
    env: Optional[Dict[str, str]] = None,
    volumes: Optional[Dict[str, str]] = None,
    cpuset_cpus: Optional[str] = None,
    cpuset_mems: Optional[str] = None,
    command: Optional[List[str]] = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """
    Run a container with specified configuration.

    Args:
        runtime: Container runtime (podman/docker)
        image: Container image name
        name: Container name
        detach: Run in detached mode
        ports: Port mappings {container_port: host_port}
        env: Environment variables
        volumes: Volume mappings {host_path: container_path}
        cpuset_cpus: CPU affinity (e.g., "0-3")
        cpuset_mems: NUMA memory affinity (e.g., "0")
        command: Command to run in container
        timeout: Command timeout in seconds

    Returns:
        subprocess.CompletedProcess with container ID in stdout
    """
    cmd = [runtime, "run"]

    if detach:
        cmd.append("-d")

    if name:
        cmd.extend(["--name", name])

    if ports:
        for container_port, host_port in ports.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])

    if env:
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])

    if volumes:
        for host_path, container_path in volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])

    if cpuset_cpus:
        cmd.extend(["--cpuset-cpus", cpuset_cpus])

    if cpuset_mems:
        cmd.extend(["--cpuset-mems", cpuset_mems])

    cmd.append(image)

    if command:
        cmd.extend(command)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def get_container_status(runtime: str, container_id: str) -> Optional[str]:
    """
    Get container status.

    Args:
        runtime: Container runtime
        container_id: Container ID or name

    Returns:
        Status string (running, exited, etc.) or None if not found
    """
    try:
        result = subprocess.run(
            [runtime, "inspect", "--format", "{{.State.Status}}", container_id],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_container_logs(
    runtime: str,
    container_id: str,
    tail: Optional[int] = None,
) -> str:
    """
    Get container logs.

    Args:
        runtime: Container runtime
        container_id: Container ID or name
        tail: Number of lines to tail (default: all)

    Returns:
        Container logs as string
    """
    cmd = [runtime, "logs", container_id]
    if tail:
        cmd.extend(["--tail", str(tail)])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout + result.stderr


def stop_container(runtime: str, container_id: str, timeout: int = 10) -> bool:
    """
    Stop a container.

    Args:
        runtime: Container runtime
        container_id: Container ID or name
        timeout: Stop timeout in seconds

    Returns:
        True if stopped successfully
    """
    try:
        result = subprocess.run(
            [runtime, "stop", "-t", str(timeout), container_id],
            capture_output=True,
            timeout=timeout + 5,
        )
        return result.returncode == 0
    except Exception:
        return False


def remove_container(runtime: str, container_id: str, force: bool = True) -> bool:
    """
    Remove a container.

    Args:
        runtime: Container runtime
        container_id: Container ID or name
        force: Force removal

    Returns:
        True if removed successfully
    """
    try:
        cmd = [runtime, "rm", container_id]
        if force:
            cmd.insert(2, "-f")

        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def get_container_port(runtime: str, container_id: str, container_port: int) -> Optional[int]:
    """
    Get host port mapped to container port.

    Args:
        runtime: Container runtime
        container_id: Container ID or name
        container_port: Container port number

    Returns:
        Host port number or None if not mapped
    """
    try:
        result = subprocess.run(
            [runtime, "port", container_id, str(container_port)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Output format: 0.0.0.0:8080
            port_mapping = result.stdout.strip()
            if ":" in port_mapping:
                return int(port_mapping.split(":")[-1])
    except Exception:
        pass
    return None
