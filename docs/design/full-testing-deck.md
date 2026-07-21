<!-- markdownlint-disable MD024 -->

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

**Test Suites:**

| Suite | Tool | Focus |
|-------|------|-------|
| Concurrent Load | GuideLLM | P95 latency scaling under concurrent load |
| Embedding Models | vllm bench serve | Embedding throughput and latency |
| Offline Batch | vllm bench throughput | Batch processing capacity |
| Scalability | GuideLLM | Load-latency curves, max throughput |

---

## Testing Environment/Setup

### Online Inference Testing (Concurrent Load, Embedding)

```text
+---------------------+          +---------------------+
|  Load Generator     |<-------->|  Device Under Test   |
|  GuideLLM /         |          |  vLLM-CPU           |
|  vllm bench serve   |          |  (container)        |
+---------------------+          +---------------------+
```

**Components:**

- **DUT:** Intel Xeon / AMD EPYC running vLLM in container
- **Load Generator:** Separate node running GuideLLM or vllm bench serve
- **Network:** Same segment, >=10 GbE connectivity

### Offline Batch Testing

```text
+---------------------------------------------+
|           Device Under Test                  |
|  vllm bench throughput (direct Python API)   |
|  No server required                          |
+---------------------------------------------+
```

**Components:**

- **DUT:** Runs `vllm bench throughput` directly via Podman container
- **No server or load generator needed** (offline mode)

---

## Workload Profiles

### LLM Workloads

| Workload | ISL:OSL | max-model-len | Use Case |
|----------|---------|---------------|----------|
| Chat | 512:512 | 2048 | Conversational AI |
| RAG | 7680:512 | 16384 | Long Context Retrieval |
| Code | 1024:1024 | 4096 | Code Generation |
| Summarization | 2048:256 | 4096 | Document Processing |
| Reasoning | 256:2048 | 4096 | Chain-of-Thought |

### Variable LLM Workloads (Phase 2)

| Workload | Mean ISL:OSL | Stdev | Range |
|----------|-------------|-------|-------|
| Chat (Variable) | 512:512 | +/-128 | 128-1024 : 256-1024 |
| Code (Variable) | 1024:1024 | +/-256 | 512-2048 : 512-2048 |

### Embedding Workloads

| Workload | Input Tokens | Output | Use Case |
|----------|-------------|--------|----------|
| Embedding | 512 | 1 (vector) | Semantic search, RAG retrieval |

### Offline Batch Workloads

| Use Case | Dataset | Prompts | Notes |
|----------|---------|---------|-------|
| Summarization | sharegpt | 1000 | Bulk document processing |
| Classification | sharegpt | 1000 | output=64 tokens |
| Translation | sharegpt | 500 | output=1024 tokens |
| Entity Extraction | sharegpt | 1000 | output=128 tokens |
| Dataset Generation | random 256:256 | 5000 | Synthetic data |
| ETL Pipelines | sonnet | 500 | Multi-stage processing |
| Code Generation | random 512:512 | 500 | Code output |
| Long-Doc Summarization | random 4096:256 | 500 | Prefill-heavy, long input |
| Batch RAG | random 2048:128 | 500 | Long context, short answer |
| Shared-Prefix | random 1024:64 | 1000 | Short-output template shape |
| Ultra-Short Labeling | sharegpt | 2000 | output=16 tokens |

Each use case is run across multiple core counts (e.g. 8, 16, 32, 64) to
identify the optimal core allocation for that workload.

---

## LLM Models

| Model | Parameters | Architecture | Context Length | Gated |
|-------|-----------|--------------|---------------|-------|
| meta-llama/Llama-3.2-1B-Instruct | 1.2B | Llama 3 Decoder | 8K | Yes |
| meta-llama/Llama-3.2-3B-Instruct | 3.2B | Llama 3 Decoder | 8K | Yes |
| TinyLlama/TinyLlama-1.1B-Chat-v1.0 | 1.1B | Llama 2 Decoder | 2K | No |
| ibm-granite/granite-3.2-2b-instruct | 2B | IBM Granite | 4K | No |
| Qwen/Qwen3-0.6B | 0.6B | Qwen 3 Decoder | 8K | No |
| Qwen/Qwen2.5-3B-Instruct | 3B | Qwen 2.5 Decoder | 8K | No |
| openai/gpt-oss-20b | 21B (3.6B active) | Transformer MoE | 128K | No |

