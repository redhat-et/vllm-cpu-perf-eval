"""
Integration tests for load generator abstraction layer.

Tests the public API of the load generator abstraction:
- Registry and factory functions
- GuideLLM implementation
- vLLM bench implementation
- MTEB implementation
- Configuration generation
- Metrics parsing
"""

import json
import tempfile
from pathlib import Path

import pytest

from shared.loadgens import (
    get_loadgen,
    list_loadgens,
    LoadGenConfig,
    LoadGenMetrics,
)
from shared.loadgens.guidellm_loadgen import GuideLLMLoadGen
from shared.loadgens.vllm_bench_loadgen import VLLMBenchLoadGen
from shared.loadgens.mteb_loadgen import MTEBLoadGen


class TestLoadGenRegistry:
    """Test load generator registry and factory functions."""

    def test_list_loadgens(self):
        """Test listing all available load generators."""
        loadgens = list_loadgens()
        assert isinstance(loadgens, list)
        # Check for required load generators without asserting exact count
        assert "guidellm" in loadgens
        assert "vllm_bench" in loadgens
        assert "mteb" in loadgens

    def test_get_loadgen_guidellm(self):
        """Test getting GuideLLM load generator."""
        loadgen = get_loadgen("guidellm")
        assert isinstance(loadgen, GuideLLMLoadGen)
        assert loadgen.name == "guidellm"

    def test_get_loadgen_vllm_bench(self):
        """Test getting vLLM bench load generator."""
        loadgen = get_loadgen("vllm_bench")
        assert isinstance(loadgen, VLLMBenchLoadGen)
        assert loadgen.name == "vllm_bench"

    def test_get_loadgen_mteb(self):
        """Test getting MTEB load generator."""
        loadgen = get_loadgen("mteb")
        assert isinstance(loadgen, MTEBLoadGen)
        assert loadgen.name == "mteb"

    def test_get_loadgen_invalid(self):
        """Test getting invalid load generator raises error."""
        with pytest.raises(ValueError) as exc_info:
            get_loadgen("invalid_loadgen")
        assert "Unknown load generator: invalid_loadgen" in str(exc_info.value)


