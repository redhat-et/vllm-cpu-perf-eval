---
layout: default
title: Metrics Collection Architecture
---

Comprehensive guide to how metrics are collected, stored, and visualized in the vLLM CPU Performance Evaluation framework.

## Overview

The framework collects three types of metrics:

1. **Client-Side Metrics** - GuideLLM benchmark results (always collected)
2. **Server-Side Metrics** - vLLM server performance (automatically collected when available)
3. **System Metrics** - CPU, memory, container stats (collected for managed mode)

**Key Point:** All metrics are collected automatically. Grafana/Prometheus are **optional** for real-time visualization only.

**Deployment Modes:**
- **Managed Mode** (default): vLLM runs in container on DUT → full metrics
- **External Mode**: vLLM runs externally (cloud/K8s) → client metrics + server metrics if `/metrics` exposed

## Metrics Collection Flow

```
┌─────────────────────────────────────────────────────────┐
│ BENCHMARK EXECUTION                                     │
│                                                         │
│  1. vLLM Server Starts on DUT                          │
│  2. Metrics Collector Starts (background)              │
│      ├─ Scrapes http://DUT:8000/metrics every 10s     │
│      └─ Saves to vllm-metrics.json                     │
│  3. GuideLLM Benchmark Runs                           │
│      └─ Saves to benchmarks.json                       │
│  4. Metrics Collector Stops                            │
│  5. System Metrics Collected                           │
│      └─ Saves to system-metrics.log                    │
│                                                         │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ RESULT FILES (results/llm/model/test-id/config/)       │
│                                                         │
│  • benchmarks.json      ← Client-side (GuideLLM)      │
│  • vllm-metrics.json    ← Server-side (vLLM)          │
│  • system-metrics.log   ← System resources             │
│  • test-metadata.json   ← Test configuration           │
│  • vllm-server.log      ← Server logs                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ POST-TEST ANALYSIS                                      │
│                                                         │
│  Streamlit Dashboard                                   │
│   ├─ Client Metrics View                               │
│   ├─ Server Metrics View                               │
│   └─ Unified Analysis View                             │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OPTIONAL: REAL-TIME MONITORING (During Test)           │
│                                                         │
│  Grafana Dashboards (<http://localhost:3000>)            │
│   ├─ vLLM Performance Statistics                       │
│   └─ vLLM Query Statistics                             │
│                                                         │
│  (Requires: Grafana + Prometheus + SSH tunnel)         │
└─────────────────────────────────────────────────────────┘
```

## 1. Client-Side Metrics (GuideLLM)

### Client Metrics: What is Collected

End-user experience metrics from the benchmark client:

- **Throughput**: Total tokens/sec, request rate
- **Latency**: TTFT, ITL, E2E latency (mean, P50, P95, P99)
- **Success Rate**: Request completion percentage
- **Request Distribution**: Prompt tokens, output tokens

### Client Metrics: Collection Method

Automatic - GuideLLM saves results after benchmark completes.

### Client Metrics: Output File

`benchmarks.json`

### Client Metrics: Example Structure

```json
{
  "benchmarks": [
    {
      "request_rate": 16,
      "concurrency": null,
      "completed_request_rate": 15.8,
      "total_num_completed_requests": 158,
      "total_num_errored_requests": 2,
      "total_time": 10.01,
      "completed_requests_per_min": 948.05,
      "request_latency": {
        "mean": 0.634,
        "min": 0.121,
        "max": 1.823,
        "std": 0.234,
        "p25": 0.456,
        "p50": 0.589,
        "p75": 0.721,
        "p90": 0.892,
        "p95": 1.012,
        "p99": 1.456
      },
      "time_to_first_token": { ... },
      "inter_token_latency": { ... }
    }
  ]
}
```

## 2. Server-Side Metrics (vLLM)

### Server Metrics: What is Collected

Internal vLLM server performance metrics:

- **Queue State**: Requests running, waiting
- **Cache Utilization**: KV cache usage percentage
- **Token Processing**: Prompt tokens, generation tokens (cumulative)
- **Request Counters**: Success, failures, preemptions
- **Latency Histograms**: TTFT, ITL, E2E (with percentile buckets)
- **Processing Time**: Prefill time, decode time, queue time

