# Getting Started

Complete guide to setting up and running your first vLLM performance tests.

> **📝 Note:** This is a simplified quick start guide. For the complete Ansible documentation including all playbooks, roles, and advanced configuration, see the [full Ansible automation guide](https://github.com/redhat-et/vllm-cpu-perf-eval/blob/main/automation/test-execution/ansible/ansible.md) in the repository.

## Overview

The vLLM CPU Performance Evaluation framework uses **Ansible** to automate:
- Platform setup and configuration
- vLLM server deployment
- Test execution with GuideLLM
- Results collection and analysis

## Prerequisites

### Control Machine (Where You Run Ansible)

```bash
# Install Ansible (if not already installed)
# On macOS
brew install ansible

# On Ubuntu/Debian
sudo apt update && sudo apt install -y ansible

# On RHEL/Fedora
sudo dnf install -y ansible

# Verify installation
ansible --version  # Should be 2.14+
```

### Test Hosts (DUT and Load Generator)

**Requirements:**
- **OS**: Ubuntu 22.04+, RHEL 9+, or Fedora 38+
- **SSH Access**: Password-less SSH from control machine
- **Sudo privileges**: Required for installation and setup
- **Python**: 3.8+ (usually pre-installed)
- **Network**: DUT port 8000 accessible from Load Generator

**Verify access:**
```bash
# Test SSH connectivity
ssh -i ~/.ssh/your-key.pem user@dut-hostname
ssh -i ~/.ssh/your-key.pem user@loadgen-hostname

# Test sudo access
ssh user@dut-hostname 'sudo whoami'  # Should return 'root'
```

> **Note:** Playbooks automatically install required software (Podman/Docker, vLLM, GuideLLM). No manual installation needed on remote hosts.

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/redhat-et/vllm-cpu-perf-eval.git
cd vllm-cpu-perf-eval/automation/test-execution/ansible
```

### 2. Configure Your Environment

**Option A: Environment Variables (Recommended)**

```bash
export DUT_HOSTNAME=your-dut-hostname.example.com
export LOADGEN_HOSTNAME=your-loadgen-hostname.example.com
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_SSH_KEY=~/.ssh/your-key.pem
export HF_TOKEN=hf_xxxxx  # Optional: for gated models like Llama
```

**Option B: Edit Inventory File**

Edit `inventory/hosts.yml` and update the hostname values (lines 63 and 73):

```yaml
dut:
  hosts:
    vllm-server:
      ansible_host: "192.168.1.10"  # Update this

load_generator:
  hosts:
    guidellm-client:
      ansible_host: "192.168.1.20"  # Update this
```

### 3. Test Connectivity

```bash
ansible -i inventory/hosts.yml all -m ping
```

Expected output:
```
vllm-server | SUCCESS => {"ping": "pong"}
guidellm-client | SUCCESS => {"ping": "pong"}
```

### 4. Run Your First Test

**Simple LLM test:**

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores=16"
```

**What this does:**
1. Deploys vLLM server on DUT with TinyLlama model
2. Configures for 16 CPU cores
3. Runs chat workload benchmark from Load Generator
4. Collects results to local machine

**Test takes:** ~15-20 minutes (includes vLLM startup and 10-minute test)

### 5. View Results

Results are automatically collected to your local machine:

```bash
# View JSON results
cat results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-*/benchmarks.json

# View CSV results (importable to spreadsheets)
cat results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-*/benchmarks.csv
```

## Common Test Scenarios

### Concurrent Load Testing

Test performance under increasing concurrent load:

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "requested_cores=32"
```

This runs all 3 testing phases:
- **Phase 1**: Baseline (fixed tokens, no caching)
- **Phase 2**: Realistic (variable tokens, no caching)
- **Phase 3**: Production (variable tokens, with caching)

See [3-Phase Testing Methodology](methodology/testing-phases) for details.

### Core Count Sweep

Test performance across different CPU core counts:

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "core_sweep_enabled=true" \
  -e "core_sweep_counts=[8,16,32,64]"
```

### Embedding Model Testing

```bash
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=ibm-granite/granite-embedding-278m-multilingual" \
  -e "scenario=baseline"
```

## Available Workload Types

| Workload | Input:Output | Use Case | Example |
|----------|--------------|----------|---------|
| `chat` | 512:512 | Interactive chat | Customer support bot |
| `rag` | 8192:512 | Long context RAG | Document Q&A |
| `code` | 1024:1024 | Code generation | GitHub Copilot-style |
| `summarization` | 2048:256 | Summarization | Article summaries |
| `reasoning` | 256:2048 | Long reasoning | Complex analysis |

See [Model Catalog](../models/models) for all supported models.

## Platform Setup

For deterministic benchmarking, configure your system:

```bash
ansible-playbook -i inventory/hosts.yml setup-platform.yml
```

This configures:
- CPU frequency governor
- Turbo boost settings
- NUMA balancing
- Hugepages
- Other performance-critical settings

See [Platform Setup Guide](platform-setup/x86/intel/deterministic-benchmarking) for details.

## Key Parameters

### Test Configuration

| Parameter | Description | Example |
|-----------|-------------|---------|
| `test_model` | Model to test | `meta-llama/Llama-3.2-1B-Instruct` |
| `workload_type` | Workload pattern | `chat`, `rag`, `code`, `summarization` |
| `requested_cores` | CPU cores to use | `16`, `32`, `64` |
| `vllm_caching_mode` | Caching mode | `baseline` (off), `production` (on) |

### Concurrent Testing

| Parameter | Description | Example |
|-----------|-------------|---------|
| `guidellm_profile` | Test profile | `concurrent`, `sweep`, `synchronous` |
| `guidellm_rate` | Concurrency levels | `[1,2,4,8,16,32]` |
| `guidellm_max_seconds` | Test duration | `600` (10 minutes) |

## Troubleshooting

### SSH Connection Issues

```bash
# Verify SSH key permissions
chmod 600 ~/.ssh/your-key.pem

# Test SSH manually
ssh -i ~/.ssh/your-key.pem user@hostname

# Check Ansible can connect
ansible -i inventory/hosts.yml all -m ping -vvv
```

### vLLM Server Issues

```bash
# Check vLLM logs on DUT
ssh user@dut-hostname "podman logs vllm-server"

# Check if port 8000 is accessible
nc -zv dut-hostname 8000
```

### Test Failures

```bash
# Run with verbose output
ansible-playbook -i inventory/hosts.yml <playbook.yml> -vv

# Check disk space
ansible -i inventory/hosts.yml all -m shell -a "df -h"

# Check Docker/Podman status
ansible -i inventory/hosts.yml all -m shell -a "podman ps -a"
```

## Next Steps

### Learn More
- **[Testing Methodology](methodology/overview)** - Understand the testing approach
- **[3-Phase Testing](methodology/testing-phases)** - Baseline, realistic, and production phases
- **[Metrics Guide](methodology/metrics)** - Understanding the metrics
- **[Test Suites](../tests/tests)** - Available test suites

### Run More Tests
- **[Concurrent Load Tests](../tests/concurrent-load/concurrent-load)** - P95 latency scaling
- **[Scalability Tests](../tests/scalability/scalability)** - Maximum throughput
- **[Embedding Models](../tests/embedding-models/embedding-models)** - Embedding performance

### Automation Details
For complete documentation on:
- All available playbooks
- Ansible roles and task structure
- Inventory configuration
- Filter plugins and custom modules
- Advanced usage patterns

See the [full Ansible automation documentation](https://github.com/redhat-et/vllm-cpu-perf-eval/blob/main/automation/test-execution/ansible/ansible.md).

## Support

- **Repository**: [GitHub](https://github.com/redhat-et/vllm-cpu-perf-eval)
- **Issues**: [Report Issues](https://github.com/redhat-et/vllm-cpu-perf-eval/issues)
- **Documentation**: Browse this site for comprehensive guides
