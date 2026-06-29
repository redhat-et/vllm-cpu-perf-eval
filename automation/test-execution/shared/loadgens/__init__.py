"""
Load Generator Abstraction Layer

This module provides a unified interface for different load generator tools:
- GuideLLM: LLM benchmarking (generative + embedding workloads)
- MLPerf: Standard ML benchmarks (future)
- MTEB: Massive Text Embedding Benchmark (future)

Usage:
    from shared.loadgens import get_loadgen, list_loadgens

    # Get a load generator
    loadgen = get_loadgen('guidellm')

    # Generate configuration
    config = LoadGenConfig(
        target_url='http://localhost:8000',
        model='TinyLlama/TinyLlama-1.1B-Chat-v1.0',
        workload_type='chat',
        max_requests=100
    )

    # Get command and environment
    cmd = loadgen.get_command(config)
    env = loadgen.get_env_vars(config)
    image = loadgen.get_container_image()
"""

from typing import Dict, Type, List

from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics
from .guidellm_loadgen import GuideLLMLoadGen

# Registry of available load generators
LOADGENS: Dict[str, Type[LoadGenerator]] = {
    "guidellm": GuideLLMLoadGen,
    # Future: "mlperf": MLPerfLoadGen,
    # Future: "mteb": MTEBLoadGen,
}


def get_loadgen(name: str) -> LoadGenerator:
    """Get a load generator instance by name.

    Args:
        name: Load generator name ('guidellm', 'mlperf', 'mteb')

    Returns:
        Load generator instance

    Raises:
        ValueError: If load generator not found
    """
    if name not in LOADGENS:
        available = ', '.join(LOADGENS.keys())
        raise ValueError(f"Unknown load generator: {name}. Available load generators: {available}")

    return LOADGENS[name]()


def list_loadgens() -> List[str]:
    """List all available load generators.

    Returns:
        List of load generator names
    """
    return list(LOADGENS.keys())


__all__ = [
    'LoadGenerator',
    'LoadGenConfig',
    'LoadGenMetrics',
    'get_loadgen',
    'list_loadgens',
    'LOADGENS',
]
