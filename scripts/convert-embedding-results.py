#!/usr/bin/env python3
"""
Convert vLLM embedding benchmark JSON results to CSV format.

Supports:
- Baseline performance tests (sweep-inf, sweep-25pct, sweep-50pct, sweep-75pct)
- Concurrent load tests (concurrent-16, concurrent-32, etc.)
- Core count sweep analysis
- Multi-model comparison

Usage:
    # Convert all results in default location
    python scripts/convert-embedding-results.py

    # Specify custom results directory
    python scripts/convert-embedding-results.py --results-dir ./results/embedding

    # Convert specific model
    python scripts/convert-embedding-results.py --model "RedHatAI/all-MiniLM-L6-v2"

    # Export to specific output file
    python scripts/convert-embedding-results.py --output embedding-metrics.csv
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import csv


def load_json_result(filepath: Path) -> Optional[Dict]:
    """Load and parse a JSON result file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: Failed to load {filepath}: {e}", file=sys.stderr)
        return None


def parse_test_type(filename: str) -> tuple[str, Optional[str]]:
    """
    Parse test type and parameter from filename.

    Returns:
        (test_type, parameter) tuple
        Examples:
            sweep-inf.json -> ("baseline", "inf")
            sweep-25pct.json -> ("baseline", "25pct")
            concurrent-16.json -> ("concurrent", "16")
    """
    stem = filename.replace('.json', '')

    if stem.startswith('sweep-'):
        load_level = stem.replace('sweep-', '')
        return ("baseline", load_level)
    elif stem.startswith('concurrent-'):
        concurrency = stem.replace('concurrent-', '')
        return ("concurrent", concurrency)
    else:
        return ("unknown", None)


def extract_core_count(test_run_id: str) -> Optional[int]:
    """
    Extract core count from test run ID if present.

    Examples:
        baseline-20260602-105959 -> None
        baseline-16c-20260602-105959 -> 16
        concurrent-32c-20260602-105959 -> 32
    """
    parts = test_run_id.split('-')
    for part in parts:
        if part.endswith('c') and part[:-1].isdigit():
            return int(part[:-1])
    return None


def flatten_result(
    result: Dict,
    model_name: str,
    test_run_id: str,
    test_type: str,
    parameter: str,
    core_count: Optional[int]
) -> Dict:
    """Flatten JSON result into a single row for CSV."""
    row = {
        'model': model_name,
        'test_run_id': test_run_id,
        'test_type': test_type,
        'parameter': parameter,
        'core_count': core_count,
        'date': result.get('date'),
        'backend': result.get('backend'),
        'num_prompts': result.get('num_prompts'),
        'request_rate': result.get('request_rate'),
        'max_concurrency': result.get('max_concurrency'),
        'duration_sec': result.get('duration'),
        'completed_requests': result.get('completed'),
        'total_input_tokens': result.get('total_input_tokens'),
        'request_throughput_rps': result.get('request_throughput'),
        'token_throughput_tps': result.get('total_token_throughput'),
        'mean_latency_ms': result.get('mean_e2el_ms'),
        'median_latency_ms': result.get('median_e2el_ms'),
        'std_latency_ms': result.get('std_e2el_ms'),
        'p99_latency_ms': result.get('p99_e2el_ms'),
    }
    return row


def scan_results_directory(results_dir: Path, model_filter: Optional[str] = None) -> List[Dict]:
    """
    Scan results directory and collect all metrics.

    Expected structure:
        results/embedding/
        ├── RedHatAI__all-MiniLM-L6-v2/
        │   └── 20260602-105959/
        │       ├── baseline/
        │       │   ├── sweep-inf.json
        │       │   ├── sweep-25pct.json
        │       │   ├── sweep-50pct.json
        │       │   └── sweep-75pct.json
        │       ├── latency/
        │       │   ├── concurrent-16.json
        │       │   ├── concurrent-32.json
        │       │   └── ...
        │       └── test-metadata.json
    """
    rows = []

    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}", file=sys.stderr)
        return rows

    # Iterate through model directories
    for model_dir in sorted(results_dir.iterdir()):
        if not model_dir.is_dir():
            continue

        # Model name with slashes restored
        model_name = model_dir.name.replace('__', '/')

        # Apply model filter if specified
        if model_filter and model_filter not in model_name:
            continue

        # Iterate through test run directories
        for test_run_dir in sorted(model_dir.iterdir()):
            if not test_run_dir.is_dir():
                continue

            test_run_id = test_run_dir.name
            core_count = extract_core_count(test_run_id)

            # Process JSON files in baseline/ and latency/ subdirectories
            for subdir_name in ['baseline', 'latency']:
                subdir = test_run_dir / subdir_name
                if not subdir.exists():
                    continue

                # Process all JSON files in this subdirectory
                for json_file in sorted(subdir.glob('*.json')):
                    result = load_json_result(json_file)
                    if not result:
                        continue

                    test_type, parameter = parse_test_type(json_file.name)

                    row = flatten_result(
                        result=result,
                        model_name=model_name,
                        test_run_id=test_run_id,
                        test_type=test_type,
                        parameter=parameter,
                        core_count=core_count
                    )
                    rows.append(row)

    return rows


def write_csv(rows: List[Dict], output_path: Path):
    """Write metrics to CSV file."""
    if not rows:
        print("Warning: No results found to export", file=sys.stderr)
        return

    fieldnames = [
        'model',
        'test_run_id',
        'test_type',
        'parameter',
        'core_count',
        'date',
        'backend',
        'num_prompts',
        'request_rate',
        'max_concurrency',
        'duration_sec',
        'completed_requests',
        'total_input_tokens',
        'request_throughput_rps',
        'token_throughput_tps',
        'mean_latency_ms',
        'median_latency_ms',
        'std_latency_ms',
        'p99_latency_ms',
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ Exported {len(rows)} results to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert vLLM embedding benchmark results to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--results-dir',
        type=Path,
        default=Path('results/embedding'),
        help='Path to embedding results directory (default: results/embedding)'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Filter results by model name (substring match)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('embedding-results.csv'),
        help='Output CSV file path (default: embedding-results.csv)'
    )

    args = parser.parse_args()

    print(f"Scanning results directory: {args.results_dir}")
    if args.model:
        print(f"Filtering by model: {args.model}")

    rows = scan_results_directory(args.results_dir, args.model)

    if rows:
        write_csv(rows, args.output)

        # Print summary
        models = set(r['model'] for r in rows)
        test_types = set(r['test_type'] for r in rows)
        print(f"\nSummary:")
        print(f"  Models: {len(models)}")
        print(f"  Test types: {', '.join(sorted(test_types))}")
        print(f"  Total metrics: {len(rows)}")
    else:
        print("No results found.", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
