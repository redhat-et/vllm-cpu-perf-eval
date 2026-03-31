---
layout: default
title: Models
---

## Models Directory

This directory contains centralized model definitions and selection documentation used across all test suites.

## Overview

Models are organized by type (LLM and Embedding), with each type having its own model matrix defining test configurations and scenarios.

**Key Resources:**
- **[LLM Models](#llm-models)** - Large Language Models (decoder-only architectures)
- **[Embedding Models](#embedding-models)** - Embedding models (encoder-only architectures)
- **[Model Selection Strategy](#model-selection-strategy)** - Why these models were chosen
- **[Adding Models](#adding-new-models)** - How to add new models

## Structure

```text
models/
├── llm-models/
│   ├── model-matrix.yaml        # LLM model definitions and test mappings
│   └── llm-models.md            # Points to this file
├── embedding-models/
│   ├── model-matrix.yaml        # Embedding model definitions
│   └── embedding-models.md      # Embedding-specific extended documentation
└── models.md                    # This file (comprehensive documentation)
```

---

## Model Selection Strategy

This section explains the rationale and methodology for selecting models across all test suites in the vLLM CPU Performance Evaluation framework.

## Selection Principles

The benchmarking strategy is designed to ensure **maximum architectural coverage** for effective CPU inference testing on a vLLM server. This is achieved by:

1. **Selecting a representative model from each unique underlying architectural family** present in the original list of proposed models
2. **Adding essential architectures** that stress specific inference phases (Decode, Prefill, Balanced) relevant to real-world applications (Code Gen, RAG)
3. **Minimizing redundancy** while maintaining comprehensive coverage
4. **Resource Constraints**: All models must run on typical CPU hardware (64GB+ RAM)

## Core Architectural Coverage

The following models provide baseline coverage across key architecture families:

### LLM Models (Decoder-Only)

| Architecture Family | Representative Model | Key Application Focus | Parameters | Rationale |
|---------------------|---------------------|----------------------|------------|-----------|
| Llama 3 Decoder | Llama-3.2-1B-Instruct | Prefill-Heavy (Baseline) | 1.2B | Latest Llama architecture, strong prefill performance |
| Llama 2 Decoder | TinyLlama-1.1B-Chat-v1.0 | Prefill/Decode (Small-Scale) | 1.1B | Compact Llama 2 variant, resource-efficient |
| IBM Granite Decoder | granite-3.2-2b-instruct | Balanced (Enterprise Baseline) | 2B | Enterprise-grade, balanced prefill/decode |
| Qwen 3 Decoder | Qwen/Qwen3-0.6B | Balanced (High-Efficiency) | 0.6B | Efficient architecture, strong performance/size ratio |
| Transformer MoE | openai/gpt-oss-20b | Scalability Testing (Large-Scale) | 21B (3.6B active) | MoE architecture, 128k context, CPU scalability testing |

### Embedding Models (Encoder-Only)

| Architecture Family | Representative Model | Key Application Focus | Parameters | Rationale |
|---------------------|---------------------|----------------------|------------|-----------|
| MiniLM/BERT (English Dense) | granite-embedding-english-r2 | Encoder-Only (Fastest Baseline) | ~110M | Fast English-only embedding, baseline performance |
| XLM-RoBERTa (Multilingual Dense) | granite-embedding-278m-multilingual | Encoder-Only (Multilingual) | ~278M | Multilingual support, broader language coverage |

## Workload Coverage

Each model is tested across workloads that stress different aspects of inference:

### LLM Workloads

- **Chat (512:512)**: Balanced prefill/decode, typical conversational AI
- **RAG (8192:512)**: Long context prefill, retrieval-augmented generation
- **Code Generation (1024:1024)**: Balanced code generation scenarios
- **Summarization (2048:256)**: Medium context, summarization tasks
- **Reasoning (256:2048)**: Long output decode, chain-of-thought reasoning

### Embedding Workloads

- **Embedding (512:1)**: Single-pass encoding, typical embedding generation

## Model Reuse Across Test Suites

Models are **reused across test suites** to enable longitudinal performance analysis:

- **Test Suite 1 (Concurrent Load)**: Establishes baseline P95 latency and throughput under concurrent load
- **Test Suite 2 (Scalability)**: Uses same models to characterize maximum throughput and load-latency curves
- **Test Suite 3 (Resource Contention)**: Tests same models under resource-constrained scenarios
- **Test Suite 4 (Configuration Tuning)**: Evaluates same models with different vLLM configurations

This reuse enables:
- Direct performance comparison across test types
- Understanding how configuration changes affect the same models
- Comprehensive model profiling across multiple dimensions

## Models Deferred to Later Evaluation

To maintain the focus on establishing stable, predictable baselines for core architectures, we have deliberately **excluded** several high-complexity models and workloads. These are deferred to subsequent test suites (Test Suite 4 or beyond) where specific configuration impact and stress tolerance will be measured.

### Deferred Models and Rationale

| Model | Type | Complexity | Rationale for Deferral |
|-------|------|-----------|------------------------|
| Mixtral-8x7B-Instruct-v0.1 | MoE (Mixture of Experts) | High - Sparse activation | Introduces sparse computation patterns; requires specialized configuration testing |
| Codestral-7B | Mistral/SWA | High - Sliding window attention | Advanced attention mechanism; needs dedicated attention pattern analysis |
| Mamba-1.4B | SSM (State Space Model) | High - Recurrent architecture | Non-transformer architecture; requires separate evaluation methodology |
| Flan-T5-base | Encoder-Decoder | High - Seq2seq | Dual-stack architecture; needs separate encoder/decoder analysis |

### Why These Models Are Deferred

1. **Advanced Computational Complexity**: These models introduce sparsity (MoE), recurrence (SSM), or sequence-to-sequence patterns that require specialized testing beyond baseline evaluation

2. **Extreme Performance Biases**: Some models (e.g., Codestral with sliding window attention) have extreme prefill or decode performance characteristics that would skew baseline comparisons

3. **Configuration Sensitivity**: MoE and advanced architectures are highly sensitive to vLLM configuration parameters (expert routing, memory allocation), which is the focus of later test suites

4. **Resource Requirements**: Several deferred models require significantly more memory or compute resources, making them unsuitable for baseline CPU inference benchmarking

---

## LLM Models

This section covers Large Language Model (LLM) selection and testing across all test suites.

## Current LLM Models (9 total)

| Architecture | Model | Parameters | Primary Focus | Context Length |
|--------------|-------|------------|---------------|----------------|
| Llama 3 | Llama-3.2-1B-Instruct | 1.2B | Prefill-Heavy | 8192 |
| Llama 3 | Llama-3.2-3B-Instruct | 3.2B | Prefill-Heavy | 8192 |
| Llama 2 | TinyLlama-1.1B-Chat | 1.1B | Balanced (Small-Scale) | 2048 |
| Granite | granite-3.2-2b-instruct | 2B | Balanced (Enterprise) | 4096 |
| Qwen 3 | Qwen/Qwen3-0.6B | 0.6B | Balanced (Efficient) | 8192 |
| Qwen 2.5 | Qwen/Qwen2.5-3B-Instruct | 3B | Balanced (Efficient) | 8192 |
| Transformer MoE | openai/gpt-oss-20b | 21B (3.6B active) | Scalability Testing | 128000 |

## LLM Model Selection Rationale

### Llama 3 Family
- **Latest generation** Llama architecture from Meta
- **Strong prefill performance** - ideal for testing long context scenarios
- **Two sizes** (1B, 3B) to test scaling characteristics
- **Widely adopted** in production environments

### Llama 2 / TinyLlama
- **Compact variant** of Llama 2 architecture
- **Resource-efficient** - tests lower-end CPU scenarios
- **Balanced prefill/decode** performance
- **Baseline for small-scale deployments**

### IBM Granite
- **Enterprise-grade** model optimized for business use cases
- **Balanced architecture** - neither prefill nor decode heavy
- **Strong RAG performance** with 4K context
- **Represents commercial model deployment**

### Qwen Family
- **High efficiency** - strong performance-to-size ratio
- **Qwen 3** (0.6B) and **Qwen 2.5** (3B) variants
- **Excellent code generation** capabilities
- **Balanced prefill/decode** with fast token generation

### OpenAI GPT-OSS
- **Large-scale testing** - 21B total parameters with MoE architecture
- **Efficient inference** - Only 3.6B parameters active per token (Top-4 routing)
- **Extreme long context** - Native 128k context length support
- **Scalability validation** - Tests CPU performance at higher parameter counts
- **MoE architecture** - Unique performance characteristics vs dense models
- **Memory efficient** - MXFP4 quantization enables ~16GB memory footprint
- **Tensor parallelism candidate** - Good for testing TP=2, TP=4 configurations

## LLM Workload Details

**Note**: All workloads are optimized for **absolute best performance** by setting `--max-model-len` to the minimum required for each workload. This minimizes KV cache allocation and maximizes throughput.

### Chat (512:512)
- **Input**: 512 tokens (conversation history)
- **Output**: 512 tokens (response)
- **Total**: 1024 tokens
- **Max Model Len**: 2048
- **Focus**: Balanced prefill/decode
- **Use Case**: Conversational AI, chatbots

### RAG (8192:512)
- **Input**: 8192 tokens (retrieved documents + query)
- **Output**: 512 tokens (answer)
- **Total**: 8704 tokens
- **Max Model Len**: 16384
- **Focus**: Long context prefill
- **Use Case**: Document Q&A, knowledge retrieval

### Code Generation (1024:1024)
- **Input**: 1024 tokens (code prompt/context)
- **Output**: 1024 tokens (generated code)
- **Total**: 2048 tokens
- **Max Model Len**: 4096
- **Focus**: Balanced code generation
- **Use Case**: Code completion, generation

### Summarization (2048:256)
- **Input**: 2048 tokens (document to summarize)
- **Output**: 256 tokens (summary)
- **Total**: 2304 tokens
- **Max Model Len**: 4096
- **Focus**: Medium context, short output
- **Use Case**: Document summarization

### Reasoning (256:2048)
- **Input**: 256 tokens (problem statement)
- **Output**: 2048 tokens (reasoning chain)
- **Total**: 2304 tokens
- **Max Model Len**: 4096
- **Focus**: Long output decode for reasoning
- **Use Case**: Chain-of-thought reasoning, problem solving

## LLM Inference Characteristics

### Prefill-Heavy Models
Models that excel at processing long input contexts:
- Llama-3.2-1B-Instruct
- Llama-3.2-3B-Instruct

**Best for**: RAG, long context Q&A

### Balanced Models
Models with good prefill and decode performance:
- granite-3.2-2b-instruct
- Qwen/Qwen3-0.6B
- Qwen/Qwen2.5-3B-Instruct
- TinyLlama-1.1B-Chat

**Best for**: General-purpose deployment, mixed workloads

### Large-Scale / MoE Models
Models for scalability testing and high parameter counts:
- openai/gpt-oss-20b (21B total, 3.6B active per token)

**Best for**: CPU scalability testing, long-context RAG (128k), tensor parallelism validation

## LLM Test Suite Coverage

### Test Suite 1: Concurrent Load
Tests all models at concurrency levels: **{1, 2, 4, 8, 16, 32}**

**Enhanced v2 Features:**
- Time-based testing (600 seconds)
- Single-user baseline (concurrency=1)
- Variable workloads (chat_var, code_var) for realistic traffic simulation
- 3-phase testing: Baseline → Realistic → Production

**Participating Models:**
- Llama-3.2-1B-Instruct (Chat, RAG, Code, Summarization, Reasoning)
- TinyLlama-1.1B-Chat (Chat)
- granite-3.2-2b-instruct (Chat, RAG, Code, Summarization, Reasoning)
- Qwen/Qwen3-0.6B (Chat, Code)
- openai/gpt-oss-20b (Chat, RAG, Code)

### Test Suite 2: Scalability
Uses sweep, synchronous, and Poisson profiles

**Participating Models:**
- All models from Concurrent Load suite
- Plus: Llama-3.2-3B-Instruct, Qwen2.5-3B-Instruct

### Test Suite 3: Resource Contention (Planned)
Tests fractional core allocation, NUMA isolation, noisy neighbors

---

## Embedding Models

This section covers embedding model selection and testing.

## Current Embedding Models (2 total)

| Architecture | Model | Parameters | Primary Focus |
|--------------|-------|------------|---------------|
| MiniLM/BERT | granite-embedding-english-r2 | ~110M | English Dense Embedding |
| XLM-RoBERTa | granite-embedding-278m-multilingual | ~278M | Multilingual Embedding |

## Embedding Model Selection Rationale

### Granite English R2
- **Fast baseline** for English-only workloads
- **MiniLM/BERT architecture** - well-established encoder
- **~110M parameters** - efficient for CPU inference
- **Strong retrieval performance**

### Granite Multilingual
- **Broader language support** with reasonable performance
- **XLM-RoBERTa architecture** - proven multilingual encoder
- **~278M parameters** - larger model for complex embeddings
- **Production-ready** for enterprise multilingual applications

## Embedding Workload Details

### Embedding (512:1)
- **Input**: 512 tokens (text to embed)
- **Output**: 1 token (embedding vector generated)
- **Focus**: Single-pass encoding
- **Use Case**: Document embedding, semantic search, RAG retrieval

## Embedding Test Suite Coverage

### LLM Test Suite 1: Concurrent Load
Concurrency levels: **{4, 8, 16, 32, 64}**

**Participating Models:**
- granite-embedding-english-r2
- granite-embedding-278m-multilingual

### LLM Test Suite 2: Scalability
Uses sweep profile for maximum throughput testing

**Note:** Embedding models use `vllm bench serve` with `--backend openai-embeddings` instead of GuideLLM.

---

## Model Configuration

All models use baseline configuration with model-specific optimizations:

```yaml
dtype: Model-specific (defined per model, default: auto)
quantization: false  # Full precision
kv_cache: Model and workload specific (calculated per model/workload)
max_model_len: Workload-optimized (minimizes KV cache for best performance)
affinity: FULL       # All physical cores
```

**Model-Specific Configuration:**
- Each model has its own `dtype` defined in the model matrix (fallback: `auto`)
- KV cache sizes are calculated based on model architecture and workload requirements
- `max_model_len` is set per workload to minimize memory allocation and maximize throughput

**See**: [KV Cache Calculations](#kv-cache-size-calculations) for detailed sizing methodology.

Advanced configurations (quantization, custom KV cache) are tested in Test Suite 4 (Configuration Tuning).

---

## KV Cache Size Calculations

### Performance Optimization Strategy

**These configurations are optimized for ABSOLUTE BEST PERFORMANCE per workload.**

Each workload uses `--max-model-len` set to the minimum required for that specific workload:
- Minimizes KV cache memory allocation
- Reduces memory bandwidth pressure
- Optimizes cache locality
- **Result**: Best possible throughput and latency for each workload type

**Important**: These are workload-optimized settings. Production deployments may use larger `max-model-len` values for flexibility, which would require larger KV cache and may show different performance characteristics.

### Calculation Formula

Formula from [LMCache KV Cache Calculator](https://lmcache.ai/kv_cache_calculator.html):

```
Total Elements = 2 × num_hidden_layers × total_tokens × num_key_value_heads × head_size
Where:
  - total_tokens = input_tokens + output_tokens (ISL + OSL)
  - head_size = hidden_size ÷ num_attention_heads
Total Bytes = Total Elements × dtype_size (bfloat16 = 2 bytes)
KV Cache Size (GB) = Total Bytes ÷ (1024³)
```

### Model Architecture Specifications

| Model | Hidden Size | Num Heads | Num Layers | KV Heads | Head Size | Dtype |
|-------|-------------|-----------|------------|----------|-----------|-------|
| llama-3.2-1b-instruct | 2048 | 32 | 16 | 8 | 64 | bfloat16 |
| llama-3.2-3b-instruct | 3072 | 24 | 28 | 8 | 128 | bfloat16 |
| tinyllama-1.1b-chat | 2048 | 32 | 22 | 4 | 64 | bfloat16 |
| granite-3.2-2b-instruct | 2048 | 32 | 40 | 8 | 64 | bfloat16 |
| qwen3-0.6b | 1024 | 16 | 28 | 8 | 64 | bfloat16 |
| qwen2.5-3b-instruct | 2048 | 16 | 36 | 2 | 128 | bfloat16 |
| gpt-oss-20b | 2880 | 64 | 24 | 8 | 45 | bfloat16* |

*gpt-oss-20b uses MXFP4 for MoE weights, bfloat16 for activations/KV cache

### KV Cache Sizes by Model and Workload

Calculated with **32 concurrent requests** (MAX concurrency across all workloads) and 25% safety margin (1.25x):

**Note**: All KV cache sizes are calculated for 32 concurrent requests to provide maximum headroom:
- **chat**: 32 concurrent (MAX)
- **rag**: 32 concurrent (MAX)
- **code**: 32 concurrent (MAX)
- **summarization**: 32 concurrent (MAX)
- **reasoning**: 32 concurrent (MAX)

#### Chat Workload (512:512, 1024 tokens)

| Model | Per-Request | 32 × 1.25x | Configured |
|-------|-------------|------------|------------|
| llama-3.2-1b-instruct | 0.0312 GB | 1.25 GB | 2 GiB |
| llama-3.2-3b-instruct | 0.1094 GB | 4.38 GB | 5 GiB |
| tinyllama-1.1b-chat | 0.0215 GB | 0.86 GB | 1 GiB |
| granite-3.2-2b-instruct | 0.0521 GB | 2.08 GB | 3 GiB |
| qwen3-0.6b | 0.0365 GB | 1.46 GB | 2 GiB |
| qwen2.5-3b-instruct | 0.0179 GB | 0.72 GB | 1 GiB |
| gpt-oss-20b | 0.0424 GB | 1.70 GB | 2 GiB |

#### RAG Workload (8192:512, 8704 tokens, 32 concurrent)

| Model | Per-Request | 32 × 1.25x | Configured |
|-------|-------------|------------|------------|
| llama-3.2-1b-instruct | 0.2656 GB | 10.6 GB | 11 GiB |
| llama-3.2-3b-instruct | 0.9297 GB | 37.2 GB | 38 GiB |
| tinyllama-1.1b-chat | 0.1828 GB | 7.31 GB | 8 GiB |
| granite-3.2-2b-instruct | 0.4427 GB | 17.7 GB | 18 GiB |
| qwen3-0.6b | 0.3102 GB | 12.4 GB | 13 GiB |
| qwen2.5-3b-instruct | 0.1520 GB | 6.08 GB | 7 GiB |
| gpt-oss-20b | 0.3604 GB | 14.4 GB | 15 GiB |

#### Code Generation Workload (1024:1024, 2048 tokens, 32 concurrent)

| Model | Per-Request | 32 × 1.25x | Configured |
|-------|-------------|------------|------------|
| llama-3.2-1b-instruct | 0.0625 GB | 2.50 GB | 3 GiB |
| llama-3.2-3b-instruct | 0.2188 GB | 8.75 GB | 9 GiB |
| tinyllama-1.1b-chat | 0.0430 GB | 1.72 GB | 2 GiB |
| granite-3.2-2b-instruct | 0.1042 GB | 4.17 GB | 5 GiB |
| qwen3-0.6b | 0.0730 GB | 2.92 GB | 3 GiB |
| qwen2.5-3b-instruct | 0.0358 GB | 1.43 GB | 2 GiB |
| gpt-oss-20b | 0.0848 GB | 3.39 GB | 4 GiB |

#### Summarization Workload (2048:256, 2304 tokens)

| Model | Per-Request | 32 × 1.25x | Configured |
|-------|-------------|------------|------------|
| llama-3.2-1b-instruct | 0.0703 GB | 2.81 GB | 3 GiB |
| llama-3.2-3b-instruct | 0.2461 GB | 9.84 GB | 9 GiB |
| tinyllama-1.1b-chat | 0.0483 GB | 1.93 GB | 2 GiB |
| granite-3.2-2b-instruct | 0.1172 GB | 4.69 GB | 4 GiB |
| qwen3-0.6b | 0.0821 GB | 3.28 GB | 3 GiB |
| qwen2.5-3b-instruct | 0.0403 GB | 1.61 GB | 2 GiB |
| gpt-oss-20b | 0.0954 GB | 3.81 GB | 3 GiB |

#### Reasoning Workload (256:2048, 2304 tokens, 32 concurrent)

| Model | Per-Request | 32 × 1.25x | Configured |
|-------|-------------|------------|------------|
| llama-3.2-1b-instruct | 0.0703 GB | 2.81 GB | 3 GiB |
| llama-3.2-3b-instruct | 0.2461 GB | 9.84 GB | 10 GiB |
| tinyllama-1.1b-chat | 0.0483 GB | 1.93 GB | 2 GiB |
| granite-3.2-2b-instruct | 0.1172 GB | 4.69 GB | 5 GiB |
| qwen3-0.6b | 0.0821 GB | 3.28 GB | 4 GiB |
| qwen2.5-3b-instruct | 0.0403 GB | 1.61 GB | 2 GiB |
| gpt-oss-20b | 0.0954 GB | 3.82 GB | 4 GiB |

### Usage in Test Automation

KV cache sizes are configured in `models/llm-models/model-matrix.yaml` under the `kv_cache_sizes` field for each model. The Ansible playbook automatically:

1. Loads the model configuration from the model matrix
2. Extracts the model-specific KV cache size for the workload being tested
3. Sets the `VLLM_CPU_KVCACHE_SPACE` environment variable accordingly
4. Falls back to workload defaults if model-specific values aren't found

Similarly, the `dtype` parameter is model-specific and defined in the model matrix, with a fallback to `auto` for automatic detection by vLLM.

**Test metadata captures**:
- `vllm_dtype`: Data type used (e.g., bfloat16)
- `vllm_kv_cache_size`: KV cache allocation (e.g., 2GiB)
- `vllm_max_model_len`: Maximum sequence length for workload
- `vllm_caching_mode`: Caching configuration (baseline/production)

---

## Model Matrix Format

Each model type has a `model-matrix.yaml` file defining:

```yaml
matrix:
  test_suite: "llm-models" | "embedding-models"

  models:
  - name: "model-short-name"
    full_name: "org/model-full-name"
    architecture_family: "Architecture Type"
    application_focus: "Use Case Focus"
    parameters: "Size"
    default_workloads: [...]
    test_suites: [...]

  workloads:
    workload_name:
      input_tokens: 512
      output_tokens: 256
      description: "Workload description"
```

---

## Adding New Models

## Prerequisites

1. Review the **Selection Principles** above to ensure model fits selection criteria
2. Verify model runs on CPU with vLLM (test locally first)
3. Determine which test suites should include this model
4. Identify which workloads are relevant for the model

## Steps for Adding LLM Models

1. Add model entry to `llm-models/model-matrix.yaml`
2. Define default workloads for the model (Chat, RAG, CodeGen, Summarization)
3. Specify test suite participation
4. Test with synchronous profile to verify functionality
5. Update this documentation if adding a new architecture family

### Example

```yaml
# Add to llm-models/model-matrix.yaml
llm_models:
- name: "new-model-name"
  full_name: "org/new-model-name"
  architecture_family: "New Architecture"
  application_focus: "Specific Use Case"
  parameters: "size"
  context_length: 8192
  default_workloads:
  - chat
  - rag
  test_suites:
  - concurrent-load
  - scalability
```

## Steps for Adding Embedding Models

1. Add model entry to `embedding-models/model-matrix.yaml`
2. Define embedding workload characteristics
3. Specify test suite participation
4. Test with `vllm bench serve --backend openai-embeddings`
5. Update this documentation if adding a new architecture family

## Evaluation Criteria

When evaluating whether to add a new model:

### Architecture Coverage
- Does this model represent a **new architecture family** not yet covered?
- Or is it a variant of an existing architecture we already test?

### Workload Relevance
- Does this model enable testing of a **specific workload** (e.g., long context, code generation)?
- Does it stress a particular inference phase (prefill vs. decode)?

### Resource Constraints
- Can this model run on typical CPU hardware (64GB+ RAM)?
- Does it fit within vLLM CPU inference capabilities?

### Evaluation Priority
- Is this a **baseline model** (simple, widely-used, core architecture)?
- Or a **specialized model** (complex, niche, deferred to later suites)?

---

## Related Documentation

- **[LLM Model Matrix](llm-models/model-matrix.yaml)** - Complete LLM model definitions
- **[Embedding Model Matrix](embedding-models/model-matrix.yaml)** - Complete embedding model definitions
- **[Embedding Models Extended Docs](embedding-models/embedding-models.md)** - Detailed embedding testing documentation
- **[Test Suites](../tests/)** - How models are tested
- **[Methodology](../docs/methodology/overview.md)** - Overall testing approach
