# vLLM Performance Testing - Ansible Automation

Automated testing framework for vLLM embedding and LLM generative
models with NUMA-aware CPU optimization.

## Quick Start

### 1. Configure Inventory

Edit [inventory/hosts.yml](inventory/hosts.yml) - **only change the
IP addresses** (see [inventory documentation](inventory/inventory.md) for details):

```yaml
dut:
  hosts:
    my-dut:
      ansible_host: 192.168.1.10              # ⚠️ YOUR DUT IP
      ansible_user: ec2-user                  # ⚠️ YOUR SSH USER
      ansible_ssh_private_key_file: ~/.ssh/your-key.pem

load_generator:
  hosts:
    my-loadgen:
      ansible_host: 192.168.1.20              # ⚠️ YOUR LOAD GEN IP
      ansible_user: ec2-user
      ansible_ssh_private_key_file: ~/.ssh/your-key.pem
      bench_config:
        vllm_host: 192.168.1.10               # ⚠️ MUST MATCH DUT IP
```

Everything else is pre-configured!

### 2. Test Connectivity

```bash
ansible -i inventory/hosts.yml all -m ping
```

### 3. Run a Test

```bash
# Set HuggingFace token
export HF_TOKEN=hf_xxxxx

# Run auto-configured test (easiest)
ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores=16"
```

Done!

## Architecture

```text
┌─────────────────┐         ┌──────────────────┐
│  Load Generator │◄───────►│       DUT        │
│                 │  HTTP   │                  │
│  - GuideLLM     │  :8000  │  - vLLM Server   │
│  - vllm bench   │         │  - Containerized │
└─────────────────┘         └──────────────────┘
```

**Two-node architecture:**

- **DUT** (Device Under Test): Runs vLLM server in container
- **Load Generator**: Runs benchmarking tools (GuideLLM, vllm bench
  serve)

## Configuration Approaches

### Auto-Configuration (Recommended for Exploration)

**You provide**: Number of cores (single value or list)

**Ansible handles**: NUMA detection, CPU allocation, configuration

#### Single Core Count

```bash
ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores=32"  # Just specify how many cores!
```

**What happens:**

1. Detects NUMA topology on DUT
2. Allocates 32 cores from vLLM NUMA node
3. Generates config: `32cores-auto-numa<X>`
4. Runs test

#### Multiple Core Counts (Core Sweep)

```bash
ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-core-sweep-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores_list=[8,16,24,32]"
# Test multiple core counts!
```

**What happens:**

1. Detects NUMA topology once
2. For **each** core count (8, 16, 24, 32):
   - Allocates cores from topology
   - Generates unique config name
   - Clean restart vLLM
   - Runs test
   - Collects results
3. All results organized by core count

### Manual Configuration (Recommended for Production)

**You provide**: Pre-defined configuration name

**Uses**: Exact cpuset/NUMA settings from inventory

```bash
ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_name=32cores-single-socket"
```

**When to use each:**

- **Auto**: Quick testing, exploration, unknown hardware
- **Manual**: Production benchmarks, exact reproducibility, documented
  configs

## Available Playbooks

### LLM Testing

| Playbook | Purpose | Usage |
|----------|---------|-------|
| [run-guidellm-test-auto.yml](playbooks/llm/run-guidellm-test-auto.yml) | Single test, auto cores | `-e "requested_cores=16"` |
| [run-guidellm-test.yml](playbooks/llm/run-guidellm-test.yml) | Single test, manual config | `-e "core_config_name=..."` |
| [run-core-sweep-auto.yml](playbooks/llm/run-core-sweep-auto.yml) | Test multiple core counts | `-e "requested_cores_list=[8,16,32]"` |
| [run-core-sweep.yml](playbooks/llm/run-core-sweep.yml) | Test multiple configs | `-e "core_config_names=[...]"` |

### Platform Setup

| Playbook | Purpose | When |
|----------|---------|------|
| [setup-platform.yml](playbooks/common/setup-platform.yml) | Configure DUT/LoadGen for optimal performance | One-time, before testing |


## Workload Types

Pre-configured in [inventory/hosts.yml](inventory/hosts.yml):

| Workload | ISL:OSL | Use Case | vLLM Args |
|----------|---------|----------|-----------|
| `embedding` | 512:1 | Embedding models | `--dtype=bfloat16 --max-model-len=512` |
| `summarization` | 1024:256 | Text summarization | `--dtype=bfloat16 --no_enable_prefix_caching` |
| `chat` | 512:128 | Chatbots | `--dtype=bfloat16 --no_enable_prefix_caching` |
| `code` | 2048:512 | Code generation | `--dtype=bfloat16 --no_enable_prefix_caching` |
| `rag` | 4096:256 | RAG applications | `--dtype=bfloat16 --no_enable_prefix_caching` |


## Common Tasks

### Run Platform Setup (One-Time)

```bash
# Configure CPU isolation, tuned profile, systemd pinning
ansible-playbook -i inventory/hosts.yml \
  playbooks/common/setup-platform.yml

# Reboot required
ansible -i inventory/hosts.yml all -b -m reboot

# Validate after reboot
ansible -i inventory/hosts.yml dut -b -a "tuned-adm active"
```

### Run Core Sweep

Test multiple core counts:

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-core-sweep-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores_list=[8,16,32,64]"
```

### Test Multiple Models

```bash
export HF_TOKEN=hf_xxxxx

for model in \
  "meta-llama/Llama-3.2-1B-Instruct" \
  "meta-llama/Llama-3.2-3B-Instruct"; do

  ansible-playbook -i inventory/hosts.yml \
    playbooks/llm/run-guidellm-test-auto.yml \
    -e "test_model=$model" \
    -e "workload_type=summarization" \
    -e "requested_cores=16"
