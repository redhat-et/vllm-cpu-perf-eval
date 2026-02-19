# Embedding Tests Setup Summary

Complete setup for embedding model performance testing with two-node
architecture.

## What Was Created

### 1. Test Documentation

#### [README.md](README.md)

Complete documentation based on the PDF guide covering:

- Test methodology and scenarios
- Models under test (granite-embedding-english-r2,
  granite-embedding-278m-multilingual)
- Performance metrics (RPS, P95/P99 latency)
- Configuration details
- Results format and analysis

#### [QUICKSTART.md](QUICKSTART.md)

Quick reference guide with:

- Two-node architecture overview
- Ansible and bash script usage examples
- Monitoring and debugging commands
- Common workflows
- Troubleshooting guide

### 2. Test Scenarios

#### [baseline-sweep.yaml](baseline-sweep.yaml)

Baseline performance test configuration:

- Find maximum throughput (`--request-rate inf`)
- Test at 25%, 50%, 75% of max load
- Measures request throughput and latency curves

#### [latency-concurrent.yaml](latency-concurrent.yaml)

Latency scaling test configuration:

- Concurrency levels: 16, 32, 64, 128, 196
- Measures P99 latency under load
- Identifies sweet spot and degradation point

### 3. Model Matrix

#### [model-matrix.yaml](../../models/embedding-models/model-matrix.yaml)

Defines models and test mappings:

- Test case IDs (EMB-BASELINE-*, EMB-LATENCY-*)
- Model definitions and architectures
- Test parameters and configurations
- Results structure

### 4. Ansible Automation

#### Directory Structure

```text
automation/test-execution/ansible/
├── inventory/
│   └── embedding-hosts.yml          # Two-node inventory
├── playbooks/
│   ├── embedding/                   # Embedding-specific playbooks
│   │   ├── run-tests.yml           # Main test execution
│   │   ├── run-core-sweep.yml      # Core count performance sweep
│   │   └── tasks/                  # Reusable task files
│   │       ├── baseline.yml        # Baseline test tasks
│   │       ├── latency.yml         # Latency test tasks
│   │       └── core-iteration.yml  # Core sweep iteration
│   ├── common/                      # Shared playbooks
│   │   ├── start-vllm-server.yml   # Start vLLM on DUT
│   │   ├── health-check.yml        # Wait for vLLM ready
│   │   └── collect-logs.yml        # Collect logs and results
│   └── README.md                    # Playbook documentation
└── roles/                           # Future: Ansible roles
```

#### Key Features

- **Two-node orchestration**: DUT (vLLM server) + Load Generator
  (vllm bench serve)
- **Containerized vLLM**: Podman/Docker with CPU pinning support
- **Core count sweep**: Test vLLM with varying CPU allocations (8,
  16, 32, 64 cores)
- **Health checks**: Wait for vLLM to be ready before running tests
- **Automatic log collection**: Fetch logs and results to
  controller

### 5. Bash Scripts

#### [automation/test-execution/bash/embedding/](../../automation/test-execution/bash/embedding/)

**run-baseline.sh**: Run baseline performance sweep test

- Find max RPS with `--request-rate inf`
- Test at 25%, 50%, 75% load levels
- Supports remote vLLM via `--vllm-host`

**run-latency.sh**: Run latency scaling test

- Test concurrency levels: 16, 32, 64, 128, 196
- Display real-time metrics
- Quick analysis summary table

**run-all.sh**: Run complete test suite

- Execute baseline and latency tests
- Support multiple models
- Integrated with remote vLLM

### 6. Utilities

#### [automation/utilities/health-checks/](../../automation/utilities/health-checks/)

**check-vllm.sh**: Health check script

- Wait for vLLM /health endpoint
- Verify models endpoint
- Configurable timeout and interval
- Verbose mode for debugging

#### [automation/utilities/log-monitoring/](../../automation/utilities/log-monitoring/)

**monitor-vllm-logs.sh**: Monitor vLLM container logs

- Local or remote (SSH) monitoring
- Follow logs in real-time
- Support for both podman and docker

**monitor-test-progress.sh**: Monitor test execution

- Track test completion
- Display real-time metrics
- Show active processes
- Works with local or remote load generator

## Architecture

### Two-Node Setup

