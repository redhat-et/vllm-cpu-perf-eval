# vLLM Test Execution

Automated test execution framework for vLLM CPU performance benchmarking.

## Overview

This directory contains all components for running vLLM benchmarks:

- **Ansible Playbooks** - Test orchestration and execution
- **Bash Scripts** - Test suites and workflows
- **Dashboards** - Results visualization (Streamlit)
- **Configurations** - Test parameters and settings

## Test Types

### 1. Online Inference (Client/Server)

Tests vLLM in online serving mode with concurrent requests.

**Playbooks:**
- `ansible/llm-benchmark-auto.yml` - Single configuration test
- `ansible/llm-benchmark-concurrent-load.yml` - Concurrent load testing
- `ansible/llm-core-sweep-auto.yml` - Core scaling sweep

**Metrics:**
- Client-side: TTFT, ITL, E2E latency, throughput
- Server-side: Queue depth, cache usage, token rates

**Dashboard:** `pages/1_📊_Client-Side.py`, `pages/2_🖥️_Server-Side.py`

### 2. Offline Batch Processing

Tests vLLM in offline batch mode (vllm bench throughput).

**CLI (recommended):**
- `../../cpueval run --suite offline-batch` — see [cpueval CLI Guide](../../docs/cpueval-cli.md)

**Playbook:**
- `ansible/llm-benchmark-offline-batch.yml` - Offline batch benchmark

**Test Suite:**
- `scripts/bash/run-offline-batch-suite.sh` - Comprehensive test suite (invoked by cpueval)

**Features:**
- 11 real-world use cases (summarization, classification, translation, long-doc summarization, RAG, shared-prefix, ultra-short labeling, etc.)
- Multi-model support (all 4 RedHatAI models)
- Core scaling, batch size scaling
- Container image tracking

**Metrics:**
- Throughput (requests/sec, tokens/sec)
- Processing capacity (items/hour)
- Prefill/decode throughput
- KV cache usage

**Dashboard:** `pages/4_📦_Offline_Batch.py`

**Documentation:** See [../../tests/offline-batch/offline-batch.md](../../tests/offline-batch/offline-batch.md)

### 3. Embedding Models

Tests embedding model performance using vLLM bench serve.

**Playbook:**
- `ansible/embedding-benchmark.yml` - Embedding model benchmarks

**Metrics:**
- Request throughput (req/s)
- Latency (P50, P99)
- Saturation curves

**Dashboard:** `pages/3_📊_Embedding.py`

## Quick Start

### Online Inference

```bash
# Single test - managed mode (vLLM runs on DUT)
ansible-playbook -i ansible/inventory/hosts.yml ansible/llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores=16"

# Core sweep
ansible-playbook -i ansible/inventory/hosts.yml ansible/llm-core-sweep-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "requested_cores_list=[8,16,32,64]"

# External endpoint mode
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-vllm:8000

ansible-playbook -i ansible/inventory/hosts.yml ansible/llm-benchmark-concurrent-load.yml \
  -e "base_workload=chat" \
  -e "requested_cores=16"
```

### Offline Batch Processing

**Via cpueval (recommended, from repository root):**

```bash
# Default: all 11 use cases, 3 runs each
./cpueval run --suite offline-batch

# All use cases, all RedHatAI models, 5 runs each
./cpueval run --suite offline-batch --mode use-cases --runs 5 --models all

# Single use case with core sweep
./cpueval run --suite offline-batch \
  --mode use-case-sweep \
  --use-case summarization \
  --models all \
  --cores 8,16,24,32 \
  --runs 3

# RHAIIS container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./cpueval run --suite offline-batch --mode use-cases --runs 3 --models all
```

**Via bash script (advanced):**

```bash
cd scripts/bash

# Run all 11 use cases with all 4 RedHatAI models (5 iterations each)
./run-offline-batch-suite.sh use-cases 5 all

# Single test configuration
./run-offline-batch-suite.sh run_test all sonnet 1000 16

# Test specific models (comma-separated)
./run-offline-batch-suite.sh run_test \
  "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8,RedHatAI/Qwen3-8B-quantized.w4a16" \
  sonnet 1000 16

# Use different container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./run-offline-batch-suite.sh run_test all sonnet 1000 16

# Technical benchmarks
./run-offline-batch-suite.sh baseline 32 100
./run-offline-batch-suite.sh batch-scaling <model> 16
./run-offline-batch-suite.sh input-scaling <model> 16
./run-offline-batch-suite.sh output-scaling <model> 16
./run-offline-batch-suite.sh core-scaling <model>
./run-offline-batch-suite.sh kv-capacity <model> 32
./run-offline-batch-suite.sh context-scaling <model> 32
```

