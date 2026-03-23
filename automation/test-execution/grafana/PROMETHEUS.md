# Prometheus + vLLM Live Metrics Setup

This guide explains how to monitor your vLLM inference server in real-time using Prometheus and Grafana.

## Overview

The monitoring stack includes:
- **Prometheus** - Collects and stores all metrics (live vLLM + batch GuideLLM)
- **Prometheus Pushgateway** - Receives batch GuideLLM results from Ansible
- **Grafana** - Visualizes both live and batch metrics

## Architecture

```
┌─────────────────────────────────────────────────┐
│ vLLM Server (running on DUT)                    │
│  - Exposes /metrics endpoint on port 8000       │
│  - Run with: --enable-metrics                   │
└──────────────────┬──────────────────────────────┘
                   │ HTTP GET /metrics
                   ▼
┌─────────────────────────────────────────────────┐
│ Prometheus (Port 9090)                          │
│  - Scrapes vLLM metrics every 10s               │
│  - Stores time-series data (30 day retention)   │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│ Grafana (Port 3000)                             │
│  - Dashboard: vLLM Live Metrics                 │
│  - Real-time visualization                      │
│  - Latency, throughput, queue metrics           │
└─────────────────────────────────────────────────┘
```

## Quick Start

### 1. Configure vLLM Metrics Endpoint

Update the Prometheus configuration with your vLLM server address:

```bash
cd automation/test-execution/grafana

# Edit prometheus/prometheus.yml
# Update the target address to match your vLLM server
vi prometheus/prometheus.yml
```

**Example configurations:**

**Option A: vLLM on AWS EC2 DUT**
```yaml
static_configs:
  - targets:
    - 'ec2-3-17-205-30.us-east-2.compute.amazonaws.com:8000'
```

**Option B: vLLM in Docker on same network**
```yaml
static_configs:
  - targets:
    - 'vllm-server:8000'  # Container name
```

**Option C: vLLM on localhost**
```yaml
static_configs:
  - targets:
    - 'localhost:8000'
```

### 2. Start the Monitoring Stack

```bash
cd automation/test-execution/grafana

# Start all services (Prometheus, Pushgateway, Grafana)
docker-compose up -d

# Verify all services are healthy
docker-compose ps

# Check logs if needed
docker-compose logs prometheus
docker-compose logs grafana
```

### 3. Run vLLM with Metrics Enabled

**On your DUT host, run vLLM with metrics enabled:**

```bash
# Basic example with metrics
vllm serve meta-llama/Llama-3.2-1B-Instruct \
  --enable-metrics \
  --port 8000

# With custom metrics port
vllm serve meta-llama/Llama-3.2-1B-Instruct \
  --enable-metrics \
  --metrics-port 8080

# In Docker/Podman
docker run -d \
  --name vllm-server \
  -p 8000:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --enable-metrics
```

**Important:** Ensure the metrics port is accessible from where Prometheus is running!

### 4. Verify Metrics Collection

```bash
# Check vLLM metrics endpoint
curl http://<DUT-IP>:8000/metrics

# Check Prometheus is scraping
curl http://localhost:9090/api/v1/targets

# Or open in browser
open http://localhost:9090/targets
```

You should see the `vllm` job with state `UP`.

### 5. Access Grafana Dashboards

Open Grafana: **<http://localhost:3000>**

**Login:** admin / admin

**Available Dashboards:**
1. **vLLM Live Metrics** - Real-time server performance
   - Request latencies (E2E, TTFT, ITL)
   - Throughput (prompt & generation tokens/sec)
   - Queue metrics (running/waiting requests)
   - GPU KV cache usage
   - Request length distributions

2. **vLLM Load Sweep Analysis** - Benchmark results
   - GuideLLM test results across load levels
   - Platform comparisons (AMD vs Intel)
   - Historical performance trends

## Dashboard Details

### vLLM Live Metrics Dashboard

**Panels:**
- **E2E Request Latency** - End-to-end latency percentiles (P50/P90/P95/P99)
- **Time to First Token (TTFT)** - Time until first token generated
- **Inter-Token Latency (ITL)** - Time between tokens
- **Prompt Throughput** - Tokens/sec for prompt processing
- **Generation Throughput** - Tokens/sec for generation
- **Running Requests** - Current requests being processed
- **Waiting Requests** - Queued requests
- **Queue Time** - Time requests wait in queue
- **GPU KV Cache Usage** - Cache utilization percentage
- **Request Length Heatmap** - Distribution of prompt lengths
- **Generation Length Heatmap** - Distribution of generation lengths

**Use Cases:**
- Monitor server health during benchmarks
- Identify bottlenecks (queue buildup, cache pressure)
- Tune vLLM configuration based on real-time metrics
- Detect performance degradation

## Prometheus Configuration

### Scrape Configuration

Located at: `prometheus/prometheus.yml`

**Key settings:**
```yaml
global:
  scrape_interval: 15s      # Default scrape frequency
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'vllm'
    scrape_interval: 10s    # More frequent for vLLM
    scrape_timeout: 5s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['<vllm-host>:8000']
```

