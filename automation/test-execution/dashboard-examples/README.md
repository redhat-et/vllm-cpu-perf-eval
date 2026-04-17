# vLLM CPU Performance Dashboard

Interactive Streamlit multipage dashboard for analyzing vLLM CPU benchmark results with client and server-side metrics.

## Quick Start

```bash
# Setup (one-time)
./setup.sh

# Launch dashboard
cd vllm_dashboard
./launch-dashboard.sh

# Opens at http://localhost:8501

# To stop
./stop-dashboard.sh
```

## Overview

This Streamlit dashboard provides comprehensive analysis of vLLM benchmark results, combining:

**Client-Side Metrics (GuideLLM)**
- End-user experience metrics
- Latencies, throughput, success rates
- Source: `benchmarks.json`

**Server-Side Metrics (vLLM)**
- Internal server state
- Queue depth, cache usage, token generation rates
- Source: `vllm-metrics.json` (collected via Prometheus)

**Architecture:**
```
Benchmark Run
     ↓
GuideLLM → benchmarks.json (client metrics)
     ↓
vLLM Server → Prometheus → vllm-metrics.json (server metrics)
     ↓
Streamlit Dashboard → Analysis + Visualization
```

## Dashboard Views

**One URL, Multiple Views:** All analysis accessible from `http://localhost:8501`

Navigate between views using the sidebar:

### 🏠 Home
Overview, quick start, system status

### 📊 Client Metrics (GuideLLM)

**Data Source:** `benchmarks.json`

**Metric Families:**
- Throughput (tokens/sec) - mean, P50, P95, P99
- TTFT (ms) - Time To First Token across percentiles
- ITL (ms) - Inter-Token Latency across percentiles
- E2E Latency (s) - End-to-End request latency
- Success Rate (%)
- Efficiency (tokens/sec/core) - managed mode only

**Features:**
- **Multi-percentile overlay**: Select metric family (e.g., TTFT) and view Mean, P50, P95, P99 on the same chart
- **Visual differentiation**: Each percentile uses a distinct line style (solid, dashed, dotted, dash-dot)
- **Configurable X-axis**: Request rate or concurrency
- **Platform comparison**: Side-by-side with % differences for selected percentiles
- **CSV export**: Download filtered data
- **Peak performance summary**: Shows best/peak values for all selected percentiles

**Understanding Percentiles:**

Percentile definition: Pxx = the value below which xx% of data points fall

*Latency percentiles (lower is better)*:
- **P99 = 99% of requests completed within this latency** (worst-case tail)
- High P99 latency = bad (slow tail)
- Example: TTFT P99 = 200ms means 99% of requests got first token within 200ms

*Throughput percentiles (higher is better)*:
- **P99 = 99% of requests achieved this throughput or lower** (upper bound)
- High P99 throughput = good (fast requests)
- Example: Throughput P99 = 100 tok/s means only 1% of requests exceeded 100 tok/s
- **P99 > Mean**: Some fast requests pulled up the average
- **Narrow spread (P99 ≈ P50)**: Consistent per-request throughput

**Best For:**
- Post-test performance analysis
- Understanding tail latency behavior (P99 vs P95 vs Mean)
- Platform/version comparison across multiple percentiles
- Identifying optimal load points and latency degradation

### 🖥️ Server Metrics (vLLM)

**Data Source:** `vllm-metrics.json`

**Metrics:**
- Request queue depth (running/waiting)
- CPU cache utilization
- Token generation rates
- Request processing patterns

**Features:**
- Time-series visualization
- Single test or comparison mode
- Summary statistics
- Raw data inspection

**Best For:**
- Understanding server behavior
- Identifying bottlenecks (queue buildup, cache thrashing)
- Debugging performance issues

## Analysis Workflow

**Recommended approach for performance analysis:**

1. **Start with Client Metrics** - Understand end-user experience
   - Analyze throughput and latency trends
   - Identify optimal load points using multi-percentile overlay
   - Compare P95 vs P99 to spot tail latency degradation

2. **Switch to Server Metrics** - Investigate server behavior
   - Look for queue buildup patterns
   - Check cache usage and efficiency
   - Identify resource bottlenecks

3. **Correlate findings** - Root cause analysis
   - High client latency + server queue buildup = Insufficient capacity
   - Good throughput + high cache usage = Optimal utilization
   - Client issues + empty server queue = Network/routing problem

## Usage

### 1. Run Benchmarks

```bash
# Single test
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"

# Core sweep
ansible-playbook llm-core-sweep-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores_list=[8,16,32,64]"
```

Results are saved to: `results/llm/`

### 2. Launch Dashboard

```bash
cd vllm_dashboard
./launch-dashboard.sh
```

Dashboard opens at: `http://localhost:8501`

