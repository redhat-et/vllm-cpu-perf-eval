# vLLM vs GuideLLM Metrics Comparison

This document shows how vLLM live metrics compare to GuideLLM benchmark results, enabling you to validate performance and compare real-time vs batch analysis.

## Metric Mapping

### 1. **Time to First Token (TTFT)**

**vLLM Live Metrics (real-time):**
```promql
# P50 TTFT in seconds
histogram_quantile(0.50, rate(vllm_time_to_first_token_seconds_bucket[1m]))

# P95 TTFT
histogram_quantile(0.95, rate(vllm_time_to_first_token_seconds_bucket[1m]))

# P99 TTFT
histogram_quantile(0.99, rate(vllm_time_to_first_token_seconds_bucket[1m]))
```

**GuideLLM Batch Results:**
```promql
# P50 TTFT in milliseconds (already aggregated)
guidellm_ttft_ms_p50{model="meta-llama__Llama-3.2-1B-Instruct",workload="chat"}

# P95 TTFT
guidellm_ttft_ms_p95{model="meta-llama__Llama-3.2-1B-Instruct",workload="chat"}

# P99 TTFT
guidellm_ttft_ms_p99{model="meta-llama__Llama-3.2-1B-Instruct",workload="chat"}
```

**Comparison:** GuideLLM provides percentiles calculated across the entire benchmark run. vLLM live metrics show real-time percentiles calculated over the scrape window.

---

### 2. **Inter-Token Latency (ITL / TPOT)**

**vLLM Live Metrics:**
```promql
# P50 Time Per Output Token (TPOT) in seconds
histogram_quantile(0.50, rate(vllm_time_per_output_token_seconds_bucket[1m]))

# P95 TPOT
histogram_quantile(0.95, rate(vllm_time_per_output_token_seconds_bucket[1m]))
```

**GuideLLM Batch Results:**
```promql
# P50 ITL in milliseconds
guidellm_itl_ms_p50{model="meta-llama__Llama-3.2-1B-Instruct"}

# P95 ITL
guidellm_itl_ms_p95{model="meta-llama__Llama-3.2-1B-Instruct"}
```

**Note:** vLLM calls this "time_per_output_token" while GuideLLM calls it "inter_token_latency" - they measure the same thing!

---

### 3. **End-to-End Request Latency**

**vLLM Live Metrics:**
```promql
# P50 E2E latency in seconds
histogram_quantile(0.50, rate(vllm_request_duration_seconds_bucket[1m]))

# P95 E2E latency
histogram_quantile(0.95, rate(vllm_request_duration_seconds_bucket[1m]))

# P99 E2E latency
histogram_quantile(0.99, rate(vllm_request_duration_seconds_bucket[1m]))
```

**GuideLLM Batch Results:**
```promql
# P50 E2E latency in milliseconds
guidellm_e2e_latency_ms_p50{model="meta-llama__Llama-3.2-1B-Instruct"}

# P95 E2E latency
guidellm_e2e_latency_ms_p95{model="meta-llama__Llama-3.2-1B-Instruct"}
```

---

### 4. **Throughput (Tokens/Second)**

**vLLM Live Metrics:**
```promql
# Total tokens generated per second
rate(vllm_generation_tokens_total[1m])

# Prompt tokens processed per second
rate(vllm_prompt_tokens_total[1m])

# Combined throughput
rate(vllm_generation_tokens_total[1m]) + rate(vllm_prompt_tokens_total[1m])
```

**GuideLLM Batch Results:**
```promql
# Mean throughput (tokens/sec)
guidellm_throughput_tokens_per_sec_mean{model="meta-llama__Llama-3.2-1B-Instruct"}

# P95 throughput
guidellm_throughput_tokens_per_sec_p95{model="meta-llama__Llama-3.2-1B-Instruct"}

# Max throughput
guidellm_throughput_tokens_per_sec_max{model="meta-llama__Llama-3.2-1B-Instruct"}
```

**Comparison:** vLLM shows instantaneous throughput rate. GuideLLM shows statistical distribution across the benchmark.

