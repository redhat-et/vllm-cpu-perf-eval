"""
Integration tests for backend abstraction.

These tests validate the complete backend abstraction flow including:
- Backend discovery and registration
- Command generation
- Configuration validation
- Metrics parsing
"""

import pytest
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from backends import get_backend, list_backends, BACKENDS
from backends.base import BackendConfig, BackendMetrics


class TestBackendRegistry:
    """Test backend registration and discovery."""

    def test_list_backends(self):
        """Test that list_backends returns expected backends."""
        backends = list_backends()
        assert isinstance(backends, list)
        assert len(backends) > 0
        assert 'vllm' in backends

    def test_backend_registry_not_empty(self):
        """Test that BACKENDS registry is populated."""
        assert len(BACKENDS) > 0
        assert 'vllm' in BACKENDS

    def test_get_backend_vllm(self):
        """Test that vLLM backend can be retrieved."""
        backend = get_backend('vllm')
        assert backend is not None
        assert backend.name == 'vllm'

    def test_get_backend_invalid(self):
        """Test that invalid backend raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_backend('nonexistent')
        assert 'Unknown backend' in str(exc_info.value)
        assert 'Available backends' in str(exc_info.value)


class TestVLLMBackend:
    """Integration tests for vLLM backend."""

    @pytest.fixture
    def vllm_backend(self):
        """Fixture to get vLLM backend instance."""
        return get_backend('vllm')

    @pytest.fixture
    def basic_config(self):
        """Fixture for basic backend configuration."""
        return BackendConfig(
            model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            host="0.0.0.0",
            port=8000,
            dtype="bfloat16",
            max_tokens=512
        )

    def test_backend_properties(self, vllm_backend):
        """Test basic backend properties."""
        assert vllm_backend.name == 'vllm'
        assert vllm_backend.version is not None
        assert len(vllm_backend.version) > 0

    def test_get_container_image(self, vllm_backend):
        """Test container image generation."""
        image = vllm_backend.get_container_image()
        assert 'vllm' in image.lower()
        assert 'openai-cpu' in image
        assert vllm_backend.version in image

    def test_health_check_endpoint(self, vllm_backend):
        """Test health check endpoint."""
        endpoint = vllm_backend.health_check_endpoint()
        assert endpoint == '/health'

    def test_models_endpoint(self, vllm_backend):
        """Test models endpoint."""
        endpoint = vllm_backend.models_endpoint()
        assert endpoint == '/v1/models'

    def test_supports_features(self, vllm_backend):
        """Test feature support detection."""
        assert vllm_backend.supports_feature('prefix-caching') is True
        assert vllm_backend.supports_feature('tensor-parallel') is True
        assert vllm_backend.supports_feature('openai-api') is True
        assert vllm_backend.supports_feature('nonexistent-feature') is False

    def test_get_start_command_basic(self, vllm_backend, basic_config):
        """Test basic command generation."""
        cmd = vllm_backend.get_start_command(basic_config)

        assert isinstance(cmd, list)
        assert '--model' in cmd
        assert 'TinyLlama/TinyLlama-1.1B-Chat-v1.0' in cmd
        assert '--host' in cmd
        assert '0.0.0.0' in cmd
        assert '--port' in cmd
        assert '8000' in cmd
        assert '--dtype' in cmd
        assert 'bfloat16' in cmd
        assert '--max-model-len' in cmd
        assert '512' in cmd

    def test_get_start_command_with_extra_args(self, vllm_backend):
        """Test command generation with extra arguments."""
        config = BackendConfig(
            model="test-model",
            extra_args={
                'enable-prefix-caching': True,
                'disable-log-requests': True,
                'gpu-memory-utilization': 0.9
            }
        )

        cmd = vllm_backend.get_start_command(config)

        # Boolean flags should be present
        assert '--enable-prefix-caching' in cmd
        assert '--disable-log-requests' in cmd

        # Key-value args should have both parts
        assert '--gpu-memory-utilization' in cmd
        assert '0.9' in cmd

    def test_get_start_command_tensor_parallel(self, vllm_backend):
        """Test command generation with tensor parallelism."""
        config = BackendConfig(
            model="test-model",
            extra_args={'tensor_parallel': 2}
        )

        cmd = vllm_backend.get_start_command(config)

        # tensor_parallel should be converted to CLI arg
        assert '--tensor_parallel' in cmd or 'tensor_parallel' in str(cmd)

    def test_validate_config_valid(self, vllm_backend, basic_config):
        """Test configuration validation with valid config."""
        # Should not raise
        vllm_backend.validate_config(basic_config)

    def test_validate_config_missing_model(self, vllm_backend):
        """Test configuration validation with missing model."""
        config = BackendConfig(model="")
        with pytest.raises(ValueError) as exc_info:
            vllm_backend.validate_config(config)
        assert 'Model name is required' in str(exc_info.value)

    def test_validate_config_invalid_port(self, vllm_backend):
        """Test configuration validation with invalid port."""
        config = BackendConfig(model="test", port=99999)
        with pytest.raises(ValueError) as exc_info:
            vllm_backend.validate_config(config)
        assert 'Invalid port' in str(exc_info.value)

    def test_validate_config_invalid_max_tokens(self, vllm_backend):
        """Test configuration validation with invalid max_tokens."""
        config = BackendConfig(model="test", max_tokens=-1)
        with pytest.raises(ValueError) as exc_info:
            vllm_backend.validate_config(config)
        assert 'Invalid max_tokens' in str(exc_info.value)

    def test_get_env_vars(self, vllm_backend, basic_config):
        """Test environment variable generation."""
        env_vars = vllm_backend.get_env_vars(basic_config)
        assert isinstance(env_vars, dict)
        # vLLM uses CLI args primarily, so env should be empty or minimal

    def test_parse_metrics_empty_samples(self, vllm_backend):
        """Test metrics parsing with empty samples."""
        metrics_data = {'samples': []}
        metrics = vllm_backend.parse_metrics(metrics_data)

        # Should return default metrics, not crash
        assert isinstance(metrics, BackendMetrics)
        assert metrics.ttft_mean >= 0
        assert metrics.e2e_mean >= 0

    def test_parse_metrics_with_data(self, vllm_backend):
        """Test metrics parsing with actual data."""
        metrics_data = {
            'samples': [
                {
                    'timestamp': '2024-01-01T00:00:00',
                    'metrics': {
                        'vllm:time_to_first_token_seconds_sum': [{'value': 10.0}],
                        'vllm:time_to_first_token_seconds_count': [{'value': 100}],
                        'vllm:e2e_request_latency_seconds_sum': [{'value': 50.0}],
                        'vllm:e2e_request_latency_seconds_count': [{'value': 100}],
                        'vllm:request_decode_time_seconds_sum': [{'value': 40.0}],
                        'vllm:request_generation_tokens_sum': [{'value': 1000}],
                        'vllm:prompt_tokens_total': [{'value': 5000}],
                        'vllm:generation_tokens_total': [{'value': 1000}],
                        'process_resident_memory_bytes': [{'value': 1024*1024*1024}],
                        'process_cpu_seconds_total': [{'value': 100}],
                    }
                }
            ]
        }

        metrics = vllm_backend.parse_metrics(metrics_data)

        assert isinstance(metrics, BackendMetrics)
        assert metrics.ttft_mean > 0  # Should be 100ms (10s / 100 requests * 1000)
        assert metrics.e2e_mean > 0   # Should be 500ms (50s / 100 requests * 1000)
        assert metrics.tpot_mean > 0  # Should be 40ms (40s / 1000 tokens * 1000)
        assert metrics.memory_mb > 0  # Should be 1024 MB
        assert metrics.raw_metrics == metrics_data


class TestBackendConfigDataclass:
    """Test BackendConfig dataclass behavior."""

    def test_default_values(self):
        """Test that default values are applied."""
        config = BackendConfig(model="test-model")

        assert config.model == "test-model"
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.dtype == "bfloat16"
        assert config.max_tokens == 512
        assert config.workload_type == "chat"
        assert config.container_name is None
        assert config.cpu_count is None
        assert config.memory_gb is None
        assert isinstance(config.extra_args, dict)
        assert len(config.extra_args) == 0

    def test_override_defaults(self):
        """Test that defaults can be overridden."""
        config = BackendConfig(
            model="test-model",
            host="127.0.0.1",
            port=9000,
            dtype="float16",
            max_tokens=1024,
            workload_type="completion"
        )

        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.dtype == "float16"
        assert config.max_tokens == 1024
        assert config.workload_type == "completion"

    def test_extra_args(self):
        """Test extra_args handling."""
        config = BackendConfig(
            model="test",
            extra_args={'custom-flag': True, 'custom-value': 123}
        )

        assert 'custom-flag' in config.extra_args
        assert config.extra_args['custom-flag'] is True
        assert config.extra_args['custom-value'] == 123


class TestBackendMetricsDataclass:
    """Test BackendMetrics dataclass behavior."""

    def test_default_values(self):
        """Test that metrics default to 0."""
        metrics = BackendMetrics()

        assert metrics.ttft_mean == 0.0
        assert metrics.tpot_mean == 0.0
        assert metrics.e2e_mean == 0.0
        assert metrics.requests_per_second == 0.0
        assert metrics.tokens_per_second == 0.0
        assert metrics.memory_mb == 0.0
        assert metrics.cpu_percent == 0.0
        assert metrics.kv_cache_usage is None
        assert metrics.prefix_cache_hit_rate is None
        assert isinstance(metrics.raw_metrics, dict)

    def test_set_values(self):
        """Test setting metric values."""
        metrics = BackendMetrics(
            ttft_mean=100.5,
            tpot_mean=10.2,
            e2e_mean=500.3,
            requests_per_second=50.0,
            tokens_per_second=1000.0,
            memory_mb=2048.0,
            cpu_percent=75.5
        )

        assert metrics.ttft_mean == 100.5
        assert metrics.tpot_mean == 10.2
        assert metrics.e2e_mean == 500.3
        assert metrics.requests_per_second == 50.0
        assert metrics.tokens_per_second == 1000.0
        assert metrics.memory_mb == 2048.0
        assert metrics.cpu_percent == 75.5

    def test_optional_metrics(self):
        """Test optional vLLM-specific metrics."""
        metrics = BackendMetrics(
            kv_cache_usage=85.5,
            prefix_cache_hit_rate=92.3
        )

        assert metrics.kv_cache_usage == 85.5
        assert metrics.prefix_cache_hit_rate == 92.3


class TestCLIIntegration:
    """Integration tests for CLI functionality."""

    def test_cli_list_backends(self):
        """Test CLI list command."""
        import subprocess
        result = subprocess.run(
            ['python3', '-m', 'shared.backends', 'list'],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), '../..')
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert isinstance(output, list)
        assert 'vllm' in output

    def test_cli_get_backend(self):
        """Test CLI get-backend command."""
        import subprocess
        result = subprocess.run(
            ['python3', '-m', 'shared.backends', 'get-backend', 'vllm'],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), '../..')
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output['name'] == 'vllm'
        assert 'version' in output
        assert 'image' in output

    def test_cli_get_command(self):
        """Test CLI get-command."""
        import subprocess
        result = subprocess.run(
            [
                'python3', '-m', 'shared.backends', 'get-command', 'vllm',
                '--model', 'test-model',
                '--host', '0.0.0.0',
                '--port', '8000',
                '--dtype', 'bfloat16',
                '--max-tokens', '512',
                '--tensor-parallel', '1'
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), '../..')
        )

        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert 'command' in output
        assert 'env' in output
        assert 'image' in output
        assert isinstance(output['command'], list)
        assert '--model' in output['command']
        assert 'test-model' in output['command']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