**Concurrent Load Testing:**

- Concurrency Levels: 1, 2, 4, 8, 16, 32
- Workloads: chat, rag, code, summarization, reasoning, chat_var, code_var
- Tool: GuideLLM (concurrent profile)

---

## Embedding Models

| Model | Size | Max Seq Len | Task |
|-------|------|-------------|------|
| RedHatAI/all-MiniLM-L6-v2 | 22.7M | 256 | Sentence Similarity |
| RedHatAI/nomic-embed-text-v1.5 | 137M | 8192 | Sentence Similarity |
| RedHatAI/granite-embedding-english-r2 | 109M | 8192 | Feature Extraction |
| RedHatAI/embeddinggemma-300m | 300M | 2048 | Sentence Similarity |
| RedHatAI/Qwen3-Embedding-8B | 8B | 40960 | Feature Extraction |

**Performance Testing Tool:** `vllm bench serve` with `--backend openai-embeddings`

> GuideLLM does not support embedding endpoints. Use `vllm bench serve` instead.

**Quality Testing Tool:** MTEB (Massive Text Embedding Benchmark)

---

## Metrics

### Key Metrics: LLM Workload/Client-side

| METRIC (unit) | DESCRIPTION |
|---------------|-------------|
| Inter-Token Latency (ms) | (ITL) - Average time between consecutive output tokens, excluding first token |
| Time to First Token (s) | (TTFT) - Time from request submission to first generated token |
| Total Tokens Throughput (tokens/s) | Combined rate of prompt and output tokens processed per second |
| Request Rate (requests/s) | Number of requests processed per second |
| End-to-End Latency (ms) | Time from request submission to complete response (Total Latency) |

### Key Metrics: Embedding Workload

| METRIC (unit) | DESCRIPTION |
|---------------|-------------|
| Request Throughput (req/s) | Total requests successfully processed per second |
| Token Throughput (tok/s) | Combined rate of input tokens processed per second |
| Mean E2EL (ms) | Average end-to-end latency from request to response |
| P95/P99 E2EL (ms) | 95th/99th percentile end-to-end latency |

### Key Metrics: Offline Batch

| METRIC (unit) | DESCRIPTION |
|---------------|-------------|
| Throughput (tokens/s) | Tokens processed per second (input + output) |
| Request Throughput (req/s) | Requests processed per second |
| Processing Capacity (items/hr) | Estimated items processable per hour |
| Batch Completion Time (s) | Total time to process the batch |

### System Level Metrics

| Metric | Description |
|--------|-------------|
| CPU Utilization (%) | Percentage of time the CPU is busy executing non-idle threads |
| Memory Utilization (GB) | Total memory used by vLLM, including model weights and KV cache |

---

## 3-Phase Testing Methodology

> **Note:** 3-phase testing is currently only implemented for Concurrent Load
> tests. Embedding and Offline Batch tests use baseline testing approaches.

```text
          /\
         /  \        Phase 3: Production
        / 3  \       Variable ISL:OSL, Prefix caching, Real Dataset
       /------\
      /        \     Phase 2: Realistic
     /    2     \    Variable ISL:OSL, No prefix caching, Synthetic Dataset
    /------------\
   /              \  Phase 1: Baseline
  /      1         \ Fixed ISL:OSL, No prefix caching, Synthetic Dataset
 /------------------\
```

---

## Phase 1: Baseline Tests

**Fixed Tokens, No Caching**

**Objectives:**

- Establish reproducible performance benchmarks
- Identify maximum throughput capabilities
- Measure single-user latency for efficiency
- Determine saturation points

**Configuration:**

- vLLM: `--no-enable-prefix-caching`, `--dtype=bfloat16` (FP16) or `--dtype=auto`
- GuideLLM: profile=concurrent, concurrency=[1,2,4,8,16,32], duration=600s, warmup=60s

