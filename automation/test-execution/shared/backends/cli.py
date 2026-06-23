#!/usr/bin/env python3
"""CLI tool for backend abstraction layer.

This tool allows querying backends from Ansible playbooks or shell scripts.

Usage:
    python3 -m backends.cli list
    python3 -m backends.cli get-backend vllm
    python3 -m backends.cli get-image vllm
    python3 -m backends.cli get-command vllm --model meta-llama/Llama-3.2-1B
"""

import sys
import json
import argparse
from typing import Dict, Any
from . import get_backend, list_backends
from .base import BackendConfig


def cmd_list() -> None:
    """List all available backends."""
    backends = list_backends()
    print(json.dumps(backends, indent=2))


def cmd_get_backend(name: str) -> None:
    """Get backend information as JSON."""
    backend = get_backend(name)
    info = {
        "name": backend.name,
        "version": backend.version,
        "image": backend.get_container_image(),
        "health_endpoint": backend.health_check_endpoint(),
        "models_endpoint": backend.models_endpoint(),
        "features": {
            "prefix-caching": backend.supports_feature("prefix-caching"),
            "tensor-parallel": backend.supports_feature("tensor-parallel"),
            "quantization": backend.supports_feature("quantization"),
            "openai-api": backend.supports_feature("openai-api"),
        },
    }
    print(json.dumps(info, indent=2))


def cmd_get_image(name: str) -> None:
    """Get container image for backend."""
    backend = get_backend(name)
    print(backend.get_container_image())


def cmd_get_command(
    name: str,
    model: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    dtype: str = "bfloat16",
    max_tokens: int = 512,
    tensor_parallel: int = 1,
    extra_args: str = None,
) -> None:
    """Get start command for backend."""
    backend = get_backend(name)

    # Parse extra_args if provided
    extra = {}
    if extra_args:
        try:
            extra = json.loads(extra_args)
        except json.JSONDecodeError:
            print(f"Error: extra_args must be valid JSON", file=sys.stderr)
            sys.exit(1)

    config = BackendConfig(
        model=model,
        host=host,
        port=port,
        dtype=dtype,
        max_tokens=max_tokens,
        tensor_parallel=tensor_parallel,
        extra_args=extra,
    )

    cmd = backend.get_start_command(config)
    env = backend.get_container_env(config)

    result = {
        "command": cmd,
        "env": env,
        "image": backend.get_container_image(),
    }
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Backend abstraction layer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list command
    subparsers.add_parser("list", help="List all available backends")

    # get-backend command
    parser_backend = subparsers.add_parser(
        "get-backend", help="Get backend information"
    )
    parser_backend.add_argument("name", help="Backend name")

    # get-image command
    parser_image = subparsers.add_parser(
        "get-image", help="Get container image URL"
    )
    parser_image.add_argument("name", help="Backend name")

    # get-command command
    parser_cmd = subparsers.add_parser(
        "get-command", help="Get start command for backend"
    )
    parser_cmd.add_argument("name", help="Backend name")
    parser_cmd.add_argument("--model", required=True, help="Model name/path")
    parser_cmd.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser_cmd.add_argument("--port", type=int, default=8000, help="Port")
    parser_cmd.add_argument("--dtype", default="bfloat16", help="Data type")
    parser_cmd.add_argument(
        "--max-tokens", type=int, default=512, help="Max context length"
    )
    parser_cmd.add_argument(
        "--tensor-parallel", type=int, default=1, help="Tensor parallelism"
    )
    parser_cmd.add_argument(
        "--extra-args", help="Extra args as JSON dict (e.g., '{\"enable-prefix-caching\": true}')"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "list":
            cmd_list()
        elif args.command == "get-backend":
            cmd_get_backend(args.name)
        elif args.command == "get-image":
            cmd_get_image(args.name)
        elif args.command == "get-command":
            cmd_get_command(
                args.name,
                args.model,
                args.host,
                args.port,
                args.dtype,
                args.max_tokens,
                args.tensor_parallel,
                args.extra_args,
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
