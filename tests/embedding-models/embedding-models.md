# Embedding Models Performance Testing

Comprehensive guide for running and analyzing embedding model performance tests on vLLM CPU platforms.

## Overview

These tests evaluate embedding model performance using `vllm bench serve` to establish:

- Baseline performance for CPU-based vLLM inference of embedding models
- Which embedding models work on CPU and their suitability for enterprise use cases based on RPS/Latency
- Performance characteristics under various load conditions
- Optimal CPU configurations and scaling behavior

## Quick Start

### Prerequisites

```bash
# Ensure vLLM >= v0.11.0 (for embedding benchmarking support)
pip install "vllm>=0.11.0"

# For Ansible automation
pip install ansible
ansible-galaxy collection install containers.podman

# Set environment variables
export VLLM_CPU_KVCACHE_SPACE=1GiB
```

### Two-Node Architecture

```text
┌─────────────────────┐          ┌─────────────────────┐
│  Load Generator     │          │    DUT (SUT)        │
│  (192.168.1.20)     │◄────────►│  (192.168.1.10)     │
│                     │  network │                     │
│  vllm bench serve   │          │    vllm (podman)    │
│  --host <dut-ip>    │          │    --port 8000      │
└─────────────────────┘          └─────────────────────┘
```

**Components**:
- **DUT (Device Under Test)**: Runs vLLM server in a container with CPU pinning
- **Load Generator**: Executes `vllm bench serve` against the DUT
- **Network**: Typically 10GbE or higher for minimal network latency impact

## Test Structure

```text
embedding-models/
├── embedding-models.md           # This comprehensive guide
├── model-matrix.yaml             # Model definitions and test mappings
└── test-scenarios/               # Test scenario configurations
    ├── baseline-sweep.yaml       # Baseline throughput test scenario
    └── latency-concurrent.yaml   # Concurrent latency test scenario

automation/test-execution/
├── ansible/                      # Ansible automation (recommended)
│   ├── inventory/
│   │   └── hosts.yml            # Two-node inventory
│   └── playbooks/
│       ├── embedding/
│       │   ├── run-tests.yml    # Main test execution
│       │   ├── run-core-sweep.yml  # Core count sweep
│       │   └── tasks/           # Reusable task files
│       └── common/              # Shared playbooks
└── bash/embedding/              # Bash scripts (manual execution)
    ├── run-baseline.sh          # Run baseline performance tests
    ├── run-latency.sh           # Run latency tests
    └── run-all.sh               # Run all embedding tests
```

## Models Under Test

The test suite focuses on representative models from different architecture families:

| Architecture Family | Representative Model | Application Focus | Parameters |
|-------------------|---------------------|-------------------|------------|
| MiniLM/BERT (English Dense) | ibm-granite/granite-embedding-english-r2 | Encoder-Only (Fastest Baseline) | ~110M |
| XLM-RoBERTa (Multilingual Dense) | ibm-granite/granite-embedding-278m-multilingual | Encoder-Only (Multilingual) | ~278M |

### Model Selection Rationale

- **Granite English R2**: Fast baseline for English-only workloads
- **Granite Multilingual**: Broader language support with reasonable performance

See [model-matrix.yaml](model-matrix.yaml) for complete model definitions and configurations.

## Test Cases and Scenarios

### Test Case 1.1: Baseline Performance and Scalability (English Model)

**Test ID**: `EMB-BASELINE-GRANITE-EN-EMB512`

**Objective**: Establish maximum Request Throughput (RPS) and analyze performance scaling.

- **Test Type**: vllm bench serve (sweep)
- **Model**: ibm-granite/granite-embedding-english-r2
- **Workload**: Embedding (512:1)
- **KV Cache**: 1GiB
- **Quantization**: OFF
- **Primary Metric**: Enterprise English Embedding Throughput (RPS)

**Test Steps**:
1. Find max throughput with `--request-rate inf`
2. Run at 25%, 50%, 75% of max throughput
3. Measure latency curves at each rate