```text
┌─────────────────────────────────┐          ┌─────────────────────────────────┐
│  Load Generator                 │          │    DUT (Device Under Test)      │
│  (192.168.1.20)                 │◄────────►│    (192.168.1.10)               │
│                                 │ network  │                                 │
│  ┌───────────────────────────┐  │          │  ┌───────────────────────────┐  │
│  │  vllm bench serve         │  │          │  │  vLLM Container           │  │
│  │  --host 192.168.1.10      │  │          │  │  (Podman/Docker)          │  │
│  │  --backend openai-embed   │  │          │  │                           │  │
│  └───────────────────────────┘  │          │  │  --model <model>          │  │
│                                 │          │  │  --port 8000              │  │
│  Results: /var/tmp/results      │          │  │  --dtype bfloat16         │  │
│                                 │          │  │  CPU Pinning: 0-63        │  │
│                                 │          │  └───────────────────────────┘  │
│                                 │          │                                 │
│                                 │          │  Logs: /var/log/vllm-*          │
└─────────────────────────────────┘          └─────────────────────────────────┘
```

### Workflow

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

## Quick Start Examples

### Example 1: Single Model Baseline Test (Ansible)

```bash
cd automation/test-execution/ansible

ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=baseline" \
  -e "test_model=ibm-granite/granite-embedding-278m-multilingual"
```

### Example 2: Core Count Sweep (Ansible)

```bash
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/embedding-hosts.yml \
  -e "test_core_counts=[8,16,32,64]" \
  -e "scenario=baseline"
```

### Example 3: Manual Test with Bash Scripts

```bash
# On DUT (192.168.1.10): Start vLLM
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

# On Load Generator (192.168.1.20): Run tests
export VLLM_HOST=192.168.1.10
cd automation/test-execution/bash/embedding
./run-baseline.sh \
ibm-granite/granite-embedding-278m-multilingual
./run-latency.sh \
ibm-granite/granite-embedding-278m-multilingual
```

## Results Structure

```text
results/
├── embedding-models/
│   ├── granite-embedding-278m-multilingual/
│   │   ├── baseline/
│   │   │   ├── sweep-inf.json
│   │   │   ├── sweep-25pct.json
│   │   │   ├── sweep-50pct.json
│   │   │   └── sweep-75pct.json
│   │   └── latency/
│   │       ├── concurrent-16.json
│   │       ├── concurrent-32.json
│   │       ├── concurrent-64.json
│   │       ├── concurrent-128.json
│   │       └── concurrent-196.json
│   └── core-sweep-20260218-143022/
│       ├── 8cores/
│       ├── 16cores/
│       ├── 32cores/
│       └── 64cores/
└── logs/
    ├── embedding-dut-01/
    │   ├── vllm-server-*.log
    │   └── system-metrics-*.log
    └── embedding-loadgen-01/
```

## Test Metrics

### Primary Metrics

- **Request throughput (req/s)**: Total requests processed per second
- **Total Token throughput (tok/s)**: Input tokens processed per second
- **Mean E2EL (ms)**: Average end-to-end latency
- **P95 E2EL (ms)**: 95th percentile latency
- **P99 E2EL (ms)**: 99th percentile latency (primary metric)

### System Metrics

- **vLLM Process CPU Utilization (%)**: CPU usage
- **Memory Utilization (GB)**: RAM consumption

## Configuration Parameters

### Test Parameters

- **Input Sequence Length**: 512 tokens
- **Output Sequence Length**: 1 token
- **Num Prompts**: 1000
- **Dtype**: bfloat16
- **KV Cache**: 1GiB (minimal for embedding models)

### Hardware Configuration

- **Cores**: Vendor-defined (8-64 typical)
- **NUMA nodes**: Vendor-defined
- **Hyperthreading**: Platform-dependent
- **Frequency**: Performance governor recommended

## Monitoring During Tests

### Terminal 1: DUT vLLM Logs
```bash
automation/utilities/log-monitoring/monitor-vllm-logs.sh \
  --mode remote \
  --remote-host 192.168.1.10 \
  --follow
```

### Terminal 2: Load Generator Progress
```bash
automation/utilities/log-monitoring/monitor-test-progress.sh \
  --mode remote \
  --remote-host 192.168.1.20 \
  --refresh 5
```

### Terminal 3: Health Check
```bash
automation/utilities/health-checks/check-vllm.sh \
  --host 192.168.1.10 \
  --verbose
```

## Next Steps

1. **Configure Inventory**: Edit
   `ansible/inventory/embedding-hosts.yml` with your IPs
2. **Run Test**: Start with a single baseline test
3. **Monitor**: Use monitoring scripts to track progress
4. **Analyze Results**: Generate reports from JSON results
5. **Tune**: Adjust core counts, NUMA settings based on results
6. **Scale**: Run core sweeps to find optimal configuration

## References

- [Full Documentation](README.md)
- [Quick Start Guide](QUICKSTART.md)
- [Ansible Playbooks README](../../automation/test-execution/ansible/playbooks/README.md)
- [Model Matrix](model-matrix.yaml)
- [Test Scenarios](.)
