# KV Cache Size Calculations for LLM Models

## Performance Optimization Strategy

**These configurations are optimized for ABSOLUTE BEST PERFORMANCE per workload.**

Each workload uses `--max-model-len` set to the minimum required for that specific workload:
- Minimizes KV cache memory allocation
- Reduces memory bandwidth pressure
- Optimizes cache locality
- **Result**: Best possible throughput and latency for each workload type

**Important**: These are workload-optimized settings. Production deployments may use larger `max-model-len` values for flexibility, which would require larger KV cache and may show different performance characteristics.

## Formula
```
Total Elements = 2 × num_hidden_layers × tokens × num_key_value_heads × head_size
Where: head_size = hidden_size ÷ num_attention_heads
Total Bytes = Total Elements × dtype_size (bfloat16 = 2 bytes)
KV Cache Size (GB) = Total Bytes ÷ (1024³)
```

## Data Type Configuration
All models in this test suite use **bfloat16** precision for KV cache and activations:
- bfloat16 = 2 bytes per element
- Provides good balance between memory efficiency and numerical accuracy
- Model-specific dtype is defined in `models/llm-models/model-matrix.yaml`
- Fallback default is `auto` (vLLM auto-detects optimal dtype)

**Note**: The `gpt-oss-20b` model uses MXFP4 quantization for MoE weights, but KV cache still uses bfloat16.

## Model Architecture Specifications

| Model | Hidden Size | Num Heads | Num Layers | KV Heads | Head Size | Dtype |
|-------|-------------|-----------|------------|----------|-----------|-------|
| llama-3.2-1b-instruct | 2048 | 32 | 16 | 8 | 64 | bfloat16 |
| llama-3.2-3b-instruct | 3072 | 24 | 28 | 8 | 128 | bfloat16 |
| tinyllama-1.1b-chat | 2048 | 32 | 22 | 4 | 64 | bfloat16 |
| opt-125m | 768 | 12 | 12 | 12 | 64 | bfloat16 |
| opt-1.3b | 2048 | 32 | 24 | 32 | 64 | bfloat16 |
| granite-3.2-2b-instruct | 2048 | 32 | 40 | 8 | 64 | bfloat16 |
| qwen3-0.6b | 1024 | 16 | 28 | 8 | 64 | bfloat16 |
| qwen2.5-3b-instruct | 2048 | 16 | 36 | 2 | 128 | bfloat16 |
| gpt-oss-20b | 2880 | 64 | 24 | 8 | 45 | bfloat16* |

*gpt-oss-20b uses MXFP4 for MoE weights, bfloat16 for activations/KV cache

## Workload Sequence Lengths

| Workload | Input Tokens | Output Tokens | Total Tokens | Rationale |
|----------|--------------|---------------|--------------|-----------|
| chat | 512 | 512 | 1024 | Primary working point |
| rag | 8192 | 512 | 8704 | ISL-heavy is fine, keep OSL short |
| code | 1024 | 1024 | 2048 | 1024 OSL is near practical ceiling on CPU |
| summarization | 2048 | 256 | 2304 | Short output is realistic and achievable |
| reasoning | 256 | 2048 | 2304 | New workload for chain-of-thought reasoning |
| chat_var | 512 (avg) | 512 (avg) | 1024 | Same as chat |
| code_var | 1024 (avg) | 1024 (avg) | 2048 | Same as code |

## Per-Request KV Cache Size (GB)

### llama-3.2-1b-instruct (layers=16, kv_heads=8, head_size=64)
- chat (1024 tokens): 0.0312 GB per request
- rag (8704 tokens): 0.2656 GB per request
- code (2048 tokens): 0.0625 GB per request
- summarization (2304 tokens): 0.0703 GB per request
- reasoning (2304 tokens): 0.0703 GB per request

### llama-3.2-3b-instruct (layers=28, kv_heads=8, head_size=128)
- chat (1024 tokens): 0.1094 GB per request
- rag (8704 tokens): 0.9297 GB per request
- code (2048 tokens): 0.2188 GB per request
- summarization (2304 tokens): 0.2461 GB per request
- reasoning (2304 tokens): 0.2461 GB per request

