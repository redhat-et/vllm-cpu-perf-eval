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

**Platform-Specific Configurations:**
- **macOS**: Uses `docker-compose.macos.yml` (bridge networking with port mappings)
- **Linux**: Uses `docker-compose.yml` (host networking for direct access)
- **Ansible playbook**: Automatically detects OS and uses the correct configuration

**For Metrics Collection & Analysis:**
- ✅ **vLLM server metrics** are automatically collected during all benchmarks (no Grafana needed)
- ✅ **Post-test analysis** via Streamlit Dashboard
- See [dashboard-examples](../dashboard-examples/README.md) for metrics visualization

## Architecture

### Deployment Scenario 1: Co-located (Same Server)

When running everything on the same server (vLLM + Grafana/Prometheus):

```
┌──────────────────────────────────────────────────┐
│ DUT Server (e.g., nfvsdn-14)                     │
│                                                   │
│  ┌────────────────────────────────────────────┐  │
│  │ vLLM Server :8000                          │  │
│  │  - Exposes /metrics endpoint               │  │
│  └────────────────────────────────────────────┘  │
│                      ▲                            │
│                      │ localhost:8000             │
│  ┌───────────────────┴────────────────────────┐  │
│  │ Prometheus :9090/9091 (host network)      │  │
│  │  - Scrapes localhost:8000 directly        │  │
│  │  - Stores vLLM metrics                    │  │
│  └───────────────────┬────────────────────────┘  │
│                      │ localhost:9090             │
│  ┌───────────────────▼────────────────────────┐  │
│  │ Grafana :3000 (host network)              │  │
│  │  - Real-time vLLM metrics dashboards      │  │
│  └───────────────────────────────────────────┘  │
│                      │                            │
└──────────────────────┼────────────────────────────┘
                       │ SSH port forward 3000:3000
              ┌────────▼────────┐
              │ Your Laptop     │
              │  - View Grafana │
              │    in browser   │
              └─────────────────┘
```

### Deployment Scenario 2: Remote Monitoring (SSH Tunnel)

When running Grafana locally to monitor a remote vLLM server:

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
```

**Note:** Post-test benchmark analysis (GuideLLM results) is handled by
Streamlit Dashboard - see ../dashboard-examples/README.md

**Benefits:**
- ✅ Real-time monitoring during test execution
- ✅ No cloud costs for monitoring infrastructure
- ✅ No exposed ports or router configuration (uses SSH tunnels)
- ✅ Access Grafana anytime at <http://localhost:3000>
- ✅ Separate tools for live monitoring (Grafana) vs post-test analysis (Streamlit)

## Quick Start

### Recommended: Using Ansible Playbook

The Ansible playbook automatically handles port detection and configuration:

```bash
cd automation/test-execution/ansible

# Start Grafana stack (auto-detects available ports and OS)
ansible-playbook start-grafana.yml
```

The playbook will:
- Auto-detect OS (macOS vs Linux) and use correct configuration
- Auto-detect available Prometheus port (9090 or 9091)
- Update Grafana datasource configuration automatically
- Start all services with proper networking
- **Create SSH tunnel automatically if DUT_HOSTNAME and ANSIBLE_SSH_KEY are set**

**For remote vLLM monitoring (SSH tunnel):**
```bash
# Set environment variables first (usually already set when running benchmarks)
export DUT_HOSTNAME=your-vllm-server.compute.amazonaws.com
export ANSIBLE_SSH_KEY=/path/to/your/key.pem
export ANSIBLE_SSH_USER=ec2-user  # Optional, defaults to ec2-user

# Then run the playbook - it will create the SSH tunnel automatically
ansible-playbook start-grafana.yml
```

### Alternative: Manual Docker Compose

For manual deployment without Ansible:

**On macOS:**
```bash
cd automation/test-execution/grafana

# Start with Docker Compose
docker-compose -f docker-compose.macos.yml up -d

# OR with Podman
podman-compose -f docker-compose.macos.yml up -d

# Verify services
docker-compose -f docker-compose.macos.yml ps
```

**On Linux:**
```bash
cd automation/test-execution/grafana

# Start with Docker Compose
docker-compose up -d

# OR with Podman
podman-compose up -d

