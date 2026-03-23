# Grafana Monitoring for vLLM CPU Performance Testing

Real-time visualization and historical analysis of GuideLLM benchmark results using Grafana and Prometheus.

## Two Types of Metrics

📊 **Batch Metrics (Post-Test)** - GuideLLM results published after benchmark completes
- ✅ Always available via Pushgateway
- ✅ No additional setup required
- 📈 Shows aggregate performance data from completed test runs

🔴 **Live Metrics (During Test)** - Real-time vLLM server metrics
- ⚠️ **Requires SSH tunnel** to remote vLLM server
- 📡 Shows queue depth, cache usage, token rates in real-time
- 📖 See [GRAFANA_LIVE_METRICS.md](GRAFANA_LIVE_METRICS.md) for setup

## Overview

This directory contains everything needed to visualize vLLM CPU performance test results:

- **Prometheus** - Time-series database for storing all metrics
- **Prometheus Pushgateway** - Receives batch GuideLLM results from Ansible
- **Grafana** - Visualization dashboards for analysis
- **Pre-built Dashboards** - Ready-to-use visualizations for live and batch metrics

## Quick Start

See **[QUICKSTART.md](QUICKSTART.md)** for complete setup instructions.

### 1. Start the Monitoring Stack (on your local machine)

```bash
cd automation/test-execution/grafana

# Start Prometheus, Pushgateway, and Grafana
docker-compose up -d
# OR with Podman
podman compose up -d

# Verify services are running
docker-compose ps
```

### 2. Set Up SSH Tunnel for Live Metrics

**⚠️ IMPORTANT:** To see **real-time metrics** in Grafana during your benchmarks, you must create an SSH tunnel to the vLLM server.

See **[GRAFANA_LIVE_METRICS.md](GRAFANA_LIVE_METRICS.md)** for complete documentation.

**Quick Setup:**

```bash
# Configure your environment
export DUT_HOSTNAME=your-vllm-server-hostname
export ANSIBLE_SSH_KEY=/path/to/your/ssh/key.pem

# Manual tunnel (recommended for single tests)
ssh -L 8000:localhost:8000 ec2-user@$DUT_HOSTNAME -N -f -i $ANSIBLE_SSH_KEY

# OR use automated script (for multiple tests)
cd scripts
./setup-tunnels.sh setup
```

**Verify tunnel is working:**
```bash
# Check tunnel is active
ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep

# Test metrics endpoint
curl http://localhost:8000/metrics | head -20

# Check Prometheus is scraping
open http://localhost:9090/targets
# vllm-live should show as UP
```

### 3. Access Grafana

Open your browser to: **<http://localhost:3000>**

- **Username:** `admin`
- **Password:** `admin`

### 4. Run Benchmarks with Publishing

```bash
cd ../ansible

ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "publish_to_prometheus=true"
```

## Architecture

```
┌──────────────────────────────────────────┐
│ DUT (EC2)                                │
│  - vLLM server with metrics enabled      │
│  - Exposes /metrics on port 8000         │
└────────────┬─────────────────────────────┘
             │ SSH tunnel (optional, for live metrics)
             │
┌────────────▼─────────────────────────────┐
│ LOADGEN (EC2)                            │
│  - Runs GuideLLM benchmarks              │
│  - Collects results                      │
└────────────┬─────────────────────────────┘
             │ Ansible publishes results
             │
┌────────────▼─────────────────────────────┐
│ YOUR LAPTOP (Ansible Controller)         │
│  ┌────────────────────────────────────┐  │
│  │ Prometheus Pushgateway :9091       │  │
│  │  ← Receives GuideLLM results       │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ Prometheus :9090                   │  │
│  │  - Scrapes Pushgateway             │  │
│  │  - Scrapes vLLM live (via tunnel)  │  │
│  │  - Stores all metrics              │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ Grafana :3000                      │  │
│  │  - Dashboards                      │  │
│  │  - Always accessible               │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Available Dashboards

### 1. vLLM Live Metrics
**File:** `dashboards/vllm-live-metrics.json`

Real-time monitoring of vLLM inference server:
- Request latencies (TTFT, ITL, E2E) - P50/P90/P95/P99
- Token throughput (prompt & generation)
- Queue metrics (running/waiting requests)
- CPU KV cache usage
- Request length distributions

**Use during:** Active benchmarks to monitor server health

### 2. vLLM vs GuideLLM Comparison
**File:** `dashboards/vllm-guidellm-comparison.json`

Combined dashboard showing:
- **Live metrics** (top section) - Real-time vLLM performance
- **Batch results** (middle) - GuideLLM load curves
- **Comparison** (bottom) - Live vs batch overlay
- **Summary stats** - Max throughput, best latency, success rate

**Use for:** Validating results, comparing live vs batch data

### 3. vLLM Load Sweep Analysis
**File:** `dashboards/vllm-load-sweep-analysis.json`

GuideLLM benchmark analysis:
- Throughput vs load curves
- Latency vs load curves (TTFT, ITL, E2E)
- Platform comparisons (AMD vs Intel)
- Performance summary tables

**Use for:** Platform comparisons, performance analysis

## Data Model

### Prometheus Metrics

**vLLM Live Metrics** (from running server):
```
vllm_time_to_first_token_seconds_bucket{...}
vllm_time_per_output_token_seconds_bucket{...}
vllm_request_duration_seconds_bucket{...}
vllm_generation_tokens_total{...}
vllm_prompt_tokens_total{...}
vllm_request_waiting{...}
vllm_request_running{...}
vllm:kv_cache_usage_perc{...}
```

**GuideLLM Batch Results** (from benchmarks):
```
guidellm_throughput_tokens_per_sec_mean{platform,model,workload,cores,...}
guidellm_ttft_ms_p95{...}
guidellm_itl_ms_p95{...}
guidellm_e2e_latency_ms_p95{...}
guidellm_success_rate_percent{...}
```

### Labels

All GuideLLM metrics include:
- `platform` - CPU/platform identifier
- `model` - Model name
- `workload` - Workload type
- `cores` - Number of cores
- `tensor_parallel` - TP degree
- `numa_node` - NUMA node
- `backend` - Backend type
- `test_run_id` - Unique test ID
- `vllm_version` - vLLM version
- `request_rate` - Request rate (req/s)

## Directory Structure

```
automation/test-execution/grafana/
├── docker-compose.yml                  # Prometheus stack
├── README.md                           # This file
├── QUICKSTART.md                       # Step-by-step setup
├── PROMETHEUS.md                       # Detailed Prometheus docs
├── METRICS_COMPARISON.md               # vLLM vs GuideLLM metrics
│
├── prometheus/
│   └── prometheus.yml                  # Prometheus config
│
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yaml             # Prometheus datasource
│   └── dashboards/
│       └── vllm-dashboards.yaml        # Dashboard provider
│
├── dashboards/                         # Pre-built dashboards
│   ├── vllm-live-metrics.json
│   ├── vllm-guidellm-comparison.json
│   └── vllm-load-sweep-analysis.json
│
└── scripts/
    └── setup-tunnels.sh                # SSH tunnel automation
