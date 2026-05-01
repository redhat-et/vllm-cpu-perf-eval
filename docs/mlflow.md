# MLflow Experiment Tracking

MLflow provides a powerful system for tracking, comparing, and analyzing LLM performance experiments over time.

## What is MLflow?

MLflow tracks your benchmark experiments with:
- **Parameters**: Model, hardware, workload configurations
- **Metrics**: Throughput, latency, efficiency measurements (both client & server-side)
- **Artifacts**: Full results, logs, and server metrics files
- **Comparison UI**: Compare multiple runs side-by-side
- **Search & Filter**: Find experiments by tags, parameters, or metrics
- **API Access**: Query experiments programmatically

## Quick Start

### Step 1: Launch MLflow (1 minute)

```bash
cd automation/test-execution/mlflow
./launch-mlflow.sh
```

This script automatically:
- ✅ Detects Docker/Podman and chooses appropriate compose command
- ✅ Creates Python virtual environment
- ✅ Installs MLflow package
- ✅ Starts MLflow tracking server container
- ✅ Sets `MLFLOW_TRACKING_URI` environment variable
- ✅ Opens browser to http://localhost:5000

### Step 2: Import Your Benchmark Results

```bash
cd automation/test-execution/ansible/scripts

# Import all results
./mlflow-quick-log.sh --all

# Or just the latest test
./mlflow-quick-log.sh --latest

# Or today's tests
./mlflow-quick-log.sh --today

# With filters
./mlflow-quick-log.sh --all --model Llama --workload chat
```

### Step 3: View Results

Open http://localhost:5000 to:
- Browse experiments organized by model and workload
- Compare runs side-by-side
- Search and filter by parameters or metrics
- Download artifacts (logs, metrics JSON files)
- Visualize trends with charts

## What Gets Tracked

### Client-Side Metrics (from GuideLLM)

Performance metrics measured at the client:
- **Throughput**:
  - `peak_throughput` - Maximum tokens/sec achieved
  - `peak_throughput_load` - Request rate at peak
  - `peak_efficiency` - Tokens/sec/core (managed mode only)
- **Latency** (lower is better, all at P95/P99):
  - `best_ttft_p95`, `best_ttft_p99` - Time to first token (ms)
  - `best_itl_p95`, `best_itl_p99` - Inter-token latency (ms)
  - `best_e2e_p95`, `best_e2e_p99` - End-to-end request latency (s)
- **Test Info**:
  - `num_load_points` - How many load levels tested
  - `test_duration_seconds` - Total test duration

### Server-Side Metrics (from vLLM)

Performance metrics measured at the server:
- **Latency Averages**:
  - `server_ttft_avg_ms` - Time to first token
  - `server_e2e_latency_avg_s` - End-to-end request latency
  - `server_prefill_time_avg_ms` - Prompt processing time
  - `server_decode_time_avg_ms` - Token generation time
  - `server_queue_time_avg_ms` - Time requests spend waiting
- **Resource Utilization**:
  - `server_kv_cache_usage_pct` - KV cache utilization percentage
  - `server_cpu_seconds_total` - Total CPU time consumed
  - `server_memory_mb` - Memory footprint
- **Throughput & Quality**:
  - `server_request_success_rate` - Percentage of successful requests
  - `server_prefix_cache_hit_rate` - Cache effectiveness
  - `server_total_tokens`, `server_prompt_tokens_total`, `server_generation_tokens_total`
  - `server_avg_prompt_tokens_per_req`, `server_avg_output_tokens_per_req`
- **Operational**:
  - `server_num_preemptions` - Request preemptions due to resource constraints
  - `server_requests_total` - Total requests processed

### Parameters

Configuration details for each run:
- **Model**: `model`, `backend`, `tensor_parallel`, `model_source`
- **Hardware**: `platform`, `core_count`, `core_config_name`, `cpuset_cpus`, `cpuset_mems`
- **Software**: `vllm_version`, `guidellm_version`
- **Test Config**: `workload`, `vllm_mode`, `config_type`, `test_name`
- **Load Config**: `load_sweep_rates`, `max_concurrency`, `strategy_type`
- **Request Config**: `output_tokens`, `prompt_tokens`

