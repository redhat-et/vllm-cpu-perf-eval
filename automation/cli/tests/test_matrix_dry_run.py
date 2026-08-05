"""Test matrix suite dry-run behavior."""

import os
import subprocess
import sys
from .conftest import repo_root


def test_rhaiis_sweep_dry_run_without_model():
    """Test that rhaiis-sweep runs without --model."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "rhaiis-sweep", "--dry-run",
        ],
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
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "embedding", "--dry-run",
        ],
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
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "offline-batch", "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-offline-batch-suite.sh" in result.stdout
    assert "use-cases" in result.stdout
    assert "3" in result.stdout


def test_offline_batch_mode_flags():
    """Test first-class offline-batch flags build positional args."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cpueval",
            "run",
            "--suite",
            "offline-batch",
            "--mode",
            "use-case-sweep",
            "--use-case",
            "summarization",
            "--models",
            "all",
            "--cores",
            "8,16,32",
            "--runs",
            "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "use-case-sweep summarization all 8,16,32 3" in result.stdout


def test_offline_batch_run_test_flags():
    """Test run_test mode via first-class flags."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cpueval",
            "run",
            "--suite",
            "offline-batch",
            "--mode",
            "run_test",
            "--model",
            "all",
            "--dataset",
            "sonnet",
            "--num-prompts",
            "1000",
            "--cores",
            "16",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run_test all sonnet 1000 16" in result.stdout


def test_offline_batch_input_output_len_flags():
    """Test --input-len and --output-len pass ansible -e flags through."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cpueval",
            "run",
            "--suite",
            "offline-batch",
            "--mode",
            "run_test",
            "--model",
            "RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4",
            "--dataset",
            "random",
            "--num-prompts",
            "3",
            "--cores",
            "8",
            "--input-len",
            "32",
            "--output-len",
            "16",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert (
        "run_test RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 random 3 8"
        in result.stdout
    )
    assert "-e input_len=32" in result.stdout
    assert "-e output_len=16" in result.stdout


def test_offline_batch_extra_args_override():
    """Test --extra args= still overrides structured flags."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cpueval",
            "run",
            "--suite",
            "offline-batch",
            "--extra",
            'args="baseline 32 100"',
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "baseline 32 100" in result.stdout


def test_chat_smoke_requires_model():
    """Test that chat-smoke requires --model."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "chat-smoke", "--dry-run",
        ],
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
    """concurrent-load default: all 4 workloads, 60 combinations (all×3×4)."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "concurrent-load",
         "--dry-run", "--skip-doctor"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0
    assert "--workloads chat,code,summarization,rag" in result.stdout
    assert "--models all" in result.stdout
    assert "--cores 8,16,32" in result.stdout


def test_audio_scenario_override():
    """--scenario on audio overrides the default and appears exactly once."""
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


def test_audio_custom_model_dtype_and_max_model_len():
    """dtype and max_model_len extras are forwarded as bash flags for non-Whisper models."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "run", "--suite", "audio",
         "--models", "fixie-ai/ultravox-v0_5-llama-3_2-1b",
         "--extra", "dtype=bfloat16",
         "--extra", "max_model_len=2048",
         "--scenario", "transcription-throughput",
         "--dry-run", "--skip-doctor"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "--models fixie-ai/ultravox-v0_5-llama-3_2-1b" in result.stdout
    assert "--dtype bfloat16" in result.stdout
    assert "--max-model-len 2048" in result.stdout


def test_dry_run_no_results_message():
    """Test that dry-run doesn't show 'Results saved' message."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "rhaiis-sweep", "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert "Results saved" not in result.stdout
    assert "✓" not in result.stdout or "Results" not in result.stdout


def test_implicit_rhaiis_sweep_dry_run():
    """rhaiis-sweep --dry-run works without the 'run' subcommand."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval",
            "--suite", "rhaiis-sweep", "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-rhaiis-concurrent-load.sh" in result.stdout
    assert "--models all" in result.stdout
    assert "--cores 8,16,32" in result.stdout