### Server Metrics: Collection Method

**Direct Collection (Default - No Grafana Required)**

1. `vllm_metrics_collector` role starts before benchmark
2. Python script runs in background
3. Scrapes `http://DUT:8000/metrics` every 10 seconds
4. Saves time-series data to JSON file
5. Stops after benchmark completes

**Implementation:**
```yaml
# Automatically integrated in llm-benchmark-auto.yml

pre_tasks:
  - name: Start vLLM metrics collection
    include_role:
      name: vllm_metrics_collector
    vars:
      vllm_url: "http://{{ bench_config.vllm_host }}:8000"
      metrics_collection_interval: 10
      metrics_collection_duration: 720  # 12 minutes

post_tasks:
  - name: Stop vLLM metrics collection
    include_role:
      name: vllm_metrics_collector
      tasks_from: stop
```

### Server Metrics: Output File

`vllm-metrics.json`

### Server Metrics: Example Structure

```json
{
  "collection_info": {
    "source": "direct",
    "vllm_url": "http://ec2-13-59-253-249.us-east-2.compute.amazonaws.com:8000",
    "interval_seconds": 10,
    "start_time": "2026-03-31T13:59:11",
    "end_time": "2026-03-31T14:05:23",
    "test_run_id": "20260331-135911",
    "total_samples": 38,
    "duration_seconds": 372
  },
  "samples": [
    {
      "timestamp": "2026-03-31T13:59:21",
      "elapsed_seconds": 10.0,
      "metrics": {
        "vllm:num_requests_running": [
          {
            "labels": {
              "engine": "0",
              "model_name": "meta-llama/Llama-3.2-1B-Instruct"
            },
            "value": 3.0
          }
        ],
        "vllm:kv_cache_usage_perc": [
          {
            "labels": {...},
            "value": 45.2
          }
        ],
        ...
      }
    }
  ]
}
```

### Configuration Options

```bash
# Skip metrics collection entirely
ansible-playbook llm-benchmark-auto.yml \
  -e "skip_metrics_collection=true"

# Adjust collection interval (default: 10s)
ansible-playbook llm-benchmark-auto.yml \
  -e "metrics_collection_interval=5"
```

### External Endpoint Metrics Collection

When testing external vLLM endpoints (cloud, K8s, production):

**Automatic Detection:**
1. Playbook checks if `${VLLM_ENDPOINT_URL}/metrics` is accessible
2. If YES (HTTP 200): Server metrics collection enabled
3. If NO (HTTP 404/403/timeout): Server metrics collection skipped

**Example - Metrics Available:**
```bash
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-endpoint:8000

# Test endpoint
curl http://your-endpoint:8000/metrics
# → Returns Prometheus metrics (vllm:*, etc.)

# Run test (cores not needed - external endpoint manages its own CPUs)
ansible-playbook llm-benchmark-concurrent-load.yml \
  -e "base_workload=chat"

# Result: vllm-metrics.json created ✅
```

**Example - Metrics Not Available:**
```bash
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://production-lb.company.com:8000

# Test endpoint
curl http://production-lb.company.com:8000/metrics
# → 403 Forbidden (metrics not publicly exposed)

# Run test (cores not needed - external endpoint manages its own CPUs)
ansible-playbook llm-benchmark-concurrent-load.yml \
  -e "base_workload=chat"

# Result: Only benchmarks.json created (client metrics) ⚠️
```

**What You Get:**

| Endpoint Type | Client Metrics | Server Metrics | System Metrics |
|---------------|----------------|----------------|----------------|
| Managed (DUT container) | ✅ Always | ✅ Always | ✅ Always |
| External + `/metrics` public | ✅ Always | ✅ Auto-collected | ❌ Not applicable |
| External + `/metrics` private | ✅ Always | ❌ Skipped | ❌ Not applicable |

**Why `/metrics` might not be available:**
- Security policies (production endpoints)
- Load balancer configuration (metrics endpoint not forwarded)
- Firewall rules (port blocked)
- Authentication required (bearer token not configured)

**Note:** Client metrics (GuideLLM) are always sufficient for performance evaluation. Server metrics provide additional debugging insight but are not required.

