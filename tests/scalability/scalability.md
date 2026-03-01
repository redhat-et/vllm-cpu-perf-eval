# Test Suite: Scalability

Characterizes maximum throughput and generates complete load-latency curves.

## Overview

This test suite uses sweep tests to generate full load-latency curves and identify
maximum throughput capability, synchronous tests for baseline latency, and
Poisson tests to measure responsiveness to bursty traffic patterns.

## Goals

- Identify maximum throughput (Max OTPS/TTPS)
- Generate complete load-latency curves via sweep tests
- Measure baseline single-threaded latency
- Test responsiveness to bursty/unpredictable traffic
- Assess KV cache efficiency at high load

## Test Cases

### LLM Models - Sweep Tests

<!-- markdownlint-disable MD013 -->

| Test ID | Test Type | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- | --- |
| SCALE-SWEEP-LLAMA32-CHAT | sweep | Llama-3.2-1B | Chat (512:256) | Max Throughput (OTPS/TTPS) |
| SCALE-SWEEP-LLAMA32-RAG | sweep | Llama-3.2-1B | RAG (4096:512) | KV Cache Efficiency / TTFT Scaling |
| SCALE-SWEEP-QWEN06-CODE | sweep | Qwen/Qwen3-0.6B | CodeGen (512:4K) | Decoding Efficiency (ITL) Long Output |
| SCALE-SWEEP-GRANITE32-RAG | sweep | granite-3.2-2b-instruct | RAG (4096:512) | Prefill TTFT Scaling (Enterprise) |
| SCALE-SWEEP-OPT125M-SUMM | sweep | facebook/opt-125m | Summarization (1024:256) | Balanced Throughput (Legacy) |
| SCALE-SWEEP-QWEN06-CHAT | sweep | Qwen/Qwen3-0.6B | Chat (512:256) | Max Throughput (Efficient Model) |
| SCALE-SWEEP-GRANITE32-CHAT | sweep | granite-3.2-2b-instruct | Chat (512:256) | Max Throughput (Enterprise) |

<!-- markdownlint-enable MD013 -->

### LLM Models - Synchronous Baseline

<!-- markdownlint-disable MD013 -->

| Test ID | Test Type | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- | --- |
| SCALE-SYNC-TINY11-CHAT | synchronous | TinyLlama-1.1B | Chat (512:256) | Raw Baseline Latency (No Contention) |

<!-- markdownlint-enable MD013 -->

### LLM Models - Poisson (Bursty Traffic)

<!-- markdownlint-disable MD013 -->

| Test ID | Test Type | Model | Workload | Target Rate | Primary Metric Focus |
| --- | --- | --- | --- | --- | --- |
| SCALE-POISSON-QWEN06-CODE | poisson | Qwen/Qwen3-0.6B | CodeGen (512:4K) | 60% of Max (from SCALE-SWEEP-QWEN06-CODE) | Responsiveness to Code Bursts |
| SCALE-POISSON-GRANITE32-CHAT | poisson | granite-3.2-2b-instruct | Chat (512:256) | 60% of Max (from SCALE-SWEEP-GRANITE32-CHAT) | Responsiveness to Bursty Traffic |

<!-- markdownlint-enable MD013 -->

### Embedding Models - Sweep Tests

<!-- markdownlint-disable MD013 -->

| Test ID | Test Type | Model | Workload | Primary Metric Focus |
| --- | --- | --- | --- | --- |
| SCALE-SWEEP-GRANITE-EN-R2-EMB | sweep | granite-embedding-english-r2 | Embedding (512:1) | English Embedding Throughput |
| SCALE-SWEEP-GRANITE-EMB278M-EMB | sweep | granite-embedding-278m-multilingual | Embedding (512:1) | Multilingual Embedding Throughput |

<!-- markdownlint-enable MD013 -->

## Test Parameters

<!-- markdownlint-disable MD013 MD033 -->

| Variable | Setting |
| --- | --- |
| **KV Cache** | MAX (for sweep tests)<br>MIN (1GiB for synchronous) |
| **Dtype** | bfloat16 |
| **Quantization** | OFF (Full Precision) |
| **Affinity** | FULL: All physical cores |

<!-- markdownlint-enable MD013 MD033 -->

## Running Tests

### Option 1: Docker/Podman Compose