---

### 5. **Success Rate**

**vLLM Live Metrics:**
```promql
# Success rate (%) over 1 minute
(rate(vllm_request_success_total[1m]) / rate(vllm_request_total[1m])) * 100
```

**GuideLLM Batch Results:**
```promql
# Success rate (%) for entire benchmark
guidellm_success_rate_percent{model="meta-llama__Llama-3.2-1B-Instruct"}
```

---

### 6. **Request Counts**

**vLLM Live Metrics:**
```promql
# Total requests
vllm_request_total

# Successful requests
vllm_request_success_total

# Request rate (req/s)
rate(vllm_request_total[1m])
```

**GuideLLM Batch Results:**
```promql
# Total requests in benchmark
guidellm_total_requests{model="meta-llama__Llama-3.2-1B-Instruct"}

# Successful requests
guidellm_successful_requests{model="meta-llama__Llama-3.2-1B-Instruct"}

# Failed requests
guidellm_failed_requests{model="meta-llama__Llama-3.2-1B-Instruct"}
```

---

## Comparison Dashboard Panels

### Panel 1: TTFT Comparison (Live vs Batch)

**Query A - vLLM Live P95 (convert to ms):**
```promql
histogram_quantile(0.95, rate(vllm_time_to_first_token_seconds_bucket[1m])) * 1000
```

**Query B - GuideLLM Batch P95:**
```promql
guidellm_ttft_ms_p95{model="meta-llama__Llama-3.2-1B-Instruct"}
```

**Visualization:** Time series graph with both metrics overlaid

---

### Panel 2: Throughput Comparison

**Query A - vLLM Live (tokens/sec):**
```promql
rate(vllm_generation_tokens_total[1m])
```

**Query B - GuideLLM Mean Throughput:**
```promql
guidellm_throughput_tokens_per_sec_mean{model="meta-llama__Llama-3.2-1B-Instruct"}
```

**Visualization:** Time series or stat panel

---

### Panel 3: Load vs Latency Curves (GuideLLM Only)

This is where GuideLLM shines - showing how latency changes across different load levels:

```promql
# P95 TTFT across all request rates
guidellm_ttft_ms_p95{model="meta-llama__Llama-3.2-1B-Instruct"}
```

**X-Axis:** `request_rate` label
**Y-Axis:** Latency (ms)
**Visualization:** Line graph showing latency curve

---

### Panel 4: Throughput Saturation Curve (GuideLLM Only)

```promql
# Throughput vs load
guidellm_throughput_tokens_per_sec_mean{model="meta-llama__Llama-3.2-1B-Instruct"}
```

**X-Axis:** `request_rate` label
**Y-Axis:** Throughput (tokens/sec)
**Visualization:** Shows where throughput plateaus

---

## Use Cases

### During Benchmark (vLLM Live Metrics)

**What to watch:**
1. **Queue buildup** - `vllm_request_waiting` increasing?
2. **Latency spikes** - P99 TTFT suddenly jumping?
3. **Cache pressure** - `vllm_gpu_cache_usage_perc` near 100%?
4. **Throughput trends** - Generation rate dropping under high load?

**Example queries:**
```promql
# Is the queue building up?
vllm_request_waiting

# Are we hitting cache limits?
vllm_gpu_cache_usage_perc

# What's the current request rate?
rate(vllm_request_total[1m])
```

### After Benchmark (GuideLLM Results)

**What to analyze:**
1. **Load curves** - How does latency scale with load?
2. **Throughput ceiling** - What's the max sustainable throughput?
3. **Platform comparison** - AMD vs Intel performance
4. **Configuration impact** - How do cores/TP affect results?

**Example queries:**
```promql
# Compare throughput across platforms
guidellm_throughput_tokens_per_sec_max{
  model="meta-llama__Llama-3.2-1B-Instruct",
  cores="16"
}

# Find optimal request rate (highest throughput before latency degrades)
guidellm_throughput_tokens_per_sec_mean{
  model="meta-llama__Llama-3.2-1B-Instruct"
}
/ on(platform,model,workload,cores)
guidellm_ttft_ms_p95{
  model="meta-llama__Llama-3.2-1B-Instruct"
}
```

