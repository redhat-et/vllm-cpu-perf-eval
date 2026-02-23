# Models Directory

This directory contains centralized model definitions and selection documentation used across all test suites.

## Overview

Models are organized by type, with each type having its own model matrix and documentation:

- **[LLM Models](llm-models/)** - Large Language Models (decoder-only architectures)
- **[Embedding Models](embedding-models/)** - Embedding models (encoder-only architectures)
- **[Model Selection](MODEL-SELECTION.md)** - Strategy and rationale for model selection

## Structure

```text
models/
├── MODEL-SELECTION.md           # Model selection strategy and rationale
├── llm-models/                  # Large Language Models
│   ├── model-matrix.yaml        # LLM model definitions and test mappings
│   └── llm-models.md            # LLM-specific documentation
├── embedding-models/            # Embedding Models
│   ├── model-matrix.yaml        # Embedding model definitions
│   └── embedding-models.md      # Embedding-specific documentation
└── models.md                    # This file
```

## Model Selection Principles

Models are selected based on **architectural coverage** rather than popularity or size alone:

1. **Representative Coverage**: Each model represents a unique architecture family
2. **Workload Relevance**: Models stress different inference phases (prefill vs. decode)
3. **Reusability**: Same models are tested across multiple test suites for comparison
4. **Resource Constraints**: All models must run on typical CPU hardware (64GB+ RAM)

See [MODEL-SELECTION.md](MODEL-SELECTION.md) for detailed selection criteria and rationale.

## LLM Models

### Current Models (8 total)

| Architecture | Model | Parameters | Primary Focus |
|--------------|-------|------------|---------------|
| Llama 3 | Llama-3.2-1B-Instruct | 1.2B | Prefill-Heavy |
| Llama 3 | Llama-3.2-3B-Instruct | 3.2B | Prefill-Heavy |
| Llama 2 | TinyLlama-1.1B-Chat | 1.1B | Balanced (Small-Scale) |
| OPT | facebook/opt-125m | 125M | Decode-Heavy |
| OPT | facebook/opt-1.3b | 1.3B | Decode-Heavy |
| Granite | granite-3.2-2b-instruct | 2B | Balanced (Enterprise) |
| Qwen 3 | Qwen/Qwen3-0.6B | 0.6B | Balanced (Efficient) |
| Qwen 2.5 | Qwen/Qwen2.5-3B-Instruct | 3B | Balanced (Efficient) |

**Workloads Tested**: Chat, RAG, CodeGen, Summarization

See [llm-models/llm-models.md](llm-models/llm-models.md) for detailed LLM documentation.

## Embedding Models

### Current Models (2 total)

| Architecture | Model | Parameters | Primary Focus |
|--------------|-------|------------|---------------|
| MiniLM/BERT | granite-embedding-english-r2 | ~110M | English Dense Embedding |
| XLM-RoBERTa | granite-embedding-278m-multilingual | ~278M | Multilingual Embedding |

**Workloads Tested**: Embedding (512:1)

See [embedding-models/embedding-models.md](embedding-models/embedding-models.md) for detailed embedding documentation.

## Model Reuse Across Test Suites

Models are **reused across test suites** to enable:

- **Longitudinal comparison**: Same model tested under different conditions
- **Configuration impact**: Understand how settings affect the same model
- **Comprehensive profiling**: Full performance characterization across dimensions

### Test Suite Coverage

- **Test Suite 1 (Concurrent Load)**: 5 LLM models + 2 embedding models
- **Test Suite 2 (Scalability)**: 8 LLM models + 2 embedding models
- **Test Suite 3 (Resource Contention)**: Planned - same models under resource constraints
- **Test Suite 4 (Configuration Tuning)**: Future - same models with config variations

## Deferred Models

The following model types are **deferred to later test suites**:

- **Mixture of Experts (MoE)**: Mixtral-8x7B - requires specialized configuration testing
- **State Space Models (SSM)**: Mamba-1.4B - non-transformer architecture
- **Encoder-Decoder**: Flan-T5 - dual-stack architecture
- **Advanced Attention**: Codestral-7B - sliding window attention

These models introduce complexity that requires dedicated evaluation beyond baseline testing.

See [MODEL-SELECTION.md](MODEL-SELECTION.md#models-deferred-to-later-evaluation) for rationale.

## Model Matrix Format

Each model type has a \`model-matrix.yaml\` file defining:

\`\`\`yaml
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
\`\`\`

## Adding a New Model

### Prerequisites

1. Review [MODEL-SELECTION.md](MODEL-SELECTION.md) to ensure model fits selection criteria
2. Verify model runs on CPU with vLLM (test locally first)
3. Determine which test suites should include this model

### Steps

1. Add model entry to appropriate \`model-matrix.yaml\`
2. Define default workloads for the model
3. Update model-specific documentation (llm-models.md or embedding-models.md)
4. Test with synchronous profile to verify functionality
5. Add to test suite configurations

### Example

\`\`\`yaml
Add to llm-models/model-matrix.yaml
llm_models:
- name: "new-model-name"
    full_name: "org/new-model-name"
    architecture_family: "New Architecture"
    application_focus: "Specific Use Case"
    parameters: "size"
    default_workloads:
  - chat
  - rag
    test_suites:
  - concurrent-load
  - scalability
\`\`\`

## Related Documentation

- **[Model Selection Strategy](MODEL-SELECTION.md)** - Why these models were chosen
- **[LLM Models Documentation](llm-models/llm-models.md)** - LLM-specific details
- **[Embedding Models Documentation](embedding-models/embedding-models.md)** - Embedding-specific details
- **[Test Suites](../tests/)** - How models are tested
- **[Methodology](../docs/methodology/overview.md)** - Overall testing approach
