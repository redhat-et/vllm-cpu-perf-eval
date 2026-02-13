# Phase 1: Concurrent Load Testing

Tests model performance under various concurrent request loads.

## Overview

Phase 1 focuses on measuring how P95 latency and throughput scale as the
number of parallel request streams increases. This establishes baseline
performance characteristics for CPU inferencing across multiple model
architectures and workload types.

## Goals

- Measure P95 latency scaling with increasing concurrency
- Identify throughput saturation points
- Establish baseline performance for different model architectures
- Test across realistic workload profiles (Chat, RAG, CodeGen, Summarization)

## Models Under Test

### Core Architectural Coverage

<!-- markdownlint-disable MD013 -->

| Architecture Family | Representative Model | Key Application Focus |
| --- | --- | --- |
| Llama 3 Decoder | Llama-3.2-1B-Instruct | Prefill-Heavy (Baseline) |
| Llama 2 Decoder | TinyLlama-1.1B-Chat-v1.0 | Prefill/Decode (Small-Scale) |
| Traditional OPT Decoder | facebook/opt-125m | Decode-Heavy (Legacy Baseline) |
| IBM Granite Decoder | granite-3.2-2b-instruct | Balanced (Enterprise Baseline) |
| Qwen 3 Decoder | Qwen/Qwen3-0.6B | Balanced (High-Efficiency) |
| MiniLM/BERT (English Dense) | slate-125m-english-rtrvr-v2 | Encoder-Only (Fastest Baseline) |
| XLM-RoBERTa (Multilingual) | granite-embedding-278m-multilingual | Encoder-Only (Multilingual) |

<!-- markdownlint-enable MD013 -->

## Test Parameters

### Key Variables

<!-- markdownlint-disable MD013 MD033 -->

| Variable | Description | Test Setting |
| --- | --- | --- |
| **Workload** | Input/Output token counts (ISL:OSL) | • Chat (512:256)<br>• RAG (4096:512)<br>• CodeGen (512:4K)<br>• Summarization (1024:256)<br>• Embedding (512:1) |
| **Affinity** | Core allocation strategy | FULL: All physical cores |
| **Cores** | Number of cores for test | 16, 32, 64 cores |
| **Dtype** | Data type for weights | bfloat16 |
| **KV Cache** | KV cache configuration | Native precision<br>1GiB for embedding |
| **Quantization** | Quantization setting | OFF (Full Precision) |

<!-- markdownlint-enable MD013 MD033 -->

## Test Cases

### LLM Models - Concurrent Tests

Concurrency levels: **{8, 16, 32, 64, 96, 128}**

<!-- markdownlint-disable MD013 -->

| Test ID | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- |
| 1.1 | Llama-3.2-1B | Chat (512:256) | P95 Latency Scaling (Baseline) |
| 1.2 | Llama-3.2-1B | RAG (4096:512) | P95 Latency for Long Context RAG |
| 1.3 | Qwen/Qwen3-0.6B | CodeGen (512:4K) | P95 Latency for Long Output |
| 1.4 | granite-3.2-2b-instruct | RAG (4096:512) | P95 Latency for Enterprise RAG |
| 1.5 | facebook/opt-125m | Summarization (1024:256) | P95 Latency for Summarization |
| 1.6 | Qwen/Qwen3-0.6B | Chat (512:256) | P95 Latency (Efficient Model) |
| 1.7 | granite-3.2-2b-instruct | Chat (512:256) | P95 Latency (Enterprise) |
| 1.8 | TinyLlama-1.1B | Chat (512:256) | P95 Latency (Small Llama) |

<!-- markdownlint-enable MD013 -->

### Embedding Models - Concurrent Tests

Concurrency levels: **{4, 8, 16, 32, 64}**

<!-- markdownlint-disable MD013 -->

| Test ID | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- |
| 1.9 | slate-125m-english-rtrvr-v2 | Embedding (512:1) | P95 Latency (English) |
| 1.10 | granite-embedding-278m-multilingual | Embedding (512:1) | P95 Latency (Multilingual) |

<!-- markdownlint-enable MD013 -->

**Note:** Embedding models use `vllm bench serve` with
`--backend openai-embeddings`.

## Running Tests

### Option 1: Docker/Podman Compose

```bash
# Run all tests in this phase
docker compose up

# Run specific model and scenario
MODEL_NAME=llama-3.2-1b SCENARIO=concurrent-8 docker compose up
```text

### Option 2: Ansible Automation

```bash
# Run entire phase
cd ../../automation/test-execution/ansible
ansible-playbook playbooks/run-phase.yml -e "phase=phase-1-concurrent"

# Run specific model
ansible-playbook playbooks/run-model.yml \
  -e "model_name=llama-3.2-1b" \
  -e "phase=phase-1-concurrent"
```text

### Option 3: Manual Execution (GuideLLM)

```bash
# Example: Test 1.1 - Llama-3.2-1B Chat workload
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile concurrent \
  --warmup 30 \
  --rate 8,16,32,64,96,128 \
  --max-requests 280 \
  --data "prompt_tokens=512,output_tokens=256"
```text

### Option 4: Manual Execution (Embedding Models)

```bash
# Example: Test 1.9 - slate-125m at various concurrency levels
for concurrency in 4 8 16 32 64; do
  vllm bench serve --backend openai-embeddings \
    --model slate-125m-english-rtrvr-v2 \
    --dataset-name random \
    --random-input-len 512 \
    --num-prompts 1000 \
    --endpoint /v1/embeddings \
    --max-concurrency $concurrency \
    --save-result \
    --result-filename "slate-125m-concurrent-${concurrency}.json"
done
```text

## Key Metrics

Monitor these metrics for each concurrency level:

- **P95 E2EL (ms)** - 95th percentile latency (PRIMARY METRIC)
- **P99 E2EL (ms)** - 99th percentile latency
- **Mean E2EL (ms)** - Average end-to-end latency
- **Request throughput (req/s)** - Requests completed per second
- **Token throughput (tok/s)** - Tokens processed per second

### What to Look For

- **Sweet spot**: Concurrency where throughput plateaus but P95 latency is
  acceptable
- **Degradation point**: When P95 latency increases sharply while throughput
  gains diminish
- **Scaling pattern**: How P95 scales from low to high concurrency

## Results

Results are written to:

```text
../../results/
├── by-phase/phase-1-concurrent/
│   ├── llama-3.2-1b/
│   │   ├── concurrent-8.json
│   │   ├── concurrent-16.json
│   │   └── ...
│   └── ...
└── by-model/llama-3.2-1b/phase-1/
```text

## Analysis

Generate reports after completing tests:

```bash
cd ../../automation/analysis

# HTML report for entire phase
python generate-report.py \
  --input ../../results/by-phase/phase-1-concurrent \
  --format html

# Compare models at specific concurrency
python compare-models.py \
  --phase phase-1-concurrent \
  --scenario concurrent-32
```text

## Related Documentation

- [Testing Methodology](../../docs/methodology/overview.md)
- [Metrics Guide](../../docs/methodology/metrics.md)
- [Manual Testing](../../docs/methodology/manual-sweep.md)
- [Phase 2 Tests](../phase-2-scalability/)
