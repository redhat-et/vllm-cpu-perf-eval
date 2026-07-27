"""Test matrix suite dry-run behavior."""

import subprocess
import sys
from .conftest import repo_root


def test_rhaiis_sweep_dry_run_without_model():
    """Test that rhaiis-sweep runs without --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "rhaiis-sweep", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-rhaiis-concurrent-load.sh" in result.stdout
    assert "--models all" in result.stdout
    assert "--cores 8,16,32" in result.stdout


def test_embedding_dry_run_without_model():
    """Test that embedding runs without --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "embedding", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-embedding-suite.sh" in result.stdout
    assert "--models all" in result.stdout
    assert "--num-prompts 250" in result.stdout


def test_offline_batch_dry_run_without_model():
    """Test that offline-batch runs without --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "offline-batch", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-offline-batch-suite.sh" in result.stdout
    assert "use-cases 3" in result.stdout


def test_chat_smoke_requires_model():
    """Test that chat-smoke requires --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "chat-smoke", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 1
    assert "--model is required" in result.stdout


def test_rhaiis_sweep_override():
    """Test that matrix overrides work."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "rhaiis-sweep",
         "--models", "tiny", "--cores", "8", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0
    assert "--models tiny" in result.stdout
    assert "--cores 8" in result.stdout


def test_concurrent_load_workload_override():
    """Test that --workload chat overrides default matrix workloads."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "concurrent-load",
         "--workload", "chat", "--dry-run", "--skip-doctor"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "--workloads chat" in result.stdout
    # Ensure we don't see other workloads like code, summarization, rag
    assert "code,summarization,rag" not in result.stdout


def test_concurrent_load_default():
    """Test that concurrent-load default is chat only (15 combinations: 5×3×1)."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "concurrent-load",
         "--dry-run", "--skip-doctor"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0
    assert "--workloads chat" in result.stdout
    assert "--models all" in result.stdout
    assert "--cores 8,16,32" in result.stdout


def test_audio_scenario_override():
    """Test that --scenario on audio overrides default and appears only once."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "audio",
         "--scenario", "transcription-latency", "--dry-run", "--skip-doctor"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    # Must contain exactly one --scenarios flag
    assert result.stdout.count("--scenarios") == 1
    assert "--scenarios transcription-latency" in result.stdout
    # Must NOT include the default
    assert "transcription-throughput" not in result.stdout


def test_dry_run_no_results_message():
    """Test that dry-run doesn't show 'Results saved' message."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "rhaiis-sweep", "--dry-run"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert "Results saved" not in result.stdout
    assert "✓" not in result.stdout or "Results" not in result.stdout