### Artifacts

Files uploaded with each run:
- **Results**: `benchmarks.json`, `test-metadata.json`, `benchmarks.csv`
- **Client Logs**: `guidellm.log`, `metrics-collector.log`
- **Server Metrics**: `vllm-metrics.json`
- **Server Logs**: `vllm-server.log` (if available)

### Tags

For filtering and organization:
- `model_family`: e.g., "meta-llama", "Qwen"
- `model_name`: e.g., "Llama-3.1-8B-Instruct"
- `workload_type`: chat, summarization, code, rag
- `vllm_mode`: managed or external
- `platform`: CPU platform name
- `test_name`: Custom test identifier

## Using MLflow UI

### Compare Runs

1. Select an experiment (e.g., `LLM-Benchmarks/meta-llama_Llama-3.1-8B/chat`)
2. Check boxes next to 2+ runs you want to compare
3. Click "Compare" button
4. View side-by-side comparison with:
   - All metrics in bar charts
   - Parameter differences highlighted
   - Scatter plots and visualizations

**Use cases**:
- Compare Xeon vs EPYC performance
- Evaluate impact of SMT on/off
- Compare different vLLM versions
- Find best core configuration

### Visualize Metrics

1. In experiment view, click "Chart" button
2. Create custom visualizations:
   - **Parallel Coordinates**: See all metrics at once
   - **Scatter Plot**: X=core_count, Y=peak_throughput
   - **Bar Chart**: Compare peak_throughput across platforms
   - **Line Plot**: Throughput trends over time

**Example insights**:
- Does throughput scale linearly with cores?
- Latency vs throughput tradeoff analysis
- Identify optimal efficiency points

### Filter and Search

Use the table view to:
- **Sort**: Click column headers (e.g., sort by `peak_throughput`)
- **Filter**: Click "Filter" button to create queries:
  ```
  params.platform = 'Xeon'
  metrics.peak_throughput > 500
  params.vllm_mode = 'managed'
  tags.workload_type = 'chat'
  ```
- **Customize columns**: Add/remove metrics and parameters to display

### View Artifacts

1. Click on any run
2. Click "Artifacts" tab on the right
3. Navigate folders:
   - `logs/` → `guidellm.log`, `metrics-collector.log`
   - `results/` → `benchmarks.json`, `test-metadata.json`, `benchmarks.csv`
   - `server_metrics/` → `vllm-metrics.json`
4. Click any file to view or download

## Command Reference

### Quick Helper Script

```bash
cd automation/test-execution/ansible/scripts

# Import latest test only
./mlflow-quick-log.sh --latest

# Import all results
./mlflow-quick-log.sh --all

# Import today's tests
./mlflow-quick-log.sh --today

# Filter by model
./mlflow-quick-log.sh --all --model Llama-3.1

# Filter by workload
./mlflow-quick-log.sh --all --workload chat

# Combine filters
./mlflow-quick-log.sh --all --model Qwen --workload summarization

# Show help
./mlflow-quick-log.sh --help
```

### Ansible Playbook

```bash
cd automation/test-execution/ansible

# Log single test
ansible-playbook log-to-mlflow.yml \
  -e "benchmarks_file=results/llm/.../benchmarks.json" \
  -e "metadata_file=results/llm/.../test-metadata.json"

# Batch import all
ansible-playbook log-to-mlflow.yml -e "batch_import=true"

# Batch import with filters
ansible-playbook log-to-mlflow.yml \
  -e "batch_import=true" \
  -e "model_filter=Llama-3.1" \
  -e "workload_filter=chat"
```

### Direct Python Script

```bash
cd automation/test-execution/ansible/scripts

# Activate MLflow venv
source ../../mlflow/venv/bin/activate

# Log single test
python3 log_to_mlflow.py \
  benchmarks.json \
  test-metadata.json

# With custom experiment name
python3 log_to_mlflow.py \
  benchmarks.json test-metadata.json \
  -e "My-Custom-Experiment"

# With per-load-point metrics
python3 log_to_mlflow.py \
  benchmarks.json test-metadata.json \
  --log-per-load-point

# With remote server
python3 log_to_mlflow.py \
  benchmarks.json test-metadata.json \
  -u http://mlflow-server:5000
```