### 3. Navigate and Analyze

1. **Home** - Overview and quick start
2. **Select a view** from sidebar
3. **Apply filters** to focus on specific tests
4. **Analyze performance** using charts and metrics

### 4. Stop Dashboard

```bash
# From vllm_dashboard directory
./stop-dashboard.sh

# Or kill all streamlit processes
pkill -f "streamlit.*8501"
```

## Server-Side Metrics Collection

Server-side vLLM metrics are **automatically collected** during benchmarks by directly scraping the vLLM `/metrics` endpoint. This provides comprehensive performance analysis combining client experience with server internals.

**What you get:**
- Client-side (GuideLLM): Latencies, throughput, success rates
- Server-side (vLLM): Queue depth, cache usage, token generation rates

**Benefits:**
- ✅ **No Grafana/Prometheus required** - metrics collected independently
- ✅ Automatic collection during benchmark execution
- ✅ No additional configuration needed
- ✅ Works out-of-the-box with all benchmark playbooks

### How It Works

The benchmark playbook automatically collects vLLM metrics during each test:

1. **Before benchmark starts**: Metrics collector launches in background
2. **During benchmark**: Collector scrapes vLLM `/metrics` endpoint every 10s
3. **After benchmark completes**: Collector stops and saves data
4. **Result**: `vllm-metrics.json` saved alongside GuideLLM results

**No configuration needed** - it's already integrated into `llm-benchmark-auto.yml`.

### Grafana Integration (Optional)

While metrics are collected independently, you can **optionally** run Grafana for real-time visualization during tests:

```bash
# Optional: Start Grafana for live monitoring
ansible-playbook start-grafana.yml
```

**Key point:** Grafana is only for real-time dashboards during test execution. Metrics collection works with or without it.

## Output Files

```
results/llm/model-name/test-date/config/
├── benchmarks.json           # GuideLLM results (client-side)
├── test-metadata.json        # Test configuration
├── vllm-metrics.json         # vLLM server metrics (from Prometheus)
└── vllm-server.log           # Server logs
```

### vLLM Metrics Captured

The exported `vllm-metrics.json` contains time-series data:

```json
{
  "collection_info": {
    "vllm_url": "http://localhost:8000",
    "interval_seconds": 10,
    "start_time": "2026-03-22T10:00:00",
    "end_time": "2026-03-22T10:05:00",
    "total_samples": 60
  },
  "samples": [
    {
      "timestamp": "2026-03-22T10:00:10",
      "elapsed_seconds": 10.0,
      "metrics": {
        "vllm:num_requests_running": [...],
        "vllm:num_requests_waiting": [...],
        "vllm:cpu_cache_usage_perc": [...],
        "vllm:prompt_tokens_total": [...],
        "vllm:generation_tokens_total": [...],
        "vllm:time_to_first_token_seconds": [...],
        "vllm:time_per_output_token_seconds": [...],
        ...
      }
    }
  ]
}
```

## Data Structure

```
results/llm/
└── meta-llama__Llama-3.2-1B-Instruct/
    └── chat-20260322-142026/
        └── 16cores-numa0-tp1/
            ├── benchmarks.json         ← GuideLLM (client-side)
            ├── vllm-metrics.json       ← vLLM (server-side) [optional]
            ├── test-metadata.json      ← Test configuration
            └── vllm-server.log         ← Server logs
```

**Default path:** `../../../../../results/llm` (relative to dashboard pages)

## Configuration

### Results Directory

The dashboard allows you to configure a custom results directory path that **persists across sessions**.

#### How to Configure

1. **Via Sidebar** (recommended):
   - Open any dashboard page
   - Enter your results directory path in the sidebar "Results Directory" field
   - Click the **💾** (save) button next to the input field
   - Path is saved to `.dashboard_config.ini`
   - Survives dashboard stop/restart cycles

2. **Via Environment Variable**:
   ```bash
   export VLLM_DASHBOARD_RESULTS_DIR="/path/to/your/results/llm"
   ./launch-dashboard.sh
   ```
   Environment variable takes priority over saved config.

3. **Via Config File** (advanced):
   Edit `vllm_dashboard/.dashboard_config.ini`:
   ```ini
   [Paths]
   results_directory = /absolute/path/to/results/llm
   ```

#### Path Types Supported

- **Relative paths**: `../../../../results/llm` (default)
- **Absolute paths**: `/Users/username/benchmarks/results/llm`
- **Home directory**: `~/benchmarks/results/llm` (expands to full path)

**Note:** Configuration is stored in `vllm_dashboard/.dashboard_config.ini` and is **not** committed to git.

## Setup

### Quick Setup (Recommended)

```bash
./setup.sh
```

This creates a virtual environment and installs all dependencies.

