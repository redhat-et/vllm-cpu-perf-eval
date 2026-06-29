"""
GuideLLM load generator implementation.

Wraps the GuideLLM benchmarking tool for LLM workloads.
"""

import json
from pathlib import Path
from typing import Dict, List

from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics


class GuideLLMLoadGen(LoadGenerator):
    """GuideLLM load generator for LLM benchmarking."""

    @property
    def name(self) -> str:
        return "guidellm"

    @property
    def version(self) -> str:
        return "0.6.0"

    def get_command(self, config: LoadGenConfig) -> List[str]:
        """Generate GuideLLM command.

        GuideLLM uses environment variables for configuration,
        so the command is minimal.
        """
        # GuideLLM is typically run via environment variables
        # The actual command depends on the profile/mode
        cmd = []

        # Add common args that might not be in env vars
        if config.extra_args.get('profile'):
            # Profile-based execution handled via env vars
            pass

        return cmd

    def get_container_image(self) -> str:
        return f"ghcr.io/vllm-project/guidellm:v{self.version}"

    def get_env_vars(self, config: LoadGenConfig) -> Dict[str, str]:
        """Generate GuideLLM environment variables.

        GuideLLM uses environment variables for configuration.
        """
        env = {
            "GUIDELLM_TARGET": config.target_url,
            "GUIDELLM_MODEL": config.model,
            "GUIDELLM_MAX_REQUESTS": str(config.max_requests),
            "GUIDELLM_MAX_SECONDS": str(config.max_seconds),
            "GUIDELLM_OUTPUT_PATH": config.output_path,
        }

        # Add rate if specified
        if config.rate:
            env["GUIDELLM_RATE"] = config.rate

        # Add profile if specified
        profile = config.extra_args.get('profile', 'sweep')
        env["GUIDELLM_PROFILE"] = profile

        # Add dataset if specified
        if config.dataset:
            env["GUIDELLM_DATASET"] = config.dataset

        # Add workload-specific parameters
        if config.workload_type in ['chat', 'rag', 'code']:
            # These are generative workloads
            env["GUIDELLM_WORKLOAD_TYPE"] = "generative"
        elif config.workload_type == 'embedding':
            env["GUIDELLM_BACKEND"] = "openai-embeddings"
            env["GUIDELLM_ENDPOINT"] = "/v1/embeddings"

        # Add any extra environment variables
        for key, value in config.extra_args.items():
            if key.startswith('GUIDELLM_'):
                env[key] = str(value)

        return env

    def parse_results(self, results_path: str) -> LoadGenMetrics:
        """Parse GuideLLM results JSON into standardized metrics.

        Args:
            results_path: Path to benchmarks.json file

        Returns:
            Standardized metrics
        """
        results_file = Path(results_path)
        if not results_file.exists():
            # Return empty metrics if file doesn't exist
            return LoadGenMetrics()

        try:
            with open(results_file, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return LoadGenMetrics()

        # GuideLLM benchmarks.json structure:
        # {
        #   "request_latency": {"mean": X, "p50": Y, "p95": Z, "p99": W},
        #   "throughput": {"requests_per_second": R, "tokens_per_second": T},
        #   "time_to_first_token": {"mean": TTFT},
        #   "inter_token_latency": {"mean": TPOT},
        #   ...
        # }

        metrics = LoadGenMetrics(raw_metrics=data)

        # Extract request counts
        metrics.requests_total = data.get('total_requests', 0)
        metrics.requests_successful = data.get('successful_requests', 0)
        metrics.requests_failed = data.get('failed_requests', 0)

        # Extract throughput
        throughput = data.get('throughput', {})
        metrics.throughput_rps = throughput.get('requests_per_second', 0.0)
        metrics.throughput_tps = throughput.get('tokens_per_second', 0.0)

        # Extract latencies (convert to milliseconds if needed)
        latency = data.get('request_latency', {})
        metrics.latency_mean_ms = latency.get('mean', 0.0) * 1000  # Assume seconds
        metrics.latency_p50_ms = latency.get('p50', 0.0) * 1000
        metrics.latency_p95_ms = latency.get('p95', 0.0) * 1000
        metrics.latency_p99_ms = latency.get('p99', 0.0) * 1000

        # Extract TTFT and TPOT for generative workloads
        ttft = data.get('time_to_first_token', {})
        if ttft:
            metrics.ttft_mean_ms = ttft.get('mean', 0.0) * 1000

        tpot = data.get('inter_token_latency', {})
        if tpot:
            metrics.tpot_mean_ms = tpot.get('mean', 0.0) * 1000

        # Extract duration
        metrics.duration_seconds = data.get('duration_seconds', 0.0)

        return metrics

    def validate_config(self, config: LoadGenConfig) -> None:
        """Validate GuideLLM configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if not config.target_url:
            raise ValueError("target_url is required")

        if not config.target_url.startswith('http'):
            raise ValueError(f"target_url must start with http:// or https://, got: {config.target_url}")

        if not config.model:
            raise ValueError("model is required")

        if config.max_requests <= 0:
            raise ValueError(f"max_requests must be positive, got: {config.max_requests}")

        if config.max_seconds <= 0:
            raise ValueError(f"max_seconds must be positive, got: {config.max_seconds}")

        # Validate profile if specified
        profile = config.extra_args.get('profile')
        if profile and profile not in ['sweep', 'synchronous', 'concurrent', 'throughput']:
            raise ValueError(f"Invalid profile: {profile}. Must be one of: sweep, synchronous, concurrent, throughput")

    def supports_workload(self, workload_type: str) -> bool:
        """GuideLLM supports generative and embedding workloads."""
        supported = ['chat', 'rag', 'code', 'summarization', 'reasoning', 'embedding']
        return workload_type in supported

    def get_output_format(self) -> str:
        return "json"
