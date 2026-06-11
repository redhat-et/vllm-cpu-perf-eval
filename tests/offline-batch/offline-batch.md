---
layout: default
title: Offline Batch
---

## Test Suite: Offline Batch Processing

> **🚧 Status: Initial Implementation**
>
> This test suite is newly implemented. Core tests validated, production use pending.

Tests vLLM's offline batch processing performance using the native Python API (not server mode).

> **📚 Testing Methodology**
>
> This test suite focuses on **batch processing workloads** where:
> - Prompts are processed in batches using vLLM's `LLM()` class
> - No HTTP server overhead (unlike GuideLLM concurrent tests)
> - Total throughput and batch completion time matter more than per-request latency
> - Optimized for bulk processing, dataset generation, and ETL pipelines

## Overview

Offline batch testing measures vLLM CPU performance for batch inference workloads that don't require a running server. This complements the existing [Concurrent Load](../concurrent-load/concurrent-load.md) tests which measure server-based performance.

**Key Differences from Concurrent Load Tests:**

| Aspect | Offline Batch (This Suite) | Concurrent Load (Server Mode) |
|--------|---------------------------|-------------------------------|
| **Tool** | vLLM `LLM()` Python API | GuideLLM + vLLM server |
| **Mode** | Direct Python batch inference | HTTP requests to server |
| **Primary Metric** | Total batch time, throughput | Per-request latency (P95, P99) |
| **Use Case** | Bulk processing, ETL, dataset gen | Real-time serving, user requests |
| **Overhead** | Minimal (direct API) | HTTP + queue management |

## Goals

- **Measure bulk processing performance**: How long to process N documents/prompts
- **Find optimal batch sizes**: Balance throughput vs memory usage
- **Characterize prefill vs decode**: Understand input/output scaling
- **Establish batch processing baselines**: For ETL, dataset generation, bulk inference
- **Guide capacity planning**: Estimate time/resources for batch workloads

## Use Cases for Offline Batch

**✅ Suitable for offline batch processing:**

1. **Bulk Document Processing**
   - Summarizing 10,000 customer support tickets overnight
   - Classifying 50,000 articles for tagging
   - Translating documentation corpus
   - Extract entities from document batches

2. **Dataset Generation**
   - Generate 100,000 synthetic training examples
   - Create evaluation datasets
   - Augment existing datasets with LLM-generated content

3. **ETL Pipelines**
   - Batch inference in data processing workflows
   - Scheduled bulk processing jobs
   - Periodic batch analysis tasks

4. **Bulk Code Generation**
   - Generate tests for 1,000 functions
   - Batch code migration/conversion
   - Documentation generation for codebase

**❌ NOT suitable for offline batch (use Concurrent Load suite instead):**

- Real-time user requests
- Streaming responses
- Low-latency requirements
- Interactive applications
- Scenarios where per-request latency matters

## Models Under Test

This test suite can be run with any generative LLM model. For detailed model information, see [Model Selection Strategy](../../models/models.md).

**Recommended starting models:**
- **Small**: TinyLlama-1.1B (fast development/testing)
- **Medium**: Llama-3.2-1B, Qwen3-0.6B
- **Large**: Llama-3.1-8B, granite-3.2-2b

**Quantized variants** for memory efficiency:
- RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8
- RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16

## Test Parameters

### Key Variables

<!-- markdownlint-disable MD013 MD033 -->

| Variable | Description | Typical Values |
| --- | --- | --- |
| **Batch Size** | Number of prompts processed together | 1, 10, 50, 100, 250, 500, 1000 |
| **Input Length** | Tokens per input prompt | 128, 256, 512, 1024, 2048, 4096 |
| **Output Length** | Tokens to generate per prompt | 64, 128, 256, 512, 1024 |
| **Dtype** | Model weight precision | bfloat16, float16 |
| **KV Cache** | KV cache size | 1GiB, 2GiB, 4GiB, 8GiB |
| **Quantization** | Weight quantization level | fp16, bf16, w8a8, w4a16 |

<!-- markdownlint-enable MD013 MD033 -->

## Test Cases

### Core Tests

<!-- markdownlint-disable MD013 -->

| Test ID | Test Name | Focus | Batch Sizes | Primary Metrics |
| --- | --- | --- | --- | --- |
| OFFLINE-DOC-SUMM | Document Summarization | Bulk doc processing | 10, 100, 1000 | Total time, docs/sec |
| OFFLINE-BATCH-SCALE | Batch Size Scaling | Optimal batch size | 1→1000 | Throughput vs memory |
| OFFLINE-IO-VAR | Input/Output Variation | Prefill/decode scaling | Fixed batch, vary I/O | Tokens/sec, prefill/decode split |

