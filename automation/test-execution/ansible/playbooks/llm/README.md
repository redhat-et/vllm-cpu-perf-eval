# LLM Generative Model Testing Playbooks

Ansible playbooks for testing LLM generative models with GuideLLM.

## Overview

These playbooks test LLM generative models (Llama, Qwen, Granite,
etc.) across various:

- **Workloads**: SUMMARIZATION (1024:256), CHAT (512:128), CODE
  (2048:512), RAG (4096:256)
- **Core configurations**: From 16 cores to 128+ cores
- **Tensor parallelism**: Single process (TP=1) to multi-process
  (TP=2,3,4)
- **OMP settings**: Auto (default) or manually tuned

## Key Features

### Clean Restart Between Tests

Each test iteration ensures a fresh vLLM state:

1. Stops existing vLLM container
2. Removes container completely
3. Starts fresh with new configuration
4. Prevents state carryover affecting results

### Flexible CPU Configuration

**Container-level (REQUIRED):**

- `cpuset_cpus`: Which cores container can use
- `cpuset_mems`: Which NUMA nodes container can use

**vLLM-level (OPTIONAL):**

- `omp_num_threads`: Number of OMP threads (omit for auto)
- `omp_threads_bind`: OMP thread binding (omit for auto)

### GuideLLM Integration

- Runs as containerized benchmark on load generator
- Supports sweep profile for finding optimal throughput
- Generates HTML, JSON, CSV reports

## Playbooks

See [AUTO_VS_MANUAL_CONFIG.md](../../AUTO_VS_MANUAL_CONFIG.md)
for detailed comparison of auto vs manual configuration approaches.

### Manual Configuration Playbooks

These playbooks require pre-defined core configurations in inventory.

#### run-guidellm-test.yml

Run a single test with one core configuration.

**Usage:**

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook playbooks/llm/run-guidellm-test.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_name=16cores-socket0"
```

**Required Variables:**

- `test_model`: Model to test (e.g.,
  meta-llama/Llama-3.2-1B-Instruct)
- `workload_type`: One of: summarization, chat, code, rag
- `core_config_name`: Name of core configuration from inventory

**Optional Variables:**

- `cleanup_after_test`: Stop vLLM after test (default: false)

**Workflow:**

1. Start vLLM on DUT with specified core config
2. Health check
3. Run GuideLLM benchmark from load generator
4. Collect results and logs
5. Optional cleanup

#### run-core-sweep.yml

Test across multiple core configurations (e.g., T14, T16, T17, T18).

**Usage:**

```bash
export HF_TOKEN=hf_xxxxx

# Test T14, T16, T17, T18 configurations
ansible-playbook playbooks/llm/run-core-sweep.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_names=['16cores-socket0','32cores-socket0','64cores-socket0-tp2','96cores-dual-socket-tp3']"
```

**Required Variables:**

- `test_model`: Model to test
- `workload_type`: One of: summarization, chat, code, rag
- `core_config_names`: List of core configuration names

**Workflow (for each core config):**

1. Clean restart vLLM container
2. Start vLLM with specific core/NUMA/TP config
3. Health check
4. Run GuideLLM benchmark
5. Collect results with metadata
6. Stop vLLM (clean slate for next config)

### Auto-Configuration Playbooks

These playbooks auto-detect NUMA topology and generate configurations
from simple core counts.

#### run-guidellm-test-auto.yml

Run a single test with auto-generated configuration from core count.

**Usage:**

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook playbooks/llm/run-guidellm-test-auto.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores=16"
```

**Required Variables:**

- `test_model`: Model to test
- `workload_type`: One of: summarization, chat, code, rag
- `requested_cores`: Number of cores to allocate

**Optional Variables:**

- `requested_tensor_parallel`: TP count (default: 1)
- `requested_omp_threads`: Manual OMP thread count
- `requested_omp_bind`: Manual OMP binding
- `cleanup_after_test`: Stop vLLM after test (default: false)

**Workflow:**

1. Detect NUMA topology on DUT
2. Allocate requested cores from vLLM node
3. Generate configuration: `<N>cores-auto-numa<X>`
4. Start vLLM with auto-generated config
5. Health check
6. Run GuideLLM benchmark
7. Collect results and logs

#### run-core-sweep-auto.yml

Test across multiple core counts with auto-generated configurations.

