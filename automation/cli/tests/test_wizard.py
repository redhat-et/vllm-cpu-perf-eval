"""Tests for the interactive cpueval wizard."""

import pytest
import typer

from cpueval.suite_registry import SuiteRegistry
from cpueval.wizard import (
    build_params_from_answers,
    get_host_env_status,
    run_wizard,
    select_suite_by_index,
    validate_field_value,
    validate_tag,
    _sorted_suites,
    _suite_supports_cpu_pinning,
    _wizard_fields_for_suite,
)


@pytest.fixture
def host_env(monkeypatch):
    monkeypatch.setenv("DUT_HOSTNAME", "dut.example.com")
    monkeypatch.setenv("LOADGEN_HOSTNAME", "loadgen.example.com")
    monkeypatch.delenv("VLLM_ENDPOINT_MODE", raising=False)


def _suite_menu_index(name: str) -> str:
    suites = _sorted_suites(SuiteRegistry())
    for index, suite in enumerate(suites, start=1):
        if suite.name == name:
            return str(index)
    raise AssertionError(f"Suite not found in menu: {name}")


def test_wizard_fields_deduplicate_concurrent_load():
    registry = SuiteRegistry()
    suite = registry.get_suite("concurrent-load")
    assert suite is not None

    fields = _wizard_fields_for_suite(suite)
    assert fields == ["models", "cores", "workloads", "phase"]
    assert "model" not in fields
    assert "workload" not in fields


