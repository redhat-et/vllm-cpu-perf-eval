---
layout: default
title: Ansible Test Execution
---

## Ansible Test Execution Guide

Automated testing framework for vLLM performance evaluation with NUMA-aware CPU
optimization.

> **📚 Complete Reference:** For full details on all playbooks, roles, and
> configuration options, see the [Ansible automation
> guide](https://github.com/redhat-et/vllm-cpu-perf-eval/blob/main/automation/test-execution/ansible/ansible.md)
> in the repository.

## Quick Start

### Prerequisites

**Control Machine (where you run Ansible):**

```bash
# Install Ansible
pip install ansible-core

# Navigate to ansible directory
cd automation/test-execution/ansible

# Install required collections
ansible-galaxy collection install -r requirements.yml
```

**Test Hosts (DUT and Load Generator):**

- OS: Ubuntu 22.04+, RHEL 9+, or Fedora 38+
- SSH access with sudo privileges
- Python 3.8+

### Run Your First Test

```bash
# Simple LLM benchmark
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"
```

## Available Playbooks

### LLM Testing

| Playbook | Purpose | Configuration |
|----------|---------|---------------|
| `llm-benchmark-auto.yml` | Single LLM test | Auto (core count) |
| `llm-benchmark-concurrent-load.yml` | 3-phase concurrent load test | Auto |
| `llm-core-sweep-auto.yml` | Multi-core sweep | Auto |

### Platform Setup

| Playbook | Purpose |
|----------|---------|
| `setup-platform.yml` | Install packages, configure performance settings |
| `health-check.yml` | Verify system readiness |

## Test Configuration

### Basic Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `test_model` | HuggingFace model ID | `meta-llama/Llama-3.2-1B-Instruct` |
| `workload_type` | Test workload | `chat`, `code`, `summarization` |
| `requested_cores` | CPU cores for vLLM | `16`, `32`, `64` |

### Optional Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `requested_tensor_parallel` | Tensor parallelism | Auto-calculated |
| `guidellm_profile` | Benchmark profile | `concurrent` |
| `guidellm_rate` | Concurrency levels | `[1,2,4,8,16,32]` |
| `guidellm_max_seconds` | Test duration (seconds) | `600` |

## Advanced Features

### Socket Pinning (NUMA Affinity)

Socket pinning isolates vLLM server and GuideLLM load generator to different
CPU sockets/NUMA nodes, minimizing performance interference.

**Supported Playbooks:**

- ✅ `llm-benchmark-auto.yml`
- ✅ `llm-benchmark-concurrent-load.yml`

**Parameters:**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `vllm_cpu_start` | CPU ID to start vLLM allocation | `64` (socket 1) |
| `vllm_numa_node` | NUMA node for vLLM | `1` |
| `guidellm_cpus` | CPU range for load generator | `"0-31"` |
| `guidellm_numa_node` | NUMA node for load generator | `0` |

**Determine System Socket Layout:**

```bash
# Show NUMA topology
lscpu | grep NUMA

# Show cores per NUMA node
numactl --hardware

# Example output:
# node 0 cpus: 0 1 2 ... 31
# node 1 cpus: 64 65 66 ... 95
```

**Example: vLLM on Socket 1, GuideLLM on Socket 0**

Assuming 2-socket system:

- Socket 0: Cores 0-31 (NUMA node 0)
- Socket 1: Cores 64-95 (NUMA node 1)

```bash
# Single test with socket separation
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=32" \
  -e "vllm_cpu_start=64" \
  -e "vllm_numa_node=1" \
  -e "guidellm_cpus=0-31" \
  -e "guidellm_numa_node=0"
```

```bash
# Concurrent load test with socket separation
ansible-playbook llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "requested_cores=32" \
  -e "vllm_cpu_start=64" \
  -e "vllm_numa_node=1" \
  -e "guidellm_cpus=0-31" \
  -e "guidellm_numa_node=0"
```

**Validation:**

```bash
# Verify vLLM container pinning
podman ps | grep vllm
podman inspect <container-id> | grep -A 2 cpuset
# Expected: "CpusetCpus": "64-95", "CpusetMems": "1"

# Verify GuideLLM container pinning
podman ps | grep guidellm
podman inspect <container-id> | grep -A 2 cpuset
# Expected: "CpusetCpus": "0-31", "CpusetMems": "0"
```

**Use Cases:**

- **Minimize Interference**: Eliminate CPU contention between server and load
  generator
- **Test Cross-NUMA Performance**: Measure impact of cross-socket memory access
- **Multi-Tenant Systems**: Isolate benchmarks from other workloads

**Notes:**

- Socket pinning requires `vllm_numa_node` to be set
- When pinning to single NUMA node, `tensor_parallel` must equal 1
- The automation validates requested cores fit within specified socket

### 3-Phase Concurrent Load Testing

The concurrent load test runs three phases to evaluate different scenarios:

**Phase 1: Baseline (Fixed Tokens, No Caching)**

- Fixed input/output token counts
- Prefix caching disabled
- Establishes baseline performance

**Phase 2: Realistic (Variable Tokens, No Caching)**

- Variable token counts (realistic traffic)
- Prefix caching disabled
- Tests production-like variability

**Phase 3: Production (Variable Tokens, With Caching)**

- Variable token counts
- Prefix caching enabled
- Tests production configuration

**Example:**

```bash
# Run all 3 phases
ansible-playbook llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "requested_cores=32"

# Run only Phase 1 (baseline)
ansible-playbook llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "requested_cores=16" \
  -e "skip_phase_2=true" \
  -e "skip_phase_3=true"
```

## Results

Test results are saved to `results/llm/<model>/<test-run-id>/`:

```text
results/llm/meta-llama__Llama-3.2-1B-Instruct/20240428-120000/
├── benchmarks.json          # GuideLLM benchmark results
├── benchmarks.csv           # CSV format
├── test-metadata.json       # Test configuration
├── vllm-metrics.log         # vLLM server metrics
└── guidellm.log             # Load generator logs
```

## Workload Types

### Baseline Workloads (Fixed Tokens)

| Workload | Input Tokens | Output Tokens | Use Case |
|----------|--------------|---------------|----------|
| `chat` | 1024 | 256 | Conversational AI |
| `code` | 1024 | 512 | Code generation |
| `summarization` | 2048 | 256 | Document summarization |
| `rag` | 2048 | 512 | RAG applications |

### Variable Workloads (Realistic Traffic)

| Workload | Token Range | Use Case |
|----------|-------------|----------|
| `chat_var` | ISL: 256-2048, OSL: 64-512 | Production chat |
| `code_var` | ISL: 512-2048, OSL: 128-1024 | Production code gen |
| `summarization_var` | ISL: 1024-4096, OSL: 64-512 | Production summarization |

## Troubleshooting

### Connection Issues

```bash
# Test SSH connectivity
ansible -i inventory/hosts.yml all -m ping

# Verbose output
ansible -i inventory/hosts.yml all -m ping -vvv
```

### vLLM Won't Start

```bash
# Check container logs
podman logs <container-id>

# Check if port is in use
ss -tlnp | grep 8000
```

### HuggingFace Token

For gated models (Llama, Mistral):

```bash
# Set token as environment variable
export HF_TOKEN=your_token_here

# Or configure in inventory
vim inventory/group_vars/all/credentials.yml
```

## Next Steps

- [Understanding Metrics](../methodology/metrics.md) - Metrics definitions
- [Platform Setup](../platform-setup/x86/intel/deterministic-benchmarking.md) -
  Intel Xeon tuning
- [Complete Ansible Guide](https://github.com/redhat-et/vllm-cpu-perf-eval/blob/main/automation/test-execution/ansible/ansible.md) -
  Full reference

## Reference

- [Ansible Documentation](https://docs.ansible.com/)
- [GuideLLM](https://github.com/vllm-project/guidellm)
- [vLLM](https://github.com/vllm-project/vllm)
