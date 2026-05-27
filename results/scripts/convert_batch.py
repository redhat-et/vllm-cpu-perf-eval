#!/usr/bin/env python3
"""Batch convert CPU benchmark results to dashboard CSV format.

This script recursively finds all benchmark results in the results/llm directory
and converts them using the CPU-specific import script.

Results are separated into two CSV files based on vllm_mode:
- managed_cpu_benchmarks.csv: Single-instance tests (vllm_mode=managed)
- external_cpu_benchmarks.csv: External Endpoint/Multi-instance tests (vllm_mode=external)
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd


def find_benchmark_results(results_dir):
    """Find all benchmark result directories with benchmarks.json and test-metadata.json.

    Args:
        results_dir: Root directory to search for results.

    Returns:
        list: List of tuples (benchmarks_json_path, metadata_json_path, vllm_metrics_json_path)
    """
    results = []
    results_path = Path(results_dir)

    # Find all directories containing both required files
    for benchmarks_json in results_path.rglob("benchmarks.json"):
        parent_dir = benchmarks_json.parent
        metadata_json = parent_dir / "test-metadata.json"
        vllm_metrics_json = parent_dir / "vllm-metrics.json"

        if metadata_json.exists():
            # vllm-metrics.json is optional - include path if it exists, else None
            vllm_path = str(vllm_metrics_json) if vllm_metrics_json.exists() else None
            results.append((str(benchmarks_json), str(metadata_json), vllm_path))
        else:
            print(f"Warning: Found {benchmarks_json} but no corresponding test-metadata.json")

    return results


def convert_result(benchmarks_json, metadata_json, vllm_metrics_json, output_csv, script_path):
    """Convert a single benchmark result to CSV format.

    Args:
        benchmarks_json: Path to benchmarks.json
        metadata_json: Path to test-metadata.json
        vllm_metrics_json: Path to vllm-metrics.json (optional, can be None)
        output_csv: Path to output CSV file
        script_path: Path to the convert_single.py script

    Returns:
        bool: True if successful, False otherwise
    """
    cmd = [
        sys.executable,  # Use the same Python interpreter
        script_path,
        benchmarks_json,
        "--metadata-file", metadata_json,
        "--csv-file", output_csv,
    ]

    # Add vllm-metrics file if available
    if vllm_metrics_json:
        cmd.extend(["--vllm-metrics-file", vllm_metrics_json])

    print(f"\nProcessing: {benchmarks_json}")
    print(f"  Metadata: {metadata_json}")
    if vllm_metrics_json:
        print(f"  Server Metrics: {vllm_metrics_json}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minutes timeout to avoid indefinite blocking
        )
        print(result.stdout)
        return True
    except subprocess.TimeoutExpired:
        print(f"Error: Conversion timed out after 300s for {benchmarks_json}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error processing {benchmarks_json}:")
        print(e.stdout)
        print(e.stderr)
        return False


def main():
    """Main batch conversion function."""
    # Determine paths - script can be run from repo root or from results/scripts/
    script_dir = Path(__file__).parent.absolute()
    repo_root = script_dir.parent.parent if script_dir.name == "scripts" else Path.cwd()

    # Configuration
    results_dir = repo_root / "results" / "llm"
    temp_csv = repo_root / "results" / "temp_all_cpu_benchmarks.csv"
    managed_csv = repo_root / "results" / "managed_cpu_benchmarks.csv"
    external_csv = repo_root / "results" / "external_cpu_benchmarks.csv"
    import_script = script_dir / "convert_single.py"

    if not results_dir.exists():
        print(f"Error: Results directory '{results_dir}' not found")
        sys.exit(1)

    if not import_script.exists():
        print(f"Error: Single converter script '{import_script}' not found")
        sys.exit(1)

    # Remove temp CSV if it exists
    if temp_csv.exists():
        temp_csv.unlink()

    # Find all benchmark results
    print(f"Searching for benchmark results in {results_dir}...")
    benchmark_results = find_benchmark_results(str(results_dir))

    if not benchmark_results:
        print("No benchmark results found!")
        sys.exit(1)

    print(f"\nFound {len(benchmark_results)} benchmark result(s)")

    # Process each result into temp CSV
    successful = 0
    failed = 0

    for benchmarks_json, metadata_json, vllm_metrics_json in benchmark_results:
        if convert_result(benchmarks_json, metadata_json, vllm_metrics_json, str(temp_csv), str(import_script)):
            successful += 1
        else:
            failed += 1

    if failed > 0:
        print(f"\nWarning: {failed} results failed to convert")

    # Split results by vllm_mode
    if temp_csv.exists():
        print("\nSplitting results by vllm_mode...")
        df = pd.read_csv(temp_csv)

        # Split into managed and external
        managed_df = df[df['vllm_mode'] == 'managed']
        external_df = df[df['vllm_mode'] == 'external']

        # Save to separate files
        if not managed_df.empty:
            managed_df.to_csv(managed_csv, index=False)
            print(f"  Saved {len(managed_df)} managed results to {managed_csv}")
        else:
            print("  No managed results found")

        if not external_df.empty:
            external_df.to_csv(external_csv, index=False)
            print(f"  Saved {len(external_df)} external results to {external_csv}")
        else:
            print("  No external results found")

        # Clean up temp file
        temp_csv.unlink()
        print(f"  Removed temporary file {temp_csv}")

    # Summary
    print("\n" + "=" * 60)
    print("Batch Conversion Summary")
    print("=" * 60)
    print(f"Total results found: {len(benchmark_results)}")
    print(f"Successfully converted: {successful}")
    print(f"Failed: {failed}")
    print(f"\nOutput files:")
    print(f"  Managed (single-instance): {managed_csv}")
    print(f"  External (variable instances): {external_csv}")
    print(f"Script location: {import_script}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
