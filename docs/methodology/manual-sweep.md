# Manual Sweep Testing Guide

<!-- markdownlint-disable MD013 MD024 MD032 MD031 MD033 -->

## Overview

This guide describes how to manually execute each stage of the sweep test process. While GuideLLM provides an automated `sweep` profile, manual execution gives you greater control and insight into system behavior, especially for detecting oversaturation, undersaturation, and determining optimal stopping points.

## Why Run Sweep Stages Manually?

The automated sweep test has several limitations:

- **Limited Saturation Detection**: May not accurately detect when a system becomes oversaturated or remains undersaturated
- **Fixed Stopping Criteria**: Uses predefined time or request limits rather than adapting to observed system behavior
- **Reduced Visibility**: Automated execution can obscure important performance transitions and degradation patterns
- **No Mid-Test Adjustments**: Cannot modify parameters based on intermediate results

Manual execution allows you to:

- Observe real-time metrics at each load level
- Make informed decisions about when saturation occurs
- Adjust test parameters based on observed behavior
- Stop testing when meaningful data has been collected
- Identify the optimal operating range more precisely

## Understanding the Sweep Test Concept

The sweep test is designed to characterize system performance across different load levels by executing multiple benchmarking strategies in sequence:

1. **Baseline Discovery** (Stage 1): Measure single-threaded throughput
2. **Capacity Discovery** (Stage 2): Measure maximum parallel throughput
3. **Range Characterization** (Stages 3-N): Test intermediate load levels between baseline and capacity

The automated sweep interpolates load levels linearly, but manual execution lets you adaptively choose load levels based on observed performance.

## Prerequisites

Before beginning manual sweep testing:

```bash
# Ensure GuideLLM is installed
pip install guidellm

# Verify your system under test is running
# Example: vLLM server at http://localhost:8000
curl http://localhost:8000/health

# Choose consistent test parameters
# - Prompt token count (e.g., 256)
# - Output token count (e.g., 128)
# - Test duration (e.g., 60 seconds minimum per stage)
```

## Stage 1: Baseline Synchronous Testing

### Purpose

Measure the system's baseline sequential throughput - how fast it can process requests one at a time without any concurrency overhead.

### When to Run

Always start with this stage to establish your lower bound performance baseline.

### How to Execute

```bash
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile synchronous \
  --max-seconds 60 \
  --output-format json \
  --output-path stage1-synchronous.json
```

### What to Observe

Monitor these key metrics during execution:

- **Requests Per Second**: Your baseline throughput rate
- **Time to First Token (TTFT)**: Baseline latency for request initiation
- **Request Latency**: Total time per request
- **Consistency**: TTFT values should be similar across requests (healthy baseline performance)

### Interpreting Results

```bash
# View results
guidellm report generate --input stage1-synchronous.json

# Key values to extract:
# - Average requests/second (baseline_rate)
# - P50/P95/P99 TTFT
# - P50/P95/P99 request latency
```

**Example Output**:

```text
Synchronous Rate: 12.5 req/sec
P50 TTFT: 145ms
P95 TTFT: 189ms
P50 Latency: 3.2s
```

**Record**: Save the `baseline_rate` value (e.g., 12.5 req/sec) for
use in later stages.

### Signs of Issues

- **High variance in TTFT**: System resource contention or instability
- **Very low throughput**: Configuration issues or system problems
- **Increasing latency over time**: Memory leaks or resource exhaustion

### When to Stop

Run for at least 60 seconds to ensure stable measurements. Continue until metrics stabilize (variance decreases).

## Stage 2: Maximum Capacity Testing

### Purpose

Determine the maximum throughput your system can sustain when processing requests as fast as possible with maximum parallelism.

### When to Run

After completing Stage 1 and recording your baseline rate.

### How to Execute

```bash
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile throughput \
  --max-seconds 120 \
  --output-format json \
  --output-path stage2-throughput.json
```

### What to Observe

Monitor for saturation indicators:

- **Requests Per Second**: Should plateau at maximum capacity
- **Time to First Token (TTFT)**: Watch for increasing trends
- **Concurrent Requests**: Track how many requests are in-flight
- **CPU Utilization**: Should be high (80-100%) at saturation on CPU-based systems
  - Unlike GPUs, CPUs may not reach 100% due to I/O waits, memory bandwidth limits, or thread scheduling
  - Monitor all CPU cores - check if specific cores are bottlenecked