class TestGuideLLMLoadGen:
    """Test GuideLLM load generator (v0.7.x, default)."""

    @pytest.fixture
    def loadgen(self):
        return GuideLLMLoadGen()

    @pytest.fixture
    def config(self):
        return LoadGenConfig(
            target_url="http://localhost:8000",
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            workload_type="chat",
            max_requests=100,
            max_seconds=300,
            output_path="/results",
        )

    def test_name_and_version(self, loadgen):
        """Test load generator name and version."""
        assert loadgen.name == "guidellm"
        assert loadgen.version == "0.7.1"

    def test_get_container_image(self, loadgen):
        """Test container image generation."""
        image = loadgen.get_container_image()
        assert image == "ghcr.io/vllm-project/guidellm:v0.7.1"

    def test_is_v7_or_later(self, loadgen):
        """Test version detection property."""
        assert loadgen._is_v7_or_later is True

    def test_get_command_v7(self, loadgen, config):
        """Test v0.7.x generates CLI args."""
        cmd = loadgen.get_command(config)
        assert cmd[0] == "run"
        assert "--backend" in cmd
        assert "--data" in cmd
        assert "--tokenizer" in cmd
        assert "--profile" in cmd
        assert "--constraint" in cmd
        assert "--output" in cmd

    def test_get_command_v7_backend(self, loadgen, config):
        """Test v0.7.x --backend arg format."""
        cmd = loadgen.get_command(config)
        idx = cmd.index("--backend")
        backend = cmd[idx + 1]
        assert backend.startswith("kind=openai_http,target=")
        assert "http://localhost:8000" in backend

    def test_get_command_v7_data(self, loadgen, config):
        """Test v0.7.x --data arg format."""
        config.extra_args = {"isl": 256, "osl": 128}
        cmd = loadgen.get_command(config)
        idx = cmd.index("--data")
        data = cmd[idx + 1]
        assert "kind=synthetic_text" in data
        assert "prompt_tokens=256" in data
        assert "output_tokens=128" in data

    def test_get_command_v7_profile_sweep(self, loadgen, config):
        """Test v0.7.x --profile with sweep."""
        config.extra_args = {"profile": "sweep"}
        cmd = loadgen.get_command(config)
        idx = cmd.index("--profile")
        profile = cmd[idx + 1]
        assert "kind=sweep" in profile

    def test_get_command_v7_profile_concurrent(self, loadgen, config):
        """Test v0.7.x concurrent profile with rates."""
        config.extra_args = {"profile": "concurrent"}
        config.rate = "1,2,4,8"
        cmd = loadgen.get_command(config)
        idx = cmd.index("--profile")
        profile = cmd[idx + 1]
        assert "kind=concurrent" in profile
        assert "streams=1" in profile
        assert "--override" in cmd
        oidx = cmd.index("--override")
        assert cmd[oidx + 1] == "profile.streams"
        assert cmd[oidx + 2] == "1,2,4,8"

    def test_get_command_v7_constraints(self, loadgen, config):
        """Test v0.7.x --constraint args."""
        cmd = loadgen.get_command(config)
        constraints = [
            cmd[i + 1] for i, v in enumerate(cmd)
            if v == "--constraint"
        ]
        duration = [c for c in constraints if "max_duration" in c]
        requests = [c for c in constraints if "max_requests" in c]
        assert len(duration) == 1
        assert "seconds=300" in duration[0]
        assert len(requests) == 1
        assert "count=100" in requests[0]

    def test_get_command_v7_output(self, loadgen, config):
        """Test v0.7.x --output arg."""
        cmd = loadgen.get_command(config)
        idx = cmd.index("--output")
        output = cmd[idx + 1]
        assert "kind=json" in output
        assert "benchmarks.json" in output

    def test_get_env_vars_v7_minimal(self, loadgen, config):
        """Test v0.7.x returns minimal env vars."""
        env = loadgen.get_env_vars(config)
        assert "GUIDELLM_TARGET" not in env
        assert "GUIDELLM_PROFILE" not in env

    def test_get_env_vars_v7_with_hf_token(self, loadgen, config):
        """Test v0.7.x passes through HF_TOKEN."""
        config.extra_args = {"HF_TOKEN": "hf_test"}
        env = loadgen.get_env_vars(config)
        assert env["HF_TOKEN"] == "hf_test"

    def test_supports_workload_generative(self, loadgen):
        """Test workload support for generative workloads."""
        assert loadgen.supports_workload("chat") is True
        assert loadgen.supports_workload("rag") is True
        assert loadgen.supports_workload("code") is True
        assert loadgen.supports_workload("summarization") is True

    def test_supports_workload_embedding(self, loadgen):
        """Test workload support for embedding."""
        assert loadgen.supports_workload("embedding") is True

    def test_supports_workload_invalid(self, loadgen):
        """Test workload support for invalid workload."""
        assert loadgen.supports_workload("invalid") is False

    def test_validate_config_valid(self, loadgen, config):
        """Test configuration validation with valid config."""
        loadgen.validate_config(config)

    def test_validate_config_missing_target(self, loadgen, config):
        """Test configuration validation with missing target."""
        config.target_url = ""
        with pytest.raises(ValueError) as exc_info:
            loadgen.validate_config(config)
        assert "target_url is required" in str(exc_info.value)

    def test_validate_config_missing_model(self, loadgen, config):
        """Test configuration validation with missing model."""
        config.model = ""
        with pytest.raises(ValueError) as exc_info:
            loadgen.validate_config(config)
        assert "model is required" in str(exc_info.value)

    def test_validate_config_v7_profiles(self, loadgen, config):
        """Test v0.7.x accepts constant and poisson profiles."""
        for profile in ['constant', 'poisson']:
            config.extra_args = {"profile": profile}
            loadgen.validate_config(config)

    def test_get_output_format(self, loadgen):
        """Test output format."""
        assert loadgen.get_output_format() == "json"


