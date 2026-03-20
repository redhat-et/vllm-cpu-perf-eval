# 3-Phase Testing Methodology

## Overview

> **Current Status:** 3-phase testing is **only implemented for the Concurrent Load Test Suite**. Scalability and embedding model tests currently use baseline testing approaches only.

The vLLM CPU performance evaluation uses a structured 3-phase testing approach to separate baseline performance measurement, realistic variability analysis, and production optimization evaluation. This methodology was designed to be adaptable across test suites but is currently fully implemented only for concurrent load testing.

**Key Benefits:**
- **Reproducible baselines**: Fixed workloads eliminate variability for apples-to-apples comparisons
- **Realistic insights**: Variable workloads simulate real-world traffic patterns
- **Production validation**: Caching comparison quantifies optimization benefits
- **Clear progression**: Each phase builds on previous results

> **📚 Test Suite Implementations**
>
> This document describes the **general methodology**. For specific test implementations:
> - **Concurrent Load Tests**: See [tests/concurrent-load/concurrent-load.md](../../tests/concurrent-load/concurrent-load.md)
> - **Scalability Tests**: See [tests/scalability/scalability.md](../../tests/scalability/scalability.md)
> - **Embedding Models**: See [tests/embedding-models/embedding-models.md](../../tests/embedding-models/embedding-models.md)

---

## Phase 1: Baseline Tests

**Fixed Tokens, No Caching**

### Phase 1: Objectives

- Establish pure baseline performance without caching optimizations
- Create reproducible performance benchmarks for cross-architecture comparison
- Identify maximum throughput without production optimizations
- Measure single-user/minimal load baseline for efficiency calculations
- Determine saturation points for each model/workload combination

### Phase 1: Configuration Pattern

**vLLM Server:**
- Disable prefix caching: `--no-enable-prefix-caching`
- Data type: `--dtype=bfloat16` (for FP16 models) or `--dtype=auto` (for other precisions)

**Load Generator (GuideLLM or vllm bench):**
- Time-based testing for consistency
- Warmup period to exclude cold start effects
- Fixed token counts (no variability)

**Workload Characteristics:**
- Fixed input token counts
- Fixed output token counts
- Synthetic prompts with deterministic behavior

### Phase 1: Expected Outcomes

**Metrics to Collect:**
- P95/P99 latency across different load levels
- Maximum throughput without caching
- Baseline latency at minimal load
- Time to First Token (TTFT) baseline
- Inter-Token Latency (ITL) baseline
- Saturation points for each model/workload

**Analysis:**
- Identify optimal operating points (best latency/throughput trade-off)
- Compare model efficiency across architectures
- Establish baseline for future comparisons
- Determine which models work well on CPU

### Phase 1: Success Criteria

- ✅ All tests complete without errors
- ✅ Consistent latency measurements (low variance across runs)
- ✅ Clear saturation point identification
- ✅ Minimal load baseline provides efficiency reference

---

## Phase 2: Realistic Tests

**Variable Tokens, No Caching**

### Phase 2: Objectives

- Quantify impact of token distribution variance on latency
- Identify performance stability under variable load
- Compare realistic vs baseline to understand variability impact
- Understand real-world traffic pattern effects
- Validate that systems can handle realistic workload distributions

### Phase 2: Configuration Pattern

**vLLM Server:**
- Disable prefix caching: `--no-enable-prefix-caching` (same as Phase 1)
- Data type: `--dtype=bfloat16` (for FP16 models) or `--dtype=auto` (for other precisions)

**Load Generator:**
- Time-based testing (same duration as Phase 1)
- Warmup period
- Variable token counts with statistical distribution

**Workload Characteristics:**
- Token counts with mean, standard deviation, min, and max
- Synthetic prompts with statistical variability
- Example: Input tokens ~ N(512, 128) with bounds [128, 1024]

### Phase 2: Expected Outcomes

**Metrics to Collect:**
- P95/P99 latency variance under realistic load
- Latency distribution spread (compare to Phase 1)
- Throughput stability with variable requests
- TTFT/ITL (Inter-Token Latency) variance
- Performance degradation from baseline

**Analysis:**
- Quantify latency variance increase (realistic vs fixed)
- Identify models with better variance handling
- Understand performance stability characteristics
- Compare to Phase 1 to isolate variability impact

### Phase 2: Success Criteria

- ✅ Variable workloads show expected token distribution
- ✅ P95/P99 latency variance quantified relative to Phase 1
- ✅ Throughput impact measured
- ✅ Recommendations identified for production workload modeling