- **Queue Depth**: Increasing queue indicates oversaturation

### Interpreting Results

```bash
# View results
guidellm report generate --input stage2-throughput.json

# Key values to extract:
# - Maximum sustained requests/second (max_capacity_rate)
# - Concurrent request count at peak
# - TTFT degradation compared to Stage 1
```

**Example Output**:

```text
Maximum Throughput: 156.3 req/sec
Peak Concurrent Requests: 48
P50 TTFT: 2.1s (14x increase from baseline)
P95 TTFT: 4.8s
P50 Latency: 5.9s
```

**Record**: Save the `max_capacity_rate` value (e.g., 156.3 req/sec) for
calculating intermediate stages.

### Signs of Saturation

This table helps you identify whether your system is undersaturated, at
optimal load, or oversaturated. All metrics come from the GuideLLM report
output and can be monitored in real-time during testing.

| Indicator | Undersaturated | Optimal | Oversaturated | Where to Find This |
| --- | --- | --- | --- | --- |
| **TTFT Trend** | Flat, matches baseline<br/>(~150ms like Stage 1) | Slight increase, stable<br/>(300-450ms, not growing) | Rapidly increasing<br/>(starts at 500ms, grows to 2s+) | GuideLLM report: "Time to First Token" metrics<br/>Compare P50 across the test duration |
| **Throughput** | Below capacity<br/>(achieving 50-100 req/sec when max is 150+) | At capacity, stable<br/>(achieving 145-150 req/sec consistently) | Plateaued or decreasing<br/>(target is 150 but only achieving 130-140) | GuideLLM report: "Requests per Second"<br/>Compare "Achieved Rate" vs "Target Rate" |
| **Queue Depth** | Near zero<br/>(0-5 queued requests) | Low, stable<br/>(5-20 queued requests, not growing) | Growing continuously<br/>(starts at 20, grows to 100+) | **Not directly in GuideLLM report**<br/>Monitor server logs or use system monitoring<br/>(vLLM: check `/metrics` endpoint for queue size) |
| **Latency P95/P99** | Similar to P50<br/>(P50=150ms, P95=200ms) | 2-3x P50<br/>(P50=300ms, P95=700ms) | 5-10x P50 or higher<br/>(P50=500ms, P95=4s) | GuideLLM report: "Request Latency" section<br/>Look at percentile breakdown (P50/P95/P99) |
| **Concurrent Requests** | Low<br/>(5-15 concurrent) | Moderate, stable<br/>(20-40 concurrent, steady) | Very high, increasing<br/>(50+ and climbing) | GuideLLM report: "Concurrent Requests" metric<br/>Also check server metrics/dashboard |

#### How to Interpret Each Metric

**TTFT Trend** (Time to First Token):
- **Source**: GuideLLM report shows P50/P95/P99 TTFT values
- **How to check**: Compare TTFT at start of test vs end of test
  - Healthy: TTFT stays roughly the same throughout (±10%)
  - Oversaturated: TTFT at end is 2x+ higher than at start

**Throughput**:
- **Source**: GuideLLM report shows "Requests per Second"
- **Below capacity**: Achieved rate is less than what system can handle (you could push more)
  - Example: System can do 150 req/sec but you're only seeing 80 req/sec
- **At capacity**: Achieved rate matches maximum sustainable throughput
  - Example: System achieves 150 req/sec and stays there
- **Oversaturated**: Cannot achieve target rate or rate is decreasing
  - Example: Target is 150 req/sec but only achieving 130 req/sec (or dropping from 150→140→130)

**Queue Depth**:
- **Source**: Not in GuideLLM report - check your server directly
  - **vLLM**: Check `http://your-server:8000/metrics` endpoint, look for queue-related metrics
  - **System monitoring**: Use Prometheus, Grafana, or server logs
  - **Manual check**: Some servers log queue depth in their console output
- **What it means**: How many requests are waiting to be processed
  - Near zero: System is keeping up, no backlog
  - Low/stable: System has a small buffer but isn't falling behind
  - Growing: System cannot keep up, backlog is building

**Latency P95/P99**:
- **Source**: GuideLLM report shows percentile breakdown
- **What to look for**: Gap between P50 (median) and P95/P99 (worst cases)
  - Small gap (P95 ≈ 1.3x P50): Consistent performance
  - Moderate gap (P95 ≈ 2-3x P50): Some variance but acceptable
  - Large gap (P95 ≈ 5-10x P50): Significant variance, some requests very slow