**Expected Outputs**:
- Maximum sustained RPS
- Latency vs throughput curves
- Saturation point identification

### Test Case 1.2: Baseline Performance and Scalability (Multilingual Model)

**Test ID**: `EMB-BASELINE-GRANITE-ML-EMB512`

**Objective**: Establish maximum Request Throughput (RPS) for multilingual model.

- **Test Type**: vllm bench serve (sweep)
- **Model**: ibm-granite/granite-embedding-278m-multilingual
- **Workload**: Embedding (512:1)
- **KV Cache**: 1GiB
- **Quantization**: OFF
- **Primary Metric**: Multilingual Embedding Throughput (RPS)

**Test Steps**: Same as Test Case 1.1

### Test Case 2.1: Latency and Stability Under Load

**Test ID**: `EMB-LATENCY-GRANITE-ML-EMB512`

**Objective**: Measure latency scaling under increasing concurrent requests.

- **Test Type**: vllm bench serve (concurrent)
- **Model**: ibm-granite/granite-embedding-278m-multilingual
- **Workload**: Embedding (512:1)
- **Concurrency Levels**: {16, 32, 64, 128, 196}
- **Primary Metric**: P99 Latency Scaling

**Test Steps**:
1. Run at each concurrency level
2. Measure P95/P99 latency at each level
3. Identify optimal concurrency (throughput plateau, acceptable P99)

**Expected Outputs**:
- Mean/P95/P99 latency at each concurrency
- Throughput at each concurrency
- Sweet spot identification

## Running Tests

### With Ansible (Recommended for Production)

#### 1. Configure Inventory

Edit `automation/test-execution/ansible/inventory/hosts.yml`:

```yaml
dut:
  hosts:
    embedding-dut-01:
      ansible_host: 192.168.1.10  # Your DUT IP

load_generator:
  hosts:
    embedding-loadgen-01:
      ansible_host: 192.168.1.20  # Your Load Gen IP
```

#### 2. Run Tests

```bash
cd automation/test-execution/ansible

# Run all embedding tests
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/hosts.yml

# Run baseline test only
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/hosts.yml \
  -e "scenario=baseline"

# Run latency test only
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/hosts.yml \
  -e "scenario=latency"

# Test specific model
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/hosts.yml \
  -e "test_model=ibm-granite/granite-embedding-english-r2"

# Keep vLLM running after tests
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/hosts.yml \
  -e "cleanup_after_test=false"
```

### With Bash Scripts

#### 1. Start vLLM on DUT

On the DUT node (192.168.1.10):

```bash
# Start vLLM in container
podman run -d \
  --name vllm-embedding-server \
  --network host \
  --cpuset-cpus 0-63 \
  -v /var/lib/vllm-models:/root/.cache/huggingface:rw \
  -e VLLM_CPU_KVCACHE_SPACE=1GiB \
  -e OMP_NUM_THREADS=64 \
  vllm/vllm-openai:latest \
  --model ibm-granite/granite-embedding-278m-multilingual \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16 \
  --max-model-len 512

# Check vLLM is ready
automation/utilities/health-checks/check-vllm.sh \
  --host 192.168.1.10 \
  --port 8000 \
  --verbose
```

#### 2. Run Tests from Load Generator

On the load generator node (192.168.1.20):

```bash
cd automation/test-execution/bash/embedding

# Set DUT connection
export VLLM_HOST=192.168.1.10
export VLLM_PORT=8000

# Run baseline test
./run-baseline.sh ibm-granite/granite-embedding-278m-multilingual

# Run latency test
./run-latency.sh ibm-granite/granite-embedding-278m-multilingual

# Run all tests
./run-all.sh

# Custom configuration
./run-baseline.sh ibm-granite/granite-embedding-english-r2 \
  --vllm-host 192.168.1.10 \
  --num-prompts 2000

# Custom concurrency levels
./run-latency.sh ibm-granite/granite-embedding-278m-multilingual \
  --concurrency "8 16 32 64 128"
```

