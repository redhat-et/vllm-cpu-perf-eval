"""Tests for offline-batch positional arg builder."""

import pytest

from cpueval.offline_batch import build_offline_batch_args


def test_use_cases_defaults():
    assert build_offline_batch_args({"mode": "use-cases", "runs": 3}) == [
        "use-cases",
        "3",
    ]


def test_use_cases_with_models():
    assert build_offline_batch_args(
        {"mode": "use-cases", "runs": 5, "models": "all"}
    ) == ["use-cases", "5", "all"]


def test_use_case_sweep_full():
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "summarization",
            "models": "all",
            "cores": "8,16,32",
            "runs": 3,
        }
    ) == ["use-case-sweep", "summarization", "all", "8,16,32", "3"]


def test_use_case_sweep_requires_use_case():
    with pytest.raises(ValueError, match="--use-case"):
        build_offline_batch_args({"mode": "use-case-sweep"})


def test_use_case_sweep_only_use_case():
    assert build_offline_batch_args(
        {"mode": "use-case-sweep", "use_case": "summarization"}
    ) == ["use-case-sweep", "summarization"]


def test_use_case_sweep_runs_without_models_or_cores():
    assert build_offline_batch_args(
        {"mode": "use-case-sweep", "use_case": "summarization", "runs": 5}
    ) == ["use-case-sweep", "summarization", "all", "8,16,24,32", "5"]


def test_use_case_sweep_cores_without_models():
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "summarization",
            "cores": "16,32",
        }
    ) == ["use-case-sweep", "summarization", "all", "16,32"]


def test_baseline_num_prompts_without_cores():
    assert build_offline_batch_args(
        {"mode": "baseline", "num_prompts": 100}
    ) == ["baseline", "32", "100"]


def test_run_test():
    assert build_offline_batch_args(
        {
            "mode": "run_test",
            "model": "all",
            "dataset": "sonnet",
            "num_prompts": 1000,
            "cores": "16",
        }
    ) == ["run_test", "all", "sonnet", "1000", "16"]


def test_run_test_missing_args():
    with pytest.raises(ValueError, match="run_test mode requires"):
        build_offline_batch_args({"mode": "run_test", "model": "all"})


def test_core_scaling():
    assert build_offline_batch_args(
        {"mode": "core-scaling", "models": "meta-llama/Llama-3.2-1B-Instruct"}
    ) == ["core-scaling", "meta-llama/Llama-3.2-1B-Instruct"]


def test_batch_scaling_with_cores():
    assert build_offline_batch_args(
        {
            "mode": "batch-scaling",
            "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            "cores": "16",
        }
    ) == ["batch-scaling", "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "16"]


def test_baseline():
    assert build_offline_batch_args(
        {"mode": "baseline", "cores": "32", "num_prompts": 100}
    ) == ["baseline", "32", "100"]