**Concurrent Requests**:
- **Source**: GuideLLM report and server metrics
- **What it means**: How many requests are being processed at the same time
  - Should be proportional to your request rate and request duration
  - Formula: `Concurrent ≈ Rate × Average_Latency`
  - Example: 50 req/sec × 0.5s latency = ~25 concurrent requests
- **Warning sign**: If concurrent count keeps growing, system is falling behind

#### Quick Check Example

During a Stage 2 (throughput) test, at minute 1 vs minute 2:

**Healthy System** ✅:

```text
Minute 1: 150 req/sec, P50 TTFT=300ms, 30 concurrent
Minute 2: 150 req/sec, P50 TTFT=305ms, 31 concurrent
→ Stable metrics, system at optimal capacity
```

**Oversaturated System** 🔴:

```text
Minute 1: 145 req/sec, P50 TTFT=500ms, 35 concurrent
Minute 2: 138 req/sec, P50 TTFT=1.2s, 58 concurrent
→ Decreasing throughput, increasing TTFT and concurrency = oversaturated
```

#### CPU-Specific Saturation Indicators

For **CPU-based systems**, watch for these additional signs:

**Pre-Saturation (System approaching limits)**:
- CPU utilization reaches 80-95% across all cores
- Context switches increasing significantly (check with `vmstat` or `pidstat`)
- System load average approaching or exceeding CPU core count
- Memory bandwidth utilization high (check with `perf` or system monitoring)

**At Saturation (System at maximum capacity)**:
- CPU may not reach 100% due to I/O waits or memory bottlenecks
- High CPU "steal" time in virtualized environments (check `top` or `mpstat`)
- Increased cache misses as concurrency grows
- Thread scheduling delays become noticeable

**Over-Saturation (System degrading)**:
- CPU usage may actually **decrease** as system spends more time context switching
- "Load average" significantly exceeds CPU core count (e.g., 64 cores but load = 120)
- Memory pressure builds (check `free -h` for available memory)
- Swap usage begins (major performance degradation indicator)

**How to monitor CPU saturation**:
```bash
# Watch CPU usage per core
mpstat -P ALL 1

# Monitor system load and context switches
vmstat 1

# Check memory pressure
free -h

# Monitor CPU frequency (check for throttling)
watch -n 1 "grep MHz /proc/cpuinfo"
```

**Key difference from GPU systems**: CPU saturation often manifests as **increasing variability** in response times rather than pure throughput limits. You may see TTFT spread widely (large P95/P99 gaps) before throughput actually drops.

### When to Stop

**Stop when you observe**:
- Throughput plateau (no increase for 30+ seconds)
- TTFT shows consistent upward trend
- Queue depth continuously growing
- Error rate begins increasing

**Critical**: Do not run this stage longer than necessary once saturation is detected - it may cause system instability.

## Stage 3+: Intermediate Load Testing

### Purpose

Characterize system performance at various load levels between baseline and maximum capacity to identify the optimal operating point.

### When to Run

After completing Stages 1 and 2, with recorded baseline_rate and max_capacity_rate.

### Calculating Test Points

Calculate intermediate load levels using one of three strategies. For this example, we'll use:
- **baseline_rate** = 12.5 req/sec (from Stage 1)
- **max_capacity_rate** = 156.3 req/sec (from Stage 2)

#### Strategy 1: Percentage-Based (Recommended for Manual Testing)

Calculate test rates as percentages of maximum capacity:

**Formula**: `test_rate = max_capacity_rate × percentage`

**Example calculations**:
- 25% of capacity: 156.3 × 0.25 = **39.1 req/sec**
- 50% of capacity: 156.3 × 0.50 = **78.2 req/sec**
- 75% of capacity: 156.3 × 0.75 = **117.2 req/sec**

This is the simplest approach and provides good coverage across the performance range. Start with these three rates and adjust based on observed performance.

#### Strategy 2: Linear Interpolation

Calculate evenly-spaced rates between baseline and maximum capacity:

**Formula**: `step = (max_capacity_rate - baseline_rate) ÷ (num_points + 1)`

Then: `rate[i] = baseline_rate + (i × step)` for i = 1, 2, 3...

