#!/usr/bin/env python3
"""Helper functions for validating benchmark metrics and results."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


def validate_benchmark_output(output_file: Path) -> Dict[str, Any]:
    """
    Validate GuideLLM benchmark output structure.

    Args:
        output_file: Path to benchmark output JSON file

    Returns:
        Dict with validation results

    Raises:
        AssertionError: If validation fails
    """
    assert output_file.exists(), f"Benchmark output not found: {output_file}"

    with open(output_file) as f:
        data = json.load(f)

    validation = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "metrics": {},
    }

    # Check for required top-level keys
    required_keys = ["benchmark_results", "benchmark_config"]
    for key in required_keys:
        if key not in data:
            validation["errors"].append(f"Missing required key: {key}")
            validation["valid"] = False

    if not validation["valid"]:
        return validation

    # Validate benchmark results
    results = data.get("benchmark_results", {})
    required_metrics = [
        "throughput",
        "time_to_first_token",
        "inter_token_latency",
        "request_latency",
    ]

    for metric in required_metrics:
        if metric not in results:
            validation["errors"].append(f"Missing metric: {metric}")
            validation["valid"] = False
        else:
            # Check for common statistical fields
            metric_data = results[metric]
            if isinstance(metric_data, dict):
                validation["metrics"][metric] = {
                    "mean": metric_data.get("mean"),
                    "p50": metric_data.get("p50"),
                    "p95": metric_data.get("p95"),
                    "p99": metric_data.get("p99"),
                }

    return validation


def validate_results_structure(results_dir: Path) -> Dict[str, Any]:
    """
    Validate benchmark results directory structure.

    Args:
        results_dir: Path to results directory

    Returns:
        Dict with validation results
    """
    validation = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "files_found": [],
    }

    if not results_dir.exists():
        validation["errors"].append(f"Results directory not found: {results_dir}")
        validation["valid"] = False
        return validation

    # Expected files/patterns
    expected_patterns = [
        "*.json",  # Benchmark output
        "*.log",   # Server logs
    ]

    for pattern in expected_patterns:
        files = list(results_dir.glob(pattern))
        if not files:
            validation["warnings"].append(f"No files matching pattern: {pattern}")
        validation["files_found"].extend([f.name for f in files])

    return validation


def extract_key_metrics(benchmark_output: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract key performance metrics from benchmark output.

    Args:
        benchmark_output: Parsed benchmark JSON

    Returns:
        Dict of key metrics
    """
    results = benchmark_output.get("benchmark_results", {})

    metrics = {}

    # Throughput
    if "throughput" in results:
        throughput = results["throughput"]
        if isinstance(throughput, dict):
            metrics["throughput_mean"] = throughput.get("mean")
        elif isinstance(throughput, (int, float)):
            metrics["throughput_mean"] = throughput

    # Time to First Token (TTFT)
    if "time_to_first_token" in results:
        ttft = results["time_to_first_token"]
        if isinstance(ttft, dict):
            metrics["ttft_p50"] = ttft.get("p50")
            metrics["ttft_p95"] = ttft.get("p95")
            metrics["ttft_p99"] = ttft.get("p99")

    # Inter-Token Latency (TPOT)
    if "inter_token_latency" in results:
        tpot = results["inter_token_latency"]
        if isinstance(tpot, dict):
            metrics["tpot_p50"] = tpot.get("p50")
            metrics["tpot_p95"] = tpot.get("p95")

    # Request Latency
    if "request_latency" in results:
        latency = results["request_latency"]
        if isinstance(latency, dict):
            metrics["latency_p50"] = latency.get("p50")
            metrics["latency_p95"] = latency.get("p95")
            metrics["latency_p99"] = latency.get("p99")

    return metrics


def assert_metrics_within_range(
    metrics: Dict[str, float],
    expected_ranges: Dict[str, tuple],
) -> None:
    """
    Assert that metrics fall within expected ranges.

    Args:
        metrics: Actual metrics
        expected_ranges: Dict of {metric_name: (min, max)}

    Raises:
        AssertionError: If any metric is out of range
    """
    for metric_name, (min_val, max_val) in expected_ranges.items():
        if metric_name not in metrics:
            raise AssertionError(f"Missing metric: {metric_name}")

        actual_val = metrics[metric_name]
        if actual_val is None:
            raise AssertionError(f"Metric {metric_name} is None")

        if not (min_val <= actual_val <= max_val):
            raise AssertionError(
                f"Metric {metric_name}={actual_val} not in range [{min_val}, {max_val}]"
            )


def compare_metrics(
    baseline: Dict[str, float],
    current: Dict[str, float],
    tolerance_pct: float = 10.0,
) -> Dict[str, Any]:
    """
    Compare current metrics against baseline with tolerance.

    Args:
        baseline: Baseline metrics
        current: Current metrics
        tolerance_pct: Acceptable percentage deviation

    Returns:
        Dict with comparison results
    """
    comparison = {
        "passed": True,
        "failures": [],
        "metrics": {},
    }

    for metric_name in baseline:
        if metric_name not in current:
            comparison["failures"].append(f"Missing metric in current: {metric_name}")
            comparison["passed"] = False
            continue

        baseline_val = baseline[metric_name]
        current_val = current[metric_name]

        if baseline_val is None or current_val is None:
            continue

        # Handle division by zero
        if baseline_val == 0:
            if current_val == 0:
                deviation_pct = 0.0
                passed = True
            else:
                deviation_pct = float('inf')
                passed = False
        else:
            deviation_pct = abs((current_val - baseline_val) / baseline_val * 100)
            passed = deviation_pct <= tolerance_pct

        comparison["metrics"][metric_name] = {
            "baseline": baseline_val,
            "current": current_val,
            "deviation_pct": deviation_pct,
            "passed": passed,
        }

        if not passed:
            comparison["failures"].append(
                f"{metric_name}: {deviation_pct:.1f}% deviation "
                f"(baseline={baseline_val}, current={current_val})"
            )
            comparison["passed"] = False

    return comparison
