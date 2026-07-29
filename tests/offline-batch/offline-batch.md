# Offline Batch Test Scenarios

This directory documents test scenarios for offline batch benchmarking with vLLM CPU.

## Overview

**Offline batch testing** measures vLLM performance for bulk processing workloads using the native Python API (`vllm bench throughput`), not the server/client model.

**Key Differences from Online/Server Testing:**

| Aspect | Offline Batch | Online Server |
|--------|--------------|---------------|
| **Mode** | Direct Python API | HTTP requests to server |
| **Primary Metric** | Total batch time, throughput | Per-request latency (P95, P99) |
| **Use Case** | Bulk processing, ETL, dataset generation | Real-time serving, user requests |
| **Overhead** | Minimal (direct API) | HTTP + queue management |

## Use Cases

**✅ Suitable for offline batch processing:**

1. **Bulk Document Processing**
   - Summarize 10,000 customer support tickets overnight
   - Classify 50,000 articles for tagging
   - Translate documentation corpus
   - Extract entities from document batches

2. **Long-Document Summarization**
   - Summarize long reports, legal filings, articles (2k-8k tokens)
   - Prefill-dominated workloads

3. **Batch RAG / Grounded Q&A**
   - Process RAG queries with retrieved context + short answers
   - Long input (retrieved chunks), short output

4. **Shared-Prefix / Template Batch**
   - Short-output template-shaped throughput (1024→64 tokens)
   - Measures items/hr and core saturation for classify/moderate/extract I/O shapes
   - Prefix caching is **disabled** — random prompts share no common prefix,
     so `--enable-prefix-caching` cannot produce meaningful hit rates.
     Re-enable when a shared-prefix dataset is available plus an on/off baseline

5. **Ultra-Short Labeling**
   - Sentiment analysis, moderation, yes/no classification
   - Output 16 tokens, high volume

6. **Dataset Generation**
   - Generate 100,000 synthetic training examples
   - Create evaluation datasets

7. **ETL Pipelines**
   - Batch inference in data workflows
   - Scheduled bulk processing jobs

8. **Code Generation**
   - Generate tests for 1,000 functions
   - Batch code migration/conversion

**❌ NOT suitable (use online/server tests instead):**
- Real-time user requests
- Streaming responses
- Low-latency requirements
- Interactive applications

## Test Scenarios

### 1. Use Case Oriented Tests

Real-world scenarios implemented in `run-offline-batch-suite.sh`:

| Use Case | Description | Parameters | Command |
|----------|-------------|------------|---------|
| **📝 Summarization** | Bulk document summarization | sharegpt, 1000 prompts | `use-case-sweep summarization` |
| **🏷️ Classification** | Article tagging/classification | sharegpt, output=64 tokens, 1000 prompts | `use-case-sweep classification` |
| **🌐 Translation** | Documentation translation | sharegpt, output=1024 tokens, 500 prompts | `use-case-sweep translation` |
| **🧬 Entity Extraction** | Extract entities from docs | sharegpt, output=128 tokens, 1000 prompts | `use-case-sweep entity-extraction` |
| **🎲 Dataset Generation** | Generate synthetic examples | random, 256→256 tokens, 5000 prompts | `use-case-sweep dataset-generation` |
| **💻 Code Generation** | Generate test code | random, 512→512 tokens, 500 prompts | `use-case-sweep code-generation` |
| **🔄 ETL Pipelines** | Batch inference workflows | sonnet, 500 prompts, core scaling | `use-case-sweep etl` |
| **📜 Long-Doc Summarization** | Summarize long documents | random, 4096→256 tokens, 500 prompts | `use-case-sweep long-summarization` |
| **🔍 Batch RAG** | RAG queries with context | random, 2048→128 tokens, 500 prompts | `use-case-sweep rag` |
| **📋 Shared-Prefix** | Template-shaped short-output throughput | random, 1024→64 tokens, 1000 prompts | `use-case-sweep shared-prefix` |
| **⚡ Ultra-Short Labeling** | Sentiment/moderation/yes-no | sharegpt, output=16 tokens, 2000 prompts | `use-case-sweep short-labeling` |

### 2. Technical Benchmarks

Performance characterization tests:

