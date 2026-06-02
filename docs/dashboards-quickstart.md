---
layout: default
title: Dashboards Quick Start
---

Quick guide to accessing and using the dashboards for vLLM performance analysis.

## TL;DR

```bash
# Run an LLM test (metrics auto-collected)
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"

# Or run an embedding test
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/all-MiniLM-L6-v2" \
  -e "scenario=all"

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
- Client metrics (GuideLLM) - LLM throughput, latency, success rate
- Server metrics (vLLM) - queue depth, cache usage, token rates
- Embedding metrics (vLLM bench serve) - request throughput, latency
- Unified analysis - correlate client & server behavior
- Platform comparisons - side-by-side performance

**Data source:**
- `benchmarks.json` (GuideLLM results for LLM models)
- `vllm-metrics.json` (vLLM server metrics)
- `sweep-*.json`, `concurrent-*.json` (vLLM bench serve for embeddings)

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

**Metric Families:**
- Throughput (tokens/sec) - mean, P50, P95, P99
- TTFT (Time to First Token) - all percentiles
- ITL (Inter-Token Latency) - all percentiles
- E2E Request Latency - all percentiles
- Success Rate (%)
- Efficiency (tokens/sec/core) - managed mode only

**Visualizations:**
- **Multi-percentile overlay**: Select metric family and view Mean, P50, P95, P99 on same chart
- **Visual differentiation**: Each percentile uses distinct line style (solid, dashed, dotted, dash-dot)
- Line charts by request rate or concurrency
- Peak performance summary for selected percentiles
- CSV export

**Understanding Percentiles:**

Percentile definition: Pxx = the value below which xx% of data points fall

*Latency percentiles (lower is better)*:
- **P99 = 99% of requests completed within this latency** (worst-case tail)
- High P99 latency = bad (indicates slow tail)
- Example: TTFT P99 = 200ms → 99% got first token within 200ms

*Throughput percentiles (higher is better)*:
- **P99 = 99% of requests achieved this throughput or lower** (upper bound)
- High P99 throughput = good (shows fast requests)
- Example: Throughput P99 = 100 tok/s → only 1% exceeded 100 tok/s
- **P99 > Mean** = Some fast requests pulled up the average
- **Narrow spread (P99 ≈ P50)** = Consistent per-request throughput

**Best for:**
- Finding optimal load point
- Understanding tail latency behavior (P99 vs P95 vs Mean)
- Comparing platforms across multiple percentiles
- SLO validation (check P95/P99 thresholds)
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

### 📊 Embedding Metrics

**Shows:** vLLM bench serve embedding benchmark results

**Key Metrics:**
- Request throughput (req/s) - how many embedding requests per second
- End-to-end latency (P50, P99, Mean) - time to generate embeddings
- Token processing speed (tokens/sec input)
- Concurrent request handling

**Visualizations:**
- **Saturation curves**: Throughput and P99 latency vs load level (inf, 75%, 50%, 25%)
- **Concurrent load analysis**: Performance vs concurrency level
- **Model comparison**: Side-by-side throughput and latency comparison
- CSV export

**Understanding Embedding Metrics:**

Unlike LLM models (which generate tokens), embedding models:
- ❌ No TTFT (Time To First Token) - no token generation
- ❌ No ITL (Inter-Token Latency) - no streaming
- ✅ **Request throughput (req/s)** - PRIMARY metric for embeddings
- ✅ **End-to-end latency** - time from request to embedding vector
- ✅ **Token processing speed** - how fast it processes input text

**Data Source:**
- `vllm bench serve` JSON results (`sweep-*.json`, `concurrent-*.json`)
- **Note**: Currently uses vLLM bench serve. Future versions will also support GuideLLM embedding tests when available.

**Best for:**
- Finding max sustainable throughput
- Identifying latency sweet spots for embedding workloads
- Comparing embedding model performance
- RAG/search application capacity planning

**Dashboard Filters:**

The Embedding Metrics dashboard includes comprehensive filtering for multi-dimensional analysis:

1. **Primary Filters** (Row 1)
   - **Models** - Select one or more embedding models to compare
   - **Platforms** - Filter by CPU platform (e.g., Intel Xeon, AMD EPYC)
   - **vLLM Mode** - Execution architecture (managed, dut-only, external)

2. **Configuration Filters** (Row 2)
   - **Core Count** - CPU cores allocated to vLLM (8, 16, 32, 64, etc.)
   - **Input Length** - Token length used for testing (512, 1024, 2048, etc.)
   - **Scenario** - Test type (baseline, latency, or all)

3. **Version & Identification** (Row 3)
   - **vLLM Version** - Software version tested
   - **Test Name** - Custom configuration identifier
   - **Date Range** - Time-based filtering for trend analysis

4. **Test Run** (Row 4)
   - Select specific test run to analyze (most recent first)

**Populating Filter Data:**

Filters show "(no data)" when viewing old test results. To populate all filters, run a new test:

```bash
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/all-MiniLM-L6-v2" \
  -e "test_name=Xeon-32C-1024tok" \
  -e "requested_cores=32" \
  -e "embedding_random_input_len=1024" \
  -e "scenario=all"
