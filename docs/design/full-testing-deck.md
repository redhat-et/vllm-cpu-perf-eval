---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section {
    font-size: 28px;
  }
  h1 {
    font-size: 1.6em;
  }
  h2 {
    font-size: 1.25em;
  }
  table {
    font-size: 0.72em;
  }
  th, td {
    padding: 0.25em 0.45em;
  }
  pre, code {
    font-size: 0.78em;
  }
  ul, ol {
    font-size: 0.92em;
  }
  blockquote {
    font-size: 0.85em;
  }
---

<!-- markdownlint-disable MD024 MD025 -->

# vLLM CPU Performance Evaluation

## Full Testing Methodology

Maryam Tahhan, John Harrigan

---

## Overview

**Purpose:** Comprehensive performance evaluation framework for vLLM on CPU
platforms that aligns with the
[LLM Inference Benchmark Guide](https://github.com/openshift-psap/LLM-inference-benchmark-guide).

**Key Goals:**

- Establish baseline performance characteristics for CPU inferencing
- Identify optimal operating points (throughput vs. latency)
- Characterize architectural differences across models
- Validate production optimizations
- Evaluate embedding model performance and quality on CPU
- Measure offline/batch processing throughput

---

## Test Suites

| Suite | Tool | Focus |
|-------|------|-------|
| Concurrent Load | GuideLLM | P95 latency scaling under concurrent load |
| Embedding Models | vllm bench serve | Embedding throughput and latency |
| Offline Batch | vllm bench throughput | Batch processing capacity |
| Scalability | GuideLLM | Load-latency curves, max throughput |

---

## Testing Environment — Online

### Concurrent Load & Embedding

```text
+---------------------+          +---------------------+
|  Load Generator     |<-------->|  Device Under Test   |
|  GuideLLM /         |          |  vLLM-CPU           |
|  vllm bench serve   |          |  (container)        |
+---------------------+          +---------------------+
```

- **DUT:** Intel Xeon / AMD EPYC running vLLM in container
- **Load Generator:** Separate node (GuideLLM or vllm bench serve)
- **Network:** Same segment, >=10 GbE connectivity

---

## Testing Environment — Offline Batch

```text
+---------------------------------------------+
|           Device Under Test                  |
|  vllm bench throughput (direct Python API)   |
|  No server required                          |
+---------------------------------------------+
```

- **DUT:** Runs `vllm bench throughput` via Podman
- **No HTTP server or load generator** (offline mode)

---

## Workload Profiles — LLM

| Workload | ISL:OSL | max-model-len | Use Case |
|----------|---------|---------------|----------|
| Chat | 512:512 | 2048 | Conversational AI |
| RAG | 7680:512 | 16384 | Long Context Retrieval |
| Code | 1024:1024 | 4096 | Code Generation |
| Summarization | 2048:256 | 4096 | Document Processing |
| Reasoning | 256:2048 | 4096 | Chain-of-Thought |

---

## Workload Profiles — Variable & Embedding

### Variable LLM (Phase 2)

| Workload | Mean ISL:OSL | Stdev | Range |
|----------|-------------|-------|-------|
| Chat (Variable) | 512:512 | +/-128 | 128-1024 : 256-1024 |
| Code (Variable) | 1024:1024 | +/-256 | 512-2048 : 512-2048 |

### Embedding

| Workload | Input Tokens | Output | Use Case |
|----------|-------------|--------|----------|
| Embedding | 512 | 1 (vector) | Semantic search, RAG retrieval |

---

## Workload Profiles — Offline Batch (1/2)

| Use Case | Dataset | Prompts | Notes |
|----------|---------|---------|-------|
| Summarization | sharegpt | 1000 | Bulk document processing |
| Classification | sharegpt | 1000 | output=64 tokens |
| Translation | sharegpt | 500 | output=1024 tokens |
| Entity Extraction | sharegpt | 1000 | output=128 tokens |
| Dataset Generation | random 256:256 | 5000 | Synthetic data |
| ETL Pipelines | sonnet | 500 | Multi-stage processing |

---

## Workload Profiles — Offline Batch (2/2)

| Use Case | Dataset | Prompts | Notes |
|----------|---------|---------|-------|
| Code Generation | random 512:512 | 500 | Code output |
| Long-Doc Summarization | random 4096:256 | 500 | Prefill-heavy |
| Batch RAG | random 2048:128 | 500 | Long context, short answer |
| Shared-Prefix | random 1024:64 | 1000 | Template-shaped I/O |
| Ultra-Short Labeling | sharegpt | 2000 | output=16 tokens |

Core sweep per use case: **8, 16, 24, 32**

---

## LLM Models

| Model | Params | Architecture | Context | Gated |
|-------|--------|--------------|---------|-------|
| meta-llama/Llama-3.2-1B-Instruct | 1.2B | Llama 3 | 8K | Yes |
| meta-llama/Llama-3.2-3B-Instruct | 3.2B | Llama 3 | 8K | Yes |
| TinyLlama/TinyLlama-1.1B-Chat-v1.0 | 1.1B | Llama 2 | 2K | No |
| ibm-granite/granite-3.2-2b-instruct | 2B | Granite | 4K | No |
| Qwen/Qwen3-0.6B | 0.6B | Qwen 3 | 8K | No |
| Qwen/Qwen2.5-3B-Instruct | 3B | Qwen 2.5 | 8K | No |
| openai/gpt-oss-20b | 21B (3.6B act.) | MoE | 128K | No |

---

## Concurrent Load Coverage

- **Concurrency:** 1, 2, 4, 8, 16, 32
- **Workloads:** chat, rag, code, summarization, reasoning, chat_var, code_var
- **Tool:** GuideLLM (`concurrent` profile)

---

## Embedding Models

| Model | Size | Max Seq | Task |
|-------|------|---------|------|
| RedHatAI/all-MiniLM-L6-v2 | 22.7M | 256 | Sentence Similarity |
| RedHatAI/nomic-embed-text-v1.5 | 137M | 8192 | Sentence Similarity |
| RedHatAI/granite-embedding-english-r2 | 109M | 8192 | Feature Extraction |
| RedHatAI/embeddinggemma-300m | 300M | 2048 | Sentence Similarity |
| RedHatAI/Qwen3-Embedding-8B | 8B | 40960 | Feature Extraction |

**Perf:** `vllm bench serve --backend openai-embeddings`
**Quality:** MTEB (GuideLLM does not support embeddings)

---

## Metrics — Online LLM (Client)

| Metric | Description |
|--------|-------------|
| Inter-Token Latency (ms) | Avg time between output tokens (excl. first) |
| Time to First Token (s) | Request → first generated token |
| Total Tokens Throughput (tok/s) | Prompt + output tokens per second |
| Request Rate (req/s) | Requests processed per second |
| End-to-End Latency (ms) | Request → complete response |

---

## Metrics — Embedding & Offline Batch

### Embedding

| Metric | Description |
|--------|-------------|
| Request Throughput (req/s) | Successful requests per second |
| Token Throughput (tok/s) | Input tokens per second |
| Mean / P95 / P99 E2EL (ms) | End-to-end latency |

### Offline Batch

| Metric | Description |
|--------|-------------|
| Throughput (tok/s) | Input + output tokens per second |
| Request Throughput (req/s) | Requests per second |
| Processing Capacity (items/hr) | Extrapolated production capacity |
| Batch Completion Time (s) | Wall-clock time for the batch |

---

## Metrics — System Level

| Metric | Description |
|--------|-------------|
| CPU Utilization (%) | Non-idle CPU time |
| Memory Utilization (GB) | Model weights + KV cache (+ runtime) |

---

## 3-Phase Testing Methodology

> **Note:** 3-phase testing is currently only implemented for Concurrent Load.
> Embedding and Offline Batch use baseline-style approaches.

```text
          /\
         /  \        Phase 3: Production
        / 3  \       Variable ISL:OSL, Prefix caching, Real Dataset
       /------\
      /        \     Phase 2: Realistic
     /    2     \    Variable ISL:OSL, No prefix caching, Synthetic
    /------------\
   /              \  Phase 1: Baseline
  /      1         \ Fixed ISL:OSL, No prefix caching, Synthetic
 /------------------\
```

---

## Phase 1: Baseline

**Fixed tokens, no caching**

**Objectives:** Reproducible baselines, max throughput, single-user latency,
saturation points

**Config:**

- vLLM: `--no-enable-prefix-caching`, `--dtype=bfloat16` or `auto`
- GuideLLM: concurrent, concurrency=[1,2,4,8,16,32], duration=600s, warmup=60s

**Coverage:** 5 workloads × 7 models × 6 concurrency levels
(models filtered by context length)

**Outcome:** Clean baseline for all comparisons

---

## Phase 2: Realistic

**Variable tokens (ISL:OSL), no caching**

**Objectives:** Impact of token variance; stability under variable load

**Changes from Phase 1:**

- chat: 512±128 in / 512±128 out
- code: 1024±256 in / 1024±256 out
- Caching still disabled

**Focus:** Throughput stability, latency variance, P95/P99 spread

---

## Phase 3: Production

**Variable tokens + prefix caching**

> Status: Pending realistic dataset selection

**Config:**

- vLLM: `--enable-prefix-caching`
- GuideLLM: variable tokens (Phase 2), concurrent profile
- Models: Llama-3.2-1B, granite-3.2-2b, gpt-oss-20b

**Analysis:** Phase 3 vs 2 (caching), Phase 3 vs 1 (combined)

---

## Embedding Testing — Overview

Performance on CPU via `vllm bench serve` (not GuideLLM).

```text
vllm bench serve --backend openai-embeddings --endpoint /v1/embeddings
```

| Mode | Description | Best For |
|------|-------------|----------|
| Managed (2-node) | vLLM on DUT, bench on loadgen | Production-like |
| DUT-Only (1-node) | Both on localhost | No network latency |
| External | Existing endpoint | Cloud / K8s |

---

## Embedding Testing — Scenarios

### Baseline Sweep (~20–30 min / model)

1. Max throughput (`--request-rate inf`)
2. 25% / 50% / 75% of max load

### Latency Concurrent (~25–40 min / model)

Concurrency: **16, 32, 64, 128, 196**

---

## Embedding Testing — Coverage Examples

| Test ID | Model | Scenario | Primary Metric |
|---------|-------|----------|----------------|
| EMB-BASELINE-GRANITE-EN-EMB512 | granite-embedding-english-r2 | Baseline | Enterprise EN RPS |
| EMB-BASELINE-GRANITE-ML-EMB512 | granite-embedding-278m-multilingual | Baseline | Multilingual RPS |
| EMB-LATENCY-GRANITE-ML-EMB512 | granite-embedding-278m-multilingual | Latency | P99 scaling |

---

## Embedding — MTEB Quality

| Preset | Tasks | Duration |
|--------|-------|----------|
| quick | Banking77, Emotion | ~5 min |
| retrieval | ArguAna, NFCorpus, SCIDOCS | ~30 min |
| classification | Banking77, Emotion, ToxicConversations | ~15 min |
| sts | STS12, STS15, STS16 | ~20 min |
| comprehensive | Mixed | ~45 min |

---

## Embedding — Perf vs Quality

| Model | Throughput | Quality | Best For |
|-------|-----------|---------|----------|
| all-MiniLM-L6-v2 | Highest | Good | Constrained / high RPS |
| granite-english-r2 | High | High | Balanced enterprise |
| nomic-embed-text-v1.5 | High | High | General purpose |
| embeddinggemma-300m | Medium | High | Quality priority |
| Qwen3-Embedding-8B | Lower | Highest | Max quality / long docs |

---

## Offline Batch — Overview

`vllm bench throughput` (direct Python API via Podman) — bulk jobs where
**total throughput** matters more than per-request latency.

| Criteria | Offline Batch | Online Server |
|----------|--------------|---------------|
| Interaction | None (batch) | Real-time |
| Latency | Not critical | SLO-critical |
| Priority | Max throughput | Latency + throughput |
| Examples | ETL, docs, datagen | Chat, APIs, online RAG |

---

## Offline Batch — Use Cases (1/2)

Core counts: **8, 16, 24, 32**

1. **Bulk Summarization** — sharegpt, 1000 prompts
2. **Classification/Tagging** — sharegpt, output=64
3. **Translation** — sharegpt, output=1024
4. **Entity Extraction** — sharegpt, output=128
5. **Dataset Generation** — random 256:256, 5000
6. **ETL Pipelines** — sonnet, 500

---

## Offline Batch — Use Cases (2/2)

<!-- markdownlint-disable MD029 -->
7. **Code Generation** — random 512:512, 500
8. **Long-Document Summarization** — random 4096:256, 500
9. **Batch RAG / Grounded Q&A** — random 2048:128, 500
10. **Shared-Prefix / Template** — random 1024:64, 1000
    *(no prefix caching — random prompts share no prefix)*
11. **Ultra-Short Labeling** — sharegpt, output=16, 2000
<!-- markdownlint-enable MD029 -->

---

## Offline Batch — Core Scaling

Primary tuning axis: **how many cores for this job?**

**Standard cores:** 8, 16, 24, 32

- Small models often saturate earlier
- Short-output tasks saturate sooner than long-output
- Past saturation → better to run a second job in parallel

---

## Offline Batch — Technical Benchmarks

1. **Baseline** — 4 RedHatAI models × core sweep
2. **Batch size scaling** — 10 … 1000 prompts
3. **Input length** — 128 … 2048
4. **Output length** — 64 … 1024
5. **Quantization** — w8a8 vs w4a16
6. **Core scaling** — 8, 16, 24, 32
7. **KV-cache capacity** — 100 … 5000 prompts
8. **Context scaling** — 1024 … 8192 input tokens

---

## Offline Batch — Models & Metrics

| Model | Notes |
|-------|-------|
| RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 | Pruned, fast baseline |
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8 | INT8 |
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 | INT4 |
| RedHatAI/Qwen3-8B-quantized.w4a16 | INT4 |

**Metrics:** tok/s, req/s, items/hour, batch completion time
(+ prefill/decode, max KV % where available)

---

## KV Cache — Why It Matters

- Stores key/value tensors to avoid recomputation
- Largest memory consumer after model weights
- Caps concurrent requests and throughput

```text
Elements = 2 × layers × tokens × kv_heads × head_size
Bytes    = Elements × dtype_size (bf16 = 2)
Size GB  = Bytes / 1024³
```

---

## KV Cache — Sizing Strategy

- Per-request size from model architecture
- × concurrent requests (e.g. 32)
- × 1.25 safety margin
- Workload-tuned `max_model_len`

| Workload | Tokens | Llama-3.2-1B | Granite-3.2-2B | GPT-OSS-20B |
|----------|--------|--------------|---------------|-------------|
| Chat | 1,024 | 2 GiB | 3 GiB | 2 GiB |
| RAG | 8,192 | 11 GiB | N/A* | 14 GiB |
| Code | 2,048 | 3 GiB | 5 GiB | 4 GiB |
| Summarization | 2,304 | 3 GiB | 4 GiB | 3 GiB |

\*Granite-3.2-2B max context 4K — insufficient for RAG

---

## Stability — Test Setup

- Model: Llama-3.2-1B-Instruct
- Workload: Chat (512:256)
- Cores: 16, 32, 64 *(concurrent-load study)*
- Concurrency: 1, 8, 16
- 3 runs / config · Platform: c8i.metal-48xl
- vLLM 0.15.0 CPU · GuideLLM 0.5.3

```text
|----- 300 s measurement window ----|
| 30s warmup | 240s measure | 30s cool |
```

Warmup/cooldown excluded from reported metrics.

---

## Stability — Coefficient of Variation

| Rank | Config | Avg CV | Median CV | Max CV | Grade |
|------|--------|--------|-----------|--------|-------|
| 1 | 32-core | 0.267% | 0.239% | 1.236% | A+ |
| 2 | 16-core | 0.374% | 0.137% | 2.325% | A |
| 3 | 64-core | 1.612% | 1.287% | 5.090% | B+ |

**< 1%** Excellent · **1–3%** Good · **3–5%** Acceptable · **> 5%** Poor

---

## Status — Concurrent Load & Embeddings

**Concurrent load**

- Repo + live docs published
- Phase 1 & 2 automated (Managed Mode)
- Limits: no Phase 3; scale-up only (not scale-out)

**Embeddings**

- vllm bench serve + Ansible operational
- 5 models · 3 execution modes · MTEB integrated
- Dashboard: Embedding Metrics page

---

## Status — Offline Batch & Infra

**Offline batch**

- 11 use cases + 8 technical benchmarks
- Ansible playbook + bash suite
- Dashboard: Offline Batch page

**Abstraction**

- Backends: vLLM (TGI / llama.cpp planned)
- Loadgens: GuideLLM, vllm-bench, MTEB

**Infra**

- LibOMP fixes under validation
- Red Hat Summit 2026: community day talk accepted

---

## References

- [Methodology Overview](../methodology/overview.md)
- [3-Phase Testing](../methodology/testing-phases.md)
- [Metrics Guide](../methodology/metrics.md)
- [Concurrent Load](../../tests/concurrent-load/concurrent-load.md)
- [Embedding Tests](../../tests/embedding-models/embedding-models.md)
- [Offline Batch](../../tests/offline-batch/offline-batch.md)
- Live docs: <https://redhat-et.github.io/vllm-cpu-perf-eval/>