def test_implicit_concurrent_load_dry_run():
    """concurrent-load --dry-run --skip-doctor works without 'run'."""
    result = subprocess.run(
        [sys.executable, "-m", "cpueval", "--suite", "concurrent-load",
         "--dry-run", "--skip-doctor"],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "run-concurrent-load-suite.sh" in result.stdout
    assert "--models all" in result.stdout


def test_implicit_matches_explicit_run():
    """Implicit and explicit 'run' invocation produce identical output."""
    implicit = subprocess.run(
        [
            sys.executable, "-m", "cpueval",
            "--suite", "rhaiis-sweep", "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    explicit = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "rhaiis-sweep", "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert implicit.returncode == 0, f"STDERR: {implicit.stderr}"
    assert implicit.stdout == explicit.stdout


def test_concurrent_load_profile_pinning_passthrough():
    """CPU pinning profile vars are forwarded to the suite script."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "concurrent-load",
            "--profile", "dual-socket-split",
            "--models", "tiny",
            "--cores", "8",
            "--workloads", "chat",
            "--dry-run",
            "--skip-doctor",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "--vllm-cpu-start 64" in result.stdout
    assert "--vllm-numa-node 1" in result.stdout
    assert "--guidellm-cpus 0-31" in result.stdout
    assert "--guidellm-numa-node 0" in result.stdout


def test_rhaiis_sweep_pinning_flags():
    """Explicit pinning flags are forwarded to the rhaiis sweep script."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "rhaiis-sweep",
            "--vllm-cpu-start", "96",
            "--vllm-numa", "1",
            "--guidellm-cpus", "0-31",
            "--guidellm-numa", "0",
            "--dry-run",
            "--skip-doctor",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "--vllm-cpu-start 96" in result.stdout
    assert "--vllm-numa-node 1" in result.stdout
    assert "--guidellm-cpus 0-31" in result.stdout
    assert "--guidellm-numa-node 0" in result.stdout


def test_embedding_bench_pinning_flags():
    """Embedding bench CPU pinning flags are forwarded to the suite script."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "embedding",
            "--models", "quick",
            "--cores", "8",
            "--vllm-bench-cpus", "8-15",
            "--vllm-bench-numa-node", "0",
            "--max-seconds", "300",
            "--dry-run",
            "--skip-doctor",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "--vllm-bench-cpus 8-15" in result.stdout
    assert "--vllm-bench-numa-node 0" in result.stdout
    assert "--max-seconds 300" in result.stdout


def test_continue_on_error_flag_only():
    """Boolean suite flags are passed without a value."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "concurrent-load",
            "--models", "tiny",
            "--continue-on-error",
            "--dry-run",
            "--skip-doctor",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "--continue-on-error" in result.stdout
    assert "--continue-on-error True" not in result.stdout


def test_endpoint_url_sets_external_mode():
    """--endpoint-url enables external endpoint mode for ansible-backed runs."""
    result = subprocess.run(
        [
            sys.executable, "-c",
            "import os, sys; "
            "sys.path.insert(0, 'automation/cli/src'); "
            "from cpueval.cli import _apply_endpoint_env; "
            "_apply_endpoint_env('http://lb.example:8080'); "
            "print(os.environ.get('VLLM_ENDPOINT_MODE', '')); "
            "print(os.environ.get('VLLM_ENDPOINT_URL', ''))",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
        env={
            **dict(os.environ),
            "VLLM_ENDPOINT_MODE": "",
            "VLLM_ENDPOINT_URL": "",
        },
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert lines[0] == "external"
    assert lines[1] == "http://lb.example:8080"


def test_endpoint_url_dry_run_invokes_ansible():
    """Integration: --endpoint-url still produces an ansible dry-run command."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "chat-smoke",
            "--model", "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            "--cores", "8",
            "--endpoint-url", "http://lb.example:8080",
            "--dry-run",
            "--skip-doctor",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )

    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "ansible-playbook" in result.stdout


# ---------------------------------------------------------------------------
# Offline batch — Tier 1 use cases (highest enterprise ROI)
# ---------------------------------------------------------------------------

def test_offline_batch_use_case_summarization():
    """Summarization via implicit run (no subcommand): sharegpt, 1000 prompts."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval",
            "--suite", "offline-batch",
            "--mode", "use-case-sweep",
            "--use-case", "summarization",
            "--models", "all",
            "--cores", "8,16,24,32",
            "--runs", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "use-case-sweep summarization all 8,16,24,32 3" in result.stdout


def test_offline_batch_use_case_classification():
    """Classification: sharegpt, 1000 prompts, output=64, core sweep."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "offline-batch",
            "--mode", "use-case-sweep",
            "--use-case", "classification",
            "--models", "all",
            "--cores", "8,16,24,32",
            "--runs", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "use-case-sweep classification all 8,16,24,32 3" in result.stdout


def test_offline_batch_use_case_rag():
    """RAG Batch: random, 500 prompts, input=2048, output=128, core sweep."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "offline-batch",
            "--mode", "use-case-sweep",
            "--use-case", "rag",
            "--models", "all",
            "--cores", "8,16,24,32",
            "--runs", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "use-case-sweep rag all 8,16,24,32 3" in result.stdout


def test_offline_batch_use_case_entity_extraction():
    """Entity Extraction: sharegpt, 1000 prompts, output=128, core sweep."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "offline-batch",
            "--mode", "use-case-sweep",
            "--use-case", "entity-extraction",
            "--models", "all",
            "--cores", "8,16,24,32",
            "--runs", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "use-case-sweep entity-extraction all 8,16,24,32 3" in result.stdout


# ---------------------------------------------------------------------------
# Offline batch — Tier 2 use cases (high value, narrower audience)
# ---------------------------------------------------------------------------

def test_offline_batch_use_case_long_summarization():
    """Long-Doc Summary: random, 500 prompts, 4096→256 tokens, core sweep."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "offline-batch",
            "--mode", "use-case-sweep",
            "--use-case", "long-summarization",
            "--models", "all",
            "--cores", "8,16,24,32",
            "--runs", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert (
        "use-case-sweep long-summarization all 8,16,24,32 3"
        in result.stdout
    )


def test_offline_batch_use_case_etl():
    """ETL: sonnet, 500 prompts, core-scaling sweep (8/16/24/32)."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "offline-batch",
            "--mode", "use-case-sweep",
            "--use-case", "etl",
            "--models", "all",
            "--cores", "8,16,24,32",
            "--runs", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "use-case-sweep etl all 8,16,24,32 3" in result.stdout


def test_offline_batch_use_case_short_labeling():
    """Short Labeling: sharegpt, 2000 prompts, output=16, core sweep."""
    result = subprocess.run(
        [
            sys.executable, "-m", "cpueval", "run",
            "--suite", "offline-batch",
            "--mode", "use-case-sweep",
            "--use-case", "short-labeling",
            "--models", "all",
            "--cores", "8,16,24,32",
            "--runs", "3",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root()),
    )
    assert result.returncode == 0, f"STDERR: {result.stderr}"
    assert "use-case-sweep short-labeling all 8,16,24,32 3" in result.stdout