**Usage:**

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook playbooks/llm/run-core-sweep-auto.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores_list=[8,16,32,64]"
```

**Required Variables:**

- `test_model`: Model to test
- `workload_type`: One of: summarization, chat, code, rag
- `requested_cores_list`: List of core counts to test

**Workflow (for each core count):**

1. Detect NUMA topology (once)
2. For each core count:
   - Allocate cores from topology
   - Generate unique config name
   - Clean restart vLLM
   - Start vLLM with auto-config
   - Health check
   - Run GuideLLM benchmark
   - Collect results with metadata
   - Stop vLLM (clean slate for next)

## Configuration

### Core Configurations

Define in inventory `core_configs`:

```yaml
core_configs:
  # Auto OMP (recommended for most cases)
  - name: "16cores-socket0"
    cores: 16
    cpuset_cpus: "64-79"      # Container boundary
    cpuset_mems: "0"          # NUMA node
    tensor_parallel: 1

  # Manual OMP tuning (advanced)
  - name: "64cores-socket0-tp2"
    cores: 64
    cpuset_cpus: "32-95"      # Container boundary
    cpuset_mems: "0"
    omp_num_threads: 32       # OPTIONAL: Manual OMP config
    omp_threads_bind: "32-63|64-95"  # OPTIONAL: Per-worker binding
    tensor_parallel: 2
```

**When to use manual OMP:**

- Testing specific OMP configurations
- Multi-worker (TP>1) with custom thread placement
- Performance tuning experiments

**Default behavior (OMP omitted):**

- vLLM auto-configures OMP threads
- Usually optimal for most scenarios
- Recommended starting point

### Workload Configurations

Define in inventory `test_configs`:

```yaml
test_configs:
  summarization:
    workload_type: "summarization"
    isl: 1024
    osl: 256
    backend: "openai-completions"
    vllm_args:
      - "--dtype=bfloat16"
      - "--no_enable_prefix_caching"
    kv_cache_space: "40GiB"

  chat:
    workload_type: "chat"
    isl: 512
    osl: 128
    # ...
```

### GuideLLM Configuration

Define in inventory `benchmark_tool.guidellm`:

```yaml
benchmark_tool:
  guidellm:
    container_image: "quay.io/mtahhan/guidellm:saturation-fix"
    cpuset_cpus: "32-63"  # Load generator CPU allocation
    cpuset_mems: "0"
    profile: "sweep"
    max_seconds: 600
    max_requests: 2000
    saturation_threshold: 0.98
    max_concurrency: 128
    # ...
```

## Examples

### Example 1: T14 - 16 cores, SUMMARIZATION

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook playbooks/llm/run-guidellm-test.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_name=16cores-socket0"
```

**Result**: Single test with 16 cores, auto OMP, TP=1

### Example 2: T14-T18 Core Sweep

```bash
export HF_TOKEN=hf_xxxxx

ansible-playbook playbooks/llm/run-core-sweep.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_names=['16cores-socket0','32cores-socket0','64cores-socket0-tp2','96cores-dual-socket-tp3']"
```

**Result**: 4 tests (T14, T16, T17, T18), each with clean vLLM
restart

### Example 3: Multiple Workloads

```bash
export HF_TOKEN=hf_xxxxx

# Test SUMMARIZATION
ansible-playbook playbooks/llm/run-guidellm-test.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "core_config_name=32cores-socket0"

# Test CHAT
ansible-playbook playbooks/llm/run-guidellm-test.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "core_config_name=32cores-socket0"
```

### Example 4: Multiple Models

```bash
export HF_TOKEN=hf_xxxxx

for model in \
  "meta-llama/Llama-3.2-1B-Instruct" \
  "meta-llama/Llama-3.2-3B-Instruct" \
  "Qwen/Qwen2.5-0.5B-Instruct"; do

  ansible-playbook playbooks/llm/run-core-sweep.yml \
    -i inventory/example-full-config.yml \
    -e "test_model=$model" \
    -e "workload_type=summarization" \
    -e "core_config_names=['16cores-socket0','32cores-socket0']"
done
```

### Example 5: Auto-Config - Single Test

```bash
export HF_TOKEN=hf_xxxxx

# Simple 16-core test with auto NUMA allocation
ansible-playbook playbooks/llm/run-guidellm-test-auto.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores=16"
```

**Result**: Auto-detects NUMA, allocates 16 cores, generates config
`16cores-auto-numa<X>`

