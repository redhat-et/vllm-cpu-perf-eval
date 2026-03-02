# Test Suite: Concurrent Load

Tests model performance under various concurrent request loads.

## Overview

This test suite focuses on measuring how P95 latency and throughput scale as the
number of parallel request streams increases. The suite includes both baseline
(fixed token) and realistic (variable token) workload testing to establish
comprehensive performance characteristics for CPU inferencing across multiple
model architectures and workload types.

**Version 2 Enhancements:**
- ⏱️ Time-based testing (600 seconds) for consistency across CPU types
- 1️⃣ Single-user baseline (concurrency=1) for efficiency calculations
- 📊 Variable workload support for realistic traffic simulation
- 🔄 3-phase testing strategy (baseline → realistic → production)
- 🎯 Explicit prefix caching control (baseline vs production)

## Goals

- Measure P95 latency scaling with increasing concurrency
- Identify throughput saturation points
- Establish baseline performance for different model architectures
- Test across realistic workload profiles (Chat, RAG, CodeGen, Summarization)

## Models Under Test

This test suite evaluates generative LLM models across multiple architecture families to ensure comprehensive coverage of CPU inference scenarios. For detailed model information including architecture details, selection rationale, and full specifications, see [Model Selection Strategy](../../models/models.md#core-architectural-coverage).

**Quick Reference:**
- **LLM Models**: Llama-3.2-1B, TinyLlama-1.1B, facebook/opt-125m, granite-3.2-2b, Qwen/Qwen3-0.6B, **gpt-oss-20b (21B MoE)**

**Note:** Embedding model concurrent load testing is covered in the dedicated [Embedding Models Test Suite](../embedding-models/embedding-models.md).

## Test Parameters

### Key Variables

<!-- markdownlint-disable MD013 MD033 -->

| Variable | Description | Baseline Tests | Realistic Tests |
| --- | --- | --- | --- |
| **Workload** | Input/Output token counts (ISL:OSL) | • Chat (512:256)<br>• RAG (4096:512)<br>• CodeGen (512:4096)<br>• Summarization (1024:256) | • Chat (512±128:256±64)<br>• CodeGen (512±128:4096±1024) |
| **Test Duration** | Time per profile | `--max-seconds=600` (10 min) | `--max-seconds=600` (10 min) |
| **Warmup** | Warmup period | `--warmup=0.1` (10% = 60s) | `--warmup=0.1` (10% = 60s) |
| **Request Timeout** | Max time per request | `--request-timeout=600` | `--request-timeout=600` |
| **Concurrency** | Parallel request levels | `{1, 8, 16, 32, 64, 96, 128}` | `{1, 8, 16, 32, 64, 96, 128}` |
| **Affinity** | Core allocation strategy | FULL: All physical cores | FULL: All physical cores |
| **Cores** | Number of cores for test | 16, 32, 64 cores | 16, 32, 64 cores |
| **Dtype** | Data type for weights | bfloat16 | bfloat16 |
| **KV Cache** | KV cache configuration | Native precision | Native precision |
| **Prefix Caching** | Caching configuration | **OFF** (baseline) | **OFF** (baseline) / **ON** (production comparison) |

<!-- markdownlint-enable MD013 MD033 -->

## Test Cases

### LLM Models - Concurrent Tests

Concurrency levels: **{1, 8, 16, 32, 64, 96, 128}**

<!-- markdownlint-disable MD013 -->

| Test ID | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- |
| CONC-LLAMA32-CHAT | Llama-3.2-1B | Chat (512:256) | P95 Latency Scaling (Baseline) |
| CONC-LLAMA32-CHAT-VAR | Llama-3.2-1B | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-LLAMA32-RAG | Llama-3.2-1B | RAG (4096:512) | P95 Latency for Long Context RAG |
| CONC-LLAMA32-CODE | Llama-3.2-1B | CodeGen (512:4096) | P95 Latency for Long Output (Baseline) |
| CONC-LLAMA32-CODE-VAR | Llama-3.2-1B | CodeGen (512±128:4096±1024) | P95 Latency for Long Output (Realistic) |
| CONC-QWEN06-CHAT | Qwen/Qwen3-0.6B | Chat (512:256) | P95 Latency (Efficient Model) |
| CONC-QWEN06-CHAT-VAR | Qwen/Qwen3-0.6B | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-QWEN06-CODE | Qwen/Qwen3-0.6B | CodeGen (512:4096) | P95 Latency for Long Output |
| CONC-QWEN06-CODE-VAR | Qwen/Qwen3-0.6B | CodeGen (512±128:4096±1024) | P95 Latency for Long Output (Realistic) |
| CONC-GRANITE32-CHAT | granite-3.2-2b-instruct | Chat (512:256) | P95 Latency (Enterprise) |
| CONC-GRANITE32-CHAT-VAR | granite-3.2-2b-instruct | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-GRANITE32-RAG | granite-3.2-2b-instruct | RAG (4096:512) | P95 Latency for Enterprise RAG |
| CONC-GRANITE32-CODE | granite-3.2-2b-instruct | CodeGen (512:4096) | P95 Latency for Code Generation |
| CONC-GPT20B-CHAT | gpt-oss-20b | Chat (512:256) | P95 Latency (Large-Scale MoE) |
| CONC-GPT20B-CHAT-VAR | gpt-oss-20b | Chat (512±128:256±64) | P95 Latency (Realistic, Large-Scale) |
| CONC-GPT20B-RAG | gpt-oss-20b | RAG (4096:512) | P95 Latency for Long Context RAG (128k capable) |
| CONC-GPT20B-CODE | gpt-oss-20b | CodeGen (512:4096) | P95 Latency for Code Generation (MoE) |
| CONC-TINY11-CHAT | TinyLlama-1.1B | Chat (512:256) | P95 Latency (Small Llama) |
| CONC-TINY11-CHAT-VAR | TinyLlama-1.1B | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-OPT125M-SUMM | facebook/opt-125m | Summarization (1024:256) | P95 Latency for Summarization |
| CONC-OPT125M-CHAT | facebook/opt-125m | Chat (512:256) | P95 Latency (Small Baseline) |

**Note:** Tests with `-VAR` suffix include statistical variability. Run these after baseline tests for comparison.

<!-- markdownlint-enable MD013 -->

## Embedding Models

**Note:** Embedding model concurrent load testing is covered in the
dedicated [Embedding Models Test Suite](../embedding-models/embedding-models.md).
See specifically:
- [Latency Concurrent Testing](../embedding-models/latency-concurrent.yaml) -
  Concurrency levels {16, 32, 64, 128, 196}
- Comprehensive embedding-specific metrics and analysis

This test suite focuses exclusively on **generative LLM models**.

## Testing Strategy: 3-Phase Approach

This test suite implements a phased testing methodology to separate baseline
performance, realistic variability, and production optimization analysis.

### Phase 1: Baseline Tests (Fixed Tokens, No Caching)

**Objective:** Establish pure baseline performance without caching optimizations

**Configuration:**
- vLLM: `--no-enable-prefix-caching`, `--disable-radix-cache`
- Token counts: Fixed (no variability)
- Concurrency: `{1, 8, 16, 32, 64, 96, 128}`

**Tests:** All models × All workload profiles (Chat, RAG, CodeGen, Summarization)

**Example:**
```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=baseline" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,8,16,32,64,96,128]" \
  -e "guidellm_max_seconds=600"
```

### Phase 2: Realistic Tests (Variable Tokens, No Caching)

**Objective:** Understand performance under realistic traffic variability

**Configuration:**
- vLLM: `--no-enable-prefix-caching`, `--disable-radix-cache`
- Token counts: Variable (with stdev)
- Concurrency: Same as Phase 1

**Tests (Priority):**
1. Chat workload - All models with variability
2. CodeGen workload - All models with variability

**Example:**
```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat_var" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=baseline" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,8,16,32,64,96,128]" \
  -e "guidellm_max_seconds=600"
```

### Phase 3: Production Comparison (Fixed Tokens, With Caching)

**Objective:** Quantify production optimization gains from prefix caching

**Configuration:**
- vLLM: `--enable-prefix-caching` (or omit)
- Token counts: Fixed (for easier comparison to Phase 1)
- Concurrency: Same as Phase 1

**Tests (Select models):**
- High-priority models (e.g., Llama-3.2-1B, granite-3.2-2b, gpt-oss-20b)
- Workloads that benefit most from caching (Chat, RAG)

**Example:**
```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=production" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,8,16,32,64,96,128]" \
  -e "guidellm_max_seconds=600"
```

## Running Tests

### Option 1: Docker/Podman Compose

```bash
# Run all concurrent load tests
docker compose up

# Run specific model and scenario
MODEL_NAME=llama-3.2-1b SCENARIO=concurrent-8 docker compose up
```text

### Option 2: Ansible Automation

```bash
# Run entire test suite
cd ../../automation/test-execution/ansible
ansible-playbook playbooks/run-suite.yml -e "test_suite=concurrent-load"

# Run specific model
ansible-playbook playbooks/run-model.yml \
  -e "model_name=llama-3.2-1b" \
  -e "test_suite=concurrent-load"
```text

### Option 3: Manual Execution (GuideLLM)

#### Baseline Test (Fixed Tokens)

```bash
# Example: Llama-3.2-1B Chat workload (Fixed - Baseline)
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile concurrent \
  --warmup 0.1 \
  --rate 1,8,16,32,64,96,128 \
  --max-seconds 600 \
  --request-timeout 600 \
  --data "prompt_tokens=512,output_tokens=256"
```

#### Realistic Test (Variable Tokens)

```bash
# Example: Llama-3.2-1B Chat workload (Variable - Realistic)
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile concurrent \
  --warmup 0.1 \
  --rate 1,8,16,32,64,96,128 \
  --max-seconds 600 \
  --request-timeout 600 \
  --data "prompt_tokens=512,prompt_tokens_stdev=128,prompt_tokens_min=128,prompt_tokens_max=1024,output_tokens=256,output_tokens_stdev=64,output_tokens_min=64,output_tokens_max=512"
```

#### Production Test (With Caching)

```bash
# Example: gpt-oss-20b RAG workload (Production - With Caching)
# Start vLLM with --enable-prefix-caching (or omit caching flags)
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile concurrent \
  --warmup 0.1 \
  --rate 1,8,16,32,64,96,128 \
  --max-seconds 600 \
  --request-timeout 600 \
  --data "prompt_tokens=4096,output_tokens=512"
```

## Key Metrics

Monitor these metrics for each concurrency level:

- **P95 E2EL (ms)** - 95th percentile latency (PRIMARY METRIC)
- **P99 E2EL (ms)** - 99th percentile latency
- **Mean E2EL (ms)** - Average end-to-end latency
- **Request throughput (req/s)** - Requests completed per second
- **Token throughput (tok/s)** - Tokens processed per second

### What to Look For

- **Sweet spot**: Concurrency where throughput plateaus but P95 latency is
  acceptable
- **Degradation point**: When P95 latency increases sharply while throughput
  gains diminish
- **Scaling pattern**: How P95 scales from low to high concurrency

## Results

Results are written to:

```text
../../results/
├── by-suite/concurrent-load/
│   ├── llama-3.2-1b/
│   │   ├── concurrent-8.json
│   │   ├── concurrent-16.json
│   │   └── ...
│   └── ...
└── by-model/llama-3.2-1b/concurrent-load/
```text

## Analysis

Generate reports after completing tests:

```bash
cd ../../automation/analysis

# HTML report for entire test suite
python generate-report.py \
  --input ../../results/by-suite/concurrent-load \
  --format html

# Compare models at specific concurrency
python compare-models.py \
  --suite concurrent-load \
  --scenario concurrent-32
```text

## Related Documentation

- [Testing Methodology](../../docs/methodology/overview.md)
- [Metrics Guide](../../docs/methodology/metrics.md)
- [Manual Testing](../../docs/methodology/manual-sweep.md)
- [Scalability Test Suite](../scalability/)