**Test Coverage:** 5 workloads x 7 models x 6 concurrency levels
(models filtered by context length compatibility)

**Key Metrics:** P95/P99 latency curves, maximum throughput (req/s, tok/s),
TTFT, ITL

**Outcome:** Clean, stable baseline for all comparisons

---

## Phase 2: Realistic Tests

**Variable Tokens (ISL:OSL), No Caching**

**Objectives:**

- Quantify impact of token distribution variance
- Measure performance stability under variable load
- Enable realistic vs. baseline comparison

**Changes from Phase 1:**

- Token Distribution: Variable with statistical distribution
  - chat: 512+/-128 input, 512+/-128 output
  - code: 1024+/-256 input, 1024+/-256 output
- Caching: Still disabled (same as Phase 1)

**Analysis Focus:**

- Throughput stability with variable batch sizes
- Latency variance impact on batch processing efficiency
- P95/P99 spread analysis

---

## Phase 3: Production Tests

**Variable Tokens, With Caching**

> Status: Pending realistic dataset selection

**Objectives:**

- Simulate true production conditions
- Measure real-world performance with all optimizations
- Quantify combined impact of variability + caching

**Configuration:**

- vLLM: `--enable-prefix-caching`
- GuideLLM: Variable tokens (same as Phase 2), concurrent profile
- Select models: Llama-3.2-1B-Instruct, granite-3.2-2b-instruct, gpt-oss-20b

**Analysis:**

- Compare Phase 3 vs. Phase 2 (caching impact with variance)
- Compare Phase 3 vs. Phase 1 (combined optimizations)
- True production latency/throughput characteristics

---

## Embedding Model Testing

### Overview

Embedding model performance evaluation on CPU using `vllm bench serve`
(not GuideLLM, which does not support embedding endpoints).

**Tool:** `vllm bench serve --backend openai-embeddings --endpoint /v1/embeddings`

### Execution Modes

| Mode | Description | Best For |
|------|-------------|----------|
| Managed (2-node) | vLLM on DUT, vllm bench on load generator | Production-like testing |
| DUT-Only (1-node) | Both on same node (localhost) | Eliminating network latency |
| External | Test existing vLLM endpoint | Cloud/K8s deployments |

### Test Scenarios

#### Baseline Sweep

Establishes maximum throughput and performance scaling across load levels.

**Stages:**

1. Max throughput (`--request-rate inf`)
2. 25% of max load
3. 50% of max load
4. 75% of max load

**Duration:** ~20-30 minutes per model

#### Latency Concurrent

Measures latency scaling under increasing concurrent requests.

**Concurrency Levels:** 16, 32, 64, 128, 196

**Duration:** ~25-40 minutes per model

### Test Coverage

<!-- markdownlint-disable MD013 -->

| Test ID | Model | Scenario | Primary Metric |
|---------|-------|----------|----------------|
| EMB-BASELINE-GRANITE-EN-EMB512 | granite-embedding-english-r2 | Baseline Sweep | Enterprise English RPS |
| EMB-BASELINE-GRANITE-ML-EMB512 | granite-embedding-278m-multilingual | Baseline Sweep | Multilingual RPS |
| EMB-LATENCY-GRANITE-ML-EMB512 | granite-embedding-278m-multilingual | Latency Concurrent | P99 Latency Scaling |

<!-- markdownlint-enable MD013 -->

### MTEB Quality Testing

In addition to performance, embedding quality is evaluated using MTEB
(Massive Text Embedding Benchmark).

| Preset | Tasks | Duration |
|--------|-------|----------|
| quick | Banking77, Emotion | ~5 min |
| retrieval | ArguAna, NFCorpus, SCIDOCS | ~30 min |
| classification | Banking77, Emotion, ToxicConversations | ~15 min |
| sts | STS12, STS15, STS16 | ~20 min |
| comprehensive | Mixed tasks | ~45 min |

### Performance vs Quality Trade-offs

