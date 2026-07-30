# Offline Batch Testing Methodology

## Overview

Offline batch testing measures vLLM throughput for bulk processing workloads
using the native Python API (`vllm bench throughput`), bypassing the HTTP
server entirely. This eliminates network and scheduling overhead, isolating
raw inference performance.

> **Tool:** `vllm bench throughput` (direct Python API via Podman container)
>
> **CLI:** `./cpueval run --suite offline-batch` (recommended)
>
> **Playbook:** `llm-benchmark-offline-batch.yml`
>
> **Test Suite:** `run-offline-batch-suite.sh`

### When to Use Offline Batch Testing

| Criteria | Offline Batch | Online Server (GuideLLM) |
|----------|--------------|--------------------------|
| **Mode** | Direct Python API | HTTP requests to server |
| **Primary Metric** | Total batch time, throughput | Per-request latency (P95, P99) |
| **Use Case** | Bulk processing, ETL, dataset generation | Real-time serving, user requests |
| **Overhead** | Minimal (direct API) | HTTP + queue management |
| **Concurrency** | Internal batching | External concurrent requests |

## Test Architecture

```text
+---------------------------------------------+
|           Device Under Test                  |
|  vllm bench throughput (direct Python API)   |
|  Podman container with --cpuset-cpus         |
|  No server required                          |
+---------------------------------------------+
```

Unlike online serving tests which require a separate load generator node,
offline batch tests run entirely on the DUT. The `--cpuset-cpus` flag
controls which cores are available to vLLM.

## Core Scaling as Primary Tuning Axis

All offline batch tests sweep across core counts to identify the optimal
allocation for each model/workload combination. More cores does not always
yield better throughput — models and workloads saturate at different points.

**Standard core counts tested:** 8, 16, 24, 32

This sweep answers a key production question: *how many cores should I
allocate for this batch job?*

### Expected Patterns

- **Small models** (1B) often saturate at 16-32 cores
- **Large quantized models** (8B) can benefit from 32-64 cores
- **Short output tasks** (classification, entity extraction) saturate earlier
  than long output tasks (translation, code generation)
- **Diminishing returns** above the saturation point waste resources that
  could run a second batch job in parallel

## Test Scenarios

### Use Case Oriented Tests

Real-world scenarios that exercise different model capabilities. Each
use case is tested across the full range of core counts.

| Use Case | Dataset | Prompts | Notes |
|----------|---------|---------|-------|
| Summarization | sharegpt | 1000 | Bulk document processing |
| Classification | sharegpt | 1000 | Short output (64 tokens) |
| Translation | sharegpt | 500 | Long output (1024 tokens) |
| Entity Extraction | sharegpt | 1000 | Medium output (128 tokens) |
| Dataset Generation | random 256:256 | 5000 | Synthetic data, fixed lengths |
| ETL Pipelines | sonnet | 500 | Reproducible baseline text |
| Code Generation | random 512:512 | 500 | Balanced I/O lengths |
| Long-Doc Summarization | random 4096:256 | 500 | Prefill-heavy, long input |
| Batch RAG / Grounded Q&A | random 2048:128 | 500 | Long context, short answer |
| Shared-Prefix / Template | random 1024:64 | 1000 | Short-output template shape |
| Ultra-Short Labeling | sharegpt | 2000 | Output 16 tokens, high volume |

**Production questions each new use case answers:**

- **Long-Doc Summarization** — How many long documents (reports, legal
  filings, articles) can we summarize per hour? Where is the bottleneck:
  prefill or decode?
- **Batch RAG** — How fast can we process RAG queries where most tokens
  are retrieved context and output is a short answer?
- **Shared-Prefix** — How fast can we process template-shaped batches
  (moderate input, very short output) typical of classify/moderate/extract
  jobs? At what core count does this short-output shape saturate?
  *Note:* `--enable-prefix-caching` is disabled because `vllm bench
  throughput` with `--dataset-name random` generates independent random
  prompts with no shared prefix, so cache hit rate stays ~0. Re-enable
  only when a workload with a fixed instruction prefix + unique suffixes
  (or an equivalent shared-prefix dataset) is available, plus an on/off
  baseline.
- **Ultra-Short Labeling** — At what core count do sentiment/yes-no
  tasks saturate? How does output=16 compare to classification@64?

**Datasets:**

- **ShareGPT** — real conversations with variable token lengths (100-2000).
  Used for realistic text workloads (summarization, classification,
  translation, entity extraction, ultra-short labeling)
- **Random** — synthetic with controlled I/O lengths. Used for dataset
  generation, code generation, long-doc summarization, RAG, shared-prefix,
  and technical benchmarks
- **Sonnet** — classic poetry, ~50 prompts. Used for reproducible baselines

### Technical Benchmarks

Performance characterization tests that isolate individual variables
while sweeping core counts:

| Test | Purpose | Variable |
|------|---------|----------|
| Baseline | Cross-model throughput comparison | 4 RedHatAI models |
| Batch Scaling | Find optimal batch size | 10, 50, 100, 250, 500, 1000 prompts |
| Input Scaling | Prefill performance curve | 128, 256, 512, 1024, 2048 input tokens |
| Output Scaling | Decode performance curve | 64, 128, 256, 512, 1024 output tokens |
| Quantization | INT8 vs INT4 comparison | w8a8, w4a16 |
| KV-Cache Capacity | Max batch before KV saturation | 100, 250, 500, 1000, 2000, 5000 prompts |
| Context Scaling | Throughput vs context length | 1024, 2048, 4096, 8192 input tokens |

## Models Under Test

Offline batch testing focuses on RedHatAI quantized models optimized for
Intel Xeon CPU inference:

| Model | Parameters | Quantization |
|-------|-----------|-------------|
| RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 | 1.1B | Pruned |
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8 | 8B | INT8 (W8A8) |
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 | 8B | INT4 (W4A16) |
| RedHatAI/Qwen3-8B-quantized.w4a16 | 8B | INT4 (W4A16) |

## Metrics

### Primary Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| Throughput (total) | tokens/s | Input + output tokens processed per second |
| Throughput (output) | tokens/s | Output tokens generated per second |
| Request throughput | req/s | Requests completed per second |
| Total time | seconds | Wall-clock time for entire batch |
| Avg time per request | seconds | Mean per-request processing time |

### Detailed Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| Prefill throughput | tokens/s | Prompt processing (prefill phase) speed |
| Decode throughput | tokens/s | Token generation (decode phase) speed |
| Max KV cache usage | % | Peak KV cache memory utilization |
| Prefix cache hit rate | % | Prefix caching efficiency (when enabled) |

### Efficiency Metrics

| Metric | Unit | Description |
|--------|------|-------------|
| Tokens/sec/core | tokens/s/core | Throughput normalized by core count |
| Items per hour | items/hr | Extrapolated production processing capacity |

**Tokens/sec/core** is especially important for core scaling analysis —
the optimal core count maximizes total throughput while maintaining
reasonable per-core efficiency.

## Execution

### Via cpueval (recommended)

From the repository root:

```bash
# Default: all 11 use cases, 3 runs each
./cpueval run --suite offline-batch

# All use cases, all RedHatAI models, 5 runs each
./cpueval run --suite offline-batch --mode use-cases --runs 5 --models all

# Single use case with core sweep
./cpueval run --suite offline-batch \
  --mode use-case-sweep \
  --use-case summarization \
  --models all \
  --cores 8,16,24,32 \
  --runs 3

# Technical benchmarks
./cpueval run --suite offline-batch --mode core-scaling --model <model>
./cpueval run --suite offline-batch --mode batch-scaling --model <model> --cores 16
```

cpueval maps `--mode`, `--runs`, `--use-case`, `--models`, `--cores`, `--dataset`,
and `--num-prompts` to the bash script's positional arguments. See
[cpueval CLI Guide](../cpueval-cli.md) for full options.

### Via Bash Test Suite

```bash
cd automation/test-execution/scripts/bash

# Sweep use cases across models and core counts
./run-offline-batch-suite.sh use-case-sweep summarization \
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8" \
  8,16,24,32 3

# Technical benchmarks
./run-offline-batch-suite.sh core-scaling <model>
./run-offline-batch-suite.sh batch-scaling <model> 16

# All use cases, all models
./run-offline-batch-suite.sh use-cases 5 all
```

### Via Ansible Playbook

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8" \
  -e "dataset_name=sharegpt" \
  -e "num_prompts=100" \
  -e "requested_cores=32" \
  -e "vllm_container_image=docker.io/vllm/vllm-openai-cpu:v0.25.1"
```

## Results and Visualization

Results are saved to `results/llm/` with:

- `test-metadata.json` — configuration and environment
- `results.json` — performance metrics
- `benchmark.log` — raw vllm bench output

View results in the Streamlit dashboard:

```bash
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch_dashboard.sh
# Navigate to "Offline Batch" page
```

The dashboard shows:

- Processing capacity estimates (items/hour)
- Core scaling curves (throughput vs. core count)
- Batch size scaling analysis
- Model comparison charts

## Cross-Reference with Other Test Suites

Offline batch results complement online serving tests:

- **Concurrent Load** — measures latency under load; offline batch
  measures raw throughput without latency constraints
- **Scalability** — both use core scaling, but concurrent load includes
  HTTP/scheduling overhead that offline batch excludes
- **Embedding** — embedding models use `vllm bench serve`, not
  `vllm bench throughput` (different API)

## Related Documentation

- [Testing Methodology Overview](overview.md)
- [cpueval CLI Guide](../cpueval-cli.md) - Recommended entry point
- [3-Phase Testing Methodology](testing-phases.md) (concurrent load only)
- [Metrics Guide](metrics.md)
- [Offline Batch Test Scenarios](../../tests/offline-batch/offline-batch.md)
- [Full Testing Deck](../design/full-testing-deck.md)
