"""Tests for vLLM metrics parsing."""

import pytest
from shared.backends import vLLMBackend


class TestVLLMMetricsParsing:
    """Tests for vLLM parse_metrics() implementation."""

    def test_parse_metrics_basic(self):
        """Test basic metrics parsing from vLLM metrics JSON."""
        backend = vLLMBackend()

        # Realistic vLLM metrics structure
        metrics_data = {
            "samples": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "metrics": {
                        "vllm:time_to_first_token_seconds_sum": [{"value": 5.0}],
                        "vllm:time_to_first_token_seconds_count": [{"value": 10}],
                        "vllm:e2e_request_latency_seconds_sum": [{"value": 50.0}],
                        "vllm:e2e_request_latency_seconds_count": [{"value": 10}],
                        "vllm:request_decode_time_seconds_sum": [{"value": 20.0}],
                        "vllm:request_generation_tokens_sum": [{"value": 5000}],
                        "vllm:prompt_tokens_total": [{"value": 1000}],
                        "vllm:generation_tokens_total": [{"value": 5000}],
                        "process_resident_memory_bytes": [{"value": 8589934592}],  # 8GB
                        "process_cpu_seconds_total": [{"value": 120}],
                        "vllm:kv_cache_usage_perc": [{"value": 85.5}],
                        "vllm:prefix_cache_hits_total": [{"value": 800}],
                        "vllm:prefix_cache_queries_total": [{"value": 1000}],
                    },
                },
                {
                    "timestamp": "2024-01-01T10:02:00Z",  # 2 minutes later
                    "metrics": {
                        "vllm:time_to_first_token_seconds_sum": [{"value": 10.0}],
                        "vllm:time_to_first_token_seconds_count": [{"value": 20}],
                        "vllm:e2e_request_latency_seconds_sum": [{"value": 100.0}],
                        "vllm:e2e_request_latency_seconds_count": [{"value": 20}],
                        "vllm:request_decode_time_seconds_sum": [{"value": 40.0}],
                        "vllm:request_generation_tokens_sum": [{"value": 10000}],
                        "vllm:prompt_tokens_total": [{"value": 2000}],
                        "vllm:generation_tokens_total": [{"value": 10000}],
                        "process_resident_memory_bytes": [{"value": 8589934592}],
                        "process_cpu_seconds_total": [{"value": 240}],
                        "vllm:kv_cache_usage_perc": [{"value": 85.5}],
                        "vllm:prefix_cache_hits_total": [{"value": 1600}],
                        "vllm:prefix_cache_queries_total": [{"value": 2000}],
                    },
                },
            ]
        }

        result = backend.parse_metrics(metrics_data)

        # Uses last sample for metrics
        assert result.ttft_mean == 500.0  # 10.0 / 20 * 1000 ms
        assert result.e2e_mean == 5000.0  # 100.0 / 20 * 1000 ms
        assert result.tpot_mean == 4.0  # 40.0 / 10000 * 1000 ms per token

        # Throughput calculated from duration (120 seconds)
        assert result.requests_per_second == pytest.approx(20 / 120, rel=0.01)
        assert result.tokens_per_second == pytest.approx(12000 / 120, rel=0.01)

        # Memory and CPU
        assert result.memory_mb == pytest.approx(8192.0, rel=0.01)  # 8GB in MB
        assert result.cpu_percent == pytest.approx(200.0, rel=0.01)  # 240 / 120 * 100

        # vLLM-specific metrics
        assert result.kv_cache_usage == 85.5
        assert result.prefix_cache_hit_rate == pytest.approx(80.0, rel=0.01)  # 1600/2000*100

    def test_parse_metrics_empty_samples(self):
        """Test handling of empty samples."""
        backend = vLLMBackend()
        metrics_data = {"samples": []}

        result = backend.parse_metrics(metrics_data)

        # Should return zeros on error
        assert result.ttft_mean == 0.0
        assert result.e2e_mean == 0.0
        assert result.tpot_mean == 0.0
        assert result.requests_per_second == 0.0
        assert result.tokens_per_second == 0.0

    def test_parse_metrics_missing_fields(self):
        """Test handling of missing metric fields."""
        backend = vLLMBackend()
        metrics_data = {
            "samples": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "metrics": {
                        # Only partial metrics
                        "vllm:time_to_first_token_seconds_sum": [{"value": 5.0}],
                        "vllm:time_to_first_token_seconds_count": [{"value": 10}],
                    },
                }
            ]
        }

        result = backend.parse_metrics(metrics_data)

        # Should have TTFT but zeros for missing metrics
        assert result.ttft_mean == 500.0  # 5.0 / 10 * 1000
        assert result.e2e_mean == 0.0
        assert result.tpot_mean == 0.0

    def test_parse_metrics_single_sample_no_duration(self):
        """Test with single sample (no duration calculation)."""
        backend = vLLMBackend()
        metrics_data = {
            "samples": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "metrics": {
                        "vllm:time_to_first_token_seconds_sum": [{"value": 5.0}],
                        "vllm:time_to_first_token_seconds_count": [{"value": 10}],
                        "vllm:e2e_request_latency_seconds_sum": [{"value": 50.0}],
                        "vllm:e2e_request_latency_seconds_count": [{"value": 10}],
                    },
                }
            ]
        }

        result = backend.parse_metrics(metrics_data)

        # Latencies should work
        assert result.ttft_mean == 500.0
        assert result.e2e_mean == 5000.0

        # Throughput should be 0 (no duration)
        assert result.requests_per_second == 0.0
        assert result.tokens_per_second == 0.0

    def test_parse_metrics_no_prefix_cache(self):
        """Test when prefix cache metrics are absent."""
        backend = vLLMBackend()
        metrics_data = {
            "samples": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "metrics": {
                        "vllm:time_to_first_token_seconds_sum": [{"value": 5.0}],
                        "vllm:time_to_first_token_seconds_count": [{"value": 10}],
                    },
                }
            ]
        }

        result = backend.parse_metrics(metrics_data)

        # prefix_cache_hit_rate should be None when not available
        assert result.prefix_cache_hit_rate is None
        assert result.kv_cache_usage is None

    def test_parse_metrics_invalid_data(self):
        """Test handling of completely invalid data."""
        backend = vLLMBackend()
        metrics_data = {"invalid": "data"}

        result = backend.parse_metrics(metrics_data)

        # Should return zeros without crashing
        assert result.ttft_mean == 0.0
        assert result.e2e_mean == 0.0
        assert result.tpot_mean == 0.0
        assert result.requests_per_second == 0.0
        assert result.tokens_per_second == 0.0
        assert result.memory_mb == 0.0
        assert result.cpu_percent == 0.0

    def test_parse_metrics_preserves_raw(self):
        """Test that raw_metrics preserves original data."""
        backend = vLLMBackend()
        metrics_data = {
            "samples": [
                {
                    "timestamp": "2024-01-01T10:00:00Z",
                    "metrics": {"custom": "value"},
                }
            ]
        }

        result = backend.parse_metrics(metrics_data)

        # raw_metrics should contain original data
        assert result.raw_metrics == metrics_data