| Model | Throughput | Quality | Best For |
|-------|-----------|---------|----------|
| all-MiniLM-L6-v2 | Highest | Good | High throughput, resource-constrained |
| granite-english-r2 | High | High | Balanced enterprise use |
| nomic-embed-text-v1.5 | High | High | General purpose |
| embeddinggemma-300m | Medium | High | Quality priority |
| Qwen3-Embedding-8B | Lower | Highest | Maximum quality, long documents |

---

## Offline Batch Testing

### Overview

Offline/static batch benchmarking using `vllm bench throughput` — the direct
Python API, not the HTTP server mode. Designed for bulk processing workloads
where latency per request is less important than total throughput.

**Tool:** `vllm bench throughput` via Podman container

### When to Use Offline Batch vs. Online Server Testing

<!-- markdownlint-disable MD013 -->

| Criteria | Offline Batch | Online Server |
|----------|--------------|---------------|
| User interaction | None (batch jobs) | Real-time requests |
| Latency requirement | Not critical | Critical (SLOs) |
| Throughput priority | Maximum | Balanced with latency |
| Examples | Document processing, ETL, dataset generation | Chatbots, APIs, RAG |

<!-- markdownlint-enable MD013 -->

### Use Cases (11 Scenarios)

Each use case is tested across a range of core counts (e.g. 8, 16, 32, 64)
to identify the optimal core allocation for that workload.

1. **Bulk Summarization** - sharegpt, 1000 prompts
2. **Classification/Tagging** - sharegpt, 1000 prompts, output=64 tokens
3. **Translation** - sharegpt, 500 prompts, output=1024 tokens
4. **Entity Extraction** - sharegpt, 1000 prompts, output=128 tokens
5. **Dataset Generation** - random 256:256, 5000 prompts
6. **ETL Pipelines** - sonnet, 500 prompts
7. **Code Generation** - random 512:512, 500 prompts
8. **Long-Document Summarization** - random 4096:256, 500 prompts
9. **Batch RAG / Grounded Q&A** - random 2048:128, 500 prompts
10. **Shared-Prefix / Template Batch** - random 1024:64, 1000 prompts
11. **Ultra-Short Labeling** - sharegpt, 2000 prompts, output=16 tokens

### Core Scaling

All offline batch tests sweep across core counts to find the best
throughput for each model/workload combination:

**Core counts tested:** 8, 16, 32, 64

This is the primary tuning axis — different models and workloads saturate
at different core counts, and more cores does not always mean better
throughput.

### Technical Benchmarks (8 Tests)

In addition to per-use-case core sweeps, dedicated benchmarks isolate
individual variables:

1. **Baseline throughput** across 4 RedHatAI models (all core counts)
2. **Batch size scaling** (10, 50, 100, 250, 500, 1000)
3. **Input length variation** (128, 256, 512, 1024, 2048)
4. **Output length variation** (64, 128, 256, 512, 1024)
5. **Quantization comparison** (w8a8, w4a16)
6. **Core scaling** (8, 16, 32, 64 cores)
7. **KV-cache capacity sweep** (100, 250, 500, 1000, 2000, 5000 prompts)
8. **Context length scaling** (1024, 2048, 4096, 8192 input tokens)

### Offline Batch Models

| Model | Parameters | Notes |
|-------|-----------|-------|
| RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 | 1.1B | Pruned, fast baseline |
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8 | 8B | INT8 quantized |
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 | 8B | INT4 quantized |
| RedHatAI/Qwen3-8B-quantized.w4a16 | 8B | INT4 quantized |

### Key Metrics

- **Throughput** (tokens/sec) - Total tokens processed per second
- **Request throughput** (req/sec) - Requests completed per second
- **Processing capacity** (items/hour) - Estimated production capacity
- **Batch completion time** (seconds) - Total processing time

---

## KV Cache

### What is KV Cache and Why It Matters

- **What:** Stores key-value tensors during inference to avoid recomputation
- **Why:** Enables efficient autoregressive generation
- **Memory Impact:** Largest memory consumer after model weights
- **Performance Impact:** Directly affects maximum concurrent requests and
  throughput

### KV Cache Sizing Formula

