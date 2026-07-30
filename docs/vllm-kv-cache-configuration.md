# vLLM CPU Performance: Understanding KV Cache, max_model_len, and block_size

## Executive Summary

Three configuration parameters have **critical impact** on vLLM CPU inference performance:

| Parameter | Impact | Default | CPU Recommendation |
|-----------|--------|---------|-------------------|
| `--max-model-len` | Memory allocation, throughput, latency | Model's max context | **Set to workload needs** (2048-8192) |
| `VLLM_CPU_KVCACHE_SPACE` | KV cache memory budget | 4 GiB | **Scale with cores** (8-40 GiB) |
| `--block-size` | Memory alignment, attention perf | 128 | **Always use 128** (or multiple of 32) |

**Key Takeaway:** Properly configuring these parameters can improve:
- **Throughput:** 2-3x (via better memory utilization)
- **Latency:** 10-30% (via cache alignment)
- **Concurrency:** 2-4x (via appropriate KV cache sizing)

---

## Table of Contents

1. [Parameter Overview](#parameter-overview)
2. [max_model_len: Context Length Configuration](#max_model_len-context-length-configuration)
3. [KV Cache Size: Memory Budget](#kv-cache-size-memory-budget)
4. [block_size: Cache Alignment](#block_size-cache-alignment)
5. [Practical Recommendations](#practical-recommendations)
6. [Common Pitfalls](#common-pitfalls)
7. [Quick Reference](#quick-reference)
8. [References](#references)

---

## Parameter Overview

### What is the KV Cache?

The **Key-Value (KV) cache** stores attention keys and values for previously processed tokens, enabling efficient autoregressive generation:

```
Without KV cache:     Token 1 → recompute all    (O(n²) for n tokens)
With KV cache:        Token 1 → cache → Token 2  (O(n) for n tokens)
```

**Memory formula:**
```
KV_cache_memory = 2 × num_layers × num_kv_heads × head_size × max_tokens × dtype_bytes
```

For example, **Llama-3.2-1B** with 8192 context (bfloat16):
```
= 2 × 16 × 8 × 256 × 8192 × 2 bytes
= ~1.07 GB per request at full context
```

### Three Pillars of CPU Performance

| Parameter | Effect | Tuning guidance |
| --- | --- | --- |
| `max_model_len` | Maximum context per request | Higher = more memory per request; lower = more concurrent requests |
| KV cache size | Total memory budget for all requests | Higher = more concurrent requests; limited by available RAM |
| `block_size` | Cache alignment and access pattern | Must be a multiple of 32 for CPU; default 128 is optimal |

---

## max_model_len: Context Length Configuration

### How max_model_len Works

`--max-model-len` sets the **maximum sequence length** (prompt + output) that vLLM will process.

**Command line:**
```bash
vllm serve model-name \
  --max-model-len 4096
```

**Default behavior:**
- If not specified: Uses model's native maximum context length
- `--max-model-len -1` or `auto`: Auto-selects largest that fits in memory

### Performance Impact of max_model_len

#### 1. **Memory Allocation (PRIMARY IMPACT)**

KV cache memory is **pre-allocated** based on `max_model_len`:

```python
# From vLLM source (simplified)
kv_cache_blocks = (max_model_len × max_num_seqs) / block_size
total_kv_memory = kv_cache_blocks × block_memory_size
```

**Example:** Chat workload (512 input + 512 output = 1024 tokens needed)

| max_model_len | KV Cache Used | Wasted Memory | Max Concurrent (20 GiB) |
|---------------|---------------|---------------|------------------------|
| 2048          | ~1 GB/req     | ~50%          | ~20 requests           |
| 4096          | ~2 GB/req     | ~75%          | ~10 requests           |
| 8192          | ~4 GB/req     | ~87%          | ~5 requests            |
| 32768         | ~16 GB/req    | ~97%          | ~1 request             |

**Observation:** Using `32768` when you only need `1024` tokens **wastes 97% of memory** and **reduces concurrency by 20x**.

### Recommendations for max_model_len

**Principle:** Set to **actual workload needs + 20-50% headroom**

| Use Case | Token Needs | Recommended max_model_len | Reasoning |
|----------|-------------|--------------------------|-----------|
| **Chat** | 512 + 512 = 1024 | 2048 | 2x headroom for variance |
| **RAG** | 7680 + 512 = 8192 | 8192 | Exact fit (no room to waste) |
| **Code Gen** | 1024 + 1024 = 2048 | 4096 | 2x headroom for complex code |
| **Summarization** | 2048 + 256 = 2304 | 4096 | ~1.7x headroom |
| **Long Context** | Variable up to 32K | 32768 | Only if actually needed |

---

## KV Cache Size: Memory Budget

### How KV Cache Size Works

`VLLM_CPU_KVCACHE_SPACE` (environment variable) or `--kv-cache-memory-bytes` sets the **total memory budget** for KV cache.

**Configuration methods:**

```bash
# Method 1: Environment variable (CPU-specific, legacy)
export VLLM_CPU_KVCACHE_SPACE=16  # 16 GiB
vllm serve model-name

# Method 2: Command line (platform-agnostic)
vllm serve model-name \
  --kv-cache-memory-bytes $((16 * 1024 * 1024 * 1024))  # 16 GiB in bytes
```

**Default:** 4 GiB (for CPU)

### Recommendations for KV Cache Size

**System-based sizing:**

| System RAM | vLLM Cores | Recommended KV Cache | Max Models |
|------------|-----------|---------------------|-----------|
| 16 GB      | 8         | 4-8 GiB             | 1B-3B     |
| 32 GB      | 16        | 12-20 GiB           | 1B-8B     |
| 64 GB      | 32        | 24-40 GiB           | 1B-13B    |
| 128 GB     | 64        | 48-80 GiB           | 1B-30B    |
| 256 GB+    | 96+       | 80-160 GiB          | Any       |

---

## block_size: Cache Alignment

### How block_size Works

`--block-size` sets the **granularity** of KV cache block allocation.

**Command line:**
```bash
vllm serve model-name \
  --block-size 128
```

**Default:** 128 (for CPU)

### Performance Impact of block_size

#### 1. **Memory Alignment (CRITICAL FOR CPU)**

CPU SIMD operations (AVX2/AVX512/NEON) require **aligned memory access**:

From vLLM CPU platform:

```python
if cache_config.block_size % 32 != 0:
    logger.warning(
        "CPU backend prefers block_size is multiples of 32, "
        "otherwise the performance is not optimized."
    )
```

**Why multiples of 32?**
- **AVX2:** 256-bit registers = 32 bytes (16 × bfloat16)
- **AVX512:** 512-bit registers = 64 bytes (32 × bfloat16)
- **NEON:** 128-bit registers = 16 bytes (8 × bfloat16)

**Block size 128 = 4 × 32**, optimal for all CPU architectures.

### Recommendations for block_size

**Simple rule:** **Always use `--block-size=128` for CPU**

| Scenario | Recommended | Alternative | Rationale |
|----------|-------------|-------------|-----------|
| **Intel x86 (AVX2/AVX512/AMX)** | 128 | 64, 32 | Optimal alignment |
| **ARM (NEON)** | 128 | 64, 32 | Multiple of 16 |
| **RISC-V (RVV)** | 128 | 64, 32 | Vector alignment |
| **Prefix caching enabled** | 128 | 64 | Balance reuse/perf |
| **Memory constrained** | 128 | 64 | Minimal waste |

**Configuration:**
```bash
# ✅ RECOMMENDED: Always use for CPU
vllm serve model-name \
  --block-size 128

# ❌ AVOID: Not multiple of 32
vllm serve model-name \
  --block-size 100
# WARNING: "CPU backend prefers block_size is multiples of 32"
```

---

## Practical Recommendations

### Quick Reference Table

**For different CPU configurations:**

| CPU Cores | RAM   | Model Size | max_model_len | KV Cache | block_size | Expected Concurrency |
|-----------|-------|------------|---------------|----------|------------|---------------------|
| 8         | 16GB  | 1-3B       | 2048          | 4-8 GB   | 128        | 2-4                 |
| 16        | 32GB  | 1-8B       | 2048-4096     | 12-20 GB | 128        | 6-10                |
| 32        | 64GB  | 1-13B      | 2048-4096     | 24-40 GB | 128        | 12-20               |
| 64        | 128GB | 1-30B      | 2048-8192     | 48-80 GB | 128        | 24-40               |
| 96+       | 256GB | Any        | 4096-16384    | 80-160GB | 128        | 40-80               |

### Workload-Specific Presets

#### Chat Applications (512:512 tokens)
```bash
vllm serve model-name \
  --max-model-len 2048 \
  --block-size 128 \
  --kv-cache-memory-bytes $((16 * 1024 * 1024 * 1024))  # 16 GB
```

#### RAG Applications (7680:512 tokens)
```bash
vllm serve model-name \
  --max-model-len 8192 \
  --block-size 128 \
  --kv-cache-memory-bytes $((32 * 1024 * 1024 * 1024))  # 32 GB
```

#### Code Generation (1024:1024 tokens)
```bash
vllm serve model-name \
  --max-model-len 4096 \
  --block-size 128 \
  --kv-cache-memory-bytes $((20 * 1024 * 1024 * 1024))  # 20 GB
```

#### Document Summarization (2048:256 tokens)
```bash
vllm serve model-name \
  --max-model-len 4096 \
  --block-size 128 \
  --kv-cache-memory-bytes $((16 * 1024 * 1024 * 1024))  # 16 GB
```

### Ansible/Automation Configuration

Example for test automation frameworks:

```yaml
# test-workloads.yml
workloads:
  chat:
    vllm_args:
      - "--dtype=bfloat16"
      - "--max-model-len=2048"
      - "--block-size=128"              # CRITICAL: Always include
      - "--no-enable-prefix-caching"    # For baseline testing
    kv_cache_space: "16GiB"

  rag:
    vllm_args:
      - "--dtype=bfloat16"
      - "--max-model-len=8192"
      - "--block-size=128"              # CRITICAL: Always include
      - "--no-enable-prefix-caching"
    kv_cache_space: "32GiB"
```

---

## Common Pitfalls

### Pitfall 1: Oversized max_model_len

**Problem:**
```bash
# Chat workload (512:512) with 32K context
vllm serve model --max-model-len 32768
```

**Impact:**
- 16x memory waste
- 1/16th throughput
- Unnecessary latency

**Solution:**
```bash
# Right-size to workload
vllm serve model --max-model-len 2048  # 2x actual need
```

---

### Pitfall 2: Missing block_size Configuration

**Problem:**
```bash
# No block_size specified
vllm serve model --max-model-len 4096
```

**Impact:**
- May use default (usually OK)
- No guarantee of optimal alignment
- Potential 10-20% performance loss

**Solution:**
```bash
# Always explicitly set for CPU
vllm serve model \
  --max-model-len 4096 \
  --block-size 128
```

---

### Pitfall 3: Non-Multiple-of-32 block_size

**Problem:**
```bash
vllm serve model --block-size 100
```

**Impact:**
```
WARNING: CPU backend prefers block_size is multiples of 32,
otherwise the performance is not optimized.
```
- Misaligned SIMD operations
- 15-30% slower attention

**Solution:**
```bash
vllm serve model --block-size 128  # Or 32, 64, 96, 160, etc.
```

---

## Quick Reference

### Workload → `max_model_len`

| Workload | Token ratio | Recommended `max_model_len` |
| --- | --- | --- |
| Chat | 512:512 | 2048 |
| RAG | 7680:512 | 8192 |
| Code | 1024:1024 | 4096 |
| Custom | — | `2 × (ISL + OSL)` |

### RAM → KV cache budget

| Available RAM | Recommended KV cache |
| --- | --- |
| 16 GB | 4–8 GB |
| 32 GB | 12–20 GB |
| 64 GB | 24–40 GB |
| 128+ GB | 48–80+ GB |

### CPU architecture → `block_size`

All CPU architectures (x86, ARM, RISC-V) should use `block_size=128`.

Copy final values from the **Practical Recommendations** section above.

---

## References

### vLLM Source Code

1. **CPU Platform Configuration:**
   [`vllm/platforms/cpu.py`](https://github.com/vllm-project/vllm/blob/main/vllm/platforms/cpu.py)
   - Lines 124-131: Block size validation
   - Lines 133-137: KV cache space configuration

2. **Model Configuration:**
   [`vllm/config/model.py`](https://github.com/vllm-project/vllm/blob/main/vllm/config/model.py)
   - Lines 189-200: max_model_len definition

3. **Cache Configuration:**
   [`vllm/config/cache.py`](https://github.com/vllm-project/vllm/blob/main/vllm/config/cache.py)
   - KV cache memory sizing and block configuration

4. **Environment Variables:**
   [`vllm/envs.py`](https://github.com/vllm-project/vllm/blob/main/vllm/envs.py)
   - `VLLM_CPU_KVCACHE_SPACE` definition

### Documentation

1. **vLLM CPU Installation:**
   [CPU Installation Guide](https://docs.vllm.ai/en/latest/getting_started/cpu-installation.html)

2. **Memory Configuration:**
   [Engine Arguments - Memory](https://docs.vllm.ai/en/latest/serving/engine_args.html#memory)

3. **Performance Optimization:**
   [Engine Arguments - Performance](https://docs.vllm.ai/en/latest/serving/engine_args.html#performance)
