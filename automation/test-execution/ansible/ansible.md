# vLLM Performance Testing - Ansible Automation

Automated testing framework for vLLM embedding and LLM generative
models with NUMA-aware CPU optimization.

## Quick Start

### 1. Configure Inventory

Edit [inventory/hosts.yml](inventory/hosts.yml) - **only change the
IP addresses** (see [inventory documentation](inventory/README.md) for details):

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
| [llm-benchmark-auto.yml](llm-benchmark-auto.yml) | Single LLM test with auto core allocation | `-e "requested_cores=16"` |
| **[llm-benchmark-concurrent-load.yml](llm-benchmark-concurrent-load.yml)** | **3-phase concurrent load testing** | `-e "base_workload=chat" -e "core_sweep_counts=[16,32]"` |
| [llm-core-sweep.yml](llm-core-sweep.yml) | Test multiple core configs | `-e "core_config_names=[...]"` |
| [llm-core-sweep-auto.yml](llm-core-sweep-auto.yml) | Test multiple core counts (auto-allocated) | `-e "requested_cores_list=[8,16,32]"` |
| [embedding-benchmark.yml](embedding-benchmark.yml) | Single embedding test | `-e "test_model=..." -e "scenario=baseline"` |
| [embedding-core-sweep.yml](embedding-core-sweep.yml) | Embedding core sweep | Multiple configs |

### Platform Setup

| Playbook | Purpose | When |
|----------|---------|------|
| [setup-platform.yml](setup-platform.yml) | Configure DUT/LoadGen for optimal performance | One-time, before testing |
| [collect-logs.yml](collect-logs.yml) | Collect logs from DUT | After tests |
| [health-check.yml](health-check.yml) | Check vLLM server health | Standalone or imported |

## Workload Types

Pre-configured in [inventory/group_vars/all/test-workloads.yml](inventory/group_vars/all/test-workloads.yml):

### Baseline Workloads (Fixed Tokens)

| Workload | ISL:OSL | Use Case | Baseline vLLM Args |
|----------|---------|----------|-----------|
| `embedding` | 512:1 | Embedding models | `--dtype=bfloat16 --max-model-len=512` |
| `chat` | 512:256 | Chatbots | `--dtype=bfloat16 --no-enable-prefix-caching` |
| `rag` | 4096:512 | RAG applications | `--dtype=bfloat16 --no-enable-prefix-caching` |
| `code` | 512:4096 | Code generation | `--dtype=bfloat16 --no-enable-prefix-caching` |
| `short_codegen` | 256:2048 | Short code generation | `--dtype=bfloat16 --no-enable-prefix-caching` |
| `summarization` | 1024:256 | Text summarization | `--dtype=bfloat16 --no-enable-prefix-caching` |

### Variable Workloads (Realistic Traffic)

| Workload | ISL±σ:OSL±σ | Use Case | Baseline vLLM Args |
|----------|---------|----------|-----------|
| `chat_var` | 512±128:256±64 | Realistic chat traffic | `--dtype=bfloat16 --no-enable-prefix-caching` |
| `code_var` | 512±128:4096±1024 | Realistic code generation | `--dtype=bfloat16 --no-enable-prefix-caching` |

**Note:** Baseline mode disables both prefix caching and radix cache for true baseline measurements. Production mode enables caching optimizations.


## 3-Phase Concurrent Load Testing

The recommended testing methodology for CPU inference performance evaluation follows a 3-phase approach:

### Phase 1: Baseline (Fixed Tokens, No Caching)
Establish pure baseline performance without any caching optimizations.
- **Configuration:** `vllm_caching_mode=baseline`
- **Workload:** Fixed token counts (e.g., `chat`, `rag`, `code`)
- **vLLM flags:** `--no-enable-prefix-caching`
- **Concurrency levels:** `[1, 8, 16, 32, 64, 96, 128]`

### Phase 2: Realistic (Variable Tokens, No Caching)
Measure performance under realistic traffic variability.
- **Configuration:** `vllm_caching_mode=baseline`
- **Workload:** Variable token counts (e.g., `chat_var`, `code_var`)
- **vLLM flags:** `--no-enable-prefix-caching`
- **Concurrency levels:** `[1, 8, 16, 32, 64, 96, 128]`

### Phase 3: Production (Variable Tokens, With Caching)
Simulate true production conditions with realistic load and optimizations.
- **Configuration:** `vllm_caching_mode=production`
- **Workload:** Variable token counts (e.g., `chat_var`, `code_var`)
- **vLLM flags:** Default (caching enabled)
- **Concurrency levels:** `[1, 8, 16, 32, 64, 96, 128]`

### Run All 3 Phases (Recommended)

```bash
export HF_TOKEN=hf_xxxxx

# Full 3-phase concurrent load test with core sweep
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "core_sweep_counts=[16,32,64]"
```