### Core Count Sweep

Test vLLM with different CPU allocations to find optimal configuration:

```bash
# Test with 8, 16, 32, 64 cores
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/hosts.yml \
  -e "test_core_counts=[8,16,32,64]"

# Baseline test across core counts
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/hosts.yml \
  -e "scenario=baseline" \
  -e "test_core_counts=[16,32,48,64]"

# Full core sweep with latency tests
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/hosts.yml \
  -e "scenario=latency" \
  -e "test_core_counts=[8,16,24,32,40,48,56,64]"
```

**Core Sweep Results Location**:
```text
results/embedding-models/core-sweep-<timestamp>/
├── 8cores/
├── 16cores/
├── 32cores/
└── 64cores/
```

## Test Parameters

### Common Parameters

| Variable | Description | Test Setting |
|----------|-------------|--------------|
| **Workload** | Input/Output token counts (ISL:OSL) | Embedding (512:1) |
| **Input Sequence Length** | Fixed input token count | 512 |
| **Output Sequence Length** | Fixed output token count | 1 |
| **Affinity** | Core allocation strategy | Handled by vLLM automatically |
| **Cores** | Number of cores for test | VENDOR-DEFINED OPTIMAL CONFIGURATION |
| **NUMA nodes** | Number of NUMA nodes used | VENDOR-DEFINED OPTIMAL CONFIGURATION |
| **Dtype** | Data type for model weights | bfloat16 |
| **KV Cache** | KV Cache size | VLLM_CPU_KVCACHE_SPACE=1GiB |
| **Num Prompts** | Total requests in test | 1000 (default) |

### Baseline Test Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `--request-rate` | `inf`, 25%, 50%, 75% of max | Request rate (req/s) |
| `--backend` | `openai-embeddings` | Embedding API backend |
| `--endpoint` | `/v1/embeddings` | API endpoint |
| `--dataset-name` | `random` | Random input generation |
| `--random-input-len` | `512` | Input token count |

### Latency Test Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `--max-concurrency` | `16`, `32`, `64`, `128`, `196` | Concurrent requests |
| `--request-rate` | `inf` | Unlimited request rate |
| `--backend` | `openai-embeddings` | Embedding API backend |
| `--endpoint` | `/v1/embeddings` | API endpoint |

## Test Methodology

### Baseline Performance Tests

These tests use `vllm bench serve` to simulate sweep-rate behavior:

#### 1. Find Maximum Throughput

```bash
vllm bench serve --backend openai-embeddings \
  --model <model> \
  --dataset-name random \
  --random-input-len 512 \
  --num-prompts 1000 \
  --request-rate inf \
  --endpoint /v1/embeddings \
  --save-result \
  --result-filename "<model>-sweep-inf.json"
```

**Key Output**: Maximum sustained RPS (e.g., 42.35 req/s)

#### 2. Measure at Load Levels

Extract max RPS from step 1 and test at fractions:

```bash
# Example: If max RPS = 42.35 req/s
# 25% = 10.6 req/s
# 50% = 21.2 req/s
# 75% = 31.8 req/s

for rate in 10.6 21.2 31.8; do
  vllm bench serve --backend openai-embeddings \
    --model <model> \
    --dataset-name random \
    --random-input-len 512 \
    --num-prompts 1000 \
    --request-rate $rate \
    --endpoint /v1/embeddings \
    --save-result \
    --result-filename "<model>-sweep-${rate}.json"
done
```

**What to Measure**:
- Achieved RPS vs requested rate
- Mean/P95/P99 latency at each rate
- Saturation point where increasing rate doesn't increase throughput

### Latency and Concurrent Load Tests

These tests measure latency scaling with concurrency:

```bash
for concurrency in 16 32 64 128 196; do
  vllm bench serve \
    --backend openai-embeddings \
    --model <model> \
    --dataset-name random \
    --random-input-len 512 \
    --num-prompts 1000 \
    --endpoint /v1/embeddings \
    --request-rate inf \
    --max-concurrency $concurrency \
    --save-result \
    --result-filename "<model>-concurrent-${concurrency}.json"
done
```

**Key Metrics to Monitor**:
- Mean E2EL (ms) - Average end-to-end latency
- P95 E2EL (ms) - 95th percentile latency
- P99 E2EL (ms) - 99th percentile latency (primary metric)
- Request throughput (req/s) - Actual requests completed per second

**What to Look For**:
- **Sweet spot**: Concurrency level where throughput plateaus but P99 latency remains acceptable
- **Degradation point**: When P99 latency increases significantly while throughput gains diminish
- **Comparison**: How P99 scales from low (16) to high (196) concurrency

### Performance Metrics

#### Primary Metrics

| Metric | Description |
|--------|-------------|
| **Request throughput (req/s)** | Total requests successfully processed per second |
| **Total Token throughput (tok/s)** | Combined rate of all input tokens processed per second |
| **Mean E2EL (ms)** | Average end-to-end latency from request to response |
| **P95 E2EL (ms)** | 95th percentile end-to-end latency |
| **P99 E2EL (ms)** | 99th percentile end-to-end latency (primary metric) |

#### System Level Metrics

| Metric | Description |
|--------|-------------|
| **vLLM Process CPU Utilization (%)** | CPU time spent on non-idle threads |
| **Memory Utilization/Consumption (GB)** | Total RAM used by vLLM process |

## Monitoring and Debugging

### Monitor vLLM Logs (DUT)

```bash
# Local monitoring on DUT
automation/utilities/log-monitoring/monitor-vllm-logs.sh

# Remote monitoring from load generator
automation/utilities/log-monitoring/monitor-vllm-logs.sh \
  --mode remote \
  --remote-host 192.168.1.10

# Show last 500 lines without following
automation/utilities/log-monitoring/monitor-vllm-logs.sh \
  --no-follow \
  --lines 500
```

### Monitor Test Progress (Load Generator)

```bash
# Local monitoring
automation/utilities/log-monitoring/monitor-test-progress.sh

# Remote monitoring
automation/utilities/log-monitoring/monitor-test-progress.sh \
  --mode remote \
  --remote-host 192.168.1.20

# Fast refresh (every 2 seconds)
automation/utilities/log-monitoring/monitor-test-progress.sh \
  --refresh 2
```

### Check vLLM Health

```bash
# Quick health check
automation/utilities/health-checks/check-vllm.sh \
  --host 192.168.1.10

# With detailed info
automation/utilities/health-checks/check-vllm.sh \
  --host 192.168.1.10 \
  --verbose

# With custom timeout
automation/utilities/health-checks/check-vllm.sh \
  --host 192.168.1.10 \
  --timeout 600 \
  --interval 10
```

### Multi-Terminal Monitoring Setup

**Terminal 1: DUT vLLM Logs**
```bash
automation/utilities/log-monitoring/monitor-vllm-logs.sh \
  --mode remote \
  --remote-host 192.168.1.10 \
  --follow
```

**Terminal 2: Load Generator Progress**
```bash
automation/utilities/log-monitoring/monitor-test-progress.sh \
  --mode remote \
  --remote-host 192.168.1.20 \
  --refresh 5
```

**Terminal 3: Health Check**
```bash
automation/utilities/health-checks/check-vllm.sh \
  --host 192.168.1.10 \
  --verbose
```

## Results Format and Location

### Results Directory Structure

