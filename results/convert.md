# CPU Benchmark Results Conversion Guide

This guide explains how to convert your CPU-based guidellm benchmark results to the format required by the [performance dashboard](https://github.com/openshift-psap/performance-dashboard).

## Quick Start

### 1. Setup

```bash
# From repository root
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Convert All Results

```bash
# Run batch conversion
python results/scripts/convert_batch.py
```

This creates **two separate CSV files**:
- `results/managed_cpu_benchmarks.csv` - Single-instance tests
- `results/external_cpu_benchmarks.csv` - External/multi-instance tests

### 3. Review and Share

```bash
# Preview the managed results (single-instance)
head results/managed_cpu_benchmarks.csv

# Preview the external results (variable instances)
head results/external_cpu_benchmarks.csv

# Check row counts
wc -l results/*.csv

# When done
deactivate
```
---

## Overview

The `convert_single.py` script is a CPU-specific adaptation of the dashboard's `import_manual_runs_json_v2.py` script. It processes guidellm v0.5.0+ JSON results from CPU-based inference runs.

### Output Files

Results are automatically separated into two CSV files based on test mode:

- **`managed_cpu_benchmarks.csv`**: Single-instance tests where the benchmark framework manages the vLLM server
- **`external_cpu_benchmarks.csv`**: Tests against external vLLM endpoints (may be single or multi-instance)

This separation allows the dashboard team to import single-instance results for direct GPU comparison, while keeping external/scaled results available as supplementary data.

## Key Differences from GPU Version

### What's Changed
- **Accelerator → CPU Type**: The `--accelerator` field now accepts CPU types (e.g., "Xeon", "EPYC")
- **Metadata Auto-Detection**: Can read from `test-metadata.json` to auto-populate fields
- **CPU-Specific Fields**: Added columns for:
  - `core_count`: Number of CPU cores used
  - `cpuset_cpus`: CPU affinity configuration
  - `cpuset_mems`: Memory node affinity
  - `omp_num_threads`: OpenMP thread count
  - `tpot_mean`: Mean time per output token
- **Test Configuration Fields**: Distinguish test types:
  - `vllm_mode`: external (remote server) vs managed (co-located)
  - `core_config_name`: specific configuration used
  - `config_type`: auto or manual configuration
- **Server-Side Metrics**: 21 metrics from vllm-metrics.json (resource usage, cache stats, server latencies)

### What's Preserved
- All performance metrics (throughput, latency percentiles, token counts)
- UUID tracking for individual benchmark runs
- CSV column structure for dashboard compatibility

## File Structure

```
results/
├── scripts/
│   ├── convert_single.py                 # Single result converter
│   └── convert_batch.py                  # Batch processor
├── llm/                                   # Your benchmark data
│   ├── RedHatAI__gemma-3-4b-it-quantized.w8a8/
│   ├── RedHatAI__Llama-3.1-8B-Instruct/
│   └── ...
├── all_cpu_benchmarks.csv                # Output CSV
└── convert.md                             # This file
```

## Usage

### Option 1: Batch Convert All Results (Recommended)

Process all your benchmark results at once:

```bash
# From repository root
python results/scripts/convert_batch.py
```

This will:
1. Find all `benchmarks.json` + `test-metadata.json` pairs in `results/llm/`
2. Convert each one using the CPU import script
3. Split results by vllm_mode:
   - Managed tests → `results/managed_cpu_benchmarks.csv`
   - External tests → `results/external_cpu_benchmarks.csv`

### Option 2: Convert Individual Results

For a single benchmark run:

```bash
python results/scripts/convert_single.py \
  results/llm/model-name/test-run/external-endpoint/benchmarks.json \
  --metadata-file results/llm/model-name/test-run/external-endpoint/test-metadata.json \
  --csv-file results/output.csv
```

The `--metadata-file` option auto-populates most fields. You can override any field:

```bash
python results/scripts/convert_single.py \
  results/llm/model-name/test-run/external-endpoint/benchmarks.json \
  --metadata-file results/llm/model-name/test-run/external-endpoint/test-metadata.json \
  --cpu-type "Xeon-Platinum-8480+" \
  --core-count 112 \
  --csv-file results/my_benchmarks.csv
```

### Option 3: Manual Specification (No Metadata File)

If you don't have a metadata file:

```bash
python results/scripts/convert_single.py \
  path/to/benchmarks.json \
  --model "RedHatAI/gemma-3-4b-it-quantized.w8a8" \
  --version "vLLM-0.18.0" \
  --cpu-type "Xeon" \
  --core-count 48 \
  --runtime-args "dtype=auto;kv_cache=auto;max_len=auto" \
  --image-tag "vllm:0.18.0+rhaiv.5" \
  --guidellm-version "v0.6.0" \
  --csv-file results/output.csv
```

## Command-Line Arguments

### Required (if no --metadata-file)
- `--model`: Model name (e.g., "RedHatAI/gemma-3-4b-it-quantized.w8a8")
- `--version`: Framework version (e.g., "vLLM-0.18.0")

### Optional (auto-detected from metadata or defaults)
- `--metadata-file`: Path to test-metadata.json (highly recommended)
- `--cpu-type`: CPU platform type (default: from metadata "platform" or "test_name")
- `--core-count`: Number of CPU cores used (default: from metadata)
- `--tensor-parallel`: Tensor parallelism size (if applicable)
- `--cpuset-cpus`: CPU affinity configuration
- `--cpuset-mems`: Memory node affinity
- `--omp-num-threads`: OpenMP thread count
- `--runtime-args`: Runtime configuration (default: auto-built from metadata)
- `--image-tag`: Container image tag (default: from metadata vllm_version)
- `--guidellm-version`: guidellm version (default: auto-detected)
- `--csv-file`: Output CSV path (default: "cpu_benchmarks.csv")

## Example Workflow

```bash
# 1. Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Run batch conversion
python results/scripts/convert_batch.py

# 3. Check the output
head results/all_cpu_benchmarks.csv
wc -l results/all_cpu_benchmarks.csv

# 4. Upload to the performance dashboard
# (Follow dashboard submission instructions)
```

## Output Format

The script generates a CSV with these columns (compatible with the dashboard):

**Core Identifiers:**
- run, accelerator (CPU type), model, version, uuid

**Configuration:**
- prompt toks, output toks, TP, runtime_args, image_tag, guidellm_version

**Concurrency:**
- measured concurrency, intended concurrency, measured rps

**Throughput:**
- output_tok/sec, total_tok/sec

**Token Counts:**
- prompt_token_count_mean, prompt_token_count_p99
- output_token_count_mean, output_token_count_p99

**Latency Metrics (all in milliseconds):**
- TTFT: ttft_median, ttft_mean, ttft_p1, ttft_p95, ttft_p99, ttft_p999
- TPOT: tpot_median, tpot_mean, tpot_p1, tpot_p95, tpot_p99, tpot_p999
- ITL: itl_median, itl_mean, itl_p1, itl_p95, itl_p99, itl_p999
- Request: request_latency_median, request_latency_min, request_latency_max

**Request Stats:**
- successful_requests, errored_requests
- guidellm_start_time_ms, guidellm_end_time_ms

**CPU-Specific:**
- core_count, cpuset_cpus, cpuset_mems, omp_num_threads, tpot_mean

**Test Configuration:**
- vllm_mode: `external` (remote server) or `managed` (co-located)
- core_config_name: e.g., `external-endpoint`, `32cores-numa1-tp1`
- config_type: `auto` or `manual`

**Server-Side Metrics** (from vllm-metrics.json):
- Resource usage: server_cpu_usage_rate, server_memory_mean/max_bytes, server_kv_cache_usage_mean/max
- Queue/Concurrency: server_requests_running_mean/max, server_requests_waiting_mean/max
- Cache performance: server_prefix_cache_hits/queries/hit_rate, server_num_preemptions
- Token counts: server_prompt_tokens_total, server_generation_tokens_total
- Server latencies (ms): server_ttft/tpot/e2e/queue/prefill/decode_time_mean_ms

**Note**: Client metrics (no prefix) include network latency; server metrics (`server_` prefix) are pure server-side measurements.

## Your Current Results Structure

```
results/llm/
├── RedHatAI__gemma-3-4b-it-quantized.w8a8/
│   └── chat_lite-Xeon-NO-SMT-20260427-111314/
│       └── external-endpoint/
│           ├── benchmarks.json          ← guidellm output
│           ├── test-metadata.json       ← CPU config metadata
│           └── vllm-metrics.json
├── RedHatAI__Llama-3.1-8B-Instruct/
└── ...
```

Each `external-endpoint/` directory with both JSON files will be processed.

## Troubleshooting

### "No benchmark results found"
- Ensure you're running from the repository root
- Check that `results/llm/` exists and contains subdirectories
- Verify each result has both `benchmarks.json` and `test-metadata.json`

### "JSONDecodeError" or "KeyError"
- Check that your JSON files are valid guidellm v0.5.0+ format
- Ensure metadata file contains expected fields (model, vllm_version, etc.)

### Missing or None values in CSV
- Some fields are optional and may be None/empty if not in metadata
- Check your test-metadata.json has all expected fields

## Contributing to the Dashboard

Once you've generated the CSVs:

1. Review both outputs for correctness
2. **Primary submission**: `managed_cpu_benchmarks.csv` - single-instance results for direct GPU comparison
3. **Supplementary data**: `external_cpu_benchmarks.csv` - external/multi-instance results showing scaling behavior
4. Follow the dashboard's submission guidelines
5. You may need to coordinate with dashboard maintainers for:
   - Adding CPU-specific column support
   - Updating visualization queries
   - Documenting CPU vs GPU result differences

## Scripts

- [`scripts/convert_single.py`](scripts/convert_single.py) - Single result converter (adapted from [import_manual_runs_json_v2.py](https://github.com/openshift-psap/performance-dashboard/blob/main/manual_runs/scripts/import_manual_runs_json_v2.py))
- [`scripts/convert_batch.py`](scripts/convert_batch.py) - Batch processor for all results
