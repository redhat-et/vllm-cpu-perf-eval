# MTEB Timing Guide

## Quick Reference

| Test Preset | Tasks | Per-Model Time | 5 Models Total |
|-------------|-------|----------------|----------------|
| **quick** | 2 | ~2-5 minutes | **10-25 minutes** |
| **retrieval** | 3 | ~10-15 minutes | **50-75 minutes** |
| **classification** | 3 | ~5-10 minutes | **25-50 minutes** |
| **sts** | 3 | ~3-8 minutes | **15-40 minutes** |
| **comprehensive** | 5 | ~20-30 minutes | **100-150 minutes (1.7-2.5 hours)** |

**Note:** Clustering tasks are currently disabled due to segmentation faults.

**Model count:** 5 models in the test suite:
- RedHatAI/all-MiniLM-L6-v2 (22.7M) - fastest
- RedHatAI/granite-embedding-english-r2 (109M)
- RedHatAI/nomic-embed-text-v1.5 (137M)
- RedHatAI/embeddinggemma-300m (300M)
- RedHatAI/Qwen3-Embedding-8B (8B) - slowest

## Task Preset Details

### Quick Preset (Recommended for Development)
```bash
./run-mteb-model-sweep.sh --task-preset quick
```

**Tasks:**
1. Banking77Classification (2-3 min per model)
2. EmotionClassification (1-2 min per model)

**Total Time:** ~10-25 minutes for all 5 models

**Use Case:** Development, smoke testing, quick validation

---

### Retrieval Preset
```bash
./run-mteb-model-sweep.sh --task-preset retrieval
```

**Tasks:**
1. ArguAna (5-8 min per model)
2. NFCorpus (3-5 min per model)
3. SCIDOCS (2-4 min per model)

**Total Time:** ~50-75 minutes for all 5 models

**Use Case:** Evaluating search/retrieval quality

---

### Classification Preset
```bash
./run-mteb-model-sweep.sh --task-preset classification
```

**Tasks:**
1. Banking77Classification (2-3 min)
2. EmotionClassification (1-2 min)
3. ToxicConversationsClassification (2-5 min)

**Total Time:** ~25-50 minutes for all 5 models

**Use Case:** Text categorization evaluation

---

### STS (Semantic Textual Similarity) Preset
```bash
./run-mteb-model-sweep.sh --task-preset sts
```

**Tasks:**
1. STS12 (1-2 min)
2. STS15 (1-2 min)
3. STS16 (1-2 min)

**Total Time:** ~15-40 minutes for all 5 models

**Use Case:** Semantic similarity evaluation

---

### Clustering Preset

**Status:** Currently disabled due to segmentation faults with MTEB clustering tasks.

---

### Comprehensive Preset (Full Evaluation)
```bash
./run-mteb-model-sweep.sh --task-preset comprehensive
```

**Tasks:**
1. Banking77Classification (2-3 min)
2. ArguAna (5-8 min)
3. STS12 (1-2 min)
4. EmotionClassification (1-2 min)
5. NFCorpus (3-5 min)

**Total Time:** ~100-150 minutes (1.7-2.5 hours) for all 5 models

**Use Case:** Complete model evaluation, benchmarking reports

**Note:** Clustering tasks removed due to segmentation faults.

---

## Timing Factors

### Model Size Impact

Larger models take longer per task:

| Model Size | Speed Factor | Example Time (Banking77) |
|------------|--------------|--------------------------|
| 22M (all-MiniLM) | 1.0x (baseline) | ~1-2 min |
| 109-137M (granite, nomic) | 1.2-1.5x | ~1.5-3 min |
| 300M (embeddinggemma) | 1.8-2.5x | ~2-5 min |
| 8B (Qwen3) | 3-5x | ~5-10 min |

### Hardware Impact

CPU configuration affects speed:

| Configuration | Speed Factor |
|---------------|--------------|
| 16 cores, 1 socket | 1.0x (baseline) |
| 32 cores, 1 socket | 1.4-1.6x faster |
| 64 cores, 2 sockets | 1.8-2.2x faster |
| 128 cores, 2 sockets | 2.5-3.0x faster |

