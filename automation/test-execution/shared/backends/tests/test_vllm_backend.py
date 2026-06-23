"""Unit tests for vLLM backend implementation."""

import pytest
from shared.backends import get_backend, vLLMBackend
from shared.backends.base import BackendConfig, BackendMetrics


class TestVLLMBackend:
    """Tests for vLLMBackend class."""

    def test_backend_name(self):
        """Test backend name is correct."""
        backend = vLLMBackend()
        assert backend.name == "vllm"

    def test_backend_version(self):
        """Test backend version is set."""
        backend = vLLMBackend()
        assert backend.version == "0.20.0"

    def test_container_image(self):
        """Test container image URL."""
        backend = vLLMBackend()
        image = backend.get_container_image()
        assert "vllm" in image.lower()
        assert backend.version in image

    def test_health_endpoint(self):
        """Test health check endpoint."""
        backend = vLLMBackend()
        assert backend.health_check_endpoint() == "/health"

    def test_models_endpoint(self):
        """Test models list endpoint."""
        backend = vLLMBackend()
        assert backend.models_endpoint() == "/v1/models"

    def test_feature_support(self):
        """Test feature support detection."""
        backend = vLLMBackend()
        assert backend.supports_feature("prefix-caching") is True
        assert backend.supports_feature("tensor-parallel") is True
        assert backend.supports_feature("quantization") is True
        assert backend.supports_feature("openai-api") is True
        assert backend.supports_feature("nonexistent-feature") is False

    def test_start_command_basic(self):
        """Test basic start command generation."""
        backend = vLLMBackend()
        config = BackendConfig(
            model="meta-llama/Llama-3.2-1B",
            host="0.0.0.0",
            port=8000,
        )
        cmd = backend.get_start_command(config)

        assert "--model" in cmd
        assert "meta-llama/Llama-3.2-1B" in cmd
        assert "--host" in cmd
        assert "0.0.0.0" in cmd
        assert "--port" in cmd
        assert "8000" in cmd

    def test_start_command_with_tensor_parallel(self):
        """Test start command with tensor parallelism."""
        backend = vLLMBackend()
        config = BackendConfig(
            model="meta-llama/Llama-3.2-1B",
            tensor_parallel=4,
        )
        cmd = backend.get_start_command(config)

        assert "--tensor-parallel-size" in cmd
        assert "4" in cmd

    def test_start_command_without_tensor_parallel(self):
        """Test start command doesn't include TP=1."""
        backend = vLLMBackend()
        config = BackendConfig(
            model="meta-llama/Llama-3.2-1B",
            tensor_parallel=1,
        )
        cmd = backend.get_start_command(config)

        # TP=1 should not be in command (it's default)
        assert "--tensor-parallel-size" not in cmd

    def test_start_command_with_extra_args_bool(self):
        """Test extra args with boolean flags."""
        backend = vLLMBackend()
        config = BackendConfig(
            model="meta-llama/Llama-3.2-1B",
            extra_args={
                "enable-prefix-caching": True,
                "disable-log-requests": False,
            },
        )
        cmd = backend.get_start_command(config)

        # True boolean becomes flag
        assert "--enable-prefix-caching" in cmd
        # False boolean is omitted
        assert "--disable-log-requests" not in cmd

    def test_start_command_with_extra_args_values(self):
        """Test extra args with key-value pairs."""
        backend = vLLMBackend()
        config = BackendConfig(
            model="meta-llama/Llama-3.2-1B",
            extra_args={
                "gpu-memory-utilization": 0.9,
                "quantization": "awq",
            },
        )
        cmd = backend.get_start_command(config)

        assert "--gpu-memory-utilization" in cmd
        assert "0.9" in cmd
        assert "--quantization" in cmd
        assert "awq" in cmd

    def test_get_container_env(self):
        """Test container environment variables."""
        backend = vLLMBackend()
        config = BackendConfig(model="meta-llama/Llama-3.2-1B")
        env = backend.get_container_env(config)

        # vLLM uses CLI args, not env vars (unlike TGI)
        assert env == {}


class TestBackendRegistry:
    """Tests for backend registry functions."""

    def test_get_backend_vllm(self):
        """Test getting vLLM backend from registry."""
        backend = get_backend("vllm")
        assert isinstance(backend, vLLMBackend)
        assert backend.name == "vllm"

    def test_get_backend_invalid(self):
        """Test getting non-existent backend raises error."""
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nonexistent")

    def test_get_backend_error_message(self):
        """Test error message lists available backends."""
        try:
            get_backend("invalid")
        except ValueError as e:
            assert "vllm" in str(e).lower()


class TestBackendConfig:
    """Tests for BackendConfig dataclass."""

    def test_defaults(self):
        """Test default configuration values."""
        config = BackendConfig(model="test-model")
        assert config.model == "test-model"
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.dtype == "bfloat16"
        assert config.max_tokens == 512
        assert config.tensor_parallel == 1
        assert config.extra_args == {}

    def test_custom_values(self):
        """Test custom configuration values."""
        config = BackendConfig(
            model="my-model",
            host="127.0.0.1",
            port=9000,
            dtype="float16",
            max_tokens=2048,
            tensor_parallel=4,
            extra_args={"key": "value"},
        )
        assert config.model == "my-model"
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.dtype == "float16"
        assert config.max_tokens == 2048
        assert config.tensor_parallel == 4
        assert config.extra_args == {"key": "value"}


class TestBackendMetrics:
    """Tests for BackendMetrics dataclass."""

    def test_required_fields(self):
        """Test creating metrics with required fields."""
        metrics = BackendMetrics(
            ttft_mean=10.5,
            tpot_mean=2.3,
            e2e_mean=50.2,
            requests_per_second=100.0,
            tokens_per_second=5000.0,
            memory_mb=8192.0,
            cpu_percent=75.5,
        )
        assert metrics.ttft_mean == 10.5
        assert metrics.tpot_mean == 2.3
        assert metrics.e2e_mean == 50.2
        assert metrics.requests_per_second == 100.0
        assert metrics.tokens_per_second == 5000.0
        assert metrics.memory_mb == 8192.0
        assert metrics.cpu_percent == 75.5

    def test_optional_fields(self):
        """Test optional metrics fields."""
        metrics = BackendMetrics(
            ttft_mean=10.0,
            tpot_mean=2.0,
            e2e_mean=50.0,
            requests_per_second=100.0,
            tokens_per_second=5000.0,
            memory_mb=8192.0,
            cpu_percent=75.0,
            kv_cache_usage=0.85,
            prefix_cache_hit_rate=0.92,
            raw_metrics={"custom": "data"},
        )
        assert metrics.kv_cache_usage == 0.85
        assert metrics.prefix_cache_hit_rate == 0.92
        assert metrics.raw_metrics == {"custom": "data"}