# Verify services
docker-compose ps
```

**Expected output (macOS):**
```
NAME              STATUS              PORTS
prometheus        running             0.0.0.0:9090->9090/tcp
grafana           running             0.0.0.0:3000->3000/tcp
```

**Expected output (Linux):**
```
NAME           STATUS
prometheus     running (host network)
grafana        running (host network)
```

#### Handling Port Conflicts (Manual Deployment)

If port 9090 is already in use on your system (e.g., by systemd):

1. **Set the Prometheus port:**
   ```bash
   export PROMETHEUS_PORT=9091
   ```

2. **Update the Grafana datasource file:**
   Edit `provisioning/datasources/prometheus.yaml` and change:
   ```yaml
   url: http://localhost:9090
   ```
   to:
   ```yaml
   url: http://localhost:9091
   ```

3. **Start the stack:**
   ```bash
   docker-compose up -d
   # OR
   podman-compose up -d
   ```

4. **Verify the datasource in Grafana:**
   - Open Grafana at `http://localhost:3000`
   - Go to **Configuration → Data Sources → Prometheus-vLLM**
   - Verify URL shows `http://localhost:9091` (or your port)
   - If not, update it manually and click **Save & Test**

**Note:** The Ansible playbook handles all of this automatically.

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

**macOS:**
```bash
# Stop and keep data
docker-compose -f docker-compose.macos.yml down

# Stop and remove all data
docker-compose -f docker-compose.macos.yml down -v
```

**Linux:**
```bash
# Stop and keep data
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## SSH Tunnel Setup (Only for Remote Deployment)

**Note:** If you're running Grafana/Prometheus on the **same server as vLLM**, you don't need an SSH tunnel. The containers use host networking and can access vLLM directly at `localhost:8000`.

If deploying Grafana on your **local machine** to monitor a **remote vLLM server**, you must create an SSH tunnel to forward the vLLM metrics endpoint (port 8000) to localhost.

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
      # macOS: use host.containers.internal:8000
      # Linux: use localhost:8000
      - targets: ['<vllm_host>:8000']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'vllm_.*'
        action: keep
```

### Key Settings

- **Scrape interval:** 10s for real-time monitoring
- **Retention:** 30 days by default
- **Storage:** Local volume (persists between restarts)
- **Target host:** Platform-specific
  - macOS: Use `host.containers.internal:8000` (bridge networking)
  - Linux: Use `localhost:8000` (host networking)

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

### Grafana shows "No data" or datasource errors

1. **Check time range** - Top-right picker, try "Last 5 minutes" or "Last 15 minutes"

2. **Verify datasource port is correct:**
   - In Grafana, go to **Configuration → Data Sources → Prometheus-vLLM**
   - Check the URL matches your Prometheus port (e.g., `http://localhost:9091`)
   - If it's wrong, update it manually:
     - Change URL to `http://localhost:9091` (or your PROMETHEUS_PORT)
     - Click **Save & Test**
   - Common issue: If you see `http://vllm-prometheus:9090`, the datasource wasn't updated for host networking

3. **Test the datasource** - Settings → Data Sources → Prometheus → Save & Test
   - Should show "Data source is working"
   - If you see connection errors, verify the port number matches Prometheus

4. **Verify Prometheus is accessible:**
   ```bash
   curl http://localhost:9091/api/v1/targets
   ```

5. **Check vLLM server is running** and exposing metrics:
   ```bash
   curl http://localhost:8000/metrics | grep vllm
   ```

### Manually Updating Datasource Port in Grafana

If Prometheus is using a different port (e.g., 9091 instead of 9090):

1. Open Grafana: `http://localhost:3000`
2. Navigate to **Configuration** (⚙️) → **Data Sources**
3. Click on **Prometheus-vLLM**
4. Update the **URL** field:
   - Change from: `http://localhost:9090` or `http://vllm-prometheus:9090`
   - Change to: `http://localhost:9091` (or your PROMETHEUS_PORT)
5. Click **Save & Test**
6. Should show: "Data source is working" ✅

### No live vLLM metrics

1. **Verify vLLM is running and exposing metrics:**
   ```bash
   curl http://localhost:8000/metrics | grep vllm
   ```

2. **Check Prometheus is scraping:**
   ```bash
   curl -s http://localhost:9091/api/v1/targets | grep -A 10 vllm-live
   # Should show "health": "up"
   ```

3. **Verify Prometheus can reach vLLM:**
   ```bash
   curl -s "http://localhost:9091/api/v1/query?query=up{job='vllm-live'}"
   ```

4. **Check Prometheus targets page:**
   - Open `http://localhost:9091/targets`
   - Look for `vllm-live` target showing as UP

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