This runs:
1. Phase 1: `chat` baseline (fixed tokens, no caching)
2. Phase 2: `chat_var` realistic (variable tokens, no caching)
3. Phase 3: `chat_var` production (variable tokens, with caching)

**Note:** You specify the base workload (e.g., `base_workload=chat`), and the playbook automatically:
- Uses `chat` for Phase 1 (fixed)
- Uses `chat_var` for Phase 2 (adds `_var` suffix)
- Uses `chat_var` for Phase 3 (adds `_var` suffix)

All phases use the same concurrency sweep: `[1, 8, 16, 32, 64, 96, 128]`

### Run Individual Phases

```bash
# Phase 1 only (baseline)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "base_workload=chat" \
  -e "requested_cores=16" \
  -e "skip_phase_2=true" \
  -e "skip_phase_3=true"

# Phase 3 only (production)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=rag" \
  -e "core_sweep_counts=[16,32]" \
  -e "skip_phase_1=true" \
  -e "skip_phase_2=true"
```

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
├── llm-benchmark-auto.yml           # Auto-config LLM test
├── llm-core-sweep.yml               # LLM sweep
├── llm-core-sweep-auto.yml          # Auto-config sweep
├── embedding-benchmark.yml          # Embedding playbook
├── embedding-core-sweep.yml         # Embedding sweep
├── setup-platform.yml               # Platform setup
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

### Override GuideLLM Parameters

**Default Configuration (CPU Testing):**
- **Profile:** `concurrent` - Fixed concurrency level testing
- **Concurrency Rates:** `[1, 8, 16, 32, 64, 96, 128]` - CPU-appropriate levels
- **Test Duration:** `600` seconds (10 minutes per concurrency level)
- **Request Timeout:** `600` seconds (matches test duration)
- **Max Concurrency:** `128` (CPU testing limit)

You can customize GuideLLM benchmark parameters in two ways:

**Option 1: Simple flat variables (recommended for quick tests)**

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=Qwen/Qwen2.5-3B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "guidellm_max_seconds=120" \
  -e "guidellm_rate=[1,8,16]"
```

**Option 2: Dictionary syntax (for multiple parameters)**

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=Qwen/Qwen2.5-3B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e '{"benchmark_tool": {"guidellm": {"max_seconds": 120, "profile": "throughput", "rate": [32]}}}'
```

**Available flat variables:**
- `guidellm_profile` - Benchmark profile (concurrent, throughput, sweep, synchronous)
- `guidellm_rate` - Concurrency levels for concurrent profile (e.g., `[1,8,16,32]`)
- `guidellm_max_seconds` - Maximum test duration (default: 600)
- `guidellm_max_requests` - Maximum requests to send (default: 1000)
- `guidellm_request_timeout` - Request timeout (default: 600)
- `guidellm_max_concurrency` - Maximum concurrent requests (default: 128)
- `guidellm_warmup` - Warmup percentage (default: 0.1 = 10%)
- `guidellm_cooldown` - Cooldown between tests in seconds (default: 30)
- `guidellm_outputs` - Output formats (default: "html,json,csv")
- `guidellm_container_image` - GuideLLM container image
- `guidellm_use_container` - Use container mode (default: true)
- `guidellm_cpuset_cpus` - CPU allocation for GuideLLM (default: "16-31")
- `guidellm_cpuset_mems` - NUMA node allocation (default: "0")

Defaults are defined in [inventory/group_vars/all/benchmark-tools.yml](inventory/group_vars/all/benchmark-tools.yml).

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

### Benchmark Timeout

If a benchmark times out waiting for completion:

```bash
# Default timeout = min(max_seconds + 600, 14400)
# - Short tests: max_seconds + 10min buffer
# - Long tests: capped at 4 hours

# Override timeout for very long tests:
ansible-playbook ... -e "guidellm_wait_timeout_seconds=7200"  # 2 hours

# Monitor container in real-time:
ssh <DUT_IP> "sudo podman logs -f <container-name>"

# Check if container is stuck:
ssh <DUT_IP> "sudo podman ps -a"
ssh <DUT_IP> "sudo podman inspect <container-name> --format '{{.State.Status}}'"
```

**Timeout Examples:**
- `max_seconds: 120` → timeout: 720s (12 min)
- `max_seconds: 1800` → timeout: 2400s (40 min)
- `max_seconds: 10800` → timeout: 14400s (4 hours, capped)

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

- [Inventory Documentation](inventory/README.md) - Detailed inventory guide
- [Filter Plugins](filter_plugins/filter_plugins.md) - Custom filter documentation
- [vLLM Documentation](https://docs.vllm.ai/)
- [GuideLLM Documentation](https://github.com/neuralmagic/guidellm)
- [Ansible Best Practices](https://docs.ansible.com/projects/ansible/latest/tips_tricks/sample_setup.html)
