
# Latency and Stability Under Load Test
# Overview

The latency concurrent test measures how latency scales under increasing concurrent requests to identify the optimal concurrency level and degradation point.
# Test Type

**Latency Scaling and Stability Testing**
# Objectives

1. **Measure Latency Scaling** - Understand how P99 latency changes with concurrency
2. **Identify Sweet Spot** - Find the concurrency level where throughput plateaus but latency remains acceptable
3. **Find Degradation Point** - Identify when latency increases significantly while throughput gains diminish
4. **Compare Scaling Behavior** - Analyze how different models handle concurrent load

## Test Configuration

### Backend Configuration
- **Backend**: `openai-embeddings`
- **Endpoint**: `/v1/embeddings`
- **Dataset**: Random text generation
- **Input Length**: 512 tokens per request
- **Prompts**: 1000 total requests
- **Request Rate**: `inf` (unlimited - controlled by max-concurrency)

### vLLM Server Configuration
- **Data Type**: `bfloat16`
- **KV Cache**: `1GiB` (minimal for encoder-only models)

## Concurrency Levels

### Level 1: Low Concurrency (16)
**Purpose:** Establish baseline latency behavior

**Configuration:**
- Max concurrency: 16
- Result file: `concurrent-16.json`

**Expected:**
- Low latency
- Good throughput
- Minimal queueing

### Level 2: Medium Concurrency (32)
**Purpose:** Test moderate concurrent load

**Configuration:**
- Max concurrency: 32
- Result file: `concurrent-32.json`

**Expected:**
- Moderate latency increase
- Higher throughput than Level 1
- Some queueing

### Level 3: High Concurrency (64)
**Purpose:** Test high concurrent load

**Configuration:**
- Max concurrency: 64
- Result file: `concurrent-64.json`

**Expected:**
- Higher latency
- Throughput approaching plateau
- Significant queueing

### Level 4: Very High Concurrency (128)
**Purpose:** Identify degradation characteristics

**Configuration:**
- Max concurrency: 128
- Result file: `concurrent-128.json`

**Expected:**
- Significant latency degradation possible
- Throughput plateau
- Heavy queueing

### Level 5: Maximum Concurrency (196)
**Purpose:** Test extreme load conditions

**Configuration:**
- Max concurrency: 196
- Result file: `concurrent-196.json`

**Expected:**
- Maximum latency
- Minimal throughput gain from Level 4
- Extreme queueing

## Metrics Collected

### Primary Metrics
- **Request Throughput** (req/s) - Requests processed per second
- **Total Token Throughput** (tok/s) - Tokens processed per second
- **Mean E2E Latency** (ms) - Average end-to-end request latency
- **P95 E2E Latency** (ms) - 95th percentile latency
- **P99 E2E Latency** (ms) - **PRIMARY METRIC** for this test

### Focus Metric
**P99 Latency** is the key metric because it represents the worst-case experience for users and is most sensitive to queueing and resource contention.

## Analysis Objectives

### 1. Sweet Spot Identification
**Goal:** Find concurrency where throughput plateaus but P99 latency stays acceptable

**Criteria:**
- Throughput within 90% of maximum
- P99 latency < 1000ms (configurable threshold)

**Method:**
- Plot throughput vs concurrency
- Plot P99 vs concurrency
- Find intersection point

### 2. Degradation Point Detection
**Goal:** Identify when system starts to degrade significantly

**Criteria:**
- P99 latency increase > 50% from previous level
- Throughput gain < 10% from previous level

**Method:**
- Calculate deltas between consecutive concurrency levels
- Flag when both criteria are met

### 3. Scaling Comparison
**Goal:** Understand how latency scales across the full range

**Metric:** P99 Latency Ratio = P99(high) / P99(low)

**Interpretation:**
- Ratio < 2: Excellent scaling
- Ratio 2-5: Good scaling
- Ratio 5-10: Moderate scaling
- Ratio > 10: Poor scaling

## Success Criteria

1. ✅ All concurrency levels complete without errors
2. ✅ Throughput increases with concurrency (at least initially)
3. ✅ P99 latency correlates positively with concurrency level
4. ✅ Clear sweet spot and degradation point can be identified

## Expected Results

### Result Format
- **Format**: JSON
- **Location**: `results/embedding-models/{model}/latency/`

### Files Generated
```
results/embedding-models/{model}/latency/
├── concurrent-16.json   # Low concurrency baseline
├── concurrent-32.json   # Medium concurrency
├── concurrent-64.json   # High concurrency
├── concurrent-128.json  # Very high concurrency
└── concurrent-196.json  # Maximum concurrency
```

## Analysis Graphs

### 1. Throughput vs Concurrency
**Purpose:** Show how throughput scales with concurrency

- **X-axis**: Concurrency Level (16, 32, 64, 128, 196)
- **Y-axis**: Throughput (req/s)
- **Expected Pattern**: Increases then plateaus