| Test | Purpose | Parameters | Command |
|------|---------|------------|---------|
| **Baseline** | Throughput across models | 4 RedHatAI models, 100 prompts | `baseline [cores] [prompts]` |
| **Batch Scaling** | Optimal batch size | 1, 10, 50, 100, 250, 500, 1000 | `batch-scaling <model> [cores]` |
| **Input Scaling** | Prefill performance | 128-2048 tokens | `input-scaling <model> [cores]` |
| **Output Scaling** | Decode performance | 64-1024 tokens | `output-scaling <model> [cores]` |
| **Core Scaling** | CPU scaling | 8, 16, 24, 32 cores | `core-scaling <model>` |
| **Quantization** | Quantization comparison | w8a8, w4a16 | `quantization [cores] [prompts]` |
| **KV-Cache Capacity** | Max batch before KV saturation | 100-5000 prompts, fixed 512→256 | `kv-capacity <model> [cores]` |
| **Context Scaling** | Throughput vs context length | 1024-8192 input, output=128 | `context-scaling <model> [cores]` |

## Implementation

The test scenarios are implemented in:

**cpueval CLI (recommended entry point):**
- `./cpueval run --suite offline-batch` — wraps the bash suite below
- See [cpueval CLI Guide](../../docs/cpueval-cli.md) for suite options and overrides

**Bash Test Suite:**
- `automation/test-execution/scripts/bash/run-offline-batch-suite.sh`
- See [Offline Batch Methodology](../../docs/methodology/offline-batch.md) for detailed usage

**Ansible Playbook:**
- `automation/test-execution/ansible/llm-benchmark-offline-batch.yml`
- Executes `vllm bench throughput` with specified parameters

**Dashboard:**
- `automation/test-execution/dashboard-examples/vllm_dashboard/pages/4_📦_Offline_Batch.py`
- Visualizes results: processing capacity, time estimates, scaling curves

**Unit Tests:**
- `automation/test-execution/tests/dashboard/test_offline_batch_page.py` - Dashboard page tests
- `automation/test-execution/tests/scripts/test_run_offline_batch_suite.sh` - Bash script tests

## Quick Start

### Via cpueval (recommended)

From the repository root:

```bash
# Default: all 11 use cases, 3 runs each (TinyLlama pruned)
./cpueval run --suite offline-batch

# All use cases, 5 runs, all 4 RedHatAI models
./cpueval run --suite offline-batch --mode use-cases --runs 5 --models all

# Single use case with core sweep
./cpueval run --suite offline-batch \
  --mode use-case-sweep \
  --use-case summarization \
  --models all \
  --cores 8,16,24,32 \
  --runs 3

# Single test configuration
./cpueval run --suite offline-batch \
  --mode run_test \
  --model all \
  --dataset sonnet \
  --num-prompts 1000 \
  --cores 16

# RHAIIS container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./cpueval run --suite offline-batch --mode use-cases --runs 3 --models all
```

Modes: `use-cases`, `use-case-sweep`, `baseline`, `batch-scaling`, `input-scaling`,
`output-scaling`, `core-scaling`, `quantization`, `kv-capacity`, `context-scaling`,
`all`, `run_test`. See [cpueval CLI Guide](../../docs/cpueval-cli.md) for full options.

For unsupported combinations, use the escape hatch:
`--extra args="batch-scaling <model> 16"`.

### Via bash script (advanced)

```bash
cd automation/test-execution/scripts/bash

# Run all 11 use cases with all RedHatAI models (5 runs each)
./run-offline-batch-suite.sh use-cases 5 all

# Run summarization with specific models across core counts
./run-offline-batch-suite.sh use-case-sweep summarization \
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8,RedHatAI/Qwen3-8B-quantized.w4a16" \
  8,16,24,32 3

# New use cases
./run-offline-batch-suite.sh use-case-sweep long-summarization all 16,32 3
./run-offline-batch-suite.sh use-case-sweep rag all
./run-offline-batch-suite.sh use-case-sweep shared-prefix all
./run-offline-batch-suite.sh use-case-sweep short-labeling all 8,16,24,32

# Single test
./run-offline-batch-suite.sh run_test all sonnet 1000 16

# Technical benchmarks
./run-offline-batch-suite.sh batch-scaling <model> 16
./run-offline-batch-suite.sh core-scaling <model>
./run-offline-batch-suite.sh kv-capacity <model> 32
./run-offline-batch-suite.sh context-scaling <model> 32

# View full usage
./run-offline-batch-suite.sh
```

