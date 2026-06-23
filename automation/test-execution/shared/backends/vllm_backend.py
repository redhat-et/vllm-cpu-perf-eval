"""vLLM inference backend implementation."""

from typing import List, Dict
from .base import InferenceBackend, BackendConfig, BackendMetrics


class vLLMBackend(InferenceBackend):
    """vLLM inference backend.

    vLLM is an optimized LLM inference engine with OpenAI-compatible API.
    Supports prefix caching, tensor parallelism, and various quantization methods.
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
            "--max-model-len",
            str(config.max_tokens),
        ]

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

    def get_container_image(self) -> str:
        """Get vLLM container image.

        Returns CPU-optimized vLLM image. For GPU, this should be overridden.
        """
        return f"vllm/vllm-openai-cpu:v{self.version}"

    def parse_metrics(self, metrics_data: Dict) -> BackendMetrics:
        """Parse vLLM Prometheus metrics to standard format.

        Args:
            metrics_data: Raw Prometheus metrics from /metrics endpoint

        Returns:
            BackendMetrics with standardized fields

        TODO: Implement actual metrics parsing using vllm_metrics.py
        or prometheus_client parsing logic. For now, returns placeholder.
        """
        # Placeholder implementation - will be replaced with actual parsing
        # using the existing vllm_metrics_parser.py or similar logic
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
