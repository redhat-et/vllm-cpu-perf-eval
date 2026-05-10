#!/usr/bin/env python3
"""Analyze benchmark repeatability using Coefficient of Variation (CV).

This script analyzes GuideLLM benchmark results across multiple runs to measure
repeatability and consistency. It calculates the Coefficient of Variation (CV)
for each metric and assigns repeatability scores.

CV = (standard deviation / mean) * 100%

CV Interpretation:
- CV < 1%: Excellent repeatability
- CV 1-3%: Good repeatability
- CV 3-5%: Acceptable repeatability
- CV > 5%: Poor repeatability
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


# Repeatability grade thresholds
CV_THRESHOLDS = {
    'excellent': 1.0,  # CV < 1%
    'good': 3.0,       # CV 1-3%
    'acceptable': 5.0,  # CV 3-5%
    # CV > 5% is 'poor'
}

# Metrics to analyze (metric_name: (json_path, unit, display_name))
METRICS_CONFIG = {
    'request_latency_mean': {
        'path': ['metrics', 'request_latency', 'successful', 'mean'],
        'unit': 's',
        'display': 'Request Latency (Mean)',
        'percentiles': ['p90', 'p95']
    },
    'ttft_mean': {
        'path': ['metrics', 'time_to_first_token_ms', 'successful', 'mean'],
        'unit': 'ms',
        'display': 'TTFT (Mean)',
        'percentiles': ['p90', 'p95']
    },
    'tpot_mean': {
        'path': ['metrics', 'inter_token_latency_ms', 'successful', 'mean'],
        'unit': 'ms',
        'display': 'TPoT (Mean)',
        'percentiles': ['p90', 'p95']
    },
    'throughput': {
        'path': ['metrics', 'tokens_per_second', 'successful', 'mean'],
        'unit': 'tok/s',
        'display': 'Output Throughput',
        'percentiles': []
    },
}


def get_nested_value(data: Dict[str, Any], path: List[str], default=None) -> Any:
    """Get value from nested dictionary using path."""
    current = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def calculate_cv(values: List[float]) -> float:
    """Calculate coefficient of variation as percentage.

    Args:
        values: List of numeric values

    Returns:
        CV as percentage, or NaN if calculation not possible
    """
    if len(values) < 2:
        return np.nan

    mean = np.mean(values)
    if mean == 0:
        return np.nan

    std = np.std(values, ddof=1)  # Sample standard deviation
    return (std / mean) * 100


def get_repeatability_grade(cv: float) -> str:
    """Assign repeatability grade based on CV value.

    Args:
        cv: Coefficient of variation as percentage

    Returns:
        Grade string: 'Excellent', 'Good', 'Acceptable', or 'Poor'
    """
    if np.isnan(cv):
        return 'N/A'

    if cv < CV_THRESHOLDS['excellent']:
        return 'Excellent'
    elif cv < CV_THRESHOLDS['good']:
        return 'Good'
    elif cv < CV_THRESHOLDS['acceptable']:
        return 'Acceptable'
    else:
        return 'Poor'


def get_letter_grade(avg_cv: float) -> str:
    """Convert average CV to letter grade.

    Args:
        avg_cv: Average CV across metrics

    Returns:
        Letter grade: A+, A, A-, B+, etc.
    """
    if np.isnan(avg_cv):
        return 'N/A'

    if avg_cv < 0.5:
        return 'A+'
    elif avg_cv < 1.0:
        return 'A'
    elif avg_cv < 2.0:
        return 'A-'
    elif avg_cv < 3.0:
        return 'B+'
    elif avg_cv < 5.0:
        return 'B'
    elif avg_cv < 7.5:
        return 'B-'
    else:
        return 'C'


def load_benchmark_runs(results_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Load all benchmark runs and group by configuration.

    Args:
        results_dir: Path to results directory

    Returns:
        Dictionary mapping config_key to list of benchmark runs
    """
    runs_by_config = defaultdict(list)

    if not results_dir.exists():
        print(f"Error: Results directory not found: {results_dir}", file=sys.stderr)
        return {}

    # Scan for all benchmarks.json files
    for json_file in results_dir.rglob("benchmarks.json"):
        try:
            with open(json_file) as f:
                bench_data = json.load(f)

            # Load metadata
            metadata_file = json_file.parent / "test-metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file) as f:
                metadata = json.load(f)

            # Create configuration key
            # Group by: platform, model, workload, cores, tensor_parallel, vllm_version
            config_key = (
                metadata.get('platform', 'unknown'),
                metadata.get('model', 'unknown'),
                metadata.get('workload', 'unknown'),
                metadata.get('core_count', 0),
                metadata.get('tensor_parallel', 1),
                metadata.get('vllm_version', 'unknown')
            )

            # Store each benchmark (concurrency level) separately
            for i, benchmark in enumerate(bench_data.get('benchmarks', [])):
                # Get concurrency/rate
                config = benchmark.get('config', {})
                strategy = config.get('strategy', {})
                concurrency = strategy.get('max_concurrency', 0)

                # Create extended config key including concurrency
                extended_key = config_key + (concurrency,)

                runs_by_config[extended_key].append({
                    'benchmark': benchmark,
                    'metadata': metadata,
                    'concurrency': concurrency
                })

        except Exception as e:
            print(f"Warning: Failed to load {json_file}: {e}", file=sys.stderr)
            continue

    return runs_by_config


