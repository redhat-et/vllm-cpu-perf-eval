# RHAIIS LLM Concurrent Load Testing Guide
# Overview

This guide covers running concurrent load tests on RHAIIS (Red Hat AI Inference Service) quantized models.
# Prerequisites

1. **Pull the RHAIIS container image on the DUT:**
   ```bash
   podman pull registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
   ```

2. **Set the container image environment variable:**
   ```bash
   export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
   ```

3. **Set HuggingFace token (if needed):**
   ```bash
   export HF_TOKEN=hf_xxxxx
   ```

4. **REQUIRED: Set LD_PRELOAD for optimal performance:**
   ```bash
   export LD_PRELOAD=/usr/lib64/libomp.so
   ```

   This enables Intel OpenMP for best inference performance with RHAIIS images. **Without this, you will see significantly degraded latency.**

5. **Optional: Configure test duration (default 600 seconds):**

   **⚠️ IMPORTANT:** Test duration significantly impacts result stability. Shorter tests (< 300s) will show **erratic spikes** in P95/P99 metrics due to warmup effects and insufficient sample size.

   **Recommended durations:**
   - **600 seconds (10 min)** - DEFAULT, use for production benchmarks ✅
     - Stable P95/P99 metrics (< 5% variance)
     - Warmup effects < 5% of samples
     - ≥ 5000 requests for statistical confidence
   - **300 seconds (5 min)** - Acceptable for development testing ⚠️
     - Reasonable P95 stability, P99 less stable
     - 2x faster iteration than 600s
     - Good compromise for quick validation
   - **180 seconds (3 min)** - NOT RECOMMENDED for benchmarks ❌
     - Unstable P95/P99 (25-50% variance between runs)
     - Warmup dominates (17-33% of test time)
     - Only use for smoke tests, not performance comparison

   **Configuration examples:**
   ```bash
   # Development testing (5 minutes)
   export GUIDELLM_MAX_SECONDS=300
   export GUIDELLM_REQUEST_TIMEOUT=300

   # Production benchmarks (10 minutes - default, most stable)
   export GUIDELLM_MAX_SECONDS=600
   export GUIDELLM_REQUEST_TIMEOUT=600

   # Quick smoke test only (3 minutes - expect spikes!)
   export GUIDELLM_MAX_SECONDS=180
   export GUIDELLM_REQUEST_TIMEOUT=180
   ```

   **Why this matters:** Shorter tests show erratic P95/P99 due to: (1) warmup effects dominating samples, (2) insufficient request count for statistical stability, (3) GC pauses causing visible spikes.
# RHAIIS Models to Test

The test suite includes 5 quantized models:

| Model | Description | Quantization | Context Length | Workload Support |
|-------|-------------|--------------|----------------|------------------|
| `RedHatAI/Qwen3-8B-quantized.w4a16` | Qwen3 8B | w4a16 | 32768 | ✅ All workloads |
| `RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16` | Llama 3.1 8B | w4a16 | 131072 | ✅ All workloads |
| `RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8` | Llama 3.1 8B | w8a8 | 131072 | ✅ All workloads |
| `RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4` | TinyLlama 1.1B | Pruned | **2048** | ⚠️ **Chat only** |
| `RedHatAI/Qwen3-8B-W8A8-INT8` | Qwen3 8B | W8A8-INT8 | 32768 | ⚠️ **Skip - Known Issue** |

## TinyLlama Context Window Limitation

**⚠️ CRITICAL:** TinyLlama has a maximum context window of **2048 tokens** (`max_position_embeddings=2048`), which creates a hard limit on Input Sequence Length (ISL). This is a **model architecture limitation**, not a configuration issue.

### Workload Compatibility Analysis

| Workload | ISL (Input) | OSL (Output) | Total Needed | TinyLlama Limit | Status |
|----------|-------------|--------------|--------------|-----------------|--------|
| **Chat** | 512 | 512 | 1024 | 2048 | ✅ **Compatible** |
| **Code** | 1024 | 1024 | 2048 | 2048 | ⚠️ **Exact fit** (no headroom) |
| **Summarization** | **2048** | 256 | 2304 | 2048 | ❌ **ISL too large** |
| **RAG** | **7680** | 512 | 8192 | 2048 | ❌ **ISL way too large** |

### Why Summarization and RAG Fail

**Summarization workload:**
```
ISL (document to summarize):  2048 tokens
TinyLlama max context:        2048 tokens
Space remaining for output:   0 tokens (2048 - 2048 = 0)
OSL needed:                   256 tokens
Result:                       IMPOSSIBLE ❌
```