### Example 6: Auto-Config - Core Sweep

```bash
export HF_TOKEN=hf_xxxxx

# Test multiple core counts with auto-configuration
ansible-playbook playbooks/llm/run-core-sweep-auto.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores_list=[8,16,32,64]"
```

**Result**: 4 tests with auto-generated configs, clean restart
between each

### Example 7: Auto-Config with Manual OMP

```bash
export HF_TOKEN=hf_xxxxx

# Auto NUMA allocation but manual OMP settings
ansible-playbook playbooks/llm/run-guidellm-test-auto.yml \
  -i inventory/example-full-config.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores=32" \
  -e "requested_tensor_parallel=2" \
  -e "requested_omp_threads=16" \
  -e "requested_omp_bind=64-79|80-95"
```

**Result**: Auto-allocated 32 cores with manual TP=2 and OMP
settings

## Results Structure

```text
results/llm/
├── Llama-3.2-1B-Instruct/
│   ├── summarization-20260218-143022/
│   │   ├── 16cores-socket0/
│   │   │   ├── test-metadata.json
│   │   │   ├── guidellm-report.html
│   │   │   ├── guidellm-results.json
│   │   │   └── guidellm-results.csv
│   │   ├── 32cores-socket0/
│   │   ├── 64cores-socket0-tp2/
│   │   └── 96cores-dual-socket-tp3/
│   └── chat-20260218-150033/
└── Llama-3.2-3B-Instruct/
```

## Monitoring

### Monitor vLLM on DUT

```bash
# Real-time logs
automation/utilities/log-monitoring/monitor-vllm-logs.sh \
  --mode remote \
  --remote-host <dut-ip>

# Container stats
ssh <dut-ip> "podman stats vllm-server"
```

### Monitor GuideLLM on Load Generator

```bash
# Real-time logs
ssh <loadgen-ip> "podman logs -f guidellm-summarization-16cores-socket0"

# Test progress
automation/utilities/log-monitoring/monitor-test-progress.yml \
  --mode remote \
  --remote-host <loadgen-ip>
```

## Troubleshooting

### vLLM OOM (Out of Memory)

**Problem**: vLLM crashes with OOM error

**Solution**: Reduce KV cache in workload config:

```yaml
test_configs:
  summarization:
    kv_cache_space: "20GiB"  # Reduced from 40GiB
```

### Tensor Parallelism Errors

**Problem**: TP workers fail to communicate

**Solution**: Check OMP thread binding matches TP config:

```yaml
# For TP=2 with 64 cores
omp_num_threads: 32  # 64/2 = 32 threads per worker
omp_threads_bind: "32-63|64-95"  # Split cores between workers
```

### GuideLLM Timeout

**Problem**: GuideLLM times out without completing

**Solution**: Increase max_seconds or reduce max_requests:

```yaml
benchmark_tool:
  guidellm:
    max_seconds: 1200  # 20 minutes
    max_requests: 1000  # Fewer requests
```

### Model Download Fails

**Problem**: HuggingFace token invalid or model not accessible

**Solution**: Verify token and model access:

```bash
export HF_TOKEN=hf_xxxxx
huggingface-cli login --token $HF_TOKEN
huggingface-cli download meta-llama/Llama-3.2-1B-Instruct --token $HF_TOKEN
```

## Best Practices

1. **Start with Auto OMP**: Omit `omp_num_threads` and
   `omp_threads_bind` initially
2. **Clean Restart**: Always included automatically between core
   configs
3. **Monitor First Run**: Watch logs to ensure vLLM starts
   correctly
4. **Incremental Testing**: Start with small core counts, then
   scale up
5. **Match TP to Hardware**: Use TP=1 for <64 cores, TP=2+ for 64+
   cores
6. **Document Custom OMP**: If using manual OMP, document why in
   comments

## References

- [Auto vs Manual Configuration Guide](../../AUTO_VS_MANUAL_CONFIG.md)
- [Configuration Guide](../../CONFIGURATION_GUIDE.md)
- [Example Inventory](../../inventory/example-full-config.yml)
- [Common Playbooks](../common/)
- [Platform Setup Script](../../../../platform-setup/bash/intel/setup-guidellm-platform.sh)
- [GuideLLM Documentation](https://github.com/neuralmagic/guidellm)
- [vLLM Documentation](https://docs.vllm.ai/)