### 2. Latency vs Concurrency
**Purpose:** Show how latency degrades with concurrency

- **X-axis**: Concurrency Level
- **Y-axis**: Latency (ms)
- **Series**:
  - Mean E2E Latency
  - P99 E2E Latency
- **Expected Pattern**: Exponential increase at high concurrency

## Running the Test

### Using Ansible
```bash
cd automation/test-execution/ansible

# Run latency concurrent test for multilingual model
ansible-playbook embedding-benchmark.yml \
  -e "test_model=ibm-granite/granite-embedding-278m-multilingual" \
  -e "test_scenario=latency-concurrent" \
  -e "requested_cores=32"
```

### Using vllm bench serve (Manual)
```bash
# Test each concurrency level
for concurrency in 16 32 64 128 196; do
  vllm bench serve \
    ibm-granite/granite-embedding-278m-multilingual \
    --backend openai-embeddings \
    --endpoint /v1/embeddings \
    --dataset-name random \
    --random-input-len 512 \
    --num-prompts 1000 \
    --request-rate inf \
    --max-concurrency $concurrency \
    --save-results concurrent-${concurrency}.json
done
```

## Interpreting Results

### Example Output

**Concurrency 16 (Baseline):**
```json
{
  "request_throughput": 32.5,
  "total_token_throughput": 16640.0,
  "mean_e2el": 492.3,
  "p95_e2el": 587.1,
  "p99_e2el": 645.8
}
```
**Interpretation:** Low concurrency, baseline latency ~645ms P99

**Concurrency 32 (Sweet Spot):**
```json
{
  "request_throughput": 38.42,
  "total_token_throughput": 19670.4,
  "mean_e2el": 832.5,
  "p95_e2el": 945.2,
  "p99_e2el": 1024.8
}
```
**Interpretation:** Good throughput (+18%), acceptable P99 increase (+59%)

**Concurrency 64 (Approaching Saturation):**
```json
{
  "request_throughput": 41.2,
  "total_token_throughput": 21094.4,
  "mean_e2el": 1553.7,
  "p95_e2el": 1842.3,
  "p99_e2el": 2156.9
}
```
**Interpretation:** Minimal throughput gain (+7%), significant P99 increase (+110%)

**Concurrency 128 (Degradation Point):**
```json
{
  "request_throughput": 42.1,
  "total_token_throughput": 21555.2,
  "mean_e2el": 3041.2,
  "p95_e2el": 3687.5,
  "p99_e2el": 4234.6
}
```
**Interpretation:** Marginal throughput gain (+2%), extreme P99 increase (+96%)

### Analysis Summary

| Concurrency | Throughput | P99 Latency | Throughput Gain | P99 Increase | Assessment |
|-------------|------------|-------------|-----------------|--------------|------------|
| 16 | 32.5 | 645.8ms | baseline | baseline | Baseline |
| 32 | 38.4 | 1024.8ms | +18% | +59% | **Sweet Spot** ✅ |
| 64 | 41.2 | 2156.9ms | +7% | +110% | Approaching Limit ⚠️ |
| 128 | 42.1 | 4234.6ms | +2% | +96% | **Degradation** ❌ |
| 196 | 42.3 | 6543.2ms | +0.5% | +55% | Extreme Degradation ❌ |

**Recommendation:** Operate at concurrency 32 for optimal throughput/latency balance

## Performance Expectations

### Throughput Pattern
- **16 → 32**: 15-20% increase
- **32 → 64**: 5-10% increase
- **64 → 128**: 0-5% increase
- **128 → 196**: < 2% increase

### Latency Pattern
- **16 → 32**: 50-100% increase (acceptable)
- **32 → 64**: 100-150% increase (moderate)
- **64 → 128**: 100-200% increase (significant)
- **128 → 196**: > 50% increase (extreme)

## Optimization Recommendations

Based on test results:

### If Degradation Occurs Early (< 32 concurrency)
- Check CPU core allocation
- Verify NUMA configuration
- Ensure no resource contention
- Consider smaller models

### If Sweet Spot is High (> 64 concurrency)
- System has good throughput capacity
- Consider testing higher core counts
- Validate stability under sustained load

### If No Clear Plateau
- Test intermediate concurrency levels (24, 48, 96)
- Extend test duration for better accuracy
- Check for thermal throttling or other system issues

## Next Steps

After latency concurrent testing:
1. Compare results with [Baseline Sweep](baseline-sweep.md) findings
2. Test different CPU core counts at optimal concurrency
3. Evaluate cost/performance trade-offs
4. Run production validation tests

## Related Documentation

- [Baseline Sweep Methodology](baseline-sweep.md)
- [Embedding Models Overview](embedding-models.md)
- [Model Matrix](../../models/embedding-models/model-matrix.yaml)
