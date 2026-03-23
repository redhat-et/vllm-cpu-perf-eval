# vLLM CPU Performance Dashboard

Interactive Streamlit multipage dashboard for analyzing vLLM CPU benchmark results.

## 🎯 Quick Start

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

## 📊 Dashboard Overview

**One URL, Multiple Views**: All analysis tools accessible from `http://localhost:8501`

Navigate between views using the **sidebar**:

- 🏠 **Home** - Overview, quick start, system status
- 📊 **Client Metrics** - GuideLLM performance analysis
- 🖥️ **Server Metrics** - vLLM server-side metrics
- 🔄 **Unified View** - Combined client + server correlation

## ✨ Features

### All Views Include
- 🔍 Platform filtering
- 📦 Model filtering
- 📋 Workload filtering
- ⚙️ Core count filtering
- 🏷️ vLLM version filtering

### 📊 Client Metrics (GuideLLM)
**Data Source:** `benchmarks.json`

**Metrics:**
- Throughput (tokens/sec)
- TTFT, ITL, E2E latency (P50, P95, P99)
- Success rates
- Efficiency (tokens/sec/core)

**Features:**
- Configurable X-axis (request rate or concurrency)
- Platform comparison with % differences
- CSV export for external analysis
- Peak performance summary

**Best For:**
- Post-test performance analysis
- Platform/version comparison
- Identifying optimal load points

---

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

**Note:** Requires Prometheus metrics collection during tests. See [VLLM_METRICS_INTEGRATION.md](VLLM_METRICS_INTEGRATION.md)

---

### 🔄 Unified View
**Data Source:** Combined GuideLLM + vLLM metrics

**Analysis:**
- Client-server correlation
- Side-by-side performance comparison
- Peak performance metrics
- Bottleneck identification

**Best For:**
- Root cause analysis
- Performance validation
- Understanding end-to-end behavior

---

## 🚀 Usage

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

## 📂 Data Structure

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

Configurable in sidebar of each view.

## 🔧 Setup

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

## 🔗 Related Tools

### Grafana (Live Monitoring)
**Location:** `../grafana/`
**URL:** <http://localhost:3000>
**Type:** Real-time monitoring DURING tests
**Docs:** [../grafana/GRAFANA_LIVE_METRICS.md](../grafana/GRAFANA_LIVE_METRICS.md)

### When to Use What

| Tool | When | Data Source | Use Case |
|------|------|-------------|----------|
| **Grafana** | DURING test | Live /metrics endpoint | Monitor test progress in real-time |
| **Streamlit Dashboard** | AFTER test | benchmarks.json + vllm-metrics.json | Analyze results, compare configs |

## 💡 Tips

### Enabling Server Metrics Collection

Server-side metrics are automatically collected if:
1. Grafana/Prometheus is running (`ansible-playbook start-grafana.yml`)
2. SSH tunnel to vLLM server is active
3. Prometheus can scrape vLLM `/metrics` endpoint

**Verify:**
```bash
# Check for vllm-metrics.json in results
ls results/llm/*/*/*/vllm-metrics.json

# Check Prometheus is scraping
open http://localhost:9090/targets
```

See [VLLM_METRICS_INTEGRATION.md](VLLM_METRICS_INTEGRATION.md) for details.

### Navigating the Dashboard

- **Sidebar navigation** - Always visible, click any view to switch
- **Home button** - Click "Home" in sidebar to return to landing page
- **Filters persist** - Filter settings are maintained when switching views (within same session)
- **Refresh data** - Reload the page to pick up new test results

### Comparing Multiple Tests

1. Run tests with different configurations
2. Each test gets unique `test_run_id`
3. Use filters to select specific tests
4. Switch to comparison mode (available in Client and Server views)

## 🐛 Troubleshooting

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

```bash
# Verify results directory exists
ls -la ../../../results/llm/

# Check path in dashboard sidebar
# Default: ../../../../../results/llm (relative to pages/)
# Adjust if results are elsewhere

# Look for benchmarks.json files
find ../../../results/llm -name "benchmarks.json"
```

### Server metrics not found

```bash
# Check if vllm-metrics.json exists
find ../../../results/llm -name "vllm-metrics.json"

# If missing, check:
# 1. Was Grafana running during test?
curl http://localhost:9090/-/healthy

# 2. Was SSH tunnel active?
ps aux | grep "ssh.*8000:localhost:8000"

# 3. Did Prometheus scrape vLLM?
open http://localhost:9090/targets
```

See [VLLM_METRICS_INTEGRATION.md](VLLM_METRICS_INTEGRATION.md) for setup.

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

## 📚 Documentation

- **Dashboard Guide:** [vllm_dashboard/README.md](vllm_dashboard/README.md)
- **Server Metrics Integration:** [VLLM_METRICS_INTEGRATION.md](VLLM_METRICS_INTEGRATION.md)
- **Grafana Live Metrics:** [../grafana/GRAFANA_LIVE_METRICS.md](../grafana/GRAFANA_LIVE_METRICS.md)

## 🔄 Updates

**Latest Changes:**
- ✅ Created multipage Streamlit app (single URL, sidebar navigation)
- ✅ Added vLLM version filter to all dashboards
- ✅ Automatic metadata capture (platform, backend, vLLM version)
- ✅ Prometheus-based server metrics export (replaces separate collector)
- ✅ Unified dashboard combining client + server metrics
- ✅ Removed old separate dashboard scripts

## 📞 Architecture

### Multipage App Structure

```
vllm_dashboard/
├── Home.py                          # Main entry point
├── pages/
│   ├── 1_📊_Client_Metrics.py      # GuideLLM analysis
│   ├── 2_🖥️_Server_Metrics.py      # vLLM server metrics
│   └── 3_🔄_Unified_View.py        # Combined view
├── launch-dashboard.sh              # Start script
├── stop-dashboard.sh                # Stop script
└── README.md                        # Dashboard-specific docs
```

### Data Flow

```
Benchmark Run
     ↓
GuideLLM → benchmarks.json (client metrics)
     ↓
vLLM Server → Prometheus → vllm-metrics.json (server metrics)
     ↓
Streamlit Dashboard → Analysis + Visualization
```

## 📄 License

See main project LICENSE file.
