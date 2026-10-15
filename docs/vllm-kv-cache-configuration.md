# vLLM CPU Performance: Understanding KV Cache and max_model_len

## Executive Summary

Two configuration parameters have **critical impact** on vLLM CPU inference performance:

| Parameter | Impact | Default | CPU Recommendation |
|-----------|--------|---------|-------------------|
| `--max-model-len` | Memory allocation, throughput | Model's max context | **Set to workload needs** (2048-8192) |
| `VLLM_CPU_KVCACHE_SPACE` | KV cache memory budget | 4 GiB | **Scale with RAM tier** (4–100 GiB; see system-based sizing table) |

---

## Table of Contents

1. [Parameter Overview](#parameter-overview)
2. [max_model_len: Context Length Configuration](#max_model_len-context-length-configuration)
3. [KV Cache Size: Memory Budget](#kv-cache-size-memory-budget)
4. [Practical Recommendations](#practical-recommendations)
5. [Common Pitfalls](#common-pitfalls)
6. [Quick Reference](#quick-reference)
7. [References](#references)

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
num_layers=16, num_kv_heads=8, head_size=64 (hidden_size 2048 / num_attn_heads 32)

= 2 × 16 × 8 × 64 × 8192 × 2 bytes
= ~256 MB per request at full context
```

### Two Primary Tuning Levers

| Parameter | Effect | Tuning guidance |
| --- | --- | --- |
| `max_model_len` | Maximum context per request | Higher = more memory per request; lower = more concurrent requests |
| KV cache size | Total memory budget for all requests | Higher = more concurrent requests; limited by available RAM |

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
per_request_kv ∝ max_model_len
total_kv_memory ≈ per_request_kv × max_num_seqs
```

**Example:** Chat workload (512 input + 512 output = 1024 tokens needed), ~7B model (bfloat16, MHA)

| max_model_len | KV Cache Used | Wasted Memory | Max Concurrent (20 GiB budget) |
|---------------|---------------|---------------|-------------------------------|
| 2048          | ~1 GB/req     | ~50%          | ~20 requests                  |
| 4096          | ~2 GB/req     | ~75%          | ~10 requests                  |
| 8192          | ~4 GB/req     | ~87%          | ~5 requests                   |
| 32768         | ~16 GB/req    | ~97%          | ~1 request                    |

_The 20 GiB budget is illustrative for this ~7B MHA model example; scale the concurrency column proportionally for your actual KV cache budget._

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

**System-based sizing (RAM heuristic):**

The table below gives the maximum KV cache that can be allocated after reserving RAM for model weights and OS overhead. It assumes modern GQA models and provides conservative headroom to scale concurrency — use the formula below for workload-specific precision.

| System RAM | vLLM Cores | Model Weights (bfloat16) | Recommended KV Cache | Model Size Range |
|------------|-----------|-------------------------|---------------------|-----------------|
| 16 GB      | 8         | ≤6 GB (3B)              | 4-6 GiB             | 1B-3B           |
| 32 GB      | 16        | ≤16 GB (8B)             | 8-12 GiB            | 1B-8B           |
| 64 GB      | 32        | ≤26 GB (13B)            | 16-32 GiB           | 1B-13B          |
| 128 GB     | 64        | ≤60 GB (30B)            | 40-60 GiB           | 1B-30B          |
| 256 GB+    | 128+      | ≤140 GB (70B)           | 64-100 GiB          | 1B-70B          |

### Why the 1.25× Safety Margin?

For workload-specific sizing, always compute the KV budget using the formula and apply a **1.25× safety margin**:

```
KV cache budget = per_request_kv × max_concurrent_requests × 1.25
```

The 25% overhead covers:
- **OS and runtime memory pressure** — kernel, hugepage bookkeeping, allocator metadata
- **Activation memory during forward passes** — intermediate tensors not counted in the static KV formula
- **Memory allocator fragmentation** — blocks freed but not yet returned to the OS
- **Burst headroom** — spikes above the average concurrency target

This convention is established in the project's [KV Cache Sizing Strategy](./design/full-testing-deck.md).

> **Tip — use the LMCache KV Cache Calculator** to get per-model, per-request KV sizes:
> [https://docs.lmcache.ai/getting_started/kv_cache_calculator.html](https://docs.lmcache.ai/getting_started/kv_cache_calculator.html)
>
> Enter your model, dtype, and context length. The calculator outputs the **per-request KV size**. Apply the full formula to get the `VLLM_CPU_KVCACHE_SPACE` budget:
>
> ```
> budget = per_request_kv × max_concurrent_requests × 1.25
> ```
>
> ```bash
> # Example: per-request KV = 0.25 GiB, 32 concurrent → 0.25 × 32 × 1.25 = 10 GiB
> export VLLM_CPU_KVCACHE_SPACE=10
> ```

---

## Practical Recommendations

### Quick Reference Table

**For different CPU configurations** (KV cache ranges are RAM-constrained heuristics for GQA models; for precise values use `per_request_kv × concurrency × 1.25` — see [Why the 1.25× Safety Margin?](#why-the-125-safety-margin)):

| CPU Cores | RAM   | Model Size | max_model_len | KV Cache    | Expected Concurrency |
|-----------|-------|------------|---------------|-------------|---------------------|
| 8         | 16GB  | 1-3B       | 2048          | 4-6 GiB     | 2-4                 |
| 16        | 32GB  | 1-8B       | 2048-4096     | 8-12 GiB    | 6-10                |
| 32        | 64GB  | 1-13B      | 2048-4096     | 16-32 GiB   | 12-20               |
| 64        | 128GB | 1-30B      | 2048-8192     | 40-60 GiB   | 24-40               |
| 128+      | 256GB | 1B-70B     | 4096-16384    | 64-100 GiB  | 40-80               |

### Workload-Specific Presets

The examples below are sized for a **64 GB system** (KV cache range 16–32 GiB, 1B–13B models). Adjust `--kv-cache-memory-bytes` for your RAM tier using the [Quick Reference Table](#quick-reference-table) or the [1.25× formula](#why-the-125-safety-margin).

#### Chat Applications (512:512 tokens)
```bash
vllm serve model-name \
  --max-model-len 2048 \
  --kv-cache-memory-bytes $((16 * 1024 * 1024 * 1024))  # 16 GB
```

#### RAG Applications (7680:512 tokens)
```bash
vllm serve model-name \
  --max-model-len 8192 \
  --kv-cache-memory-bytes $((32 * 1024 * 1024 * 1024))  # 32 GB
```

#### Code Generation (1024:1024 tokens)
```bash
vllm serve model-name \
  --max-model-len 4096 \
  --kv-cache-memory-bytes $((20 * 1024 * 1024 * 1024))  # 20 GB
```

#### Document Summarization (2048:256 tokens)
```bash
vllm serve model-name \
  --max-model-len 4096 \
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
      - "--no-enable-prefix-caching"    # For baseline testing
    kv_cache_space: "16GiB"

  batch_generation:
    vllm_args:
      - "--dtype=bfloat16"
      - "--max-model-len=8192"
      - "--no-enable-prefix-caching"
    kv_cache_space: "40GiB"
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
| 16 GB | 4–6 GiB |
| 32 GB | 8–12 GiB |
| 64 GB | 16–32 GiB |
| 128+ GB | 40–60+ GiB |

Copy final values from the **Practical Recommendations** section above.

---

## References

### vLLM Source Code

1. **CPU Platform Configuration:**
   [`vllm/platforms/cpu.py`](https://github.com/vllm-project/vllm/blob/main/vllm/platforms/cpu.py)
   - KV cache space configuration

2. **Model Configuration:**
   [`vllm/config/model.py`](https://github.com/vllm-project/vllm/blob/main/vllm/config/model.py)
   - Lines 189-200: max_model_len definition

3. **Cache Configuration:**
   [`vllm/config/cache.py`](https://github.com/vllm-project/vllm/blob/main/vllm/config/cache.py)
   - KV cache memory sizing

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

4. **KV Cache Calculator (LMCache):**
   [https://docs.lmcache.ai/getting_started/kv_cache_calculator.html](https://docs.lmcache.ai/getting_started/kv_cache_calculator.html)
   — Outputs per-request KV size for a given model, dtype, and context length. Apply: `per_request_kv × max_concurrent_requests × 1.25` to get the `VLLM_CPU_KVCACHE_SPACE` budget.
