# Embedding Models - Testing Guide

## Overview

This guide covers testing embedding models on Intel Xeon processors using the vLLM performance evaluation framework. The framework supports three execution modes to accommodate different testing scenarios.

## Execution Modes

### 1. Managed Mode (Load Generator + DUT) - Default
- **vLLM Server**: Runs on DUT in container (Device Under Test)
- **Benchmark Tool**: Runs on separate Load Generator node
- **Best For**: Production-like performance testing, network overhead measurement
- **Network**: Requires network connectivity between DUT and Load Generator

```bash
# Using environment variables (recommended)
export DUT_HOSTNAME=your-dut-ip
export LOADGEN_HOSTNAME=your-loadgen-ip
export VLLM_MODE=managed  # or omit (default)

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "scenario=baseline"
```

### 2. DUT-Only Mode
- **vLLM Server**: Runs on DUT (in container)
- **Benchmark Tool**: Runs on same DUT node (localhost)
- **Best For**: Single-node testing, eliminating network latency overhead
- **Network**: No network communication needed (uses localhost)

```bash
export DUT_HOSTNAME=your-dut-ip
export VLLM_MODE=dut-only

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/nomic-embed-text-v1.5" \
  -e "scenario=latency"
```

### 3. External Mode
- **vLLM Server**: Already running externally (not managed by Ansible)
- **Benchmark Tool**: Runs on Load Generator node
- **Best For**: Testing production deployments, cloud/K8s endpoints, remote services
- **Network**: Requires network access to external vLLM endpoint

```bash
export LOADGEN_HOSTNAME=your-loadgen-ip
export VLLM_MODE=external
export VLLM_ENDPOINT_URL=http://production-vllm.example.com:8000

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/Qwen3-Embedding-8B"  # Optional: auto-detected if omitted
```

## Supported Embedding Models