The **input alone** fills TinyLlama's entire context window, leaving no space for output generation.

**RAG workload:**
```
ISL (retrieved context):      7680 tokens
TinyLlama max context:        2048 tokens
Result:                       Input exceeds model capacity by 3.75x ❌
```

### Technical Details

**Why this is not a configuration issue:**
- TinyLlama's `max_position_embeddings=2048` is hardcoded in the model architecture
- Cannot be increased without retraining the model
- Each workload in `test-workloads.yml` sets `--max-model-len` based on workload requirements (e.g., 4096 for summarization)
- vLLM validates: `max_model_len ≤ max_position_embeddings`
- **Validation fails because:** 4096 (workload requirement) > 2048 (model maximum)

**Error message you'll see:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ModelConfig
  Value error, User-specified max_model_len (4096) is greater than the
  derived max_model_len (max_position_embeddings=2048.0)
```

### Recommendations

**For testing:**
- ✅ Use TinyLlama only for **chat workload** quick validation
- ✅ Use Llama 3.1 8B or Qwen3 8B for comprehensive workload testing
- ✅ When running `--models tiny`, explicitly specify `--workloads chat`

**Command examples:**
```bash
# ✅ GOOD: TinyLlama with chat only
./run-rhaiis-concurrent-load.sh --models tiny --workloads chat --cores 8

# ❌ WILL FAIL: TinyLlama with summarization
./run-rhaiis-concurrent-load.sh --models tiny --workloads summarization

# ✅ GOOD: Use continue-on-error to test other models even if TinyLlama fails
./run-rhaiis-concurrent-load.sh --models all --continue-on-error
```

**Bottom line:** This is a **fundamental model limitation**, not a bug or misconfiguration. TinyLlama (1.1B parameters, 2K context) is designed for lightweight chat applications, not long-context workloads like summarization or RAG.

---

### Qwen3-8B-W8A8-INT8 Quantization Issue

**⚠️ CRITICAL:** The `RedHatAI/Qwen3-8B-W8A8-INT8` model **fails to load** in RHAIIS 3.4.0 due to a quantization configuration validation error.

#### Error Details

**Error message:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for VllmConfig
  Value error, Must use group quantization strategy in order to apply activation ordering
```

**Root cause:**
- Model's quantization config has `'actorder': 'weight'`
- RHAIIS vLLM 0.18.0+rhaiv.7 requires **group quantization** when activation ordering is used
- The model's quantization scheme is incompatible with this vLLM version

**Impact:**
- ❌ Model fails during initialization before any workload can run
- ❌ Affects all workloads (chat, code, summarization, rag)
- ❌ Cannot be worked around with configuration changes

**Workaround:**
Skip this model when running test suites:
```bash
./run-rhaiis-concurrent-load.sh \
  --models all \
  --skip-models "RedHatAI/Qwen3-8B-W8A8-INT8" \
  --continue-on-error
```

Or use the other Qwen3 model which works fine:
```bash
./run-rhaiis-concurrent-load.sh \
  --models "RedHatAI/Qwen3-8B-quantized.w4a16"  # ✅ Works
```

**Status:**
- **Tested with:** RHAIIS 3.4.0 (`registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0`)
- **Platform:** AWS EC2 c8i.metal-48xl (eu-west-1)
- **Date:** 2026-06-08

This is a **known compatibility issue** between the model's quantization scheme and the RHAIIS vLLM version. It may be resolved in future RHAIIS releases.

---

## NUMA/Socket Configuration

### Determining Your System Topology

First, check your system's NUMA topology:

```bash
lscpu | grep NUMA
numactl --hardware
```

### Recommended Configurations

#### Single-Socket Systems
No socket separation needed - let auto-detect handle it:
```bash
# No NUMA parameters needed
./run-rhaiis-concurrent-load.sh
```

#### 2-Socket Systems (RECOMMENDED CONFIGURATION)
Separate vLLM and GuideLLM to different sockets:

**Example: 2 × 64-core sockets (128 cores total)**
```bash
# vLLM on socket 1 (cores 64-127)
export VLLM_CPU_START=64
export VLLM_NUMA_NODE=1

# GuideLLM on socket 0 (cores 0-31)
export GUIDELLM_CPUS=0-31
export GUIDELLM_NUMA_NODE=0
```

