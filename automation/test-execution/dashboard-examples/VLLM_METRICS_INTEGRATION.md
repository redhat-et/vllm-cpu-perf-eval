# vLLM Server-Side Metrics Collection

## Overview

Capture server-side vLLM metrics during benchmark execution for comprehensive performance analysis.

**What you get**:
- Client-side metrics (GuideLLM): End-user experience (latencies, throughput, success rates)
- Server-side metrics (vLLM): Internal server state (queue depth, cache hits, generation rate)

## Architecture

**Metrics are collected via Prometheus export (no separate collector needed):**

```
vLLM Server
    ↓ (SSH tunnel)
    ↓ /metrics endpoint
    ↓
Prometheus ← scrapes every 10s during test
    ↓
    ↓ (after test completes)
    ↓
Prometheus API Query ← exports to JSON
    ↓
vllm-metrics.json ← saved with benchmark results
    ↓
Streamlit Dashboard ← analyzes server metrics
```

**Benefits:**
- ✅ No separate collector script
- ✅ No Python dependencies
- ✅ Uses same data Grafana displays live
- ✅ Can export historical data anytime
- ✅ Automatic with benchmark playbook

## Prerequisites

**To collect server-side metrics, you MUST:**

1. **Start Grafana stack** (includes Prometheus):
   ```bash
   ansible-playbook start-grafana.yml
   ```

2. **Create SSH tunnel to vLLM server** (for live metrics):
   ```bash
   export DUT_HOSTNAME=your-vllm-server.compute.amazonaws.com
   export ANSIBLE_SSH_KEY=/path/to/your/key.pem
   ssh -L 8000:localhost:8000 ec2-user@$DUT_HOSTNAME -N -f -i $ANSIBLE_SSH_KEY
   ```

   Or use the automated tunnel setup:
   ```bash
   # SSH tunnel is created automatically by start-grafana.yml if env vars are set
   ```

3. **Verify Prometheus is scraping**:
   ```bash
   # Check targets page
   open http://localhost:9090/targets
   # vllm-live should show as UP
   ```

## Files Created

### Ansible Role: `prometheus_exporter`

```
ansible/roles/prometheus_exporter/
├── tasks/
│   └── main.yml   # Export metrics from Prometheus to JSON
└── defaults/
    └── main.yml   # Configuration variables
```

### Output Files (saved with benchmark results)

```
results/llm/model-name/test-date/config/
├── benchmarks.json           # GuideLLM results (client-side)
├── test-metadata.json        # Test configuration
├── vllm-metrics.json         # vLLM server metrics (exported from Prometheus)
└── vllm-server.log           # Server logs
```

## How It Works

### Automatic Integration (Already configured)

The playbook is already configured with Prometheus export (no manual changes needed):

```yaml
# STEP 5: Run GuideLLM Benchmark
- name: "Auto-Configured LLM Test - Run GuideLLM"
  hosts: load_generator
  become: true
  vars:
    test_run_id: "{{ hostvars['localhost']['test_run_id'] }}"
    core_configuration: "{{ hostvars['localhost']['core_configuration'] }}"

  # Records benchmark start time
  pre_tasks:
    - name: Record benchmark start time
      ansible.builtin.set_fact:
        benchmark_start_time: "{{ ansible_date_time.epoch }}"
      delegate_to: localhost

  roles:
    - role: hf_token
      tasks_from: setup-optional
    - role: benchmark_guidellm

  # Exports metrics from Prometheus after benchmark
  post_tasks:
    - name: Export vLLM metrics from Prometheus
      block:
        - name: Export metrics to JSON
          ansible.builtin.include_role:
            name: prometheus_exporter
          vars:
            prometheus_url: "http://localhost:9090"
            test_start_timestamp: "{{ hostvars['localhost']['benchmark_start_time'] }}"
            test_run_id: "{{ test_run_id }}"
            results_path: "{{ playbook_dir }}/../../../results/llm/{{ test_model | replace('/', '__') }}/{{ workload_type }}-{{ test_run_id }}/{{ core_configuration.name }}"
            export_interval_seconds: 10
      delegate_to: localhost
      become: false
      when: not (skip_prometheus_export | default(false) | bool)
```

### Manual Export (for testing or historical data)

If you want to export metrics from Prometheus manually (e.g., for a test that already ran):

```bash
# 1. Ensure Prometheus is running
curl http://localhost:9090/-/healthy

# 2. Query Prometheus API for specific time range
START_TIME=1711123200  # Unix timestamp of test start
END_TIME=1711123500    # Unix timestamp of test end

# 3. Use the export script (created by prometheus_exporter role)
# This is done automatically by the playbook, but you can run it manually:
ansible-playbook export-prometheus-metrics.yml \
  -e "test_start_timestamp=$START_TIME" \
  -e "test_end_timestamp=$END_TIME" \
  -e "results_path=/path/to/results"
```

**Or use Prometheus web UI to query manually:**
1. Open <http://localhost:9090/graph>
2. Query: `vllm:num_requests_running`
3. Adjust time range to match your test
4. Export data as needed

## vLLM Metrics Captured

Prometheus scrapes the vLLM `/metrics` endpoint every 10 seconds during your test.
After the test, the data is exported to JSON:

```json
{
  "collection_info": {
    "vllm_url": "http://localhost:8000",
    "interval_seconds": 5,
    "duration_seconds": 300,
    "start_time": "2026-03-22T10:00:00",
    "end_time": "2026-03-22T10:05:00",
    "total_samples": 60
  },
  "samples": [
    {
      "timestamp": "2026-03-22T10:00:05",
      "elapsed_seconds": 5.0,
      "metrics": {
        "vllm:num_requests_running": [...],
        "vllm:num_requests_waiting": [...],
        "vllm:gpu_cache_usage_perc": [...],
        "vllm:cpu_cache_usage_perc": [...],
        "vllm:num_preemptions_total": [...],
        "vllm:prompt_tokens_total": [...],
        "vllm:generation_tokens_total": [...],
        "vllm:time_to_first_token_seconds": [...],
        "vllm:time_per_output_token_seconds": [...],
        "vllm:e2e_request_latency_seconds": [...],
        ...
      }
    },
    ...
  ]
}
```

