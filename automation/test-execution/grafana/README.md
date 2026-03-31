# Grafana Monitoring for vLLM CPU Performance Testing

**Optional** real-time monitoring of vLLM server metrics during benchmark execution using Grafana and Prometheus.

## Overview

> **Note:** Grafana is **optional** for metrics collection. vLLM server metrics are automatically collected during benchmarks without requiring Grafana. This stack is only for **real-time visualization** during test execution.

This monitoring stack runs on your **local machine** (Ansible controller) to visualize **live vLLM server metrics** during performance tests on remote servers.

**🔴 Live Server Metrics (During Test)**
- 📡 Real-time queue depth, cache usage, token generation rates
- 📊 Request latencies (TTFT, ITL, E2E) with percentile breakdowns
- 🎯 Request processing patterns and scheduler state
- ⚠️ Requires SSH tunnel to remote vLLM server

**Stack Components:**
- **Prometheus** - Time-series database for metrics scraping
- **Grafana** - Real-time visualization dashboards
- **vLLM Official Dashboards** - Performance Statistics & Query Statistics dashboards from vLLM project

**For Metrics Collection & Analysis:**
- ✅ **vLLM server metrics** are automatically collected during all benchmarks (no Grafana needed)
- ✅ **Post-test analysis** via Streamlit Dashboard
- See [dashboard-examples](../dashboard-examples/README.md) for metrics visualization

## Architecture

```
┌──────────────────────────────┐
│ DUT (Remote Server)          │
│  - vLLM server :8000         │
│  - Exposes /metrics          │
└────────────┬─────────────────┘
             │ SSH tunnel (forwards :8000 → localhost:8000)
             │
┌────────────▼────────────────────────────────────┐
│         Ansible Controller (Local Machine)      │
│  ┌──────────────────────────────────────────┐   │
│  │ Prometheus :9090                         │   │
│  │  - Scrapes localhost:8000 via tunnel     │   │
│  │  - Stores vLLM metrics locally           │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │ Grafana :3000                            │   │
│  │  - Real-time vLLM metrics dashboards     │   │
│  │  - Monitor tests as they run             │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘

Note: Post-test benchmark analysis (GuideLLM results) is handled by
      Streamlit Dashboard - see ../dashboard-examples/README.md
```

**Benefits:**
- ✅ Real-time monitoring during test execution
- ✅ No cloud costs for monitoring infrastructure
- ✅ No exposed ports or router configuration (uses SSH tunnels)
- ✅ Access Grafana anytime at <http://localhost:3000>
- ✅ Separate tools for live monitoring (Grafana) vs post-test analysis (Streamlit)

## Quick Start

### 1. Start Monitoring Stack

```bash
cd automation/test-execution/grafana

# Start with Docker Compose
docker-compose up -d

# OR with Podman
podman compose up -d

# Verify services
docker-compose ps
```

**Expected output:**
```
NAME           STATUS    PORTS
prometheus     running   0.0.0.0:9090->9090/tcp
grafana        running   0.0.0.0:3000->3000/tcp
```

### 2. Access Grafana

Open browser to: **<http://localhost:3000>**