### Manual Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Requirements

- Python 3.9+
- Streamlit
- Plotly
- Pandas
- Numpy

See [requirements.txt](requirements.txt) for full list.

## Features

### All Views Include
- 🔍 Platform filtering
- 📦 Model filtering
- 📋 Workload filtering
- ⚙️ Core count filtering
- 🏷️ vLLM version filtering

### Navigation Tips

- **Sidebar navigation** - Always visible, click any view to switch
- **Home button** - Click "Home" in sidebar to return to landing page
- **Filters persist** - Filter settings maintained when switching views
- **Refresh data** - Reload page to pick up new test results

### Comparing Multiple Tests

1. Run tests with different configurations
2. Each test gets unique `test_run_id`
3. Use filters to select specific tests
4. Switch to comparison mode (available in Client and Server views)

## Related Tools

### Grafana (Live Monitoring)

**Location:** `../grafana/`
**URL:** <http://localhost:3000>
**Type:** Real-time monitoring DURING tests
**Docs:** [../grafana/README.md](../grafana/README.md)

### When to Use What

| Tool | When | Data Source | Use Case |
|------|------|-------------|----------|
| **Grafana** | DURING test | Live /metrics endpoint | Monitor test progress in real-time |
| **Streamlit Dashboard** | AFTER test | benchmarks.json + vllm-metrics.json | Analyze results, compare configs |

## Troubleshooting

### Dashboard won't start

```bash
# Check logs
tail -f /tmp/streamlit-vllm-dashboard.log

# Verify virtual environment
cd vllm_dashboard
source ../venv/bin/activate
which python  # Should point to venv/bin/python

# Reinstall dependencies
cd ..
./setup.sh
```

### No data appears

**Solution 1: Check/Update Results Directory**

1. Open dashboard sidebar
2. Verify "Results Directory" path is correct
3. Update path if needed - it will persist across sessions
4. Refresh the page

**Solution 2: Use Absolute Path**

If relative paths aren't working, use an absolute path:
```bash
# In dashboard sidebar, enter:
/Users/your-username/path/to/vllm-cpu-perf-eval/results/llm
```

**Solution 3: Reset Configuration**

```bash
# Remove saved config and restart
rm vllm_dashboard/.dashboard_config.ini
./launch-dashboard.sh
```

**Verify Data Exists:**
```bash
# Check if results directory exists
ls -la results/llm/

# Look for benchmarks.json files
find results/llm -name "benchmarks.json"
```

### Server metrics not found

```bash
# Check if vllm-metrics.json exists
find ../../../results/llm -name "vllm-metrics.json"

# If missing, check:
# 1. Did the metrics collector run?
tail -f results/llm/*/metrics-collector.log

# 2. Can vLLM /metrics endpoint be reached?
curl http://$DUT_HOSTNAME:8000/metrics
```

**To fix for next test:**
1. Ensure vLLM server is accessible from your local machine
2. Check firewall/security group allows port 8000
3. Metrics collection is automatic - no setup needed!

**To skip metrics collection intentionally:**
```bash
ansible-playbook llm-benchmark-auto.yml -e "skip_metrics_collection=true"
```

### Navigation not working

- Refresh browser if sidebar doesn't show navigation
- Ensure you're running from `Home.py` (not individual pages)
- Check that you launched via `./launch-dashboard.sh`

### Port already in use

```bash
# Check what's using port 8501
lsof -i :8501

# Stop existing dashboard
cd vllm_dashboard
./stop-dashboard.sh

# Or kill manually
pkill -f "streamlit.*8501"
```

## Example Analysis Insights

**1. High P99 latency + Server queue waiting**
→ Insufficient capacity, add more cores

**2. Stable throughput + Cache hit rate dropping**
→ Working set too large for cache

**3. Client timeout errors + Server queue empty**
→ Network/routing issue, not server bottleneck

**4. ITL variance + Preemption spikes**
→ Memory pressure, reduce batch size

## Architecture

### Multipage App Structure

```
vllm_dashboard/
├── Home.py                          # Main entry point
├── pages/
│   ├── 1_📊_Client_Metrics.py      # GuideLLM analysis
│   └── 2_🖥️_Server_Metrics.py      # vLLM server metrics
├── launch-dashboard.sh              # Start script
├── stop-dashboard.sh                # Stop script
└── README.md                        # This file
```

## Documentation

- **Dashboard Guide:** [vllm_dashboard/README.md](vllm_dashboard/README.md)
- **Grafana Live Metrics:** [../grafana/README.md](../grafana/README.md)
- **Prometheus Exporter Role:** [../ansible/roles/prometheus_exporter/](../ansible/roles/prometheus_exporter/)

## License

See main project LICENSE file.