The following embedding models from the [RedHatAI Intel Xeon-compatible collection](https://huggingface.co/collections/RedHatAI/intel-xeon-compatible-models) are tested and supported:

### Quick Reference

| Model | Size | Max Sequence Length | Task |
|-------|------|---------------------|------|
| **RedHatAI/all-MiniLM-L6-v2** | 22.7M | 256 tokens | Sentence Similarity |
| **RedHatAI/nomic-embed-text-v1.5** | 137M | 8192 tokens | Sentence Similarity |
| **RedHatAI/granite-embedding-english-r2** | 109M | 8192 tokens | Feature Extraction |
| **RedHatAI/embeddinggemma-300m** | 300M | 2048 tokens | Sentence Similarity |
| **RedHatAI/Qwen3-Embedding-8B** | 8B | 40960 tokens | Feature Extraction |

**Note**: Max sequence lengths are auto-detected by vLLM from model configs. The `--max-model-len` parameter is optional and only needed if you want to override the default.

### Small Models (< 1B parameters)

#### 1. RedHatAI/all-MiniLM-L6-v2
- **Size**: 22.7M parameters
- **Max Sequence Length**: 256 tokens (sentence-transformers config)
- **Task**: Sentence Similarity
- **Use Case**: Fast inference, resource-constrained environments
- **Example**:
  ```bash
  ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
    -e "test_model=RedHatAI/all-MiniLM-L6-v2" \
    -e "scenario=all"
  ```

#### 2. RedHatAI/nomic-embed-text-v1.5
- **Size**: 0.1B parameters (137M)
- **Max Sequence Length**: 8192 tokens (trained on 2048)
- **Task**: Sentence Similarity
- **Use Case**: General-purpose embeddings, good balance of quality and speed
- **Example**:
  ```bash
  ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
    -e "test_model=RedHatAI/nomic-embed-text-v1.5" \
    -e "scenario=baseline"
  ```

#### 3. RedHatAI/granite-embedding-english-r2
- **Size**: 0.1B parameters (109M)
- **Max Sequence Length**: 8192 tokens
- **Task**: Feature Extraction
- **Use Case**: English-only embeddings, enterprise applications
- **Example**:
  ```bash
  ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
    -e "test_model=RedHatAI/granite-embedding-english-r2" \
    -e "scenario=latency"
  ```

#### 4. RedHatAI/embeddinggemma-300m
- **Size**: 0.3B parameters
- **Max Sequence Length**: 2048 tokens
- **Task**: Sentence Similarity
- **Use Case**: Medium-quality embeddings with reasonable compute requirements
- **Example**:
  ```bash
  ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
    -e "test_model=RedHatAI/embeddinggemma-300m" \
    -e "scenario=baseline"
  ```

### Large Models (> 1B parameters)

#### 5. RedHatAI/Qwen3-Embedding-8B
- **Size**: 8B parameters
- **Max Sequence Length**: 40960 tokens (40K context!)
- **Task**: Feature Extraction
- **Use Case**: High-quality embeddings, semantic search, RAG applications, long documents
- **Example**:
  ```bash
  ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
    -e "test_model=RedHatAI/Qwen3-Embedding-8B" \
    -e "scenario=all" \
    -e "requested_cores=32"  # Larger model needs more cores
  ```

## Test Scenarios

The `scenario` parameter controls which test suite to run:

### baseline
Finds maximum throughput and tests at configurable load levels (default: 25%, 50%, 75%):
- Infinite rate test to determine max throughput
- Fixed-rate tests at percentage intervals

```bash
# Use default percentages (25, 50, 75)
-e "scenario=baseline"

# Customize load percentages
-e "scenario=baseline" \
-e "baseline_load_percentages=[10,25,50,75,90]"
```

### latency
Tests concurrent request handling at different concurrency levels:
- Default levels: [16, 32, 64, 128, 196]
- Measures P50, P90, P99 latencies

```bash
-e "scenario=latency"
```

### all
Runs both baseline and latency test suites:

```bash
-e "scenario=all"
```

## Configuration Examples

### Production Testing (Managed Mode)
```bash
# Managed mode: Two-node setup with optimal resource isolation
export DUT_HOSTNAME=10.0.1.100
export LOADGEN_HOSTNAME=10.0.1.101
export HF_TOKEN=hf_xxxxx

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/Qwen3-Embedding-8B" \
  -e "scenario=all" \
  -e "requested_cores=64" \
  -e "use_persistent_cache=true" \
  -e "model_cache_dir=/mnt/nvme/hf-cache"
```

### Development Testing (DUT-Only Mode)
```bash
# Single-node development setup
export DUT_HOSTNAME=localhost
export VLLM_MODE=dut-only

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/all-MiniLM-L6-v2" \
  -e "scenario=baseline" \
  -e "requested_cores=16"
```

### Cloud/K8s Testing (External Mode)
```bash
# Test against running production endpoint
export LOADGEN_HOSTNAME=test-runner.example.com
export VLLM_MODE=external
export VLLM_ENDPOINT_URL=https://vllm-prod.k8s.cluster:8000

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "scenario=latency"
# test_model auto-detected from /v1/models endpoint
```

## Performance Tuning

### CPU Core Allocation

For larger models (> 1B parameters), allocate more CPU cores:

```bash
# Small models (< 500M parameters)
-e "requested_cores=16"

# Medium models (500M - 2B parameters)
-e "requested_cores=32"

# Large models (> 2B parameters)
-e "requested_cores=64"
```

### Socket Pinning

For NUMA systems, pin vLLM and benchmark to different sockets:

```bash
# Pin vLLM to socket 1, GuideLLM to socket 0
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/Qwen3-Embedding-8B" \
  -e "requested_cores=32" \
  -e "vllm_cpu_start=64" \
  -e "vllm_numa_node=1" \
  -e "guidellm_cpus=0-31" \
  -e "guidellm_numa_node=0"
```

### Model Caching

Enable persistent model caching to avoid re-downloading on each test:

```bash
-e "use_persistent_cache=true" \
-e "model_cache_dir=/mnt/nvme/hf-cache"
```

See [Model Pre-Download Documentation](ansible/model-predownload.md) for details.

### Customizing Baseline Load Percentages

By default, baseline tests run at 25%, 50%, and 75% of maximum throughput. You can customize these percentages:

```bash
# Default behavior (25%, 50%, 75%)
ansible-playbook embedding-benchmark.yml \
  -e "scenario=baseline"

# Custom percentages for fine-grained analysis
ansible-playbook embedding-benchmark.yml \
  -e "scenario=baseline" \
  -e "baseline_load_percentages=[10,25,50,75,90,95]"

# Focus on high-load scenarios
ansible-playbook embedding-benchmark.yml \
  -e "scenario=baseline" \
  -e "baseline_load_percentages=[80,85,90,95,99]"

# Quick test with fewer data points
ansible-playbook embedding-benchmark.yml \
  -e "scenario=baseline" \
  -e "baseline_load_percentages=[50,75]"
```

**Use Cases:**
- **Fine-grained saturation curves**: `[10,20,30,40,50,60,70,80,90,95]`
- **High-load focus**: `[75,80,85,90,95,99]` - Find breaking point
- **Quick validation**: `[50]` - Single mid-point check
- **Custom SLO testing**: `[60,80]` - Match your target load levels

**Results:**
Files are generated as `sweep-{percentage}pct.json` (e.g., `sweep-10pct.json`, `sweep-95pct.json`)

## Benchmark Parameters

Override default benchmark settings:

```bash
# Adjust number of test prompts (trade-off: sample size vs duration)
-e "num_prompts=500"  # Default: 250

# Set input token length for random text generation
-e "embedding_random_input_len=1024"  # Default: 512
# Options: 128, 256, 512, 1024, 2048, 4096, 8192
# Use smaller values for quick tests, larger to test model limits

# Use containerized benchmark tool (default: true)
-e "use_container=true"

# Custom vllm-bench container image
-e "vllm_bench_image=docker.io/vllm/vllm-openai-cpu:v0.20.0"
```

**Example: Test different input lengths**
```bash
# Short inputs (128 tokens)
ansible-playbook embedding-benchmark.yml \
  -e "test_model=RedHatAI/all-MiniLM-L6-v2" \
  -e "embedding_random_input_len=128" \
  -e "test_name=short-input" \
  -e "scenario=all"

# Long inputs (2048 tokens)
ansible-playbook embedding-benchmark.yml \
  -e "test_model=RedHatAI/nomic-embed-text-v1.5" \
  -e "embedding_random_input_len=2048" \
  -e "test_name=long-input" \
  -e "scenario=all"
```

Configuration in `inventory/group_vars/all/benchmark-tools.yml`:
```yaml
vllm_bench:
  use_container: true
  container_image: docker.io/vllm/vllm-openai-cpu:v0.20.0
  num_prompts: 250
```

## Architecture Support

The framework **automatically detects system architecture** and selects appropriate container images for both the vLLM server (DUT) and benchmark tools (load generator).

### Supported Architectures

| Architecture | vLLM Server Image | vllm-bench/GuideLLM Image |
|--------------|-------------------|---------------------------|
| **x86_64/amd64** | `docker.io/vllm/vllm-openai-cpu:v0.20.0` | `docker.io/vllm/vllm-openai-cpu:v0.20.0` |
| **aarch64/arm64** | `quay.io/mtahhan/vllm:arm-base-cpu` | `quay.io/mtahhan/vllm:arm-base-cpu` |

### How It Works

Architecture detection runs automatically on **both hosts**:
- **DUT (vLLM Server)**: Detects architecture and selects vLLM server container image
- **Load Generator**: Detects architecture and selects benchmark tool container image

```bash
# No special configuration needed - architecture is detected automatically
export DUT_HOSTNAME=x86-server.example.com
export LOADGEN_HOSTNAME=arm-loadgen.example.com  # Different architecture? No problem!

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2"
```

### Override Container Images

To use custom container images, set environment variables:

```bash
# Override vLLM server image (DUT)
export VLLM_CONTAINER_IMAGE=your-registry/custom-vllm:latest

# Override vllm-bench image (load generator)
export VLLM_BENCH_CONTAINER_IMAGE=your-registry/custom-vllm-bench:latest

# Override GuideLLM image (for LLM testing)
export GUIDELLM_CONTAINER_IMAGE=your-registry/custom-guidellm:latest
```

**Note**: Environment variable overrides take precedence over architecture auto-detection.

### Using Red Hat AI Inference Server (RHAIIS) Images

Red Hat provides enterprise-grade vLLM images optimized for Intel Xeon and AMD EPYC processors. These images require authentication to Red Hat's container registry.

#### Prerequisites

1. **Authenticate with Red Hat registry and pull image** (one-time setup):
   ```bash
   # SSH to your DUT
   ssh admin@your-dut-hostname
   
   # Login and pull with sudo (both commands must use sudo together)
   sudo podman login registry.redhat.io  # Enter Red Hat customer portal credentials
   sudo podman pull registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
   ```
   
   **Important:** Both `login` and `pull` must use `sudo` together (or neither should use `sudo`). Root and regular user have separate credential stores, so mixing will fail.

   **Why manual pull?** Ansible cannot automatically pull authenticated images. You must pull the image manually on the DUT before running tests.

3. **Set the image environment variable**:
   ```bash
   # On your control machine (where you run ansible-playbook)
   export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
   ```

#### Complete Example

```bash
# Step 1: On DUT - Login and pull image (one time)
ssh admin@10.19.26.252
sudo podman login registry.redhat.io  # Enter Red Hat credentials
sudo podman pull registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
exit

# Step 2: On control machine - Run benchmark
export DUT_HOSTNAME=10.19.26.252
export LOADGEN_HOSTNAME=10.19.26.200
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "scenario=all" \
  -e "requested_cores=16"
```

#### Red Hat AI Image Configuration

The framework automatically detects and configures Red Hat AI images with the correct environment variables:
- `HF_HOME=/opt/app-root/src/.cache/huggingface` (different from default `/root/.cache/huggingface`)
- `HF_HUB_OFFLINE=0` (enable network access for model downloads)
- `MALLOC_TRIM_THRESHOLD_=-1` (memory optimization)

**Reference**: [Red Hat AI Inference Documentation](https://docs.redhat.com/en/documentation/red_hat_ai_inference/3.4/html/getting_started/about-cpu-inference_getting-started)

## Results Collection

Test results are collected in:
```
results/embedding/<model-name>/<timestamp>/
├── baseline/                # Created when scenario=baseline or all
│   ├── sweep-inf.json       # Max throughput test
│   ├── sweep-25pct.json     # 25% load test
│   ├── sweep-50pct.json     # 50% load test
│   └── sweep-75pct.json     # 75% load test
├── latency/                 # Created when scenario=latency or all
│   ├── concurrent-16.json   # Concurrency level tests
│   ├── concurrent-32.json
│   ├── concurrent-64.json
│   ├── concurrent-128.json
│   └── concurrent-196.json
├── test-metadata.json       # Test run metadata
└── logs/
    └── vllm-server.log      # vLLM server logs (managed/dut-only modes only)
```

## Adding Custom Models

To test a custom embedding model:

1. Ensure the model is compatible with vLLM's embedding support
2. Use the model's HuggingFace ID:
   ```bash
   -e "test_model=your-org/your-embedding-model"
   ```
3. Set HF_TOKEN if the model is gated:
   ```bash
   export HF_TOKEN=hf_xxxxx
   ```

## Troubleshooting

### Model Not Found
```
Error: Model not found in /v1/models
```
**Solution**: Verify model ID is correct and HF_TOKEN is set for gated models

### Network Connectivity (Managed Mode)
```
Error: Connection refused on port 8000
```
**Solution**: Check security groups, firewall rules, verify DUT is binding to 0.0.0.0

### Insufficient Memory
```
Error: CUDA out of memory / Insufficient memory
```
**Solution**: Reduce model size or increase allocated CPU cores

### External Endpoint Not Accessible
```
Error: Failed to connect to VLLM_ENDPOINT_URL
```
**Solution**: Verify URL format, network accessibility, and endpoint is running

## See Also

- [Getting Started Guide](getting-started.md)
- [Model Pre-Download](ansible/model-predownload.md)
- [Test Execution Guide](ansible/test-execution.md)
- [Methodology Overview](methodology/overview.md)