<!-- markdownlint-enable MD013 -->

### Test 1: Document Summarization (OFFLINE-DOC-SUMM)

**Purpose**: Answer "How long to summarize N documents?"

**Configuration**: See [document-summarization.yaml](document-summarization.yaml)

**Test Stages**:
- Small batch: 10 docs (1000 tokens → 256 token summary)
- Medium batch: 100 docs (1000 tokens → 256 token summary)
- Large batch: 1000 docs (1000 tokens → 256 token summary)
- Long docs: 100 docs (3000 tokens → 512 token summary)
- Stress test: 1000 long docs (3000 tokens → 512 token summary)

**Key Metrics**:
- `total_time_sec`: Total wall-clock time
- `throughput_docs_per_sec`: Documents processed per second
- `throughput_tokens_per_sec`: Total tokens (input+output) per second
- `memory_peak_gb`: Peak memory usage

**Use Case**: Estimate bulk summarization job completion time

### Test 2: Batch Size Scaling (OFFLINE-BATCH-SCALE)

**Purpose**: Find optimal batch size for throughput

**Configuration**: See [batch-size-scaling.yaml](batch-size-scaling.yaml)

**Test Stages**:
Batch sizes: 1, 10, 25, 50, 100, 250, 500, 1000
Fixed I/O: 512 input tokens, 256 output tokens

**Key Metrics**:
- `throughput_tokens_per_sec`: Tokens/sec at each batch size
- `tokens_per_sec_per_core`: Efficiency metric
- `memory_peak_gb`: Memory usage scaling
- `avg_time_per_request_sec`: Time per item in batch

**Use Case**: Optimize batch size for your workload

### Test 3: Input/Output Variation (OFFLINE-IO-VAR)

**Purpose**: Characterize prefill (input) vs decode (output) performance

**Configuration**: See [input-output-variation.yaml](input-output-variation.yaml)

**Test Stages**:
- Input sweep: 128, 256, 512, 1024, 2048, 4096 tokens (fixed output: 256)
- Output sweep: 64, 128, 256, 512, 1024 tokens (fixed input: 512)

**Key Metrics**:
- `prefill_time_sec`: Time processing inputs
- `decode_time_sec`: Time generating outputs
- `throughput_tokens_per_sec`: Total throughput
- `memory_peak_gb`: Memory vs context length

**Use Case**: Understand performance for different document/output lengths

## Metrics Explained

### Primary Metrics for Batch Processing

**total_time_sec**
- Total wall-clock time to process entire batch
- **Use for**: Estimating job completion time
- Example: 100 docs in 45.2 seconds

**throughput_requests_per_sec** (or throughput_docs_per_sec)
- Documents/prompts processed per second
- **Use for**: Capacity planning
- Example: 2.21 docs/sec → 1000 docs = 452 seconds (7.5 min)

**throughput_tokens_per_sec**
- Total tokens (input + output) processed per second
- **Use for**: Comparing configurations, measuring efficiency
- Example: 567 tokens/sec

**avg_time_per_request_sec**
- Average time per individual item in batch
- **Use for**: Understanding per-item cost
- Example: 0.452 sec/doc

### System Resource Metrics

**memory_peak_gb**
- Peak memory usage during batch processing
- **Use for**: Hardware sizing, preventing OOM
- **Critical for**: Finding maximum batch size

**cpu_utilization_avg_pct**
- Average CPU utilization during batch
- **Use for**: Identifying bottlenecks

**tokens_per_sec_per_core**
- Throughput divided by CPU cores
- **Use for**: Efficiency comparison across configurations
- Higher = better CPU utilization

### Derived Metrics

**prefill_time_sec**
- Time spent processing input tokens
- Scales with input length

**decode_time_sec**
- Time spent generating output tokens
- Scales with output length and batch size

## Running Tests

### Prerequisites

```bash
# Set HuggingFace token for model access
export HF_TOKEN=hf_xxxxx

# For Ansible automation
pip install ansible
ansible-galaxy collection install containers.podman
```

### Quick Start with Ansible (Recommended)

**Using vLLM's standard benchmark (`vllm bench throughput`)**:

