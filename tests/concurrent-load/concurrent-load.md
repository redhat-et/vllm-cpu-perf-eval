---
layout: default
title: Concurrent Load
---

# Test Suite: Concurrent Load

> **✅ Status: Validated**
>
> This test suite has been fully validated and tested. Safe for production use.

Tests model performance under various concurrent request loads.

> **📚 Testing Methodology**
>
> This test suite implements the [3-Phase Testing Methodology](../../docs/methodology/testing-phases.md):
> - **Phase 1**: Baseline tests with fixed tokens and no caching
> - **Phase 2**: Realistic tests with variable tokens and no caching
> - **Phase 3**: Production tests with realistic datasets and caching enabled
>
> See [testing-phases.md](../../docs/methodology/testing-phases.md) for the general methodology that applies to all test suites.

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
| **Concurrency** | Parallel request levels | `{1, 2, 4, 8, 16, 32}` | `{1, 2, 4, 8, 16, 32}` |
| **Affinity** | Core allocation strategy | FULL: All physical cores | FULL: All physical cores |
| **Cores** | Number of cores for test | 16, 32, 64 cores | 16, 32, 64 cores |
| **Dtype** | Data type for weights | bfloat16 | bfloat16 |
| **KV Cache** | KV cache configuration | Native precision | Native precision |
| **Prefix Caching** | Caching configuration | **OFF** (baseline) | **OFF** (baseline) / **ON** (production comparison) |

<!-- markdownlint-enable MD013 MD033 -->

## Test Cases

### Phase 1: Baseline Tests (Fixed Tokens, No Caching)

Concurrency levels: **{1, 2, 4, 8, 16, 32}**

<!-- markdownlint-disable MD013 -->

| Test ID | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- |
| CONC-LLAMA32-CHAT | Llama-3.2-1B | Chat (512:256) | P95 Latency Scaling (Baseline) |
| CONC-LLAMA32-RAG | Llama-3.2-1B | RAG (4096:512) | P95 Latency for Long Context RAG |
| CONC-LLAMA32-CODE | Llama-3.2-1B | CodeGen (512:4096) | P95 Latency for Long Output (Baseline) |
| CONC-QWEN06-CHAT | Qwen/Qwen3-0.6B | Chat (512:256) | P95 Latency (Efficient Model) |
| CONC-QWEN06-CODE | Qwen/Qwen3-0.6B | CodeGen (512:4096) | P95 Latency for Long Output |
| CONC-GRANITE32-CHAT | granite-3.2-2b-instruct | Chat (512:256) | P95 Latency (Enterprise) |
| CONC-GRANITE32-RAG | granite-3.2-2b-instruct | RAG (4096:512) | P95 Latency for Enterprise RAG |
| CONC-GRANITE32-CODE | granite-3.2-2b-instruct | CodeGen (512:4096) | P95 Latency for Code Generation |
| CONC-GPT20B-CHAT | gpt-oss-20b | Chat (512:256) | P95 Latency (Large-Scale MoE) |
| CONC-GPT20B-RAG | gpt-oss-20b | RAG (4096:512) | P95 Latency for Long Context RAG (128k capable) |
| CONC-GPT20B-CODE | gpt-oss-20b | CodeGen (512:4096) | P95 Latency for Code Generation (MoE) |
| CONC-TINY11-CHAT | TinyLlama-1.1B | Chat (512:256) | P95 Latency (Small Llama) |
| CONC-OPT125M-SUMM | facebook/opt-125m | Summarization (1024:256) | P95 Latency for Summarization |
| CONC-OPT125M-CHAT | facebook/opt-125m | Chat (512:256) | P95 Latency (Small Baseline) |

<!-- markdownlint-enable MD013 -->

### Phase 2: Realistic Tests (Variable Tokens, No Caching)

Concurrency levels: **{1, 2, 4, 8, 16, 32}**

<!-- markdownlint-disable MD013 -->

