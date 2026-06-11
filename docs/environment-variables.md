---
layout: default
title: Environment Variables Reference
---

Complete reference for environment variables used in vLLM CPU Performance Evaluation scripts and playbooks.

## Test Configuration

### Model and Test Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `TEST_MODEL` | Override test model | None | `meta-llama/Llama-3.2-1B-Instruct` |
| `REQUESTED_CORES` | Override core count | Varies by script | `16` |
| `VLLM_MODE` | vLLM operational mode | `managed` | `managed`, `external` |
| `WORKLOAD_TYPE` | Test workload type | Varies | `chat`, `rag`, `code` |

### MTEB Quality Testing

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MTEB_TASK_PRESET` | Task preset | `quick` | `quick`, `comprehensive`, `retrieval` |
| `MTEB_TASKS` | Custom task list | None | `Banking77,Emotion` |
| `MTEB_LANGUAGES` | Language configuration | `en` | `en`, `en,es,fr` |
| `MTEB_CONTAINER_IMAGE` | Custom MTEB container | `quay.io/vllm-cpu-perf-eval/vllm-mteb:latest` | Custom registry URL |
| `RESULTS_DIR` | MTEB results directory | `results/mteb` | `/path/to/results` |

### Container Images

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VLLM_CONTAINER_IMAGE` | vLLM container image | Latest vLLM CPU | `registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0` |
| `VLLM_CONTAINER_ENTRYPOINT` | Custom entrypoint | None | `/opt/zendnn/activate.sh && vllm serve` |

### vLLM Server Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VLLM_ENDPOINT_URL` | External vLLM endpoint | None (auto-detect) | `http://192.168.1.100:8000` |
| `VLLM_HEALTH_TIMEOUT` | Health check timeout (seconds) | `300` | `600` (for ZenDNN) |
| `VLLM_CPU_START` | Starting CPU for vLLM | Auto | `64` |
| `VLLM_NUMA_NODE` | NUMA node for vLLM | Auto | `1` |

### Load Generator Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `GUIDELLM_CPUS` | CPU range for GuideLLM | Auto | `0-31` |
| `GUIDELLM_NUMA_NODE` | NUMA node for GuideLLM | Auto | `0` |

## Monitoring and Logging

### MLflow

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MLFLOW_TRACKING_URI` | MLflow server URI | `http://localhost:5000` | `http://mlflow.example.com:5000` |
| `MLFLOW_EXPERIMENT_NAME` | Experiment name | Auto-generated | `vllm-embedding-benchmarks` |

### Prometheus and Grafana

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `PROMETHEUS_PORT` | Prometheus port | `9090` | `9091` |
| `GRAFANA_PORT` | Grafana port | `3000` | `3001` |

## Ansible Configuration

### SSH and Connectivity

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DUT_HOSTNAME` | Device under test hostname | Required | `dut.example.com` |
| `ANSIBLE_SSH_KEY` | SSH private key path | `~/.ssh/id_rsa` | `~/.ssh/custom_key` |
| `ANSIBLE_SSH_USER` | SSH username | Current user | `testuser` |

### Inventory Management

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `INVENTORY_FILE` | Ansible inventory path | `inventory/hosts.yml` | `custom-inventory.yml` |

## Script-Specific Variables

### run-rhaiis-concurrent-load.sh

| Variable | Description | Example |
|----------|-------------|---------|
| `MODELS_INPUT` | Model preset or list | `all`, `llama`, `qwen`, `tiny` |
| `CORES_INPUT` | Core counts | `8,16,32` |
| `WORKLOADS_INPUT` | Workload types | `chat,rag` |
| `TENSOR_PARALLEL` | Tensor parallelism value | `2`, `4`, `8` |
| `SKIP_MODELS_INPUT` | Models to skip | `RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4` |

### run-embedding-suite.sh

| Variable | Description | Example |
|----------|-------------|---------|
| `EMBEDDING_MODELS` | Model preset | `all`, `small`, `medium`, `large`, `quick` |
| `CORE_COUNTS` | Core counts to test | `4,8,16,32` |
| `NUM_PROMPTS` | Number of prompts | `100` |

### run-mteb-model-sweep.sh

| Variable | Description | Example |
|----------|-------------|---------|
| `MTEB_MODELS` | Model list | `all`, custom list |
| `MTEB_CORES` | Core count | `4` |

## Advanced Configuration

### NUMA and CPU Pinning

All socket pinning variables can be set via environment:

```bash
export VLLM_CPU_START=64
export VLLM_NUMA_NODE=1
export GUIDELLM_CPUS="0-31"
export GUIDELLM_NUMA_NODE=0
```

### Container Runtime

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `CONTAINER_RUNTIME` | Container runtime | Auto-detect | `docker`, `podman` |

## Usage Examples

### Override Test Model
```bash
export TEST_MODEL="meta-llama/Llama-3.2-3B-Instruct"
./bash/run-embedding-suite.sh
```

### Use Custom RHAIIS Container
```bash
export VLLM_CONTAINER_IMAGE="registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0"
./bash/run-rhaiis-concurrent-load.sh
```

### Configure MLflow Tracking
```bash
export MLFLOW_TRACKING_URI="http://mlflow-server.example.com:5000"
ansible-playbook log-to-mlflow.yml
```

### Socket Separation via Environment
```bash
export VLLM_CPU_START=64
export VLLM_NUMA_NODE=1
export GUIDELLM_CPUS="0-31"
export GUIDELLM_NUMA_NODE=0
./bash/run-rhaiis-concurrent-load.sh --models qwen --cores 32
```

### External vLLM Endpoint (DUT-Only Mode)
```bash
export VLLM_MODE="external"
export VLLM_ENDPOINT_URL="http://192.168.1.100:8000"
ansible-playbook llm-benchmark-auto.yml \
  -e "workload_type=chat" \
  -e "requested_cores=16"
```

### ZenDNN Configuration (AMD)
```bash
export VLLM_CONTAINER_IMAGE="amd-vllm-zendnn:latest"
export VLLM_CONTAINER_ENTRYPOINT="/opt/zendnn/activate.sh && vllm serve"
export VLLM_HEALTH_TIMEOUT=600  # ZenDNN takes longer to initialize
ansible-playbook llm-benchmark-auto.yml
```

## Precedence

Environment variables are overridden by:
1. **Command-line flags** (highest priority)
2. **Ansible extra vars** (`-e` flag)
3. **Environment variables**
4. **Script defaults** (lowest priority)

Example:
```bash
# Environment sets 16 cores
export REQUESTED_CORES=16

# But command-line flag overrides to 32
./bash/run-embedding-suite.sh --cores 32  # Uses 32 cores
```

## See Also

- [Scripts Reference](scripts-reference.md) - Script usage and options
- [Ansible Test Execution](ansible/test-execution.md) - Ansible playbook parameters
- [MTEB Testing Guides](mteb-sweep-guide.md) - MTEB-specific configuration