```

## Configuration

### Prometheus

Located at: `prometheus/prometheus.yml`

**Key settings:**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  # GuideLLM batch results
  - job_name: 'pushgateway'
    static_configs:
      - targets: ['pushgateway:9091']

  # vLLM live metrics (via SSH tunnel)
  - job_name: 'vllm-live'
    static_configs:
      - targets: ['host.containers.internal:8000']
```

### Ansible Publishing

The `metrics_publisher` role automatically publishes results when enabled:

```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "publish_to_prometheus=true"
```

See [metrics_publisher role README](../ansible/roles/metrics_publisher/README.md) for details.

## Common Operations

### Start Stack

```bash
cd automation/test-execution/grafana
docker-compose up -d

# Check status
docker-compose ps
```

### Stop Stack

```bash
docker-compose down       # Stops, keeps data
docker-compose down -v    # Stops, removes all data
```

### View Logs

```bash
docker-compose logs -f prometheus
docker-compose logs -f pushgateway
docker-compose logs -f grafana
```

### Check Prometheus Targets

```bash
# Web UI
open http://localhost:9090/targets

# API
curl http://localhost:9090/api/v1/targets | jq
```

### Check Pushgateway Metrics

```bash
# Web UI
open http://localhost:9091

# Metrics endpoint
curl http://localhost:9091/metrics | grep guidellm
```

## Troubleshooting

### No Live vLLM Metrics

**Check tunnel is active:**
```bash
./scripts/setup-tunnels.sh status
```

**Verify vLLM is exposing metrics:**
```bash
ssh user@dut-host "curl http://localhost:8000/metrics"
```

**Check Prometheus is scraping:**
```bash
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="vllm-live")'
```

### No GuideLLM Results

**Verify Pushgateway received data:**
```bash
curl http://localhost:9091/metrics | grep guidellm
```

**Check Prometheus scraped it:**
```bash
curl 'http://localhost:9090/api/v1/query?query=guidellm_benchmark_info'
```

**Check Ansible publishing:**
```bash
# Review playbook output for publishing step
# Should show: "Successfully published X benchmark metrics"
```

### Grafana Dashboard Shows "No data"

1. **Check time range** - Top-right picker, try "Last 30 days"
2. **Check datasource** - Settings → Data Sources → Test
3. **Check queries** - Dashboard → Panel → Edit → Query tab
4. **Check Prometheus** - Query Explorer: `http://localhost:9090/graph`

## Example Queries

### vLLM Live Metrics

```promql
# P95 TTFT (in milliseconds)
histogram_quantile(0.95, rate(vllm_time_to_first_token_seconds_bucket[1m])) * 1000

# Current throughput (tokens/sec)
rate(vllm_generation_tokens_total[1m])

# Queue depth
vllm_request_waiting
```

### GuideLLM Results

```promql
# Throughput across platforms
guidellm_throughput_tokens_per_sec_mean{cores="16"}

# TTFT comparison
guidellm_ttft_ms_p95{model=~".*Llama.*",workload="chat"}

# Success rate
guidellm_success_rate_percent
```

### Platform Comparison

```promql
# Max throughput by platform
max by(platform) (guidellm_throughput_tokens_per_sec_max{cores="16"})

# Best latency by platform
min by(platform) (guidellm_ttft_ms_p95{workload="chat"})
```

## Port Reference

| Service | Port | Purpose |
|---------|------|---------|
| vLLM | 8000 | API + Metrics |
| Prometheus | 9090 | Web UI + API |
| Pushgateway | 9091 | Metrics receiver |
| Grafana | 3000 | Dashboards |

## Resources

- [QUICKSTART.md](QUICKSTART.md) - Complete setup guide
- [METRICS_COMPARISON.md](METRICS_COMPARISON.md) - vLLM vs GuideLLM metrics
- [PROMETHEUS.md](PROMETHEUS.md) - Detailed Prometheus configuration
- [metrics_publisher role](../ansible/roles/metrics_publisher/README.md) - Publishing details
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

## License

Same as parent project
