# Model Selection Strategy

This document explains the rationale and methodology for selecting models across all test suites in the vLLM CPU Performance Evaluation framework.

## Selection Principles

The benchmarking strategy is designed to ensure **maximum architectural coverage** for effective CPU inference testing on a vLLM server. This is achieved by:

1. **Selecting a representative model from each unique underlying architectural family** present in the original list of proposed models
2. **Adding essential architectures** that stress specific inference phases (Decode, Prefill, Balanced) relevant to real-world applications (Code Gen, RAG)
3. **Minimizing redundancy** while maintaining comprehensive coverage

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

## Adding New Models

When adding new models, consider:

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

## Model Matrix Organization

Models are organized by type in the `models/` directory:

```
models/
├── llm-models/
│   ├── model-matrix.yaml      # LLM model definitions
│   └── llm-models.md           # LLM-specific documentation
├── embedding-models/
│   ├── model-matrix.yaml       # Embedding model definitions
│   └── embedding-models.md     # Embedding-specific documentation
└── MODEL-SELECTION.md          # This file
```

Each `model-matrix.yaml` defines:
- Model metadata (architecture, parameters, focus area)
- Default test scenarios
- Configuration parameters
- Test case mappings

## References

- [LLM Models Documentation](llm-models/llm-models.md)
- [Embedding Models Documentation](embedding-models/embedding-models.md)
- [Test Suite Documentation](../tests/)
- [Methodology Overview](../docs/methodology/overview.md)
