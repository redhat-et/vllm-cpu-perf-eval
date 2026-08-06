"""Unit tests for cpueval CLI helper functions."""

import os

from cpueval.cli import _apply_endpoint_env, _build_script_args, _result_model_hint
from cpueval.suite_registry import SuiteRegistry


def test_apply_endpoint_env_sets_external_mode(monkeypatch):
    """--endpoint-url sets VLLM_ENDPOINT_MODE and VLLM_ENDPOINT_URL."""
    monkeypatch.delenv("VLLM_ENDPOINT_MODE", raising=False)
    monkeypatch.delenv("VLLM_ENDPOINT_URL", raising=False)

    _apply_endpoint_env("http://lb.example:8080")

    assert os.environ["VLLM_ENDPOINT_MODE"] == "external"
    assert os.environ["VLLM_ENDPOINT_URL"] == "http://lb.example:8080"


def test_apply_endpoint_env_noop_when_unset(monkeypatch):
    """Omitting --endpoint-url leaves existing env vars unchanged."""
    monkeypatch.setenv("VLLM_ENDPOINT_MODE", "managed")
    monkeypatch.setenv("VLLM_ENDPOINT_URL", "http://existing:8000")

    _apply_endpoint_env(None)

    assert os.environ["VLLM_ENDPOINT_MODE"] == "managed"
    assert os.environ["VLLM_ENDPOINT_URL"] == "http://existing:8000"


def test_build_script_args_prefixes_mapping_values_without_dashes():
    """Mappings may omit --; _build_script_args normalizes before invoking scripts."""
    suite = SuiteRegistry().get_suite("concurrent-load")
    assert suite is not None

    args = _build_script_args(
        suite,
        {
            "vllm_cpu_start": 64,
            "guidellm_cpus": "0-31",
            "continue_on_error": True,
        },
    )

    assert args == [
        "--vllm-cpu-start",
        "64",
        "--guidellm-cpus",
        "0-31",
        "--continue-on-error",
    ]


def test_build_script_args_vllm_cpus_mapping():
    """--vllm-cpus range is forwarded via the suite param_mapping."""
    suite = SuiteRegistry().get_suite("concurrent-load")
    assert suite is not None

    args = _build_script_args(suite, {"vllm_cpus": "64-95"})

    assert args == ["--vllm-cpus", "64-95"]


def test_build_script_args_preserves_existing_dash_prefix():
    """Mappings that already include -- are left unchanged."""
    suite = SuiteRegistry().get_suite("concurrent-load")
    assert suite is not None

    args = _build_script_args(suite, {"cores": "8"})

    assert args == ["--cores", "8"]


# ---------------------------------------------------------------------------
# _result_model_hint — preset blocklist
# ---------------------------------------------------------------------------

def test_result_model_hint_preset_tiny_returns_none():
    """'tiny' is a preset name and must not be used as a model directory filter."""
    assert _result_model_hint(None, "tiny", {}) is None


def test_result_model_hint_preset_llama_returns_none():
    """'llama' is a preset name and must not be used as a model directory filter."""
    assert _result_model_hint(None, "llama", {}) is None


def test_result_model_hint_preset_qwen_returns_none():
    """'qwen' is a preset name and must not be used as a model directory filter."""
    assert _result_model_hint(None, "qwen", {}) is None


def test_result_model_hint_preset_in_final_vars_returns_none():
    """Preset stored in final_vars.models must also be blocked."""
    assert _result_model_hint(None, None, {"models": "tiny"}) is None


def test_result_model_hint_real_model_returned():
    """An actual model ID passes through the blocklist unchanged."""
    model = "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
    assert _result_model_hint(model, None, {}) == model


def test_result_model_hint_prefers_explicit_model():
    """--model takes precedence over --models even when both are present."""
    assert (
        _result_model_hint(
            "RedHatAI/model-a", "tiny", {}
        ) == "RedHatAI/model-a"
    )