| Test ID | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- |
| CONC-LLAMA32-CHAT-VAR | Llama-3.2-1B | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-LLAMA32-CODE-VAR | Llama-3.2-1B | CodeGen (512±128:4096±1024) | P95 Latency for Long Output (Realistic) |
| CONC-QWEN06-CHAT-VAR | Qwen/Qwen3-0.6B | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-QWEN06-CODE-VAR | Qwen/Qwen3-0.6B | CodeGen (512±128:4096±1024) | P95 Latency for Long Output (Realistic) |
| CONC-GRANITE32-CHAT-VAR | granite-3.2-2b-instruct | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-GPT20B-CHAT-VAR | gpt-oss-20b | Chat (512±128:256±64) | P95 Latency (Realistic, Large-Scale) |
| CONC-TINY11-CHAT-VAR | TinyLlama-1.1B | Chat (512±128:256±64) | P95 Latency (Realistic) |
| CONC-OPT125M-SUMM-VAR | facebook/opt-125m | Summarization (1024±256:256±64) | P95 Latency for Summarization (Realistic) |

<!-- markdownlint-enable MD013 -->

### Phase 3: Production Tests (Realistic Datasets, With Caching)

> **⚠️ PHASE 3 NOT YET SUPPORTED**
>
> Phase 3 testing requires realistic prompt datasets that simulate
> production traffic patterns. Currently, we use synthetic data with
> statistical variability (Phase 2), but true production testing requires
> actual conversation histories, code repositories, or document collections.
>
> **Blocked by:** Selection and integration of realistic datasets for each
> workload type (Chat, RAG, CodeGen). Once datasets are available, Phase 3
> will use the same infrastructure as Phase 2 but with
> `vllm_caching_mode=production` and real-world prompts.

Concurrency levels: **{1, 2, 4, 8, 16, 32}** (when implemented)

<!-- markdownlint-disable MD013 -->

| Test ID | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- |
| CONC-LLAMA32-CHAT-PROD | Llama-3.2-1B | Chat (realistic dataset) | Production P95 Latency with Caching |
| CONC-LLAMA32-CODE-PROD | Llama-3.2-1B | CodeGen (realistic dataset) | Production P95 Latency with Caching |
| CONC-GRANITE32-CHAT-PROD | granite-3.2-2b-instruct | Chat (realistic dataset) | Production P95 Latency (Enterprise) |
| CONC-GPT20B-CHAT-PROD | gpt-oss-20b | Chat (realistic dataset) | Production P95 Latency (Large-Scale) |

<!-- markdownlint-enable MD013 -->

**Notes:**
- **Phase 1 (Baseline)**: All models tested with fixed token counts to
  establish reproducible baselines
- **Phase 2 (Realistic)**: Priority models tested with variable token
  distributions (synthetic)
- **Phase 3 (Production)**: Subset of models tested with real-world
  datasets and caching enabled (pending dataset selection)
- The complete test matrix is defined in
  [`model-matrix.yaml`](../../models/llm-models/model-matrix.yaml), which
  serves as the source-of-truth for execution
- Not all models are tested with all workload profiles - combinations are
  selected based on model characteristics and primary use cases

## Embedding Models

**Note:** Embedding model concurrent load testing is covered in the
dedicated [Embedding Models Test Suite](../embedding-models/embedding-models.md).
See specifically:
- [Latency Concurrent Testing](../embedding-models/latency-concurrent.yaml) -
  Concurrency levels {16, 32, 64, 128, 196}
- Comprehensive embedding-specific metrics and analysis

This test suite focuses exclusively on **generative LLM models**.

## Testing Strategy: 3-Phase Approach

This test suite implements the
[3-Phase Testing Methodology](../../docs/methodology/testing-phases.md) to
separate baseline performance, realistic variability, and production
optimization analysis.

**Quick Reference:**
- **Phase 1 (Baseline)**: Fixed tokens, no caching, all models/workloads
- **Phase 2 (Realistic)**: Variable tokens, no caching, priority
  models/workloads
- **Phase 3 (Production)**: Realistic datasets, with caching (⚠️ pending
  dataset selection)

**See [Testing Phases Documentation](../../docs/methodology/testing-phases.md)**
for the complete methodology, configuration patterns, and cross-phase analysis.

### Phase Configuration Summary

**Phase 1: Baseline Tests**
```bash
cd ../../automation/test-execution/ansible
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=baseline" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,2,4,8,16,32]" \
  -e "guidellm_max_seconds=600"
```

**Phase 2: Realistic Tests**
```bash
cd ../../automation/test-execution/ansible
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat_var" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=baseline" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,2,4,8,16,32]" \
  -e "guidellm_max_seconds=600"
```

