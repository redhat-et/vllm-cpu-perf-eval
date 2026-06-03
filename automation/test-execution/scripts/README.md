# Test Execution Scripts

High-level test execution and utility scripts for running comprehensive test suites.

## Directory Structure

```
automation/test-execution/scripts/
├── bash/                                # Bash shell scripts
│   ├── run-embedding-suite.sh          # Run performance tests on all embedding models
│   ├── run-mteb-model-sweep.sh         # Run MTEB quality tests on all models
│   ├── reorganize-mteb-results.sh      # Reorganize MTEB results directory structure
│   └── README-MTEB-SWEEP.md            # Detailed MTEB sweep documentation
└── python/                              # Python utility scripts
    └── convert-embedding-results.py    # Convert benchmark JSON to CSV
```

## Quick Start

### Run Complete Test Suite

```bash
cd automation/test-execution/scripts

# 1. Run performance tests on all models (~2-4 hours)
./bash/run-embedding-suite.sh

# 2. Run quality tests (~10-25 minutes for quick, ~2 hours for comprehensive)
./bash/run-mteb-model-sweep.sh --task-preset quick

# 3. View results
cd ../dashboard-examples/vllm_dashboard
./launch-dashboard.sh
```

### Quick Smoke Test

```bash
# Fast validation (~5-10 minutes total)
cd automation/test-execution/scripts

./bash/run-embedding-suite.sh --models quick --cores 4 --num-prompts 10
./bash/run-mteb-model-sweep.sh --models quick --task-preset quick
```

---

## Bash Scripts

### [run-embedding-suite.sh](bash/run-embedding-suite.sh)

**Consolidated performance test suite** - Combines and enhances the previous `run-embedding-suite.sh` and `run-embedding-suite-remaining.sh` scripts.

**Purpose:** Run comprehensive performance benchmarks across all embedding models and core counts.

**Key Features:**
- Model presets (all, small, medium, large, quick)
- Flexible core count configuration
- Scenario selection (baseline, latency, all)
- Skip specific models
- Continue on error option
- Dry-run mode

**Examples:**

```bash
# All models, all core counts (default: 4,8,16,32)
./bash/run-embedding-suite.sh

# Quick smoke test
./bash/run-embedding-suite.sh --models quick --cores 4 --num-prompts 10

# Small models only
./bash/run-embedding-suite.sh --models small --cores 8,16,32

# Skip the largest model
./bash/run-embedding-suite.sh --skip-models "RedHatAI/Qwen3-Embedding-8B"

# Baseline tests only on 16 cores
./bash/run-embedding-suite.sh --scenario baseline --cores 16

# Specific models
./bash/run-embedding-suite.sh \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2" \
  --cores 8,16
```

**Model Presets:**
- `all` - All 5 models (22M to 8B)
- `small` - all-MiniLM (22M), granite-english (109M)
- `medium` - nomic-embed (137M), embeddinggemma (300M)
- `large` - Qwen3-Embedding-8B (8B)
- `quick` - all-MiniLM-L6-v2 only (for testing)

**Run with `--help` for complete options.**

---

### [run-mteb-model-sweep.sh](bash/run-mteb-model-sweep.sh)

**MTEB quality benchmark suite** - Run quality tests on all embedding models.

**Purpose:** Evaluate embedding quality using the MTEB (Massive Text Embedding Benchmark) framework.

**Timing Reference:**

| Preset | Tasks | Time (5 models) |
|--------|-------|-----------------|
| quick | 2 | 10-25 min |
| comprehensive | 5 | 100-150 min |

**Examples:**

```bash
# Quick test on all models
./bash/run-mteb-model-sweep.sh

# Comprehensive evaluation
./bash/run-mteb-model-sweep.sh --task-preset comprehensive

# Test specific models
./bash/run-mteb-model-sweep.sh \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2"

# Skip large models
./bash/run-mteb-model-sweep.sh --skip-models "RedHatAI/Qwen3-Embedding-8B"

# Use external vLLM endpoint
./bash/run-mteb-model-sweep.sh \
  --vllm-mode external \
  --endpoint http://production-vllm:8000
```

**See [README-MTEB-SWEEP.md](bash/README-MTEB-SWEEP.md) for detailed documentation and [../../../docs/mteb-timing-guide.md](../../../docs/mteb-timing-guide.md) for timing estimates.**

---

### [reorganize-mteb-results.sh](bash/reorganize-mteb-results.sh)

**MTEB results reorganizer** - Transform MTEB output to clean directory structure.

**Purpose:** Convert nested MTEB results to flat format for easier navigation.

**Usage:**
```bash
# Reorganize default results directory
./bash/reorganize-mteb-results.sh

# Reorganize custom directory
./bash/reorganize-mteb-results.sh /path/to/results/mteb
```

**Transformation:**
```
FROM: results/mteb/MODEL/TIMESTAMP/no_model_name_available/no_revision_available/*.json
TO:   results/mteb/MODEL/TIMESTAMP/TaskName/test.json
```

