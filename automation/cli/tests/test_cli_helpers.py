"""Unit tests for cpueval CLI helper functions."""

import os

from cpueval.cli import _apply_endpoint_env, _build_script_args
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


def test_build_script_args_preserves_existing_dash_prefix():
    """Mappings that already include -- are left unchanged."""
    suite = SuiteRegistry().get_suite("concurrent-load")
    assert suite is not None

    args = _build_script_args(suite, {"cores": "8"})

    assert args == ["--cores", "8"]
