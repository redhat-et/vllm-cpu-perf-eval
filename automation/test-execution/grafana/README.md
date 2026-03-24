# Grafana Monitoring for vLLM CPU Performance Testing

Real-time and historical analysis of vLLM benchmark results using Grafana and Prometheus.

## Overview

This monitoring stack runs on your **local machine** (Ansible controller) to visualize vLLM performance tests running on remote servers. It provides two types of metrics:

**📊 Metrics (Post-Test)** - GuideLLM results published after benchmark completes
- ✅ Always available via Pushgateway
- ✅ No additional setup required
- 📈 Shows aggregate performance from completed test runs

**🔴 Live Metrics (During Test)** - Real-time vLLM server metrics
- ⚠️ Requires SSH tunnel to remote vLLM server
- 📡 Shows queue depth, cache usage, token rates in real-time
- 📖 Setup instructions below

**Stack Components:**
- **Prometheus** - Time-series database for all metrics
- **Prometheus Pushgateway** - Receives GuideLLM results from Ansible
- **Grafana** - Visualization dashboards
- **Pre-built Dashboards** - Ready-to-use visualizations

## Architecture

```
┌──────────────────────────────┐
│ DUT (Remote Server)          │
│  - vLLM server :8000         │
│  - Exposes /metrics          │
└────────────┬─────────────────┘
             │ SSH tunnel (optional, for live metrics)
             │
┌────────────▼─────────────────┐
│ LOADGEN (Remote Server)      │
│  - Runs GuideLLM benchmarks  │
│  - Pushes results            │
└────────────┬─────────────────┘
             │ HTTP push
             │
┌────────────▼───────────────────────────────────┐
│         (Ansible Controller)                   │
│  ┌──────────────────────────────────────────┐  │
│  │ Prometheus Pushgateway :9091             │  │
│  │  ← Receives GuideLLM results             │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Prometheus :9090                         │  │
│  │  - Scrapes Pushgateway (batch metrics)   │  │
│  │  - Scrapes vLLM live (via tunnel)        │  │
│  │  - Stores all data locally               │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ Grafana :3000                            │  │
│  │  - Dashboards for analysis               │  │
│  │  - Always accessible                     │  │
│  └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ No cloud costs for monitoring infrastructure
- ✅ Shut down expensive EC2 instances immediately after tests
- ✅ Keep all historical data on the Ansible Controller
- ✅ Access Grafana anytime at <http://localhost:3000>
- ✅ No exposed ports or router configuration (uses SSH tunnels)

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
pushgateway    running   0.0.0.0:9091->9091/tcp
grafana        running   0.0.0.0:3000->3000/tcp
```

### 2. Access Grafana

Open browser to: **<http://localhost:3000>**