### tinyllama-1.1b-chat (layers=22, kv_heads=4, head_size=64)
- chat (1024 tokens): 0.0215 GB per request
- rag (8704 tokens): 0.1828 GB per request
- code (2048 tokens): 0.0430 GB per request
- summarization (2304 tokens): 0.0483 GB per request
- reasoning (2304 tokens): 0.0483 GB per request

### opt-125m (layers=12, kv_heads=12, head_size=64)
- chat (1024 tokens): 0.0226 GB per request
- rag (8704 tokens): 0.1920 GB per request
- code (2048 tokens): 0.0452 GB per request
- summarization (2304 tokens): 0.0509 GB per request
- reasoning (2304 tokens): 0.0509 GB per request

### opt-1.3b (layers=24, kv_heads=32, head_size=64)
- chat (1024 tokens): 0.0477 GB per request
- rag (8704 tokens): 0.4053 GB per request
- code (2048 tokens): 0.0954 GB per request
- summarization (2304 tokens): 0.1074 GB per request
- reasoning (2304 tokens): 0.1074 GB per request

### granite-3.2-2b-instruct (layers=40, kv_heads=8, head_size=64)
- chat (1024 tokens): 0.0521 GB per request
- rag (8704 tokens): 0.4427 GB per request
- code (2048 tokens): 0.1042 GB per request
- summarization (2304 tokens): 0.1172 GB per request
- reasoning (2304 tokens): 0.1172 GB per request

### qwen3-0.6b (layers=28, kv_heads=8, head_size=64)
- chat (1024 tokens): 0.0365 GB per request
- rag (8704 tokens): 0.3102 GB per request
- code (2048 tokens): 0.0730 GB per request
- summarization (2304 tokens): 0.0821 GB per request
- reasoning (2304 tokens): 0.0821 GB per request

### qwen2.5-3b-instruct (layers=36, kv_heads=2, head_size=128)
- chat (1024 tokens): 0.0179 GB per request
- rag (8704 tokens): 0.1520 GB per request
- code (2048 tokens): 0.0358 GB per request
- summarization (2304 tokens): 0.0403 GB per request
- reasoning (2304 tokens): 0.0403 GB per request

### gpt-oss-20b (layers=24, kv_heads=8, head_size=45)
- chat (1024 tokens): 0.0424 GB per request
- rag (8704 tokens): 0.3604 GB per request
- code (2048 tokens): 0.0848 GB per request
- summarization (2304 tokens): 0.0954 GB per request
- reasoning (2304 tokens): 0.0954 GB per request

## Recommended KV Cache Sizes for Concurrent Load Testing

Calculated with concurrency targets and 25% safety margin (1.25x):
- chat: 32 concurrent requests
- rag: 16 concurrent (large context)
- code: 24 concurrent
- summarization: 32 concurrent
- reasoning: 24 concurrent

### chat workload (512:512, 1024 tokens, 32 concurrent)

| Model | Per-Request (GB) | 32 × 1.25x | Recommended |
|-------|------------------|------------|-------------|
| llama-3.2-1b-instruct | 0.0312 | 1.25 | **2 GiB** |
| llama-3.2-3b-instruct | 0.1094 | 4.38 | **5 GiB** |
| tinyllama-1.1b-chat | 0.0215 | 0.86 | **1 GiB** |
| opt-125m | 0.0226 | 0.90 | **1 GiB** |
| opt-1.3b | 0.0477 | 1.91 | **2 GiB** |
| granite-3.2-2b-instruct | 0.0521 | 2.08 | **3 GiB** |
| qwen3-0.6b | 0.0365 | 1.46 | **2 GiB** |
| qwen2.5-3b-instruct | 0.0179 | 0.72 | **1 GiB** |
| gpt-oss-20b | 0.0424 | 1.70 | **2 GiB** |

### rag workload (8192:512, 8704 tokens, 16 concurrent)

