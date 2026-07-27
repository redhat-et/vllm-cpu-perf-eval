"""Test matrix suite dry-run behavior."""

import subprocess
import sys


def test_rhaiis_sweep_dry_run_without_model():
    """Test that rhaiis-sweep runs without --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "rhaiis-sweep", "--dry-run"],
        capture_output=True,
        text=True,
        cwd="/Users/mtahhan/git-workspace/format-results",
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-rhaiis-concurrent-load.sh" in result.stdout
    assert "--models all" in result.stdout
    assert "--cores 8,16,32" in result.stdout
    assert "--workloads chat,code,summarization,rag" in result.stdout


def test_embedding_dry_run_without_model():
    """Test that embedding runs without --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "embedding", "--dry-run"],
        capture_output=True,
        text=True,
        cwd="/Users/mtahhan/git-workspace/format-results",
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
        cwd="/Users/mtahhan/git-workspace/format-results",
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-offline-batch-suite.sh" in result.stdout
    assert "use-cases 3" in result.stdout  # Changed from 5 to 3 for faster testing


def test_chat_smoke_requires_model():
    """Test that chat-smoke requires --model."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "chat-smoke", "--dry-run"],
        capture_output=True,
        text=True,
        cwd="/Users/mtahhan/git-workspace/format-results",
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
        cwd="/Users/mtahhan/git-workspace/format-results",
    )

    assert result.returncode == 0
    assert "--models tiny" in result.stdout
    assert "--cores 8" in result.stdout


def test_dry_run_no_results_message():
    """Test that dry-run doesn't show 'Results saved' message."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "rhaiis-sweep", "--dry-run"],
        capture_output=True,
        text=True,
        cwd="/Users/mtahhan/git-workspace/format-results",
    )

    assert "Results saved" not in result.stdout
    assert "✓" not in result.stdout or "Results" not in result.stdout
