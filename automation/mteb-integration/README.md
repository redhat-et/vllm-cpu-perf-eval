## MTEB Integration for vLLM CPU Performance Evaluation

This directory contains integration components for running MTEB (Massive Text Embedding Benchmark) quality tests on embedding models served by vLLM CPU or Red Hat AI Inference Server (RHAIIS).

### Overview

**MTEB** provides standardized benchmarks for evaluating embedding model quality across multiple tasks:
- **Retrieval** - Information retrieval performance
- **Classification** - Text classification accuracy  
- **Clustering** - Document clustering quality
- **Semantic Textual Similarity (STS)** - Sentence similarity correlation
- **Reranking** - Document reranking effectiveness

This integration complements your existing **performance benchmarks** (throughput, latency) with **quality metrics** (accuracy, F1, NDCG).

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   MTEB Test Flow                        │
│                                                         │
│  ┌──────────────┐         HTTP API        ┌──────────┐ │
│  │ MTEB Container│ ◄─────────────────────► │  vLLM    │ │
│  │  - Test Runner│   /v1/embeddings        │  Server  │ │
│  │  - Tasks      │                         │          │ │
│  │  - Metrics    │                         └──────────┘ │
│  └──────────────┘                                       │
│         │                                               │
│         ▼                                               │
│  ┌──────────────┐                                       │
│  │   Results    │                                       │
│  │  - Accuracy  │                                       │
│  │  - F1 Score  │                                       │
│  │  - NDCG      │                                       │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

### Components

#### 1. vLLM CPU Wrapper (`wrappers/vllm_cpu_wrapper.py`)

Custom MTEB encoder that communicates with vLLM via HTTP API:

- **`VllmCPUEncoderWrapper`** - HTTP-based wrapper for remote vLLM servers
- **`VllmCPULocalWrapper`** - Direct vLLM integration (for local testing)

Features:
- Batch processing for efficiency
- Retry logic for reliability
- Connection validation
- Task-specific prompt handling

#### 2. Container Image (`Dockerfile`)

Lightweight Python container with:
- MTEB framework
- Custom vLLM CPU wrapper
- All necessary dependencies
- CPU-optimized PyTorch

#### 3. Benchmark Runner (`scripts/run_mteb_benchmark.py`)

Main test execution script with:
- Task preset configurations
- Connection testing
- Result collection
- Error handling

#### 4. Ansible Playbook (`../test-execution/ansible/mteb-benchmark.yml`)

Automated test orchestration:
- Managed mode (starts vLLM automatically)
- External mode (uses existing endpoint)
- Results collection and organization

### Quick Start

#### 1. Build the Container

```bash
cd automation/mteb-integration
./build-container.sh vllm-mteb:latest
```

#### 2. Test with Running vLLM Server

```bash
# Test connection
podman run --rm --network host vllm-mteb:latest \
  python /opt/mteb/scripts/run_mteb_benchmark.py \
    --endpoint-url http://localhost:8000 \
    --model-name RedHatAI/granite-embedding-english-r2 \
    --test-connection

# Run quick benchmark
podman run --rm --network host \
  -v $PWD/results:/results:z \
  vllm-mteb:latest \
  python /opt/mteb/scripts/run_mteb_benchmark.py \
    --endpoint-url http://localhost:8000 \
    --model-name RedHatAI/granite-embedding-english-r2 \
    --task-preset quick
```

#### 3. Run with Ansible (Recommended)

```bash
cd ../test-execution/ansible

# Managed mode (starts vLLM automatically)
ansible-playbook -i inventory/hosts.yml mteb-benchmark.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "mteb_task_preset=quick" \
  -e "requested_cores=16"

# External mode (test existing endpoint)
ansible-playbook -i inventory/hosts.yml mteb-benchmark.yml \
  -e "vllm_mode=external" \
  -e "vllm_endpoint_url=http://production-vllm:8000" \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "mteb_task_preset=comprehensive"
```

### Task Presets

Pre-configured task groups for different evaluation needs:

| Preset | Tasks | Use Case | Duration |
|--------|-------|----------|----------|
| **quick** | Banking77, Emotion | Fast smoke test | ~5 min |
| **retrieval** | ArguAna, NFCorpus, SCIDOCS | Retrieval performance | ~30 min |
| **classification** | Banking77, Emotion, ToxicConversations | Classification accuracy | ~15 min |
| **sts** | STS12, STS15, STS16 | Semantic similarity | ~20 min |
| **clustering** | ArxivClustering, TwentyNewsgroups | Clustering quality | ~25 min |
| **comprehensive** | Mixed tasks | Full evaluation | ~45 min |

### Custom Task Selection

Run specific tasks instead of presets:

```bash
python /opt/mteb/scripts/run_mteb_benchmark.py \
  --endpoint-url http://localhost:8000 \
  --model-name RedHatAI/granite-embedding-english-r2 \
  --tasks Banking77Classification ArguAna STS12
```

