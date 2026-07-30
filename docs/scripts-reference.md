---
layout: default
title: Scripts Reference
---

Complete reference for all test execution and utility scripts in the repository.

## High-Level Test Execution Scripts

Located in `automation/test-execution/scripts/`

### [run-embedding-suite.sh](../automation/test-execution/scripts/bash/run-embedding-suite.sh)

**Purpose:** Run comprehensive performance benchmarks across all embedding models and core counts.

**Location:** `automation/test-execution/scripts/bash/run-embedding-suite.sh`

**Quick Examples:**
```bash
cd automation/test-execution/scripts

# Run all models on all core counts (default: 4,8,16,32)
./bash/run-embedding-suite.sh

# Quick smoke test
./bash/run-embedding-suite.sh --models quick --cores 4 --num-prompts 10

# Test small models only
./bash/run-embedding-suite.sh --models small --cores 8,16,32

# Skip the 8B model
./bash/run-embedding-suite.sh --skip-models "RedHatAI/Qwen3-Embedding-8B"
```

**Model Presets:**
- `all` - All 5 models (22M to 8B)
- `small` - all-MiniLM (22M), granite-english (109M)
- `medium` - nomic-embed (137M), embeddinggemma (300M)
- `large` - Qwen3-Embedding-8B
- `quick` - all-MiniLM-L6-v2 only

**Full Documentation:** Run `./bash/run-embedding-suite.sh --help`

---

### [run-mteb-model-sweep.sh](../automation/test-execution/scripts/bash/run-mteb-model-sweep.sh)

**Purpose:** Run MTEB quality benchmarks on all embedding models.

**Location:** `automation/test-execution/scripts/bash/run-mteb-model-sweep.sh`