## 3. System Metrics

### System Metrics: What is Collected

Infrastructure-level metrics:

- **CPU Info**: Model, cores, NUMA topology
- **Memory**: Total, used, free
- **Container Stats**: CPU%, Memory, I/O

### System Metrics: Collection Method

Automatic - `results_collector` role runs after benchmark.

### System Metrics: Output File

`system-metrics.log`

### Example Content

```
=== CPU Info ===
Architecture:         x86_64
CPU(s):              32
Model name:          Intel(R) Xeon(R) 6975P-C
Threads per core:    2
Cores per socket:    16
NUMA node(s):        1

=== Memory Usage ===
              total        used        free      shared  buff/cache   available
Mem:          125Gi        23Gi        89Gi       1.2Gi        13Gi       100Gi

=== Container Stats ===
CONTAINER ID  NAME         CPU %   MEM USAGE / LIMIT    MEM %   NET IO      BLOCK IO
1f8fbcd2e8f0  vllm-server  524%    12.3GiB / 125GiB    9.84%   45.2MB / 0B  0B / 0B
```

## Two Independent Systems

### System 1: Metrics Collection & Analysis (Always Active)

```
vLLM Server :8000/metrics
         │
         ▼
   Direct Collector (Python)
         │
         ▼
   vllm-metrics.json  ←───┐
         │                 │
         ▼                 │
   Streamlit Dashboard ───┘
   (Reads JSON files)
```

**No Grafana/Prometheus needed!**

### System 2: Real-Time Monitoring (Optional)

```
vLLM Server :8000/metrics
         │
         ▼ (via SSH tunnel)
   Prometheus (TSDB)
         │
         ▼
   Grafana Dashboards
   (Live visualization)
```

**Completely separate - only for watching tests in real-time!**

## Optional: Real-Time Monitoring with Grafana

While metrics are automatically collected (System 1), you can **optionally** run Grafana (System 2) for live visualization during tests.

### Setup

```bash
# 1. Start Grafana stack
cd automation/test-execution/ansible
ansible-playbook start-grafana.yml

# 2. Open Grafana
open <http://localhost:3000>
# Username: admin
# Password: admin

# 3. Run benchmark (metrics visible in real-time)
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"
```

### Architecture

```
┌──────────────────────────────┐
│ DUT (vLLM Server)            │
│  http://DUT:8000/metrics     │
└────────────┬─────────────────┘
             │
             ├─────────────────────────────┐
             │                             │
             ▼                             ▼
┌────────────────────────┐    ┌────────────────────────┐
│ Direct Collector       │    │ SSH Tunnel             │
│ (Always Active)        │    │ (Optional for Grafana) │
│                        │    │                        │
│ Scrapes /metrics       │    │ Forwards :8000         │
│ Saves to JSON          │    │ to localhost:8000      │
└────────────────────────┘    └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │ Prometheus             │
                              │ Scrapes localhost:8000 │
                              │ Stores in TSDB         │
                              └───────────┬────────────┘
                                          │
                                          ▼
                              ┌────────────────────────┐
                              │ Grafana Dashboards     │
                              │ Real-time viz          │
                              └────────────────────────┘
```

**Key Points:**
- Direct collector and Prometheus both scrape the same `/metrics` endpoint (read-only, no conflict)
- Grafana is purely for live monitoring - not required for metrics collection
- After test completes, both paths produce the same data
- Use whichever visualization tool fits your workflow

### When to Use Grafana

✅ **Use Grafana when:**
- Running long tests (>5 minutes) and want to monitor progress
- Debugging performance issues in real-time
- Need to verify server is handling load correctly
- Team collaboration - share dashboard URL for live view

❌ **Skip Grafana when:**
- Running quick tests (<2 minutes)
- Only care about final results
- Don't want to manage extra services
- Post-test analysis is sufficient

## Analysis & Visualization

### Streamlit Dashboard (Post-Test Analysis)

> **Note:** Streamlit reads JSON files directly. **No Grafana/Prometheus required.**

**Location:** `automation/test-execution/dashboard-examples/vllm_dashboard/`

