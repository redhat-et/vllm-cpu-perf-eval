"""
Base classes for load generator abstraction.

This module provides abstract interfaces for different load generator tools
(GuideLLM, MLPerf, MTEB) allowing standardized configuration and execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class LoadGenConfig:
    """Configuration for load generator execution.

    Attributes:
        target_url: URL of the inference endpoint to test (online mode)
        model: Model name/identifier
        workload_type: Type of workload (chat, rag, code, embedding, etc.)
        mode: Execution mode - "online" (server + load generator) or
            "offline_batch" (direct API, no server). Defaults to "online".
        max_requests: Maximum number of requests to send
        max_seconds: Maximum duration in seconds
        rate: Request rate (requests/second) or 'inf' for max throughput
        output_path: Path to save results
        dataset: Dataset name or path (optional)
        model_path: Local model path for offline batch mode (optional)
        num_cores: CPU cores for offline batch mode (optional)
        extra_args: Additional load generator specific arguments
    """
    target_url: str = ""
    model: str = ""
    workload_type: str = "chat"
    mode: str = "online"
    max_requests: int = 1000
    max_seconds: int = 600
    rate: Optional[str] = None
    output_path: str = "/results"
    dataset: Optional[str] = None
    model_path: Optional[str] = None
    num_cores: Optional[int] = None
    extra_args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadGenMetrics:
    """Standardized metrics from load generator results.

    Attributes:
        requests_total: Total requests sent
        requests_successful: Successful requests
        requests_failed: Failed requests
        throughput_rps: Requests per second
        throughput_tps: Tokens per second (if applicable)
        latency_mean_ms: Mean latency in milliseconds
        latency_p50_ms: P50 latency
        latency_p95_ms: P95 latency
        latency_p99_ms: P99 latency
        ttft_mean_ms: Time to first token mean (LLM workloads)
        tpot_mean_ms: Time per output token mean (LLM workloads)
        duration_seconds: Total test duration
        prefill_throughput_tps: Prefill phase tokens/sec (offline batch)
        decode_throughput_tps: Decode phase tokens/sec (offline batch)
        output_throughput_tps: Output tokens/sec (offline batch)
        kv_cache_usage_pct: Peak KV cache usage percent (offline batch)
        raw_metrics: Raw metrics dict from load generator
    """
    requests_total: int = 0
    requests_successful: int = 0
    requests_failed: int = 0
    throughput_rps: float = 0.0
    throughput_tps: float = 0.0
    latency_mean_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    ttft_mean_ms: Optional[float] = None
    tpot_mean_ms: Optional[float] = None
    duration_seconds: float = 0.0
    prefill_throughput_tps: Optional[float] = None
    decode_throughput_tps: Optional[float] = None
    output_throughput_tps: Optional[float] = None
    kv_cache_usage_pct: Optional[float] = None
    raw_metrics: Dict[str, Any] = field(default_factory=dict)


class LoadGenerator(ABC):
    """Abstract base class for load generators.

    Each load generator tool (GuideLLM, MLPerf, MTEB) implements this interface
    to provide standardized configuration and execution.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the load generator name (e.g., 'guidellm', 'mlperf', 'mteb')."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the load generator version."""
        pass

    @abstractmethod
    def get_command(self, config: LoadGenConfig) -> List[str]:
        """Generate the command to run the load generator.

        Args:
            config: Load generator configuration

        Returns:
            List of command arguments (e.g., ['guidellm', '--target', 'http://...'])
        """
        pass

    @abstractmethod
    def get_container_image(self) -> str:
        """Return the container image URL for this load generator.

        Returns:
            Container image URL (e.g., 'ghcr.io/vllm-project/guidellm:v0.7.1')
        """
        pass

    @abstractmethod
    def get_env_vars(self, config: LoadGenConfig) -> Dict[str, str]:
        """Generate environment variables for the load generator.

        Args:
            config: Load generator configuration

        Returns:
            Dictionary of environment variables
        """
        pass

    @abstractmethod
    def parse_results(self, results_path: str) -> LoadGenMetrics:
        """Parse load generator results into standardized metrics.

        Args:
            results_path: Path to results file(s)

        Returns:
            Standardized metrics object
        """
        pass

    @abstractmethod
    def validate_config(self, config: LoadGenConfig) -> None:
        """Validate configuration for this load generator.

        Args:
            config: Load generator configuration

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    def supports_workload(self, workload_type: str) -> bool:
        """Check if this load generator supports a given workload type.

        Args:
            workload_type: Workload type (chat, rag, embedding, etc.)

        Returns:
            True if workload is supported
        """
        pass

    def supports_mode(self, mode: str) -> bool:
        """Check if this load generator supports a given execution mode.

        Args:
            mode: Execution mode ("online" or "offline_batch")

        Returns:
            True if mode is supported. Default: online only.
        """
        return mode == "online"

    def get_output_format(self) -> str:
        """Return the output format (json, csv, etc.).

        Returns:
            Output format string
        """
        return "json"
