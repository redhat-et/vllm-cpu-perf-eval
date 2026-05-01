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
# Run batch conversion (processes all 47 benchmark results)
python results/scripts/batch_convert_results.py
```

**✅ Conversion Summary:**
- **417 rows** generated (416 benchmark data points + 1 header)
- **50 columns** (45 standard metrics + 5 CPU-specific fields)
- **100% success rate** (47/47 results converted)
- **Output file**: `results/all_cpu_benchmarks.csv`

### 3. Review and Share

```bash
# Preview the output
head results/all_cpu_benchmarks.csv

# Check row count
wc -l results/all_cpu_benchmarks.csv

# When done
deactivate
```

Now you can share `results/all_cpu_benchmarks.csv` with the performance dashboard team!

---

## Overview

The `import_manual_runs_json_cpu.py` script is a CPU-specific adaptation of the dashboard's `import_manual_runs_json_v2.py` script. It processes guidellm v0.5.0+ JSON results from CPU-based inference runs.

## Key Differences from GPU Version

### What's Changed:
- **Accelerator → CPU Type**: The `--accelerator` field now accepts CPU types (e.g., "Xeon", "EPYC")
- **Metadata Auto-Detection**: Can read from `test-metadata.json` to auto-populate fields
- **CPU-Specific Fields**: Added columns for:
  - `core_count`: Number of CPU cores used
  - `cpuset_cpus`: CPU affinity configuration
  - `cpuset_mems`: Memory node affinity
  - `omp_num_threads`: OpenMP thread count
  - `tpot_mean`: Mean time per output token

### What's Preserved:
- All performance metrics (throughput, latency percentiles, token counts)
- UUID tracking for individual benchmark runs
- CSV column structure for dashboard compatibility

## File Structure

```
results/
├── scripts/
│   ├── import_manual_runs_json_cpu.py    # CPU-specific converter
│   └── batch_convert_results.py          # Batch processor
├── llm/                                   # Your benchmark data
│   ├── RedHatAI__gemma-3-4b-it-quantized.w8a8/
│   ├── RedHatAI__Llama-3.1-8B-Instruct/
│   └── ...
├── all_cpu_benchmarks.csv                # Output CSV
└── README-cpu-results-psap-conversion.md # This file
```

## Usage

### Option 1: Batch Convert All Results (Recommended)

Process all your benchmark results at once:

```bash
# From repository root
python results/scripts/batch_convert_results.py
```

This will:
1. Find all `benchmarks.json` + `test-metadata.json` pairs in `results/llm/`
2. Convert each one using the CPU import script
3. Append all results to `results/all_cpu_benchmarks.csv`

### Option 2: Convert Individual Results

For a single benchmark run:

```bash
python results/scripts/import_manual_runs_json_cpu.py \
  results/llm/model-name/test-run/external-endpoint/benchmarks.json \
  --metadata-file results/llm/model-name/test-run/external-endpoint/test-metadata.json \
  --csv-file results/output.csv
```

The `--metadata-file` option auto-populates most fields. You can override any field:

```bash
python results/scripts/import_manual_runs_json_cpu.py \
  results/llm/model-name/test-run/external-endpoint/benchmarks.json \
  --metadata-file results/llm/model-name/test-run/external-endpoint/test-metadata.json \
  --cpu-type "Xeon-Platinum-8480+" \
  --core-count 112 \
  --csv-file results/my_benchmarks.csv
```

### Option 3: Manual Specification (No Metadata File)

If you don't have a metadata file:

```bash
python results/scripts/import_manual_runs_json_cpu.py \
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

### Required (if no --metadata-file):
- `--model`: Model name (e.g., "RedHatAI/gemma-3-4b-it-quantized.w8a8")
- `--version`: Framework version (e.g., "vLLM-0.18.0")

### Optional (auto-detected from metadata or defaults):
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
python results/scripts/batch_convert_results.py

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
- core_count, cpuset_cpus, cpuset_mems, omp_num_threads

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

Once you've generated the CSV:

1. Review the output for correctness
2. Follow the dashboard's submission guidelines
3. You may need to coordinate with dashboard maintainers for:
   - Adding CPU-specific column support
   - Updating visualization queries
   - Documenting CPU vs GPU result differences

## Scripts

- [`scripts/import_manual_runs_json_cpu.py`](scripts/import_manual_runs_json_cpu.py) - Single result converter (adapted from [import_manual_runs_json_v2.py](https://github.com/openshift-psap/performance-dashboard/blob/main/manual_runs/scripts/import_manual_runs_json_v2.py))
- [`scripts/batch_convert_results.py`](scripts/batch_convert_results.py) - Batch processor for all results
