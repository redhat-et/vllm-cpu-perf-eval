---
layout: default
title: Dashboards Quick Start
---

Quick guide to accessing and using the dashboards for vLLM performance analysis.

## TL;DR

```bash
# Run a test (metrics auto-collected)
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"

# View results
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh
open <http://localhost:8501>
```

**That's it!** No Grafana setup needed for analysis.

## Two Dashboard Systems

### Streamlit Dashboard (Post-Test Analysis)

**Purpose:** Analyze test results after completion

**Setup:** One-time
```bash
cd automation/test-execution/dashboard-examples
./setup.sh
```

**Launch:**
```bash
cd vllm_dashboard
./launch-dashboard.sh
```

**Access:** <http://localhost:8501>

**What it shows:**
- Client metrics (GuideLLM) - throughput, latency, success rate
- Server metrics (vLLM) - queue depth, cache usage, token rates
- Unified analysis - correlate client & server behavior
- Platform comparisons - side-by-side performance

**Data source:**
- `benchmarks.json` (GuideLLM results)
- `vllm-metrics.json` (vLLM server metrics)

**Requirement:**
- ✅ **No Grafana needed!**
- ✅ Reads JSON files directly
- ✅ Works offline

### Grafana Dashboards (Real-Time Monitoring)

**Purpose:** Watch tests in real-time as they execute

**Setup:**
```bash
cd automation/test-execution/ansible
ansible-playbook start-grafana.yml
```

**Access:** <http://localhost:3000>
- Username: `admin`
- Password: `admin` <!-- pragma: allowlist secret -->

**What it shows:**
- vLLM Performance Statistics
- vLLM Query Statistics
- Live updates during test execution

**Data source:**
- Prometheus scraping vLLM `/metrics` endpoint
- Requires SSH tunnel to DUT

**Requirement:**
- ⚠️ **Optional** - only for live monitoring
- ⚠️ Requires Grafana/Prometheus running
- ⚠️ Requires SSH tunnel setup

## When to Use What

| Scenario | Use | Why |
|----------|-----|-----|
| Analyze completed test | Streamlit | Comprehensive post-test analysis |
| Compare multiple tests | Streamlit | Side-by-side comparison tools |
| Export data to CSV | Streamlit | Built-in export functionality |
| Watch long test progress | Grafana | Real-time monitoring |
| Debug performance issue | Both | Live view + detailed analysis |
| Quick test (<2 min) | Streamlit only | Not worth Grafana setup |
| External endpoint testing | Streamlit | Client metrics always available |

## Testing External Endpoints

When testing external vLLM deployments (cloud, K8s, production):

**Client Metrics (Always Available):**
- ✅ Full GuideLLM results (throughput, latency, success rate)
- ✅ Displayed in Streamlit Client Metrics dashboard
- ✅ Can filter by "vLLM Mode = external"

**Server Metrics (Conditional):**
- ✅ Collected if endpoint exposes `/metrics` endpoint
- ⚠️ Not available if `/metrics` endpoint is private/blocked
- ✅ Automatically detected during test execution
- ✅ Displayed in Streamlit Server Metrics dashboard (if available)

**Grafana Live Monitoring:**
- ❌ Not auto-configured for external endpoints
- ⚠️ Requires manual Prometheus setup
- ℹ️  Rarely available for production endpoints (security)

**Typical workflow:**
```bash
# 1. Configure external endpoint
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-endpoint:8000

# 2. Run test (cores not needed in external mode)
ansible-playbook llm-benchmark-concurrent-load.yml \
  -e "base_workload=chat"

# 3. View results in Streamlit (client metrics + server metrics if available)
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh
```

## Streamlit Dashboard Pages

### 📊 Client Metrics

**Shows:** GuideLLM benchmark results

**Key Metrics:**
- Throughput (tokens/sec)
- TTFT (Time to First Token)
- ITL (Inter-Token Latency)
- E2E Request Latency
- Success Rate

**Visualizations:**
- Line charts by request rate/concurrency
- P50/P95/P99 percentiles
- Peak performance summary
- CSV export

**Best for:**
- Finding optimal load point
- Comparing platforms
- SLO validation
- External endpoint testing (works for both managed and external modes)

### 🖥️ Server Metrics

**Shows:** vLLM internal server performance

**Key Metrics:**
- Request queue (running/waiting)
- KV cache usage
- Token generation rates
- Preemption events

**Visualizations:**
- Time-series plots
- Summary statistics
- Comparison mode (2 tests)
- Raw data view

**Best for:**
- Understanding bottlenecks
- Identifying queue buildup
- Cache behavior analysis
- Server capacity planning

## Analysis Workflow

**Recommended approach:**

1. **Start with Client Metrics**
   - Understand end-user performance
   - Identify optimal load points
   - Check P95/P99 tail latency with multi-percentile overlay

2. **Switch to Server Metrics**
   - Investigate queue buildup
   - Check cache usage patterns
   - Identify bottlenecks

3. **Correlate findings**
   - High latency + queue buildup = Capacity issue
   - Good throughput + high cache = Optimal utilization
   - Client issues + empty queue = Network problem

## Quick Examples

### Example 1: Analyze Single Test