## Jupyter Notebook Integration

The notebook has been updated to:

1. ✅ **Load GuideLLM results** correctly (fixed for v0.5.4 structure)
2. ✅ **Support configurable result paths** (analyze one or many tests)
3. 🔄 **Load vLLM metrics** (TO DO - add visualization cells)

### Next Step: Add vLLM Metrics Visualization

Add these cells to your notebook after running the GuideLLM analysis:

```python
# Load vLLM server metrics
def load_vllm_metrics(results_path):
    metrics_file = Path(results_path) / "vllm-metrics.json"

    if not metrics_file.exists():
        return None

    with open(metrics_file) as f:
        return json.load(f)

# Visualize server vs client metrics
vllm_metrics = load_vllm_metrics(filtered_results[0]['_file_path'])

if vllm_metrics:
    # Extract time-series data
    timestamps = [s['elapsed_seconds'] for s in vllm_metrics['samples']]

    # Example: Queue depth over time
    queue_waiting = []
    queue_running = []

    for sample in vllm_metrics['samples']:
        waiting = [m['value'] for m in sample['metrics'].get('vllm:num_requests_waiting', [])]
        running = [m['value'] for m in sample['metrics'].get('vllm:num_requests_running', [])]

        queue_waiting.append(sum(waiting) / len(waiting) if waiting else 0)
        queue_running.append(sum(running) / len(running) if running else 0)

    # Plot
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=timestamps, y=queue_waiting, name='Waiting', mode='lines'))
    fig.add_trace(go.Scatter(x=timestamps, y=queue_running, name='Running', mode='lines+markers'))
    fig.update_layout(
        title="vLLM Server Queue Depth Over Time",
        xaxis_title="Time (seconds)",
        yaxis_title="Number of Requests"
    )
    fig.show()
```

## Configuration Variables

Edit `ansible/roles/prometheus_exporter/defaults/main.yml`:

```yaml
# Prometheus connection
prometheus_url: "http://localhost:9090"

# Export interval (how often samples are in the exported data)
export_interval_seconds: 10  # Matches Prometheus scrape interval

# vLLM metrics to export (can add more)
vllm_metrics_patterns:
  - "vllm:num_requests_running"
  - "vllm:num_requests_waiting"
  - "vllm:cpu_cache_usage_perc"
  # ... and more
```

## Dependencies

**No additional dependencies required!**

- ✅ Uses Prometheus (already running for Grafana)
- ✅ Python stdlib only (urllib, json)
- ✅ No pip installs needed
- ✅ Works on any system with Python 3

## Troubleshooting

### vllm-metrics.json not created

**Check 1: Is Grafana/Prometheus running?**
```bash
# Prometheus must be running during the test
curl http://localhost:9090/-/healthy

# If not running, start it:
ansible-playbook start-grafana.yml
```

**Check 2: Is SSH tunnel active?**
```bash
# Tunnel must be active for Prometheus to scrape vLLM
ps aux | grep "ssh.*8000:localhost:8000" | grep -v grep

# Verify metrics endpoint is accessible
curl http://localhost:8000/metrics
```

**Check 3: Did Prometheus collect data?**
```bash
# Check Prometheus targets
open http://localhost:9090/targets
# vllm-live should show as UP during test

# Query Prometheus directly
open http://localhost:9090/graph
# Query: vllm:num_requests_running
# Should show data from your test time range
```

**Check 4: Did export run?**
```bash
# Look for export messages in Ansible output
# Should see: "✓ vLLM Metrics Export Complete"

# Check for export errors
# Export only runs if Prometheus is accessible
```

### Prometheus export skipped

If you see "Prometheus is not accessible", this means:
- Grafana stack wasn't running during test
- SSH tunnel wasn't active
- vLLM server wasn't accessible

**To fix:**
1. Start Grafana before next test: `ansible-playbook start-grafana.yml`
2. Ensure SSH tunnel is created (automatically by start-grafana.yml if env vars set)
3. Verify Prometheus can scrape: <http://localhost:9090/targets>

**To skip Prometheus export intentionally:**
```bash
# Run test without server metrics export
ansible-playbook llm-benchmark-auto.yml -e "skip_prometheus_export=true"
```

### Export failed - Prometheus returned no data

**Possible causes:**
- Test ran but Prometheus wasn't scraping (no SSH tunnel)
- Time range incorrect (test finished before export started)
- vLLM server wasn't exposing metrics

**Verify:**
```bash
# Check if vLLM was configured to export metrics
# vLLM should be started with metrics enabled (default behavior)

# Check Prometheus retention (data might be expired)
# Default: 30 days
```

## Benefits

**Side-by-side analysis**:
- Client sees: "Latency increased at 10 req/s"
- Server shows: "Queue depth spiked, cache thrashing occurred"
- Root cause: Insufficient cache capacity

**Performance optimization**:
- Correlate client latency spikes with server queue depth
- Identify cache hit rate impact on throughput
- Monitor preemption events during load spikes
- Track token generation rate vs client-observed ITL

## Example Insights

1. **High P99 latency** + **Server queue waiting** → Insufficient capacity
2. **Stable throughput** + **Cache hit rate dropping** → Working set too large
3. **Client timeout errors** + **Server queue empty** → Network/routing issue
4. **ITL variance** + **Preemption spikes** → Memory pressure, reduce batch size
