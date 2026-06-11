---
layout: default
title: Baseline Sweep Test Methodology
---

# Baseline Performance and Scalability Test

## Overview

The baseline sweep test establishes maximum request throughput (RPS) and analyzes how performance scales across different load levels for embedding models.

## Test Type

**Baseline Performance Testing**

## Objectives

1. **Find Maximum Throughput** - Determine the maximum sustained requests per second (RPS)
2. **Analyze Performance Scaling** - Measure how latency and throughput change at various load levels
3. **Establish Baselines** - Create performance baselines for comparison across configurations

## Test Configuration

### Backend Configuration
- **Backend**: `openai-embeddings`
- **Endpoint**: `/v1/embeddings`
- **Dataset**: Random text generation
- **Input Length**: 512 tokens per request
- **Prompts**: 1000 total requests

### vLLM Server Configuration
- **Data Type**: `bfloat16`
- **KV Cache**: `1GiB` (minimal for encoder-only models)

## Test Stages

### Stage 1: Maximum Throughput Discovery
**Purpose:** Find the maximum sustained RPS the system can handle

**Configuration:**
- Request rate: `inf` (unlimited)
- Duration: Until 1000 requests complete
- Result file: `sweep-inf.json`

**Expected Output:**
- Maximum request throughput (req/s)
- This value is used to calculate subsequent stage rates

### Stage 2: 25% Load Test
**Purpose:** Test performance at light load

**Configuration:**
- Request rate: 25% of maximum from Stage 1
- Duration: Until 1000 requests complete
- Result file: `sweep-25pct.json`

**Expected Behavior:**
- Low latency
- Linear throughput scaling
- Minimal queueing

### Stage 3: 50% Load Test
**Purpose:** Test performance at moderate load

**Configuration:**
- Request rate: 50% of maximum from Stage 1
- Duration: Until 1000 requests complete
- Result file: `sweep-50pct.json`

**Expected Behavior:**
- Moderate latency increase
- Good throughput
- Some queueing may occur

### Stage 4: 75% Load Test
**Purpose:** Test performance near saturation

**Configuration:**
- Request rate: 75% of maximum from Stage 1
- Duration: Until 1000 requests complete
- Result file: `sweep-75pct.json`

**Expected Behavior:**
- Higher latency
- Throughput approaching saturation
- Significant queueing

## Metrics Collected

### Primary Metrics
- **Request Throughput** (req/s) - Requests processed per second
- **Total Token Throughput** (tok/s) - Tokens processed per second
- **Mean E2E Latency** (ms) - Average end-to-end request latency
- **P95 E2E Latency** (ms) - 95th percentile latency
- **P99 E2E Latency** (ms) - 99th percentile latency

### Derived Metrics
- **Calculated Average Concurrency** = RPS × Mean Latency (in seconds)

## Success Criteria

1. ✅ All stages complete without errors
2. ✅ Latency increases progressively with load (25% < 50% < 75%)
3. ✅ Throughput saturates near maximum (75% stage approaches Stage 1 throughput)
4. ✅ System remains stable under sustained load

## Expected Results

### Result Format
- **Format**: JSON
- **Location**: `results/embedding-models/{model}/baseline/`

### Files Generated
```
results/embedding-models/{model}/baseline/
├── sweep-inf.json      # Stage 1: Maximum throughput
├── sweep-25pct.json    # Stage 2: 25% load
├── sweep-50pct.json    # Stage 3: 50% load
└── sweep-75pct.json    # Stage 4: 75% load
```

## Analysis Graphs

### 1. Throughput Saturation Curve
**Purpose:** Show how achieved throughput relates to requested rate

- **X-axis**: Requested Rate (req/s)
- **Y-axis**: Achieved Throughput (req/s)
- **Expected Pattern**: Linear initially, then plateaus at saturation

### 2. Latency vs Request Rate
**Purpose:** Show how latency increases with load

- **X-axis**: Request Rate (req/s)
- **Y-axis**: Latency (ms)
- **Series**:
  - Mean E2E Latency
  - P99 E2E Latency
- **Expected Pattern**: Exponential increase near saturation

## Running the Test

### Using Ansible
```bash
cd automation/test-execution/ansible

# Run baseline sweep for English model
ansible-playbook embedding-benchmark.yml \
  -e "test_model=ibm-granite/granite-embedding-english-r2" \
  -e "test_scenario=baseline-sweep" \
  -e "requested_cores=32"
```

### Using vllm bench serve (Manual)
```bash
# Stage 1: Find max throughput
vllm bench serve \
  ibm-granite/granite-embedding-english-r2 \
  --backend openai-embeddings \
  --endpoint /v1/embeddings \
  --dataset-name random \
  --random-input-len 512 \
  --num-prompts 1000 \
  --request-rate inf \
  --save-results sweep-inf.json

# Calculate 25%, 50%, 75% rates from Stage 1 results
# Then run subsequent stages with calculated rates
```

## Interpreting Results

### Example Output

**Stage 1 (Maximum Throughput):**
```json
{
  "request_throughput": 52.3,
  "total_token_throughput": 26777.6,
  "mean_e2el": 45.2,
  "p99_e2el": 87.4
}
```
**Interpretation:** System can handle ~52 req/s at maximum throughput

**Stage 2 (25% Load - ~13 req/s):**
```json
{
  "request_throughput": 13.1,
  "mean_e2el": 42.1,
  "p99_e2el": 65.3
}
```
**Interpretation:** Light load, minimal queueing, low latency

**Stage 4 (75% Load - ~39 req/s):**
```json
{
  "request_throughput": 39.2,
  "mean_e2el": 128.5,
  "p99_e2el": 245.7
}
```
**Interpretation:** Near saturation, latency increases significantly

## Performance Expectations

### Throughput Scaling
- **25% Load**: Should achieve exactly 25% of max RPS
- **50% Load**: Should achieve exactly 50% of max RPS
- **75% Load**: May achieve slightly less than 75% due to saturation effects

### Latency Scaling
- **25% Load**: Latency should be close to Stage 1 (max throughput)
- **50% Load**: Moderate increase (1.5-2x of 25%)
- **75% Load**: Significant increase (2-3x of 50%)

## Next Steps

After baseline sweep testing:
1. Run [Latency Concurrent Tests](latency-concurrent.md) to find optimal concurrency
2. Compare performance across different core counts
3. Test with different CPU affinity configurations
4. Analyze performance/cost trade-offs

## Related Documentation

- [Latency Concurrent Methodology](latency-concurrent.md)
- [Embedding Models Overview](embedding-models.md)
- [Model Matrix](../../models/embedding-models/model-matrix.yaml)