**Phase 3: Production Tests** (⚠️ pending realistic dataset selection)
```bash
cd ../../automation/test-execution/ansible
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat_var" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=production" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,2,4,8,16,32]" \
  -e "guidellm_max_seconds=600"
```

## Running Tests

### Quick Start

**Two playbooks for concurrent load testing:**

#### Option A: `llm-benchmark-concurrent-load.yml` (Recommended)
Runs all 3 phases (baseline, realistic, production) automatically.

**Single core count:**
```bash
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "base_workload=chat" \
  -e "requested_cores=16"
```

**Core sweep:**
```bash
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "base_workload=chat" \
  -e "core_sweep_counts=[8,16]"
```

#### Option B: `llm-benchmark-auto.yml` (Manual control)
Runs ONE phase only - you control everything.

**Single core count:**
```bash
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=baseline" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,2,4,8,16,32]"
```

**Core sweep:**
```bash
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "core_sweep_enabled=true" \
  -e "core_sweep_counts=[8,16]" \
  -e "vllm_caching_mode=baseline" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,2,4,8,16,32]"
```

### Playbook Selection Guide

**Use the correct playbook for concurrent load testing:**

<!-- markdownlint-disable MD013 -->

| Playbook | Purpose | Workload | Cores | Use For |
| --- | --- | --- | --- | --- |
| `llm-benchmark-concurrent-load.yml` | Concurrent (3-phase) | `base_workload=chat` | `core_sweep_counts=[8,16]` OR `requested_cores=16` | ✅ Recommended |
| `llm-benchmark-auto.yml` | Concurrent (single) | `workload_type=chat` | `requested_cores=16` | ✅ One phase |
| `llm-core-sweep-auto.yml` | Scalability tests | `workload_type=chat` | `requested_cores_list=[8,16]` | ❌ NOT concurrent |

<!-- markdownlint-enable MD013 -->

**Common Mistakes:**

❌ **Wrong:** Using `llm-core-sweep-auto.yml` for concurrent load tests
- This playbook is for **scalability tests** (different test suite)
- Uses `requested_cores_list` (list of cores) instead of `core_sweep_counts`
- Uses `sweep`/`synchronous` profiles, not `concurrent`

✅ **Correct:** Using `llm-benchmark-concurrent-load.yml`
- Automatically orchestrates all 3 phases
- Uses `base_workload` (not `workload_type`)
- Uses `core_sweep_counts` or `requested_cores` (not `requested_cores_list`)

**Choose your testing approach:**

- **Option 1** - Run single model/workload with all 3 phases
  (recommended for individual tests)
- **Option 2** - Run test suite for selected model/workload combinations
  (as defined in model-matrix.yaml)
- **Option 3** - Run individual phases separately
  (for flexibility and debugging)
- **Option 4** - Manual GuideLLM execution
  (for development and testing)

### Option 1: Ansible Automation (Recommended)

The `llm-benchmark-concurrent-load.yml` playbook orchestrates all 3 phases automatically:

```bash
cd ../../automation/test-execution/ansible
export HF_TOKEN=hf_xxxxx

# Run all 3 phases with core sweep
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "core_sweep_counts=[16,32,64]"

# Run baseline phase only (Phase 1)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "base_workload=chat" \
  -e "requested_cores=16" \
  -e "skip_phase_2=true" \
  -e "skip_phase_3=true"

# Run production comparison only (Phase 3)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "requested_cores=32" \
  -e "skip_phase_1=true" \
  -e "skip_phase_2=true"
```

### Option 2: Run Test Suite (Selected Model × Workload Combinations)