def test_get_host_env_status_managed_missing(monkeypatch):
    monkeypatch.delenv("DUT_HOSTNAME", raising=False)
    monkeypatch.delenv("LOADGEN_HOSTNAME", raising=False)
    monkeypatch.delenv("VLLM_ENDPOINT_MODE", raising=False)

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

    # customize, models, cores, pinning x4, workloads, tag, dry-run, skip-doctor, launch
    result = run_wizard(
        Console(),
        inputs=[
            _suite_menu_index("concurrent-load"),
            "y",
            "tiny",
            "32",
            "64-95",
            "1",
            "0-31",
            "0",
            "chat",
            "",
            "y",
            "y",
            "y",
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

    # chat-smoke: customize=no, tag=skip, dry-run=no, skip-doctor=no, launch=no
    result = run_wizard(
        Console(),
        inputs=[_suite_menu_index("chat-smoke"), "n", "", "n", "n", "n"],
    )

    assert result is None


def test_embedding_suite_supports_cpu_pinning():
    registry = SuiteRegistry()
    suite = registry.get_suite("embedding")
    assert suite is not None
    assert _suite_supports_cpu_pinning(suite)


def test_build_params_embedding_cpu_pinning():
    registry = SuiteRegistry()
    suite = registry.get_suite("embedding")
    assert suite is not None

    result = build_params_from_answers(
        suite,
        {
            "models": "quick",
            "cores": "16",
            "scenario": "all",
            "vllm_bench_cpus": "64-95",
            "vllm_bench_numa_node": "1",
        },
    )

    assert result.vllm_bench_cpus == "64-95"
    assert result.vllm_bench_numa == 1
    assert result.vllm_cpus is None
    assert result.guidellm_cpus is None


def test_wizard_embedding_cpu_pinning_flow(host_env):
    from rich.console import Console

    # customize, suite fields, skip inference pinning, bench pinning, tag, flags, launch
    result = run_wizard(
        Console(),
        inputs=[
            _suite_menu_index("embedding"),
            "y",
            "quick",
            "16",
            "all",
            "100",
            "",
            "",
            "64-95",
            "1",
            "",
            "y",
            "y",
            "y",
        ],
    )

    assert result is not None
    assert result.suite == "embedding"
    assert result.models == "quick"
    assert result.cores == "16"
    assert result.scenario == "all"
    assert result.num_prompts == 100
    assert result.vllm_cpus is None
    assert result.vllm_bench_cpus == "64-95"
    assert result.vllm_bench_numa == 1


def test_embedding_as_execute_kwargs_includes_bench_cpus():
    registry = SuiteRegistry()
    suite = registry.get_suite("embedding")
    assert suite is not None

    result = build_params_from_answers(
        suite,
        {"models": "quick", "vllm_bench_cpus": "0-31", "vllm_bench_numa_node": "0"},
    )

    kwargs = result.as_execute_kwargs()
    assert kwargs["vllm_bench_cpus"] == "0-31"
    assert kwargs["vllm_bench_numa"] == 0


# ─── Scale-out suites ────────────────────────────────────────────────────────


def test_wizard_fields_scaleout():
    registry = SuiteRegistry()
    suite = registry.get_suite("vllm-scaleout")
    assert suite is not None

    fields = _wizard_fields_for_suite(suite)
    assert fields == [
        "model",
        "num_instances",
        "cores_per_instance",
        "routing_policy",
        "start_core",
    ]


def test_wizard_fields_embedding_scaleout():
    registry = SuiteRegistry()
    suite = registry.get_suite("embedding-scaleout")
    assert suite is not None
    assert suite.runner == "ansible"
    fields = _wizard_fields_for_suite(suite)
    assert "model" in fields
    assert "num_instances" in fields
    assert "routing_policy" in fields


def test_get_host_env_status_external_ready(monkeypatch):
    monkeypatch.setenv("VLLM_ENDPOINT_MODE", "external")
    monkeypatch.setenv("VLLM_ENDPOINT_URL", "http://dut:8081/v1")

    status = get_host_env_status()
    assert status["mode"] == "external"
    assert status["hosts_ready"] is True
    assert status["missing"] == []


def test_get_host_env_status_external_missing_url(monkeypatch):
    monkeypatch.setenv("VLLM_ENDPOINT_MODE", "external")
    monkeypatch.delenv("VLLM_ENDPOINT_URL", raising=False)

    status = get_host_env_status()
    assert status["mode"] == "external"
    assert status["hosts_ready"] is False
    assert status["missing"] == ["VLLM_ENDPOINT_URL"]


def test_build_params_scaleout_maps_to_scaleout_vars():
    registry = SuiteRegistry()
    suite = registry.get_suite("vllm-scaleout")
    assert suite is not None

    result = build_params_from_answers(
        suite,
        {
            "model": "RedHatAI/granite-embedding-english-r2",
            "num_instances": "3",
            "cores_per_instance": "16",
            "routing_policy": "round_robin",
            "start_core": "0",
        },
    )

    assert result.suite == "vllm-scaleout"
    assert result.model == "RedHatAI/granite-embedding-english-r2"
    assert sorted(result.extra) == [
        "scaleout_cores_per_instance=16",
        "scaleout_num_instances=3",
        "scaleout_routing_policy=round_robin",
        "scaleout_start_core=0",
    ]


@pytest.mark.parametrize(
    "answers",
    [
        {"num_instances": "0"},
        {"num_instances": "11"},
        {"num_instances": "abc"},
        {"cores_per_instance": "12"},
        {"cores_per_instance": "fast"},
        {"routing_policy": "random"},
        {"start_core": "-1"},
        {"start_core": "zero"},
    ],
)
def test_build_params_scaleout_rejects_invalid_values(answers):
    registry = SuiteRegistry()
    suite = registry.get_suite("vllm-scaleout")
    assert suite is not None

    with pytest.raises(typer.BadParameter):
        build_params_from_answers(suite, answers)


def test_wizard_scaleout_customized_flow(host_env):
    from rich.console import Console

    # suite, customize, model, instances, cores/instance, routing, start core,
    # CPU pinning x2 (skip), tag, dry-run, skip-doctor, launch
    result = run_wizard(
        Console(),
        inputs=[
            _suite_menu_index("vllm-scaleout"),
            "y",
            "RedHatAI/granite-embedding-english-r2",
            "3", "16", "round_robin", "0",
            "", "",
            "scaleout-test", "y", "y", "y",
        ],
    )

    assert result is not None
    assert result.suite == "vllm-scaleout"
    assert result.model == "RedHatAI/granite-embedding-english-r2"
    assert sorted(result.extra) == [
        "scaleout_cores_per_instance=16",
        "scaleout_num_instances=3",
        "scaleout_routing_policy=round_robin",
        "scaleout_start_core=0",
    ]
    assert result.tag == "scaleout-test"
    assert result.dry_run is True


def test_wizard_scaleout_defaults_flow(host_env):
    from rich.console import Console

    # suite, no customize, tag skip, dry-run, skip-doctor, launch
    result = run_wizard(
        Console(),
        inputs=[
            _suite_menu_index("vllm-scaleout"),
            "n", "", "y", "y", "y",
        ],
    )

    assert result is not None
    assert result.suite == "vllm-scaleout"
    assert result.model == "meta-llama/Llama-3.2-1B-Instruct"
    assert sorted(result.extra) == [
        "scaleout_cores_per_instance=24",
        "scaleout_num_instances=2",
        "scaleout_routing_policy=intelligent",
        "scaleout_start_core=0",
    ]


# ─── Validation ──────────────────────────────────────────────────────────────


def test_validate_field_value_scaleout():
    assert validate_field_value("num_instances", "3") is None
    assert validate_field_value("num_instances", "1") is None
    assert validate_field_value("num_instances", "10") is None
    assert validate_field_value("cores_per_instance", "24") is None
    assert validate_field_value("routing_policy", "intelligent") is None
    assert validate_field_value("routing_policy", "round_robin") is None
    assert validate_field_value("start_core", "0") is None

    assert validate_field_value("num_instances", "0") is not None
    assert validate_field_value("num_instances", "11") is not None
    assert validate_field_value("num_instances", "abc") is not None
    assert validate_field_value("cores_per_instance", "12") is not None
    assert validate_field_value("routing_policy", "random") is not None
    assert validate_field_value("start_core", "-1") is not None

    # Non-scaleout fields are not validated by the wizard.
    assert validate_field_value("model", "anything-goes") is None


def test_validate_tag():
    assert validate_tag("smoke-1") is None
    assert validate_tag("a") is None
    assert validate_tag("x" * 30) is None

    assert validate_tag("") is not None
    assert validate_tag("bad tag!") is not None
    assert validate_tag("under_score") is not None
    assert validate_tag("x" * 31) is not None


def test_wizard_rejects_invalid_tag_then_accepts(host_env):
    from rich.console import Console

    result = run_wizard(
        Console(),
        inputs=[
            _suite_menu_index("chat-smoke"),
            "n", "bad tag!", "good-tag", "y", "y", "y",
        ],
    )

    assert result is not None
    assert result.tag == "good-tag"
