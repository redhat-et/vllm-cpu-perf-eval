"""Test Ansible param_mappings (cores → requested_cores, scenario → test_scenario)."""

import subprocess
import sys
from .conftest import repo_root


def test_chat_smoke_cores_mapping():
    """Test that --cores maps to requested_cores for ansible suite."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "chat-smoke",
         "--model", "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "--cores", "8",
         "--dry-run", "--skip-doctor"],
        capture_output=True, text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0
    assert "requested_cores=8" in result.stdout
    assert "-e cores=8" not in result.stdout  # Should NOT use bare "cores"


def test_concurrent_load_matrix_no_model():
    """Test that concurrent-load runs as matrix without --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "concurrent-load",
         "--dry-run", "--skip-doctor"],
        capture_output=True, text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0
    assert "run-concurrent-load-suite.sh" in result.stdout
    assert "--models all" in result.stdout


def test_audio_matrix_no_model():
    """Test that audio runs as matrix without --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "audio",
         "--dry-run", "--skip-doctor"],
        capture_output=True, text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0
    assert "run-audio-suite.sh" in result.stdout
    assert "--models all" in result.stdout
