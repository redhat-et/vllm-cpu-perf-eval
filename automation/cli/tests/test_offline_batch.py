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


def test_use_case_sweep_inherited_runs_from_defaults():
    """Suite defaults include runs: 3; must not pass 3 as the model slot."""
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "summarization",
            "runs": 3,
        }
    ) == ["use-case-sweep", "summarization", "all", "8,16,24,32", "3"]


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


def test_quantization_num_prompts_without_cores():
    assert build_offline_batch_args(
        {"mode": "quantization", "num_prompts": 100}
    ) == ["quantization", "32", "100"]


def test_run_test_with_input_output_len():
    assert build_offline_batch_args(
        {
            "mode": "run_test",
            "model": "RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4",
            "dataset": "random",
            "num_prompts": 3,
            "cores": "8",
            "input_len": 32,
            "output_len": 16,
        }
    ) == [
        "run_test",
        "RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4",
        "random",
        "3",
        "8",
        "-e",
        "input_len=32",
        "-e",
        "output_len=16",
    ]


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


# ---------------------------------------------------------------------------
# Tier 1 — use-case-sweep arg builder (highest enterprise ROI)
# ---------------------------------------------------------------------------

def test_use_case_sweep_classification():
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "classification",
            "models": "all",
            "cores": "8,16,24,32",
            "runs": 3,
        }
    ) == ["use-case-sweep", "classification", "all", "8,16,24,32", "3"]


def test_use_case_sweep_rag():
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "rag",
            "models": "all",
            "cores": "8,16,24,32",
            "runs": 3,
        }
    ) == ["use-case-sweep", "rag", "all", "8,16,24,32", "3"]


def test_use_case_sweep_entity_extraction():
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "entity-extraction",
            "models": "all",
            "cores": "8,16,24,32",
            "runs": 3,
        }
    ) == [
        "use-case-sweep", "entity-extraction", "all", "8,16,24,32", "3",
    ]


# ---------------------------------------------------------------------------
# Tier 2 — use-case-sweep arg builder (high value, narrower audience)
# ---------------------------------------------------------------------------

def test_use_case_sweep_long_summarization():
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "long-summarization",
            "models": "all",
            "cores": "8,16,24,32",
            "runs": 3,
        }
    ) == [
        "use-case-sweep", "long-summarization", "all", "8,16,24,32", "3",
    ]


def test_use_case_sweep_etl():
    """ETL: core-scaling sweep directly answers capacity-planning questions."""
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "etl",
            "models": "all",
            "cores": "8,16,24,32",
            "runs": 3,
        }
    ) == ["use-case-sweep", "etl", "all", "8,16,24,32", "3"]


def test_use_case_sweep_short_labeling():
    assert build_offline_batch_args(
        {
            "mode": "use-case-sweep",
            "use_case": "short-labeling",
            "models": "all",
            "cores": "8,16,24,32",
            "runs": 3,
        }
    ) == [
        "use-case-sweep", "short-labeling", "all", "8,16,24,32", "3",
    ]