def analyze_metric_repeatability(
    runs: List[Dict[str, Any]],
    metric_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyze repeatability for a specific metric across runs.

    Args:
        runs: List of benchmark runs for the same configuration
        metric_config: Configuration for the metric

    Returns:
        Dictionary with mean, std, CV, and grade
    """
    # Extract mean values
    mean_values = []
    percentile_values = defaultdict(list)

    for run in runs:
        benchmark = run['benchmark']

        # Get mean value
        mean_val = get_nested_value(benchmark, metric_config['path'])
        if mean_val is not None:
            mean_values.append(mean_val)

        # Get percentile values if configured
        for percentile in metric_config.get('percentiles', []):
            percentile_path = metric_config['path'][:-1] + ['percentiles', percentile]
            p_val = get_nested_value(benchmark, percentile_path)
            if p_val is not None:
                percentile_values[percentile].append(p_val)

    # Calculate statistics for mean
    result = {
        'mean': {
            'value': np.mean(mean_values) if mean_values else np.nan,
            'std': np.std(mean_values, ddof=1) if len(mean_values) > 1 else np.nan,
            'cv': calculate_cv(mean_values),
            'n_runs': len(mean_values)
        }
    }

    result['mean']['grade'] = get_repeatability_grade(result['mean']['cv'])

    # Calculate statistics for percentiles
    for percentile, values in percentile_values.items():
        result[percentile] = {
            'value': np.mean(values) if values else np.nan,
            'std': np.std(values, ddof=1) if len(values) > 1 else np.nan,
            'cv': calculate_cv(values),
            'n_runs': len(values)
        }
        result[percentile]['grade'] = get_repeatability_grade(result[percentile]['cv'])

    return result


def generate_markdown_report(
    analysis_results: Dict[Tuple, Dict[str, Dict]],
    output_file: Path
) -> None:
    """Generate markdown report with repeatability analysis.

    Args:
        analysis_results: Dictionary mapping config to metric analysis
        output_file: Path to output markdown file
    """
    with open(output_file, 'w') as f:
        f.write("# Benchmark Repeatability Analysis\n\n")

        f.write("## Overview\n\n")
        f.write("Repeatability is measured using the Coefficient of Variation (CV) - ")
        f.write("the ratio of standard deviation to mean, expressed as a percentage. ")
        f.write("Lower CV values indicate better repeatability.\n\n")

        f.write("### CV Interpretation:\n\n")
        f.write("- **CV < 1%**: Excellent repeatability\n")
        f.write("- **CV 1-3%**: Good repeatability\n")
        f.write("- **CV 3-5%**: Acceptable repeatability\n")
        f.write("- **CV > 5%**: Poor repeatability\n\n")

        f.write("---\n\n")

        # Group by base configuration (without concurrency)
        configs_by_base = defaultdict(list)
        for config_key, metrics in analysis_results.items():
            base_key = config_key[:-1]  # Remove concurrency
            configs_by_base[base_key].append((config_key, metrics))

        # Generate report for each base configuration
        for base_config, concurrency_results in sorted(configs_by_base.items()):
            platform, model, workload, cores, tp, vllm_version = base_config

            f.write(f"## Configuration: {platform} - {cores} cores (TP={tp})\n\n")
            f.write(f"**Model:** {model}\n\n")
            f.write(f"**Workload:** {workload}\n\n")
            f.write(f"**vLLM Version:** {vllm_version}\n\n")

            # Sort by concurrency
            concurrency_results.sort(key=lambda x: x[0][-1])

            # Generate tables for each metric
            for metric_name, metric_config in METRICS_CONFIG.items():
                f.write(f"### {metric_config['display']} Repeatability\n\n")

                # Table header
                stats = ['Mean', 'P90', 'P95'] if metric_config['percentiles'] else ['Mean']

                f.write("| Configuration | Stat | ")
                for config_key, _ in concurrency_results:
                    concurrency = config_key[-1]
                    f.write(f"Conc {concurrency} | ")
                f.write("\n")

                f.write("|" + "---|" * (len(concurrency_results) + 2) + "\n")

                # Table rows
                config_name = f"{cores}-core"

                for stat in stats:
                    stat_key = stat.lower() if stat != 'Mean' else 'mean'

                    f.write(f"| {config_name} | {stat} | ")

                    for config_key, metrics in concurrency_results:
                        if metric_name in metrics and stat_key in metrics[metric_name]:
                            data = metrics[metric_name][stat_key]
                            value = data['value']
                            cv = data['cv']
                            unit = metric_config['unit']

                            if not np.isnan(value) and not np.isnan(cv):
                                # Format value based on unit
                                if unit == 's':
                                    f.write(f"{value:.2f}s (±{cv:.2f}%) | ")
                                elif unit == 'ms':
                                    f.write(f"{value:.1f}ms (±{cv:.2f}%) | ")
                                else:
                                    f.write(f"{value:.1f} {unit} (±{cv:.2f}%) | ")
                            else:
                                f.write("N/A | ")
                        else:
                            f.write("N/A | ")

                    f.write("\n")

                f.write("\n")

            f.write("---\n\n")

        # Generate overall rankings
        f.write("## Overall Repeatability Rankings\n\n")

        # Calculate average CV for each configuration
        config_rankings = []

        for base_config, concurrency_results in configs_by_base.items():
            all_cvs = []

            for config_key, metrics in concurrency_results:
                for metric_name, metric_data in metrics.items():
                    for stat_data in metric_data.values():
                        if isinstance(stat_data, dict) and 'cv' in stat_data:
                            cv = stat_data['cv']
                            if not np.isnan(cv):
                                all_cvs.append(cv)

            if all_cvs:
                avg_cv = np.mean(all_cvs)
                median_cv = np.median(all_cvs)
                max_cv = np.max(all_cvs)
                grade = get_letter_grade(avg_cv)

                platform, model, workload, cores, tp, vllm_version = base_config
                config_rankings.append({
                    'config': f"{cores}-core (TP={tp})",
                    'platform': platform,
                    'vllm_version': vllm_version,
                    'avg_cv': avg_cv,
                    'median_cv': median_cv,
                    'max_cv': max_cv,
                    'grade': grade
                })

        # Sort by average CV
        config_rankings.sort(key=lambda x: x['avg_cv'])

        f.write("Configurations ranked by repeatability (lower CV = better):\n\n")
        f.write("| Rank | Configuration | Platform | vLLM Version | Avg CV | Median CV | Max CV | Grade |\n")
        f.write("|------|---------------|----------|--------------|--------|-----------|--------|-------|\n")

        for i, ranking in enumerate(config_rankings, 1):
            f.write(f"| {i} | {ranking['config']} | "
                   f"{ranking['platform']} | "
                   f"{ranking['vllm_version']} | "
                   f"{ranking['avg_cv']:.3f}% | "
                   f"{ranking['median_cv']:.3f}% | "
                   f"{ranking['max_cv']:.3f}% | "
                   f"{ranking['grade']} |\n")

        f.write("\n")


def generate_json_report(
    analysis_results: Dict[Tuple, Dict[str, Dict]],
    output_file: Path
) -> None:
    """Generate JSON report with repeatability analysis.

    Args:
        analysis_results: Dictionary mapping config to metric analysis
        output_file: Path to output JSON file
    """
    # Convert tuple keys to strings for JSON serialization
    json_results = {}

    for config_key, metrics in analysis_results.items():
        platform, model, workload, cores, tp, vllm_version, concurrency = config_key

        config_str = (
            f"{platform}_{model.replace('/', '_')}_"
            f"{workload}_{cores}c_TP{tp}_{vllm_version}_conc{concurrency}"
        )

        # Convert numpy types to Python types
        json_metrics = {}
        for metric_name, metric_data in metrics.items():
            json_metrics[metric_name] = {}
            for stat_name, stat_data in metric_data.items():
                json_metrics[metric_name][stat_name] = {
                    'value': float(stat_data['value']) if not np.isnan(stat_data['value']) else None,
                    'std': float(stat_data['std']) if not np.isnan(stat_data['std']) else None,
                    'cv': float(stat_data['cv']) if not np.isnan(stat_data['cv']) else None,
                    'n_runs': stat_data['n_runs'],
                    'grade': stat_data['grade']
                }

        json_results[config_str] = {
            'platform': platform,
            'model': model,
            'workload': workload,
            'cores': cores,
            'tensor_parallel': tp,
            'vllm_version': vllm_version,
            'concurrency': concurrency,
            'metrics': json_metrics
        }

    with open(output_file, 'w') as f:
        json.dump(json_results, f, indent=2)
        f.write('\n')


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze benchmark repeatability using Coefficient of Variation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze results and generate markdown report
  %(prog)s results/llm -o repeatability_report.md

  # Generate both markdown and JSON reports
  %(prog)s results/llm -o report.md -j report.json

  # Analyze specific model results
  %(prog)s results/llm/meta-llama/Llama-3.2-1B-Instruct -o llama_repeatability.md
        """
    )

    parser.add_argument(
        'results_dir',
        type=Path,
        help='Path to results directory'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        default='repeatability_report.md',
        help='Output markdown file (default: repeatability_report.md)'
    )

    parser.add_argument(
        '-j', '--json-output',
        type=Path,
        help='Optional JSON output file'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Load all benchmark runs
    print(f"Loading benchmark results from {args.results_dir}...")
    runs_by_config = load_benchmark_runs(args.results_dir)

    if not runs_by_config:
        print("Error: No benchmark results found", file=sys.stderr)
        return 1

    print(f"Found {len(runs_by_config)} unique configurations")

    # Analyze repeatability for each configuration
    analysis_results = {}

    for config_key, runs in runs_by_config.items():
        if len(runs) < 2:
            if args.verbose:
                print(f"Skipping {config_key} - only {len(runs)} run(s)")
            continue

        if args.verbose:
            platform, model, workload, cores, tp, vllm_version, conc = config_key
            print(f"Analyzing {platform} {cores}c TP={tp} {vllm_version} conc={conc}: {len(runs)} runs")

        config_analysis = {}

        for metric_name, metric_config in METRICS_CONFIG.items():
            config_analysis[metric_name] = analyze_metric_repeatability(
                runs, metric_config
            )

        analysis_results[config_key] = config_analysis

    if not analysis_results:
        print("Error: No configurations with multiple runs found", file=sys.stderr)
        return 1

    # Generate reports
    print(f"\nGenerating markdown report: {args.output}")
    generate_markdown_report(analysis_results, args.output)

    if args.json_output:
        print(f"Generating JSON report: {args.json_output}")
        generate_json_report(analysis_results, args.json_output)

    print("\n✓ Analysis complete!")

    return 0


if __name__ == '__main__':
    sys.exit(main())