class _GuideLLMV6(GuideLLMLoadGen):
    """GuideLLM subclass simulating v0.6.x for testing."""

    @property
    def version(self) -> str:
        return "0.6.0"


class TestGuideLLMLoadGenV6:
    """Test GuideLLM backward compat with v0.6.x."""

    @pytest.fixture
    def loadgen(self):
        return _GuideLLMV6()

    @pytest.fixture
    def config(self):
        return LoadGenConfig(
            target_url="http://localhost:8000",
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            workload_type="chat",
            max_requests=100,
            max_seconds=300,
            output_path="/results",
        )

    def test_is_not_v7(self, loadgen):
        """Test v0.6.x is detected as legacy."""
        assert loadgen._is_v7_or_later is False

    def test_get_command_empty(self, loadgen, config):
        """Test v0.6.x returns empty command."""
        cmd = loadgen.get_command(config)
        assert cmd == []

    def test_get_env_vars_full(self, loadgen, config):
        """Test v0.6.x returns full env var set."""
        env = loadgen.get_env_vars(config)
        assert env["GUIDELLM_TARGET"] == "http://localhost:8000"
        assert env["GUIDELLM_MODEL"] == (
            "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        )
        assert env["GUIDELLM_MAX_REQUESTS"] == "100"
        assert env["GUIDELLM_MAX_SECONDS"] == "300"
        assert env["GUIDELLM_OUTPUT_PATH"] == "/results"

    def test_get_env_vars_with_profile(self, loadgen, config):
        """Test v0.6.x env vars include profile."""
        config.extra_args = {"profile": "sweep"}
        env = loadgen.get_env_vars(config)
        assert env["GUIDELLM_PROFILE"] == "sweep"

    def test_get_env_vars_with_rate(self, loadgen, config):
        """Test v0.6.x env vars include rate."""
        config.rate = "10,20,40"
        env = loadgen.get_env_vars(config)
        assert env["GUIDELLM_RATE"] == "10,20,40"

    def test_validate_rejects_v7_profiles(self, loadgen, config):
        """Test v0.6.x rejects constant/poisson profiles."""
        config.extra_args = {"profile": "constant"}
        with pytest.raises(ValueError):
            loadgen.validate_config(config)


class TestVLLMBenchLoadGen:
    """Test vLLM bench load generator implementation."""

    @pytest.fixture
    def loadgen(self):
        return VLLMBenchLoadGen()

    @pytest.fixture
    def config(self):
        return LoadGenConfig(
            target_url="http://localhost:8000",
            model="granite-embedding",
            workload_type="embedding",
            max_requests=250,
            rate="inf",
            output_path="/results/baseline.json",
            dataset="random",
        )

    def test_name_and_version(self, loadgen):
        """Test load generator name and version."""
        assert loadgen.name == "vllm_bench"
        assert loadgen.version == "0.25.1"

    def test_get_container_image(self, loadgen):
        """Test container image generation."""
        image = loadgen.get_container_image()
        assert image == "vllm/vllm-openai-cpu:v0.25.1"

    def test_get_command_embedding(self, loadgen, config):
        """Test command generation for embedding workload."""
        cmd = loadgen.get_command(config)
        assert "vllm" in cmd
        assert "bench" in cmd
        assert "serve" in cmd
        assert "--backend" in cmd
        assert "openai-embeddings" in cmd
        assert "--endpoint" in cmd
        assert "/v1/embeddings" in cmd
        assert "--model" in cmd
        assert "granite-embedding" in cmd
        assert "--request-rate" in cmd
        assert "inf" in cmd

    def test_get_command_generative(self, loadgen):
        """Test command generation for generative workload."""
        config = LoadGenConfig(
            target_url="http://localhost:8000",
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            workload_type="chat",
            max_requests=100,
        )
        cmd = loadgen.get_command(config)
        assert "vllm" in cmd
        assert "bench" in cmd
        assert "serve" in cmd
        assert "--backend" in cmd
        # For generative, should use "openai" backend
        backend_idx = cmd.index("--backend")
        assert cmd[backend_idx + 1] == "openai"

    def test_get_env_vars(self, loadgen, config):
        """Test environment variable generation."""
        env = loadgen.get_env_vars(config)
        # vLLM bench uses CLI args mostly, minimal env vars
        assert isinstance(env, dict)

    def test_get_env_vars_with_hf_token(self, loadgen, config):
        """Test environment variables with HF token."""
        config.extra_args = {"HF_TOKEN": "hf_test123"}
        env = loadgen.get_env_vars(config)
        assert env["HF_TOKEN"] == "hf_test123"

    def test_supports_workload(self, loadgen):
        """Test workload support."""
        assert loadgen.supports_workload("chat") is True
        assert loadgen.supports_workload("embedding") is True
        assert loadgen.supports_workload("rag") is True
        assert loadgen.supports_workload("invalid") is False

    def test_validate_config_valid(self, loadgen, config):
        """Test configuration validation with valid config."""
        loadgen.validate_config(config)  # Should not raise

    def test_validate_config_invalid_max_requests(self, loadgen, config):
        """Test configuration validation with invalid max_requests."""
        config.max_requests = 0
        with pytest.raises(ValueError) as exc_info:
            loadgen.validate_config(config)
        assert "max_requests must be positive" in str(exc_info.value)

    def test_parse_results(self, loadgen):
        """Test parsing vLLM bench results."""
        # Create temporary results file
        results_data = {
            "total_requests": 250,
            "successful_requests": 250,
            "failed_requests": 0,
            "request_throughput": 12.5,
            "token_throughput": 625.0,
            "latency_mean": 0.045,  # 45ms in seconds
            "latency_p50": 0.042,
            "latency_p95": 0.068,
            "latency_p99": 0.086,
            "duration": 20.0,
        }

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            json.dump(results_data, f)
            results_path = f.name

        try:
            metrics = loadgen.parse_results(results_path)
            assert metrics.requests_total == 250
            assert metrics.requests_successful == 250
            assert metrics.requests_failed == 0
            assert metrics.throughput_rps == 12.5
            assert metrics.throughput_tps == 625.0
            assert metrics.latency_mean_ms == 45.0  # Converted to ms
            assert metrics.duration_seconds == 20.0
        finally:
            Path(results_path).unlink()


class TestMTEBLoadGen:
    """Test MTEB load generator implementation."""

    @pytest.fixture
    def loadgen(self):
        return MTEBLoadGen()

    @pytest.fixture
    def config(self):
        return LoadGenConfig(
            target_url="http://localhost:8000",
            model="granite-embedding",
            workload_type="embedding",
            output_path="/results",
            extra_args={"task_preset": "quick"},
        )

    def test_name_and_version(self, loadgen):
        """Test load generator name and version."""
        assert loadgen.name == "mteb"
        assert loadgen.version == "1.0"

    def test_get_container_image(self, loadgen):
        """Test container image generation."""
        image = loadgen.get_container_image()
        assert image == "quay.io/vllm-cpu-perf-eval/vllm-mteb:latest"

    def test_get_command(self, loadgen, config):
        """Test command generation (should be empty for MTEB)."""
        cmd = loadgen.get_command(config)
        assert cmd == []

    def test_get_env_vars_basic(self, loadgen, config):
        """Test basic environment variable generation."""
        env = loadgen.get_env_vars(config)
        assert env["MTEB_MODEL_NAME"] == "granite-embedding"
        assert env["MTEB_VLLM_ENDPOINT"] == "http://localhost:8000"
        assert env["MTEB_OUTPUT_DIR"] == "/results"
        assert env["MTEB_TASK_PRESET"] == "quick"
        assert env["MTEB_LANGUAGES"] == "eng"

    def test_get_env_vars_custom_tasks(self, loadgen, config):
        """Test environment variables with custom tasks."""
        config.extra_args = {"tasks": "TaskA,TaskB,TaskC"}
        env = loadgen.get_env_vars(config)
        assert env["MTEB_TASKS"] == "TaskA,TaskB,TaskC"
        assert "MTEB_TASK_PRESET" not in env

    def test_get_env_vars_with_batch_size(self, loadgen, config):
        """Test environment variables with batch size."""
        config.extra_args = {"task_preset": "quick", "batch_size": 64}
        env = loadgen.get_env_vars(config)
        assert env["MTEB_BATCH_SIZE"] == "64"

    def test_supports_workload_embedding_only(self, loadgen):
        """Test MTEB only supports embedding workloads."""
        assert loadgen.supports_workload("embedding") is True
        assert loadgen.supports_workload("chat") is False
        assert loadgen.supports_workload("rag") is False
        assert loadgen.supports_workload("code") is False

    def test_validate_config_valid(self, loadgen, config):
        """Test configuration validation with valid config."""
        loadgen.validate_config(config)  # Should not raise

    def test_validate_config_invalid_preset(self, loadgen, config):
        """Test configuration validation with invalid preset."""
        config.extra_args = {"task_preset": "invalid"}
        with pytest.raises(ValueError) as exc_info:
            loadgen.validate_config(config)
        assert "Invalid MTEB task_preset" in str(exc_info.value)

    def test_validate_config_valid_presets(self, loadgen, config):
        """Test configuration validation with all valid presets."""
        for preset in ["quick", "standard", "comprehensive"]:
            config.extra_args = {"task_preset": preset}
            loadgen.validate_config(config)  # Should not raise

    def test_get_output_format(self, loadgen):
        """Test output format."""
        assert loadgen.get_output_format() == "json"


class TestLoadGenConfig:
    """Test LoadGenConfig dataclass."""

    def test_config_defaults(self):
        """Test default values."""
        config = LoadGenConfig(
            target_url="http://localhost:8000",
            model="test-model",
        )
        assert config.workload_type == "chat"
        assert config.max_requests == 1000
        assert config.max_seconds == 600
        assert config.rate is None
        assert config.output_path == "/results"
        assert config.dataset is None
        assert config.extra_args == {}

    def test_config_custom_values(self):
        """Test custom values."""
        config = LoadGenConfig(
            target_url="http://localhost:8000",
            model="test-model",
            workload_type="embedding",
            max_requests=250,
            max_seconds=300,
            rate="inf",
            output_path="/custom/path",
            dataset="random",
            extra_args={"key": "value"},
        )
        assert config.workload_type == "embedding"
        assert config.max_requests == 250
        assert config.max_seconds == 300
        assert config.rate == "inf"
        assert config.output_path == "/custom/path"
        assert config.dataset == "random"
        assert config.extra_args == {"key": "value"}


class TestLoadGenMetrics:
    """Test LoadGenMetrics dataclass."""

    def test_metrics_defaults(self):
        """Test default values."""
        metrics = LoadGenMetrics()
        assert metrics.requests_total == 0
        assert metrics.requests_successful == 0
        assert metrics.requests_failed == 0
        assert metrics.throughput_rps == 0.0
        assert metrics.throughput_tps == 0.0
        assert metrics.latency_mean_ms == 0.0
        assert metrics.duration_seconds == 0.0
        assert metrics.raw_metrics == {}

    def test_metrics_custom_values(self):
        """Test custom values."""
        metrics = LoadGenMetrics(
            requests_total=100,
            requests_successful=98,
            requests_failed=2,
            throughput_rps=10.5,
            latency_mean_ms=45.2,
        )
        assert metrics.requests_total == 100
        assert metrics.requests_successful == 98
        assert metrics.requests_failed == 2
        assert metrics.throughput_rps == 10.5
        assert metrics.latency_mean_ms == 45.2
