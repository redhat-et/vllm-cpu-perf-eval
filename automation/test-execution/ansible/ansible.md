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

# Run LLM benchmark (manual config)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_name=32cores-single-socket"
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

## Available Playbooks

### LLM Testing

| Playbook | Purpose | Usage |
|----------|---------|-------|
| [llm-benchmark.yml](llm-benchmark.yml) | Single LLM test with manual config | `-e "core_config_name=..."` |
| [llm-core-sweep.yml](llm-core-sweep.yml) | Test multiple core configs | `-e "core_config_names=[...]"` |
| [embedding-benchmark.yml](embedding-benchmark.yml) | Single embedding test | `-e "test_model=..." -e "scenario=baseline"` |
| [embedding-core-sweep.yml](embedding-core-sweep.yml) | Embedding core sweep | Multiple configs |

### Platform Setup

| Playbook | Purpose | When |
|----------|---------|------|
| [setup-platform.yml](setup-platform.yml) | Configure DUT/LoadGen for optimal performance | One-time, before testing |
| [collect-logs.yml](collect-logs.yml) | Collect logs and results | After tests |
| [health-check.yml](health-check.yml) | Check vLLM server health | Standalone or imported |

**Note:** `llm-benchmark-auto.yml` and `llm-core-sweep-auto.yml` have broken references and need updating.

## Workload Types

Pre-configured in [inventory/group_vars/all/test-workloads.yml](inventory/group_vars/all/test-workloads.yml):

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
ansible-playbook -i inventory/hosts.yml setup-platform.yml

# Reboot required
ansible -i inventory/hosts.yml all -b -m reboot

# Validate after reboot
ansible -i inventory/hosts.yml dut -b -a "tuned-adm active"
```

### Run LLM Benchmark

Test with specific core configuration:

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook -i inventory/hosts.yml \
  llm-benchmark.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_name=32cores-single-socket"
```

### Run Embedding Benchmark

```bash
ansible-playbook -i inventory/hosts.yml \
  embedding-benchmark.yml \
  -e "test_model=ibm-granite/granite-embedding-278m-multilingual" \
  -e "scenario=baseline"
```

### Test Multiple Models

```bash
export HF_TOKEN=hf_xxxxx

for model in \
  "meta-llama/Llama-3.2-1B-Instruct" \
  "meta-llama/Llama-3.2-3B-Instruct"; do

  ansible-playbook -i inventory/hosts.yml \
    llm-benchmark.yml \
    -e "test_model=$model" \
    -e "workload_type=summarization" \
    -e "core_config_name=16cores-single-socket"
done
```

## Directory Structure

```text
automation/test-execution/ansible/
├── ansible.cfg                       # Ansible configuration
├── inventory/
│   ├── hosts.yml                    # Main inventory - edit IPs here
│   ├── group_vars/                  # Group variables
│   │   ├── all/                     # Variables for all hosts
│   │   │   ├── benchmark-tools.yml  # GuideLLM, vllm-bench config
│   │   │   ├── credentials.yml      # HuggingFace token setup
│   │   │   ├── endpoints.yml        # Network endpoints
│   │   │   ├── hardware-profiles.yml # Core configurations
│   │   │   ├── infrastructure.yml    # Paths, directories
│   │   │   └── test-workloads.yml   # Workload definitions
│   │   ├── dut/main.yml             # DUT-specific vars
│   │   └── load_generator/main.yml  # Load gen-specific vars
│   ├── examples/                    # Example inventory files
│   └── README.md                    # Inventory documentation
│
├── roles/                           # Reusable roles
│   ├── vllm_server/                 # vLLM server management
│   │   ├── defaults/main.yml        # Default variables
│   │   └── tasks/                   # Tasks
│   │       ├── main.yml
│   │       ├── start-llm.yml
│   │       ├── start-embedding.yml
│   │       └── clean-restart.yml
│   ├── hf_token/                    # HuggingFace token setup
│   │   └── tasks/
│   │       ├── main.yml
│   │       └── setup-optional.yml
│   ├── benchmark_guidellm/          # GuideLLM benchmarks
│   │   ├── defaults/main.yml
│   │   └── tasks/main.yml
│   ├── benchmark_embedding/         # Embedding benchmarks
│   │   └── tasks/
│   │       ├── main.yml
│   │       ├── baseline.yml
│   │       └── latency.yml
│   ├── benchmark_vllm_bench/        # vllm-bench base
│   │   └── tasks/main.yml
│   └── results_collector/           # Log/result collection
│       └── tasks/
│           ├── main.yml
│           ├── collect-vllm-logs.yml
│           └── collect-test-results.yml
│
├── llm-benchmark.yml                # LLM playbook
├── llm-benchmark-auto.yml           # Auto-config (broken)
├── llm-core-sweep.yml               # LLM sweep
├── llm-core-sweep-auto.yml          # Auto sweep (broken)
├── embedding-benchmark.yml          # Embedding playbook
├── embedding-core-sweep.yml         # Embedding sweep
├─��� setup-platform.yml               # Platform setup
├── collect-logs.yml                 # Log collection
├── health-check.yml                 # Health check
├── start-vllm-server.yml            # vLLM starter
│
├── filter_plugins/                  # Custom Jinja2 filters
│   ├── cpu_utils.py                 # CPU topology filters
│   └── test_cpu_utils.py            # Unit tests
│
└── ansible.md                       # This file
```

## Roles

### vllm_server
Manages vLLM server lifecycle:
- Starts vLLM for LLM or embedding workloads
- Handles HuggingFace token setup
- Clean container restarts
- CPU/NUMA pinning

### hf_token
HuggingFace authentication:
- Multiple token sources (env, file, vault, prompt)
- Optional setup (allows public models)

### benchmark_guidellm
GuideLLM benchmark execution:
- Container or host execution
- Configurable workloads
- Result collection

### benchmark_embedding
Embedding model benchmarks:
- Baseline throughput tests
- Latency/concurrency tests
- Uses vllm-bench

### results_collector
Log and result collection:
- Collects vLLM logs from DUT
- Fetches benchmark results from load generator
- Organizes by test run ID

## Custom Configurations

### Add Custom Workload

Edit [inventory/group_vars/all/test-workloads.yml](inventory/group_vars/all/test-workloads.yml):

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

Edit [inventory/group_vars/all/hardware-profiles.yml](inventory/group_vars/all/hardware-profiles.yml):

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

## Key Features

- **Role-based architecture** - Modular, reusable components
- **Group variables** - Environment-specific configuration
- **Custom Jinja2 filters** - Native Python (no shell/awk scripts)
- **Clean restarts** - Fresh vLLM state between tests
- **Secure HF tokens** - Multiple methods (env, file, vault, prompt)
- **Container isolation** - Podman/Docker with CPU/NUMA pinning
- **Platform tuning** - CPU isolation, tuned profiles, systemd pinning
- **Comprehensive testing** - Unit tests for all filters
- **Single inventory** - Just edit IPs and run

## References

- [Inventory Documentation](inventory/inventory.md) - Detailed inventory guide
- [Filter Plugins](filter_plugins/filter_plugins.md) - Custom filter documentation
- [vLLM Documentation](https://docs.vllm.ai/)
- [GuideLLM Documentation](https://github.com/neuralmagic/guidellm)
- [Ansible Best Practices](https://docs.ansible.com/projects/ansible/latest/tips_tricks/sample_setup.html)