- **Username:** `admin`
- **Password:** `admin` (you'll be prompted to change on first login)

### 3. Run Benchmarks

```bash
cd ../ansible

ansible-playbook llm-benchmark-auto.yml \
  -i inventory/hosts.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "publish_to_prometheus=true"
```

Results will appear in Grafana dashboards automatically.

### 4. Stop Monitoring Stack

```bash
# Stop and keep data
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## SSH Tunnel for Live Metrics (Optional)

To see **real-time vLLM metrics** during benchmarks, create an SSH tunnel from your local machine to the vLLM server.

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
  # GuideLLM batch results
  - job_name: 'pushgateway'
    honor_labels: true
    static_configs:
      - targets: ['pushgateway:9091']

  # vLLM live metrics (via SSH tunnel)
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

- **Scrape interval:** 10s for live metrics, 15s for batch
- **Retention:** 30 days by default
- **Storage:** Local volume (persists between restarts)

### Customization

To change Prometheus settings, edit `prometheus/prometheus.yml` and restart:

```bash
docker-compose restart prometheus
```

## Available Dashboards

### 1. vLLM Live Metrics

**File:** `dashboards/vllm-live-metrics.json`

Real-time monitoring during benchmark execution:
- Request latencies (TTFT, ITL, E2E) - P50/P90/P95/P99
- Token throughput (prompt & generation)
- Queue metrics (running/waiting requests)
- CPU KV cache usage
- Request length distributions

**Use during:** Active benchmarks to monitor server health

### 2. vLLM vs GuideLLM Comparison

**File:** `dashboards/vllm-guidellm-comparison.json`

Combined analysis:
- **Live metrics** (top) - Real-time vLLM performance
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

### GuideLLM Batch Metrics

Published after benchmark completion:

```promql
# Throughput (tokens/sec)
guidellm_throughput_tokens_per_sec_mean{platform,model,workload,cores}

# Latencies (milliseconds, P50/P95/P99)
guidellm_ttft_ms_p50{...}
guidellm_ttft_ms_p95{...}
guidellm_ttft_ms_p99{...}
guidellm_itl_ms_p50{...}
guidellm_itl_ms_p95{...}
guidellm_itl_ms_p99{...}
guidellm_e2e_latency_ms_p50{...}
guidellm_e2e_latency_ms_p95{...}
guidellm_e2e_latency_ms_p99{...}

# Success rate (%)
guidellm_success_rate_percent{...}
```

### Metric Labels

All GuideLLM metrics include:
- `platform` - CPU/platform identifier
- `model` - Model name
- `workload` - Workload type
- `cores` - Number of cores
- `tensor_parallel` - TP degree
- `numa_node` - NUMA node
- `backend` - Backend type (upstream/intel-optimized)
- `test_run_id` - Unique test ID
- `vllm_version` - vLLM version
- `request_rate` - Request rate (req/s)

## Troubleshooting

### Grafana shows "No data"

1. **Check time range** - Top-right picker, try "Last 30 days"
2. **Check datasource** - Settings → Data Sources → Prometheus → Test
3. **Verify Prometheus** - Open <http://localhost:9090/graph>
4. **Check metrics exist:**
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=guidellm_benchmark_info'
   ```

### No live vLLM metrics

1. **Verify SSH tunnel:**
   ```bash
   ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep
   ```

2. **Test vLLM endpoint:**
   ```bash
   curl http://localhost:8000/metrics | grep vllm
   ```

3. **Check Prometheus targets:**
   ```bash
   open http://localhost:9090/targets
   # vllm-live should show as UP
   ```

### No batch/GuideLLM results

1. **Verify Pushgateway received data:**
   ```bash
   curl http://localhost:9091/metrics | grep guidellm
   ```

2. **Check Prometheus scraped it:**
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=guidellm_benchmark_info'
   ```

3. **Verify publishing was enabled:**
   - Check playbook was run with `-e "publish_to_prometheus=true"`
   - Review playbook output for "Successfully published X metrics"

### Containers won't start

```bash
# Check logs
docker-compose logs prometheus
docker-compose logs pushgateway
docker-compose logs grafana

# Check port conflicts
lsof -i :3000  # Grafana
lsof -i :9090  # Prometheus
lsof -i :9091  # Pushgateway

# Full reset
docker-compose down -v
docker-compose up -d
```

## Port Reference

| Service | Port | Purpose |
|---------|------|---------|
| vLLM | 8000 | API + Metrics |
| Prometheus | 9090 | Web UI + API |
| Pushgateway | 9091 | Metrics receiver |
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
├── dashboards/                         # Pre-built dashboards
│   ├── vllm-live-metrics.json
│   ├── vllm-guidellm-comparison.json
│   └── vllm-load-sweep-analysis.json
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

### Run Benchmark with Publishing

```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "publish_to_prometheus=true"
```

Results are automatically:
- Published to Pushgateway (batch metrics)
- Exported from Prometheus (live metrics, if SSH tunnel active)
- Saved to results directory as JSON

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
- [metrics_publisher role](../ansible/roles/metrics_publisher/README.md) - Publishing details
