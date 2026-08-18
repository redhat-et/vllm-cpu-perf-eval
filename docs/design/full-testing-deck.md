---
marp: true
theme: default
paginate: true
size: 16:9
html: true
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
  section.divider {
    background: #003366;
    color: white;
    justify-content: center;
    text-align: center;
  }
  section.divider h1 {
    color: white;
    font-size: 2em;
  }
  section.divider p {
    color: #cce0ff;
  }
---

<!-- markdownlint-disable MD024 MD025 -->

# vLLM CPU Performance Evaluation

---

## Overview

**Purpose:** Comprehensive performance evaluation framework for vLLM on CPU
platforms that aligns with
[LLM Inference Benchmark Guide](https://github.com/openshift-psap/LLM-inference-benchmark-guide).

**Key Goals:**

- Establish baseline performance characteristics for CPU inferencing
- Identify optimal operating points (throughput vs. latency)
- Validate production optimizations
- Evaluate embedding model performance and quality on CPU
- Measure offline/batch processing throughput
- Benchmark Audio Models on CPU

---
<!-- _class: divider -->

# The Framework

Test suites · Environments · CLI · Telemetry

---

## Test Suites

Ansible automation is used to drive the following test suites:

| Suite | Flag | Tool | Focus | Status |
|-------|------|------|-------|--------|
| Concurrent Load | `--suite concurrent-load` | GuideLLM | P95 latency scaling under concurrent load | Validated |
| Embedding Models | `--suite embedding` | vllm bench serve | Embedding throughput and latency | Validated |
| Offline Batch | `--suite offline-batch` | vllm bench throughput | Batch processing capacity | Validated |
| Audio Models | `--suite audio` | GuideLLM | Whisper ASR throughput, latency, quality | Validated |
| RHAIIS Sweep | `--suite rhaiis-sweep` | GuideLLM | RHAIIS model concurrent load sweep | Validated |

---
<style scoped>section { font-size: 20px; }</style>

## Testing Environments

**Managed Mode (2-node)** — Online/Embedding/Audio inference.
```text
+--------------------+              +---------------------------+
|  Load Generator    |<------------>|  Device Under Test (DUT)  |
|  GuideLLM /        |              |  vLLM-CPU (container)     |
|  vllm bench serve  |              |  (Intel Xeon / AMD EPYC )   |
+--------------------+              +---------------------------+
```
- vLLM can be 'Managed' or 'External'

**Single-node Mode** — Online/Embedding/Audio.

```text
+------------------------------------------------------+
|  Device Under Test (DUT)                             |
|  ┌──────────────────────┐  ┌──────────────────────┐  |
|  │  Load Generator      │  │  vLLM-CPU (container)│  |
|  │  GuideLLM /          │  │  Intel Xeon / EPYC   │  |
|  │  vllm bench serve    │  └──────────────────────┘  |
|  └──────────────────────┘                            |
+------------------------------------------------------+
```

- Use separate NUMA nodes for Load Generator and vLLM in single-node mode.
- No Network Latency.

<style scoped>blockquote { color: blue; border-left-color: blue; font-style: normal; }</style>
> For Offline benchmarking a single DUT with a single container is used.

---
<style scoped>section{font-size:22px;}</style>

## `cpueval` CLI — Command Reference

cpueval is a wrapper around the ansible automation.

| Command | Description |
|---------|-------------|
| `cpueval doctor` | Validate environment (Ansible, SSH, env vars) |
| `cpueval --suite <name>` | Run a test suite |
| `cpueval list` | List all available suites |
| `cpueval show <suite>` | Show suite details and defaults |
| `cpueval profiles` | List CPU pinning profiles |
| `cpueval results [--last]` | View results in terminal |
| `cpueval dashboard start/stop` | Launch/stop Streamlit dashboard |
| `cpueval --install-completion` | Enable bash/zsh/fish tab completion |

```bash
cpueval doctor
cpueval --suite chat-smoke --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8
cpueval results --last
```
---
<style scoped>section { font-size: 22px; }</style>

## Telemetry — Streamlit & MLflow

**1. Streamlit Dashboard** (`cpueval dashboard start`)

| Page | Content |
|------|---------|
| Client Metrics | LLM latency / throughput curves |
| Server Metrics | vLLM KV cache %, CPU, memory |
| Embedding Metrics | RPS, latency scaling by model |
| Audio Metrics | RTF, WER, throughput by model |
| Offline Batch | Items/hr, tok/s by use case |

**2. MLflow Tracking** — experiment management & cross-run comparison

- Tracks: TTFT, ITL, E2E latency, throughput, KV cache %, CPU/memory
- Deduplication by `test_run_id`; PostgreSQL backend optional
- Launch: `automation/test-execution/mlflow/launch-mlflow.sh`

**3. Grafana** — used during live test runs to track server side stats.

---
<!-- _class: divider -->

# Models & Workloads

---

## Default Concurrent Load Testing Models

`cpueval --suite concurrent-load` (`--models all`)

| Model | Params | Architecture | Context | Gated |
|-------|--------|--------------|---------|-------|
| meta-llama/Llama-3.2-1B-Instruct | 1.2B | Llama 3 | 8K | Yes |
| meta-llama/Llama-3.2-3B-Instruct | 3.2B | Llama 3 | 8K | Yes |
| TinyLlama/TinyLlama-1.1B-Chat-v1.0 | 1.1B | Llama 2 | 2K | No |
| ibm-granite/granite-3.2-2b-instruct | 2B | Granite | 4K | No |
| Qwen/Qwen3-0.6B | 0.6B | Qwen 3 | 8K | No |

<style scoped>blockquote { color: blue; border-left-color: blue; font-style: normal; }</style>
> Also in the matrix: **Qwen2.5-3B-Instruct** (scalability suite only);
> **gpt-oss-20b** (listed for concurrent-load, skipped from default `all` — too large for typical CPU runs).

---
<style scoped>blockquote { color: blue; border-left-color: blue; font-style: normal; }</style>
## Default Embedding Testing Models

| Model | Size | Max Seq | Task |
|-------|------|---------|------|
| RedHatAI/all-MiniLM-L6-v2 | 22.7M | 256 | Sentence Similarity |
| RedHatAI/nomic-embed-text-v1.5 | 137M | 8192 | Sentence Similarity |
| RedHatAI/granite-embedding-english-r2 | 109M | 8192 | Feature Extraction |
| RedHatAI/embeddinggemma-300m | 300M | 2048 | Sentence Similarity |
| RedHatAI/Qwen3-Embedding-8B | 8B | 40960 | Feature Extraction |

**Perf:** `vllm bench serve --backend openai-embeddings`

> *Coming soon*: Guidellm embedding testing support

**Quality:** MTEB (GuideLLM does not support quality embeddings)

---

## Default Audio Testing Models
<style scoped>blockquote { color: red; border-left-color: red; font-style: normal; }</style>

| Model | Size | Architecture | Scenarios |
|-------|------|-------------|-----------|
| openai/whisper-tiny | 39M | Encoder-Decoder | Full suite |
| openai/whisper-small | 244M | Encoder-Decoder | Full suite |
| openai/whisper-medium | 769M | Encoder-Decoder | Subset |

**Scenarios:** `transcription-throughput`, `transcription-latency`,
`audio-duration-scaling`, `constant-rate-stress`, `format-comparison`,
`transcription-quality`, `quick-test`

**Tool:** GuideLLM audio benchmark via `--suite audio`

> \* Audio testing depends on versions of vLLM.

---

## Workload Profiles — Concurrent Load Testing

| Workload | ISL:OSL | max-model-len | Use Case |
|----------|---------|---------------|----------|
| Chat | 512:512 | 2048 | Conversational AI |
| RAG | 7680:512 | 16384 | Long Context Retrieval |
| Code | 1024:1024 | 4096 | Code Generation |
| Summarization | 2048:256 | 4096 | Document Processing |
| Reasoning | 256:2048 | 4096 | Chain-of-Thought |

### Variable LLM (Phase 2)

| Workload | Mean ISL:OSL | Stdev | Range |
|----------|-------------|-------|-------|
| Chat (Variable) | 512:512 | +/-128 | 128-1024 : 256-1024 |
| Code (Variable) | 1024:1024 | +/-256 | 512-2048 : 512-2048 |

**Phase 3**: involves the use of real data sets (TBD)

---
<style scoped>section { font-size: 22px; }</style>

## Workload Profiles — Offline Batch

| Use Case | Dataset | Prompts | Notes |
|----------|---------|---------|-------|
| Summarization | sharegpt | 1000 | Bulk document processing |
| Classification | sharegpt | 1000 | output=64 tokens |
| Translation | sharegpt | 500 | output=1024 tokens |
| Entity Extraction | sharegpt | 1000 | output=128 tokens |
| Dataset Generation | random 256:256 | 5000 | Synthetic data |
| ETL Pipelines | sonnet | 500 | Multi-stage processing |
| Code Generation | random 512:512 | 500 | Code output |
| Long-Doc Summarization | random 4096:256 | 500 | Prefill-heavy |
| Batch RAG | random 2048:128 | 500 | Long context, short answer |
| Shared-Prefix | random 1024:64 | 1000 | Template-shaped I/O |
| Ultra-Short Labeling | sharegpt | 2000 | output=16 tokens |

Core sweep per use case: **8, 16, 24, 32**

---
<!-- _class: divider -->

# Concurrent Load Testing Methodology

3-phase graduated testing approach

---

## 3-Phase Testing Methodology
<style scoped>blockquote { color: blue; border-left-color: blue; font-style: normal; }</style>
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
  /       1        \ Fixed ISL:OSL, No prefix caching, Synthetic
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
<!-- _class: divider -->

# Test Suite Deep-Dives

Concurrent Load · Embedding · Audio · Offline Batch

---

## Concurrent Load — Test Coverage

- **Core counts** (via `--cores`): 8, 16, 32 (defaults)
- **GuideLLM concurrency levels:** 1, 2, 4, 8, 16, 32 (`concurrent` profile)
- **Default workloads** (via `--workloads`): chat, code, summarization, rag
- **Also available:** reasoning (Phase 1); chat_var, code_var (Phase 2)
- **Models:** via `--models` (preset or comma-list)

---

## Embedding Testing — Overview
<style scoped>section { font-size: 22px; }</style>

Performance on CPU via `vllm bench serve` (not GuideLLM yet).

```text
vllm bench serve --backend openai-embeddings --endpoint /v1/embeddings
```
### Performance

#### 1. Sweep

  1. Measure Max throughput (`--request-rate inf`)
  2. Measure 25% / 50% / 75% of max load

#### 2. Latency Concurrent

**Concurrency levels** (`vllm bench serve --max-concurrency`): **16, 32, 64, 128, 196**

### MTEB quality testing

**Tasks** : Banking77, Emotion, ArguAna, NFCorpus, SCIDOCS, STS12, STS15, STS16 ...

---

## Audio Testing — Metrics

| Metric | Description |
|--------|-------------|
| Real-Time Factor (RTF) | Processing time ÷ audio duration (< 1.0 = faster than real-time) |
| Word Error Rate (WER) | Transcription quality (lower is better) |
| Request Throughput (req/s) | Transcription requests per second |
| Time to First Chunk (ms) | Latency to first partial transcript |
| End-to-End Latency (ms) | Full transcription turnaround |
| Audio Duration Processed (s/s) | Seconds of audio per second of compute |

---
<style scoped>section { font-size: 20px; }</style>

## Offline Batch — Overview

`vllm bench throughput` (direct Python API via Podman) — bulk jobs where
**total throughput** matters more than per-request latency.

| Criteria | Offline Batch | Online Server |
|----------|--------------|---------------|
| Interaction | None (batch) | Real-time |
| Latency | Not critical | SLO-critical |
| Priority | Max throughput | Latency + throughput |
| Examples | ETL, docs, datagen | Chat, APIs, online RAG |

### Offline Batch — Core Scaling

Primary tuning axis: **how many cores for this job?**

**Standard cores:** 8, 16, 24, 32

- Small models often saturate earlier
- Short-output tasks saturate sooner than long-output
- Past saturation → better to run a second job in parallel

---
<style scoped>section { font-size: 22px; }</style>

## Offline Batch — Use Cases

<!-- markdownlint-disable MD029 -->
Core counts: **8, 16, 24, 32**

1. **Bulk Summarization** — sharegpt, 1000 prompts
2. **Classification/Tagging** — sharegpt, output=64
3. **Translation** — sharegpt, output=1024
4. **Entity Extraction** — sharegpt, output=128
5. **Dataset Generation** — random 256:256, 5000
6. **ETL Pipelines** — sonnet, 500
7. **Code Generation** — random 512:512, 500
8. **Long-Document Summarization** — random 4096:256, 500
9. **Batch RAG / Grounded Q&A** — random 2048:128, 500
10. **Shared-Prefix / Template** — random 1024:64, 1000
    *(no prefix caching — random prompts share no prefix)*
11. **Ultra-Short Labeling** — sharegpt, output=16, 2000
<!-- markdownlint-enable MD029 -->

---

## Offline Batch — Models & Metrics

| Model | Notes |
|-------|-------|
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8 | INT8 — default sweep |
| RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 | INT4 — default sweep |
| RedHatAI/Qwen3-8B-quantized.w4a16 | INT4 — default sweep |
| RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 | Pruned baseline (excluded from default: context too small) |

**Metrics:** tok/s, req/s, items/hour, batch completion time
(+ prefill/decode, max KV % where available)

---
<!-- _class: divider -->

# Metrics

What we measure across all suites

---

## Metrics — Online Inference (Client)

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
<!-- _class: divider -->

# Infrastructure/vLLM Tuning

KV cache sizing · Measurement stability

---
<style scoped>section { font-size: 18px; }</style>

## KV Cache — Why It Matters

- Stores key/value tensors to avoid recomputation
- Largest memory consumer after model weights
- Caps concurrent requests and throughput

```text
Elements = 2 × layers × tokens × kv_heads × head_size
Bytes    = Elements × dtype_size (bf16 = 2)
Size GB  = Bytes / 1024³
```

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

<style scoped>blockquote { color: red; border-left-color: red; font-style: normal; }</style>
> \*Granite-3.2-2B max context 4K — insufficient for RAG

---
<style scoped>section { font-size: 22px; }</style>

## Stability — Coefficient of Variation

Llama-3.2-1B-Instruct · Chat (512:256) · cores 16/32/64 · concurrency 1, 8, 16 ·
3 runs / config · c8i.metal-48xl · vLLM 0.15.0 CPU · GuideLLM 0.5.3

300s window: 30s warmup · 240s measure · 30s cool (warmup/cooldown excluded)

| Rank | Config | Avg CV | Median CV | Max CV | Grade |
|------|--------|--------|-----------|--------|-------|
| 1 | 32-core | 0.267% | 0.239% | 1.236% | A+ |
| 2 | 16-core | 0.374% | 0.137% | 2.325% | A |
| 3 | 64-core | 1.612% | 1.287% | 5.090% | B+ |

**< 1%** Excellent · **1–3%** Good · **3–5%** Acceptable · **> 5%** Poor

---
<!-- _class: divider -->

# Thank You