```bash
cd ../../automation/test-execution/ansible

# Run with sonnet dataset (100 prompts)
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8" \
  -e "dataset_name=sonnet" \
  -e "num_prompts=100" \
  -e "requested_cores=32"

# Run with random dataset (1000 prompts)
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "dataset_name=random" \
  -e "num_prompts=1000" \
  -e "input_len=512" \
  -e "output_len=256" \
  -e "requested_cores=16"

# Run with RHAIIS container
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
ansible-playbook -i inventory/hosts.yml llm-benchmark-offline-batch.yml \
  -e "test_model=RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8" \
  -e "dataset_name=sonnet" \
  -e "num_prompts=100" \
  -e "requested_cores=32"
```

### Alternative: Custom Python Scripts

**Run custom benchmark scripts:**

```bash
cd ../../automation/test-execution/scripts/bash

# All tests
./run-offline-batch-benchmark.sh all meta-llama/Llama-3.2-1B-Instruct

# Individual tests
./run-offline-batch-benchmark.sh summarization TinyLlama/TinyLlama-1.1B-Chat-v1.0
./run-offline-batch-benchmark.sh scaling meta-llama/Llama-3.1-8B-Instruct
./run-offline-batch-benchmark.sh io-variation Qwen/Qwen3-0.6B
```

**Direct Python script usage:**

```bash
cd ../python

# Document summarization
python offline_batch_benchmark.py \
  --config ../../../tests/offline-batch/document-summarization.yaml \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --output ../../../results/

# Batch size scaling
python offline_batch_benchmark.py \
  --config ../../../tests/offline-batch/batch-size-scaling.yaml \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --output ../../../results/
```

### Configuration Tuning

**Increase throughput:**

```bash
# Use more CPU cores
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32

# Use larger batch size (if memory allows)
# Edit YAML: batch_size: 250  # up from 100

# Use quantized model
./run-offline-batch-benchmark.sh scaling \
  RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8
```

**Reduce memory usage:**

```bash
# Use smaller batch size
# Edit YAML: batch_size: 50  # down from 100

# Reduce KV cache
# Edit YAML: VLLM_CPU_KVCACHE_SPACE: "1GiB"  # down from 2GiB

# Use more aggressive quantization
./run-offline-batch-benchmark.sh scaling \
  RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16
```

## Expected Results

### Example: Document Summarization

```json
{
  "test_name": "small-batch-100-docs",
  "model": "meta-llama/Llama-3.2-1B-Instruct",
  "batch_size": 100,
  "avg_input_tokens": 1000.0,
  "avg_output_tokens": 256.0,
  "total_time_sec": 45.2,
  "throughput_requests_per_sec": 2.21,
  "throughput_tokens_per_sec": 567.3,
  "avg_time_per_request_sec": 0.452,
  "memory_peak_gb": 8.4,
  "cpu_utilization_avg_pct": 87.5,
  "tokens_per_sec_per_core": 17.7
}
```

**Interpreting results:**
- **2.21 docs/sec** = Can process ~7,952 documents per hour
- **1,000 documents** = 1000 / 2.21 = **452 seconds (7.5 minutes)**
- **10,000 documents** = 10000 / 2.21 = **4,524 seconds (75 minutes)**
- **Peak memory 8.4 GB** = Need ~10 GB RAM for 100-doc batches

### Example: Batch Size Scaling

| Batch Size | Throughput (tok/s) | Memory (GB) | Efficiency (tok/s/core) |
|------------|-------------------|-------------|-------------------------|
| 1 | 45 | 3.2 | 5.6 |
| 10 | 280 | 3.8 | 35.0 |
| 50 | 520 | 5.2 | 65.0 |
| 100 | 567 | 8.4 | 70.8 |
| 250 | 610 | 18.1 | 76.2 |
| 500 | OOM | - | - |

**Finding optimal batch size:**
- Batch size 100: Best balance of throughput (567 tok/s) and memory (8.4 GB)
- Batch size 250: Higher throughput but 2x memory usage
- Batch size 500: Out of memory

## Results Location

Results are saved to:

```text
results/llm/{model}/offline-batch/
├── results-YYYYMMDD_HHMMSS.json      # Ansible benchmark results
├── benchmark-YYYYMMDD_HHMMSS.log     # Raw benchmark output
├── document-summarization/            # Custom script results
│   ├── summarize-10-docs-1k-tokens.json
│   ├── summarize-100-docs-1k-tokens.json
│   └── ...
└── batch-scaling/                     # Custom script results
    ├── batch-size-001.json
    └── ...
```

### Ansible Results Format

