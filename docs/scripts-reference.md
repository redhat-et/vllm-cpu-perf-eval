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
| clustering | 2 | 40-75 min |
| comprehensive | 5 | 100-150 min |

**Full Documentation:**
- Run `./bash/run-mteb-model-sweep.sh --help`
- [MTEB Sweep Guide](mteb-sweep-guide.md)
- [MTEB Timing Guide](mteb-timing-guide.md)

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
