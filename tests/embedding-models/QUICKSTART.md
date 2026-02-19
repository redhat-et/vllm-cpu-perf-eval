# Embedding Tests Quick Start

Quick reference for running embedding model performance tests.

## Prerequisites

```bash
# Ensure vLLM >= v0.11.0
pip install "vllm>=0.11.0"

# For Ansible automation
pip install ansible
ansible-galaxy collection install containers.podman
```

## Two-Node Architecture

```text
┌─────────────────────┐          ┌─────────────────────┐
│  Load Generator     │          │    DUT (SUT)        │
│  (192.168.1.20)     │◄────────►│  (192.168.1.10)     │
│                     │  network │                     │
│  vllm bench serve   │          │    vllm (podman)    │
│  --host <dut-ip>    │          │    --port 8000      │
└─────────────────────┘          └─────────────────────┘
```

## Quick Start - Ansible (Recommended for Production)

### 1. Configure Inventory

Edit `automation/test-execution/ansible/inventory/embedding-hosts.yml`:

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

### 2. Run Tests

```bash
cd automation/test-execution/ansible

# Run all embedding tests
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml

# Run baseline test only
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=baseline"

# Run latency test only
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=latency"

# Test specific model
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "test_model=ibm-granite/granite-embedding-english-r2"

# Keep vLLM running after tests
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "cleanup_after_test=false"
```

### 3. Run Core Count Sweep

Test vLLM with different CPU allocations:

```bash
# Test with 8, 16, 32, 64 cores
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/embedding-hosts.yml \
  -e "test_core_counts=[8,16,32,64]"

# Baseline test across core counts
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=baseline" \
  -e "test_core_counts=[16,32,48,64]"

# Full core sweep with latency tests
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=latency" \
  -e "test_core_counts=[8,16,24,32,40,48,56,64]"
```

## Quick Start - Bash Scripts

### 1. Start vLLM on DUT

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

### 2. Run Tests from Load Generator

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

## Results Location

```text
# Bash script results
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
│       └── ...

# Ansible results
results/embedding-models/
└── core-sweep-20260218-143022/
    ├── 8cores/
    ├── 16cores/
    ├── 32cores/
    └── 64cores/
```

## Viewing Results

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

## Common Workflows

### Workflow 1: Single Model Baseline Test

```bash
# 1. Start vLLM on DUT
ssh dut-node "podman run -d --name vllm ... [see above]"

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
  -i inventory/embedding-hosts.yml \
  -e "test_core_counts=[8,16,24,32,40,48,56,64]" \
  -e "scenario=baseline"

# Results in: results/embedding-models/core-sweep-<timestamp>/
```

### Workflow 3: Full Model Comparison

```bash
# Test multiple models across both test types
for model in \
  "ibm-granite/granite-embedding-english-r2" \
  "ibm-granite/granite-embedding-278m-multilingual" \
  "Salesforce/slate-125m-english-rtrvr-v2"; do

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
```

### Connection refused from load generator

```bash
# Check network connectivity
ping <dut-ip>

# Check port is open
nc -zv <dut-ip> 8000

# Check firewall
ssh <dut-ip> "firewall-cmd --list-all"
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

## Next Steps

1. **Analyze Results**: See
   [README.md](README.md#analysis-and-reporting)
2. **Generate Reports**: Use analysis scripts in
   `automation/analysis/`
3. **Tune Performance**: Adjust core counts, NUMA settings, OMP threads
4. **Scale Testing**: Add more DUT nodes for distributed testing

## References

- [Full Documentation](README.md)
- [Test Scenarios](scenarios/)
- [Model Matrix](../../models/embedding-models/model-matrix.yaml)
- [Ansible Inventory](../../automation/test-execution/ansible/inventory/embedding-hosts.yml)
