# Models Directory

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
| Traditional OPT Decoder | facebook/opt-125m | Decode-Heavy (Legacy Baseline) | 125M | Fast decode, minimal prefill, legacy baseline |
| IBM Granite Decoder | granite-3.2-2b-instruct | Balanced (Enterprise Baseline) | 2B | Enterprise-grade, balanced prefill/decode |
| Qwen 3 Decoder | Qwen/Qwen3-0.6B | Balanced (High-Efficiency) | 0.6B | Efficient architecture, strong performance/size ratio |

### Embedding Models (Encoder-Only)

| Architecture Family | Representative Model | Key Application Focus | Parameters | Rationale |
|---------------------|---------------------|----------------------|------------|-----------|
| MiniLM/BERT (English Dense) | granite-embedding-english-r2 | Encoder-Only (Fastest Baseline) | ~110M | Fast English-only embedding, baseline performance |
| XLM-RoBERTa (Multilingual Dense) | granite-embedding-278m-multilingual | Encoder-Only (Multilingual) | ~278M | Multilingual support, broader language coverage |

## Workload Coverage

Each model is tested across workloads that stress different aspects of inference:

### LLM Workloads

- **Chat (512:256)**: Balanced prefill/decode, typical conversational AI
- **RAG (4096:512)**: Long context prefill, retrieval-augmented generation
- **CodeGen (512:4K)**: Long output decode, code generation scenarios
- **Summarization (1024:256)**: Medium context, summarization tasks

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

## Current LLM Models (8 total)

| Architecture | Model | Parameters | Primary Focus | Context Length |
|--------------|-------|------------|---------------|----------------|
| Llama 3 | Llama-3.2-1B-Instruct | 1.2B | Prefill-Heavy | 8192 |
| Llama 3 | Llama-3.2-3B-Instruct | 3.2B | Prefill-Heavy | 8192 |
| Llama 2 | TinyLlama-1.1B-Chat | 1.1B | Balanced (Small-Scale) | 2048 |
| OPT | facebook/opt-125m | 125M | Decode-Heavy | 2048 |
| OPT | facebook/opt-1.3b | 1.3B | Decode-Heavy | 2048 |
| Granite | granite-3.2-2b-instruct | 2B | Balanced (Enterprise) | 4096 |
| Qwen 3 | Qwen/Qwen3-0.6B | 0.6B | Balanced (Efficient) | 8192 |
| Qwen 2.5 | Qwen/Qwen2.5-3B-Instruct | 3B | Balanced (Efficient) | 8192 |

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

### OPT Family
- **Legacy baseline** for comparison with modern architectures
- **Fast decode, minimal prefill** - stresses decode phase
- **Two sizes** (125M, 1.3B) for range testing
- **Well-documented** performance characteristics

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

## LLM Workload Details

### Chat (512:256)
- **Input**: 512 tokens (conversation history)
- **Output**: 256 tokens (response)
- **Focus**: Balanced prefill/decode
- **Use Case**: Conversational AI, chatbots

### RAG (4096:512)
- **Input**: 4096 tokens (retrieved documents + query)
- **Output**: 512 tokens (answer)
- **Focus**: Long context prefill
- **Use Case**: Document Q&A, knowledge retrieval

### CodeGen (512:4096)
- **Input**: 512 tokens (code prompt/context)
- **Output**: 4096 tokens (generated code)
- **Focus**: Long output decode
- **Use Case**: Code completion, generation

### Summarization (1024:256)
- **Input**: 1024 tokens (document to summarize)
- **Output**: 256 tokens (summary)
- **Focus**: Medium context, balanced
- **Use Case**: Document summarization

## LLM Inference Characteristics

### Prefill-Heavy Models
Models that excel at processing long input contexts:
- Llama-3.2-1B-Instruct
- Llama-3.2-3B-Instruct

**Best for**: RAG, long context Q&A

### Decode-Heavy Models
Models optimized for fast token generation:
- facebook/opt-125m
- facebook/opt-1.3b

**Best for**: Chat, real-time responses

### Balanced Models
Models with good prefill and decode performance:
- granite-3.2-2b-instruct
- Qwen/Qwen3-0.6B
- Qwen/Qwen2.5-3B-Instruct
- TinyLlama-1.1B-Chat

**Best for**: General-purpose deployment, mixed workloads

## LLM Test Suite Coverage

### Test Suite 1: Concurrent Load
Tests all models at concurrency levels: **{8, 16, 32, 64, 96, 128}**

**Participating Models:**
- Llama-3.2-1B-Instruct (Chat, RAG)
- TinyLlama-1.1B-Chat (Chat)
- facebook/opt-125m (Chat, Summarization)
- granite-3.2-2b-instruct (Chat, RAG)
- Qwen/Qwen3-0.6B (Chat, CodeGen)

### Test Suite 2: Scalability
Uses sweep, synchronous, and Poisson profiles

**Participating Models:**
- All models from Concurrent Load suite
- Plus: Llama-3.2-3B-Instruct, opt-1.3b, Qwen2.5-3B-Instruct

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

All models use baseline configuration for fair comparison:

```yaml
dtype: bfloat16
quantization: false  # Full precision
kv_cache: auto       # vLLM auto-sizing (1GiB for embeddings)
affinity: FULL       # All physical cores
```

Advanced configurations (quantization, custom KV cache) are tested in Test Suite 4 (Configuration Tuning).

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
