"""
CLI interface for load generator abstraction.

Provides command-line access to load generator functionality for Ansible integration.

Usage:
    # List available load generators
    python3 -m shared.loadgens list

    # Get load generator info
    python3 -m shared.loadgens get-loadgen guidellm

    # Generate configuration
    python3 -m shared.loadgens get-config guidellm \\
        --target http://localhost:8000 \\
        --model "TinyLlama/TinyLlama-1.1B" \\
        --workload chat \\
        --max-requests 100

    # Parse results
    python3 -m shared.loadgens parse-results guidellm /path/to/results.json
"""

import argparse
import json
import sys
from typing import Any, Dict

from . import get_loadgen, list_loadgens, LoadGenConfig


def cmd_list(_args: argparse.Namespace) -> None:
    """List available load generators."""
    loadgens = list_loadgens()
    print(json.dumps(loadgens, indent=2))


def cmd_get_loadgen(args: argparse.Namespace) -> None:
    """Get load generator information."""
    loadgen = get_loadgen(args.name)

    info = {
        "name": loadgen.name,
        "version": loadgen.version,
        "image": loadgen.get_container_image(),
        "output_format": loadgen.get_output_format(),
        "supported_workloads": {
            "chat": loadgen.supports_workload("chat"),
            "rag": loadgen.supports_workload("rag"),
            "code": loadgen.supports_workload("code"),
            "summarization": loadgen.supports_workload("summarization"),
            "embedding": loadgen.supports_workload("embedding"),
        }
    }

    print(json.dumps(info, indent=2))


def cmd_get_config(args: argparse.Namespace) -> None:
    """Generate load generator configuration."""
    loadgen = get_loadgen(args.name)

    # Build extra args from JSON if provided
    extra_args = {}
    if args.extra_args:
        extra_args = json.loads(args.extra_args)

    # Create configuration
    config = LoadGenConfig(
        target_url=args.target,
        model=args.model,
        workload_type=args.workload,
        max_requests=args.max_requests,
        max_seconds=args.max_seconds,
        rate=args.rate,
        output_path=args.output_path,
        dataset=args.dataset,
        extra_args=extra_args
    )

    # Validate configuration
    try:
        loadgen.validate_config(config)
    except ValueError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    # Generate command and environment
    command = loadgen.get_command(config)
    env = loadgen.get_env_vars(config)
    image = loadgen.get_container_image()

    result = {
        "command": command,
        "env": env,
        "image": image,
        "output_format": loadgen.get_output_format()
    }

    print(json.dumps(result, indent=2))


def cmd_parse_results(args: argparse.Namespace) -> None:
    """Parse load generator results."""
    loadgen = get_loadgen(args.name)

    metrics = loadgen.parse_results(args.results_path)

    # Convert dataclass to dict
    result = {
        "requests_total": metrics.requests_total,
        "requests_successful": metrics.requests_successful,
        "requests_failed": metrics.requests_failed,
        "throughput_rps": metrics.throughput_rps,
        "throughput_tps": metrics.throughput_tps,
        "latency_mean_ms": metrics.latency_mean_ms,
        "latency_p50_ms": metrics.latency_p50_ms,
        "latency_p95_ms": metrics.latency_p95_ms,
        "latency_p99_ms": metrics.latency_p99_ms,
        "ttft_mean_ms": metrics.ttft_mean_ms,
        "tpot_mean_ms": metrics.tpot_mean_ms,
        "duration_seconds": metrics.duration_seconds,
    }

    print(json.dumps(result, indent=2))


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load Generator Abstraction CLI"
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # list command
    subparsers.add_parser('list', help='List available load generators')

    # get-loadgen command
    parser_info = subparsers.add_parser('get-loadgen', help='Get load generator information')
    parser_info.add_argument('name', help='Load generator name')

    # get-config command
    parser_config = subparsers.add_parser('get-config', help='Generate load generator configuration')
    parser_config.add_argument('name', help='Load generator name')
    parser_config.add_argument('--target', required=True, help='Target URL')
    parser_config.add_argument('--model', required=True, help='Model name')
    parser_config.add_argument('--workload', default='chat', help='Workload type')
    parser_config.add_argument('--max-requests', type=int, default=1000, help='Maximum requests')
    parser_config.add_argument('--max-seconds', type=int, default=600, help='Maximum seconds')
    parser_config.add_argument('--rate', help='Request rate (optional)')
    parser_config.add_argument('--output-path', default='/results', help='Output path')
    parser_config.add_argument('--dataset', help='Dataset name/path (optional)')
    parser_config.add_argument('--extra-args', help='Extra arguments as JSON')

    # parse-results command
    parser_parse = subparsers.add_parser('parse-results', help='Parse load generator results')
    parser_parse.add_argument('name', help='Load generator name')
    parser_parse.add_argument('results_path', help='Path to results file')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch commands
    commands = {
        'list': cmd_list,
        'get-loadgen': cmd_get_loadgen,
        'get-config': cmd_get_config,
        'parse-results': cmd_parse_results,
    }

    commands[args.command](args)


if __name__ == '__main__':
    main()
