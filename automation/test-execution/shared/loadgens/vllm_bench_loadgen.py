"""
vLLM bench serve load generator implementation.

Container-only load generator wrapping vLLM's built-in bench serve.
Always run in containers, no host-based execution.
"""

import json
from pathlib import Path
from typing import Dict, List

from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics


class VLLMBenchLoadGen(LoadGenerator):
    """vLLM bench serve load generator."""

    @property
    def name(self) -> str:
        return "vllm_bench"

    @property
    def version(self) -> str:
        return "0.25.1"  # vLLM version

    def get_command(self, config: LoadGenConfig) -> List[str]:
        """Generate vllm bench serve command.

        Returns command arguments for running vllm bench serve.
        """
        # Parse host and port from target URL
        from urllib.parse import urlparse

        parsed = urlparse(config.target_url)
        host = parsed.hostname or config.target_url.split(':')[0]

        # Use explicit port, or default based on scheme
        if parsed.port:
            port = str(parsed.port)
        elif parsed.scheme == 'https':
            port = '443'
        else:
            port = '8000'  # Default for vLLM servers

        cmd = [
            "vllm", "bench", "serve",
            "--host", host,
            "--port", port,
            "--model", config.model,
            "--dataset-name", config.dataset or "random",
            "--num-prompts", str(config.max_requests),
        ]

        # Add backend type based on workload
        if config.workload_type == 'embedding':
            cmd.extend(["--backend", "openai-embeddings"])
            cmd.extend(["--endpoint", "/v1/embeddings"])
        else:
            cmd.extend(["--backend", "openai"])

        # Add request rate if specified
        if config.rate:
            cmd.extend(["--request-rate", config.rate])

        # Add output path
        cmd.extend(["--save-result"])
        cmd.extend(["--result-filename", config.output_path])

        # Add extra args
        for key, value in config.extra_args.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])

        return cmd

    def get_container_image(self) -> str:
        return f"vllm/vllm-openai-cpu:v{self.version}"

    def get_env_vars(self, config: LoadGenConfig) -> Dict[str, str]:
        """vLLM bench uses CLI args, minimal env vars needed."""
        env = {}

        # Add HF token if in extra_args
        if 'HF_TOKEN' in config.extra_args:
            env['HF_TOKEN'] = config.extra_args['HF_TOKEN']

        return env

    def parse_results(self, results_path: str) -> LoadGenMetrics:
        """Parse vLLM bench results JSON.

        Args:
            results_path: Path to vllm bench results JSON file

        Returns:
            Standardized metrics
        """
        results_file = Path(results_path)
        if not results_file.exists():
            return LoadGenMetrics()

        try:
            with open(results_file, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return LoadGenMetrics()

        # vLLM bench output structure varies, handle both formats
        metrics = LoadGenMetrics(raw_metrics=data)

        # Extract basic counts
        metrics.requests_total = data.get(
            'total_requests', data.get('num_prompts', 0)
        )
        metrics.requests_successful = data.get(
            'successful_requests', metrics.requests_total
        )
        metrics.requests_failed = data.get('failed_requests', 0)

        # Extract throughput
        metrics.throughput_rps = data.get(
            'request_throughput', data.get('requests_per_second', 0.0)
        )
        metrics.throughput_tps = data.get(
            'token_throughput', data.get('tokens_per_second', 0.0)
        )

        # Extract latencies (vLLM bench reports in seconds, convert to ms)
        if 'latency_mean' in data:
            metrics.latency_mean_ms = data['latency_mean'] * 1000
        if 'latency_p50' in data:
            metrics.latency_p50_ms = data['latency_p50'] * 1000
        if 'latency_p95' in data:
            metrics.latency_p95_ms = data['latency_p95'] * 1000
        if 'latency_p99' in data:
            metrics.latency_p99_ms = data['latency_p99'] * 1000

        # Extract TTFT for generative workloads
        if 'ttft_mean' in data:
            metrics.ttft_mean_ms = data['ttft_mean'] * 1000

        # Extract TPOT for generative workloads
        if 'tpot_mean' in data:
            metrics.tpot_mean_ms = data['tpot_mean'] * 1000

        # Duration
        metrics.duration_seconds = data.get(
            'duration', data.get('elapsed_time', 0.0)
        )

        return metrics

    def validate_config(self, config: LoadGenConfig) -> None:
        """Validate vLLM bench configuration."""
        if not config.target_url:
            raise ValueError("target_url is required")

        if not config.model:
            raise ValueError("model is required")

        if config.max_requests <= 0:
            raise ValueError(
                f"max_requests must be positive, got: {config.max_requests}"
            )

    def supports_workload(self, workload_type: str) -> bool:
        """vLLM bench supports generative and embedding workloads."""
        supported = [
            'chat', 'rag', 'code', 'summarization', 'reasoning', 'embedding'
        ]
        return workload_type in supported

    def get_output_format(self) -> str:
        return "json"
