# Metrics Publisher Role

**Common role for publishing GuideLLM benchmark results to monitoring systems.**

## Overview

This is the **standard role** for publishing benchmark results. It parses GuideLLM JSON output and publishes metrics to Prometheus Pushgateway for visualization in Grafana.

## Supported Backends

- ✅ **Prometheus Pushgateway** (default)

## Requirements

- GuideLLM JSON results files
- Prometheus Pushgateway accessible from Ansible controller (or via reverse SSH tunnel)

## Role Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `results_path` | Path to GuideLLM results directory | `/path/to/results/16cores-numa0-tp1` |
| `test_model` | Model identifier | `meta-llama/Llama-3.2-1B-Instruct` |
| `workload_type` | Workload type | `chat`, `rag`, `code`, `summarization` |
| `test_run_id` | Unique test identifier | `20260320-135847` |
| `core_configuration` | Core config dict with `cores`, `tensor_parallel`, `numa_node` | See example |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `enable_prometheus_publish` | `true` | Enable/disable publishing |
| `pushgateway_host` | `localhost` | Pushgateway hostname |
| `pushgateway_port` | `9091` | Pushgateway port |
| `pushgateway_protocol` | `http` | Protocol (`http` or `https`) |
| `prometheus_job_name` | `guidellm_benchmark` | Prometheus job name |
| `platform_name` | Auto-detected | CPU/platform name |
| `backend_type` | `upstream` | vLLM backend |
| `vllm_version` | `unknown` | vLLM version |
| `push_retry_count` | `3` | Retry attempts |
| `push_retry_delay` | `5` | Delay between retries (seconds) |

## Usage

### Basic

```yaml
- name: Publish results
  hosts: localhost
  gather_facts: true
  vars:
    results_path: "{{ playbook_dir }}/results/llm/model/workload/16cores"
    test_model: "meta-llama/Llama-3.2-1B-Instruct"
    workload_type: "chat"
    test_run_id: "20260320-135847"
    core_configuration:
      cores: 16
      tensor_parallel: 1
      numa_node: 0

  roles:
    - metrics_publisher
```

### Integrated with Benchmark Playbook

```yaml
# Add to end of llm-benchmark-auto.yml
- name: "Publish Results"
  hosts: localhost
  gather_facts: true
  vars:
    results_path: "{{ playbook_dir }}/../../../results/llm/{{ test_model | replace('/', '__') }}/{{ workload_type }}-{{ test_run_id }}/{{ core_configuration.name }}"
    test_run_id: "{{ hostvars['localhost']['test_run_id'] }}"
    core_configuration: "{{ hostvars['localhost']['core_configuration'] }}"

  tasks:
    - name: Publish benchmark results
      ansible.builtin.include_role:
        name: metrics_publisher
      vars:
        platform_name: "{{ hostvars[groups['dut'][0]]['ansible_processor'][1] | default('Unknown') }}"
        backend_type: "{{ vllm_backend | default('upstream') }}"
      when: publish_to_prometheus | default(false) | bool
```

### Command Line

```bash
# Run benchmark with publishing
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "publish_to_prometheus=true"

# Custom Pushgateway location
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "publish_to_prometheus=true" \
  -e "pushgateway_host=metrics.example.com" \
  -e "pushgateway_protocol=https"
```

## Metrics Published

### Throughput (tokens/sec)
- `guidellm_throughput_tokens_per_sec_mean`
- `guidellm_throughput_tokens_per_sec_p50`
- `guidellm_throughput_tokens_per_sec_p95`
- `guidellm_throughput_tokens_per_sec_p99`
- `guidellm_throughput_tokens_per_sec_max`

### Latency (milliseconds)
- `guidellm_ttft_ms_{mean,p50,p95,p99}` - Time to First Token
- `guidellm_itl_ms_{mean,p50,p95,p99}` - Inter-Token Latency
- `guidellm_e2e_latency_ms_{mean,p50,p95,p99}` - End-to-End Request Latency

### Request Statistics
- `guidellm_total_requests`
- `guidellm_successful_requests`
- `guidellm_failed_requests`
- `guidellm_success_rate_percent`

### Metadata
- `guidellm_benchmark_timestamp`
- `guidellm_benchmark_info` (labels only, value=1)

## Labels

All metrics include these labels for filtering:
- `platform` - CPU/platform name
- `model` - Model name (/ replaced with __)
- `workload` - Workload type
- `cores` - Number of cores
- `tensor_parallel` - TP degree
- `numa_node` - NUMA node ID
- `backend` - Backend type
- `test_run_id` - Unique test ID
- `vllm_version` - vLLM version
- `request_rate_tag` - Request rate * 100 (for sorting)
- `request_rate` - Actual request rate
- `concurrency` - Concurrency level