## Metrics

**Primary Metrics:**
- `throughput_requests_per_sec` - Requests/second
- `throughput_tokens_per_sec` - Total tokens/second (input + output)
- `throughput_output_tokens_per_sec` - Output tokens/second
- `total_time_sec` - Total processing time
- `avg_time_per_request_sec` - Average time per request

**Detailed Metrics:**
- `prefill_throughput_tokens_per_sec` - Prefill phase speed
- `decode_throughput_tokens_per_sec` - Decode phase speed
- `max_kv_cache_usage_percent` - Peak KV cache usage
- `avg_prefix_cache_hit_rate_percent` - Prefix cache efficiency

**Efficiency Metrics:**
- `tokens_per_sec_per_core` - Resource efficiency
- `items_per_hour` - Processing capacity (dashboard calculated)

## Results

All results saved to: `results/llm/`

Each test creates:
- `test-metadata.json` - Configuration and environment
- `results.json` - Performance metrics
- `benchmark.log` - Raw output

**View results:**
```bash
cd automation/test-execution/dashboard-examples/vllm_dashboard
streamlit run Home.py
```

## Models

**RedHatAI Intel Xeon Compatible Models:**
```
RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4
RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8
RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16
RedHatAI/Qwen3-8B-quantized.w4a16
```

**Other Supported Models:**
```
TinyLlama/TinyLlama-1.1B-Chat-v1.0
meta-llama/Llama-3.2-1B-Instruct
meta-llama/Llama-3.1-8B-Instruct
```

## Standard Datasets

**ShareGPT** (`sharegpt`) - Real conversations
- Variable length prompts (100-2000 tokens)
- Use for: Summarization, classification, translation, entity extraction (realistic text with natural language patterns)
- Built-in dataset, no download required

**Sonnet** (`sonnet`) - Baseline dataset
- Classic poetry text, ~50 prompts
- Use for: ETL pipelines, reproducible baseline measurements

**Random** (`random`) - Synthetic dataset
- Controlled input/output lengths
- Use for: Dataset generation, code generation, technical benchmarks (batch/I/O scaling)

## Example Results

**Summarization (1000 docs, sonnet):**
```json
{
  "throughput_requests_per_sec": 2.21,
  "throughput_tokens_per_sec": 567.3,
  "total_time_sec": 452.0,
  "avg_input_tokens": 508,
  "avg_output_tokens": 150
}
```

**Interpreting:**
- **2.21 docs/sec** = 7,952 docs/hour
- **1,000 docs** = 452 seconds (7.5 minutes)
- **10,000 docs** = 4,524 seconds (75 minutes)

**Batch Size Scaling:**

| Batch Size | Throughput (tok/s) | Memory (GB) | Efficiency (tok/s/core) |
|------------|-------------------|-------------|-------------------------|
| 10 | 280 | 3.8 | 35.0 |
| 50 | 520 | 5.2 | 65.0 |
| 100 | 567 | 8.4 | 70.8 |
| 250 | 610 | 18.1 | 76.2 |

**Finding optimal batch size:** Batch 100 offers best throughput/memory balance

## Configuration

**Environment Variables:**
```bash
# Container image (default: upstream vLLM)
export VLLM_CONTAINER_IMAGE=vllm/vllm-openai:latest

# RHAIIS optimized container
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

# Timeout settings
export OFFLINE_BATCH_BASE_TIMEOUT=600       # 10 min base
export OFFLINE_BATCH_TIMEOUT_PER_PROMPT=2   # 2s per prompt
export OFFLINE_BATCH_MAX_RETRIES=1          # Retry once on failure

# HuggingFace token for gated models
export HF_TOKEN=hf_your_token_here
```

## Related Documentation

- [cpueval CLI Guide](../../docs/cpueval-cli.md) - Recommended entry point
- [Automation README](../../automation/test-execution/README.md) - All test types overview
- [Dashboard README](../../automation/test-execution/dashboard-examples/vllm_dashboard/README.md) - Visualization guide
- [Main Tests Overview](../tests.md) - All test suites