- **Username:** `admin`
- **Password:** `admin` (you'll be prompted to change on first login)

### 3. Run Benchmarks

With Grafana running and SSH tunnel active, run your benchmarks:

```bash
cd ../ansible

ansible-playbook llm-benchmark-auto.yml \
  -i inventory/hosts.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"
```

vLLM server metrics will appear in Grafana dashboards in real-time.

### 4. Stop Monitoring Stack

```bash
# Stop and keep data
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## SSH Tunnel Setup (Required)

To monitor **real-time vLLM metrics** during benchmarks, you must create an SSH tunnel from your local machine to the remote vLLM server. This forwards the vLLM metrics endpoint (port 8000) to localhost.

### Manual Tunnel Setup

```bash
# Set environment variables
export DUT_HOSTNAME=your-vllm-server.compute.amazonaws.com
export ANSIBLE_SSH_KEY=/path/to/your/ssh/key.pem

# Create tunnel (forwards remote :8000 to local :8000)
ssh -L 8000:localhost:8000 ec2-user@$DUT_HOSTNAME \
  -N -f -i $ANSIBLE_SSH_KEY \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3
```

### Automated Tunnel Setup

```bash
cd scripts

# Setup tunnel
./setup-tunnels.sh setup

# Check status
./setup-tunnels.sh status

# Teardown tunnel
./setup-tunnels.sh teardown
```

### Verify Tunnel

```bash
# Check tunnel process
ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep

# Test vLLM metrics endpoint
curl http://localhost:8000/metrics | head -20

# Verify Prometheus is scraping
open http://localhost:9090/targets
# Look for "vllm-live" target showing as UP
```

## Prometheus Configuration

### Configuration File

Location: `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 10s
  evaluation_interval: 10s
  external_labels:
    environment: 'local-dev'

scrape_configs:
  # vLLM server metrics (via SSH tunnel)
  - job_name: 'vllm-live'
    scrape_interval: 10s
    static_configs:
      - targets: ['host.containers.internal:8000']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'vllm_.*'
        action: keep
```

### Key Settings

- **Scrape interval:** 10s for real-time monitoring
- **Retention:** 30 days by default
- **Storage:** Local volume (persists between restarts)

### Customization

To change Prometheus settings, edit `prometheus/prometheus.yml` and restart:

```bash
docker-compose restart prometheus
```

## Available Dashboard

### vLLM Monitoring Dashboard

**File:** `dashboards/vllm-monitoring-v2.json`

Comprehensive real-time monitoring with 24 panels organized into sections:

**Executive Summary**
- Top-line summary with key metrics at a glance
- Success rate and system efficiency
- TTFT P99 and preemption rate tracking

**Latency & User Experience**
- E2E request latency with percentile breakdowns
- Inference stage breakdown (TTFT vs TPOT)
- Request queue time analysis

**Token Throughput & Workload**
- Token throughput (prompt & generation)
- Token I/O ratio tracking
- Prefix cache savings visualization
- Request length heatmaps

**Engine Internal & Cache**
- KV cache usage monitoring
- Prefix cache hit rate
- Scheduler state (running/waiting requests)

**System Health & Reliability**
- Python GC and memory tracking
- Finish reason distribution
- Throughput vs success correlation

**Use during:** Active benchmarks to monitor server health, identify bottlenecks, and validate performance in real-time

### For Post-Test Analysis

Client-side benchmark results (GuideLLM) are analyzed using the **Streamlit Dashboard**.
See [dashboard-examples](../dashboard-examples/README.md) for post-test metrics visualization.

## Metrics Reference

### vLLM Live Metrics

Collected in real-time from vLLM `/metrics` endpoint:

```promql
# Time to First Token (P95, in milliseconds)
histogram_quantile(0.95, rate(vllm_time_to_first_token_seconds_bucket[1m])) * 1000

# Inter-Token Latency (P95, in milliseconds)
histogram_quantile(0.95, rate(vllm_time_per_output_token_seconds_bucket[1m])) * 1000

# End-to-End Latency (P95, in milliseconds)
histogram_quantile(0.95, rate(vllm_request_duration_seconds_bucket[1m])) * 1000

# Generation throughput (tokens/sec)
rate(vllm_generation_tokens_total[1m])

# Prompt throughput (tokens/sec)
rate(vllm_prompt_tokens_total[1m])

# Queue depth
vllm_request_waiting
vllm_request_running

# Cache usage (%)
vllm:kv_cache_usage_perc
```

### Common Metric Labels

vLLM metrics typically include labels like:
- `model_name` - Model being served
- `finished_reason` - Request completion reason
- Various quantile labels for histogram metrics

## Troubleshooting

### Grafana shows "No data"

1. **Check time range** - Top-right picker, try "Last 5 minutes" or "Last 15 minutes"
2. **Check datasource** - Settings → Data Sources → Prometheus → Test
3. **Verify Prometheus** - Open <http://localhost:9090/graph>
4. **Verify SSH tunnel is active:**
   ```bash
   ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep
   ```
5. **Check vLLM server is running** on the remote DUT

### No live vLLM metrics

1. **Verify SSH tunnel is active:**
   ```bash
   ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep
   ```

2. **Test vLLM endpoint through tunnel:**
   ```bash
   curl http://localhost:8000/metrics | grep vllm
   ```

3. **Check Prometheus is scraping:**
   ```bash
   open http://localhost:9090/targets
   # vllm-live should show as UP
   ```

4. **Verify vLLM server is running:**
   - SSH to DUT and check vLLM process
   - Ensure vLLM was started with metrics enabled (default)

### Containers won't start

```bash
# Check logs
docker-compose logs prometheus
docker-compose logs grafana

# Check port conflicts
lsof -i :3000  # Grafana
lsof -i :9090  # Prometheus

# Full reset
docker-compose down -v
docker-compose up -d
```

## Port Reference

| Service | Port | Purpose |
|---------|------|---------|
| vLLM (remote) | 8000 | API + Metrics endpoint (accessed via SSH tunnel) |
| Prometheus | 9090 | Web UI + API |
| Grafana | 3000 | Dashboards |

## Directory Structure

```
grafana/
├── README.md                           # This file
├── docker-compose.yml                  # Container orchestration
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
├── dashboards/
│   └── vllm-monitoring-v2.json         # vLLM live metrics dashboard
│
└── scripts/
    └── setup-tunnels.sh                # SSH tunnel automation
```

## Integration with Ansible

The monitoring stack integrates automatically with Ansible playbooks:

### Start Grafana Before Tests

```bash
ansible-playbook start-grafana.yml
```

This playbook:
- Detects Docker/Podman automatically
- Starts all services
- Waits for health checks
- Optionally creates SSH tunnel if `DUT_HOSTNAME` is set

### Run Benchmarks

```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"
```

With Grafana running and SSH tunnel active:
- vLLM server metrics are scraped in real-time by Prometheus
- View live metrics in Grafana at <http://localhost:3000>
- Benchmark results (client-side) are saved to results directory as JSON
- Post-test analysis via Streamlit Dashboard

### Stop Grafana After Tests

```bash
# Stop and keep data
ansible-playbook stop-grafana.yml

# Stop and remove all data
ansible-playbook stop-grafana.yml -e "remove_volumes=true"
```

## Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [vLLM Metrics Documentation](https://docs.vllm.ai/en/latest/serving/metrics.html)
- [Streamlit Dashboard](../dashboard-examples/README.md) - Post-test benchmark analysis