done
```

## Results

Results are organized by model and workload:

```
results/llm/
├── Llama-3.2-1B-Instruct/
│   ├── summarization-20260219-143022/
│   │   ├── 16cores-auto-numa1/
│   │   │   ├── test-metadata.json
│   │   │   ├── guidellm-report.html
│   │   │   ├── guidellm-results.json
│   │   │   └── guidellm-results.csv
│   │   └── 32cores-auto-numa1/
│   └── chat-20260219-150033/
└── Llama-3.2-3B-Instruct/
```

## NUMA Detection

The automation automatically detects NUMA topology and allocates CPUs:

```
Detected NUMA Topology:
  NUMA nodes: [0, 1, 2]
  Node count: 3

Node Allocation Strategy:
  Housekeeping: node 0 (all CPUs for system tasks)
  GuideLLM: node 1 (primary CPUs only)
  vLLM: node 2 (primary CPUs only)

NUMA Topology Detection Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Housekeeping: node 0, CPUs 0-31
GuideLLM: node 1, CPUs 32-63
vLLM: node 2, CPUs 64-95
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Key concepts:**

- **Housekeeping**: System tasks (uses all CPUs including SMT)
- **GuideLLM/vLLM**: Workload tasks (uses primary CPUs only, skip SMT
  siblings)
- **Container cpuset**: Container CPU boundary (REQUIRED)
- **vLLM OMP**: Optional threading tuning (omit for auto-configuration)

## Custom Configurations

### Add Custom Workload

Edit [inventory/hosts.yml](inventory/hosts.yml):

```yaml
test_configs:
  my_custom_workload:
    workload_type: "summarization"
    isl: 2048
    osl: 512
    backend: "openai-completions"
    vllm_args:
      - "--dtype=bfloat16"
      - "--no_enable_prefix_caching"
      - "--my-custom-flag"
    kv_cache_space: "50GiB"
```

### Add Custom Core Config

Edit [inventory/hosts.yml](inventory/hosts.yml):

```yaml
core_configs:
  - name: "my-24cores"
    cores: 24
    cpuset_cpus: "0-23"
    cpuset_mems: "0"
    tensor_parallel: 1
```

## Troubleshooting

### Connection Issues

```bash
# Test SSH manually
ssh -i ~/.ssh/your-key.pem ec2-user@<DUT_IP>

# Check key permissions
chmod 600 ~/.ssh/your-key.pem

# Verbose Ansible output
ansible -i inventory/hosts.yml all -m ping -vvv
```

### HuggingFace Token

```bash
# Verify token is set
echo $HF_TOKEN

# Test token works
huggingface-cli whoami
```

### vLLM Won't Start

```bash
# Check vLLM logs on DUT
ssh <DUT_IP> "podman logs vllm-server"

# Common issues:
# - Out of memory: Reduce kv_cache_space in inventory
# - Model not found: Check HF_TOKEN
# - Port in use: Check no other vLLM running
```

### NUMA Detection Fails

```bash
# Check lscpu on DUT
ssh <DUT_IP> lscpu -e=CPU,NODE,CORE

# If single NUMA node, use manual configs instead of auto
```

## Directory Structure

```text
automation/test-execution/ansible/
├── inventory/
│   ├── hosts.yml          # Main inventory - edit IPs here
│   └── README.md          # Inventory documentation
├── playbooks/
│   ├── common/            # Shared tasks
│   │   ├── setup-platform.yml
│   │   └── tasks/
│   │       ├── detect-numa-topology.yml
│   │       ├── allocate-cores-from-count.yml
│   │       ├── setup-hf-token.yml
│   │       └── clean-restart-vllm.yml
│   ├── llm/               # LLM generative model testing
│   │   ├── run-guidellm-test-auto.yml
│   │   ├── run-guidellm-test.yml
│   │   ├── run-core-sweep-auto.yml
│   │   ├── run-core-sweep.yml
│   │   └── tasks/
│   │       ├── start-llm-vllm.yml
│   │       ├── run-guidellm.yml
│   │       └── core-sweep-*.yml
│   └── embedding/         # Embedding model testing
├── filter_plugins/        # Custom Jinja2 filters
│   ├── cpu_utils.py       # CPU topology filters
│   └── test_cpu_utils.py  # Unit tests
└── README.md             # This file
```

## Key Features

- **Auto NUMA detection** - Discovers and allocates CPUs
  intelligently
- **Custom Jinja2 filters** - Native Python (no shell/awk scripts)
- **Clean restarts** - Fresh vLLM state between tests
- **Secure HF tokens** - Multiple methods (env, file, vault, prompt)
- **Container isolation** - Podman/Docker with CPU/NUMA pinning
- **Platform tuning** - CPU isolation, tuned profiles, systemd
  pinning
- **Comprehensive testing** - Unit tests for all filters
- **Single inventory** - Just edit IPs and run

## Performance

**NUMA detection**: <1 second (was ~10s with shell scripts)

**50x faster** than previous awk/shell implementation

**100+ unit tests** - All custom filters validated

## References

- [Inventory README](inventory/inventory.md) - Detailed inventory guide
- [LLM Playbooks](playbooks/llm/llm.md) - LLM testing details
- [Filter Plugins](filter_plugins/filter_plugins.md) - Custom filter
  documentation
- [vLLM Documentation](https://docs.vllm.ai/)
- [GuideLLM Documentation](https://github.com/neuralmagic/guidellm)

## Examples

See [inventory/inventory.md](inventory/inventory.md) for more examples.
