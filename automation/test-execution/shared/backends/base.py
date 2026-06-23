"""Abstract base classes for inference backend abstraction.

This module defines the interface that all inference backends must implement,
along with standard data structures for configuration and metrics.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class BackendConfig:
    """Common configuration for all inference backends.

    Attributes:
        model: HuggingFace model ID or path
        host: Server bind address
        port: Server port number
        dtype: Data type for model weights (e.g., "bfloat16", "float16")
        max_tokens: Maximum context length
        tensor_parallel: Tensor parallelism degree
        extra_args: Backend-specific additional arguments
    """

    model: str
    host: str = "0.0.0.0"
    port: int = 8000
    dtype: str = "bfloat16"
    max_tokens: int = 512
    tensor_parallel: int = 1
    extra_args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendMetrics:
    """Standardized metrics across all backends.

    All latency metrics are in milliseconds.
    All backends must provide at least the core metrics (ttft, tpot, e2e,
    requests_per_second, tokens_per_second). Additional backend-specific
    metrics can be stored in raw_metrics.
    """

    # Core latency metrics (milliseconds)
    ttft_mean: float  # Time to First Token
    tpot_mean: float  # Time Per Output Token
    e2e_mean: float  # End-to-End latency

    # Throughput metrics
    requests_per_second: float
    tokens_per_second: float

    # Resource usage
    memory_mb: float
    cpu_percent: float

    # Optional cache/KV metrics (backend-specific)
    kv_cache_usage: Optional[float] = None
    prefix_cache_hit_rate: Optional[float] = None

    # Raw backend-specific metrics
    raw_metrics: Dict[str, Any] = field(default_factory=dict)


class InferenceBackend(ABC):
    """Abstract base class for inference backends.

    All inference backends (vLLM, TGI, llama.cpp, etc.) must implement
    this interface to work with the benchmarking framework.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name (e.g., 'vllm', 'tgi', 'llamacpp').

        Returns:
            Lowercase backend identifier
        """
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Backend version string.

        Returns:
            Version (e.g., "0.20.0")
        """
        pass

    @abstractmethod
    def get_start_command(self, config: BackendConfig) -> List[str]:
        """Generate container start command arguments.

        Args:
            config: Backend configuration

        Returns:
            List of command-line arguments

        Example:
            ["--model", "meta-llama/Llama-3.2-1B", "--port", "8000"]
        """
        pass

    @abstractmethod
    def get_container_image(self) -> str:
        """Get container image URL for this backend.

        Returns:
            Container image URL (e.g., "vllm/vllm-openai-cpu:v0.20.0")
        """
        pass

    @abstractmethod
    def parse_metrics(self, metrics_data: Dict) -> BackendMetrics:
        """Parse backend-specific metrics to standardized format.

        Args:
            metrics_data: Raw metrics from backend /metrics endpoint

        Returns:
            BackendMetrics object with standardized fields

        Raises:
            ValueError: If metrics cannot be parsed
        """
        pass

    @abstractmethod
    def health_check_endpoint(self) -> str:
        """Get health check endpoint path.

        Returns:
            Health endpoint path (e.g., "/health")
        """
        pass

    @abstractmethod
    def models_endpoint(self) -> str:
        """Get models list endpoint path.

        Returns:
            Models endpoint path (e.g., "/v1/models")
        """
        pass

    def supports_feature(self, feature: str) -> bool:
        """Check if backend supports a specific feature.

        Args:
            feature: Feature name (e.g., 'prefix-caching', 'tensor-parallel')

        Returns:
            True if feature is supported

        Example features:
            - 'prefix-caching'
            - 'tensor-parallel'
            - 'quantization'
            - 'openai-api'
        """
        return False

    def get_container_env(self, config: BackendConfig) -> Dict[str, str]:
        """Get container environment variables.

        Some backends (like TGI) use environment variables instead of
        CLI arguments. Override this method for those backends.

        Args:
            config: Backend configuration

        Returns:
            Dictionary of environment variables
        """
        return {}