```text
results/embedding-models/
├── granite-embedding-278m-multilingual/
│   ├── baseline/
│   │   ├── sweep-inf.json
│   │   ├── sweep-25pct.json
│   │   ├── sweep-50pct.json
│   │   └── sweep-75pct.json
│   └── latency/
│       ├── concurrent-16.json
│       ├── concurrent-32.json
│       ├── concurrent-64.json
│       ├── concurrent-128.json
│       └── concurrent-196.json
├── granite-embedding-english-r2/
│   └── ...
└── core-sweep-20260218-143022/
    ├── 8cores/
    ├── 16cores/
    ├── 32cores/
    └── 64cores/

logs/
├── embedding-dut-01/
│   ├── vllm-server-*.log
│   └── system-metrics-*.log
└── embedding-loadgen-01/
    └── test-execution-*.log
```

### Test Settings Documentation

Each test result should include:

| Information | Description |
|------------|-------------|
| **vLLM serving command** | Complete command with all CLI args |
| **vLLM bench serve testing command** | Complete benchmarking command |
| **Optimal Core Count Used** | Number of physical cores (e.g., 32, 64) |
| **vLLM Environment Variables** | All non-default VLLM_ and OMP_ variables |
| **Container build params** | Build variables if built from source |
| **Container image** | Image URL if using containers |

### Baseline Performance Results

Example results table:

| Request Rate | Actual RPS | Mean (ms) | P95 (ms) | P99 (ms) | Calculated Avg. Concurrency |
|-------------|-----------|-----------|----------|----------|---------------------------|
| inf (100%) | 46.97 | 11066.20 | ~19000 | 21143.23 | 519.78 |
| 12 (25%) | 11.99 | 50.91 | ~100 | 137.83 | 0.61 |
| 23 (50%) | 22.98 | 79.27 | ~180 | 224.39 | 1.82 |
| 35 (75%) | 34.89 | 161.10 | ~380 | 451.55 | 5.62 |

**Note**: Calculated Avg. Concurrency uses Little's Law (L = RPS × Mean Latency in Seconds)

### Latency and Stability Results

Example results table:

| Concurrency | RPS | Mean (ms) | P95 (ms) | P99 (ms) |
|------------|-----|-----------|----------|----------|
| 16 | 44.87 | 353.26 | ~365 | 370.72 |
| 32 | 47.66 | 663.30 | ~705 | 731.10 |
| 64 | 48.20 | 1305.45 | ~1450 | 1502.30 |
| 128 | 48.85 | 2589.12 | ~2850 | 2945.67 |
| 196 | 49.01 | 3942.78 | ~4200 | 4356.21 |

### Viewing Results

```bash
# View result summary
cat results/embedding-models/\
granite-embedding-278m-multilingual/baseline/sweep-inf.json | \
jq '{
  rps: .request_throughput,
  mean_latency: .mean_e2e_latency_ms,
  p99_latency: .p99_e2e_latency_ms
}'

# Compare results across core counts
for cores in 8 16 32 64; do
  echo "=== ${cores} cores ==="
  cat results/embedding-models/core-sweep-*/${cores}cores/\
*/baseline/sweep-inf.json | \
    jq '{rps: .request_throughput, p99: .p99_e2e_latency_ms}'
done
```

## Analysis and Reporting

### Generate Graphs

```bash
cd automation/analysis
python generate-embedding-report.py \
  --input ../../results/embedding-models/ \
  --format html \
  --output ../../results/reports/embedding-models.html
```

### Expected Visualizations

1. **Throughput Saturation Curve**: Achieved throughput vs requested rate
2. **Latency vs Request Rate**: Mean and P99 latency scaling
3. **Throughput vs Concurrency**: Request throughput at each concurrency level
4. **Latency vs Concurrency**: Mean and P99 latency scaling with concurrency
5. **Core Count Scaling**: Performance metrics across different CPU allocations

### Key Analysis Points

- **Maximum Sustainable Throughput**: Highest RPS achieved with acceptable P99 latency
- **Latency Scaling**: How latency degrades with increasing load
- **Optimal Concurrency**: Best balance of throughput and latency
- **Core Scaling Efficiency**: Throughput gain per additional core
- **Model Comparison**: Relative performance of different embedding models