**Example: 2 × 48-core sockets (96 cores total)**
```bash
# vLLM on socket 1 (cores 48-95)
export VLLM_CPU_START=48
export VLLM_NUMA_NODE=1

# GuideLLM on socket 0 (cores 0-31)
export GUIDELLM_CPUS=0-31
export GUIDELLM_NUMA_NODE=0
```

#### 3+ Socket Systems
Auto-detection handles this optimally - no manual config needed.

### Via Command Line

Alternatively, pass NUMA parameters directly:

```bash
./run-rhaiis-concurrent-load.sh \
  --vllm-cpu-start 64 \
  --vllm-numa-node 1 \
  --guidellm-cpus 0-31 \
  --guidellm-numa-node 0
```

## Test Configuration

### Core Counts
- 8 cores
- 16 cores
- 32 cores

### Workloads
- **Chat**: Standard chat interactions (512:512 tokens)
- **Code**: Code generation (1024:1024 tokens)
- **Summarization**: Document summarization (2048:256 tokens)
- **RAG**: Retrieval-Augmented Generation (7680:512 tokens, max-model-len=8192)

### Test Phases
- **Phase 1** (default): Baseline tests with fixed tokens, no caching
- **Phase 2**: Realistic tests with variable tokens, no caching
- **Phase 3**: Production tests with realistic datasets and caching enabled

## Quick Start

### Using the Automated Script

The easiest way to run the full test suite:

```bash
cd ../../automation/test-execution/scripts/bash

# ⚠️ CRITICAL: Set LD_PRELOAD for optimal RHAIIS performance
export LD_PRELOAD=/usr/lib64/libomp.so

# Set container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

# For 2-socket systems: Set socket separation (RECOMMENDED)
export VLLM_CPU_START=64           # vLLM on socket 1
export VLLM_NUMA_NODE=1            # vLLM NUMA node 1
export GUIDELLM_CPUS=0-31          # GuideLLM on socket 0
export GUIDELLM_NUMA_NODE=0        # GuideLLM NUMA node 0

# Run all models, all workloads, all core counts (Phase 1)
./run-rhaiis-concurrent-load.sh
```

### Why Socket Separation Matters

On **2-socket systems**, vLLM and GuideLLM will share the same NUMA node by default, causing:
- ❌ Cross-socket memory access
- ❌ CPU contention between vLLM and GuideLLM
- ❌ Lower performance

**Solution**: Explicitly separate them to different sockets for best performance.

### Test Specific Models

```bash
# Test only Llama models
./run-rhaiis-concurrent-load.sh --models llama --cores 16,32

# Test only Qwen models
./run-rhaiis-concurrent-load.sh --models qwen

# Test TinyLlama only (quick test)
./run-rhaiis-concurrent-load.sh --models tiny --cores 8 --workloads chat
```

### Test Specific Workloads

```bash
# Chat and RAG only
./run-rhaiis-concurrent-load.sh --workloads chat,rag --cores 16

# Single model, single workload
./run-rhaiis-concurrent-load.sh \
  --models "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16" \
  --workloads chat \
  --cores 16
```

### Dry Run (Preview)

```bash
# See what would be executed without running
./run-rhaiis-concurrent-load.sh --dry-run
```

### Custom Test Duration

Run tests with shorter duration (e.g., 5 minutes instead of default 10 minutes):

```bash
# Set custom duration via environment variables
export GUIDELLM_MAX_SECONDS=300
export GUIDELLM_REQUEST_TIMEOUT=300

# Run tests (will use 300 seconds)
./run-rhaiis-concurrent-load.sh --models tiny --cores 8
```

## Deployment Modes

### Single Machine (Managed Mode)
Both vLLM and GuideLLM run on the same machine. This is the **default and recommended** setup for RHAIIS testing.

**Environment Setup:**
```bash
# ⚠️ CRITICAL: Must set LD_PRELOAD for optimal RHAIIS performance
export LD_PRELOAD=/usr/lib64/libomp.so

export DUT_HOSTNAME=your-ec2-instance.compute.amazonaws.com
export LOADGEN_HOSTNAME=your-ec2-instance.compute.amazonaws.com  # Same as DUT
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_SSH_KEY=~/your-key.pem

# For 2-socket systems: separate vLLM and GuideLLM to different sockets
export VLLM_CPU_START=64
export VLLM_NUMA_NODE=1
export GUIDELLM_CPUS=0-31
export GUIDELLM_NUMA_NODE=0
```

