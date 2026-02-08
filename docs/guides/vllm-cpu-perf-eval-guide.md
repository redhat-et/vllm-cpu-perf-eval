# vLLM Performance Evaluation Guide - CPU Inferencing

<!-- markdownlint-disable MD033 -->
<span style="color: red">Current status: Draft</span>
<!-- markdownlint-enable MD033 -->

## Contributors

<!-- markdownlint-disable MD060 -->

| Name |
|------|
| Maryam Tahhan |
| John Harrigan |
| Mark Kurtz |
| Tyler Michael Smith |
| Anton Ivanov |
| Luigi Mario Zuccarelli |
| Paul Power |

<!-- markdownlint-enable MD060 -->

## Table of Contents

- [Contributors](#contributors)
- [Introduction](#introduction)
  - [Primary Goals](#primary-goals)
  - [Future Stages](#future-stages)
- [Performance Evaluation Utility](#performance-evaluation-utility)
  - [GuideLLM Parameters](#guidellm-parameters)
    - [Parameter Clarifications](#parameter-clarifications)
- [Testbed Configuration](#testbed-configuration)
- [Guidellm Simulated Workload Rate Types](#guidellm-simulated-workload-rate-types)
- [Models and Testcases](#models-and-testcases)
- [Phase 1](#phase-1)
  - [Models Under Test](#models-under-test)
    - [Core Architectural Coverage](#core-architectural-coverage-from-the-original-list-of-proposed-models)
  - [Test Cases](#test-cases)
    - [Key Test Parameters Legend](#key-test-parameters-legend)
    - [Concurrent Load Tests - Latency and Throughput Scaling](#concurrent-load-tests---latency-and-throughput-scaling)
      - [Embedding Models - Concurrent Tests](#embedding-models---concurrent-tests)
      - [Key Metrics to Monitor](#key-metrics-to-monitor)
- [Phase 2](#phase-2)
  - [Performance and Scalability Tests](#performance-and-scalability-tests)
    - [Embedding Models - Sweep Tests](#embedding-models---sweep-tests)

## Introduction

This guide outlines the first stage of tests, metrics, and procedures for
evaluating the performance of the vLLM framework (CPU Mode) when running Small
Language Models (SLMs)(Tiny Models/Embedded models). This is part of a more
comprehensive evaluation that is structured into multiple stages, with
subsequent stages incorporating additional models, tests and goals.

### Primary Goals

The primary goals of this stage of the performance evaluation effort are to:

- **Establish Baseline Performance for CPU inferencing in vLLM:** Determine the
  fundamental performance characteristics (latency and throughput) of vLLM's
  CPU inferencing capabilities for various SLMs.

### Future Stages

Future stages will incorporate the following goals:

- Establish which models work on CPU
- Establish guidance on coexistence of CPU inference loads and enterprise
  compute/service loads: Assess the performance impact of using a subset of
  cores and/or NUMA nodes in the system.

## Performance Evaluation Utility

The chosen Performance Evaluation tool is **GuideLLM** (specifically v0.4.0).
GuideLLM is a platform for evaluating and optimizing the deployment of Large
Language Models (LLMs). By simulating real-world inference workloads, GuideLLM
enables users to assess the performance, resource requirements, and cost
implications of deploying LLMs on various hardware configurations.

GuideLLM serves a dual role: it functions as the **benchmark utility**,
meaning it provides the framework and metrics for measuring performance, and it
also acts as the **load generator**, meaning it simulates the user requests or
workload necessary to test the system under realistic or stress conditions.

### GuideLLM Parameters

<!-- markdownlint-disable MD013 MD060 -->

| Test Type | Guidellm CLI Parameter Example | Guidellm Podman Parameter Example |
|-----------|--------------------------------|-----------------------------------|
| **concurrent** | `guidellm benchmark --target "http://localhost:8000" --profile concurrent --warmup 30 --rate 8,16,32,64 --max-requests 280 --data "prompt_tokens=256,output_tokens=128"` | `sudo podman run --rm -it --network=host --cpuset-cpus=17-31 -v "/tmp/results:/results:z" -e GUIDELLM_TARGET=http://localhost:8000 -e GUIDELLM_PROFILE=concurrent -e GUIDELLM_RATE=8,16,32,64 -e GUIDELLM_MAX_REQUESTS=280 -e GUIDELLM_WARMUP=30 -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" -e HF_TOKEN=$HF_TOKEN ghcr.io/vllm-project/guidellm:latest` |
| **sweep** | `guidellm benchmark --target "http://localhost:8000" --profile sweep --warmup 30 --rampup 15.0 --max-requests 130 --data "prompt_tokens=256,output_tokens=128"` | `sudo podman run --rm -it --network=host --cpuset-cpus=17-31 -v "/tmp/results:/results:z" -e GUIDELLM_TARGET=http://localhost:8000 -e GUIDELLM_PROFILE=sweep -e GUIDELLM_RAMPUP=15.0 -e GUIDELLM_WARMUP=30 -e GUIDELLM_MAX_REQUESTS=130 -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" -e HF_TOKEN=$HF_TOKEN ghcr.io/vllm-project/guidellm:latest` |
| **poisson** | `guidellm benchmark --target "http://localhost:8000" --profile poisson --warmup 30 --rate 32 --max-requests 280 --data "prompt_tokens=256,output_tokens=128"` | `sudo podman run --rm -it --network=host --cpuset-cpus=17-31 -v "/tmp/results:/results:z" -e GUIDELLM_TARGET=http://localhost:8000 -e GUIDELLM_PROFILE=poisson -e GUIDELLM_RATE=32 -e GUIDELLM_MAX_REQUESTS=280 -e GUIDELLM_WARMUP=30 -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" -e HF_TOKEN=$HF_TOKEN ghcr.io/vllm-project/guidellm:latest` |

<!-- markdownlint-enable MD013 -->

#### Parameter Clarifications

**Warmup (`--warmup`):**

- Excludes initial requests/time from metrics to allow the system to stabilize
- With `--max-requests`: Value represents number of warmup requests (e.g.,
  `--warmup 30` = first 30 requests excluded)
- With time-based tests: Use fraction for percentage (e.g., `--warmup 0.1` =
  10% of duration)
- Warmup requests are executed but not included in final metrics

**Rampup (`--rampup`):**

- Gradually increases request rate over specified seconds to avoid sudden load
  spikes
- Specified in seconds (e.g., `--rampup 15.0` = 15 seconds to reach target
  rate)
- Applicable to: `throughput`, `concurrent`, and `constant` profiles
- Not applicable to: `synchronous` and `poisson` profiles
- Helps identify system behavior during load transitions

> **Note:** GuideLLM does not support embedding endpoints. For embedding model
> testing, use `vllm bench serve` with the `--backend openai-embeddings` flag
> instead.

## Testbed Configuration

<!-- markdownlint-disable MD013 MD060 -->

| Component | Description |
|-----------|-------------|
| **Device Under Test (DUT)** | Server Platform (e.g. Intel Xeon 6, AMD EPYC 9005) |
| **Load Generator** | Separate node (≥ 16 cores), same network segment as DUT (≥ 10 GbE), running GuideLLM |

<!-- markdownlint-enable MD013 MD060 -->

## Guidellm Simulated Workload Rate Types

GuideLLM supports various mechanisms for driving inference load against the
vLLM server, allowing for comprehensive testing across different traffic
patterns. The following table details the simulated workload rate types, which
define how user requests are submitted during the benchmarking process.

<!-- markdownlint-disable MD013 MD033 MD060 -->

| Type | Description | Primary Purpose / What It Measures |
|------|-------------|-------------------------------------|
| **Sweep** | Runs synchronous (min), throughput (max) benchmarks, and then runs a series of benchmarks equally spaced between the two rates. The number of benchmarks is set by `--rate` (default is 10). | • Full load–latency curve (end-to-end scalability profile)<br>• Determines optimal operating point before saturation |
| **Synchronous** | Runs a single stream of requests one at a time | • Baseline model response latency (no concurrency)<br>• Measures raw end-to-end response time per request<br>• Establishes performance floor before parallel load |
| **Throughput** | Issues all requests concurrently to fully saturate the model/server. Equivalent to a "max load" test | • Maximum throughput capacity of the serving system<br>• Identifies saturation point where latency begins to increase sharply<br>• Useful for sizing instances or cores |
| **Constant** | Sends requests at a fixed, steady rate (RPS), regardless of completion time. | • Stability of serving performance under steady, controlled load<br>• Queueing effects when request arrival exceeds processing rate |
| **Poisson** | Sends requests according to a Poisson process (random intervals, same average rate). Simulates unpredictable real-world traffic | • System responsiveness to bursty or stochastic traffic<br>• Latency jitter and recovery time after spikes |
| **Concurrent** | Runs a fixed number of streams of requests in parallel | • Scalability with concurrency<br>• Measures how latency and throughput scale as more users or parallel sessions connect |

<!-- markdownlint-enable MD013 -->

## Models and Testcases

Models and their associated test cases will be broken down into multiple
phases. **Phase 1** will include: Latency and Stability Under Load Tests.
**Phase 2** will include: Performance and Scalability. **Phase 3** will test
the platform's stability under real-world server deployment scenarios using
Resource Contention (Fractional & Noisy Neighbor) tests. **Phase 4** will
include more models and tests that measure the configuration impact of vLLM CPU
tuning and quantization params.

For Phase 1 the models and test cases can be found in the
[Phase 1 section](#phase-1) below.

---

## Phase 1

### Models Under Test

The benchmarking strategy is designed to ensure maximum architectural coverage
for effective CPU inference testing on a vLLM server. This is achieved by:

1. Selecting a representative model from each unique underlying architectural
   family present in the original list of proposed Models.
2. Adding new, essential architectures that stress specific inference phases
   (Decode, Prefill, Balanced) relevant to real-world applications (Code Gen,
   RAG).

#### Core Architectural Coverage (From the original list of proposed Models)

<!-- markdownlint-disable MD013 MD060 -->

| Architecture Family | Representative Model | Key Application Focus |
|--------------------|---------------------|----------------------|
| Llama 3 Decoder | Llama-3.2-1B-Instruct | Prefill-Heavy (Baseline) |
| Llama 2 Decoder | TinyLlama-1.1B-Chat-v1.0 | Prefill/Decode (Small-Scale) |
| Traditional OPT Decoder | facebook/opt-125m | Decode-Heavy (Legacy Baseline) |
| IBM Granite Decoder | granite-3.2-2b-instruct | Balanced (Enterprise Baseline) |
| Qwen 3 Decoder | Qwen/Qwen3-0.6B | Balanced (High-Efficiency) |
| MiniLM/BERT (English Dense) | slate-125m-english-rtrvr-v2 | Encoder-Only (Fastest Baseline) |
| XLM-RoBERTa (Multilingual Dense) | granite-embedding-278m-multilingual | Encoder-Only (Multilingual) |

<!-- markdownlint-enable MD013 MD060 -->

To maintain the focus of this Phase 1 guide on establishing stable, predictable
baselines for core architectures, we have deliberately excluded several
high-complexity models and workloads originally considered.

The following models and corresponding workloads are deferred to subsequent
evaluation stages (Phase 3 or 4) where specific configuration impact and stress
tolerance will be measured:

- **Models Deferred:** Mixtral-8x7B-Instruct-v0.1 (MoE), Codestral-7B
  (Mistral/SWA), Mamba-1.4B (SSM), and Flan-T5-base (Encoder-Decoder).
- **Rationale for Exclusion:** These models introduce advanced computational
  complexity (sparsity, recurrence, sequence-to-sequence) and extreme Prefill
  or Decode performance biases. Their testing is reserved for later phases
  where we will specifically measure the configuration impact of the vLLM CPU
  server under these maximum stress conditions.

### Test Cases

The table below defines the key variables associated with the tests.

#### Key Test Parameters Legend

<!-- markdownlint-disable MD013 MD033 MD060 -->

| Variable | Description | Test Setting |
|----------|-------------|--------------|
| **Models** | Models selected for architectural coverage and application stress testing. | Please see the models table above. |
| **Workload** | Defines input/output token counts (ISL:OSL).<br><br>Input Sequence Length (ISL)<br>Output Sequence Length(OSL) | Defined by GuideLLMs param:<br>`--data=prompt_tokens=ISL,output_tokens=OSL:`<br><br>• Chat (512:256)<br>• RAG (4096:512)<br>• CodeGen (512:4K)<br>• Short CodeGen (256:2K)<br>• Summarization (1024:256)<br>• Embedding (512:1) |
| **Affinity** | Defines core allocation strategy. | FULL: All physical cores,<br>`VLLM_CPU_OMP_THREADS_BIND=auto` |
| **Cores** | Defines the number of cores for a test | Configurations: 16,32,64 cores (find the plateau on a single socket) |
| **Dtype** | Data type used for model weights and computation. | bfloat16 |
| **KV Cache** | MAX: Maximum stable `VLLM_CPU_KVCACHE_SPACE` without OOM.<br><br>MIN: Set `VLLM_CPU_KVCACHE_SPACE=1GiB` (or minimum stable value) | KV cache at the native precision for the model<br><br>`VLLM_CPU_KVCACHE_SPACE=1GiB` (for embedding models). |
| **Quantization (Q)** | Explicitly set for quantized models (`--quantization awq`). | OFF: Default/Full Precision (`--quantization none`).<br>Not used unless specified by the model e.g. (`--quantization awq`). |

<!-- markdownlint-enable MD013 -->

#### Concurrent Load Tests - Latency and Throughput Scaling

This phase uses concurrent tests at defined concurrency levels to measure how
P95 latency and throughput scale as the number of parallel request streams
increases.

<!-- markdownlint-disable MD013 MD060 -->

| Test Case ID | Test Type | Model | Workload Profile | Concurrency (Fixed Rate) | Affinity | Primary Metric Focus |
|--------------|-----------|-------|------------------|-------------------------|----------|---------------------|
| 1.1 | concurrent | Llama-3.2-1B | Chat (512:256) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency Scaling for Llama Baseline |
| 1.2 | concurrent | Llama-3.2-1B | RAG (4096:512) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency for Long Context RAG (Llama baseline) |
| 1.3 | concurrent | Qwen/Qwen3-0.6B | CodeGen (512:4K) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency for Long Output Code Generation |
| 1.4 | concurrent | granite-3.2-2b-instruct | RAG (4096:512) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency for Enterprise RAG Workload |
| 1.5 | concurrent | facebook/opt-125m | Summarization (1024:256) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency for Summarization (Legacy Architecture) |
| 1.6 | concurrent | Qwen/Qwen3-0.6B | Chat (512:256) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency Scaling for Highly-Efficient Model |
| 1.7 | concurrent | granite-3.2-2b-instruct | Chat (512:256) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency Scaling for Enterprise Baseline |
| 1.8 | concurrent | TinyLlama-1.1B | Chat (512:256) | {8, 16, 32, 64, 96, 128} | FULL | P95 Latency for Smallest Llama Variant |

<!-- markdownlint-enable MD013 -->

##### Embedding Models - Concurrent Tests

<!-- markdownlint-disable MD013 MD060 -->

| Test Case ID | Test Type | Model | Workload Profile | Concurrency (Fixed Rate) | Affinity | Primary Metric Focus |
|--------------|-----------|-------|------------------|-------------------------|----------|---------------------|
| 1.9 | vllm bench serve | slate-125m-english-rtrvr-v2 | Embedding (512:1) | {4, 8, 16, 32, 64} | FULL | P95 Latency Scaling for English Encoder |
| 1.10 | vllm bench serve | granite-embedding-278m-multilingual | Embedding (512:1) | {4, 8, 16, 32, 64} | FULL | P95 Latency Scaling for Multilingual Encoder |

<!-- markdownlint-enable MD013 -->

Guidellm doesn't support embedding model testing, `vllm bench serve` will be
used for these tests to simulate a similar run to guidellm's concurrent test.
This test measures how end-to-end latency scales as concurrency increases,
helping identify the optimal concurrency level before latency degrades
significantly.

**Test Execution example:**

```bash
# Test 1.9 & 1.10 - Concurrent latency scaling for embedding models
# Run at each concurrency level to measure P95 latency scaling
# Replace <model> with the model being tested
for concurrency in 4 8 16 32 64; do
  vllm bench serve --backend openai-embeddings \
    --model <model> \
    --dataset-name random \
    --random-input-len 512 \
    --num-prompts 1000 \
    --endpoint /v1/embeddings \
    --max-concurrency $concurrency \
    --save-result \
    --result-filename "<model>-concurrent-${concurrency}.json"
done
```

#### Key Metrics to Monitor

For each concurrency level, examine:

- Mean E2EL (ms) - Average end-to-end latency
- P95 E2EL (ms) - 95th percentile latency (primary metric)
- P99 E2EL (ms) - 99th percentile latency
- Request throughput (req/s) - Actual requests completed per second
- Total token throughput (tok/s) - Input tokens processed per second

**Example Output Interpretation:**

```text
# Example output at --max-concurrency 32
Request throughput (req/s):    38.42
Total Token throughput (tok/s): 19,670.4
Mean E2EL (ms):                832.5
P95 E2EL (ms):                 945.2
P99 E2EL (ms):                 1,024.8
```

**What to look for:**

- **Sweet spot:** Concurrency level where throughput plateaus but P95
  latency remains acceptable
- **Degradation point:** When P95 latency starts increasing significantly
  while throughput gains diminish
- **Comparison:** How P95 scales from low (4) to high (64) concurrency

---

## Phase 2

### Performance and Scalability Tests

This phase uses sweep tests to generate the full load-latency curve and
identify maximum throughput capability (Max OTPS/TTPS), synchronous tests for
baseline latency, and poisson tests to measure responsiveness to bursty traffic
patterns.

<!-- markdownlint-disable MD013 MD060 -->

| Test Case ID | Test Type | Model | Workload Profile | KV Cache | Quantization | Primary Metric Focus |
|--------------|-----------|-------|------------------|----------|--------------|---------------------|
| 2.1 | sweep | Llama-3.2-1B | Chat (512:256) | MAX | OFF | Max Throughput (OTPS/TTPS) |
| 2.2 | sweep | Llama-3.2-1B | RAG (4096:512) | MAX | OFF | KV Cache Efficiency / TTFT Scaling (Llama baseline) |
| 2.3 | sweep | Qwen/Qwen3-0.6B | CodeGen (512:4K) | MAX | OFF | Decoding Efficiency (ITL) for Long Output on Quantized Model |
| 2.4 | Sweep | granite-3.2-2b-instruct | RAG (4096:512) | MAX | OFF | Prefill TTFT Scaling for Enterprise Baseline |
| 2.5 | Sweep | facebook/opt-125m | Summarization (1024:256) | MAX | OFF | Balanced Throughput of Legacy Architecture |
| 2.6 | sweep | Qwen/Qwen3-0.6B | Chat (512:256) | MAX | OFF | Max Throughput of Highly-Efficient Quantized Model |
| 2.7 | sweep | granite-3.2-2b-instruct | Chat (512:256) | MAX | OFF | Max Throughput of Enterprise Baseline |
| 2.8 | synchronous | TinyLlama-1.1B | Chat (512:256) | MIN | OFF | Raw Baseline Latency (No Contention) |
| 2.9 | poisson | Qwen/Qwen3-0.6B | CodeGen (512:4K) | Target RPS @ 60% of Max (from 2.3) | MAX | Responsiveness to Burstiness in Code Workloads |
| 2.10 | poisson | granite-3.2-2b-instruct | Chat (512:256) | Target RPS @ 60% of Max (from 2.7) | MAX | Responsiveness to Bursty Enterprise Traffic |

<!-- markdownlint-enable MD013 -->

#### Embedding Models - Sweep Tests

<!-- markdownlint-disable MD013 MD060 -->

| Test Case ID | Test Type | Model | Workload Profile | KV Cache | Quantization | Primary Metric Focus |
|--------------|-----------|-------|------------------|----------|--------------|---------------------|
| 2.11 | vllm bench serve | slate-125m-english-rtrvr-v2 | Embedding (512:1) | 1 | OFF | Enterprise English Embedding Throughput (RPS) |
| 2.12 | vllm bench serve | granite-embedding-278m-multilingual | Embedding (512:1) | 1 | OFF | Multilingual Embedding Throughput (RPS) |

<!-- markdownlint-enable MD013 -->

Guidellm doesn't support embedding model testing, `vllm bench serve` will be
used for these tests to simulate a similar run to guidellm's sweep.

1. Start by measuring the default (infinite rate) to find your maximum. Then
   look at the output - it will show you the actual request throughput (req/s)
   achieved. Use that value for follow-up tests (at 25%, 50%, 75% of max
   req/s).
2. Run follow up tests at at 25%, 50%, 75% of max req/s

**Example output interpretation for an infinite rate test run (step1):**

```text
Request throughput (req/s): 42.35
```

This means your max is ~42 req/s. Then test at: 10, 21, 31 req/s (25%, 50%,
75%) to see latency curves.

**Full example is shown below:**

```bash
# 1. Max throughput baseline
vllm bench serve --backend openai-embeddings \
  --model <model> \
  --dataset-name random \
  --random-input-len 512 \
  --num-prompts 1000 \
  --endpoint /v1/embeddings \
  --save-result \
  --result-filename "<model>-sweep-inf.json"

# 2. 25% rate
vllm bench serve --backend openai-embeddings \
  --model <model> \
  --dataset-name random \
  --random-input-len 512 \
  --num-prompts 1000 \
  --endpoint /v1/embeddings \
  --request-rate 10 \
  --save-result \
  --result-filename "<model>-sweep-25pct.json"

# 3. 50% rate
vllm bench serve --backend openai-embeddings \
  --model <model> \
  --dataset-name random \
  --random-input-len 512 \
  --num-prompts 1000 \
  --endpoint /v1/embeddings \
  --request-rate 21 \
  --save-result \
  --result-filename "<model>-sweep-50pct.json"

# 4. 75% rate
vllm bench serve --backend openai-embeddings \
  --model <model> \
  --dataset-name random \
  --random-input-len 512 \
  --num-prompts 1000 \
  --endpoint /v1/embeddings \
  --request-rate 31 \
  --save-result \
  --result-filename "<model>-sweep-75pct.json"
```
