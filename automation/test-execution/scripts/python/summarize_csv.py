#!/usr/bin/env python3
"""Quick summary of client metrics CSV data."""

import argparse
import sys
from pathlib import Path

import pandas as pd


def repo_root() -> Path:
    """Return the repository root (mt-perf-eval)."""
    return Path(__file__).resolve().parents[4]


def default_llm_csv(results_dir: Path) -> Path:
    """Default LLM CSV produced by convert_batch.py."""
    return results_dir / "managed_cpu_benchmarks.csv"


def default_client_metrics_csv(results_dir: Path) -> Path:
    """Default client-metrics export from the dashboard."""
    return results_dir / "client_metrics_full_data.csv"


def summarize_csv(csv_file: Path) -> None:
    """Generate readable summary of client metrics data."""
    if not csv_file.exists():
        print(f"ERROR: CSV file not found: {csv_file}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_file)

    required_columns = {
        "model",
        "workload",
        "model_short",
        "concurrency",
        "success_rate",
        "throughput_mean",
        "e2e_mean",
        "e2e_p95",
        "ttft_mean",
        "ttft_p95",
        "itl_mean",
        "itl_p95",
    }
    missing = required_columns - set(df.columns)
    if missing:
        print(
            "ERROR: CSV is missing expected client-metrics columns: "
            f"{', '.join(sorted(missing))}",
            file=sys.stderr,
        )
        print(
            "This script expects a Client Metrics dashboard export "
            f"(e.g. {default_client_metrics_csv(repo_root() / 'results').name}).",
            file=sys.stderr,
        )
        print(
            f"For convert_batch output ({default_llm_csv(repo_root() / 'results').name}), "
            "use the dashboard or convert_single column names instead.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("=" * 80)
    print("CLIENT METRICS DATA SUMMARY")
    print("=" * 80)
    print()

    print(f"Total data points: {len(df)}")
    print(f"Unique models: {df['model'].nunique()}")
    print(f"Workloads: {', '.join(df['workload'].unique())}")
    print()

    print("MODELS TESTED:")
    print("-" * 80)
    for model in sorted(df["model_short"].unique()):
        model_df = df[df["model_short"] == model]
        workloads = ", ".join(sorted(model_df["workload"].unique()))
        conc_range = f"{model_df['concurrency'].min():.0f}-{model_df['concurrency'].max():.0f}"
        print(f"  {model:50s} {workloads:15s} (concurrency: {conc_range})")
    print()

    print("PEAK PERFORMANCE (at highest stable concurrency):")
    print("-" * 80)

    for model in sorted(df["model_short"].unique()):
        model_df = df[df["model_short"] == model]

        good_runs = model_df[model_df["success_rate"] >= 80]
        if good_runs.empty:
            continue

        best_idx = good_runs["throughput_mean"].idxmax()
        best = good_runs.loc[best_idx]

        print(f"\n  {model}")
        print(f"    Concurrency:      {best['concurrency']:.0f}")
        print(f"    Throughput:       {best['throughput_mean']:.1f} req/s")
        print(
            f"    E2E Latency:      {best['e2e_mean']:.0f}ms (mean), "
            f"{best['e2e_p95']:.0f}ms (p95)"
        )
        print(
            f"    TTFT:             {best['ttft_mean']:.0f}ms (mean), "
            f"{best['ttft_p95']:.0f}ms (p95)"
        )
        print(
            f"    ITL:              {best['itl_mean']:.0f}ms (mean), "
            f"{best['itl_p95']:.0f}ms (p95)"
        )
        print(f"    Success Rate:     {best['success_rate']:.1f}%")

    print()
    print("=" * 80)
    print()

    print("THROUGHPUT TABLE (req/s by concurrency):")
    print("-" * 80)
    pivot = df.pivot_table(
        index="model_short",
        columns="concurrency",
        values="throughput_mean",
        aggfunc="mean",
    )
    print(pivot.round(1).to_string())
    print()
    print("=" * 80)


def parse_args() -> argparse.Namespace:
    root = repo_root()
    default_results_dir = root / "results"

    parser = argparse.ArgumentParser(
        description="Summarize client metrics CSV data exported from the dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Expected input is client_metrics_full_data.csv from the Client Metrics "
            "dashboard page.\n\n"
            "LLM benchmark CSVs from convert_batch.py use a different schema:\n"
            f"  {default_llm_csv(default_results_dir)}\n"
            f"  {default_results_dir / 'external_cpu_benchmarks.csv'}\n\n"
            "Embedding benchmark CSVs from convert_embedding_results.py:\n"
            f"  {default_results_dir / 'embedding-results.csv'}"
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=default_results_dir,
        help="Directory containing benchmark CSV files (default: <repo>/results)",
    )
    parser.add_argument(
        "--csv-file",
        type=Path,
        help=(
            "Path to client metrics CSV "
            f"(default: <results-dir>/{default_client_metrics_csv(default_results_dir).name})"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_file = args.csv_file or default_client_metrics_csv(args.results_dir)
    summarize_csv(csv_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