```

This populates:
- ✅ Platform (auto-detected from CPU)
- ✅ Core Count (from requested_cores)
- ✅ Input Length (from embedding_random_input_len)
- ✅ Test Name (from test_name)
- ✅ vLLM Version (auto-detected)
- ✅ Timestamp (for date filtering)

## Analysis Workflow

**Recommended approach for LLM models:**

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

**Recommended approach for Embedding models:**

1. **Start with Concurrent Load Analysis** (First Tab)
   - Verify concurrent request handling capability
   - Find sweet spot for parallel embedding generation
   - Identify where throughput plateaus
   - Validate latency remains acceptable under concurrency

2. **Deep Dive with Saturation Analysis** (Second Tab)
   - View saturation curve to find max throughput
   - Identify where P99 latency starts degrading
   - Determine optimal operating load (typically 50-75% of max)
   - Fine-tune based on your SLO requirements

3. **Compare Models** (if testing multiple)
   - Side-by-side throughput comparison
   - P99 latency at same load levels
   - Choose model that meets throughput + latency SLOs
   - Use filters to compare same configuration across models

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

### Example 4: Analyze Embedding Model Performance

```bash
# 1. Run embedding test (baseline + concurrent load)
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/all-MiniLM-L6-v2" \
  -e "scenario=all"

# 2. Launch dashboard
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh

# 3. Navigate to Embedding Metrics page
# 4. View saturation curve to identify max throughput
# 5. Check concurrent load analysis for sweet spot
# 6. Export to CSV if needed

# Note: Embedding tests use vLLM bench serve for benchmarking
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

### Workflow: Find Optimal Embedding Model

1. **Run baseline tests for multiple models:**
   ```bash
   # Test multiple embedding models
   for model in "RedHatAI/all-MiniLM-L6-v2" \
                "RedHatAI/nomic-embed-text-v1.5" \
                "RedHatAI/granite-embedding-english-r2"; do
     ansible-playbook embedding-benchmark.yml \
       -e "test_model=$model" \
       -e "scenario=baseline"
   done
   ```

2. **Launch Streamlit:**
   ```bash
   ./launch-dashboard.sh
   ```

3. **Navigate to Embedding Metrics**

4. **Select all models** from filter

5. **Compare max throughput and P99 latency:**
   - Identify which model meets your throughput requirements
   - Check if P99 latency fits your SLO
   - Consider model size vs performance tradeoff

6. **Run concurrent load test** on selected model:
   ```bash
   ansible-playbook embedding-benchmark.yml \
     -e "test_model=<selected-model>" \
     -e "scenario=latency"
   ```

7. **Validate concurrent request handling** in dashboard

**Note:** Embedding tests use `vllm bench serve` for benchmarking. Future versions will also support GuideLLM embedding tests when available.

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
- ✅ Use multi-percentile overlay to compare Mean/P50/P95/P99 on one chart
- ✅ Watch for P99 divergence under load - indicates tail latency degradation
- ✅ Select multiple percentiles (e.g., P95 + P99) to understand latency spread

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
