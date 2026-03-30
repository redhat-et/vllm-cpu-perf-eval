# vLLM CPU Performance Dashboard (Multipage App)

Comprehensive performance analysis dashboard for vLLM CPU benchmarks.

## Features

**Single URL Access**: All dashboards accessible from `http://localhost:8501`

**Four Views**:
- 🏠 **Home** - Overview, quick start, system status
- 📊 **Client Metrics** - GuideLLM performance analysis
- 🖥️ **Server Metrics** - vLLM server-side metrics
- 🔄 **Unified View** - Combined client + server correlation

**Navigation**: Use the sidebar to switch between views

**Filters**: Platform, Model, Workload, Core Count, vLLM Version

## Quick Start

```bash
# Launch dashboard
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh

# Open browser to http://localhost:8501

# Navigate using sidebar (←)
```

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

### 2. View Results

1. Open dashboard: `http://localhost:8501`
2. Select a view from sidebar
3. Apply filters as needed
4. Analyze performance

### 3. Navigate

- **Home** - Click "Home" in sidebar
- **Client Metrics** - Click "📊 Client Metrics" in sidebar
- **Server Metrics** - Click "🖥️ Server Metrics" in sidebar
- **Unified View** - Click "🔄 Unified View" in sidebar

## Dashboard Details

### 📊 Client Metrics

**Source**: GuideLLM benchmark results (`benchmarks.json`)

**Metrics**:
- Throughput (tokens/sec)
- TTFT, ITL, E2E latency (P50, P95, P99)
- Success rates
- Efficiency (tokens/sec/core)

**Features**:
- Configurable X-axis (request rate or concurrency)
- Platform comparison with % differences
- CSV export
- Peak performance summary

### 🖥️ Server Metrics

**Source**: vLLM Prometheus metrics (`vllm-metrics.json`)

**Metrics**:
- Queue depth (running/waiting)
- CPU cache usage
- Token generation rates
- Request patterns

**Features**:
- Time-series analysis
- Single test or comparison mode
- Summary statistics
- Raw data inspection

### 🔄 Unified View

**Source**: Combined GuideLLM + vLLM metrics

**Analysis**:
- Client-server correlation
- Side-by-side metrics
- Peak performance comparison
- Bottleneck identification

**Use For**:
- Root cause analysis
- Performance validation
- Troubleshooting

## Stopping

```bash
./stop-dashboard.sh

# Or kill directly
pkill -f "streamlit.*8501"
```

## Configuration

### Results Directory

Default: `../../../../../results/llm` (relative to pages directory)

Change in sidebar of any dashboard view.

### Filters

All views support:
- Platform
- Model
- Workload
- Core Count
- vLLM Version

Filters apply to the current view only.

## Troubleshooting

### Dashboard won't start

```bash
# Check logs
tail -f /tmp/streamlit-vllm-dashboard.log

# Ensure virtual environment exists
cd ../
./setup.sh
```

### No data showing

1. Verify results directory path
2. Check that benchmarks have been run
3. Look for `benchmarks.json` in results directory

### Navigation not working

- Sidebar should always show navigation links
- Refresh browser if sidebar doesn't appear
- Check that you're running from `Home.py`

## Architecture

```
vllm_dashboard/
├── Home.py                           # Main entry point (run this)
├── pages/
│   ├── 1_📊_Client_Metrics.py       # GuideLLM analysis
│   ├── 2_🖥️_Server_Metrics.py       # vLLM server metrics
│   └── 3_🔄_Unified_View.py         # Combined view
├── launch-dashboard.sh               # Start script
├── stop-dashboard.sh                 # Stop script
└── README.md                         # This file
```
