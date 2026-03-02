# 3-Phase Concurrent Load Testing Strategy

## Overview

The vLLM CPU performance evaluation uses a structured 3-phase testing approach to separate baseline performance measurement, realistic variability analysis, and production optimization evaluation. This methodology ensures comprehensive performance characterization while maintaining clear comparisons between different testing scenarios.

**Key Benefits:**
- **Reproducible baselines**: Fixed workloads eliminate variability for apples-to-apples comparisons
- **Realistic insights**: Variable workloads simulate real-world traffic patterns
- **Production validation**: Caching comparison quantifies optimization benefits
- **Clear progression**: Each phase builds on previous results

---

## Phase 1: Baseline Tests

**Fixed Tokens, No Caching**

### Phase 1: Objectives

- Establish pure baseline performance without caching optimizations
- Create reproducible performance benchmarks for cross-architecture comparison
- Identify maximum throughput without production optimizations
- Measure single-user latency (concurrency=1) for efficiency calculations
- Determine saturation points for each model/workload combination

### Phase 1: Configuration

```yaml
vLLM Server:
  --no-enable-prefix-caching
  --disable-radix-cache
  --max-model-len=6656
  --dtype=bfloat16

GuideLLM:
  --max-seconds=600
  --request-timeout=600
  --warmup=0.1
  --profile=concurrent
  --rate=1,8,16,32,64,96,128

Workloads:
  - chat (512:256) - Fixed
  - rag (4096:512) - Fixed
  - code (512:4096) - Fixed
  - summarization (1024:256) - Fixed
```

### Phase 1: Test Execution

All models × All 4 workload profiles × All concurrency levels

**Example command:**

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

### Phase 1: Expected Outcomes

**Metrics to Collect:**
- P95/P99 latency curves across concurrency levels
- Maximum throughput without caching
- Single-user latency baseline (concurrency=1)
- Time to First Token (TTFT) baseline
- Time Per Output Token (TPOT) baseline
- Saturation points for each model/workload

**Analysis:**
- Identify concurrency sweet spots (best latency/throughput trade-off)
- Compare model efficiency across architectures
- Establish baseline for future comparisons

### Phase 1: Success Criteria

- ✅ All tests complete without errors
- ✅ Consistent P95/P99 latency measurements (low variance across runs)
- ✅ Clear saturation point identification
- ✅ Single-user latency (concurrency=1) provides efficiency baseline

---

## Phase 2: Realistic Tests

**Variable Tokens, No Caching**

### Phase 2: Objectives

- Quantify impact of token distribution variance on latency
- Identify performance stability under variable load
- Compare realistic vs baseline to understand variability impact
- Understand real-world traffic pattern effects

### Phase 2: Configuration

```yaml
vLLM Server:
  --no-enable-prefix-caching
  --disable-radix-cache
  --max-model-len=6656
  --dtype=bfloat16

GuideLLM:
  --max-seconds=600
  --request-timeout=600
  --warmup=0.1
  --profile=concurrent
  --rate=1,8,16,32,64,96,128

Workloads (with variability):
  - chat_var (512±128:256±64)
    - Input: mean=512, stdev=128, min=128, max=1024
    - Output: mean=256, stdev=64, min=64, max=512

  - code_var (512±128:4096±1024)
    - Input: mean=512, stdev=128, min=128, max=1024
    - Output: mean=4096, stdev=1024, min=512, max=6144
```

### Phase 2: Test Execution

**Priority Models:**
- All models in test suite

**Priority Workloads:**
1. Chat with variability (chat_var)
2. CodeGen with variability (code_var)

**Rationale:**
- Chat: Most common production use case
- CodeGen: Highest output variability (code length varies significantly)
- RAG/Summarization: Less critical for variability testing (documents/outputs more stable)

**Example command:**

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

### Phase 2: Expected Outcomes

**Metrics to Collect:**
- P95/P99 latency variance under realistic load
- Latency distribution spread (compare to Phase 1)
- Throughput stability with variable requests
- TTFT/TPOT variance

**Analysis:**
- Quantify latency variance increase (realistic vs fixed)
- Identify models with better variance handling
- Understand performance stability characteristics

### Phase 2: Success Criteria

- ✅ Variable workloads show expected token distribution
- ✅ P95/P99 latency variance quantified relative to Phase 1
- ✅ Throughput impact measured
- ✅ Recommendations identified for production workload modeling

---

## Phase 3: Production Comparison

**Fixed Tokens, With Caching**

### Phase 3: Objectives

- Quantify production optimization gains from prefix caching
- Compare baseline (no caching) vs production (with caching) performance
- Measure TTFT improvements from prefix caching
- Identify which workloads benefit most from caching
- Validate production configurations