**Note:** You do NOT need to set `VLLM_MODE`. The LLM benchmarks use `managed` mode by default, which works for both single-machine and separate-machine setups.

### Separate Machines (Managed Mode)
vLLM runs on DUT, GuideLLM runs on separate load generator machine.

```bash
export DUT_HOSTNAME=vllm-server.example.com
export LOADGEN_HOSTNAME=loadgen.example.com  # Different machine
```

### External vLLM Instance
Connect to an already-running vLLM instance:

```bash
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-vllm-instance:8000
```

## Manual Execution

If you prefer to run tests manually using Ansible directly:

```bash
cd automation/test-execution/ansible

# ⚠️ CRITICAL: Must set LD_PRELOAD for optimal performance
export LD_PRELOAD=/usr/lib64/libomp.so

# Set container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

# Run single model/workload combination (Phase 1 only) with socket separation
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16" \
  -e "base_workload=chat" \
  -e "requested_cores=16" \
  -e "vllm_cpu_start=64" \
  -e "vllm_numa_node=1" \
  -e "guidellm_cpus=0-31" \
  -e "guidellm_numa_node=0" \
  -e "skip_phase_2=true" \
  -e "skip_phase_3=true"

# Run with RAG workload (uses max-model-len=8192)
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=RedHatAI/Qwen3-8B-quantized.w4a16" \
  -e "base_workload=rag" \
  -e "requested_cores=32" \
  -e "vllm_cpu_start=64" \
  -e "vllm_numa_node=1" \
  -e "guidellm_cpus=0-31" \
  -e "guidellm_numa_node=0" \
  -e "skip_phase_2=true" \
  -e "skip_phase_3=true"
```

## Workload Details

### Chat (512:512)
- Input: 512 tokens
- Output: 512 tokens
- Use case: Standard conversational AI
- vLLM: `max-model-len=2048`

### Code (1024:1024)
- Input: 1024 tokens
- Output: 1024 tokens
- Use case: Code generation
- vLLM: `max-model-len=4096`

### Summarization (2048:256)
- Input: 2048 tokens
- Output: 256 tokens
- Use case: Document summarization
- vLLM: `max-model-len=4096`

### RAG (7680:512)
- Input: 7680 tokens (long context retrieval)
- Output: 512 tokens (concise answer)
- Use case: Retrieval-Augmented Generation
- vLLM: `max-model-len=8192` ✅

## Test Execution Notes

### Single Instance vLLM
All tests use a single vLLM instance per test. The Ansible playbook manages:
- Starting vLLM container with specified core count
- CPU pinning and NUMA configuration
- Model loading
- Test execution
- Container cleanup

### Single DUT
Tests run on a single Device Under Test (DUT). The load generator (GuideLLM) can run on:
- The same machine as vLLM
- A separate load generator machine (configured in `inventory/hosts.yml`)

## Results

Results are saved to:
```
results/llm/<model-name>/<workload>-<cores>C.json
```

View results in the dashboard:
```bash
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh
```

## Example: Full Test Sweep

```bash
#!/bin/bash
# Complete RHAIIS test sweep for Phase 1

# ⚠️ CRITICAL: Must set LD_PRELOAD for optimal performance
export LD_PRELOAD=/usr/lib64/libomp.so

export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

cd ../../automation/test-execution/scripts/bash

# Run all 5 models × 3 core counts × 4 workloads = 60 tests
./run-rhaiis-concurrent-load.sh \
  --models all \
  --cores 8,16,32 \
  --workloads chat,code,summarization,rag \
  --phase 1 \
  --continue-on-error
```

## Troubleshooting

### Erratic P95/P99 Spikes in Results

**If you see inconsistent spikes in P95/P99 latency between test runs**, the most likely cause is **test duration too short**:

```bash
# ❌ TOO SHORT - causes unstable metrics
export GUIDELLM_MAX_SECONDS=180   # Only 3 minutes

# ✅ BETTER - acceptable for development
export GUIDELLM_MAX_SECONDS=300   # 5 minutes

# ✅ BEST - stable production metrics
export GUIDELLM_MAX_SECONDS=600   # 10 minutes (default)
```

**Symptoms of insufficient test duration:**
- P99 latency varies 25-50% between identical test runs
- Large gap between P95 and P99 (2-3x difference)
- Spikes appear inconsistently (different runs show different patterns)
- Early requests (first 30-60s) have much higher latency