```bash
# Run all scalability tests
docker compose up

# Run specific test
MODEL_NAME=llama-3.2-1b SCENARIO=sweep docker compose up
```text

### Option 2: Ansible Automation

```bash
cd ../../automation/test-execution/ansible
ansible-playbook playbooks/run-suite.yml -e "test_suite=scalability"
```text

### Option 3: Manual Execution

#### Sweep Tests

```bash
# Example: Test 2.1 - Llama-3.2-1B Chat sweep
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile sweep \
  --warmup 30 \
  --rampup 15.0 \
  --max-requests 130 \
  --data "prompt_tokens=512,output_tokens=256"
```text

#### Synchronous Test

```bash
# Example: Test 2.8 - TinyLlama synchronous baseline
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile synchronous \
  --warmup 30 \
  --max-requests 100 \
  --data "prompt_tokens=512,output_tokens=256"
```text

#### Poisson Tests

```bash
# Example: Test 2.9 - Qwen CodeGen poisson at 60% of max
# First run sweep test 2.3 to determine max rate, then:
guidellm benchmark \
  --target "http://localhost:8000" \
  --profile poisson \
  --warmup 30 \
  --rate 32 \
  --max-requests 280 \
  --data "prompt_tokens=512,output_tokens=4096"
```text

#### Embedding Model Sweep

```bash
# Example: Test 2.11 - granite-embedding-english-r2 sweep simulation

# 1. Find max throughput (infinite rate)
vllm bench serve --backend openai-embeddings \
  --model ibm-granite/granite-embedding-english-r2 \
  --dataset-name random \
  --random-input-len 512 \
  --num-prompts 1000 \
  --endpoint /v1/embeddings \
  --save-result \
  --result-filename "granite-en-r2-sweep-inf.json"

# 2. Test at 25%, 50%, 75% of max
# If max was 42 req/s, test at: 10, 21, 31 req/s
for rate in 10 21 31; do
  vllm bench serve --backend openai-embeddings \
    --model ibm-granite/granite-embedding-english-r2 \
    --dataset-name random \
    --random-input-len 512 \
    --num-prompts 1000 \
    --endpoint /v1/embeddings \
    --request-rate $rate \
    --save-result \
    --result-filename "granite-en-r2-sweep-${rate}rps.json"
done
```text

## Key Metrics

### Sweep Tests

- **Max throughput (req/s)** - Maximum sustainable request rate
- **TTFT at saturation** - Time to first token at max load
- **ITL at saturation** - Inter-token latency at max load
- **Load-latency curve** - How latency increases with load
- **Saturation point** - Where performance degrades sharply

### Synchronous Tests

- **Single-request latency** - Baseline with no concurrency
- **TTFT baseline** - Minimum achievable TTFT
- **ITL baseline** - Minimum achievable ITL

### Poisson Tests

- **Latency variance** - Consistency under bursty traffic
- **Recovery time** - How quickly system recovers from bursts
- **Tail latencies (P95/P99)** - Worst-case performance

## Results

Results are written to:

```text
../../results/
├── by-suite/scalability/
│   ├── llama-3.2-1b/
│   │   ├── sweep.json
│   │   ├── synchronous.json
│   │   └── poisson.json
│   └── ...
└── by-model/llama-3.2-1b/scalability/
```text

## Analysis

### Generate Load-Latency Curves

```bash
cd ../../automation/analysis
python generate-report.py \
  --input ../../results/by-suite/scalability \
  --format html \
  --include-curves
```text

### Compare Sweep Results

```bash
python compare-models.py \
  --suite scalability \
  --scenario sweep \
  --metric max-throughput
```text

### Identify Optimal Operating Points

Use sweep test results to find the optimal rate before saturation:

- Where TTFT < 2x baseline
- Where throughput is still near maximum
- Before P95 latency degrades significantly

See [Manual Sweep Guide](../../docs/methodology/manual-sweep.md) for detailed
analysis procedures.

## Related Documentation

- [Manual Sweep Testing](../../docs/methodology/manual-sweep.md) - Detailed
  sweep methodology
- [Metrics Guide](../../docs/methodology/metrics.md) - Metric definitions
- [Concurrent Load Test Suite](../concurrent-load/) - Concurrent load testing
- [Resource Contention Test Suite](../resource-contention/) - Resource contention