**Launch:**
```bash
cd automation/test-execution/dashboard-examples
./setup.sh
cd vllm_dashboard
./launch-dashboard.sh
```

**Access:** <http://localhost:8501>

**What it reads:**
- `benchmarks.json` (GuideLLM results - always created)
- `vllm-metrics.json` (vLLM server metrics - automatically collected)
- No database, no Prometheus, no Grafana needed!

**Features:**
- 📊 Client Metrics - GuideLLM analysis (multi-percentile overlay for throughput, latency, success rate)
- 🖥️ Server Metrics - vLLM internals (time-series for queue, cache, tokens)
- 📈 Platform Comparison - Side-by-side performance with % differences
- 💾 CSV Export - For external analysis
- 🔄 Correlation - Switch between dashboards to correlate client & server behavior

### Grafana Dashboards (Real-Time)

**Location:** <http://localhost:3000> (when running)

**Dashboards:**
- **vLLM Performance Statistics** - Queue depth, cache, token rates
- **vLLM Query Statistics** - Request processing, latencies

**See:** [Grafana README](../automation/test-execution/grafana/README.md)

## Metrics Storage

### Directory Structure

```
results/llm/
└── meta-llama__Llama-3.2-1B-Instruct/
    └── chat-20260331-135911/
        └── 16cores-numa0-tp1/
            ├── benchmarks.json         # GuideLLM results
            ├── vllm-metrics.json       # vLLM server metrics
            ├── system-metrics.log      # System resources
            ├── test-metadata.json      # Test configuration
            └── vllm-server.log         # Server logs
```

### File Sizes

Typical file sizes for a 10-minute benchmark:

- `benchmarks.json`: 50-200 KB (depends on rate sweep points)
- `vllm-metrics.json`: 500 KB - 2 MB (60 samples × ~30 metrics)
- `system-metrics.log`: 5-10 KB
- `test-metadata.json`: 1-2 KB
- `vllm-server.log`: 1-10 MB (depends on log level)

## Troubleshooting

### vllm-metrics.json not created

**Check metrics collector logs:**
```bash
tail -f results/llm/*/metrics-collector.log
```

**Common issues:**
1. **Port 8000 blocked** - Check firewall/security groups
2. **vLLM server not started** - Verify server is running
3. **Wrong hostname** - Check `bench_config.vllm_host` in inventory

**Test manually:**
```bash
curl http://$DUT_HOSTNAME:8000/metrics
```

### Empty metrics file

**Issue:** File created but no samples

**Fix:**
- Collector duration too short - increase `metrics_collection_duration`
- vLLM server not exposing metrics - check vLLM version supports `/metrics`

### Grafana shows no data

**Issue:** Grafana dashboards empty

**Fix:**
1. Check SSH tunnel: `ps aux | grep "ssh.*8000:localhost:8000"`
2. Check Prometheus targets: <http://localhost:9090/targets>
3. Verify vLLM accessible: `curl http://localhost:8000/metrics`

**Note:** Direct collection (vllm-metrics.json) works independently of Grafana

## Best Practices

### For Production Benchmarking

1. ✅ **Always collect all metrics** (default behavior)
2. ✅ **Use meaningful test IDs** - include date/config in test_run_id
3. ✅ **Save test metadata** - captures full configuration
4. ✅ **Archive results** - back up results directory regularly

### For Development/Debugging

1. ✅ **Use Grafana for long tests** - live monitoring helps debug issues
2. ✅ **Check system-metrics.log** - verify resource availability
3. ✅ **Compare vllm-metrics.json across runs** - identify regressions
4. ❌ **Don't delete metrics files** - small size, high value for analysis

### For Performance Analysis

1. ✅ **Use Streamlit dashboard** - comprehensive post-test analysis
2. ✅ **Compare multiple test runs** - identify optimal configurations
3. ✅ **Correlate client & server metrics** - root cause bottlenecks
4. ✅ **Export to CSV** - for detailed statistical analysis

## See Also

- [Dashboard Examples README](../automation/test-execution/dashboard-examples/README.md)
- [Grafana Monitoring Guide](../automation/test-execution/grafana/README.md)
- [Testing Methodology](methodology/overview.md)
- [Getting Started Guide](getting-started.md)
