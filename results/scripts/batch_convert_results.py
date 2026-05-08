#!/usr/bin/env python3
"""Batch convert CPU benchmark results to dashboard CSV format.

This script recursively finds all benchmark results in the results/llm directory
and converts them using the CPU-specific import script.
"""

import subprocess
import sys
from pathlib import Path


def find_benchmark_results(results_dir):
    """Find all benchmark result directories with benchmarks.json and test-metadata.json.

    Args:
        results_dir: Root directory to search for results.

    Returns:
        list: List of tuples (benchmarks_json_path, metadata_json_path)
    """
    results = []
    results_path = Path(results_dir)

    # Find all directories containing both required files
    for benchmarks_json in results_path.rglob("benchmarks.json"):
        parent_dir = benchmarks_json.parent
        metadata_json = parent_dir / "test-metadata.json"

        if metadata_json.exists():
            results.append((str(benchmarks_json), str(metadata_json)))
        else:
            print(f"Warning: Found {benchmarks_json} but no corresponding test-metadata.json")

    return results


def convert_result(benchmarks_json, metadata_json, output_csv, script_path):
    """Convert a single benchmark result to CSV format.

    Args:
        benchmarks_json: Path to benchmarks.json
        metadata_json: Path to test-metadata.json
        output_csv: Path to output CSV file
        script_path: Path to the import_manual_runs_json_cpu.py script

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

    print(f"\nProcessing: {benchmarks_json}")
    print(f"  Metadata: {metadata_json}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
        return True
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
    output_csv = repo_root / "results" / "all_cpu_benchmarks.csv"
    import_script = script_dir / "import_manual_runs_json_cpu.py"

    if not results_dir.exists():
        print(f"Error: Results directory '{results_dir}' not found")
        sys.exit(1)

    if not import_script.exists():
        print(f"Error: Import script '{import_script}' not found")
        sys.exit(1)

    # Find all benchmark results
    print(f"Searching for benchmark results in {results_dir}...")
    benchmark_results = find_benchmark_results(str(results_dir))

    if not benchmark_results:
        print("No benchmark results found!")
        sys.exit(1)

    print(f"\nFound {len(benchmark_results)} benchmark result(s)")

    # Process each result
    successful = 0
    failed = 0

    for benchmarks_json, metadata_json in benchmark_results:
        if convert_result(benchmarks_json, metadata_json, str(output_csv), str(import_script)):
            successful += 1
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("Batch Conversion Summary")
    print("=" * 60)
    print(f"Total results found: {len(benchmark_results)}")
    print(f"Successfully converted: {successful}")
    print(f"Failed: {failed}")
    print(f"\nOutput CSV: {output_csv}")
    print(f"Script location: {import_script}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
