#!/usr/bin/env python3
"""Log benchmark results to MLflow for experiment tracking.

This script reads benchmark results and metadata from JSON files and logs
them to MLflow, creating a comprehensive experiment tracking system for
LLM inference performance benchmarks.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import mlflow
    from mlflow.entities import RunStatus
except ImportError:
    print("Error: MLflow is not installed. Install with: pip install mlflow", file=sys.stderr)
    sys.exit(1)


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_parameters(metadata: Dict[str, Any], benchmarks: Dict[str, Any]) -> Dict[str, Any]:
    """Extract experiment parameters from metadata and benchmark data."""
    params = {
        # Model and workload configuration
        'model': metadata.get('model', 'unknown'),
        'workload': metadata.get('workload', 'unknown'),
        'backend': metadata.get('backend', 'unknown'),

        # Hardware configuration
        'platform': metadata.get('platform', 'unknown'),
        'core_count': metadata.get('core_count', 0),
        'core_config_name': metadata.get('core_config_name', 'unknown'),
        'cpuset_cpus': metadata.get('cpuset_cpus', 'unknown'),
        'cpuset_mems': metadata.get('cpuset_mems', 'unknown'),
        'tensor_parallel': metadata.get('tensor_parallel', 1),

        # Software versions
        'vllm_version': metadata.get('vllm_version', 'unknown'),
        'guidellm_version': metadata.get('guidellm_version', 'unknown'),

        # Test configuration
        'vllm_mode': metadata.get('vllm_mode', 'managed'),
        'config_type': metadata.get('config_type', 'manual'),
    }

    # Add optional parameters if present
    if metadata.get('omp_num_threads'):
        params['omp_num_threads'] = metadata['omp_num_threads']
    if metadata.get('omp_threads_bind'):
        params['omp_threads_bind'] = metadata['omp_threads_bind']
    if metadata.get('vllm_endpoint_url'):
        params['vllm_endpoint_url'] = metadata['vllm_endpoint_url']
    if metadata.get('model_source'):
        params['model_source'] = metadata['model_source']
    if metadata.get('test_name'):
        params['test_name'] = metadata['test_name']

    # Add benchmark configuration (from first benchmark)
    if benchmarks.get('benchmarks') and len(benchmarks['benchmarks']) > 0:
        first_bench = benchmarks['benchmarks'][0]
        config = first_bench.get('config', {})

        # Strategy configuration
        strategy = config.get('strategy', {})
        if 'max_concurrency' in strategy:
            params['max_concurrency'] = strategy['max_concurrency']
        if 'type' in strategy:
            params['strategy_type'] = strategy['type']

        # Request configuration
        request_config = config.get('request', {})
        if 'output_tokens' in request_config:
            params['output_tokens'] = request_config['output_tokens']
        if 'prompt_tokens' in request_config:
            params['prompt_tokens'] = request_config['prompt_tokens']

    # Add load sweep rates if present
    if benchmarks.get('args', {}).get('rate'):
        params['load_sweep_rates'] = ','.join(map(str, benchmarks['args']['rate']))

    return params


def extract_metrics_from_benchmark(benchmark: Dict[str, Any], prefix: str = "") -> Dict[str, float]:
    """Extract metrics from a single benchmark."""
    metrics_data = benchmark.get('metrics', {})
    extracted = {}

    # Throughput metrics
    throughput = metrics_data.get('tokens_per_second', {}).get('successful', {})
    if throughput:
        extracted[f'{prefix}throughput_mean'] = throughput.get('mean', 0)
        extracted[f'{prefix}throughput_std'] = throughput.get('std', 0)
        percentiles = throughput.get('percentiles', {})
        for p in ['p50', 'p95', 'p99']:
            if p in percentiles:
                extracted[f'{prefix}throughput_{p}'] = percentiles[p]

    # TTFT metrics (ms)
    ttft = metrics_data.get('time_to_first_token_ms', {}).get('successful', {})
    if ttft:
        extracted[f'{prefix}ttft_mean'] = ttft.get('mean', 0)
        extracted[f'{prefix}ttft_std'] = ttft.get('std', 0)
        percentiles = ttft.get('percentiles', {})
        for p in ['p50', 'p95', 'p99']:
            if p in percentiles:
                extracted[f'{prefix}ttft_{p}'] = percentiles[p]

    # ITL metrics (ms)
    itl = metrics_data.get('inter_token_latency_ms', {}).get('successful', {})
    if itl:
        extracted[f'{prefix}itl_mean'] = itl.get('mean', 0)
        extracted[f'{prefix}itl_std'] = itl.get('std', 0)
        percentiles = itl.get('percentiles', {})
        for p in ['p50', 'p95', 'p99']:
            if p in percentiles:
                extracted[f'{prefix}itl_{p}'] = percentiles[p]

    # E2E latency metrics (s)
    e2e = metrics_data.get('request_latency', {}).get('successful', {})
    if e2e:
        extracted[f'{prefix}e2e_latency_mean'] = e2e.get('mean', 0)
        extracted[f'{prefix}e2e_latency_std'] = e2e.get('std', 0)
        percentiles = e2e.get('percentiles', {})
        for p in ['p50', 'p95', 'p99']:
            if p in percentiles:
                extracted[f'{prefix}e2e_latency_{p}'] = percentiles[p]

    # Request metrics
    request_totals = metrics_data.get('request_totals', {})
    if request_totals:
        total = request_totals.get('total', 0)
        successful = request_totals.get('successful', 0)
        extracted[f'{prefix}total_requests'] = total
        extracted[f'{prefix}successful_requests'] = successful
        if total > 0:
            extracted[f'{prefix}success_rate'] = (successful / total) * 100

    # RPS metrics
    rps = metrics_data.get('requests_per_second', {}).get('successful', {})
    if rps:
        extracted[f'{prefix}rps_mean'] = rps.get('mean', 0)

    return extracted


def extract_aggregate_metrics(benchmarks: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, float]:
    """Extract aggregate metrics across all benchmarks (load points)."""
    all_benchmarks = benchmarks.get('benchmarks', [])

    if not all_benchmarks:
        return {}

    # Find peak throughput across all load points
    peak_throughput = 0
    peak_throughput_load = 0

    # Find best (lowest) latencies across all load points
    best_ttft_p95 = float('inf')
    best_ttft_p99 = float('inf')
    best_itl_p95 = float('inf')
    best_itl_p99 = float('inf')
    best_e2e_p95 = float('inf')
    best_e2e_p99 = float('inf')

    rates = benchmarks.get('args', {}).get('rate', [])

    for i, bench in enumerate(all_benchmarks):
        # Get concurrency or rate for this benchmark
        config = bench.get('config', {})
        strategy = config.get('strategy', {})
        concurrency = strategy.get('max_concurrency', 0)
        rate = rates[i] if i < len(rates) else concurrency

        metrics = bench.get('metrics', {})

        # Track peak throughput
        throughput = metrics.get('tokens_per_second', {}).get('successful', {}).get('mean', 0)
        if throughput > peak_throughput:
            peak_throughput = throughput
            peak_throughput_load = rate

        # Track best latencies
        ttft = metrics.get('time_to_first_token_ms', {}).get('successful', {}).get('percentiles', {})
        itl = metrics.get('inter_token_latency_ms', {}).get('successful', {}).get('percentiles', {})
        e2e = metrics.get('request_latency', {}).get('successful', {}).get('percentiles', {})

        if 'p95' in ttft and ttft['p95'] < best_ttft_p95:
            best_ttft_p95 = ttft['p95']
        if 'p99' in ttft and ttft['p99'] < best_ttft_p99:
            best_ttft_p99 = ttft['p99']
        if 'p95' in itl and itl['p95'] < best_itl_p95:
            best_itl_p95 = itl['p95']
        if 'p99' in itl and itl['p99'] < best_itl_p99:
            best_itl_p99 = itl['p99']
        if 'p95' in e2e and e2e['p95'] < best_e2e_p95:
            best_e2e_p95 = e2e['p95']
        if 'p99' in e2e and e2e['p99'] < best_e2e_p99:
            best_e2e_p99 = e2e['p99']

    aggregate = {
        'peak_throughput': peak_throughput,
        'peak_throughput_load': peak_throughput_load,
        'num_load_points': len(all_benchmarks),
    }

    # Add test duration if available
    if metadata.get('test_duration_seconds'):
        aggregate['test_duration_seconds'] = metadata['test_duration_seconds']

    # Calculate efficiency (tokens/sec/core) for managed mode
    if metadata.get('vllm_mode') == 'managed' and metadata.get('core_count', 0) > 0:
        aggregate['peak_efficiency'] = peak_throughput / metadata['core_count']

    # Add best latencies if they were found
    if best_ttft_p95 != float('inf'):
        aggregate['best_ttft_p95'] = best_ttft_p95
    if best_ttft_p99 != float('inf'):
        aggregate['best_ttft_p99'] = best_ttft_p99
    if best_itl_p95 != float('inf'):
        aggregate['best_itl_p95'] = best_itl_p95
    if best_itl_p99 != float('inf'):
        aggregate['best_itl_p99'] = best_itl_p99
    if best_e2e_p95 != float('inf'):
        aggregate['best_e2e_p95'] = best_e2e_p95
    if best_e2e_p99 != float('inf'):
        aggregate['best_e2e_p99'] = best_e2e_p99

    return aggregate


def extract_server_metrics(vllm_metrics_file: Path) -> Dict[str, float]:
    """Extract key server-side metrics from vLLM metrics JSON.

    Args:
        vllm_metrics_file: Path to vllm-metrics.json

    Returns:
        Dictionary of server metrics with 'server_' prefix
    """
    try:
        vllm_data = load_json_file(vllm_metrics_file)
        samples = vllm_data.get('samples', [])

        if not samples:
            return {}

        # Use the last sample (end of test) for cumulative metrics
        last_sample = samples[-1]
        metrics_data = last_sample.get('metrics', {})

        server_metrics = {}

        # Helper to extract single value from metric
        def get_value(metric_list):
            if metric_list and len(metric_list) > 0:
                return metric_list[0].get('value', 0)
            return 0

        # KV Cache utilization (%)
        kv_cache = metrics_data.get('vllm:kv_cache_usage_perc', [])
        if kv_cache:
            server_metrics['server_kv_cache_usage_pct'] = get_value(kv_cache)

        # Total tokens processed
        prompt_tokens = get_value(metrics_data.get('vllm:prompt_tokens_total', []))
        generation_tokens = get_value(metrics_data.get('vllm:generation_tokens_total', []))
        if prompt_tokens > 0:
            server_metrics['server_prompt_tokens_total'] = prompt_tokens
        if generation_tokens > 0:
            server_metrics['server_generation_tokens_total'] = generation_tokens
        if prompt_tokens > 0 and generation_tokens > 0:
            server_metrics['server_total_tokens'] = prompt_tokens + generation_tokens

        # Cache hit rates
        prefix_hits = get_value(metrics_data.get('vllm:prefix_cache_hits_total', []))
        prefix_queries = get_value(metrics_data.get('vllm:prefix_cache_queries_total', []))
        if prefix_queries > 0:
            server_metrics['server_prefix_cache_hit_rate'] = (prefix_hits / prefix_queries) * 100

        # Request success rate
        success_total = get_value(metrics_data.get('vllm:request_success_total', []))
        # Get total requests from histogram count
        e2e_count = get_value(metrics_data.get('vllm:e2e_request_latency_seconds_count', []))
        if e2e_count > 0:
            server_metrics['server_requests_total'] = e2e_count
            server_metrics['server_request_success_rate'] = (success_total / e2e_count) * 100

        # Average latencies from histogram sums and counts
        # TTFT
        ttft_sum = get_value(metrics_data.get('vllm:time_to_first_token_seconds_sum', []))
        ttft_count = get_value(metrics_data.get('vllm:time_to_first_token_seconds_count', []))
        if ttft_count > 0:
            server_metrics['server_ttft_avg_ms'] = (ttft_sum / ttft_count) * 1000

        # E2E latency
        e2e_sum = get_value(metrics_data.get('vllm:e2e_request_latency_seconds_sum', []))
        if e2e_count > 0:
            server_metrics['server_e2e_latency_avg_s'] = e2e_sum / e2e_count

        # Prefill time
        prefill_sum = get_value(metrics_data.get('vllm:request_prefill_time_seconds_sum', []))
        prefill_count = get_value(metrics_data.get('vllm:request_prefill_time_seconds_count', []))
        if prefill_count > 0:
            server_metrics['server_prefill_time_avg_ms'] = (prefill_sum / prefill_count) * 1000

        # Decode time
        decode_sum = get_value(metrics_data.get('vllm:request_decode_time_seconds_sum', []))
        decode_count = get_value(metrics_data.get('vllm:request_decode_time_seconds_count', []))
        if decode_count > 0:
            server_metrics['server_decode_time_avg_ms'] = (decode_sum / decode_count) * 1000

        # Queue time
        queue_sum = get_value(metrics_data.get('vllm:request_queue_time_seconds_sum', []))
        queue_count = get_value(metrics_data.get('vllm:request_queue_time_seconds_count', []))
        if queue_count > 0:
            server_metrics['server_queue_time_avg_ms'] = (queue_sum / queue_count) * 1000

        # CPU time
        cpu_seconds = get_value(metrics_data.get('process_cpu_seconds_total', []))
        if cpu_seconds > 0:
            server_metrics['server_cpu_seconds_total'] = cpu_seconds

        # Memory usage (convert to MB)
        resident_mem = get_value(metrics_data.get('process_resident_memory_bytes', []))
        if resident_mem > 0:
            server_metrics['server_memory_mb'] = resident_mem / (1024 * 1024)

        # Preemptions
        preemptions = get_value(metrics_data.get('vllm:num_preemptions_total', []))
        if preemptions > 0:
            server_metrics['server_num_preemptions'] = preemptions

        # Average tokens per request
        gen_tokens_sum = get_value(metrics_data.get('vllm:request_generation_tokens_sum', []))
        gen_tokens_count = get_value(metrics_data.get('vllm:request_generation_tokens_count', []))
        if gen_tokens_count > 0:
            server_metrics['server_avg_output_tokens_per_req'] = gen_tokens_sum / gen_tokens_count

        prompt_tokens_sum = get_value(metrics_data.get('vllm:request_prompt_tokens_sum', []))
        prompt_tokens_count = get_value(metrics_data.get('vllm:request_prompt_tokens_count', []))
        if prompt_tokens_count > 0:
            server_metrics['server_avg_prompt_tokens_per_req'] = prompt_tokens_sum / prompt_tokens_count

        return server_metrics

    except Exception as e:
        print(f"Warning: Could not parse vLLM server metrics: {e}", file=sys.stderr)
        return {}


def create_tags(metadata: Dict[str, Any]) -> Dict[str, str]:
    """Create tags for categorizing experiments."""
    tags = {
        'model_family': metadata.get('model', 'unknown').split('/')[0],
        'model_name': metadata.get('model', 'unknown').split('/')[-1],
        'workload_type': metadata.get('workload', 'unknown'),
        'vllm_mode': metadata.get('vllm_mode', 'managed'),
    }

    # Add custom test name as a tag if present
    if metadata.get('test_name'):
        tags['test_name'] = metadata['test_name']

    # Add platform tag for managed mode
    if metadata.get('platform'):
        tags['platform'] = metadata['platform']

    return tags


def log_to_mlflow(
    benchmarks_file: Path,
    metadata_file: Path,
    experiment_name: Optional[str] = None,
    run_name: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    log_per_load_point: bool = False,
) -> bool:
    """Log benchmark results to MLflow.

    Args:
        benchmarks_file: Path to benchmarks.json
        metadata_file: Path to test-metadata.json
        experiment_name: MLflow experiment name (default: "LLM-Performance-Benchmarks")
        run_name: MLflow run name (default: auto-generated from metadata)
        tracking_uri: MLflow tracking server URI (default: from env or local)
        log_per_load_point: If True, log metrics for each load point separately

    Returns:
        True if successful, False otherwise
    """
    try:
        # Load data
        benchmarks = load_json_file(benchmarks_file)
        metadata = load_json_file(metadata_file)

        # Set tracking URI
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)
        elif os.getenv('MLFLOW_TRACKING_URI'):
            mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URI'))
        else:
            # Default to local file-based tracking
            default_tracking_dir = Path.home() / 'mlruns'
            mlflow.set_tracking_uri(f"file://{default_tracking_dir}")

        # Set experiment name
        if not experiment_name:
            # Create hierarchical experiment name based on model and workload
            model_name = metadata.get('model', 'unknown').replace('/', '_')
            workload = metadata.get('workload', 'unknown')
            experiment_name = f"LLM-Benchmarks/{model_name}/{workload}"

        # Try to set experiment, restore if deleted
        try:
            experiment = mlflow.set_experiment(experiment_name)
        except mlflow.exceptions.MlflowException as e:
            if "deleted experiment" in str(e).lower():
                # Experiment was deleted, try to restore it
                print(f"⚠️  Experiment '{experiment_name}' was deleted. Restoring...")
                # Get experiment by name (even if deleted)
                from mlflow.tracking import MlflowClient
                client = MlflowClient()

                # Search for deleted experiment
                all_experiments = client.search_experiments(view_type=mlflow.entities.ViewType.DELETED_ONLY)
                deleted_exp = next((exp for exp in all_experiments if exp.name == experiment_name), None)

                if deleted_exp:
                    # Restore it
                    client.restore_experiment(deleted_exp.experiment_id)
                    print(f"✓ Restored experiment '{experiment_name}'")
                    experiment = mlflow.set_experiment(experiment_name)
                else:
                    # Can't find it, re-raise
                    raise
            else:
                # Different error, re-raise
                raise

        # Create run name if not provided
        if not run_name:
            test_run_id = metadata.get('test_run_id', 'unknown')
            platform = metadata.get('platform', 'unknown')
            cores = metadata.get('core_count', 0)
            run_name = f"{platform}_{cores}c_{test_run_id}"

            # Add test name prefix if present
            if metadata.get('test_name'):
                run_name = f"{metadata['test_name']}_{run_name}"

        # Check if this test_run_id was already logged (deduplication)
        existing_runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"params.test_run_id = '{metadata.get('test_run_id', 'unknown')}'",
            max_results=1
        )

        if not existing_runs.empty:
            existing_run_id = existing_runs.iloc[0]['run_id']
            existing_run_name = existing_runs.iloc[0]['tags.mlflow.runName']
            print(f"⚠️  Test already logged to MLflow")
            print(f"  Existing Run ID: {existing_run_id}")
            print(f"  Existing Run Name: {existing_run_name}")
            print(f"  Skipping to avoid duplicate...")
            return True  # Already logged, skip

        # Start MLflow run
        with mlflow.start_run(run_name=run_name) as run:
            try:
                # Log artifacts first (even if other steps fail, we want the logs)
                result_dir = benchmarks_file.parent

                # Log primary results
                mlflow.log_artifact(str(benchmarks_file), "results")
                mlflow.log_artifact(str(metadata_file), "results")

                # Log benchmarks CSV if it exists
                benchmarks_csv = result_dir / "benchmarks.csv"
                if benchmarks_csv.exists():
                    mlflow.log_artifact(str(benchmarks_csv), "results")

                # Log all log files
                guidellm_log = result_dir / "guidellm.log"
                if guidellm_log.exists():
                    mlflow.log_artifact(str(guidellm_log), "logs")

                metrics_collector_log = result_dir / "metrics-collector.log"
                if metrics_collector_log.exists():
                    mlflow.log_artifact(str(metrics_collector_log), "logs")

                # Log vLLM server metrics if they exist
                vllm_metrics = result_dir / "vllm-metrics.json"
                if vllm_metrics.exists():
                    mlflow.log_artifact(str(vllm_metrics), "server_metrics")

                # Log any vLLM server logs
                vllm_server_log = result_dir / "vllm-server.log"
                if vllm_server_log.exists():
                    mlflow.log_artifact(str(vllm_server_log), "logs")

                # Log parameters (including test_run_id for deduplication)
                params = extract_parameters(metadata, benchmarks)
                params['test_run_id'] = metadata.get('test_run_id', 'unknown')  # Add for dedup
                mlflow.log_params(params)

                # Log tags
                tags = create_tags(metadata)
                mlflow.set_tags(tags)

                # Log aggregate client-side metrics (from GuideLLM)
                aggregate_metrics = extract_aggregate_metrics(benchmarks, metadata)
                mlflow.log_metrics(aggregate_metrics)

                # Log server-side metrics (from vLLM) if available
                if vllm_metrics.exists():
                    server_metrics = extract_server_metrics(vllm_metrics)
                    if server_metrics:
                        mlflow.log_metrics(server_metrics)

                # Log per-load-point metrics if requested
                if log_per_load_point:
                    rates = benchmarks.get('args', {}).get('rate', [])
                    for i, bench in enumerate(benchmarks.get('benchmarks', [])):
                        rate = rates[i] if i < len(rates) else i
                        prefix = f"load_{rate:.2f}_"
                        load_metrics = extract_metrics_from_benchmark(bench, prefix)
                        mlflow.log_metrics(load_metrics, step=i)

                print(f"✓ Successfully logged experiment to MLflow")
                print(f"  Run ID: {run.info.run_id}")
                print(f"  Experiment: {experiment_name}")
                print(f"  Run Name: {run_name}")
                print(f"  Tracking URI: {mlflow.get_tracking_uri()}")

                return True

            except Exception as e:
                # Log error details to MLflow
                error_msg = str(e)
                mlflow.set_tag("error", error_msg)
                mlflow.set_tag("error_type", type(e).__name__)
                print(f"✗ Error during MLflow logging: {error_msg}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                # Re-raise to mark run as failed
                raise

    except FileNotFoundError as e:
        print(f"Error: File not found: {e.filename}", file=sys.stderr)
        return False
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error: Failed to log to MLflow: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Log GuideLLM benchmark results to MLflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s benchmarks.json test-metadata.json

  # With custom experiment name
  %(prog)s benchmarks.json test-metadata.json -e "My-LLM-Experiments"

  # With remote tracking server
  %(prog)s benchmarks.json test-metadata.json -u http://mlflow-server:5000

  # Log per-load-point metrics
  %(prog)s benchmarks.json test-metadata.json --log-per-load-point
"""
    )

    parser.add_argument(
        'benchmarks_file',
        type=Path,
        help='Path to benchmarks.json file'
    )
    parser.add_argument(
        'metadata_file',
        type=Path,
        help='Path to test-metadata.json file'
    )
    parser.add_argument(
        '-e', '--experiment-name',
        help='MLflow experiment name (default: auto-generated)'
    )
    parser.add_argument(
        '-r', '--run-name',
        help='MLflow run name (default: auto-generated)'
    )
    parser.add_argument(
        '-u', '--tracking-uri',
        help='MLflow tracking server URI (default: from MLFLOW_TRACKING_URI env or local)'
    )
    parser.add_argument(
        '--log-per-load-point',
        action='store_true',
        help='Log detailed metrics for each load point (creates more metrics)'
    )

    args = parser.parse_args()

    success = log_to_mlflow(
        args.benchmarks_file,
        args.metadata_file,
        experiment_name=args.experiment_name,
        run_name=args.run_name,
        tracking_uri=args.tracking_uri,
        log_per_load_point=args.log_per_load_point,
    )

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