| Model | Per-Request (GB) | 16 × 1.25x | Recommended |
|-------|------------------|------------|-------------|
| llama-3.2-1b-instruct | 0.2656 | 5.31 | **5 GiB** |
| llama-3.2-3b-instruct | 0.9297 | 18.59 | **18 GiB** |
| tinyllama-1.1b-chat | 0.1828 | 3.66 | **3 GiB** |
| opt-125m | 0.1920 | 3.84 | **3 GiB** |
| opt-1.3b | 0.4053 | 8.11 | **7 GiB** |
| granite-3.2-2b-instruct | 0.4427 | 8.85 | **9 GiB** |
| qwen3-0.6b | 0.3102 | 6.20 | **6 GiB** |
| qwen2.5-3b-instruct | 0.1520 | 3.04 | **3 GiB** |
| gpt-oss-20b | 0.3604 | 7.21 | **7 GiB** |

### code workload (1024:1024, 2048 tokens, 24 concurrent)

| Model | Per-Request (GB) | 24 × 1.25x | Recommended |
|-------|------------------|------------|-------------|
| llama-3.2-1b-instruct | 0.0625 | 1.88 | **2 GiB** |
| llama-3.2-3b-instruct | 0.2188 | 6.56 | **5 GiB** |
| tinyllama-1.1b-chat | 0.0430 | 1.29 | **1 GiB** |
| opt-125m | 0.0452 | 1.36 | **2 GiB** |
| opt-1.3b | 0.0954 | 2.86 | **4 GiB** |
| granite-3.2-2b-instruct | 0.1042 | 3.13 | **3 GiB** |
| qwen3-0.6b | 0.0730 | 2.19 | **2 GiB** |
| qwen2.5-3b-instruct | 0.0358 | 1.07 | **2 GiB** |
| gpt-oss-20b | 0.0848 | 2.54 | **2 GiB** |

### summarization workload (2048:256, 2304 tokens, 32 concurrent)

| Model | Per-Request (GB) | 32 × 1.25x | Recommended |
|-------|------------------|------------|-------------|
| llama-3.2-1b-instruct | 0.0703 | 2.81 | **3 GiB** |
| llama-3.2-3b-instruct | 0.2461 | 9.84 | **9 GiB** |
| tinyllama-1.1b-chat | 0.0483 | 1.93 | **2 GiB** |
| opt-125m | 0.0509 | 2.04 | **2 GiB** |
| opt-1.3b | 0.1074 | 4.30 | **4 GiB** |
| granite-3.2-2b-instruct | 0.1172 | 4.69 | **4 GiB** |
| qwen3-0.6b | 0.0821 | 3.28 | **3 GiB** |
| qwen2.5-3b-instruct | 0.0403 | 1.61 | **2 GiB** |
| gpt-oss-20b | 0.0954 | 3.81 | **3 GiB** |

### reasoning workload (256:2048, 2304 tokens, 24 concurrent)

| Model | Per-Request (GB) | 24 × 1.25x | Recommended |
|-------|------------------|------------|-------------|
| llama-3.2-1b-instruct | 0.0703 | 2.11 | **2 GiB** |
| llama-3.2-3b-instruct | 0.2461 | 7.38 | **6 GiB** |
| tinyllama-1.1b-chat | 0.0483 | 1.45 | **2 GiB** |
| opt-125m | 0.0509 | 1.53 | **2 GiB** |
| opt-1.3b | 0.1074 | 3.22 | **3 GiB** |
| granite-3.2-2b-instruct | 0.1172 | 3.52 | **3 GiB** |
| qwen3-0.6b | 0.0821 | 2.46 | **2 GiB** |
| qwen2.5-3b-instruct | 0.0403 | 1.21 | **2 GiB** |
| gpt-oss-20b | 0.0954 | 2.86 | **2 GiB** |

## Usage in Test Automation

The calculated KV cache sizes are configured in `models/llm-models/model-matrix.yaml` under the `kv_cache_sizes` field for each model. The Ansible playbook (`automation/test-execution/ansible/roles/vllm_server/tasks/start-llm.yml`) automatically:

1. Loads the model configuration from the model matrix
2. Extracts the model-specific KV cache size for the workload being tested
3. Sets the `VLLM_CPU_KVCACHE_SPACE` environment variable accordingly
4. Falls back to workload defaults if model-specific values aren't found

Similarly, the `dtype` parameter is now model-specific and defined in the model matrix, with a fallback to `auto` for automatic detection by vLLM.
