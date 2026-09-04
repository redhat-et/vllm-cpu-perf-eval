"""Tests for the interactive cpueval wizard."""

import pytest

from cpueval.suite_registry import SuiteRegistry
from cpueval.wizard import (
    build_params_from_answers,
    get_host_env_status,
    run_wizard,
    select_suite_by_index,
    _sorted_suites,
    _wizard_fields_for_suite,
)


@pytest.fixture
def host_env(monkeypatch):
    monkeypatch.setenv("DUT_HOSTNAME", "dut.example.com")
    monkeypatch.setenv("LOADGEN_HOSTNAME", "loadgen.example.com")
    monkeypatch.delenv("VLLM_ENDPOINT_MODE", raising=False)


def test_wizard_fields_deduplicate_concurrent_load():
    registry = SuiteRegistry()
    suite = registry.get_suite("concurrent-load")
    assert suite is not None

    fields = _wizard_fields_for_suite(suite)
    assert fields == ["models", "cores", "workloads", "phase"]
    assert "model" not in fields
    assert "workload" not in fields


def test_get_host_env_status_managed_missing():
    import os

    for key in ("DUT_HOSTNAME", "LOADGEN_HOSTNAME", "VLLM_ENDPOINT_MODE"):
        os.environ.pop(key, None)

    status = get_host_env_status()
    assert status["mode"] == "managed"
    assert status["hosts_ready"] is False
    assert "DUT_HOSTNAME" in status["missing"]
    assert "LOADGEN_HOSTNAME" in status["missing"]


def test_get_host_env_status_managed_ready(host_env):
    status = get_host_env_status()
    assert status["hosts_ready"] is True
    assert status["dut_hostname"] == "dut.example.com"
    assert status["loadgen_hostname"] == "loadgen.example.com"


def test_select_suite_by_index_valid():
    registry = SuiteRegistry()
    suites = _sorted_suites(registry)
    suite = select_suite_by_index(suites, "1")
    assert suite is not None
    assert suite.name == "chat-smoke"


def test_select_suite_by_index_invalid():
    registry = SuiteRegistry()
    suites = _sorted_suites(registry)
    assert select_suite_by_index(suites, "0") is None
    assert select_suite_by_index(suites, "999") is None
    assert select_suite_by_index(suites, "abc") is None


def test_build_params_from_defaults():
    registry = SuiteRegistry()
    suite = registry.get_suite("concurrent-load")
    assert suite is not None

    result = build_params_from_answers(
        suite,
        {
            "models": "tiny",
            "cores": "8",
            "workloads": "chat",
            "phase": "1",
        },
        tag="smoke",
        dry_run=True,
        skip_doctor=True,
    )

    assert result.suite == "concurrent-load"
    assert result.models == "tiny"
    assert result.cores == "8"
    assert result.workloads == "chat"
    assert result.extra == ["phase=1"]
    assert result.tag == "smoke"
    assert result.dry_run is True
    assert result.skip_doctor is True


def test_build_params_embedding_num_prompts():
    registry = SuiteRegistry()
    suite = registry.get_suite("embedding")
    assert suite is not None

    result = build_params_from_answers(
        suite,
        {"models": "quick", "cores": "8", "scenario": "all", "num_prompts": "100"},
    )

    assert result.models == "quick"
    assert result.num_prompts == 100


def test_wizard_cancel_at_suite_prompt():
    from rich.console import Console

    result = run_wizard(Console(), inputs=["q"])
    assert result is None


def test_wizard_chat_smoke_dry_run(host_env):
    from rich.console import Console

    # customize=no, tag=skip, dry-run=yes, skip-doctor=yes, launch=yes
    result = run_wizard(
        Console(),
        inputs=["1", "n", "", "y", "y", "y"],
        force_dry_run=False,
        force_skip_doctor=False,
    )

    assert result is not None
    assert result.suite == "chat-smoke"
    assert result.dry_run is True


def test_build_params_cpu_pinning():
    registry = SuiteRegistry()
    suite = registry.get_suite("concurrent-load")
    assert suite is not None

    result = build_params_from_answers(
        suite,
        {
            "models": "tiny",
            "cores": "32",
            "workloads": "chat",
            "vllm_cpus": "64-95",
            "vllm_numa_node": "1",
            "guidellm_cpus": "0-31",
            "guidellm_numa_node": "0",
            "phase": "1",
        },
    )

    assert result.vllm_cpus == "64-95"
    assert result.vllm_numa == 1
    assert result.guidellm_cpus == "0-31"
    assert result.guidellm_numa == 0


def test_wizard_concurrent_load_tailored_flow(host_env):
    from rich.console import Console

    # suite 4, customize, models, cores, pinning x4, workloads, tag, dry-run, skip-doctor, launch
    result = run_wizard(
        Console(),
        inputs=[
            "4", "y", "tiny", "32", "64-95", "1", "0-31", "0", "chat",
            "", "y", "y", "y",
        ],
    )

    assert result is not None
    assert result.suite == "concurrent-load"
    assert result.models == "tiny"
    assert result.cores == "32"
    assert result.workloads == "chat"
    assert result.vllm_cpus == "64-95"
    assert result.vllm_numa == 1
    assert result.guidellm_cpus == "0-31"
    assert result.guidellm_numa == 0
    assert result.model is None
    assert result.workload is None


def test_wizard_cancel_at_launch(host_env):
    from rich.console import Console

    result = run_wizard(
        Console(),
        inputs=["2", "n", "", "n", "n", "n"],
    )

    assert result is None