## Workflow Recommendations

### Typical Workflow

1. **Run benchmarks** (no MLflow dependency):
   ```bash
   ansible-playbook llm-benchmark.yml \
     -e "test_model=meta-llama/Llama-3.1-8B-Instruct" \
     -e "workload_type=chat" \
     -e "core_config_name=128c"
   ```

2. **Log to MLflow** (separate step):
   ```bash
   cd automation/test-execution/ansible/scripts
   ./mlflow-quick-log.sh --latest
   ```

3. **View results**: http://localhost:5000

### Batch Import Strategy

Run multiple tests, then bulk import:

```bash
# Run full test suite
ansible-playbook llm-core-sweep-auto.yml \
  -e "test_model=meta-llama/Llama-3.1-8B-Instruct"

# Import everything when done
cd automation/test-execution/ansible/scripts
./mlflow-quick-log.sh --all
```

**Benefits**:
- ✅ Tests remain independent of MLflow
- ✅ Can run tests even if MLflow is down
- ✅ Can import old results anytime
- ✅ Easier to debug test vs logging issues

## Python API

Query experiments programmatically:

```python
import mlflow
from mlflow.tracking import MlflowClient

# Set tracking URI
mlflow.set_tracking_uri("http://localhost:5000")

# Search runs
runs = mlflow.search_runs(
    experiment_names=["LLM-Benchmarks/meta-llama_Llama-3.1-8B-Instruct/chat"],
    filter_string="params.platform = 'Xeon' and metrics.peak_throughput > 500",
    order_by=["metrics.peak_throughput DESC"]
)

# Print top performers
for _, run in runs.head(5).iterrows():
    print(f"{run['run_name']}: {run['metrics.peak_throughput']:.2f} tok/s")
    print(f"  Platform: {run['params.platform']}")
    print(f"  Cores: {run['params.core_count']}")
    print(f"  Best TTFT P95: {run['metrics.best_ttft_p95']:.2f} ms")
```

### Export to DataFrame

```python
import mlflow
import pandas as pd

runs = mlflow.search_runs(
    experiment_names=["LLM-Benchmarks/meta-llama_Llama-3.1-8B-Instruct/chat"]
)

# Get specific columns
df = runs[['run_name', 'metrics.peak_throughput', 'params.platform', 'params.core_count']]

# Analyze
print(df.groupby('params.platform')['metrics.peak_throughput'].describe())

# Save to CSV
df.to_csv('experiment_results.csv', index=False)
```

## Management

### Starting/Stopping MLflow

```bash
cd automation/test-execution/mlflow

# Start
./launch-mlflow.sh

# Stop
./stop-mlflow.sh

# Stop and remove all data (careful!)
./stop-mlflow.sh
podman-compose down -v
rm -rf artifacts/
```

### Data Persistence

MLflow data is stored in:
- **Database**: Docker volume `mlflow-data`
- **Artifacts**: `./artifacts/` directory (bind mount)

Data persists across container restarts.

### Backup

```bash
cd automation/test-execution/mlflow

# Backup artifacts
tar -czf mlflow-artifacts-$(date +%Y%m%d).tar.gz artifacts/

# Backup database volume
podman run --rm \
  -v mlflow_mlflow-data:/data \
  -v $(pwd):/backup \
  alpine tar -czf /backup/mlflow-db-$(date +%Y%m%d).tar.gz -C /data .
```

### Remote Tracking Server

To use a remote MLflow server instead of local:

```bash
# Set environment variable
export MLFLOW_TRACKING_URI=http://mlflow-server.example.com:5000

# Or pass to script
./mlflow-quick-log.sh --all
```

The tracking URI will be automatically used.

### Production Setup with PostgreSQL

For production use with multiple concurrent users, enable PostgreSQL in `docker-compose.yml`:

