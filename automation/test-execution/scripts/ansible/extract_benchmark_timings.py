#!/usr/bin/env python3
"""Extract per-benchmark timings from benchmarks.json and add to test-metadata.json

This script processes GuideLLM benchmark results and extracts detailed timing information
for each benchmark run, including duration, requests processed, and temporal metadata.
The extracted data is appended to the test-metadata.json file for later analysis.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add shared library to path
_script_dir = Path(__file__).parent
_shared_dir = _script_dir.parent.parent / "shared"
sys.path.insert(0, str(_shared_dir))

from io_utils import load_json_file, save_json_file, format_duration  # noqa: E402


def extract_timings(bench_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float]:
    """Extract timing information from benchmarks data.

    Args:
        bench_data: Dictionary containing benchmark results from benchmarks.json

    Returns:
        Tuple of (benchmark_timings list, total_duration in seconds)
    """
    rates = bench_data.get('args', {}).get('rate', [])
    benchmark_timings = []
    total_duration = 0.0

    for i, benchmark in enumerate(bench_data.get('benchmarks', [])):
        duration = benchmark['duration']
        total_duration += duration

        timing = {
            'benchmark_index': i,
            'rate': rates[i] if i < len(rates) else None,
            'duration_seconds': duration,
            'warmup_duration_seconds': benchmark['warmup_duration'],
            'cooldown_duration_seconds': benchmark['cooldown_duration'],
            'start_time': benchmark['start_time'],
            'end_time': benchmark['end_time'],
            'successful_requests': benchmark['scheduler_state']['successful_requests'],
            'total_requests': benchmark['scheduler_state']['processed_requests']
        }
        benchmark_timings.append(timing)

    return benchmark_timings, total_duration


def main() -> int:
    """Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if len(sys.argv) != 3:
        print("Usage: extract_benchmark_timings.py <benchmarks.json> <test-metadata.json>",
              file=sys.stderr)
        return 1

    benchmarks_file = Path(sys.argv[1])
    metadata_file = Path(sys.argv[2])

    try:
        # Load benchmark and metadata files
        bench_data = load_json_file(benchmarks_file)
        metadata = load_json_file(metadata_file)

        # Extract timing information
        benchmark_timings, total_duration = extract_timings(bench_data)
        test_duration_string = format_duration(total_duration)

        # Update metadata with timing information
        metadata['benchmark_timings'] = benchmark_timings
        metadata['test_duration_seconds'] = int(total_duration)
        metadata['test_duration'] = test_duration_string

        # IETF sample count aggregates for statistical validity assessment
        successful_counts = [
            t['successful_requests'] for t in benchmark_timings
        ]
        metadata['total_successful_requests'] = (
            sum(successful_counts) if successful_counts else 0
        )
        min_reqs = min(successful_counts) if successful_counts else 0
        metadata['min_requests_per_benchmark'] = min_reqs

        if min_reqs < 1000:
            metadata['ietf_sample_warning'] = (
                f"Minimum requests per benchmark ({min_reqs}) is below 1000; "
                f"P99 may not be statistically reliable per IETF guidelines"
            )
        elif min_reqs < 10000:
            metadata['ietf_sample_warning'] = (
                f"Minimum requests per benchmark ({min_reqs}) is below 10000; "
                f"P99.9 may not be statistically reliable per IETF guidelines"
            )

        # Save updated metadata
        save_json_file(metadata_file, metadata)

        # Report success
        print(f"✓ Added {len(benchmark_timings)} benchmark timing(s) to metadata")
        print(f"✓ Total test duration: {test_duration_string} ({int(total_duration)}s)")
        return 0

    except FileNotFoundError as e:
        print(f"Warning: File not found: {e.filename}", file=sys.stderr)
        return 0  # Don't fail the playbook - this is a non-critical enhancement

    except KeyError as e:
        print(f"Warning: Missing expected key in benchmark data: {e}", file=sys.stderr)
        return 0  # Don't fail the playbook - this is a non-critical enhancement

    except Exception as e:
        print(f"Warning: Could not extract benchmark timings: {e}", file=sys.stderr)
        return 0  # Don't fail the playbook - this is a non-critical enhancement


if __name__ == '__main__':
    sys.exit(main())
