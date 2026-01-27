#!/usr/bin/env python3
"""
Analyze guidellm sweep test results and generate performance reports.

This script processes benchmark CSV data from /Users/Xeon-single-platform and creates
visualizations and tables comparing performance metrics across different configurations.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import re

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)

def parse_csv_file(csv_path):
    """Parse a guidellm CSV file with multi-level headers."""
    # Read the CSV file, skipping the first row (category headers)
    df = pd.read_csv(csv_path, header=[1, 2])

    # Filter out the header explanation rows (row 3 in the original CSV)
    df = df[df.iloc[:, 0] != '']  # Remove empty rows

    return df

def extract_metrics(df):
    """Extract key metrics from the dataframe."""
    metrics = []

    for idx, row in df.iterrows():
        try:
            metric = {
                'run_index': int(row[('Run Info', 'Run Index')]),
                'strategy': row[('Benchmark', 'Strategy')],
                'requests_sec_mean': float(row[('Server Throughput', 'Successful Requests/Sec')].split(',')[0]) if isinstance(row[('Server Throughput', 'Successful Requests/Sec')], str) else float(row[('Server Throughput', 'Successful Requests/Sec')]),
                'concurrency_mean': float(row[('Server Throughput', 'Successful Concurrency')].split(',')[0]) if isinstance(row[('Server Throughput', 'Successful Concurrency')], str) else float(row[('Server Throughput', 'Successful Concurrency')]),
                'throughput_tokens_sec_mean': float(row[('Token Throughput', 'Successful Output Tokens/Sec')].split(',')[0]) if isinstance(row[('Token Throughput', 'Successful Output Tokens/Sec')], str) else float(row[('Token Throughput', 'Successful Output Tokens/Sec')]),
                'ttft_mean': float(row[('Time to First Token', 'Successful ms')].split(',')[0]) if isinstance(row[('Time to First Token', 'Successful ms')], str) else float(row[('Time to First Token', 'Successful ms')]),
                'tpot_mean': float(row[('Time per Output Token', 'Successful ms')].split(',')[0]) if isinstance(row[('Time per Output Token', 'Successful ms')], str) else float(row[('Time per Output Token', 'Successful ms')]),
                'latency_mean': float(row[('Request Latency', 'Successful Sec')].split(',')[0]) if isinstance(row[('Request Latency', 'Successful Sec')], str) else float(row[('Request Latency', 'Successful Sec')]),
                'successful_requests': int(row[('Request Counts', 'Successful')]),
            }
            metrics.append(metric)
        except (ValueError, KeyError, AttributeError) as e:
            print(f"Warning: Could not parse row {idx}: {e}")
            continue

    return pd.DataFrame(metrics)

def load_all_results(base_path="/Users/Xeon-single-platform"):
    """Load all benchmark results from the directory."""
    base = Path(base_path)
    all_results = []

    # Pattern to extract test info from directory name
    pattern = r'T(\d+)-(llama|tinyllama)-(\d+)c-nopreempt'

    for test_dir in sorted(base.iterdir()):
        if not test_dir.is_dir() or test_dir.name.startswith('.'):
            continue

        match = re.match(pattern, test_dir.name)
        if not match:
            continue

        test_num, model, cores = match.groups()

        csv_file = test_dir / f"{test_dir.name}.csv"
        if not csv_file.exists():
            print(f"Warning: CSV file not found for {test_dir.name}")
            continue

        print(f"Processing {test_dir.name}...")
        try:
            df = parse_csv_file(csv_file)
            metrics_df = extract_metrics(df)

            # Add metadata
            metrics_df['test_name'] = test_dir.name
            metrics_df['model'] = 'Llama' if model == 'llama' else 'TinyLlama'
            metrics_df['cores'] = int(cores)
            metrics_df['test_num'] = int(test_num)

            all_results.append(metrics_df)
        except Exception as e:
            print(f"Error processing {test_dir.name}: {e}")
            continue

    if not all_results:
        raise ValueError("No results found!")

    return pd.concat(all_results, ignore_index=True)

def create_comparison_plots(df, output_dir="benchmark_reports"):
    """Create comparison plots for all metrics."""
    Path(output_dir).mkdir(exist_ok=True)

    # Filter to get the best performing run for each configuration
    # We'll use the run with highest throughput for each test
    best_runs = df.loc[df.groupby('test_name')['throughput_tokens_sec_mean'].idxmax()]

    metrics = [
        ('requests_sec_mean', 'Requests/Second', 'Requests per Second'),
        ('concurrency_mean', 'Mean Concurrency', 'Concurrent Requests'),
        ('throughput_tokens_sec_mean', 'Throughput (tokens/sec)', 'Tokens per Second'),
        ('ttft_mean', 'TTFT (ms)', 'Time to First Token (ms)'),
        ('tpot_mean', 'TPOT (ms)', 'Time per Output Token (ms)'),
        ('latency_mean', 'Latency (sec)', 'Request Latency (seconds)'),
    ]

    for metric_col, metric_name, ylabel in metrics:
        fig, ax = plt.subplots(figsize=(12, 6))

        # Prepare data for plotting
        plot_data = best_runs.pivot(index='cores', columns='model', values=metric_col)

        # Create bar plot
        x = np.arange(len(plot_data.index))
        width = 0.35

        bars1 = ax.bar(x - width/2, plot_data['Llama'], width, label='Llama', alpha=0.8)
        bars2 = ax.bar(x + width/2, plot_data['TinyLlama'], width, label='TinyLlama', alpha=0.8)

        ax.set_xlabel('Number of Cores', fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(f'{metric_name} vs Core Count', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([f'{cores}c' for cores in plot_data.index])
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

        # Add value labels on bars
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if not np.isnan(height):
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.1f}',
                           ha='center', va='bottom', fontsize=9)

        plt.tight_layout()
        plt.savefig(f'{output_dir}/{metric_col}_comparison.png', dpi=300, bbox_inches='tight')
        print(f"Saved {metric_col}_comparison.png")
        plt.close()

    # Create a combined performance overview
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Performance Metrics Overview', fontsize=16, fontweight='bold')

    for idx, (metric_col, metric_name, ylabel) in enumerate(metrics):
        ax = axes[idx // 3, idx % 3]

        plot_data = best_runs.pivot(index='cores', columns='model', values=metric_col)
        x = np.arange(len(plot_data.index))
        width = 0.35

        ax.bar(x - width/2, plot_data['Llama'], width, label='Llama', alpha=0.8)
        ax.bar(x + width/2, plot_data['TinyLlama'], width, label='TinyLlama', alpha=0.8)

        ax.set_xlabel('Cores')
        ax.set_ylabel(ylabel)
        ax.set_title(metric_name, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels([f'{cores}c' for cores in plot_data.index])
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(f'{output_dir}/performance_overview.png', dpi=300, bbox_inches='tight')
    print(f"Saved performance_overview.png")
    plt.close()

def create_summary_tables(df, output_dir="benchmark_reports"):
    """Create summary tables."""
    Path(output_dir).mkdir(exist_ok=True)

    # Get best runs
    best_runs = df.loc[df.groupby('test_name')['throughput_tokens_sec_mean'].idxmax()]

    # Create a comprehensive summary table
    summary = best_runs[['model', 'cores', 'requests_sec_mean', 'concurrency_mean',
                          'throughput_tokens_sec_mean', 'ttft_mean', 'tpot_mean',
                          'latency_mean', 'successful_requests']].copy()

    summary.columns = ['Model', 'Cores', 'Req/s', 'Concurrency', 'Throughput (tok/s)',
                       'TTFT (ms)', 'TPOT (ms)', 'Latency (s)', 'Successful Reqs']

    summary = summary.sort_values(['Model', 'Cores'])

    # Save to CSV
    csv_path = f'{output_dir}/performance_summary.csv'
    summary.to_csv(csv_path, index=False, float_format='%.2f')
    print(f"Saved {csv_path}")

    # Create a nicely formatted text table
    with open(f'{output_dir}/performance_summary.txt', 'w') as f:
        f.write("=" * 120 + "\n")
        f.write("VLLM CPU Performance Evaluation - Benchmark Summary\n")
        f.write("=" * 120 + "\n\n")
        f.write(summary.to_string(index=False))
        f.write("\n\n" + "=" * 120 + "\n")

    print(f"Saved performance_summary.txt")

    # Create pivot tables for each metric
    metrics = {
        'Requests/sec': 'Req/s',
        'Throughput (tokens/sec)': 'Throughput (tok/s)',
        'TTFT (ms)': 'TTFT (ms)',
        'TPOT (ms)': 'TPOT (ms)',
        'Latency (sec)': 'Latency (s)',
        'Concurrency': 'Concurrency'
    }

    with open(f'{output_dir}/pivot_tables.txt', 'w') as f:
        for metric_name, col_name in metrics.items():
            f.write(f"\n{'=' * 80}\n")
            f.write(f"{metric_name} by Model and Core Count\n")
            f.write(f"{'=' * 80}\n")
            pivot = summary.pivot(index='Model', columns='Cores', values=col_name)
            f.write(pivot.to_string(float_format='%.2f'))
            f.write("\n")

    print(f"Saved pivot_tables.txt")

    return summary

def main():
    """Main execution function."""
    print("Loading benchmark results...")
    df = load_all_results()

    print(f"\nLoaded {len(df)} benchmark runs from {df['test_name'].nunique()} tests")
    print(f"Models: {df['model'].unique()}")
    print(f"Core counts: {sorted(df['cores'].unique())}")

    print("\nCreating visualizations...")
    create_comparison_plots(df)

    print("\nGenerating summary tables...")
    summary = create_summary_tables(df)

    print("\n" + "=" * 80)
    print("Summary Preview:")
    print("=" * 80)
    print(summary.to_string(index=False))

    print("\n" + "=" * 80)
    print("Analysis complete! Check the 'benchmark_reports' directory for outputs.")
    print("=" * 80)

if __name__ == "__main__":
    main()