1. Uncomment the `postgres` service section
2. Update MLflow service environment:
   ```yaml
   environment:
     - MLFLOW_BACKEND_STORE_URI=postgresql://mlflow:mlflow@postgres:5432/mlflow
   ```
3. Restart: `./stop-mlflow.sh && ./launch-mlflow.sh`

## MLflow vs Streamlit Dashboard

Both tools serve complementary purposes:

| Feature | Streamlit Dashboard | MLflow |
|---------|---------------------|--------|
| **Purpose** | Detailed analysis & visualization | Experiment tracking & comparison |
| **Use Case** | Dive deep into specific runs | Track trends across many runs |
| **Scope** | Single session analysis | Historical tracking |
| **Strengths** | Custom plots, filters, client metrics | Server metrics, search, tags, Python API |
| **Best For** | Presenting results, exploration | Long-term tracking, multi-experiment comparison |

**Recommendation**: Use both!
- **MLflow** for tracking all experiments over time and cross-experiment comparison
- **Streamlit** for detailed analysis and visualization of specific test results

## Troubleshooting

### MLflow server not accessible

```bash
# Check if container is running
podman ps | grep mlflow

# Check logs
podman logs mlflow-tracking-server

# Restart
cd automation/test-execution/mlflow
./stop-mlflow.sh
./launch-mlflow.sh
```

### Experiments not appearing in UI

1. Verify tracking URI: `echo $MLFLOW_TRACKING_URI`
2. Check script succeeded: Look for "✓ Successfully logged experiment"
3. Refresh browser page
4. Check MLflow server logs for errors

### Permission errors with Podman

The `docker-compose.yml` is configured for Podman with SELinux:
- Uses `user: "0:0"` to run as root
- Uses `:z` flag for shared bind mounts

If issues persist:
```bash
cd automation/test-execution/mlflow
./stop-mlflow.sh
podman-compose down -v
rm -rf artifacts/
./launch-mlflow.sh
```

### Database locked (SQLite)

With concurrent writes to SQLite:
- Use the helper scripts (they run sequentially)
- Or switch to PostgreSQL backend for production

### "Read-only file system" errors

Fixed in current configuration with HTTP artifact uploads. If you see this:
```bash
cd automation/test-execution/mlflow
./stop-mlflow.sh
./launch-mlflow.sh  # Restart with latest config
```

## Experiment Organization

Experiments are automatically organized hierarchically:

```
LLM-Benchmarks/
├── meta-llama_Llama-3.1-8B-Instruct/
│   ├── chat/
│   ├── summarization/
│   └── code/
├── Qwen_Qwen2.5-7B-Instruct/
│   ├── chat/
│   └── chat_lite/
├── RedHatAI_Meta-Llama-3.1-8B-Instruct-quantized.w8a8/
│   ├── chat/
│   └── summarization/
└── ...
```

Run names follow the pattern: `{platform}_{cores}c_{test_run_id}`

Example: `Xeon-NO-SMT_128c_20260501-120000`

## Advanced Features

### Deduplication

The logging system automatically prevents duplicate entries using `test_run_id`. Running `./mlflow-quick-log.sh --all` multiple times is safe - already-logged tests are skipped.

### Deleted Experiment Recovery

If you accidentally delete an experiment in the UI, the logging script automatically restores it when you try to log to it again.

### Custom Experiment Names

```bash
python3 log_to_mlflow.py \
  benchmarks.json test-metadata.json \
  -e "Production-Validation-Tests"
```

### Per-Load-Point Metrics

Log detailed metrics for each load point instead of just aggregate:

```bash
python3 log_to_mlflow.py \
  benchmarks.json test-metadata.json \
  --log-per-load-point
```

This creates metrics like `load_32.0_throughput_mean`, `load_64.0_ttft_p95`, etc.

## References

- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [MLflow Tracking Guide](https://mlflow.org/docs/latest/tracking.html)
- [MLflow Python API](https://mlflow.org/docs/latest/python_api/index.html)
- [Docker Compose Setup](../automation/test-execution/mlflow/docker-compose.yml)
- [Logging Script](../automation/test-execution/ansible/scripts/log_to_mlflow.py)
