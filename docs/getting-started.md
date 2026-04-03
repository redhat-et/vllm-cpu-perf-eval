---
layout: default
title: Getting Started
---

## Getting Started

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

The control machine is your local laptop/workstation where you run Ansible commands.

**Install Ansible:**
```bash
# On macOS
brew install ansible

# On Ubuntu/Debian
sudo apt update && sudo apt install -y ansible

# On RHEL/Fedora
sudo dnf install -y ansible

# Verify installation
ansible --version  # Should be 2.14+

# Navigate to the ansible directory
cd automation/test-execution/ansible

# Install required Ansible collections
ansible-galaxy collection install -r requirements.yml

# Or install individually
ansible-galaxy collection install containers.podman ansible.posix
```

### Test Hosts (DUT and Load Generator)

**Requirements:**
- **OS**: Ubuntu 22.04+, RHEL 9+, or Fedora 38+
- **SSH Access**: Password-less SSH from control machine (see setup below)
- **Sudo privileges**: Required for installation and setup
- **Python**: 3.8+ (usually pre-installed)
- **Network**: DUT port 8000 accessible from Load Generator

> **Note:** Playbooks automatically install required software (Podman, tuned, numactl, vLLM, GuideLLM) on remote hosts. No manual installation needed.

### SSH Setup

**Set up password-less SSH access from your control machine to both DUT and Load Generator:**

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -C "your-email@example.com"

# Copy SSH key to DUT
ssh-copy-id -i ~/.ssh/id_ed25519.pub ec2-user@your-dut-hostname

# Copy SSH key to Load Generator
ssh-copy-id -i ~/.ssh/id_ed25519.pub ec2-user@your-loadgen-hostname

# Test connectivity (should not prompt for password)
ssh -i ~/.ssh/id_ed25519 ec2-user@your-dut-hostname 'echo "DUT: Connected"'
ssh -i ~/.ssh/id_ed25519 ec2-user@your-loadgen-hostname 'echo "LoadGen: Connected"'

# Test sudo access (required for playbooks)
ssh ec2-user@your-dut-hostname 'sudo whoami'  # Should return 'root'
ssh ec2-user@your-loadgen-hostname 'sudo whoami'  # Should return 'root'
```

**For AWS EC2:**
```bash
# Use your downloaded .pem key
chmod 400 ~/your-key.pem  # Set correct permissions
ssh -i ~/your-key.pem ec2-user@your-dut-hostname

# Or convert to standard SSH key format
ssh-keygen -p -m PEM -f ~/your-key.pem
```

### HuggingFace Token (For Gated Models)

Some models like Llama require a HuggingFace token and license acceptance.

**Create a HuggingFace token:**

1. **Sign up/Login**: Visit [huggingface.co](https://huggingface.co)
2. **Create token**: Go to Settings → Access Tokens → New Token
3. **Set permissions**: Select "Read" access
4. **Copy token**: Save it as `hf_xxxxxxxxxxxxx`
5. **Accept model licenses**: Visit model page (e.g., [meta-llama/Llama-3.2-1B-Instruct](https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct)) and accept license

**Save token locally:**
```bash
# Save to file
echo "hf_xxxxxxxxxxxxx" > ~/hf-token

# Or export directly
export HF_TOKEN=hf_xxxxxxxxxxxxx

# Or load from file
export HF_TOKEN=$(cat ~/hf-token)
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/redhat-et/vllm-cpu-perf-eval.git
cd vllm-cpu-perf-eval/automation/test-execution/ansible
```

### 2. Configure Your Environment

**Option A: Environment Variables (Recommended)**

```bash
# Set hostnames (AWS example)
export DUT_HOSTNAME=ec2-18-117-90-80.us-east-2.compute.amazonaws.com
export LOADGEN_HOSTNAME=ec2-52-15-123-132.us-east-2.compute.amazonaws.com

# SSH credentials
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_PRIVATE_KEY_FILE=~/your-key.pem  # Or ~/.ssh/id_ed25519

# Ensure SSH key has correct permissions
chmod 600 ~/your-key.pem

# HuggingFace token (for gated models like Llama)
export HF_TOKEN=$(cat ~/hf-token)
```

The inventory file automatically uses these environment variables with sensible defaults.

**Option B: Edit Inventory File**

Alternatively, edit `inventory/hosts.yml` directly and update the hostname values (lines 63 and 73):

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

### 4. Platform Setup (Optional but Recommended)

Configure your **DUT and Load Generator** hosts with performance optimizations for deterministic benchmarking:

```bash
# Configure both DUT and Load Generator
ansible-playbook -i inventory/hosts.yml setup-platform.yml

# Or configure only specific hosts
ansible-playbook -i inventory/hosts.yml setup-platform.yml --limit dut
ansible-playbook -i inventory/hosts.yml setup-platform.yml --limit load_generator

# Reboot hosts for kernel parameters to take effect
ansible -i inventory/hosts.yml all -b -m reboot
```

**What this configures (on DUT and Load Generator only):**
- ✅ **Installs**: Podman, tuned, kernel-tools, numactl
- ✅ **CPU Isolation**: Sets isolcpus, nohz_full, rcu_nocbs
- ✅ **Performance Governor**: Locks CPU frequency
- ✅ **NUMA Topology**: Detects and optimizes for NUMA layout
- ✅ **IRQ Balancing**: Disables irqbalance
- ✅ **Systemd Pinning**: Pins system processes to housekeeping CPUs

**What it does NOT configure:**
- ❌ Your control machine (Ansible host) - no changes needed there
- ❌ vLLM or GuideLLM - those are installed during test execution

> **Note:** You can skip this step if you're just trying out the framework. It's mainly for production-grade deterministic benchmarking. See [Platform Setup Guide](platform-setup/x86/intel/deterministic-benchmarking) for details.

### 5. Run Your First Test

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

### 6. View Results

Results are automatically collected to your local machine:

```bash
# View JSON results
cat results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-*/benchmarks.json

# View CSV results (importable to spreadsheets)
cat results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-*/benchmarks.csv
```

## Common Test Scenarios

### Testing Against External Endpoints

Test existing vLLM deployments (cloud, K8s, production) without managing containers:

```bash
# Configure external endpoint
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-vllm-instance:8000

# Run concurrent load test (model auto-detected from endpoint)
ansible-playbook -i inventory/hosts.yml llm-benchmark-concurrent-load.yml \
  -e "base_workload=chat" \
  -e "requested_cores=16"
```

**Features:**
- ✅ Auto-detects model from endpoint `/v1/models`
- ✅ Skips vLLM container management
- ✅ Collects client metrics (GuideLLM)
- ✅ Collects server metrics if `/metrics` exposed
- ✅ Works with cloud, K8s, or on-premise deployments

**Environment Variables:**
- `VLLM_ENDPOINT_MODE=external` - Enable external mode
- `VLLM_ENDPOINT_URL=http://...` - Full URL with protocol and port
- `LOADGEN_HOSTNAME=...` - Load generator hostname/IP
- `ANSIBLE_SSH_KEY=...` - SSH key for load generator access

**Note:** `DUT_HOSTNAME` not required in external mode (endpoint accessed directly via HTTP).

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
