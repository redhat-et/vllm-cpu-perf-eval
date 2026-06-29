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
    """Test GuideLLM load generator implementation."""

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
        assert loadgen.version == "0.6.0"

    def test_get_container_image(self, loadgen):
        """Test container image generation."""
        image = loadgen.get_container_image()
        assert image == "ghcr.io/vllm-project/guidellm:v0.6.0"

    def test_get_command(self, loadgen, config):
        """Test command generation (should be empty for GuideLLM)."""
        cmd = loadgen.get_command(config)
        assert cmd == []

    def test_get_env_vars_basic(self, loadgen, config):
        """Test basic environment variable generation."""
        env = loadgen.get_env_vars(config)
        assert env["GUIDELLM_TARGET"] == "http://localhost:8000"
        assert env["GUIDELLM_MODEL"] == "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        assert env["GUIDELLM_MAX_REQUESTS"] == "100"
        assert env["GUIDELLM_MAX_SECONDS"] == "300"
        assert env["GUIDELLM_OUTPUT_PATH"] == "/results"

    def test_get_env_vars_with_profile(self, loadgen, config):
        """Test environment variables with profile."""
        config.extra_args = {"profile": "sweep"}
        env = loadgen.get_env_vars(config)
        assert env["GUIDELLM_PROFILE"] == "sweep"

    def test_get_env_vars_with_rate(self, loadgen, config):
        """Test environment variables with rate."""
        config.rate = "10,20,40"
        env = loadgen.get_env_vars(config)
        assert env["GUIDELLM_RATE"] == "10,20,40"

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
        loadgen.validate_config(config)  # Should not raise

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

    def test_get_output_format(self, loadgen):
        """Test output format."""
        assert loadgen.get_output_format() == "json"


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
        assert loadgen.version == "0.20.0"

    def test_get_container_image(self, loadgen):
        """Test container image generation."""
        image = loadgen.get_container_image()
        assert image == "vllm/vllm-openai-cpu:v0.20.0"

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
