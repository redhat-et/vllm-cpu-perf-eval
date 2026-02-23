# LLM Models

This directory contains the model matrix and definitions for Large Language Model (LLM) testing across all test suites.

## Models Under Test

The test suite focuses on representative models from different architecture families to ensure comprehensive CPU inference evaluation:

### Decoder-Only Models

| Architecture Family | Representative Model | Application Focus | Parameters | Context Length |
|---------------------|---------------------|-------------------|------------|----------------|
| Llama 3 Decoder | Llama-3.2-1B-Instruct | Prefill-Heavy (Baseline) | 1.2B | 8192 |
| Llama 3 Decoder | Llama-3.2-3B-Instruct | Prefill-Heavy (Baseline) | 3.2B | 8192 |
| Llama 2 Decoder | TinyLlama-1.1B-Chat-v1.0 | Prefill/Decode (Small-Scale) | 1.1B | 2048 |
| Traditional OPT Decoder | facebook/opt-125m | Decode-Heavy (Legacy Baseline) | 125M | 2048 |
| Traditional OPT Decoder | facebook/opt-1.3b | Decode-Heavy (Legacy Baseline) | 1.3B | 2048 |
| IBM Granite Decoder | granite-3.2-2b-instruct | Balanced (Enterprise Baseline) | 2B | 4096 |
| Qwen 3 Decoder | Qwen/Qwen3-0.6B | Balanced (High-Efficiency) | 0.6B | 8192 |
| Qwen 2.5 Decoder | Qwen/Qwen2.5-3B-Instruct | Balanced (High-Efficiency) | 3B | 8192 |

## Model Selection Rationale

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

## Workload Coverage

Each model is tested across workloads that stress different inference phases:

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

## Test Suite Usage

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

## Inference Characteristics

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

## Model Configuration

All models use baseline configuration for fair comparison:

```yaml
dtype: bfloat16
quantization: false  # Full precision
kv_cache: auto       # vLLM auto-sizing
affinity: FULL       # All physical cores
```

Advanced configurations (quantization, custom KV cache) are tested in Test Suite 4 (Configuration Tuning).

## Adding New LLM Models

When adding a new LLM model:

1. **Check Architecture Coverage**: Does it represent a new architecture family?
2. **Verify Resource Fit**: Can it run on 64GB+ RAM with CPU inference?
3. **Define Workloads**: Which workloads (Chat, RAG, CodeGen, Summarization) are relevant?
4. **Update model-matrix.yaml**: Add model definition with metadata
5. **Test Baseline**: Run synchronous test to verify functionality

See [MODEL-SELECTION.md](../MODEL-SELECTION.md) for detailed selection criteria.

## Related Documentation

- [Model Selection Strategy](../MODEL-SELECTION.md)
- [Embedding Models](../embedding-models/embedding-models.md)
- [Test Suite Documentation](../../tests/)
- [Methodology Overview](../../docs/methodology/overview.md)