---

## Validation Workflow

### Step 1: Run Benchmark with Both Metrics Enabled

```bash
# Terminal 1: Start monitoring stack with SSH tunnels
cd automation/test-execution/grafana/scripts
./setup-tunnels.sh setup

# Terminal 2: Run benchmark
cd automation/test-execution/ansible
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "publish_to_prometheus=true"
```

### Step 2: Monitor Live During Test

Open Grafana → **vLLM Live Metrics** dashboard

**Watch for:**
- Request latencies staying stable
- No queue buildup
- Throughput matching expected rate
- Cache not filling up

### Step 3: Analyze Results After Test

Open Grafana → Create new dashboard or use existing

**Compare:**
1. **Live P95 TTFT** vs **GuideLLM P95 TTFT** - Should be very close!
2. **Live throughput** vs **GuideLLM mean throughput** - Validate accuracy
3. **Success rates** - Should be 100% or explain failures

### Step 4: Cross-Validate

```promql
# vLLM live average during benchmark window
avg_over_time(
  histogram_quantile(0.95, rate(vllm_time_to_first_token_seconds_bucket[1m]))[10m:]
) * 1000

# Compare to GuideLLM P95 for same period
guidellm_ttft_ms_p95{
  model="meta-llama__Llama-3.2-1B-Instruct",
  test_run_id="20260320-135847"
}
```

**Expected:** Within 5-10% variance is normal due to:
- Sampling windows
- Calculation methods
- System noise

---

## Key Differences

| Aspect | vLLM Live Metrics | GuideLLM Batch Results |
|--------|-------------------|------------------------|
| **Granularity** | Per-request, scraped every 10s | Aggregated per benchmark run |
| **Percentiles** | Calculated over scrape window | Calculated over entire test |
| **Use Case** | Real-time monitoring, debugging | Performance analysis, comparison |
| **Retention** | Time-series (default 30 days) | Persistent via Pushgateway |
| **Load Curves** | No | Yes (multiple request rates) |
| **Platform Comparison** | Limited | Excellent (multi-platform tags) |

---

## Example Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│ Row 1: Real-Time Monitoring (vLLM Live)            │
├─────────────────────────────────────────────────────┤
│ TTFT P95 │ ITL P95 │ Throughput │ Queue │ Cache    │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Row 2: Benchmark Results Comparison                │
├─────────────────────────────────────────────────────┤
│ Live vs Batch │ Success Rate │ Request Counts      │
│ TTFT          │              │                      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Row 3: Load Sweep Analysis (GuideLLM Only)         │
├─────────────────────────────────────────────────────┤
│ Throughput vs Load │ TTFT vs Load │ Max Throughput │
│ (full curve)       │ (latency curve)│ (stat panel)  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Row 4: Platform Comparison (GuideLLM Only)         │
├─────────────────────────────────────────────────────┤
│ AMD vs Intel Throughput │ AMD vs Intel Latency     │
└─────────────────────────────────────────────────────┘
```

---

## Pro Tips

1. **Use both metrics together:**
   - Live metrics → Spot issues during test
   - Batch results → Analyze performance characteristics

2. **Validate with live metrics:**
   - If GuideLLM shows great throughput but live metrics show queue buildup → investigate

3. **Compare across runs:**
   - Use `test_run_id` label to track specific benchmark runs
   - Compare baseline vs optimized configurations

4. **Label consistency:**
   - Both use same model/workload/cores labels
   - Easy to correlate live and batch data

---

## Next Steps

1. ✅ vLLM live metrics working
2. ⏳ Waiting for benchmark to complete
3. 🔜 GuideLLM results will be pushed to Prometheus
4. 📊 Create comparison dashboard (see example queries above)

Once your current benchmark completes, you'll have both datasets in Prometheus and can create powerful comparison visualizations!