Results from `llm-benchmark-offline-batch.yml` are saved as:

```json
{
  "test_run_id": "20260610_125901",
  "timestamp": "2026-06-10T12:59:01Z",
  "test_type": "offline-batch",
  "model": "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8",
  "dataset": "sonnet",
  "num_prompts": 100,
  "cores": 32,
  "container_image": "registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0",
  "metrics": {
    "throughput_requests_per_sec": 1.66,
    "throughput_total_tokens_per_sec": 1094.55,
    "throughput_output_tokens_per_sec": 249.47,
    "total_prompt_tokens": 50813,
    "total_output_tokens": 15000,
    "avg_input_tokens": 508.13,
    "avg_output_tokens": 150.0,
    "avg_time_per_request_sec": 0.602,
    "total_time_sec": 60.24
  }
}
```

## Analysis

### Estimating Production Workloads

**Use Case 1: Nightly document summarization**
- **Requirement**: Summarize 50,000 customer support tickets daily
- **Benchmark**: 2.21 docs/sec (from 100-doc test)
- **Estimate**: 50,000 / 2.21 = 22,624 seconds = **6.3 hours**
- **Recommendation**: Schedule 8-hour nightly batch job with headroom

**Use Case 2: Real-time batch processing**
- **Requirement**: Process 500 documents every 30 minutes
- **Benchmark**: 2.21 docs/sec
- **Estimate**: 500 / 2.21 = 226 seconds = **3.8 minutes**
- **Recommendation**: Well within 30-min window, can handle 8x spike

**Use Case 3: Dataset generation**
- **Requirement**: Generate 100,000 synthetic examples
- **Benchmark**: 567 tokens/sec, 768 tokens per example (512 in + 256 out)
- **Estimate**: (100,000 × 768) / 567 = **135,450 seconds = 37.6 hours**
- **Recommendation**: Run over weekend or use larger model/more resources

### Comparing Configurations

**Quantization Impact Example:**

| Model Variant | Throughput | Memory | Quality |
|--------------|-----------|--------|---------|
| bf16 | 450 tok/s | 16.2 GB | 100% (baseline) |
| w8a8 | 520 tok/s | 8.4 GB | ~98% |
| w4a16 | 580 tok/s | 6.1 GB | ~96% |

**Choose based on:**
- w8a8: Best balance (15% faster, 50% less memory, minimal quality loss)
- w4a16: Maximum throughput, acceptable for non-critical tasks
- bf16: Maximum quality, use if memory not constrained

## Future Tests

Additional tests to consider adding:

**Priority 1: System Configuration**
- CPU core scaling (4, 8, 16, 32, 64 cores)
- Quantization comparison (systematic fp16/bf16/w8a8/w4a16)
- Memory pressure testing (find max batch size before OOM)
- KV cache size tuning

**Priority 2: Real Workloads**
- Classification at scale (sentiment, topic)
- Multi-document Q&A batching
- Bulk code generation (batch generate tests/docs)

**Priority 3: Advanced**
- NUMA configuration impact
- Model size comparison (1B vs 3B vs 7B vs 8B)
- Long context handling (8K, 16K, 32K tokens)
- Comparison with server mode overhead (offline vs online)

See offline batch test YAML files for implementation templates.

## Related Documentation

- [Concurrent Load Test Suite](../concurrent-load/concurrent-load.md) - Server-based testing
- [Testing Methodology](../../docs/methodology/overview.md) - Overall approach
- [Model Selection](../../models/models.md) - Available models
- [Results Documentation](../../results/results.md) - Results format and location

## Test Execution Scripts

**Main scripts:**
- Python: `automation/test-execution/scripts/python/offline_batch_benchmark.py`
- Shell: `automation/test-execution/scripts/bash/run-offline-batch-benchmark.sh`

**Test configurations:**
- `document-summarization.yaml` - Bulk doc processing
- `batch-size-scaling.yaml` - Optimal batch size
- `input-output-variation.yaml` - I/O scaling

## Key Takeaways

1. **Offline batch is for bulk processing**, not real-time serving
2. **Batch size is critical** - find sweet spot between throughput and memory
3. **Use throughput metrics** (docs/sec, tokens/sec), not per-request latency
4. **Quantization helps** - w8a8 often gives best throughput/memory/quality balance
5. **Scale estimates linearly** - if 100 docs = 45 sec, then 1000 docs ≈ 450 sec
6. **Memory is the limit** - batch size constrained by available RAM