### Task Complexity

Different tasks have different computational requirements:

| Task Type | Complexity | Dataset Size |
|-----------|------------|--------------|
| Classification | Low | 1,000-10,000 samples |
| STS | Low-Medium | 1,000-8,000 pairs |
| Clustering | Medium | 5,000-25,000 docs |
| Retrieval | High | 10,000-100,000+ docs |

## Optimization Strategies

### 1. Selective Testing

Test only critical models:
```bash
./run-mteb-model-sweep.sh \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2"
```

**Time Saved:** ~60% (2 models vs 5)

### 2. Skip Large Models During Development

```bash
./run-mteb-model-sweep.sh \
  --skip-models "RedHatAI/Qwen3-Embedding-8B,RedHatAI/embeddinggemma-300m"
```

**Time Saved:** ~40-50% (skip slowest models)

### 3. Quick Preset for Iteration

Use `quick` preset during development, `comprehensive` for final reports:

```bash
# Development
./run-mteb-model-sweep.sh --task-preset quick  # 10-25 min

# Final report
./run-mteb-model-sweep.sh --task-preset comprehensive  # 1.7-2.5 hours
```

### 4. Parallel Execution (Advanced)

**WARNING:** Only use if you have abundant resources (memory, CPU)

```bash
./run-mteb-model-sweep.sh --parallel --task-preset quick
```

**Requirements:**
- At least 32GB RAM for 2 models in parallel
- At least 64GB RAM for 3+ models in parallel
- Separate CPU core allocation per model

**Time Saved:** ~50-70% (but requires 2-3x resources)

### 5. Use External vLLM Endpoint

Pre-start vLLM and reuse it for multiple models (manual iteration):

```bash
# Terminal 1: Start vLLM
ansible-playbook common/vllm-embedding-startup.yml \
  -e "test_model=RedHatAI/all-MiniLM-L6-v2"

# Terminal 2: Run tests
export VLLM_ENDPOINT=http://localhost:8000
./run-mteb-model-sweep.sh \
  --vllm-mode external \
  --endpoint "${VLLM_ENDPOINT}" \
  --models "RedHatAI/all-MiniLM-L6-v2"
```

**Time Saved:** Eliminates vLLM startup time (~30-60s per model)

## Recommended Workflows

### Development/Testing
```bash
# Quick smoke test on 2 models (~5-10 min)
./run-mteb-model-sweep.sh \
  --task-preset quick \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2"
```

### Nightly CI/CD
```bash
# Comprehensive test on all models (~2-2.5 hours)
./run-mteb-model-sweep.sh \
  --task-preset comprehensive \
  --continue-on-error
```

### Benchmarking Report
```bash
# Full evaluation with all presets (~3-5 hours total)
for preset in quick retrieval classification sts comprehensive; do
  ./run-mteb-model-sweep.sh --task-preset "${preset}"
done
```

### Quick Model Comparison
```bash
# Compare 3 models on specific task (~15-20 min)
./run-mteb-model-sweep.sh \
  --task-preset retrieval \
  --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2,RedHatAI/nomic-embed-text-v1.5"
```

## Monitoring Progress

Monitor test progress in real-time:

```bash
# Terminal 1: Run sweep
./run-mteb-model-sweep.sh --task-preset quick

# Terminal 2: Monitor logs
tail -f automation/test-execution/scripts/mteb-sweep-results-*.log

# Terminal 3: Check results
watch -n 30 'ls -lh results/mteb/'
```

## Estimation Formula

For custom configurations:

```
Total Time = (Number of Models) × (Average Task Time) × (Number of Tasks) × (Hardware Factor)

Where:
  Average Task Time = 2-5 minutes (quick) to 5-10 minutes (complex)
  Hardware Factor = 1.0 (16 cores) to 0.4 (64+ cores)
```

Example:
- 5 models × 3 minutes per task × 2 tasks × 1.0 = **30 minutes** (quick, 16 cores)
- 5 models × 7 minutes per task × 5 tasks × 0.6 = **105 minutes** (comprehensive, 32 cores)