### Phase 3: Configuration

```yaml
vLLM Server:
  --enable-prefix-caching  # or omit (enabled by default)
  --max-model-len=6656
  --dtype=bfloat16
  # Omit: --no-enable-prefix-caching, --disable-radix-cache

GuideLLM:
  --max-seconds=600
  --request-timeout=600
  --warmup=0.1
  --profile=concurrent
  --rate=1,8,16,32,64,96,128

Workloads (Fixed - for comparison to Phase 1):
  - chat (512:256)
  - rag (4096:512)
```

### Phase 3: Test Execution

**Select Models (High-Priority):**
- meta-llama/Llama-3.2-1B-Instruct
- ibm-granite/granite-3.2-2b-instruct
- openai/gpt-oss-20b

**Select Workloads:**
- Chat (512:256) - benefits from prefix caching for conversation history
- RAG (4096:512) - benefits from caching large context prefixes

**Rationale:**
- Focus on workloads where prefix caching provides the most benefit
- Use fixed tokens for direct comparison to Phase 1 baseline
- Select representative models across different sizes

**Example command:**

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

### Phase 3: Expected Outcomes

**Metrics to Collect:**
- TTFT improvements (baseline vs production)
- Throughput gains
- P95/P99 latency improvements
- Cache hit rates (from vLLM logs)
- Resource efficiency improvements

**Analysis:**
- Quantify caching benefits (% improvement over baseline)
- Identify optimal workloads for caching
- Measure cost/benefit of caching overhead

### Phase 3: Success Criteria

- ✅ TTFT improvement measured and significant (>10% for applicable workloads)
- ✅ Throughput gains documented
- ✅ Cache hit rates correlate with performance improvements
- ✅ Clear ROI demonstrated for production caching

---

## Cross-Phase Analysis

### Comparing Baseline vs Realistic

**Question:** How does token variability impact performance?

**Metrics:**
- ΔP95 Latency = P95_realistic - P95_baseline
- ΔP99 Latency = P99_realistic - P99_baseline
- Latency Variance Ratio = StdDev_realistic / StdDev_baseline

**Analysis:**
```bash
# Example comparison
Phase 1 (Fixed): P95=245ms, P99=312ms
Phase 2 (Variable): P95=278ms, P99=365ms

Impact: +13% P95, +17% P99
Conclusion: Variability adds ~13-17% latency overhead
```

**Interpretation:**
- **Low impact (<10%)**: Model handles variability well
- **Medium impact (10-20%)**: Expected variance, acceptable
- **High impact (>20%)**: May indicate bottlenecks under variable load

### Comparing Baseline vs Production

**Question:** What performance gains does prefix caching provide?

**Metrics:**
- TTFT Improvement % = (TTFT_baseline - TTFT_production) / TTFT_baseline * 100
- Throughput Gain % = (Throughput_production - Throughput_baseline) / Throughput_baseline * 100
- Latency Reduction % = (P95_baseline - P95_production) / P95_baseline * 100

**Analysis:**
```bash
# Example comparison
Phase 1 (No Cache): TTFT=156ms, Throughput=38.2 rps, P95=245ms
Phase 3 (With Cache): TTFT=89ms, Throughput=52.1 rps, P95=178ms

Gains:
- TTFT: 43% improvement
- Throughput: 36% improvement
- P95 Latency: 27% improvement
```

**Interpretation:**
- **RAG workloads**: Expect 30-50% TTFT improvement (large prefix caching)
- **Chat workloads**: Expect 15-30% improvement (moderate prefix reuse)
- **Code workloads**: Expect 5-15% improvement (less prefix reuse)

### Recommended Testing Order

```
1. Phase 1: Baseline Tests (Fixed, No Caching)
   ├── Run all models on all 4 workloads
   ├── Document: P95/P99 latency, throughput, TTFT, TPOT
   └── Establish performance baselines

2. Phase 2: Realistic Tests (Variable, No Caching)
   ├── Run Chat and CodeGen workloads with variability
   ├── Compare to Phase 1 fixed results
   └── Document variance and stability

3. Phase 3: Production Tests (Fixed, With Caching)
   ├── Run select models with prefix caching enabled
   ├── Compare to Phase 1 baseline
   └── Document caching gains
```

---

## Automation Examples

### Running Complete 3-Phase Suite

**For a single model:**