---

## Phase 3: Production Tests

**Realistic Datasets, With Caching**

> **⚠️ PHASE 3 STATUS**
>
> Phase 3 requires realistic prompt datasets that simulate actual production traffic patterns.
> Different test suites may have different Phase 3 readiness levels. Check the individual
> test suite documentation for current status and dataset availability.

### Phase 3: Objectives

- Simulate true production conditions with realistic datasets and optimizations
- Measure real-world performance with variable traffic and caching enabled
- Quantify combined impact of variability and caching optimizations
- Validate production configurations under realistic conditions
- Establish production performance baselines

### Phase 3: Configuration Pattern

**vLLM Server:**
- Enable prefix caching: `--enable-prefix-caching` (or omit - enabled by default)
- Data type: `--dtype=bfloat16` (for FP16 models) or `--dtype=auto` (for other precisions)

**Load Generator:**
- Time-based testing (same duration as Phase 1/2)
- Warmup period
- **Realistic prompt datasets** (not synthetic)

**Workload Characteristics:**
- Natural token distribution from real prompts
- Actual conversation histories, code repositories, or document collections
- Representative production traffic patterns

### Phase 3: Expected Outcomes

**Metrics to Collect:**
- Production latency characteristics (P95/P99) with realistic load
- Production throughput under variable traffic
- TTFT with caching under realistic conditions
- Cache hit rates and effectiveness (from vLLM logs)
- Resource efficiency in production configuration

**Analysis:**
- Compare Phase 3 vs Phase 2 (caching impact with realistic load)
- Compare Phase 3 vs Phase 1 (total production improvement)
- Measure production performance stability with variable load + caching
- Identify cache effectiveness under realistic traffic patterns

### Phase 3: Success Criteria

- ✅ True production performance characteristics established
- ✅ Performance improvements over Phase 2 (caching impact) quantified
- ✅ Total improvement over Phase 1 (baseline) documented
- ✅ Cache hit rates under realistic load measured
- ✅ Production SLOs validated

---

## Cross-Phase Analysis

### Comparing Baseline vs Realistic (Phase 1 vs Phase 2)

**Question:** How does token variability impact performance?

**Metrics:**
- ΔP95 Latency = P95_realistic - P95_baseline
- ΔP99 Latency = P99_realistic - P99_baseline
- Latency Variance Ratio = StdDev_realistic / StdDev_baseline

**Example Analysis:**
```
Phase 1 (Fixed): P95=245ms, P99=312ms
Phase 2 (Variable): P95=278ms, P99=365ms

Impact: +13% P95, +17% P99
Conclusion: Variability adds ~13-17% latency overhead
```

**Interpretation:**
- **Low impact (<10%)**: Model handles variability well
- **Medium impact (10-20%)**: Expected variance, acceptable
- **High impact (>20%)**: May indicate bottlenecks under variable load

### Comparing Realistic vs Production (Phase 2 vs Phase 3)

**Question:** What performance gains does caching provide under realistic load?

**Metrics:**
- TTFT Improvement % = (TTFT_phase2 - TTFT_phase3) / TTFT_phase2 × 100
- Throughput Gain % = (Throughput_phase3 - Throughput_phase2) / Throughput_phase2 × 100
- Latency Reduction % = (P95_phase2 - P95_phase3) / P95_phase2 × 100

**Example Analysis:**
```
Phase 2 (Variable, No Cache): TTFT=165ms, Throughput=35.4 rps, P95=278ms
Phase 3 (Variable, With Cache): TTFT=98ms, Throughput=48.7 rps, P95=195ms

Gains:
- TTFT: 41% improvement
- Throughput: 38% improvement
- P95 Latency: 30% improvement
```

**Interpretation:**
- **Chat workloads**: Expect 20-40% improvement (conversation history caching)
- **CodeGen workloads**: Expect 15-30% improvement (prompt caching)
- Cache effectiveness varies based on request patterns and dataset

### Comparing Baseline vs Production (Phase 1 vs Phase 3)

**Question:** What is the total production improvement over baseline?

**Metrics:**
- Total TTFT Impact = (TTFT_phase1 - TTFT_phase3) / TTFT_phase1 × 100
- Total Throughput Impact = (Throughput_phase3 - Throughput_phase1) / Throughput_phase1 × 100