**Example with 6 points**:
1. Calculate step size: (156.3 - 12.5) ÷ 7 = 20.5
2. Calculate each rate:
   - Rate 1: 12.5 + (1 × 20.5) = **33.0 req/sec**
   - Rate 2: 12.5 + (2 × 20.5) = **53.5 req/sec**
   - Rate 3: 12.5 + (3 × 20.5) = **74.0 req/sec**
   - Rate 4: 12.5 + (4 × 20.5) = **94.5 req/sec**
   - Rate 5: 12.5 + (5 × 20.5) = **115.0 req/sec**
   - Rate 6: 12.5 + (6 × 20.5) = **135.5 req/sec**

This approach mirrors the automated sweep test behavior.

#### Strategy 3: Binary Search (Adaptive)

Start with 50% of max capacity, then narrow the range based on results:

1. **First test**: 50% of max (78.2 req/sec)
2. **If healthy** → Test 75% (halfway between 50% and 100%)
3. **If warning/oversaturated** → Test 25% (halfway between 0% and 50%)
4. Continue halving the range until you find the saturation boundary

**Example progression**:
- Test 50%: Healthy ✅ → Test higher
- Test 75%: Oversaturated 🔴 → Test between 50-75%
- Test 62.5%: Warning ⚠️ → Test between 50-62.5%
- Test 56%: Healthy ✅ → Optimal range found: 56-62.5%

This is the most efficient for finding the exact saturation point.

#### Optional: Automated Calculation Examples

If you prefer to use Python for calculations:

<details>
<summary>Click to expand Python calculation examples</summary>

```python
# Calculate suggested test rates
baseline_rate = 12.5  # from Stage 1
max_capacity_rate = 156.3  # from Stage 2

# Strategy 1: Percentage-based (simplest)
rates = [
    max_capacity_rate * 0.25,  # 39.1 req/sec
    max_capacity_rate * 0.50,  # 78.2 req/sec
    max_capacity_rate * 0.75,  # 117.2 req/sec
]

# Strategy 2: Linear interpolation
num_points = 6
step = (max_capacity_rate - baseline_rate) / (num_points + 1)
rates = [baseline_rate + (i * step) for i in range(1, num_points + 1)]
# Results: [33.0, 53.5, 74.0, 94.5, 115.0, 135.5] req/sec

# Strategy 3: Logarithmic spacing (concentrates more points at lower rates)
import numpy as np
rates = np.logspace(
    np.log10(baseline_rate),
    np.log10(max_capacity_rate),
    num=8
)[1:-1]  # Exclude baseline and max
# Results: [19.8, 31.3, 49.5, 78.3, 123.8, 195.7] req/sec
```

</details>

### How to Execute Each Test Point

For each calculated rate, run an async constant rate test:

```bash
# Example: Testing at 50% of max capacity (78.2 req/sec)
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile constant \
  --rate 78.2 \
  --max-seconds 90 \
  --output-format json \
  --output-path stage3-rate-78.json
```

**Recommended order**: Start at the lowest rate and work upward.

### What to Observe at Each Load Level

Track performance degradation as load increases:

1. **Time to First Token (TTFT)**
   - Compare to Stage 1 baseline
   - Calculate degradation ratio: `current_TTFT / baseline_TTFT`
   - Acceptable degradation: < 2x baseline
   - Warning zone: 2-5x baseline
   - Oversaturation: > 5x baseline

2. **Request Success Rate**
   - Should remain at 100% in optimal range
   - Drops indicate oversaturation or errors

3. **Throughput vs. Target Rate**
   - Achieved rate should match target rate
   - Gap indicates system cannot keep up (oversaturated)

4. **Concurrent Request Count**
   - Stable and proportional to rate = healthy
   - Continuously growing = oversaturated

### Analyzing Results

After each test point, compare metrics:

```bash
# Generate comparative report
guidellm report generate \
  --input stage1-synchronous.json \
  --input stage2-throughput.json \
  --input stage3-rate-78.json

# Look for:
# 1. TTFT degradation from baseline
# 2. Latency percentile spreads (P95/P99 vs P50)
# 3. Achieved vs target rate
```

**Example Analysis**:

| Stage | Target Rate | Achieved Rate | P50 TTFT | TTFT vs Baseline | P95 TTFT | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 1 (Sync) | - | 12.5 | 145ms | 1.0x | 189ms | Baseline |
| 3a | 39.1 | 39.0 | 218ms | 1.5x | 287ms | ✅ Healthy |
| 3b | 78.2 | 78.1 | 456ms | 3.1x | 892ms | ⚠️ Warning |
| 3c | 117.2 | 115.8 | 1.2s | 8.3x | 3.4s | 🔴 Oversaturated |
| 2 (Max) | - | 156.3 | 2.1s | 14.5x | 4.8s | 🔴 Oversaturated |

**Interpretation**: Optimal operating range is between 39-78 req/sec.

### Adaptive Testing Strategy

Based on observed results, adjust your next test points:

**If current load shows healthy performance** (TTFT < 2x baseline):
- Test at a higher rate (e.g., midpoint between current and max)
- Continue until you find the saturation boundary

**If current load shows warning signs** (TTFT 2-5x baseline):
- Test at a slightly lower rate to find the optimal point
- Narrow the range between current and previous healthy rate

**If current load is oversaturated** (TTFT > 5x baseline):
- Do not test higher rates
- Test lower rates to find the saturation boundary
- Consider the previous rate as near-optimal

### When to Stop Intermediate Testing

Stop when you have:

1. **Identified saturation boundary**: Found the load level where TTFT degradation exceeds acceptable limits
2. **Characterized optimal range**: Tested at least 2-3 points within healthy performance zone
3. **Observed clear degradation pattern**: Can draw a performance curve from baseline to saturation
4. **Reached diminishing returns**: Additional test points provide minimal new information

**Example stopping criteria**:

```text
✅ Stop: You've tested 25%, 50%, 60%, and 70% of max capacity
   - 25% and 50% show healthy performance
   - 60% shows warning signs
   - 70% is oversaturated
   → Optimal range identified: 50-60% of max capacity

❌ Don't stop: You've only tested 25% and 75%
   - Large gap between test points
   - Cannot determine where saturation begins
   → Continue testing at 50% to narrow the range
```

## Identifying Optimal Operating Point

### Metrics-Based Analysis

Calculate the optimal operating rate using collected data:

1. **TTFT Degradation Method**:

   ```text
   Optimal rate = Highest rate where TTFT < 2x baseline
   ```

2. **Throughput Efficiency Method**:

   ```text
   Efficiency = (Achieved Rate / Target Rate) × (Baseline TTFT / Current TTFT)
   Optimal rate = Rate with highest efficiency score
   ```

3. **Latency Percentile Method**:

   ```text
   Optimal rate = Highest rate where P95 TTFT < 3x P50 TTFT
   ```

### Visual Analysis

If you have graphing capabilities, plot:

1. **TTFT vs. Load Rate**
   - X-axis: Request rate (req/sec)
   - Y-axis: P50 TTFT
   - Look for: Inflection point where TTFT begins increasing rapidly

2. **Throughput vs. Target Rate**
   - X-axis: Target request rate
   - Y-axis: Achieved request rate
   - Look for: Where achieved rate diverges from target (45° line)

3. **Concurrent Requests vs. Load Rate**
   - X-axis: Request rate
   - Y-axis: Average concurrent requests
   - Look for: Exponential growth indicates saturation

### Conservative vs. Aggressive Operating Points

Choose based on your requirements:

**Conservative** (Recommended for production):

- Select rate where TTFT < 1.5x baseline
- Provides headroom for traffic spikes
- Maintains consistent user experience

**Balanced** (Common choice):

- Select rate where TTFT < 2.5x baseline
- Good utilization with acceptable latency
- Some degradation under sustained load

**Aggressive** (Maximum utilization):

- Select rate near saturation boundary
- Highest throughput but increased latency
- Risks performance degradation during peaks

## Best Practices

### Test Environment

- **Consistency**: Use the same prompt_tokens and output_tokens across all stages
- **Isolation**: Ensure no other workload on the system under test
- **Stability**: Wait for system to stabilize between stages (30-60 seconds)
- **Monitoring**: Track system resources during tests:
  - **CPU utilization**: Per-core and overall CPU usage
  - **Memory usage**: RAM utilization and available memory
  - **CPU temperature**: Thermal throttling can impact performance
  - **System load**: Check load average (should not exceed CPU core count significantly)

### Data Collection

- **Save all results**: Keep JSON output from every stage for later analysis
- **Record observations**: Note any anomalies or system events during testing
- **Document configuration**: Record system settings, model parameters, batch sizes
- **Timestamp tests**: Track when each stage was run for correlation with system logs

