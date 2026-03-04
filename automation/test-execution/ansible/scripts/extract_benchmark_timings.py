#!/usr/bin/env python3
"""Extract per-benchmark timings from benchmarks.json and add to test-metadata.json

This script processes GuideLLM benchmark results and extracts detailed timing information
for each benchmark run, including duration, requests processed, and temporal metadata.
The extracted data is appended to the test-metadata.json file for later analysis.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Time conversion constants
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60


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


def format_duration(total_seconds: float) -> str:
    """Format duration as HH:MM:SS string.

    Args:
        total_seconds: Duration in seconds

    Returns:
        Formatted string in HH:MM:SS format
    """
    hours = int(total_seconds // SECONDS_PER_HOUR)
    minutes = int((total_seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE)
    seconds = int(total_seconds % SECONDS_PER_MINUTE)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data as a dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json_file(file_path: Path, data: Dict[str, Any]) -> None:
    """Save data to a JSON file with pretty formatting.

    Args:
        file_path: Path to the output JSON file
        data: Dictionary to save as JSON
    """
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')  # Add trailing newline


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

        # Save updated metadata
        save_json_file(metadata_file, metadata)

        # Report success
        print(f"✓ Added {len(benchmark_timings)} benchmark timing(s) to metadata")
        print(f"✓ Total test duration: {test_duration_string} ({int(total_duration)}s)")
        return 0

    except FileNotFoundError as e:
        print(f"Warning: File not found: {e.filename}", file=sys.stderr)
        return 0  # Don't fail the playbook - this is a non-critical enhancement

    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in file: {e}", file=sys.stderr)
        return 0  # Don't fail the playbook - this is a non-critical enhancement

    except KeyError as e:
        print(f"Warning: Missing expected key in benchmark data: {e}", file=sys.stderr)
        return 0  # Don't fail the playbook - this is a non-critical enhancement

    except Exception as e:
        print(f"Warning: Could not extract benchmark timings: {e}", file=sys.stderr)
        return 0  # Don't fail the playbook - this is a non-critical enhancement


if __name__ == '__main__':
    sys.exit(main())