### Updating Targets

To monitor multiple vLLM instances:

```yaml
scrape_configs:
  - job_name: 'vllm'
    static_configs:
      # Instance 1
      - targets: ['dut-1.example.com:8000']
        labels:
          instance: 'dut-1'
          platform: 'intel-xeon'

      # Instance 2
      - targets: ['dut-2.example.com:8000']
        labels:
          instance: 'dut-2'
          platform: 'amd-epyc'
```

Reload Prometheus config without restart:
```bash
docker exec vllm-prometheus kill -HUP 1
# Or use API
curl -X POST http://localhost:9090/-/reload
```

## Integration with Benchmarks

### Use Both Dashboards Together

**During benchmark execution:**
1. Open **vLLM Live Metrics** dashboard
2. Run GuideLLM benchmark
3. Watch real-time metrics:
   - Is the queue building up?
   - Are latencies spiking?
   - Is cache getting full?

**After benchmark completion:**
1. Open **vLLM Load Sweep Analysis** dashboard
2. Review published GuideLLM results
3. Compare with live metrics observations
4. Identify optimization opportunities

### Example Workflow

```bash
# 1. Start monitoring stack
cd automation/test-execution/grafana
docker-compose up -d

# 2. Start vLLM with metrics
ssh $DUT_HOSTNAME
docker run -d --name vllm \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --enable-metrics

# 3. Open live metrics in browser
open http://localhost:3000/d/vllm-live-metrics

# 4. Run benchmark with publishing
cd automation/test-execution/ansible
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "publish_to_grafana=true"

# 5. Watch live metrics during test, review results after
```

## Troubleshooting

### Prometheus Not Scraping vLLM

**Check 1: vLLM metrics endpoint accessible**
```bash
curl http://<vllm-host>:8000/metrics
```

**Check 2: Network connectivity**
```bash
# From Prometheus container
docker exec vllm-prometheus wget -qO- http://<vllm-host>:8000/metrics
```

**Check 3: Prometheus targets**
```bash
# Check target status
curl http://localhost:9090/api/v1/targets | jq
```

**Check 4: Firewall/Security groups**
- Ensure port 8000 is open on DUT
- Check AWS security groups allow ingress from your monitoring host

### No Data in Grafana Dashboard

**Verify Prometheus datasource:**
1. Grafana → Configuration → Data Sources
2. Click "Prometheus-vLLM"
3. Click "Test" button
4. Should show "Data source is working"

**Verify metrics exist:**
```bash
# Query Prometheus directly
curl 'http://localhost:9090/api/v1/query?query=vllm_request_duration_seconds_count'
```

**Check time range:**
- Dashboard time picker should include current time
- Try "Last 5 minutes" or "Last 15 minutes"

### vLLM Not Exposing Metrics

**Check vLLM startup logs:**
```bash
docker logs vllm-server | grep -i metrics
```

**Verify --enable-metrics flag:**
```bash
# Check running process
docker inspect vllm-server | jq '.[0].Config.Cmd'
```

**vLLM version compatibility:**
- Metrics were added in vLLM v0.5.0+
- Ensure you're using a recent version

## Advanced Configuration

### Custom Retention Period

Edit `docker-compose.yml`:
```yaml
prometheus:
  command:
    - '--storage.tsdb.retention.time=90d'  # Change from 30d
```

### Recording Rules

Create `prometheus/rules.yml` for pre-computed metrics:
```yaml
groups:
  - name: vllm_aggregations
    interval: 60s
    rules:
      - record: vllm:throughput:rate5m
        expr: rate(vllm_generation_tokens_total[5m])

      - record: vllm:latency:p95
        expr: histogram_quantile(0.95, vllm_request_duration_seconds_bucket)
```

Add to `prometheus.yml`:
```yaml
rule_files:
  - '/etc/prometheus/rules.yml'
```

### Alerting

Configure alerts in `prometheus/alerts.yml`:
```yaml
groups:
  - name: vllm_alerts
    rules:
      - alert: HighLatency
        expr: vllm_request_duration_seconds{quantile="0.95"} > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "vLLM P95 latency high"
```

## Port Reference

| Service     | Port | Purpose                       |
|-------------|------|-------------------------------|
| vLLM        | 8000 | API + Metrics endpoint        |
| Prometheus  | 9090 | Web UI + API                  |
| Pushgateway | 9091 | Metrics receiver (GuideLLM)   |
| Grafana     | 3000 | Dashboards                    |

## Security Notes

**Production deployment:**
- [ ] Change Grafana admin password
- [ ] Use HTTPS for Prometheus/Grafana
- [ ] Configure authentication for Prometheus
- [ ] Restrict network access with firewalls
- [ ] Use TLS for vLLM metrics endpoint
- [ ] Store credentials in secrets/vault

## Resources

- [vLLM Metrics Documentation](https://docs.vllm.ai/en/latest/serving/metrics.html)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)

## License

Same as parent project
