"""
GuideLLM load generator implementation.

Container-only load generator for LLM benchmarking.
Supports both v0.6.x (env-var-based) and v0.7.x (CLI-arg-based) interfaces.
"""

import json
from pathlib import Path
from typing import Dict, List

from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics


def _parse_version(ver: str) -> tuple:
    """Parse a version string like '0.7.2' into a comparable tuple."""
    return tuple(int(x) for x in ver.split('.'))


class GuideLLMLoadGen(LoadGenerator):
    """GuideLLM load generator for LLM benchmarking."""

    @property
    def name(self) -> str:
        return "guidellm"

    @property
    def version(self) -> str:
        return "0.7.2"

    @property
    def _is_v7_or_later(self) -> bool:
        return _parse_version(self.version) >= (0, 7, 0)

    def get_command(self, config: LoadGenConfig) -> List[str]:
        """Generate GuideLLM command.

        v0.7+: returns CLI args for ``guidellm run``.
        v0.6.x: returns empty list (env vars only).
        """
        if not self._is_v7_or_later:
            return []

        cmd = ["run"]

        backend = f"kind=openai_http,target={config.target_url}"
        api_key = config.extra_args.get('api_key', '')
        if api_key:
            backend += f",api_key={api_key}"
        cmd.extend(["--backend", backend])

        isl = config.extra_args.get('isl', 512)
        osl = config.extra_args.get('osl', 512)
        data_parts = [
            f"kind=synthetic_text"
            f",prompt_tokens={isl}"
            f",output_tokens={osl}"
        ]
        if config.extra_args.get('variability'):
            var_fields = [
                'prompt_tokens_stdev',
                'prompt_tokens_min',
                'prompt_tokens_max',
                'output_tokens_stdev',
                'output_tokens_min',
                'output_tokens_max',
            ]
            for field in var_fields:
                if field in config.extra_args:
                    val = config.extra_args[field]
                    data_parts.append(f"{field}={val}")
        cmd.extend(["--data", ",".join(data_parts)])

        tokenizer = (
            f"kind=huggingface_auto,model={config.model}"
        )
        cmd.extend(["--tokenizer", tokenizer])

        profile = config.extra_args.get('profile', 'sweep')
        warmup = config.extra_args.get('warmup', '0.1')
        cooldown = config.extra_args.get('cooldown', '30')
        profile_parts = [
            f"kind={profile}",
            f"warmup={warmup}",
            f"cooldown={cooldown}",
        ]

        rates = config.rate.split(',') if config.rate else []

        if profile == 'concurrent' and rates:
            profile_parts.append(f"streams={rates[0]}")
            cmd.extend(["--profile", ",".join(profile_parts)])
            if len(rates) > 1:
                cmd.extend([
                    "--override", "profile.streams",
                    ",".join(rates),
                ])
        elif profile in ('constant', 'poisson') and rates:
            profile_parts.append(f"rate={rates[0]}")
            cmd.extend(["--profile", ",".join(profile_parts)])
            if len(rates) > 1:
                cmd.extend([
                    "--override", "profile.rate",
                    ",".join(rates),
                ])
        else:
            cmd.extend(["--profile", ",".join(profile_parts)])

        if config.max_seconds > 0:
            cmd.extend([
                "--constraint",
                f"kind=max_duration,seconds={config.max_seconds}",
            ])
        if config.max_requests > 0:
            cmd.extend([
                "--constraint",
                f"kind=max_requests,count={config.max_requests}",
            ])

        output_path = config.output_path.rstrip('/')
        cmd.extend([
            "--output",
            f"kind=json,path={output_path}/benchmarks.json",
        ])

        return cmd

    def get_container_image(self) -> str:
        return f"ghcr.io/vllm-project/guidellm:v{self.version}"

    def get_env_vars(self, config: LoadGenConfig) -> Dict[str, str]:
        """Generate GuideLLM environment variables.

        For v0.7+: returns minimal env (HF_TOKEN only, config is via CLI args).
        For v0.6.x: returns full env var configuration.
        """
        if self._is_v7_or_later:
            env = {}
            if config.extra_args.get('HF_TOKEN'):
                env["HF_TOKEN"] = config.extra_args['HF_TOKEN']
            return env

        env = {
            "GUIDELLM_TARGET": config.target_url,
            "GUIDELLM_MODEL": config.model,
            "GUIDELLM_MAX_REQUESTS": str(config.max_requests),
            "GUIDELLM_MAX_SECONDS": str(config.max_seconds),
            "GUIDELLM_OUTPUT_PATH": config.output_path,
        }

        if config.rate:
            env["GUIDELLM_RATE"] = config.rate

        profile = config.extra_args.get('profile', 'sweep')
        env["GUIDELLM_PROFILE"] = profile

        if config.dataset:
            env["GUIDELLM_DATASET"] = config.dataset

        if config.workload_type in ['chat', 'rag', 'code']:
            env["GUIDELLM_WORKLOAD_TYPE"] = "generative"
        elif config.workload_type == 'embedding':
            env["GUIDELLM_BACKEND"] = "openai-embeddings"
            env["GUIDELLM_ENDPOINT"] = "/v1/embeddings"

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
        mean = latency.get('mean', 0.0)
        metrics.latency_mean_ms = mean * 1000
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
        if config.mode == "offline_batch":
            raise ValueError(
                "GuideLLM does not yet support offline_batch mode. "
                "Use vllm bench throughput directly."
            )

        if not config.target_url:
            raise ValueError("target_url is required for online mode")

        if not config.target_url.startswith('http'):
            raise ValueError(
                "target_url must start with http:// or https://"
                f", got: {config.target_url}"
            )

        if not config.model:
            raise ValueError("model is required")

        if config.max_requests <= 0:
            raise ValueError(
                "max_requests must be positive"
                f", got: {config.max_requests}"
            )

        if config.max_seconds <= 0:
            raise ValueError(
                "max_seconds must be positive"
                f", got: {config.max_seconds}"
            )

        profile = config.extra_args.get('profile')
        if profile:
            valid_profiles = [
                'sweep', 'synchronous',
                'concurrent', 'throughput',
            ]
            if self._is_v7_or_later:
                valid_profiles.extend(['constant', 'poisson'])
            if profile not in valid_profiles:
                opts = ', '.join(valid_profiles)
                raise ValueError(
                    f"Invalid profile: {profile}."
                    f" Must be one of: {opts}"
                )

    def supports_workload(self, workload_type: str) -> bool:
        """GuideLLM supports generative and embedding workloads."""
        supported = [
            'chat', 'chat_lite', 'rag', 'code',
            'summarization', 'reasoning', 'embedding',
        ]
        return workload_type in supported

    def get_output_format(self) -> str:
        return "json"
