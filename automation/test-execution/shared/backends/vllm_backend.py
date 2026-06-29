"""vLLM inference backend implementation."""

from typing import List, Dict, Optional
from .base import InferenceBackend, BackendConfig, BackendMetrics


class vLLMBackend(InferenceBackend):
    """vLLM inference backend.

    vLLM is an optimized LLM inference engine with OpenAI-compatible
    API. Supports prefix caching, tensor parallelism, and various
    quantization methods.
    """

    @property
    def name(self) -> str:
        return "vllm"

    @property
    def version(self) -> str:
        # TODO: Make this configurable or detect from container image
        return "0.20.0"

    def get_start_command(self, config: BackendConfig) -> List[str]:
        """Generate vLLM CLI arguments.

        Returns command-line arguments for the vLLM OpenAI-compatible server.
        """
        cmd = [
            "--model",
            config.model,
            "--host",
            config.host,
            "--port",
            str(config.port),
            "--dtype",
            config.dtype,
        ]

        # Add max-model-len only if explicitly set
        if config.max_tokens:
            cmd.extend(["--max-model-len", str(config.max_tokens)])

        # Add tensor parallelism if > 1
        if config.tensor_parallel > 1:
            cmd.extend(["--tensor-parallel-size", str(config.tensor_parallel)])

        # Add backend-specific extra arguments
        if config.extra_args:
            for key, value in config.extra_args.items():
                # Handle boolean flags
                if isinstance(value, bool):
                    if value:
                        cmd.append(f"--{key}")
                else:
                    cmd.extend([f"--{key}", str(value)])

        return cmd

    def get_container_image(
        self, config: Optional[BackendConfig] = None
    ) -> str:
        """Get vLLM container image.

        Args:
            config: Optional configuration to check for custom image override

        Returns:
            Custom image if config.container_image is set,
            otherwise default CPU-optimized vLLM image
        """
        if config and config.container_image:
            return config.container_image
        return f"vllm/vllm-openai-cpu:v{self.version}"

    def parse_metrics(self, metrics_data: Dict) -> BackendMetrics:
        """Parse vLLM Prometheus metrics to standard format.

        Args:
            metrics_data: Dict with 'samples' key containing vLLM metrics JSON

        Returns:
            BackendMetrics with standardized fields

        Expected input format (from vllm-metrics.json):
        {
            "samples": [
                {
                    "timestamp": "...",
                    "metrics": {
                        "vllm:ttft_ms": [...],
                        "vllm:kv_cache_usage_perc": [...],
                        ...
                    }
                }
            ]
        }
        """
        try:
            samples = metrics_data.get('samples', [])
            if not samples:
                raise ValueError("No samples found in metrics_data")

            # Get first and last samples for computing counter deltas
            first_sample = samples[0]
            last_sample = samples[-1]
            first_metrics = first_sample.get('metrics', {})
            last_metrics = last_sample.get('metrics', {})

            # Helper to extract single value from metric list
            def get_value(metric_list):
                if metric_list and len(metric_list) > 0:
                    return metric_list[0].get('value', 0)
                return 0

            # Helper to compute delta between first and last samples
            # For single-sample case, use the value directly (no prior state)
            def get_counter_delta(metric_name):
                if len(samples) == 1:
                    return get_value(last_metrics.get(metric_name, []))
                first_val = get_value(first_metrics.get(metric_name, []))
                last_val = get_value(last_metrics.get(metric_name, []))
                return last_val - first_val

            # Extract latencies from histograms (sum / count)
            # Use deltas for cumulative histogram counters
            ttft_sum = get_counter_delta(
                'vllm:time_to_first_token_seconds_sum'
            )
            ttft_count = get_counter_delta(
                'vllm:time_to_first_token_seconds_count'
            )
            ttft_mean_ms = (
                (ttft_sum / ttft_count * 1000) if ttft_count > 0 else 0.0
            )

            e2e_sum = get_counter_delta(
                'vllm:e2e_request_latency_seconds_sum'
            )
            e2e_count = get_counter_delta(
                'vllm:e2e_request_latency_seconds_count'
            )
            e2e_mean_ms = (
                (e2e_sum / e2e_count * 1000) if e2e_count > 0 else 0.0
            )

            # Calculate TPOT from decode time
            decode_sum = get_counter_delta(
                'vllm:request_decode_time_seconds_sum'
            )
            gen_tokens_sum = get_counter_delta(
                'vllm:request_generation_tokens_sum'
            )

            # TPOT = total_decode_time / total_output_tokens (ms per token)
            tpot_mean_ms = 0.0
            if gen_tokens_sum > 0:
                tpot_mean_ms = (decode_sum / gen_tokens_sum * 1000)

            # Throughput: requests per second and tokens per second
            # Get test duration from first to last sample timestamp
            if len(samples) > 1:
                import datetime
                first_ts = datetime.datetime.fromisoformat(
                    samples[0]['timestamp']
                )
                last_ts = datetime.datetime.fromisoformat(
                    last_sample['timestamp']
                )
                duration_sec = (last_ts - first_ts).total_seconds()
            else:
                duration_sec = 0

            requests_per_second = (
                e2e_count / duration_sec if duration_sec > 0 else 0.0
            )

            # Use deltas for cumulative token counters
            prompt_tokens = get_counter_delta('vllm:prompt_tokens_total')
            generation_tokens = get_counter_delta(
                'vllm:generation_tokens_total'
            )
            total_tokens = prompt_tokens + generation_tokens
            tokens_per_second = (
                total_tokens / duration_sec if duration_sec > 0 else 0.0
            )

            # Memory (gauge, not counter - use last value)
            memory_bytes = get_value(
                last_metrics.get('process_resident_memory_bytes', [])
            )
            memory_mb = (
                memory_bytes / (1024 * 1024) if memory_bytes > 0 else 0.0
            )

            # CPU is cumulative counter - compute delta
            cpu_seconds_delta = get_counter_delta(
                'process_cpu_seconds_total'
            )
            cpu_percent = (
                (cpu_seconds_delta / duration_sec * 100)
                if duration_sec > 0 else 0.0
            )

            # Optional vLLM-specific metrics (gauges - use last value)
            kv_cache_usage = get_value(
                last_metrics.get('vllm:kv_cache_usage_perc', [])
            )

            # Prefix cache metrics are counters - use deltas
            prefix_hits = get_counter_delta(
                'vllm:prefix_cache_hits_total'
            )
            prefix_queries = get_counter_delta(
                'vllm:prefix_cache_queries_total'
            )
            prefix_cache_hit_rate = (
                (prefix_hits / prefix_queries * 100)
                if prefix_queries > 0 else None
            )

            return BackendMetrics(
                ttft_mean=ttft_mean_ms,
                tpot_mean=tpot_mean_ms,
                e2e_mean=e2e_mean_ms,
                requests_per_second=requests_per_second,
                tokens_per_second=tokens_per_second,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                kv_cache_usage=kv_cache_usage if kv_cache_usage > 0 else None,
                prefix_cache_hit_rate=prefix_cache_hit_rate,
                raw_metrics=metrics_data,
            )

        except Exception as e:
            # Return empty metrics on parse failure
            print(f"Warning: Failed to parse vLLM metrics: {e}")
            return BackendMetrics(
                ttft_mean=0.0,
                tpot_mean=0.0,
                e2e_mean=0.0,
                requests_per_second=0.0,
                tokens_per_second=0.0,
                memory_mb=0.0,
                cpu_percent=0.0,
                raw_metrics=metrics_data,
            )

    def health_check_endpoint(self) -> str:
        """vLLM health check endpoint."""
        return "/health"

    def models_endpoint(self) -> str:
        """vLLM models endpoint."""
        return "/v1/models"

    def supports_feature(self, feature: str) -> bool:
        """Check vLLM feature support."""
        features = {
            "prefix-caching": True,
            "tensor-parallel": True,
            "quantization": True,
            "openai-api": True,
            "continuous-batching": True,
            "paged-attention": True,
        }
        return features.get(feature, False)