## Troubleshooting

### vLLM not starting

```bash
# Check container logs
podman logs vllm-embedding-server

# Check for port conflicts
ss -tulpn | grep 8000

# Check resource availability
free -h
numactl --hardware

# Check for model download issues
podman exec vllm-embedding-server ls -la /root/.cache/huggingface
```

### Connection refused from load generator

```bash
# Check network connectivity
ping <dut-ip>

# Check port is open
nc -zv <dut-ip> 8000

# Check firewall
ssh <dut-ip> "firewall-cmd --list-all"

# Test endpoint directly
curl http://<dut-ip>:8000/health
curl http://<dut-ip>:8000/v1/models
```

### Tests failing

```bash
# Monitor both nodes simultaneously
# Terminal 1: DUT logs
ssh <dut-ip> "podman logs -f vllm-embedding-server"

# Terminal 2: Load generator progress
automation/utilities/log-monitoring/monitor-test-progress.sh \
  --mode remote --remote-host <loadgen-ip>

# Terminal 3: Run tests with verbose output
bash -x \
automation/test-execution/bash/embedding/run-baseline.sh <model>
```

### Slow performance

```bash
# Check CPU governor
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# Set performance mode
sudo cpupower frequency-set -g performance

# Check CPU frequency
lscpu | grep MHz

# Verify CPU pinning
podman exec vllm-embedding-server taskset -cp 1

# Check NUMA balancing
cat /proc/sys/kernel/numa_balancing

# Disable automatic NUMA balancing
echo 0 | sudo tee /proc/sys/kernel/numa_balancing
```

## Common Workflows

### Workflow 1: Single Model Baseline Test

```bash
# 1. Start vLLM on DUT
ssh dut-node "podman run -d --name vllm ... [see Running Tests section]"

# 2. Wait for ready
automation/utilities/health-checks/check-vllm.sh --host <dut-ip>

# 3. Run baseline test
export VLLM_HOST=<dut-ip>
automation/test-execution/bash/embedding/run-baseline.sh <model>

# 4. View results
cat results/embedding-models/<model>/baseline/sweep-inf.json | jq
```

### Workflow 2: Core Count Performance Analysis

```bash
# Use Ansible for automated core sweep
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/hosts.yml \
  -e "test_core_counts=[8,16,24,32,40,48,56,64]" \
  -e "scenario=baseline"

# Results in: results/embedding-models/core-sweep-<timestamp>/

# Analyze core scaling
for cores in 8 16 24 32 40 48 56 64; do
  echo "=== ${cores} cores ==="
  jq '.request_throughput' \
    results/embedding-models/core-sweep-*/\
${cores}cores/*/baseline/sweep-inf.json
done
```

### Workflow 3: Full Model Comparison

```bash
# Test multiple models across both test types
for model in \
  "ibm-granite/granite-embedding-english-r2" \
  "ibm-granite/granite-embedding-278m-multilingual"; do

  echo "Testing $model..."

  # Baseline
  automation/test-execution/bash/embedding/run-baseline.sh "$model"

  # Latency
  automation/test-execution/bash/embedding/run-latency.sh "$model"
done

# Generate comparison report
automation/analysis/generate-embedding-report.py \
  --input results/embedding-models/ \
  --format html
```

### Workflow 4: Continuous Integration Testing

```bash
# Automated nightly test run
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/hosts.yml \
  -e "scenario=all" \
  -e "cleanup_after_test=true" \
  -e "collect_logs=true"

# Results automatically timestamped and stored
# Logs collected to controller
```

## Automation Details

### What Was Created

#### 1. Test Documentation

- **embedding-models.md** (this file): Complete testing guide
- **QUICKSTART.md**: Quick reference (merged into this document)
- **SETUP_SUMMARY.md**: Setup details (merged into this document)

#### 2. Test Scenarios

- **baseline-sweep.yaml**: Baseline performance test configuration
  - Find maximum throughput (`--request-rate inf`)
  - Test at 25%, 50%, 75% of max load
  - Measures request throughput and latency curves