### Interpreting Edge Cases

#### Case 1: TTFT increases linearly from baseline

- System is scaling well but has latency overhead
- Optimal point depends on acceptable latency budget

#### Case 2: TTFT remains flat until sudden increase

- Clear saturation boundary
- Optimal point is just before the inflection point

#### Case 3: TTFT is inconsistent (high variance)

- System instability or external factors
- Repeat tests or investigate root cause before determining optimal rate

#### Case 4: Achieved rate never reaches target

- System capacity is below your test range
- Lower your test rates or investigate system bottlenecks

### Common Pitfalls

1. **Testing for too short**: Run each stage for at least 60-90 seconds to get stable metrics
2. **Skipping baseline**: Always establish baseline before testing higher loads
3. **Testing beyond saturation**: Once oversaturated, stop and test lower rates
4. **Ignoring variance**: High variance indicates unreliable results - investigate before proceeding
5. **Not accounting for warmup**: First few seconds may show different performance - exclude from analysis

## Example: Complete Manual Sweep Session

Here's a complete walkthrough of a manual sweep testing session:

### Setup

```bash
# System under test: Llama-3.1-8B model
# Hardware: CPU-based deployment (e.g., 32 vCPUs, 128GB RAM)
# Test parameters: 256 input tokens, 128 output tokens

# Create directory for results
mkdir -p sweep-results
cd sweep-results
```

### Stage 1: Baseline

```bash
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile synchronous \
  --max-seconds 60 \
  --output-format json \
  --output-path stage1-sync.json

# Result: 14.2 req/sec, P50 TTFT: 128ms
```

### Stage 2: Maximum Capacity

```bash
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile throughput \
  --max-seconds 120 \
  --output-format json \
  --output-path stage2-throughput.json

# Result: 185.7 req/sec, P50 TTFT: 1.8s
# TTFT increased 14x - system is oversaturated at max throughput
```

### Stage 3: Intermediate Tests

```bash
# Calculate test points: 25%, 50%, 75% of max capacity
# 25% = 46.4 req/sec
# 50% = 92.9 req/sec
# 75% = 139.3 req/sec

# Test 25% capacity
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile constant \
  --rate 46.4 \
  --max-seconds 90 \
  --output-format json \
  --output-path stage3a-rate-46.json

# Result: 46.4 req/sec achieved, P50 TTFT: 195ms (1.5x baseline)
# Status: ✅ Healthy - continue upward

# Test 50% capacity
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile constant \
  --rate 92.9 \
  --max-seconds 90 \
  --output-format json \
  --output-path stage3b-rate-93.json

# Result: 92.7 req/sec achieved, P50 TTFT: 312ms (2.4x baseline)
# Status: ⚠️ Warning zone - approaching saturation

# Test 75% capacity
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile constant \
  --rate 139.3 \
  --max-seconds 90 \
  --output-format json \
  --output-path stage3c-rate-139.json

# Result: 136.1 req/sec achieved, P50 TTFT: 892ms (7.0x baseline)
# Status: 🔴 Oversaturated - do not go higher

# Adaptive test: Try 60% to narrow optimal range
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile constant \
  --rate 111.4 \
  --max-seconds 90 \
  --output-format json \
  --output-path stage3d-rate-111.json

# Result: 110.8 req/sec achieved, P50 TTFT: 445ms (3.5x baseline)
# Status: ⚠️ Still in warning zone
```

### Analysis and Conclusion

```bash
# Generate comparative report
guidellm report generate \
  --input stage*.json \
  --output-format html \
  --output-path sweep-analysis.html
```

**Summary**:

- **Baseline throughput**: 14.2 req/sec
- **Maximum capacity**: 185.7 req/sec (oversaturated)
- **Optimal operating range**: 46-93 req/sec (25-50% of max capacity)
- **Recommended operating point**: 70 req/sec (38% of max)
  - TTFT degradation: ~2x baseline (acceptable)
  - Provides headroom for traffic spikes
  - Maintains low latency percentiles

**Decision**: Configure production load balancing to target 65-75 req/sec
per instance.

## Advanced Topics

### Using Over-Saturation Detection

GuideLLM includes automated over-saturation detection that can be used during manual testing:

```bash
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile constant \
  --rate 100 \
  --over-saturation '{"enabled": true, "min_seconds": 30, "max_window_seconds": 120, "moe_threshold": 2.0}' \
  --output-format json \
  --output-path stage-with-saturation-detection.json
```