## Architecture

```
┌────────────────────────────────────────┐
│ LOADGEN (or DUT)                       │
│  - GuideLLM runs benchmark             │
│  - Results saved as JSON               │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│ Ansible Controller (localhost)         │
│  ┌──────────────────────────────────┐  │
│  │ metrics_publisher role           │  │
│  │  1. Parse GuideLLM JSON          │  │
│  │  2. Extract metrics              │  │
│  │  3. Format as Prometheus metrics │  │
│  │  4. HTTP POST to Pushgateway     │  │
│  └──────────────┬───────────────────┘  │
│                 │                       │
│  ┌──────────────▼───────────────────┐  │
│  │ Prometheus Pushgateway :9091     │  │
│  │  - Receives metrics              │  │
│  │  - Stores until Prometheus       │  │
│  │    scrapes them                  │  │
│  └──────────────┬───────────────────┘  │
└─────────────────┼───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Prometheus                              │
│  - Scrapes Pushgateway every 15s        │
│  - Stores all historical metrics        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Grafana                                 │
│  - Query and visualize metrics          │
│  - Compare platforms                    │
│  - Track trends over time               │
└─────────────────────────────────────────┘
```

## Deployment Models

### 1. Ansible Controller (Recommended)

**Setup:** Pushgateway runs on your laptop/workstation
**How it works:** Role delegates push to localhost
**Benefits:** No exposed ports, all data local, zero cloud costs

```yaml
# In role tasks
- name: Push metrics
  ansible.builtin.uri:
    url: "http://localhost:9091/metrics/..."
    method: POST
  delegate_to: localhost  # ← Push from controller
  become: false
```

### 2. LOADGEN Host

**Setup:** Pushgateway runs on LOADGEN
**How it works:** Direct push from LOADGEN
**Benefits:** Simpler network setup

Requires changing:
```yaml
pushgateway_host: loadgen-hostname
```

### 3. Remote Pushgateway

**Setup:** Pushgateway on dedicated host
**How it works:** Direct push over network
**Benefits:** Centralized metrics collection

```yaml
pushgateway_host: metrics.example.com
pushgateway_protocol: https
```

## Troubleshooting

### No JSON results found

**Error:** `No GuideLLM JSON results found in <path>`

**Fix:**
1. Verify `results_path` is correct
2. Check benchmark completed successfully
3. Look for: `benchmark_results*.json` or `*_benchmark.json`

### Pushgateway connection failed

**Error:** `Failed to publish metrics to Prometheus Pushgateway`

**Fix:**
```bash
# Verify Pushgateway is accessible
curl http://localhost:9091/-/healthy

# Check from LOADGEN if not using delegation
ssh user@loadgen "curl http://localhost:9091/-/healthy"

# Test manual push
curl -X POST "http://localhost:9091/metrics/job/test" \
  -H "Content-Type: text/plain" \
  --data-binary "test_metric 1.0"
```

### Metrics not in Prometheus

**Fix:**
```bash
# 1. Check Pushgateway has metrics
curl http://localhost:9091/metrics | grep guidellm

# 2. Check Prometheus is scraping Pushgateway
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="pushgateway")'

# 3. Query Prometheus directly
curl http://localhost:9090/api/v1/query?query=guidellm_benchmark_info
```

## Examples

### Multi-Platform Comparison

```bash
# Platform 1: Intel
ansible-playbook llm-benchmark-auto.yml \
  -e "publish_to_prometheus=true" \
  -e "platform_name=Intel_Xeon_6975P"

# Platform 2: AMD
ansible-playbook llm-benchmark-auto.yml \
  -e "publish_to_prometheus=true" \
  -e "platform_name=AMD_EPYC_9R45"

# View in Grafana with platform filter
```

### Batch Publishing Existing Results

```yaml
# publish-old-results.yml
- name: Publish historical results
  hosts: localhost
  gather_facts: true
  tasks:
    - name: Find all result directories
      ansible.builtin.find:
        paths: "{{ playbook_dir }}/results/llm"
        patterns: "*cores-numa*"
        file_type: directory
        recurse: yes
      register: result_dirs

    - name: Publish each result
      ansible.builtin.include_role:
        name: metrics_publisher
      vars:
        results_path: "{{ item.path }}"
        # Extract metadata from path...
      loop: "{{ result_dirs.files }}"
```


## See Also

- [QUICKSTART.md](../../../grafana/QUICKSTART.md) - Full setup guide
- [METRICS_COMPARISON.md](../../../grafana/METRICS_COMPARISON.md) - vLLM vs GuideLLM metrics
- [Prometheus Pushgateway Docs](https://github.com/prometheus/pushgateway)

## License

Same as parent project