- **latency-concurrent.yaml**: Latency scaling test configuration
  - Concurrency levels: 16, 32, 64, 128, 196
  - Measures P99 latency under load
  - Identifies sweet spot and degradation point

#### 3. Model Matrix

- **model-matrix.yaml**: Defines models and test mappings
  - Test case IDs (EMB-BASELINE-*, EMB-LATENCY-*)
  - Model definitions and architectures
  - Test parameters and configurations
  - Results structure

#### 4. Ansible Automation

**Directory Structure**:
```text
automation/test-execution/ansible/
├── inventory/
│   └── hosts.yml                   # Two-node inventory
├── playbooks/
│   ├── embedding/                  # Embedding-specific playbooks
│   │   ├── run-tests.yml          # Main test execution
│   │   ├── run-core-sweep.yml     # Core count performance sweep
│   │   └── tasks/                 # Reusable task files
│   │       ├── baseline.yml       # Baseline test tasks
│   │       ├── latency.yml        # Latency test tasks
│   │       ├── core-iteration.yml # Core sweep iteration
│   │       └── start-embedding-vllm.yml  # Start vLLM server
│   └── common/                     # Shared playbooks
│       ├── start-vllm-server.yml  # Generic vLLM startup
│       ├── health-check.yml       # Wait for vLLM ready
│       ├── setup-platform.yml     # Platform configuration
│       └── collect-logs.yml       # Collect logs and results
├── filter_plugins/                 # Custom Ansible filters
│   └── cpu_utils.py               # CPU allocation utilities
└── ansible.cfg                     # Ansible configuration
```

**Key Features**:
- **Two-node orchestration**: DUT (vLLM server) + Load Generator (vllm bench serve)
- **Containerized vLLM**: Podman/Docker with CPU pinning support
- **Core count sweep**: Test vLLM with varying CPU allocations (8, 16, 32, 64 cores)
- **Health checks**: Wait for vLLM to be ready before running tests
- **Automatic log collection**: Fetch logs and results to controller
- **NUMA topology detection**: Automatic CPU allocation across NUMA nodes

#### 5. Bash Scripts