**Root causes:**
1. **Warmup dominates** - First 30-60s are warmup (cold cache, JIT, allocation)
   - 180s test: Warmup is 17-33% of samples ❌
   - 600s test: Warmup is 5-10% of samples ✅
2. **Insufficient samples** - P99 needs ≥5000 requests for stability
   - 180s test: ~1500-3000 requests ❌
   - 600s test: ~5000-10000 requests ✅
3. **GC artifacts** - Single garbage collection pauses cause visible spikes
   - 180s test: Only 1-2 GC events ❌
   - 600s test: 6+ GC events averaged out ✅

**Solution:**
- For **production benchmarks**: Use 600s (default)
- For **development testing**: Use 300s minimum
- For **smoke tests only**: 180s acceptable (but ignore P95/P99 spikes)

### ⚠️ CRITICAL: Poor Latency / Performance Issues

**If you see significantly degraded latency or poor performance**, the most common cause is missing `LD_PRELOAD`:

```bash
# ✅ REQUIRED for RHAIIS - must be set before running tests
export LD_PRELOAD=/usr/lib64/libomp.so
```

**Symptoms without LD_PRELOAD:**
- TTFT (Time To First Token) is 5-10x slower than expected
- ITL (Inter-Token Latency) is significantly higher
- Overall throughput is much lower than vendor benchmarks

**Why it matters:**
- `LD_PRELOAD=/usr/lib64/libomp.so` loads Intel OpenMP library
- This provides optimized threading and memory allocation for CPU inference
- Without it, vLLM uses default system libraries which are not optimized for this workload

### Model Loading Issues
If models fail to load, ensure:
- RHAIIS container image is pulled on DUT
- HuggingFace token is set (if model is gated)
- Sufficient memory for model + KV cache

### RAG Workload Context Length

**Issue:** RAG workload was failing with all requests getting HTTP 400 errors due to tokenization overhead.

**Root Cause:**
- RAG configuration: ISL=7680, OSL=512, max_model_len=8192
- Actual tokenized prompt: 7681 tokens (not 7680)
- Total required: 7681 + 512 = **8193 tokens**
- Maximum allowed: 8192 tokens
- Result: All requests rejected with `VLLMValidationError`

**Fix:** Increased `max-model-len` to **8320** to account for tokenization overhead and provide headroom.

RAG workload requires models with context length >= 8192. The configuration automatically sets `--max-model-len=8320` for RAG tests (increased from 8192 to handle tokenization overhead).

### Container Image
The script will warn if `VLLM_CONTAINER_IMAGE` is not set. For RHAIIS testing, always set:
```bash
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
```

## Advanced Options

### Custom Core Counts
```bash
./run-rhaiis-concurrent-load.sh --cores 4,8,12,16,20,24
```

### Skip Specific Models
```bash
./run-rhaiis-concurrent-load.sh \
  --models all \
  --skip-models "RedHatAI/Qwen3-8B-W8A8-INT8"
```

### Continue on Error
```bash
./run-rhaiis-concurrent-load.sh --continue-on-error
```
This will continue testing remaining models even if one fails.

## Script Reference

### run-rhaiis-concurrent-load.sh Options

| Option | Description | Default |
|--------|-------------|---------|
| `--models` | Comma-separated models or preset (all\|llama\|qwen\|tiny) | all |
| `--cores` | Comma-separated core counts | 8,16,32 |
| `--workloads` | Comma-separated workloads | chat,code,summarization,rag |
| `--phase` | Test phase (1\|2\|3\|all) | 1 |
| `--skip-models` | Models to skip | - |
| `--continue-on-error` | Continue if a test fails | false |
| `--dry-run` | Preview without executing | false |
| `-h, --help` | Show help | - |

### Model Presets

- **all**: All 5 RHAIIS models
- **llama**: Llama 3.1 models (w4a16, w8a8)
- **qwen**: Qwen3 models (w4a16, W8A8-INT8)
- **tiny**: TinyLlama pruned model only

## Related Documentation

- [Concurrent Load Test Suite](concurrent-load.md)
- [3-Phase Testing Methodology](../../docs/methodology/testing-phases.md)
- [Test Workload Configurations](../../automation/test-execution/ansible/inventory/group_vars/all/test-workloads.yml)
- [RHAIIS Test Script](../../automation/test-execution/scripts/bash/run-rhaiis-concurrent-load.sh)
- **[vLLM KV Cache Configuration Guide](../../docs/vllm-kv-cache-configuration.md)** - Deep dive into max_model_len, KV cache sizing, and block_size for optimal performance