```text
Total Elements = 2 x num_layers x total_tokens x num_kv_heads x head_size
Total Bytes = Total Elements x dtype_size (bfloat16 = 2 bytes)
KV Cache Size (GB) = Total Bytes / (1024^3)
```

### Sizing Strategy

- Per-request size calculated from model architecture
- Multiplied by concurrent requests (32 in our tests)
- 25% safety margin (1.25x) for stability
- Workload-optimized max_model_len for best performance

### KV Cache Sizing Examples

| Workload | Tokens | Llama-3.2-1B | Granite-3.2-2B | GPT-OSS-20B |
|----------|--------|-------------|----------------|-------------|
| Chat | 1,024 | 2 GiB | 3 GiB | 2 GiB |
| RAG | 8,192 | 11 GiB | N/A* | 14 GiB |
| Code | 2,048 | 3 GiB | 5 GiB | 4 GiB |
| Summarization | 2,304 | 3 GiB | 4 GiB | 3 GiB |

*Granite-3.2-2B has 4K context, insufficient for RAG workload

---

## Stability/Repeatability of Results

### Test Configuration

- Model: Llama-3.2-1B-Instruct
- Chat workload (512:256)
- Core configurations: 16, 32, 64 cores
- Concurrency levels: 1, 8, 16
- 3 runs per configuration
- Platform: c8i.metal-48xl (AWS)
- vLLM: v0.15.0 (CPU backend), GuideLLM: v0.5.3

### Benchmark Run Anatomy

```text
|-- 300 s ------------------------------------------|
| 30s warmup | 240s measurement window | 30s cooldown|
```

- **Warmup:** System initialization, cache filling, scheduler stabilization
  (excluded from results)
- **Measurement:** Core benchmarking phase, strict boundary enforcement
- **Cooldown:** Prevents edge-effect errors and request truncation
  (excluded from results)

### Coefficient of Variation Results

| Rank | Configuration | Avg CV | Median CV | Max CV | Grade |
|------|--------------|--------|-----------|--------|-------|
| 1 | 32-core | 0.267% | 0.239% | 1.236% | A+ |
| 2 | 16-core | 0.374% | 0.137% | 2.325% | A |
| 3 | 64-core | 1.612% | 1.287% | 5.090% | B+ |

Grading scale: < 1.0% Excellent (A+), 1.0-3.0% Good (A to B+),
3.0-5.0% Acceptable (B), > 5.0% Poor (C)

---

## Status Update

- **Concurrent load test automation**
  - Repo: <https://github.com/redhat-et/vllm-cpu-perf-eval>
  - Live docs: <https://redhat-et.github.io/vllm-cpu-perf-eval/>
  - Phase 1 and 2 automated via Ansible (Managed Mode)
  - Limitations: No Phase 3, scale up not scale out
- **Embedding model testing**
  - Automation with vllm bench serve + Ansible operational
  - 5 models supported across 3 execution modes
  - MTEB quality testing integrated
  - Dashboard visualization available (Embedding Metrics page)
- **Offline batch testing**
  - 11 use-case scenarios + 8 technical benchmarks automated
  - Ansible playbook + bash test suite
  - Dashboard visualization (Offline Batch page)
- **Backend/Load Generator Abstraction**
  - Phase 1 (backends): vLLM implemented, TGI/llama.cpp planned
  - Phase 2 (load generators): GuideLLM, vllm-bench, MTEB implemented
- **Infrastructure**
  - LibOMP bugfixes being validated
  - Red Hat Summit 2026: talk accepted for community dev day

---

## References

- [Testing Methodology Overview](../methodology/overview.md)
- [3-Phase Testing Methodology](../methodology/testing-phases.md)
- [Metrics Guide](../methodology/metrics.md)
- [LLM Model Matrix](../../models/llm-models/model-matrix.yaml)
- [Embedding Model Matrix](../../models/embedding-models/model-matrix.yaml)
- [Concurrent Load Tests](../../tests/concurrent-load/concurrent-load.md)
- [Embedding Model Tests](../../tests/embedding-models/embedding-models.md)
- [Offline Batch Tests](../../tests/offline-batch/offline-batch.md)
- [Embedding Models Guide](../embedding-models.md)
