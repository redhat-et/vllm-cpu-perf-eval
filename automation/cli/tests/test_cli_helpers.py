"""Unit tests for cpueval CLI helper functions."""

import os

from cpueval.cli import (
    _apply_endpoint_env,
    _build_script_args,
    _complete_model,
    _complete_models,
    _complete_profile,
    _complete_suite,
    _result_model_hint,
)
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


# ---------------------------------------------------------------------------
# Shell completion helpers
# ---------------------------------------------------------------------------

def test_complete_suite_returns_all_when_empty(tmp_path, monkeypatch):
    """Empty incomplete string returns all registered suite names."""
    import cpueval.cli as cli_mod
    import cpueval.paths as paths_mod

    monkeypatch.setattr(paths_mod, "get_suites_dir", lambda: paths_mod.get_suites_dir())
    results = _complete_suite(None, None, "")
    assert isinstance(results, list)
    assert len(results) > 0
    assert all(isinstance(s, str) for s in results)


def test_complete_suite_prefix_filtering():
    """Prefix 'ch' returns only suites starting with 'ch'."""
    results = _complete_suite(None, None, "ch")
    assert results == ["chat-smoke"]


def test_complete_suite_no_match_returns_empty():
    """Prefix that matches nothing returns an empty list."""
    results = _complete_suite(None, None, "zzz-nonexistent")
    assert results == []


def test_complete_model_converts_double_underscore(tmp_path, monkeypatch):
    """Directory names with __ are converted to org/model format."""
    import cpueval.cli as cli_mod

    llm_dir = tmp_path / "llm"
    llm_dir.mkdir()
    (llm_dir / "meta-llama__Llama-3.2-1B-Instruct").mkdir()
    (llm_dir / "TinyLlama__TinyLlama-1.1B-Chat-v1.0").mkdir()

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    embed_dir = tmp_path / "embedding"
    embed_dir.mkdir()

    monkeypatch.setattr(cli_mod, "get_llm_results_dir", lambda: llm_dir)
    monkeypatch.setattr(cli_mod, "get_audio_results_dir", lambda: audio_dir)
    monkeypatch.setattr(cli_mod, "get_embedding_results_dir", lambda: embed_dir)

    results = _complete_model(None, None, "")
    assert "meta-llama/Llama-3.2-1B-Instruct" in results
    assert "TinyLlama/TinyLlama-1.1B-Chat-v1.0" in results


def test_complete_model_prefix_filtering(tmp_path, monkeypatch):
    """Prefix 'meta' returns only models starting with 'meta'."""
    import cpueval.cli as cli_mod

    llm_dir = tmp_path / "llm"
    llm_dir.mkdir()
    (llm_dir / "meta-llama__Llama-3.2-1B-Instruct").mkdir()
    (llm_dir / "TinyLlama__TinyLlama-1.1B-Chat-v1.0").mkdir()

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    embed_dir = tmp_path / "embedding"
    embed_dir.mkdir()

    monkeypatch.setattr(cli_mod, "get_llm_results_dir", lambda: llm_dir)
    monkeypatch.setattr(cli_mod, "get_audio_results_dir", lambda: audio_dir)
    monkeypatch.setattr(cli_mod, "get_embedding_results_dir", lambda: embed_dir)

    results = _complete_model(None, None, "meta")
    assert results == ["meta-llama/Llama-3.2-1B-Instruct"]


def test_complete_model_includes_embedding_results(tmp_path, monkeypatch):
    """Embedding results directory is included in model completion."""
    import cpueval.cli as cli_mod

    (tmp_path / "llm").mkdir()
    (tmp_path / "audio").mkdir()
    embed_dir = tmp_path / "embedding"
    embed_dir.mkdir()
    (embed_dir / "ibm-granite__granite-embedding-278m-multilingual").mkdir()

    monkeypatch.setattr(cli_mod, "get_llm_results_dir", lambda: tmp_path / "llm")
    monkeypatch.setattr(cli_mod, "get_audio_results_dir", lambda: tmp_path / "audio")
    monkeypatch.setattr(cli_mod, "get_embedding_results_dir", lambda: embed_dir)

    results = _complete_model(None, None, "ibm")
    assert "ibm-granite/granite-embedding-278m-multilingual" in results


def test_complete_model_missing_dirs_returns_empty(tmp_path, monkeypatch):
    """Missing results directories produce an empty list, not an exception."""
    import cpueval.cli as cli_mod

    monkeypatch.setattr(cli_mod, "get_llm_results_dir", lambda: tmp_path / "no-llm")
    monkeypatch.setattr(cli_mod, "get_audio_results_dir", lambda: tmp_path / "no-audio")
    monkeypatch.setattr(cli_mod, "get_embedding_results_dir", lambda: tmp_path / "no-embed")

    assert _complete_model(None, None, "") == []


def test_complete_models_includes_presets():
    """_complete_models surfaces preset names alongside discovered models."""
    results = _complete_models(None, None, "")
    for preset in ("all", "tiny", "llama", "qwen", "granite"):
        assert preset in results


def test_complete_models_preset_prefix_filtering():
    """Prefix 't' returns 'tiny' from presets."""
    results = _complete_models(None, None, "t")
    assert "tiny" in results


def test_complete_profile_returns_stem(tmp_path, monkeypatch):
    """Profile names are returned without the .yaml extension."""
    import cpueval.cli as cli_mod

    (tmp_path / "dual-socket-split.yaml").touch()
    (tmp_path / "single-socket.yaml").touch()

    monkeypatch.setattr(cli_mod, "get_profiles_dir", lambda: tmp_path)

    results = _complete_profile(None, None, "")
    assert "dual-socket-split" in results
    assert "single-socket" in results
    assert not any(r.endswith(".yaml") for r in results)


def test_complete_profile_prefix_filtering(tmp_path, monkeypatch):
    """Prefix 'dual' returns only matching profiles."""
    import cpueval.cli as cli_mod

    (tmp_path / "dual-socket-split.yaml").touch()
    (tmp_path / "single-socket.yaml").touch()

    monkeypatch.setattr(cli_mod, "get_profiles_dir", lambda: tmp_path)

    results = _complete_profile(None, None, "dual")
    assert results == ["dual-socket-split"]


def test_complete_profile_missing_dir_returns_empty(tmp_path, monkeypatch):
    """Missing profiles directory produces an empty list, not an exception."""
    import cpueval.cli as cli_mod

    monkeypatch.setattr(cli_mod, "get_profiles_dir", lambda: tmp_path / "no-profiles")

    assert _complete_profile(None, None, "") == []
