"""Backend abstraction layer for inference engines.

This module provides a pluggable backend system that allows the benchmarking
framework to work with multiple inference engines (vLLM, TGI, llama.cpp, etc.)
while maintaining a consistent interface.

Usage:
    from shared.backends import get_backend, list_backends

    # Get a backend instance
    backend = get_backend("vllm")

    # Generate container start command
    config = BackendConfig(model="meta-llama/Llama-3.2-1B")
    cmd = backend.get_start_command(config)
"""

from typing import Dict, Type
from .base import InferenceBackend, BackendConfig, BackendMetrics
from .vllm_backend import vLLMBackend

# Backend registry
BACKENDS: Dict[str, Type[InferenceBackend]] = {
    "vllm": vLLMBackend,
    # Future backends:
    # "tgi": TGIBackend,
    # "llamacpp": LlamaCppBackend,
    # "tensorrt-llm": TensorRTLLMBackend,
}


def get_backend(name: str) -> InferenceBackend:
    """Get backend instance by name.

    Args:
        name: Backend name (e.g., "vllm", "tgi")

    Returns:
        Backend instance

    Raises:
        ValueError: If backend name is unknown
    """
    if name not in BACKENDS:
        available = ", ".join(BACKENDS.keys())
        raise ValueError(
            f"Unknown backend: {name}. Available backends: {available}"
        )
    return BACKENDS[name]()


def list_backends() -> list:
    """List all registered backend names.

    Returns:
        List of backend names
    """
    return list(BACKENDS.keys())


__all__ = [
    "InferenceBackend",
    "BackendConfig",
    "BackendMetrics",
    "get_backend",
    "list_backends",
    "vLLMBackend",
]