**Example Analysis:**
```
Phase 1 (Fixed, No Cache): TTFT=156ms, Throughput=38.2 rps, P95=245ms
Phase 3 (Variable, With Cache): TTFT=98ms, Throughput=48.7 rps, P95=195ms

Total Impact:
- TTFT: 37% improvement (despite variability)
- Throughput: 27% improvement
- P95 Latency: 20% improvement
```

**Interpretation:**
- Shows combined effect of caching benefits offsetting variability overhead
- Production configuration (Phase 3) should outperform baseline (Phase 1) despite variable load
- Validates that production optimizations compensate for realistic traffic complexity

---

## Testing Order and Dependencies

### Recommended Testing Sequence

```
1. Phase 1: Baseline Tests (Fixed, No Caching)
   ├── Run all models on all workload types
   ├── Document: P95/P99 latency, throughput, TTFT, ITL (Inter-Token Latency)
   └── Establish performance baselines

2. Phase 2: Realistic Tests (Variable, No Caching)
   ├── Run priority models/workloads with variability
   ├── Compare to Phase 1 fixed results
   └── Document variance and stability

3. Phase 3: Production Tests (Realistic Datasets, With Caching)
   ├── Run select models with realistic datasets + caching enabled
   ├── Compare to Phase 2 (caching impact) and Phase 1 (total improvement)
   └── Document true production performance
```

### Dependencies Between Phases

- **Phase 2** depends on **Phase 1** for baseline comparison
- **Phase 3** depends on **Phase 2** for caching impact measurement
- **Phase 3** depends on **Phase 1** for total improvement calculation
- All phases should use **consistent test configuration** (duration, warmup, cores, etc.)

---

## Test Suite Implementation Status

The 3-phase methodology was designed to be adaptable across test suites, but implementation varies:

### Concurrent Load Tests ✅ **FULLY IMPLEMENTED**

- **Load Pattern**: Fixed concurrency levels (e.g., {1, 2, 4, 8, 16, 32})
- **Primary Metric**: P95 latency scaling with concurrency
- **Phase Implementation**: All 3 phases (baseline, realistic, production*)
- **Status**: Phases 1 & 2 fully operational; Phase 3 pending realistic datasets
- **See**: [tests/concurrent-load/concurrent-load.md](../../tests/concurrent-load/concurrent-load.md)

### Scalability Tests ⚠️ **BASELINE ONLY**

- **Load Pattern**: Range of request rates (synchronous → throughput)
- **Primary Metric**: Load-latency curves, maximum throughput
- **Phase Implementation**: Baseline tests only (fixed tokens, no caching)
- **Status**: 3-phase approach not yet implemented
- **See**: [tests/scalability/scalability.md](../../tests/scalability/scalability.md)

### Embedding Model Tests ⚠️ **BASELINE ONLY**

- **Load Pattern**: High concurrency levels optimized for embedding workloads
- **Primary Metric**: Embedding-specific latency and throughput
- **Phase Implementation**: Baseline tests only
- **Status**: 3-phase approach not yet implemented
- **See**: [tests/embedding-models/embedding-models.md](../../tests/embedding-models/embedding-models.md)

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

❌ **Ignoring minimal load baseline** - Essential for efficiency calculations

❌ **Skipping warmup** - Cold starts skew initial measurements

❌ **Running too short** - Allow sufficient time for stable measurements

❌ **Mixing caching modes** - Always document baseline vs production clearly

---

## Summary

| Phase | Configuration | Purpose | Key Metrics | Applies To |
|-------|--------------|---------|-------------|------------|
| **1. Baseline** | Fixed tokens, No caching | Reproducible baseline | P95/P99, TTFT, Throughput | All test suites |
| **2. Realistic** | Variable tokens, No caching | Real-world simulation | Variance, Stability | All test suites |
| **3. Production** | Realistic datasets, With caching | True production conditions | Production performance, Cache effectiveness | All test suites |

**Estimated time per model/test suite: 4-6 hours**

---

## References

- [Testing Methodology Overview](overview.md)
- [Concurrent Load Test Suite](../../tests/concurrent-load/concurrent-load.md)
- [Scalability Test Suite](../../tests/scalability/scalability.md)
- [Embedding Models Test Suite](../../tests/embedding-models/embedding-models.md)
- [Model Selection Strategy](../../models/models.md)
- [Metrics Guide](metrics.md)
- [GuideLLM Documentation](https://github.com/neuralmagic/guidellm)
- [vLLM Prefix Caching](https://docs.vllm.ai/en/latest/models/performance.html#automatic-prefix-caching-apc)
