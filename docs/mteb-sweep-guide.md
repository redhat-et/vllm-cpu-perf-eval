---
layout: default
title: MTEB Quality Testing - Quick Start Guide
---

# MTEB Model Sweep - Quick Start Guide

## Quick Answer: Timing

**TL;DR:**  
- **Quick test (2 tasks)**: ~10-25 minutes for all 5 models
- **Comprehensive (5 tasks)**: ~100-150 minutes (1.7-2.5 hours) for all 5 models

See [MTEB Timing Guide](mteb-timing-guide.md) for detailed timing information.

## Quick Start

### Run All Models (Quick Test)
```bash
cd automation/test-execution/scripts
./run-mteb-model-sweep.sh
```

This runs the "quick" preset (2 tasks) on all 5 models (~10-25 minutes).

### Run Comprehensive Tests
```bash
./run-mteb-model-sweep.sh --task-preset comprehensive
```

This runs 5 tasks on all 5 models (~1.7-2.5 hours).

### Run Specific Models Only
```bash
./run-mteb-model-sweep.sh \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2"
```

## Fixing Directory Structure

### Option 1: Dashboard Auto-Handles It (Recommended)

The dashboard already supports both directory structures:
- `no_model_name_available/no_revision_available/*.json` (MTEB default)
- `TaskName/test.json` (clean format)

Just view results in the dashboard - no action needed.

### Option 2: Reorganize Results (Optional)

If you prefer clean directories:

```bash
cd scripts
./reorganize-mteb-results.sh
```

This converts:
```
FROM: results/mteb/MODEL/TIMESTAMP/no_model_name_available/no_revision_available/Banking77Classification.json
TO:   results/mteb/MODEL/TIMESTAMP/Banking77Classification/test.json
```

## Viewing Results

After tests complete:

```bash
# Start dashboard
cd automation/test-execution/dashboard-examples/vllm_dashboard
streamlit run Home.py

# Navigate to: 📊 Embedding Metrics → 🎯 MTEB Quality tab
```

## All Available Options

```bash
./run-mteb-model-sweep.sh --help
```

### Common Options

| Option | Description | Example |
|--------|-------------|---------|
| `--task-preset` | Task set to run | `--task-preset comprehensive` |
| `--models` | Specific models | `--models "RedHatAI/all-MiniLM-L6-v2"` |
| `--skip-models` | Skip large models | `--skip-models "RedHatAI/Qwen3-Embedding-8B"` |
| `--cores` | CPU cores (default: 4) | `--cores 16` |
| `--dry-run` | Preview without running | `--dry-run` |

## Task Presets

| Preset | Tasks | Time (all 5 models) |
|--------|-------|---------------------|
| `quick` | 2 | 10-25 min |
| `retrieval` | 3 | 50-75 min |
| `classification` | 3 | 25-50 min |
| `sts` | 3 | 15-40 min |
| `clustering` | 2 | 40-75 min |
| `comprehensive` | 5 | 100-150 min |

## Models Tested

1. **RedHatAI/all-MiniLM-L6-v2** (22.7M) - Fastest
2. **RedHatAI/granite-embedding-english-r2** (109M)
3. **RedHatAI/nomic-embed-text-v1.5** (137M)
4. **RedHatAI/embeddinggemma-300m** (300M)
5. **RedHatAI/Qwen3-Embedding-8B** (8B) - Most thorough, slowest

## Examples

### Skip slowest models during development
```bash
./run-mteb-model-sweep.sh \
  --skip-models "RedHatAI/Qwen3-Embedding-8B,RedHatAI/embeddinggemma-300m"
```
**Time:** ~6-15 minutes (3 models, quick preset)

### Test only small fast model
```bash
./run-mteb-model-sweep.sh \
  --models "RedHatAI/all-MiniLM-L6-v2" \
  --task-preset quick
```
**Time:** ~2-5 minutes (1 model, 2 tasks)

### Full benchmark for report
```bash
./run-mteb-model-sweep.sh --task-preset comprehensive
```
**Time:** ~1.7-2.5 hours (5 models, 5 tasks)

## Troubleshooting

### Results not showing in dashboard

1. Check results exist:
   ```bash
   ls -la results/mteb/
   ```

2. Reorganize if needed:
   ```bash
   ./scripts/reorganize-mteb-results.sh
   ```

3. Reload dashboard:
   - Click "🔄 Reload Data" in dashboard sidebar
   - Or restart Streamlit

### Tests taking too long

- Use `--skip-models` to exclude large models
- Use `--task-preset quick` for faster tests
- Test fewer models with `--models`

### Out of memory

Large models (especially Qwen3-8B) require significant RAM:
- 16GB minimum for small models
- 32GB+ recommended for 8B models
- Use `--skip-models` to exclude large models if needed

## Next Steps

1. **Run quick test** to validate setup
2. **View results** in dashboard
3. **Run comprehensive** for final benchmarking
4. **Generate report** from dashboard data

## Files Created

| File | Purpose |
|------|---------|
| `run-mteb-model-sweep.sh` | Main sweep script |
| `../../../scripts/reorganize-mteb-results.sh` | Directory restructuring |
| `../../../docs/mteb-timing-guide.md` | Detailed timing info |
| `README-MTEB-SWEEP.md` | This file |