**automation/test-execution/bash/embedding/**:

- **run-baseline.sh**: Run baseline performance sweep test
  - Find max RPS with `--request-rate inf`
  - Test at 25%, 50%, 75% load levels
  - Supports remote vLLM via `--vllm-host`

- **run-latency.sh**: Run latency scaling test
  - Test concurrency levels: 16, 32, 64, 128, 196
  - Display real-time metrics
  - Quick analysis summary table

- **run-all.sh**: Run complete test suite
  - Execute baseline and latency tests
  - Support multiple models
  - Integrated with remote vLLM

#### 6. Utilities

**automation/utilities/health-checks/**:
- **check-vllm.sh**: Health check script
  - Wait for vLLM /health endpoint
  - Verify models endpoint
  - Configurable timeout and interval
  - Verbose mode for debugging

**automation/utilities/log-monitoring/**:
- **monitor-vllm-logs.sh**: Monitor vLLM container logs
  - Local or remote (SSH) monitoring
  - Follow logs in real-time
  - Support for both podman and docker

- **monitor-test-progress.sh**: Monitor test execution
  - Track test completion
  - Display real-time metrics
  - Show active processes
  - Works with local or remote load generator

### Ansible Workflow

1. **Start vLLM on DUT**
   - Deploy containerized vLLM with CPU pinning
   - Configure NUMA and OMP settings
   - Wait for initialization

2. **Health Check**
   - Poll `/health` endpoint from load generator
   - Verify `/v1/models` endpoint
   - Ensure vLLM is ready

3. **Run Tests**
   - Execute baseline or latency tests
   - Save results with timestamps
   - Tag with configuration metadata

4. **Collect Results**
   - Fetch results from load generator
   - Collect vLLM logs from DUT
   - Save to controller for analysis

## Configuration Details Required

### Hardware & BIOS Information

When reporting results, include:

- Baseboard Model/Vendor
- Architecture/MicroArchitecture (e.g., Intel Sapphire Rapids)
- Sockets & Cores per Socket
- Instruction Set Architecture (ISA) - AVX512, AMX, VNNI, AVX512_BF16
- L3 Cache Size (MB)
- Hyperthreading Status
- Base/All-Core Max Frequency (GHz)
- NUMA nodes count
- Sub-NUMA Clustering (SNC) status
- Installed Memory Size/Speed/Channels
- Hugepage size and status
- BIOS version
- TDP (W)

### OS & Software Settings

- RHEL Version & Kernel Version
- OS Tuning Parameters (tuned profile, etc.)
- Automatic NUMA Balancing status
- Power and performance policy
- Frequency Governor & Driver
- vLLM version
- Container runtime (Podman/Docker version)
- Python version

### vLLM Configuration

Document all non-default settings:

```bash
# Example configuration documentation
vLLM Version: v0.11.0
Container Image: vllm/vllm-openai:latest
CPU Cores: 64 (0-63)
NUMA Nodes: 2
OMP_NUM_THREADS: 64
VLLM_CPU_KVCACHE_SPACE: 1GiB
Model: ibm-granite/granite-embedding-278m-multilingual
Dtype: bfloat16
Max Model Length: 512
```

## Test ID Naming Convention

Embedding test cases follow the hierarchical naming scheme:

**Format**: `EMB-{TYPE}-{model}-{workload}`

**Components**:
- **Prefix**: `EMB` (Embedding)
- **Type**: `BASELINE` (Baseline Performance), `LATENCY` (Concurrent Latency)
- **Model**: Short abbreviation
  - `GRANITE-EN`: ibm-granite/granite-embedding-english-r2
  - `GRANITE-ML`: ibm-granite/granite-embedding-278m-multilingual
- **Workload**: `EMB512` (512-token embedding)

**Examples**:
- `EMB-BASELINE-GRANITE-EN-EMB512`: Baseline test, Granite English model
- `EMB-LATENCY-GRANITE-ML-EMB512`: Latency test, Granite Multilingual model

**Usage in Results**:
```text
results/embedding-models/
└── EMB-BASELINE-GRANITE-ML-EMB512/
    ├── sweep-inf.json
    ├── sweep-25pct.json
    ├── sweep-50pct.json
    └── sweep-75pct.json
```

## References

### Documentation
- [vLLM Benchmarking Documentation](https://docs.vllm.ai/en/latest/serving/benchmarking.html)
- [vLLM Embedding Models Guide](https://docs.vllm.ai/en/latest/models/embedding_models.html)
- [Ansible Documentation](https://docs.ansible.com/)

### Project Files
- [Model Matrix](model-matrix.yaml)
- [Test Scenarios](test-scenarios/)
- [Ansible Playbooks](../../automation/test-execution/ansible/playbooks/README.md)
- [Ansible Inventory](../../automation/test-execution/ansible/inventory/README.md)

### Related Guides
- [Main Testing Guide](../README.md)
- [LLM Performance Testing](../llm-models/README.md)
- [Performance Evaluation Guide PDF](../../docs/vllm-embedding-perf-eval-guide.pdf)

## Next Steps

1. **Configure Inventory**: Edit `ansible/inventory/hosts.yml` with your node IPs
2. **Run Initial Test**: Start with a single baseline test to validate setup
3. **Monitor Progress**: Use monitoring scripts to track test execution
4. **Analyze Results**: Generate reports from JSON results
5. **Tune Configuration**: Adjust core counts, NUMA settings based on results
6. **Scale Testing**: Run core sweeps to find optimal configuration
7. **Compare Models**: Test multiple embedding models for comparison
8. **Generate Reports**: Use analysis scripts for visualizations