The benchmark will automatically stop if saturation is detected based on:

- Increasing TTFT trends
- Concurrent request growth
- Statistical slope analysis

### Testing with Different Request Patterns

Instead of constant rate, try Poisson distribution for more realistic traffic:

```bash
guidellm benchmark run \
  --target "http://localhost:8000" \
  --data "prompt_tokens=256,output_tokens=128" \
  --profile poisson \
  --rate 80 \
  --max-seconds 90 \
  --output-format json \
  --output-path stage-poisson-80.json
```

Poisson patterns introduce natural variance, revealing how the system handles bursty traffic.

### Multi-Dimensional Sweeps

Test different prompt/output token combinations to understand capacity across workload types:

```bash
# Small requests (128 input, 64 output)
guidellm benchmark run --data "prompt_tokens=128,output_tokens=64" ...

# Medium requests (256 input, 128 output)
guidellm benchmark run --data "prompt_tokens=256,output_tokens=128" ...

# Large requests (512 input, 256 output)
guidellm benchmark run --data "prompt_tokens=512,output_tokens=256" ...
```

Compare optimal operating points across workload sizes.

## Troubleshooting

### Problem: Metrics are inconsistent between runs

**Solution**:

- Ensure system is stable (check CPU temperature, system load,
  memory pressure)
  - **CPU thermal throttling**: Check `sensors` or system monitoring -
    throttling causes inconsistent performance
  - **Background processes**: Use `top` or `htop` to check for competing
    workloads
  - **Swap usage**: If system is swapping to disk, performance will be
    erratic
- Wait longer between stages (60+ seconds) to let CPU temperatures stabilize
- Increase test duration (120+ seconds per stage)
- Check CPU governor settings (should be "performance" not "powersave" for
  consistent results)

### Problem: Cannot reach target rate even at low loads

**Solution**:

- System capacity is insufficient for your workload
- Check system resource utilization:
  - **CPU utilization**: Use `top`, `htop`, or `mpstat` - are all cores
    being utilized?
  - **Memory**: Check available RAM - memory exhaustion causes swapping and
    slowdowns
  - **CPU frequency**: Verify CPUs are running at full speed (not throttled)
- Verify network is not the bottleneck
- Review system configuration (batch size, max concurrent requests,
  thread/worker count)

### Problem: TTFT varies widely within a single test

**Solution**:
- System may be experiencing resource contention
- Check for garbage collection pauses or memory issues
- Review system logs for warnings or errors
- Consider testing at a lower rate

### Problem: Throughput stage never saturates

**Solution**:
- Increase test duration (try 180-300 seconds)
- System may have very high capacity
- Verify test is actually reaching the system (check server logs)
- Try adding `--max-concurrency` limit to force saturation

## Summary

Manual sweep testing provides fine-grained control over benchmarking and helps you:

1. **Understand system behavior** at different load levels
2. **Identify saturation boundaries** precisely
3. **Make informed decisions** about optimal operating points
4. **Detect performance issues** early through careful observation
5. **Adapt testing strategy** based on real-time results

The key advantage over automated sweeps is the ability to stop when you have enough data, adjust test points based on observations, and deeply understand your system's performance characteristics.

### Quick Reference: Decision Tree

```text
Start
  ↓
Run Stage 1 (Synchronous)
  → Record baseline_rate and baseline_TTFT
  ↓
Run Stage 2 (Throughput)
  → Record max_capacity_rate
  → Observe saturation level
  ↓
Calculate test rates (25%, 50%, 75% of max_capacity)
  ↓
For each rate (starting lowest):
  ↓
  Run async constant test
  ↓
  Is TTFT < 2x baseline?
    ├─ YES → ✅ Healthy - continue to next higher rate
    └─ NO → Is TTFT 2-5x baseline?
        ├─ YES → ⚠️ Warning - test between current and previous rate
        └─ NO → 🔴 Oversaturated - stop testing higher rates
  ↓
Have you found saturation boundary?
    ├─ NO → Continue testing
    └─ YES → Done!
        ↓
        Select optimal operating point
        (Highest rate where TTFT < 2x baseline)
```

---

For questions or issues with manual sweep testing, consult the [main benchmark documentation](benchmark.md) or [open an issue](https://github.com/anthropics/guidellm/issues).
