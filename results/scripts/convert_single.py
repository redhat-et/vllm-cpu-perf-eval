"""Import Manual Run JSONs Script for CPU-based guidellm runs.

Script to process and import benchmark results from guidellm 0.5.x+ JSON files
into the performance dashboard data format, adapted for CPU-based inference runs.

Based on import_manual_runs_json_v2.py but modified to accommodate CPU-specific fields.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd


def load_test_metadata(metadata_path):
    """Load test metadata from test-metadata.json.

    Args:
        metadata_path: Path to the test-metadata.json file.

    Returns:
        dict: Test metadata including CPU configuration.
    """
    try:
        with open(metadata_path) as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Metadata file not found at {metadata_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Warning: Could not decode metadata JSON from {metadata_path}")
        return {}


def parse_vllm_metrics(vllm_metrics_path):
    """Parse vLLM server-side metrics from vllm-metrics.json.

    Args:
        vllm_metrics_path: Path to the vllm-metrics.json file.

    Returns:
        dict: Aggregated server-side metrics.
    """
    if not vllm_metrics_path or not Path(vllm_metrics_path).exists():
        print(f"Warning: vLLM metrics file not found at {vllm_metrics_path}")
        return {}

    try:
        with open(vllm_metrics_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not parse vLLM metrics from {vllm_metrics_path}: {e}")
        return {}

    samples = data.get("samples", [])
    if not samples:
        print("Warning: No samples found in vLLM metrics")
        return {}

    # Helper function to extract metric values across all samples
    def get_metric_values(metric_name, label_filter=None):
        """Extract all values for a given metric across samples."""
        values = []
        for sample in samples:
            metrics = sample.get("metrics", {})
            metric_data = metrics.get(metric_name, [])

            if isinstance(metric_data, list):
                for item in metric_data:
                    if label_filter is None or (
                        isinstance(item, dict) and
                        item.get("labels", {}) == label_filter
                    ):
                        values.append(item.get("value", 0))
            elif isinstance(metric_data, (int, float)):
                values.append(metric_data)

        return values

    # Helper to compute percentiles
    def compute_percentiles(values):
        """Compute statistics from a list of values."""
        if not values:
            return {}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        return {
            "mean": sum(values) / n,
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": sorted_vals[int(n * 0.50)],
            "p95": sorted_vals[int(n * 0.95)] if n > 1 else sorted_vals[0],
            "p99": sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[0],
        }

    # Extract and aggregate metrics
    result = {}

    # Resource usage metrics
    cpu_values = get_metric_values("process_cpu_seconds_total")
    if cpu_values:
        # CPU is cumulative, so compute rate (difference / time)
        if len(cpu_values) > 1:
            cpu_rate = (cpu_values[-1] - cpu_values[0]) / len(samples)
            result["server_cpu_usage_rate"] = cpu_rate
        else:
            result["server_cpu_usage_rate"] = 0

    mem_values = get_metric_values("process_resident_memory_bytes")
    if mem_values:
        mem_stats = compute_percentiles(mem_values)
        result["server_memory_mean_bytes"] = mem_stats.get("mean")
        result["server_memory_max_bytes"] = mem_stats.get("max")

    kv_cache_values = get_metric_values("vllm:kv_cache_usage_perc")
    if kv_cache_values:
        kv_stats = compute_percentiles(kv_cache_values)
        result["server_kv_cache_usage_mean"] = kv_stats.get("mean")
        result["server_kv_cache_usage_max"] = kv_stats.get("max")

    # Queue/Concurrency metrics
    running_values = get_metric_values("vllm:num_requests_running")
    if running_values:
        running_stats = compute_percentiles(running_values)
        result["server_requests_running_mean"] = running_stats.get("mean")
        result["server_requests_running_max"] = running_stats.get("max")

    waiting_values = get_metric_values("vllm:num_requests_waiting")
    if waiting_values:
        waiting_stats = compute_percentiles(waiting_values)
        result["server_requests_waiting_mean"] = waiting_stats.get("mean")
        result["server_requests_waiting_max"] = waiting_stats.get("max")

    # Cache performance - extract from last sample (cumulative counters)
    if samples:
        last_metrics = samples[-1].get("metrics", {})

        # Prefix cache hits/queries
        prefix_hits = last_metrics.get("vllm:prefix_cache_hits_total", [])
        prefix_queries = last_metrics.get("vllm:prefix_cache_queries_total", [])

        if prefix_hits and prefix_queries and isinstance(prefix_hits, list) and isinstance(prefix_queries, list):
            total_hits = sum(item.get("value", 0) for item in prefix_hits)
            total_queries = sum(item.get("value", 0) for item in prefix_queries)

            result["server_prefix_cache_hits"] = total_hits
            result["server_prefix_cache_queries"] = total_queries
            result["server_prefix_cache_hit_rate"] = (
                total_hits / total_queries if total_queries > 0 else 0
            )

        # Preemptions
        preemptions = last_metrics.get("vllm:num_preemptions_total", [])
        if preemptions and isinstance(preemptions, list):
            result["server_num_preemptions"] = sum(
                item.get("value", 0) for item in preemptions
            )

        # Token counts
        prompt_tokens = last_metrics.get("vllm:prompt_tokens_total", [])
        if prompt_tokens and isinstance(prompt_tokens, list):
            result["server_prompt_tokens_total"] = sum(
                item.get("value", 0) for item in prompt_tokens
            )

        generation_tokens = last_metrics.get("vllm:generation_tokens_total", [])
        if generation_tokens and isinstance(generation_tokens, list):
            result["server_generation_tokens_total"] = sum(
                item.get("value", 0) for item in generation_tokens
            )

    # Extract histogram metrics (converted from bucket/sum/count format)
    def extract_histogram_stats(base_name):
        """Extract summary stats from Prometheus histogram."""
        sum_metric = f"{base_name}_sum"
        count_metric = f"{base_name}_count"

        # Get final cumulative values from last sample
        if not samples:
            return {}

        last_metrics = samples[-1].get("metrics", {})
        sum_data = last_metrics.get(sum_metric, [])
        count_data = last_metrics.get(count_metric, [])

        total_sum = 0
        total_count = 0

        if isinstance(sum_data, list):
            total_sum = sum(item.get("value", 0) for item in sum_data)
        elif isinstance(sum_data, (int, float)):
            total_sum = sum_data

        if isinstance(count_data, list):
            total_count = sum(item.get("value", 0) for item in count_data)
        elif isinstance(count_data, (int, float)):
            total_count = count_data

        if total_count > 0:
            return {
                "mean": total_sum / total_count,
                "total": total_sum,
                "count": total_count,
            }
        return {}

    # Server-side latency metrics (in seconds, convert to ms)
    ttft_stats = extract_histogram_stats("vllm:time_to_first_token_seconds")
    if ttft_stats:
        result["server_ttft_mean_ms"] = ttft_stats["mean"] * 1000

    tpot_stats = extract_histogram_stats("vllm:request_time_per_output_token_seconds")
    if tpot_stats:
        result["server_tpot_mean_ms"] = tpot_stats["mean"] * 1000

    e2e_stats = extract_histogram_stats("vllm:e2e_request_latency_seconds")
    if e2e_stats:
        result["server_e2e_latency_mean_ms"] = e2e_stats["mean"] * 1000

    queue_stats = extract_histogram_stats("vllm:request_queue_time_seconds")
    if queue_stats:
        result["server_queue_time_mean_ms"] = queue_stats["mean"] * 1000

    prefill_stats = extract_histogram_stats("vllm:request_prefill_time_seconds")
    if prefill_stats:
        result["server_prefill_time_mean_ms"] = prefill_stats["mean"] * 1000

    decode_stats = extract_histogram_stats("vllm:request_decode_time_seconds")
    if decode_stats:
        result["server_decode_time_mean_ms"] = decode_stats["mean"] * 1000

    return result


def process_benchmark_section(
    benchmark,
    cpu_type,
    model_name,
    version,
    core_count,
    runtime_args,
    global_data_config,
    image_tag,
    guidellm_version,
    guidellm_start_time_ms,
    guidellm_end_time_ms,
    cpuset_cpus=None,
    cpuset_mems=None,
    omp_num_threads=None,
    tensor_parallel=None,
    vllm_metrics=None,
    vllm_mode=None,
    core_config_name=None,
    config_type=None,
):
    """Process a single benchmark section and extract performance metrics.

    Args:
        benchmark: Benchmark data from JSON (guidellm 0.5.x format).
        cpu_type: CPU platform/type (e.g., Xeon, EPYC).
        model_name: Name of the AI model.
        version: Version of the inference server.
        core_count: Number of CPU cores used.
        runtime_args: Runtime configuration arguments.
        global_data_config: Global data configuration from top-level args.
        image_tag: Container image tag used for the run.
        guidellm_version: Version of guidellm used to run the benchmark.
        guidellm_start_time_ms: Aggregated start time in milliseconds.
        guidellm_end_time_ms: Aggregated end time in milliseconds.
        cpuset_cpus: CPU affinity configuration (optional).
        cpuset_mems: Memory node affinity (optional).
        omp_num_threads: OpenMP thread count (optional).
        tensor_parallel: Tensor parallelism size (optional, for CPU inference).
        vllm_metrics: Server-side metrics (optional).
        vllm_mode: vLLM mode - external or managed (optional).
        core_config_name: Core configuration name (optional).
        config_type: Configuration type - auto or manual (optional).

    Returns:
        dict: Processed benchmark metrics.
    """
    # Create run identifier
    parallelism_tag = tensor_parallel if tensor_parallel else core_count
    full_model_name = f"{cpu_type}-{model_name}-{parallelism_tag}"

    config = benchmark.get("config", {})
    uuid = config.get("run_id")

    # Get strategy info (streams/concurrency)
    strategy = config.get("strategy", {})
    intended_concurrency = strategy.get("streams") or strategy.get("max_concurrency", 0)

    # Parse data config for prompt/output tokens
    config_prompt_tokens = 0
    config_output_tokens = 0
    try:
        if global_data_config and len(global_data_config) > 0:
            data_str = global_data_config[0]
            # Try JSON format first
            try:
                request_config = json.loads(data_str)
                config_prompt_tokens = request_config.get("prompt_tokens", 0)
                config_output_tokens = request_config.get("output_tokens", 0)
            except json.JSONDecodeError:
                # Try key=value format: "prompt_tokens=1000,output_tokens=1000"
                for item in data_str.split(","):
                    if "=" in item:
                        key, value = item.strip().split("=", 1)
                        if key == "prompt_tokens":
                            config_prompt_tokens = int(value)
                        elif key == "output_tokens":
                            config_output_tokens = int(value)
    except (KeyError, TypeError, ValueError):
        config_prompt_tokens = 0
        config_output_tokens = 0

    # Get request stats from scheduler_metrics
    scheduler_metrics = benchmark.get("scheduler_metrics", {})
    requests_made = scheduler_metrics.get("requests_made", {})
    successful_reqs = requests_made.get("successful", 0)
    errored_reqs = requests_made.get("errored", 0)

    # Get metrics
    metrics = benchmark.get("metrics", {})

    # Output tokens per second
    output_tps_metrics = metrics.get("output_tokens_per_second", {}).get("total", {})
    output_tok_per_sec = output_tps_metrics.get("mean", 0)

    # Total tokens per second
    total_tps_metrics = metrics.get("tokens_per_second", {}).get("total", {})
    total_tok_per_sec = total_tps_metrics.get("mean", 0)

    # Token counts
    prompt_tok_metrics = metrics.get("prompt_token_count", {}).get("successful", {})
    output_tok_metrics = metrics.get("output_token_count", {}).get("successful", {})

    # Latency metrics
    ttft_metrics = metrics.get("time_to_first_token_ms", {}).get("successful", {})
    tpot_metrics = metrics.get("time_per_output_token_ms", {}).get("successful", {})
    itl_metrics = metrics.get("inter_token_latency_ms", {}).get("successful", {})
    request_latency_metrics = metrics.get("request_latency", {}).get("successful", {})

    # Request concurrency
    request_concurrency = metrics.get("request_concurrency", {}).get("successful", {})
    measured_concurrency = request_concurrency.get("mean", intended_concurrency)

    # Requests per second
    rps_metrics = metrics.get("requests_per_second", {}).get("successful", {})
    measured_rps = rps_metrics.get("mean", 0)

    # Helper to get percentiles
    def get_percentile(metrics_dict, key):
        percentiles = metrics_dict.get("percentiles", {})
        return percentiles.get(key)

    row = {
        "run": full_model_name,
        "accelerator": cpu_type,  # Keep column name for compatibility, but use CPU type
        "model": model_name,
        "version": version,
        "prompt toks": config_prompt_tokens,
        "output toks": config_output_tokens,
        "TP": tensor_parallel,  # Tensor parallelism (or None for CPU)
        "measured concurrency": measured_concurrency,
        "intended concurrency": intended_concurrency,
        "measured rps": measured_rps,
        "output_tok/sec": output_tok_per_sec,
        "total_tok/sec": total_tok_per_sec,
        "prompt_token_count_mean": prompt_tok_metrics.get("mean"),
        "prompt_token_count_p99": get_percentile(prompt_tok_metrics, "p99"),
        "output_token_count_mean": output_tok_metrics.get("mean"),
        "output_token_count_p99": get_percentile(output_tok_metrics, "p99"),
        "ttft_median": ttft_metrics.get("median"),
        "ttft_p95": get_percentile(ttft_metrics, "p95"),
        "ttft_p1": get_percentile(ttft_metrics, "p01"),
        "ttft_p999": get_percentile(ttft_metrics, "p999"),
        "tpot_median": tpot_metrics.get("median"),
        "tpot_p95": get_percentile(tpot_metrics, "p95"),
        "tpot_p99": get_percentile(tpot_metrics, "p99"),
        "tpot_p999": get_percentile(tpot_metrics, "p999"),
        "tpot_p1": get_percentile(tpot_metrics, "p01"),
        "itl_median": itl_metrics.get("median"),
        "itl_p95": get_percentile(itl_metrics, "p95"),
        "itl_p999": get_percentile(itl_metrics, "p999"),
        "itl_p1": get_percentile(itl_metrics, "p01"),
        "request_latency_median": request_latency_metrics.get("median"),
        "request_latency_min": request_latency_metrics.get("min"),
        "request_latency_max": request_latency_metrics.get("max"),
        "successful_requests": successful_reqs,
        "errored_requests": errored_reqs,
        "uuid": uuid,
        "ttft_mean": ttft_metrics.get("mean"),
        "ttft_p99": get_percentile(ttft_metrics, "p99"),
        "itl_mean": itl_metrics.get("mean"),
        "itl_p99": get_percentile(itl_metrics, "p99"),
        "runtime_args": runtime_args,
        "guidellm_start_time_ms": guidellm_start_time_ms,
        "guidellm_end_time_ms": guidellm_end_time_ms,
        "image_tag": image_tag,
        "guidellm_version": guidellm_version,
        "DP": None,  # Not applicable for CPU runs
        # CPU-specific fields
        "core_count": core_count,
        "cpuset_cpus": cpuset_cpus,
        "cpuset_mems": cpuset_mems,
        "omp_num_threads": omp_num_threads,
        "tpot_mean": tpot_metrics.get("mean"),
        # Test configuration fields
        "vllm_mode": vllm_mode,
        "core_config_name": core_config_name,
        "config_type": config_type,
    }

    # Add server-side metrics if available
    if vllm_metrics:
        row.update({
            # Resource usage
            "server_cpu_usage_rate": vllm_metrics.get("server_cpu_usage_rate"),
            "server_memory_mean_bytes": vllm_metrics.get("server_memory_mean_bytes"),
            "server_memory_max_bytes": vllm_metrics.get("server_memory_max_bytes"),
            "server_kv_cache_usage_mean": vllm_metrics.get("server_kv_cache_usage_mean"),
            "server_kv_cache_usage_max": vllm_metrics.get("server_kv_cache_usage_max"),
            # Queue/Concurrency
            "server_requests_running_mean": vllm_metrics.get("server_requests_running_mean"),
            "server_requests_running_max": vllm_metrics.get("server_requests_running_max"),
            "server_requests_waiting_mean": vllm_metrics.get("server_requests_waiting_mean"),
            "server_requests_waiting_max": vllm_metrics.get("server_requests_waiting_max"),
            # Cache performance
            "server_prefix_cache_hits": vllm_metrics.get("server_prefix_cache_hits"),
            "server_prefix_cache_queries": vllm_metrics.get("server_prefix_cache_queries"),
            "server_prefix_cache_hit_rate": vllm_metrics.get("server_prefix_cache_hit_rate"),
            "server_num_preemptions": vllm_metrics.get("server_num_preemptions"),
            # Token counts
            "server_prompt_tokens_total": vllm_metrics.get("server_prompt_tokens_total"),
            "server_generation_tokens_total": vllm_metrics.get("server_generation_tokens_total"),
            # Server-side latencies (ms)
            "server_ttft_mean_ms": vllm_metrics.get("server_ttft_mean_ms"),
            "server_tpot_mean_ms": vllm_metrics.get("server_tpot_mean_ms"),
            "server_e2e_latency_mean_ms": vllm_metrics.get("server_e2e_latency_mean_ms"),
            "server_queue_time_mean_ms": vllm_metrics.get("server_queue_time_mean_ms"),
            "server_prefill_time_mean_ms": vllm_metrics.get("server_prefill_time_mean_ms"),
            "server_decode_time_mean_ms": vllm_metrics.get("server_decode_time_mean_ms"),
        })

    return row


def parse_guidellm_json(
    json_path,
    cpu_type,
    model_name,
    version,
    core_count,
    runtime_args,
    image_tag,
    guidellm_version,
    metadata_path=None,
    cpuset_cpus=None,
    cpuset_mems=None,
    omp_num_threads=None,
    tensor_parallel=None,
    vllm_metrics_path=None,
):
    """Parse guidellm 0.5.x+ JSON benchmark results for CPU runs.

    Args:
        json_path: Path to the benchmarks JSON file.
        cpu_type: CPU platform/type.
        model_name: Name of the AI model.
        version: Version of the inference server.
        core_count: Number of CPU cores used.
        runtime_args: Runtime configuration arguments.
        image_tag: Container image tag used for the run.
        guidellm_version: Version of guidellm used to run the benchmark.
        metadata_path: Optional path to test-metadata.json.
        cpuset_cpus: CPU affinity configuration.
        cpuset_mems: Memory node affinity.
        omp_num_threads: OpenMP thread count.
        tensor_parallel: Tensor parallelism size.
        vllm_metrics_path: Optional path to vllm-metrics.json for server-side metrics.

    Returns:
        DataFrame: Processed benchmark results.
    """
    # Load metadata if provided
    metadata = {}
    vllm_mode = None
    core_config_name = None
    config_type = None

    if metadata_path:
        metadata = load_test_metadata(metadata_path)
        # Override with metadata values if not provided as arguments
        if not cpu_type and metadata.get("platform"):
            cpu_type = metadata["platform"]
        if not core_count and metadata.get("core_count"):
            core_count = metadata["core_count"]
        if not cpuset_cpus and metadata.get("cpuset_cpus"):
            cpuset_cpus = metadata["cpuset_cpus"]
        if not cpuset_mems and metadata.get("cpuset_mems"):
            cpuset_mems = metadata["cpuset_mems"]
        if not omp_num_threads and metadata.get("omp_num_threads"):
            omp_num_threads = metadata["omp_num_threads"]
        if not tensor_parallel and metadata.get("tensor_parallel"):
            tensor_parallel = metadata["tensor_parallel"]
        if not image_tag and metadata.get("vllm_version"):
            image_tag = f"vllm:{metadata['vllm_version']}"
        if not model_name and metadata.get("model"):
            model_name = metadata["model"]

        # Extract test configuration fields
        vllm_mode = metadata.get("vllm_mode")
        core_config_name = metadata.get("core_config_name")
        config_type = metadata.get("config_type")

    try:
        with open(json_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_path}")
        return None

    # Check guidellm version
    json_metadata = data.get("metadata", {})
    detected_guidellm_version = json_metadata.get("guidellm_version", guidellm_version)
    print(f"Detected guidellm version: {detected_guidellm_version}")

    all_run_data = []

    if not data.get("benchmarks"):
        print("Error: JSON file does not contain a 'benchmarks' key.")
        return None

    benchmarks = data["benchmarks"]

    # Get global data config (prompt_tokens, output_tokens)
    global_args = data.get("args", {})
    global_data_config = global_args.get("data", [])

    # Extract aggregated guidellm start and end times from scheduler_metrics
    start_times = []
    end_times = []
    for benchmark in benchmarks:
        scheduler_metrics = benchmark.get("scheduler_metrics", {})
        if "start_time" in scheduler_metrics:
            start_times.append(scheduler_metrics["start_time"])
        if "end_time" in scheduler_metrics:
            end_times.append(scheduler_metrics["end_time"])

    # Get min start_time and max end_time, convert to milliseconds
    guidellm_start_time_ms = int(min(start_times) * 1000) if start_times else ""
    guidellm_end_time_ms = int(max(end_times) * 1000) if end_times else ""

    # Parse server-side metrics if available
    vllm_metrics = None
    if vllm_metrics_path:
        print(f"Loading server-side metrics from {vllm_metrics_path}...")
        vllm_metrics = parse_vllm_metrics(vllm_metrics_path)
        if vllm_metrics:
            print(f"  Loaded {len(vllm_metrics)} server-side metric(s)")

    print(f"Processing {len(benchmarks)} benchmark sections...")

    for i, benchmark in enumerate(benchmarks):
        row_data = process_benchmark_section(
            benchmark,
            cpu_type,
            model_name,
            version,
            core_count,
            runtime_args,
            global_data_config,
            image_tag,
            detected_guidellm_version,
            guidellm_start_time_ms,
            guidellm_end_time_ms,
            cpuset_cpus=cpuset_cpus,
            cpuset_mems=cpuset_mems,
            omp_num_threads=omp_num_threads,
            tensor_parallel=tensor_parallel,
            vllm_metrics=vllm_metrics,
            vllm_mode=vllm_mode,
            core_config_name=core_config_name,
            config_type=config_type,
        )
        if row_data:
            all_run_data.append(row_data)
            streams = (
                benchmark.get("config", {}).get("strategy", {}).get("streams", "?")
            )
            print(
                f"  Processed benchmark {i + 1}/{len(benchmarks)} (streams={streams})"
            )

    if all_run_data:
        return pd.DataFrame(all_run_data)
    else:
        print("No valid data extracted from benchmark sections.")
        return None


def main():
    """Main function to process benchmark JSON files for CPU runs.

    Processes command line arguments and imports benchmark results
    from JSON files into the consolidated CSV format.
    """
    parser = argparse.ArgumentParser(
        description="Import guidellm 0.5.x+ JSON results (CPU runs) into the consolidated benchmark CSV.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "json_file", help="Path to the guidellm benchmarks JSON output file to import"
    )
    parser.add_argument(
        "--metadata-file",
        help="Path to test-metadata.json (will auto-populate many fields)",
    )
    parser.add_argument(
        "--vllm-metrics-file",
        help="Path to vllm-metrics.json (adds server-side performance metrics)",
    )
    parser.add_argument(
        "--model",
        help="Model name (e.g., 'RedHatAI/gemma-3-4b-it-quantized.w8a8'). "
             "Can be auto-detected from metadata file.",
    )
    parser.add_argument(
        "--version",
        help="Version/framework identifier (e.g., 'vLLM-0.18.0'). "
             "Can be auto-detected from metadata file.",
    )
    parser.add_argument(
        "--cpu-type",
        help="CPU platform/type (e.g., 'Xeon', 'EPYC'). "
             "Can be auto-detected from metadata file.",
    )
    parser.add_argument(
        "--core-count",
        type=int,
        help="Number of CPU cores used. Can be auto-detected from metadata file.",
    )
    parser.add_argument(
        "--tensor-parallel",
        type=int,
        help="Tensor parallelism size (if applicable for CPU inference)",
    )
    parser.add_argument(
        "--cpuset-cpus",
        help="CPU affinity configuration (e.g., '0-15')",
    )
    parser.add_argument(
        "--cpuset-mems",
        help="Memory node affinity (e.g., '0')",
    )
    parser.add_argument(
        "--omp-num-threads",
        type=int,
        help="OpenMP thread count",
    )
    parser.add_argument(
        "--runtime-args",
        help="Runtime arguments used for the inference server. "
             "Can be auto-detected from metadata file.",
    )
    parser.add_argument(
        "--image-tag",
        help="Container image tag used for the run. "
             "Can be auto-detected from metadata file.",
    )
    parser.add_argument(
        "--guidellm-version",
        help="Version of guidellm used to run the benchmark. "
             "Can be auto-detected from JSON or metadata file.",
    )
    parser.add_argument(
        "--csv-file",
        default="cpu_benchmarks.csv",
        help="Path to the output CSV file (default: cpu_benchmarks.csv)",
    )
    args = parser.parse_args()

    # Load metadata if provided
    metadata = {}
    if args.metadata_file:
        metadata = load_test_metadata(args.metadata_file)

    # Determine values (priority: CLI args > metadata file > defaults)
    # For CPU type, prefer test_name over platform if platform is "unknown"
    cpu_type = args.cpu_type
    if not cpu_type:
        platform = metadata.get("platform", "")
        if platform and platform != "unknown":
            cpu_type = platform
        else:
            cpu_type = metadata.get("test_name", "unknown")

    model_name = args.model or metadata.get("model")
    core_count = args.core_count if args.core_count is not None else metadata.get("core_count", 0)
    cpuset_cpus = args.cpuset_cpus or metadata.get("cpuset_cpus")
    cpuset_mems = args.cpuset_mems or metadata.get("cpuset_mems")
    omp_num_threads = args.omp_num_threads or metadata.get("omp_num_threads")
    tensor_parallel = args.tensor_parallel or metadata.get("tensor_parallel")

    # Build runtime args from metadata if not provided
    runtime_args = args.runtime_args
    if not runtime_args and metadata:
        runtime_parts = []
        if metadata.get("vllm_dtype"):
            runtime_parts.append(f"dtype={metadata['vllm_dtype']}")
        if metadata.get("vllm_kv_cache_size"):
            runtime_parts.append(f"kv_cache={metadata['vllm_kv_cache_size']}")
        if metadata.get("vllm_max_model_len"):
            runtime_parts.append(f"max_len={metadata['vllm_max_model_len']}")
        if tensor_parallel:
            runtime_parts.append(f"tp={tensor_parallel}")
        runtime_args = ";".join(runtime_parts) if runtime_parts else "default"

    version = args.version or (f"vLLM-{metadata.get('vllm_version')}" if metadata.get("vllm_version") else None)
    image_tag = args.image_tag or (f"vllm:{metadata.get('vllm_version')}" if metadata.get("vllm_version") else None)
    guidellm_version = args.guidellm_version or metadata.get("guidellm_version", "unknown")

    # Validate required fields
    if not model_name:
        parser.error("--model is required (or provide --metadata-file with model field)")
    if not version:
        parser.error("--version is required (or provide --metadata-file with vllm_version field)")

    print(f"Processing {args.json_file}...")
    print(f"  CPU Type: {cpu_type}")
    print(f"  Model: {model_name}")
    print(f"  Core Count: {core_count}")
    if tensor_parallel:
        print(f"  Tensor Parallel: {tensor_parallel}")

    new_data_df = parse_guidellm_json(
        args.json_file,
        cpu_type,
        model_name,
        version,
        core_count,
        runtime_args,
        image_tag,
        guidellm_version,
        metadata_path=args.metadata_file,
        cpuset_cpus=cpuset_cpus,
        cpuset_mems=cpuset_mems,
        omp_num_threads=omp_num_threads,
        tensor_parallel=tensor_parallel,
        vllm_metrics_path=args.vllm_metrics_file,
    )

    if new_data_df is not None and not new_data_df.empty:
        if os.path.exists(args.csv_file):
            print(f"Appending {len(new_data_df)} new rows to {args.csv_file}...")
            existing_df = pd.read_csv(args.csv_file)
            combined_df = pd.concat([existing_df, new_data_df], ignore_index=True)
        else:
            print(
                f"Creating new CSV file at {args.csv_file} with {len(new_data_df)} rows..."
            )
            combined_df = new_data_df

        # Define fieldnames (extended with CPU-specific fields)
        fieldnames = [
            "run",
            "accelerator",  # CPU type in our case
            "model",
            "version",
            "prompt toks",
            "output toks",
            "TP",
            "measured concurrency",
            "intended concurrency",
            "measured rps",
            "output_tok/sec",
            "total_tok/sec",
            "prompt_token_count_mean",
            "prompt_token_count_p99",
            "output_token_count_mean",
            "output_token_count_p99",
            "ttft_median",
            "ttft_p95",
            "ttft_p1",
            "ttft_p999",
            "tpot_median",
            "tpot_p95",
            "tpot_p99",
            "tpot_p999",
            "tpot_p1",
            "itl_median",
            "itl_p95",
            "itl_p999",
            "itl_p1",
            "request_latency_median",
            "request_latency_min",
            "request_latency_max",
            "successful_requests",
            "errored_requests",
            "uuid",
            "ttft_mean",
            "ttft_p99",
            "itl_mean",
            "itl_p99",
            "runtime_args",
            "guidellm_start_time_ms",
            "guidellm_end_time_ms",
            "image_tag",
            "guidellm_version",
            "DP",
            # CPU-specific additions
            "core_count",
            "cpuset_cpus",
            "cpuset_mems",
            "omp_num_threads",
            "tpot_mean",
            # Test configuration
            "vllm_mode",
            "core_config_name",
            "config_type",
            # Server-side metrics (from vllm-metrics.json)
            "server_cpu_usage_rate",
            "server_memory_mean_bytes",
            "server_memory_max_bytes",
            "server_kv_cache_usage_mean",
            "server_kv_cache_usage_max",
            "server_requests_running_mean",
            "server_requests_running_max",
            "server_requests_waiting_mean",
            "server_requests_waiting_max",
            "server_prefix_cache_hits",
            "server_prefix_cache_queries",
            "server_prefix_cache_hit_rate",
            "server_num_preemptions",
            "server_prompt_tokens_total",
            "server_generation_tokens_total",
            "server_ttft_mean_ms",
            "server_tpot_mean_ms",
            "server_e2e_latency_mean_ms",
            "server_queue_time_mean_ms",
            "server_prefill_time_mean_ms",
            "server_decode_time_mean_ms",
        ]

        for col in fieldnames:
            if col not in combined_df.columns:
                combined_df[col] = None

        combined_df = combined_df[fieldnames]
        combined_df.to_csv(args.csv_file, index=False)
        print(f"Successfully saved to {args.csv_file}")
    else:
        print(
            "No valid benchmark data was loaded. Exiting without creating a CSV file."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