**Default Configuration:**
- **Cores:** 4 (most efficient for quality tests - quality metrics don't change with core count)
- **Task Preset:** quick (2 tasks, ~10-25 minutes)

**Quick Examples:**
```bash
cd automation/test-execution/scripts

# Run quick tests on all models (~10-25 min, 4 cores default)
./bash/run-mteb-model-sweep.sh

# Comprehensive quality evaluation (~1.7-2.5 hours)
./bash/run-mteb-model-sweep.sh --task-preset comprehensive

# Test specific models
./bash/run-mteb-model-sweep.sh \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2"

# Use more cores if needed (though won't affect quality scores)
./bash/run-mteb-model-sweep.sh --cores 16
```

**Task Presets:**

| Preset | Tasks | Time (5 models) |
|--------|-------|-----------------|
| quick | 2 | 10-25 min |
| retrieval | 3 | 50-75 min |
| classification | 3 | 25-50 min |
| sts | 3 | 15-40 min |
| comprehensive | 5 | 100-150 min |

**Note:** Clustering tasks are currently disabled due to segmentation faults.

**Full Documentation:**
- Run `./bash/run-mteb-model-sweep.sh --help`
- [MTEB Sweep Guide](mteb-sweep-guide.md)
- [MTEB Timing Guide](mteb-timing-guide.md)
- [MTEB Troubleshooting](mteb-troubleshooting.md)

---

### [reorganize-mteb-results.sh](../automation/test-execution/scripts/bash/reorganize-mteb-results.sh)

**Purpose:** Reorganize MTEB results from nested directory structure to flat format.

**Location:** `automation/test-execution/scripts/bash/reorganize-mteb-results.sh`

**Usage:**
```bash
# Reorganize default results directory
./bash/reorganize-mteb-results.sh

# Reorganize custom directory
./bash/reorganize-mteb-results.sh /path/to/results/mteb
```

**Note:** The dashboard now handles both formats automatically, so this is optional.

---

### [fix-mteb-results-structure.sh](../automation/test-execution/scripts/bash/fix-mteb-results-structure.sh)

**Purpose:** Fix MTEB results directory structure for dashboard compatibility.

**Location:** `automation/test-execution/scripts/bash/fix-mteb-results-structure.sh`

**What it does:**
- Converts nested `no_model_name_available/no_revision_available/*.json` to `TaskName/test.json`
- Fixes root-level JSON files from incorrect reorganization
- Preserves `run_summary.json` and `model_meta.json` metadata files
- Shows count of fixed files and expected structure

**Usage:**
```bash
cd automation/test-execution/scripts

# Fix default results directory (results/mteb/)
./bash/fix-mteb-results-structure.sh

# Fix custom directory
RESULTS_DIR=/path/to/results/mteb ./bash/fix-mteb-results-structure.sh
```

**When to use:**
- After running MTEB benchmarks with the vLLM MTEB container
- When MTEB results don't appear in the dashboard
- When you see nested `no_model_name_available` directories

**Expected structure after fix:**

Base path: `results/mteb/MODEL/TIMESTAMP/`

| File / directory | Description |
| --- | --- |
| `run_summary.json` | Test metadata |
| `model_meta.json` | Model metadata |
| `Banking77Classification/test.json` | Classification metrics (accuracy, F1) |
| `EmotionClassification/test.json` | Classification metrics |
| `<TaskName>/test.json` | Per-task MTEB results |

---

### [run-rhaiis-concurrent-load.sh](../automation/test-execution/scripts/bash/run-rhaiis-concurrent-load.sh)

**Purpose:** Run concurrent load benchmarks on RHAIIS quantized LLM models across different core counts and workload types.

**Location:** `automation/test-execution/scripts/bash/run-rhaiis-concurrent-load.sh`

**Prerequisites:**
- RHAIIS vLLM container image pulled on DUT:
  ```bash
  podman pull registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
  ```
- Set `VLLM_CONTAINER_IMAGE` to use custom image

**Quick Examples:**
```bash
cd automation/test-execution/scripts

# Run all models, all workloads, all core counts (Phase 1 only)
./bash/run-rhaiis-concurrent-load.sh

# Test specific models with specific workloads
./bash/run-rhaiis-concurrent-load.sh \
  --models "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16" \
  --workloads "chat,rag" \
  --cores "16,32"

# Quick test on 8 cores
./bash/run-rhaiis-concurrent-load.sh --models tiny --cores 8 --workloads chat

# Test Llama models only
./bash/run-rhaiis-concurrent-load.sh --models llama --cores 16

# Socket separation for 2-socket systems (recommended)
./bash/run-rhaiis-concurrent-load.sh \
  --vllm-cpu-start 64 \
  --vllm-numa-node 1 \
  --guidellm-cpus 0-31 \
  --guidellm-numa-node 0

# Test with Tensor Parallel (TP=2 for improved high-latency performance)
./bash/run-rhaiis-concurrent-load.sh \
  --models qwen \
  --cores 32 \
  --workloads "rag,summarization" \
  --tensor-parallel 2
```

**Model Presets:**
- `all` - All 5 RHAIIS quantized models
- `llama` - Llama models (3.1-8B w4a16, w8a8)
- `qwen` - Qwen models (8B w4a16, W8A8-INT8)
- `tiny` - TinyLlama pruned model

**Supported Workloads:**
- `chat` - 512:512 tokens (interactive conversations)
- `code` - 1024:1024 tokens (code generation)
- `summarization` - 2048:256 tokens (document summarization)
- `rag` - 8192:512 tokens (retrieval-augmented generation)

**Key Options:**
- `--models LIST` - Comma-separated models or preset (all|llama|qwen|tiny)
- `--cores LIST` - Comma-separated core counts (default: 8,16,32)
- `--workloads LIST` - Comma-separated workloads (default: chat,code,summarization,rag)
- `--phase PHASE` - Test phase (1|2|3|all, default: 1)
- `--tensor-parallel NUM` - Tensor parallelism (1|2|4|8, auto-calculated by default)
- `--vllm-cpu-start NUM` - Starting CPU for vLLM (socket separation)
- `--vllm-numa-node NUM` - NUMA node for vLLM
- `--guidellm-cpus RANGE` - CPU range for GuideLLM (e.g., 0-31)
- `--guidellm-numa-node NUM` - NUMA node for GuideLLM
- `--skip-models LIST` - Models to skip
- `--continue-on-error` - Continue if a model/workload fails
- `--dry-run` - Show what would run without executing

**Tensor Parallel (TP) Support:**

Tensor parallelism splits model layers across multiple NUMA nodes for improved performance on high-latency workloads (RAG, summarization).

- **Values:** 1 (no parallelism), 2, 4, or 8
- **Default:** Auto-calculated based on NUMA topology
- **When to use TP=2:** Large input contexts (RAG 8K, Summarization 2K) on 2-socket systems
- **Cores requirement:** Must be evenly divisible by TP value

**Full Documentation:** Run `./bash/run-rhaiis-concurrent-load.sh --help`

---

### [convert-embedding-results.py](../automation/test-execution/scripts/python/convert-embedding-results.py)

**Purpose:** Convert embedding benchmark JSON results to CSV format.

**Location:** `automation/test-execution/scripts/python/convert-embedding-results.py`

**Usage:**
```bash
# Convert all results
python python/convert-embedding-results.py

# Specify custom directory
python python/convert-embedding-results.py --results-dir ../../results/embedding

# Convert specific model
python python/convert-embedding-results.py --model "RedHatAI/all-MiniLM-L6-v2"

# Custom output file
python python/convert-embedding-results.py --output my-metrics.csv
```

---

## Ansible-Specific Scripts

Located in `automation/test-execution/ansible/scripts/`

### run-core-sweep.sh

**Purpose:** Run tests across multiple core counts for performance analysis.

**Location:** `automation/test-execution/ansible/scripts/run-core-sweep.sh`

**Usage:**
```bash
# Test with different core counts
./scripts/run-core-sweep.sh --cores "4 8 16 32" --model "RedHatAI/all-MiniLM-L6-v2"
```

---

### mlflow-quick-log.sh

**Purpose:** Quickly log benchmark results to MLflow.

**Location:** `automation/test-execution/ansible/scripts/mlflow-quick-log.sh`

**Usage:**
```bash
# Log results to MLflow
./scripts/mlflow-quick-log.sh results/embedding/model-name/baseline/sweep-inf.json
```

---

### extract-all-timings.sh

**Purpose:** Extract timing data from all benchmark results.

**Location:** `automation/test-execution/ansible/scripts/extract-all-timings.sh`

**Usage:**
```bash
# Extract timings from results directory
./scripts/extract-all-timings.sh results/embedding/
```

---

## Manual Test Scripts

Located in `automation/test-execution/bash/embedding/`

### run-baseline.sh

**Purpose:** Manually run baseline performance test for a single model.

**Location:** `automation/test-execution/bash/embedding/run-baseline.sh`

**Usage:**
```bash
# Set endpoint
export VLLM_HOST=192.168.1.10
export VLLM_PORT=8000

# Run baseline test
./bash/embedding/run-baseline.sh RedHatAI/all-MiniLM-L6-v2
```

---

### run-latency.sh

**Purpose:** Manually run latency test for a single model.

**Location:** `automation/test-execution/bash/embedding/run-latency.sh`

**Usage:**
```bash
# Run latency test
./bash/embedding/run-latency.sh RedHatAI/all-MiniLM-L6-v2
```

---

### run-all.sh

**Purpose:** Run both baseline and latency tests for a single model.

**Location:** `automation/test-execution/bash/embedding/run-all.sh`

**Usage:**
```bash
# Run all tests
./bash/embedding/run-all.sh RedHatAI/all-MiniLM-L6-v2
```

---

## Utility Scripts

### Health Checks

**Location:** `automation/utilities/health-checks/check-vllm.sh`

**Purpose:** Verify vLLM server is healthy and responsive.

**Usage:**
```bash
# Quick health check
./utilities/health-checks/check-vllm.sh --host 192.168.1.10

# With verbose output
./utilities/health-checks/check-vllm.sh --host 192.168.1.10 --verbose
```

---

### Log Monitoring

**Locations:**
- `automation/utilities/log-monitoring/monitor-vllm-logs.sh`
- `automation/utilities/log-monitoring/monitor-test-progress.sh`

**Usage:**
```bash
# Monitor vLLM logs
./utilities/log-monitoring/monitor-vllm-logs.sh --mode remote --remote-host dut-ip

# Monitor test progress
./utilities/log-monitoring/monitor-test-progress.sh
```

---

## Container Build Scripts

### MTEB Container

**Location:** `container-images/vllm-mteb/build.sh`

**Purpose:** Build the MTEB benchmark container image.

**Usage:**
```bash
cd container-images/vllm-mteb
./build.sh
```

---

### Model Downloader

**Location:** `container-images/model-downloader/build.sh`

**Purpose:** Build the model pre-download container.

**Usage:**
```bash
cd container-images/model-downloader
./build.sh
```

---

## Recommended Workflows

### Complete Model Evaluation

```bash
cd automation/test-execution/scripts

# 1. Run performance tests
./bash/run-embedding-suite.sh --models all --scenario all

# 2. Run quality tests (uses 4 cores for efficiency)
./bash/run-mteb-model-sweep.sh --task-preset comprehensive

# 3. Convert to CSV
python python/convert-embedding-results.py

# 4. View in dashboard
cd ../dashboard-examples/vllm_dashboard
./launch-dashboard.sh
```

---

### Quick Smoke Test

```bash
cd automation/test-execution/scripts

# Fast validation (~5-10 minutes)
./bash/run-embedding-suite.sh --models quick --cores 4 --num-prompts 10
./bash/run-mteb-model-sweep.sh --models quick --task-preset quick
```

---

### Production Benchmarking

```bash
cd automation/test-execution/scripts

# Skip development models
./bash/run-embedding-suite.sh \
  --skip-models "RedHatAI/embeddinggemma-300m" \
  --cores 8,16,32 \
  --scenario all

./bash/run-mteb-model-sweep.sh \
  --skip-models "RedHatAI/embeddinggemma-300m" \
  --task-preset comprehensive
```

---

## Related Documentation

- [Embedding Models Guide](embedding-models.md) - Complete embedding testing guide
- [MTEB Sweep Guide](mteb-sweep-guide.md) - MTEB quick start
- [MTEB Timing Guide](mteb-timing-guide.md) - Detailed timing estimates
- [MTEB Troubleshooting](mteb-troubleshooting.md) - Common issues and solutions
- [Ansible Automation](ansible/test-execution.md) - Ansible playbook documentation

---

## Core Count Recommendations

### For Performance Testing (Throughput/Latency)
- **Test multiple core counts:** 4, 8, 16, 32
- **Goal:** Find optimal performance/resource tradeoff
- **Script:** `run-embedding-suite.sh --cores 4,8,16,32`

### For Quality Testing (MTEB Accuracy)
- **Use 4 cores (default):** Most efficient
- **Why:** Quality metrics don't change with core count
- **Goal:** Minimize resource usage and test runtime
- **Script:** `run-mteb-model-sweep.sh` (defaults to 4 cores)

---

## Getting Help

All scripts support `--help`:

```bash
./bash/run-embedding-suite.sh --help
./bash/run-mteb-model-sweep.sh --help
```

For issues or questions:
- GitHub Issues: <https://github.com/redhat-et/vllm-cpu-perf-eval/issues>
- Documentation: <https://redhat-et.github.io/vllm-cpu-perf-eval/>
