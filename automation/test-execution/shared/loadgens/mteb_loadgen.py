"""
MTEB (Massive Text Embedding Benchmark) load generator implementation.

Container-only load generator for embedding quality evaluation.
Always run in containers, no host-based execution.
"""

import json
from pathlib import Path
from typing import Dict, List

from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics


class MTEBLoadGen(LoadGenerator):
    """MTEB load generator for embedding quality evaluation."""

    @property
    def name(self) -> str:
        return "mteb"

    @property
    def version(self) -> str:
        return "1.0"

    def get_command(self, config: LoadGenConfig) -> List[str]:
        """Generate MTEB command.

        MTEB is CONTAINER-ONLY and runs via Python script in container.
        """
        _ = config  # Unused - MTEB uses env vars only
        return []

    def get_container_image(self) -> str:
        return "quay.io/vllm-cpu-perf-eval/vllm-mteb:latest"

    def get_env_vars(self, config: LoadGenConfig) -> Dict[str, str]:
        """Generate MTEB environment variables."""
        env = {
            "MTEB_MODEL_NAME": config.model,
            "MTEB_VLLM_ENDPOINT": config.target_url,
            "MTEB_OUTPUT_DIR": config.output_path,
        }

        # Add task configuration
        if 'task_preset' in config.extra_args:
            env["MTEB_TASK_PRESET"] = config.extra_args['task_preset']
        elif 'tasks' in config.extra_args:
            env["MTEB_TASKS"] = config.extra_args['tasks']
        else:
            env["MTEB_TASK_PRESET"] = "quick"  # Default

        # Add language configuration
        env["MTEB_LANGUAGES"] = config.extra_args.get('languages', 'eng')

        # Add batch size if specified
        if 'batch_size' in config.extra_args:
            env["MTEB_BATCH_SIZE"] = str(config.extra_args['batch_size'])

        # Note: HF_TOKEN should be passed via environment inheritance
        # or Ansible's no_log mechanism, not through this env dict
        # which gets logged by cli.py

        return env

    def parse_results(self, results_path: str) -> LoadGenMetrics:
        """Parse MTEB results.

        MTEB produces quality metrics (accuracy, retrieval scores),
        not performance metrics. We return what we can map to standard format.

        Args:
            results_path: Path to MTEB results directory or file

        Returns:
            Standardized metrics (limited for MTEB)
        """
        results_file = Path(results_path)

        # MTEB typically outputs to a directory with multiple JSON files
        # Look for summary or results files
        if results_file.is_dir():
            # Try to find results.json or similar
            candidates = [
                'results.json', 'summary.json', 'mteb_results.json'
            ]
            for candidate in candidates:
                candidate_path = results_file / candidate
                if candidate_path.exists():
                    results_file = candidate_path
                    break

        if not results_file.exists() or not results_file.is_file():
            return LoadGenMetrics()

        try:
            with open(results_file, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return LoadGenMetrics()

        # MTEB provides quality metrics, not throughput/latency
        # We populate what makes sense
        metrics = LoadGenMetrics(raw_metrics=data)

        # MTEB doesn't have traditional load testing metrics
        # It has task scores, accuracy, etc.
        # We can't map these directly to throughput/latency

        # Store number of tasks evaluated as "requests"
        if isinstance(data, dict):
            metrics.requests_total = len(data.get('tasks', []))
            metrics.requests_successful = metrics.requests_total

        return metrics

    def validate_config(self, config: LoadGenConfig) -> None:
        """Validate MTEB configuration."""
        if not config.target_url:
            raise ValueError("target_url is required for MTEB")

        if not config.model:
            raise ValueError("model is required for MTEB")

        # Validate task preset if provided
        task_preset = config.extra_args.get('task_preset')
        valid_presets = ['quick', 'standard', 'comprehensive']
        if task_preset and task_preset not in valid_presets:
            raise ValueError(
                f"Invalid MTEB task_preset: {task_preset}. "
                f"Must be: quick, standard, or comprehensive"
            )

    def supports_workload(self, workload_type: str) -> bool:
        """MTEB only supports embedding workloads."""
        return workload_type == 'embedding'

    def get_output_format(self) -> str:
        return "json"