See [cpueval CLI Guide](../../docs/cpueval-cli.md) and
[Offline Batch Test Scenarios](../../tests/offline-batch/offline-batch.md).

### Embedding Models

```bash
# All scenarios (baseline + concurrent load)
ansible-playbook -i ansible/inventory/hosts.yml ansible/embedding-benchmark.yml \
  -e "test_model=RedHatAI/all-MiniLM-L6-v2" \
  -e "scenario=all"

# External endpoint mode
export VLLM_MODE=external
export VLLM_ENDPOINT_URL=http://your-endpoint:8000
ansible-playbook -i ansible/inventory/hosts.yml ansible/embedding-benchmark.yml \
  -e "scenario=baseline"
```

## Results

All results are saved to `../../results/`:
- **LLM (online & offline)**: `results/llm/`
- **Embedding**: `results/embedding/`

Each test creates:
- `test-metadata.json` - Test configuration and environment
- `results.json` - Performance metrics
- `benchmark.log` - Raw output

## Dashboards

View results in interactive dashboards:

```bash
cd dashboard-examples/vllm_dashboard
streamlit run Home.py
```

**Pages:**
1. **Client-Side** - GuideLLM benchmark results (online)
2. **Server-Side** - vLLM server metrics (online)
3. **Embedding** - Embedding model performance
4. **Offline Batch** - Batch processing performance

## Environment Variables

### Container Images

```bash
# vLLM container (default: upstream vLLM)
export VLLM_CONTAINER_IMAGE=vllm/vllm-openai:latest

# Use RHAIIS optimized container
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
```

### Endpoint Configuration

```bash
# Use external vLLM endpoint
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-vllm:8000

# Embedding models
export VLLM_MODE=external
export VLLM_ENDPOINT_URL=http://your-endpoint:8000
```

### HuggingFace

```bash
# For gated models
export HF_TOKEN=hf_your_token_here
```

## Testing

Run unit tests:

```bash
# Offline batch dashboard tests
python -m pytest automation/test-execution/tests/dashboard/test_offline_batch_page.py -v

# Offline batch script tests
bash automation/test-execution/tests/scripts/test_run_offline_batch_suite.sh
```

## Directory Structure

```
automation/test-execution/
├── ansible/                    # Ansible playbooks and roles
│   ├── llm-benchmark-auto.yml
│   ├── llm-benchmark-concurrent-load.yml
│   ├── llm-benchmark-offline-batch.yml
│   ├── llm-core-sweep-auto.yml
│   ├── embedding-benchmark.yml
│   ├── inventory/              # Inventory files
│   └── roles/                  # Ansible roles
├── scripts/
│   └── bash/
│       └── run-offline-batch-suite.sh
├── dashboard-examples/
│   └── vllm_dashboard/
│       ├── Home.py
│       └── pages/
│           ├── 1_📊_Client-Side.py
│           ├── 2_🖥️_Server-Side.py
│           ├── 3_📊_Embedding.py
│           └── 4_📦_Offline_Batch.py
└── README.md                   # This file
```

## Documentation

- **Test Scenarios**: See [../../tests/](../../tests/) for detailed test documentation
  - [Offline Batch](../../tests/offline-batch/offline-batch.md)
  - [Concurrent Load](../../tests/concurrent-load/concurrent-load.md)
  - [Embedding Models](../../tests/embedding-models/embedding-models.md)
- **Ansible**: [ansible/README.md](ansible/README.md)
- **Scripts**: [scripts/README.md](scripts/README.md)
- **Dashboards**: [dashboard-examples/vllm_dashboard/README.md](dashboard-examples/vllm_dashboard/README.md)

## Models

### RedHatAI Intel Xeon Compatible Models

```
RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4
RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8
RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16
RedHatAI/Qwen3-8B-quantized.w4a16
```

### Other Supported Models

```
TinyLlama/TinyLlama-1.1B-Chat-v1.0
meta-llama/Llama-3.2-1B-Instruct
meta-llama/Llama-3.1-8B-Instruct
```

## Support

For issues or questions:
- Check the relevant README in subdirectories
- Review test scenario specifications in `tests/offline-batch/`
- Examine example playbook runs in playbook headers