```bash
#!/bin/bash
MODEL="meta-llama/Llama-3.2-1B-Instruct"
CORES=16

# Phase 1: Baseline Tests
for workload in chat rag code summarization; do
  ansible-playbook llm-benchmark-auto.yml \
    -e "test_model=$MODEL" \
    -e "workload_type=$workload" \
    -e "requested_cores=$CORES" \
    -e "vllm_caching_mode=baseline" \
    -e "guidellm_profile=concurrent" \
    -e "guidellm_rate=[1,8,16,32,64,96,128]"
done

# Phase 2: Realistic Tests
for workload in chat_var code_var; do
  ansible-playbook llm-benchmark-auto.yml \
    -e "test_model=$MODEL" \
    -e "workload_type=$workload" \
    -e "requested_cores=$CORES" \
    -e "vllm_caching_mode=baseline" \
    -e "guidellm_profile=concurrent" \
    -e "guidellm_rate=[1,8,16,32,64,96,128]"
done

# Phase 3: Production Tests
for workload in chat rag; do
  ansible-playbook llm-benchmark-auto.yml \
    -e "test_model=$MODEL" \
    -e "workload_type=$workload" \
    -e "requested_cores=$CORES" \
    -e "vllm_caching_mode=production" \
    -e "guidellm_profile=concurrent" \
    -e "guidellm_rate=[1,8,16,32,64,96,128]"
done
```

### Running Specific Phases

**Phase 1 only:**

```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=baseline"
```

**Phase 2 only:**

```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat_var" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=baseline"
```

**Phase 3 only:**

```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "vllm_caching_mode=production"
```

---

## Results Organization

### Directory Structure

```
results/
├── phase1-baseline/
│   ├── llama-3.2-1b-instruct/
│   │   ├── chat-concurrent-1.json
│   │   ├── chat-concurrent-8.json
│   │   ├── chat-concurrent-16.json
│   │   ├── rag-concurrent-8.json
│   │   ├── code-concurrent-8.json
│   │   └── ...
│   └── granite-3.2-2b-instruct/
│       └── ...
├── phase2-realistic/
│   ├── llama-3.2-1b-instruct/
│   │   ├── chat_var-concurrent-1.json
│   │   ├── chat_var-concurrent-8.json
│   │   ├── code_var-concurrent-8.json
│   │   └── ...
│   └── ...
└── phase3-production/
    ├── llama-3.2-1b-instruct/
    │   ├── chat-concurrent-1-cached.json
    │   ├── chat-concurrent-8-cached.json
    │   ├── rag-concurrent-8-cached.json
    │   └── ...
    └── ...
```

### Results Naming Convention

- **Phase 1**: `{model}/{workload}-concurrent-{concurrency}.json`
- **Phase 2**: `{model}/{workload}_var-concurrent-{concurrency}.json`
- **Phase 3**: `{model}/{workload}-concurrent-{concurrency}-cached.json`

---

## Best Practices

### Test Execution

1. **Run phases sequentially** - Complete Phase 1 before Phase 2, etc.
2. **Document system state** - Record CPU governor, turbo settings, background processes
3. **Single workload isolation** - Run one test at a time to avoid interference
4. **Cooldown between tests** - Allow 30-60 seconds between runs
5. **Log everything** - Collect vLLM logs, system metrics, test outputs

### Results Analysis

1. **Compare like-to-like** - Fixed vs fixed, variable vs variable
2. **Account for variance** - Run multiple iterations for statistical significance
3. **Watch for outliers** - P99 > 2× P95 may indicate issues
4. **Cross-validate** - Verify results make sense across models/workloads
5. **Document assumptions** - Note any deviations from standard configuration

### Common Pitfalls

❌ **Comparing different phases directly** - Fixed vs variable comparisons require careful interpretation
❌ **Ignoring single-user baseline** - Concurrency=1 is critical for efficiency calculations
❌ **Skipping warmup** - Cold starts skew initial measurements
❌ **Running too short** - 600 seconds allows stable measurement collection
❌ **Mixing caching modes** - Always document baseline vs production clearly

---

## Summary

| Phase | Configuration | Purpose | Key Metrics | Duration |
|-------|--------------|---------|-------------|----------|
| **1. Baseline** | Fixed tokens, No caching | Reproducible baseline | P95/P99, TTFT, Throughput | ~2-3 hours per model |
| **2. Realistic** | Variable tokens, No caching | Real-world simulation | Variance, Stability | ~1-2 hours per model |
| **3. Production** | Fixed tokens, With caching | Optimization validation | Cache gains, ROI | ~1 hour per model |

**Total estimated time per model: 4-6 hours**

---

## References

- [Concurrent Load Test Suite](../../tests/concurrent-load/concurrent-load.md)
- [Model Selection Strategy](../../models/models.md)
- [GuideLLM Documentation](https://github.com/neuralmagic/guidellm)
- [vLLM Prefix Caching](https://docs.vllm.ai/en/latest/models/performance.html#automatic-prefix-caching-apc)