```bash
cd ../../automation/test-execution/ansible
export HF_TOKEN=hf_xxxxx

# Llama-3.2-1B - All workloads
for workload in chat rag code summarization; do
  ansible-playbook -i inventory/hosts.yml \
    llm-benchmark-concurrent-load.yml \
    -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
    -e "base_workload=$workload" \
    -e "core_sweep_counts=[16,32,64]"
done

# Qwen3-0.6B - Chat and Code workloads
for workload in chat code; do
  ansible-playbook -i inventory/hosts.yml \
    llm-benchmark-concurrent-load.yml \
    -e "test_model=Qwen/Qwen3-0.6B" \
    -e "base_workload=$workload" \
    -e "core_sweep_counts=[16,32,64]"
done

# granite-3.2-2b - All workloads
for workload in chat rag code; do
  ansible-playbook -i inventory/hosts.yml \
    llm-benchmark-concurrent-load.yml \
    -e "test_model=ibm-granite/granite-3.2-2b-instruct" \
    -e "base_workload=$workload" \
    -e "core_sweep_counts=[16,32,64]"
done

# gpt-oss-20b (MoE) - All workloads
for workload in chat rag code; do
  ansible-playbook -i inventory/hosts.yml \
    llm-benchmark-concurrent-load.yml \
    -e "test_model=gpt-oss-20b" \
    -e "base_workload=$workload" \
    -e "core_sweep_counts=[16,32,64]"
done

# TinyLlama-1.1B - Chat workload
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "base_workload=chat" \
  -e "core_sweep_counts=[16,32,64]"

# facebook/opt-125m - Chat and Summarization
for workload in chat summarization; do
  ansible-playbook -i inventory/hosts.yml \
    llm-benchmark-concurrent-load.yml \
    -e "test_model=facebook/opt-125m" \
    -e "base_workload=$workload" \
    -e "core_sweep_counts=[16,32,64]"
done
```

### Option 3: Individual Phase Execution

```bash
cd ../../automation/test-execution/ansible
export HF_TOKEN=hf_xxxxx

# Phase 1: Baseline (Fixed Tokens, No Caching)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "core_sweep_enabled=true" \
  -e "core_sweep_counts=[16,32]" \
  -e "vllm_caching_mode=baseline"

# Phase 2: Realistic (Variable Tokens, No Caching)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat_var" \
  -e "core_sweep_enabled=true" \
  -e "core_sweep_counts=[16,32]" \
  -e "vllm_caching_mode=baseline"

# Phase 3: Production (Variable Tokens, With Caching)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat_var" \
  -e "core_sweep_enabled=true" \
  -e "core_sweep_counts=[16,32]" \
  -e "vllm_caching_mode=production"
```

### Option 4: Manual Execution (GuideLLM)

#### Baseline Test (Fixed Tokens)

```bash
# Example: Llama-3.2-1B Chat workload (Fixed - Baseline)
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile concurrent \
  --warmup 0.1 \
  --rate 1,2,4,8,16,32 \
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
  --rate 1,2,4,8,16,32 \
  --max-seconds 600 \
  --request-timeout 600 \
  --data "prompt_tokens=512,prompt_tokens_stdev=128,prompt_tokens_min=128,prompt_tokens_max=1024,output_tokens=256,output_tokens_stdev=64,output_tokens_min=64,output_tokens_max=512"
```

#### Production Test (Variable Tokens, With Caching)

```bash
# Example: Llama-3.2-1B Chat workload (Production - Variable + Caching)
# Start vLLM with --enable-prefix-caching (or omit caching flags)
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile concurrent \
  --warmup 0.1 \
  --rate 1,2,4,8,16,32 \
  --max-seconds 600 \
  --request-timeout 600 \
  --data "prompt_tokens=512,prompt_tokens_stdev=128,prompt_tokens_min=128,prompt_tokens_max=1024,output_tokens=256,output_tokens_stdev=64,output_tokens_min=64,output_tokens_max=512"
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
```

## Analysis

Generate reports after completing tests:

```bash
# Generate reports using GuideLLM
cd ../../results/by-suite/concurrent-load

# Console report for a specific test
guidellm report generate --input llama-3.2-1b/concurrent-16.json

# JSON report for programmatic analysis
guidellm report generate \
  --input llama-3.2-1b/concurrent-*.json \
  --output-format json \
  --output-path llama-3.2-1b-analysis.json
```

> **Note:** Custom analysis scripts (`generate-report.py`, `compare-models.py`)
> are planned but not yet implemented. Use GuideLLM's built-in reporting for now.

## Related Documentation

- [Testing Methodology](../../docs/methodology/overview.md)
- [Metrics Guide](../../docs/methodology/metrics.md)
- [Manual Testing](../../docs/methodology/manual-sweep.md)
- [Scalability Test Suite](../scalability/scalability.md)