```bash
# 1. Run test
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"

# 2. Launch dashboard
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh

# 3. Navigate to Client Metrics page
# 4. Select your test from filters
# 5. Analyze throughput and latency charts
```

### Example 2: Compare Two Platforms

```bash
# 1. Run test on Platform 1 (Intel)
ansible-playbook llm-benchmark-auto.yml -e "..." \
  -e "platform_name=Intel_Xeon_6975P"

# 2. Run test on Platform 2 (AMD)
ansible-playbook llm-benchmark-auto.yml -e "..." \
  -e "platform_name=AMD_EPYC_9654"

# 3. Launch dashboard
./launch-dashboard.sh

# 4. Use platform filter to select both
# 5. View % difference in Client Metrics page
```

### Example 3: Monitor Long Test

```bash
# 1. Start Grafana (optional for real-time view)
ansible-playbook start-grafana.yml

# 2. Open Grafana in browser
open <http://localhost:3000>

# 3. Run long test
ansible-playbook llm-benchmark-auto.yml -e "guidellm_max_seconds=600" ...

# 4. Watch real-time in Grafana during test
# 5. Analyze detailed results in Streamlit after test
```

## Common Workflows

### Workflow: Find Optimal Configuration

1. **Run core sweep:**
   ```bash
   ansible-playbook llm-core-sweep-auto.yml \
     -e "requested_cores_list=[8,16,32,64]" \
     -e "test_model=..." \
     -e "workload_type=chat"
   ```

2. **Launch Streamlit:**
   ```bash
   ./launch-dashboard.sh
   ```

3. **Navigate to Client Metrics**

4. **Filter by test run ID** (to see all core counts)

5. **Identify peak throughput** and optimal cores

6. **Check Server Metrics** to verify no bottlenecks

### Workflow: Debug Performance Issue

1. **Run test with Grafana** (for real-time monitoring):
   ```bash
   ansible-playbook start-grafana.yml
   ansible-playbook llm-benchmark-auto.yml -e "..."
   ```

2. **Watch Grafana** during test:
   - Check queue depth spikes
   - Monitor cache hit rate
   - Watch for preemptions

3. **Analyze in Streamlit** after test:
   - Start with Client Metrics to check latency
   - Switch to Server Metrics to check queue depth
   - Correlate findings to identify root cause

### Workflow: Validate SLO Compliance

1. **Run test:**
   ```bash
   ansible-playbook llm-benchmark-auto.yml -e "..."
   ```

2. **Open Streamlit Client Metrics**

3. **Check P99 values:**
   - TTFT P99 < 200ms? (chat SLO)
   - ITL P99 < 50ms? (chat SLO)

4. **Export to CSV** if needed for reporting

## Troubleshooting

### Dashboard won't start

```bash
# Check logs
tail -f /tmp/streamlit-vllm-dashboard.log

# Reinstall
cd automation/test-execution/dashboard-examples
./setup.sh
```

### No data appears

1. **Check results directory** in sidebar
2. **Verify test completed:**
   ```bash
   ls -la results/llm/*/
   ```
3. **Update path** if needed (persists across sessions)

### Metrics file missing

```bash
# Check if test completed
find results/llm -name "vllm-metrics.json"

# If missing, metrics collection may have failed
# Check logs:
tail -f results/llm/*/metrics-collector.log
```

### Grafana shows no data

```bash
# 1. Verify Grafana running
curl http://localhost:9090/-/healthy

# 2. Check SSH tunnel
ps aux | grep "ssh.*8000:localhost:8000"

# 3. Check Prometheus targets
open http://localhost:9090/targets
```

**Note:** Streamlit works independently of Grafana - if Grafana has issues, you can still analyze results in Streamlit!

## Tips

### Performance Tips

- ✅ Use Streamlit for detailed analysis - faster than Grafana for post-test review
- ✅ Export to CSV for sharing results with others
- ✅ Use filters to focus on specific tests
- ✅ Keep results directory clean - improves dashboard load time

### Analysis Tips

- ✅ Start with Client Metrics to understand user experience
- ✅ Check Server Metrics if performance is below expectations
- ✅ Switch between dashboards to correlate client & server behavior
- ✅ Compare P50 vs P99 to understand tail latencies

### Grafana Tips

- ✅ Only run Grafana for tests >5 minutes
- ✅ Use "Refresh" dropdown for live updates
- ✅ Zoom into specific time ranges
- ✅ Use annotations to mark test phases

## Reference

- **Metrics Collection Guide:** [metrics-collection.md](metrics-collection.md)
- **Streamlit Dashboard Details:** [dashboard-examples README](../automation/test-execution/dashboard-examples/README.md)
- **Grafana Setup:** [grafana README](../automation/test-execution/grafana/README.md)
- **Getting Started:** [getting-started.md](getting-started.md)

## Quick Commands

```bash
# Start Streamlit dashboard
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh

# Stop Streamlit dashboard
./stop-dashboard.sh

# Start Grafana (optional)
cd ../ansible
ansible-playbook start-grafana.yml

# Stop Grafana
ansible-playbook stop-grafana.yml

# Check what's running
lsof -i :8501  # Streamlit
lsof -i :3000  # Grafana
```