**Note:** The dashboard now handles both formats, so this is optional.

---

## Python Scripts

### [convert-embedding-results.py](python/convert-embedding-results.py)

**Results converter** - Convert JSON benchmark results to CSV format.

**Purpose:** Export performance metrics to CSV for spreadsheet analysis or further processing.

**Usage:**
```bash
# Convert all results
python python/convert-embedding-results.py

# Specify results directory
python python/convert-embedding-results.py --results-dir ../../results/embedding

# Convert specific model
python python/convert-embedding-results.py --model "RedHatAI/all-MiniLM-L6-v2"

# Custom output file
python python/convert-embedding-results.py --output my-metrics.csv
```

**Output:** CSV with columns for model, core count, RPS, latency percentiles, etc.

---

## Models Tested

All scripts operate on these embedding models from [RedHatAI Intel Xeon-compatible collection](https://huggingface.co/collections/RedHatAI/intel-xeon-compatible-models):

| Model | Size | Context | Type |
|-------|------|---------|------|
| RedHatAI/all-MiniLM-L6-v2 | 22.7M | 256 | Fastest |
| RedHatAI/granite-embedding-english-r2 | 109M | 8192 | English |
| RedHatAI/nomic-embed-text-v1.5 | 137M | 8192 | Multilingual |
| RedHatAI/embeddinggemma-300m | 300M | 2048 | Mid-size |
| RedHatAI/Qwen3-Embedding-8B | 8B | 40960 | Large context |

---

## Complete Workflows

### Development/CI Testing

```bash
cd automation/test-execution/scripts

# Quick validation (~10-15 min total)
./bash/run-embedding-suite.sh \
  --models quick \
  --cores 4,8 \
  --num-prompts 10

./bash/run-mteb-model-sweep.sh \
  --models quick \
  --task-preset quick
```

### Nightly Benchmarking

```bash
cd automation/test-execution/scripts

# Comprehensive tests (~3-4 hours)
./bash/run-embedding-suite.sh --models all --scenario all
./bash/run-mteb-model-sweep.sh --task-preset comprehensive

# Convert and analyze
python python/convert-embedding-results.py
```

### Model Comparison

```bash
cd automation/test-execution/scripts

# Compare 2-3 specific models
./bash/run-embedding-suite.sh \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2" \
  --cores 8,16,32 \
  --scenario all

./bash/run-mteb-model-sweep.sh \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2" \
  --task-preset comprehensive
```

### Production Baseline

```bash
cd automation/test-execution/scripts

# Skip development models, focus on production candidates
./bash/run-embedding-suite.sh \
  --skip-models "RedHatAI/embeddinggemma-300m" \
  --scenario baseline

./bash/run-mteb-model-sweep.sh \
  --skip-models "RedHatAI/embeddinggemma-300m" \
  --task-preset comprehensive
```

---

## Environment Variables

```bash
# Optional: Use custom vLLM image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

# Then run tests
./bash/run-embedding-suite.sh
```

---

## Other Test Execution Scripts

### Ansible-Specific Scripts

Located in `../ansible/scripts/`:

- `run-core-sweep.sh` - Run tests across multiple core counts
- `copy-guidellm-logs.sh` - Collect GuideLLM logs
- `extract-all-timings.sh` - Extract timing data
- `mlflow-quick-log.sh` - Log results to MLflow

### Manual Bash Scripts

Located in `../bash/embedding/`:

- `run-baseline.sh` - Manual baseline test execution
- `run-latency.sh` - Manual latency test execution
- `run-all.sh` - Run both baseline and latency

**Note:** The scripts in this directory (`scripts/bash/`) are **higher-level** and automate multiple models/configurations. Use the manual scripts in `../bash/embedding/` for single-model testing or debugging.

---

## Related Documentation

- [Embedding Models Guide](../../../docs/embedding-models.md)
- [MTEB Timing Guide](../../../docs/mteb-timing-guide.md)
- [MTEB Troubleshooting](../../../docs/mteb-troubleshooting.md)
- [Embedding Models Test Plan](../../../tests/embedding-models/embedding-models.md)
- [Dashboard Quickstart](../../../docs/dashboards-quickstart.md)

---

## Viewing Results

After running tests:

```bash
cd ../dashboard-examples/vllm_dashboard
./launch-dashboard.sh

# Navigate to:
# - 📊 Embedding Metrics (for performance data)
# - 🎯 MTEB Quality tab (for quality metrics)
```

Or convert to CSV:

```bash
python python/convert-embedding-results.py --output my-results.csv
```

---

## Contributing

When adding new high-level test execution scripts:

1. Place bash scripts in `bash/` directory
2. Place Python scripts in `python/` directory
3. Make scripts executable: `chmod +x script-name.sh`
4. Add `--help` option with detailed usage
5. Update this README with description and examples
6. Follow existing patterns for error handling and logging