### Testing Your Models

For the 5 RedHatAI embedding models:

```bash
# Quick validation test
for model in \
  "RedHatAI/all-MiniLM-L6-v2" \
  "RedHatAI/granite-embedding-english-r2" \
  "RedHatAI/nomic-embed-text-v1.5" \
  "RedHatAI/embeddinggemma-300m" \
  "RedHatAI/Qwen3-Embedding-8B"
do
  echo "Testing $model..."
  ansible-playbook -i inventory/hosts.yml mteb-benchmark.yml \
    -e "test_model=$model" \
    -e "mteb_task_preset=quick" \
    -e "requested_cores=16"
done

# Comprehensive evaluation
for model in \
  "RedHatAI/all-MiniLM-L6-v2" \
  "RedHatAI/granite-embedding-english-r2"
do
  echo "Comprehensive testing $model..."
  ansible-playbook -i inventory/hosts.yml mteb-benchmark.yml \
    -e "test_model=$model" \
    -e "mteb_task_preset=comprehensive" \
    -e "requested_cores=32"
done
```

### Results Structure

```
results/mteb/
├── RedHatAI__granite-embedding-english-r2/
│   └── 20260603-143025/
│       ├── run_summary.json          # Test metadata
│       ├── Banking77Classification/  # Per-task results
│       │   └── test.json
│       ├── ArguAna/
│       │   └── test.json
│       └── ...
└── RedHatAI__all-MiniLM-L6-v2/
    └── ...
```

**Result Files:**
- `run_summary.json` - Test run metadata
- `<task_name>/test.json` - Detailed task results with metrics

**Example Metrics:**
```json
{
  "test": {
    "accuracy": 0.8542,
    "f1": 0.8498,
    "precision": 0.8621,
    "recall": 0.8380
  }
}
```

### Performance vs Quality Trade-offs

| Model | Size | Performance | Quality | Best For |
|-------|------|-------------|---------|----------|
| **all-MiniLM-L6-v2** | 23M | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | High throughput |
| **granite-english-r2** | 109M | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Balanced |
| **nomic-embed** | 137M | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | General purpose |
| **embeddinggemma** | 300M | ⭐⭐⭐ | ⭐⭐⭐⭐ | Quality priority |
| **Qwen3-8B** | 8B | ⭐⭐ | ⭐⭐⭐⭐⭐ | Maximum quality |

### Integration with Existing Benchmarks

Run both performance and quality tests:

```bash
# 1. Performance test (throughput, latency)
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "scenario=all" \
  -e "requested_cores=16"

# 2. Quality test (accuracy, retrieval)
ansible-playbook -i inventory/hosts.yml mteb-benchmark.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "mteb_task_preset=comprehensive" \
  -e "requested_cores=16"

# Results in:
# - results/embedding/... (performance metrics)
# - results/mteb/... (quality metrics)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VLLM_MODE` | Test mode: managed or external | managed |
| `TEST_MODEL` | Model to test | (required) |
| `MTEB_TASK_PRESET` | Task preset to run | quick |
| `MTEB_TASKS` | Custom task list (space-separated) | - |
| `MTEB_LANGUAGES` | Languages to test | en |
| `MTEB_CONTAINER_IMAGE` | Container image to use | vllm-mteb:latest |
| `VLLM_ENDPOINT_URL` | vLLM server URL (external mode) | - |
| `DUT_HOSTNAME` | DUT hostname (managed mode) | localhost |
| `REQUESTED_CORES` | CPU cores for vLLM (managed) | 16 |

### Troubleshooting

**Connection refused:**
```bash
# Verify vLLM server is running
curl http://localhost:8000/v1/models

# Test connection explicitly
podman run --rm --network host vllm-mteb:latest \
  python /opt/mteb/scripts/run_mteb_benchmark.py \
    --endpoint-url http://localhost:8000 \
    --model-name <your-model> \
    --test-connection
```

**Model not found:**
```bash
# Check model name matches vLLM server
curl http://localhost:8000/v1/models | jq '.data[].id'

# Use exact model name from server response
```

**Timeout errors:**
```bash
# Increase timeout for large models
python /opt/mteb/scripts/run_mteb_benchmark.py \
  ... \
  --timeout 600  # 10 minutes
```

**Container build fails:**
```bash
# Ensure podman is available
podman --version

# Build with verbose output
podman build --no-cache -t vllm-mteb:latest -f Dockerfile .
```

### Next Steps

1. **Build container:** `./build-container.sh`
2. **Test connection:** Run with `--test-connection`
3. **Quick validation:** Use `quick` preset on one model
4. **Full evaluation:** Use `comprehensive` preset on all models
5. **Analyze results:** Compare quality vs performance trade-offs

### Related Documentation

- [Embedding Models Testing Guide](../../docs/embedding-models.md)
- [MTEB Official Documentation](https://github.com/embeddings-benchmark/mteb)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Test Execution Guide](../test-execution/ansible/README.md)
