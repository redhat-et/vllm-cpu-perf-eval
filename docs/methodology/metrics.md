# Collected Metrics

## Understanding Percentiles

Percentile definition: **Pxx = the value below which xx% of data points fall**

### Latency Percentiles (lower is better)

- **P50 (median)**: 50% of requests completed within this latency
- **P90**: 90% of requests completed within this latency
- **P95**: 95% of requests completed within this latency
- **P99**: 99% of requests completed within this latency (worst-case tail)
- **P99.9**: 99.9% of requests completed within this latency (extreme tail)

**Interpretation**:
- High P99 latency = **bad** (indicates slow tail)
- Example: TTFT P99 = 200ms → 99% of requests got first token within 200ms, 1% took longer
- **P99.9 > P99 > P95 > P90 > P50** is normal (higher percentiles show worse-case performance)

### Throughput Percentiles (higher is better)

- **P50 (median)**: 50% of requests achieved this throughput or lower
- **P95**: 95% of requests achieved this throughput or lower
- **P99**: 99% of requests achieved this throughput or lower (upper bound)

**Interpretation**:
- High P99 throughput = **good** (shows fast requests exist)
- Example: Throughput P99 = 100 tok/s → only 1% of requests exceeded 100 tok/s
- **P99 > Mean**: Some fast requests pulled up the average
- **Narrow spread (P99 ≈ P50)**: Consistent per-request throughput

**Key Difference**:
- For **latency**: Higher percentiles (P95, P99) show **worst-case** performance
- For **throughput**: Higher percentiles (P95, P99) show **upper bound** of performance

### IETF Minimum Sample Counts

<!-- markdownlint-disable MD013 MD060 -->

Per the IETF benchmarking methodology, percentile accuracy requires minimum
sample sizes:

| Percentile | Minimum Samples | Notes |
|------------|----------------|-------|
| P50 | 100 | Sufficient for median estimation |
| P90 | 500 | Moderate tail accuracy |
| P95 | 1,000 | Standard tail latency reporting |
| P99 | 1,000 | IETF MUST requirement |
| P99.9 | 10,000 | IETF SHOULD requirement; may not be achievable for CPU tests within time constraints |

<!-- markdownlint-enable MD013 MD060 -->

The `ietf_sample_warning` field in `test-metadata.json` flags when a test run
has insufficient samples for reliable percentile reporting.

## Guidellm Metrics

GuideLLM documents the key metrics measured/reported and how to interpret
them (URL). For purposes of vLLM performance evaluation on CPU-mode specific
workloads this Table provides the key metrics, along with a description.

### Key Metrics: Workload/Client-side

<!-- markdownlint-disable MD013 MD060 -->

| METRIC (unit) | DESCRIPTION |
|---------------|-------------|
| **Primary Metrics** | |
| Inter-Token Latency (ms) | (ITL) - Average time between generating consecutive tokens in the output, excluding the first token. IETF term: TBT (Time Between Tokens). ITL is a client-side measurement; TBT is server-side. For single-machine tests the difference is negligible. |
| Time to First Token (s) | (TTFT) - Time from request submission to receiving the first generated token |
| Total Tokens Throughput (tokens/s) | The combined rate of prompt and output tokens processed per second as a throughput metric across all requests. |
| Request Success Rate (%) | Percentage of requests completed successfully without errors |
| **Additional Metrics** | |
| Request Rate (requests/s) | The number of requests processed per second |
| End-to-End Latency (ms) | Time from request submission to receiving the complete response (a.k.a. Total Latency) |

<!-- markdownlint-enable MD013 MD060 -->

## System Level Metrics

<!-- markdownlint-disable MD013 MD060 -->

| Metric | Description |
|--------|-------------|
| CPU Utilization (%) | The percentage of time the CPU is busy executing non-idle threads. |
| Memory Utilization/Consumption (GB) | The total memory (RAM) used by the vLLM process, including model weights and key-value (KV) cache. |

<!-- markdownlint-enable MD013 MD060 -->

## IETF-Aligned Metrics

The following metrics are defined by the IETF LLM benchmarking methodology
but not directly reported by GuideLLM. They can be derived from test results:

<!-- markdownlint-disable MD013 MD060 -->

| Metric | Definition | Derivation |
|--------|-----------|------------|
| Goodput (tokens/s) | Output tokens from requests meeting SLO targets | Filter successful requests by SLO, sum output tokens / time |
| SLO Attainment Rate (%) | Fraction of requests meeting all SLO targets | Count(requests meeting SLO) / Count(total requests) |
| Normalized Latency (ms/token) | E2E latency divided by output token count | request_latency / output_token_count per request |

<!-- markdownlint-enable MD013 MD060 -->

See [IETF Alignment](ietf-alignment.md) for full terminology mapping and
compliance status.

## Service Level Objective (SLO) Definition

GuideLLM defines Service Level Objectives terminology, trade-offs (e.g.
latency vs throughput vs cost per request) and provides example thresholds for
common LLM use-cases (URL). For Real-Time use cases the highlighted metrics
include: TTFT, ITL and Request Latency. For Offline/Batch, highlighted metrics
are Throughput focused.

### SLO Examples

GuideLLM also defines a number of example SLOs for various use cases. The
examples provided serve as a starting point. These are summarized by the tables
below.

<!-- markdownlint-disable MD013 MD060 -->

#### Real-Time, Application-Facing Use Cases

| Use Case | Enterprise Example | SLO (p99) – TTFT | SLO (p99) – ITL / Token | SLO (p99) – Request Latency | Notes |
|----------|-------------------|------------------|-------------------------|----------------------------|-------|
| Chat Applications | Customer-support chatbot | ≤ 200 ms | ≤ 50 ms | — | Very low-latency UX; external-facing |
| RAG (Retrieval-Augmented Generation) | Legal search & summarization tool | ≤ 300 ms (if streaming) | ≤ 100 ms (if streaming) | ≤3s | Allows slightly longer total latency due to retrieval |
| Instruction-Following / Agentic AI | Virtual assistant / task manager | — | — | ≤5s | Focus on full request completion rather than streaming speed |

#### Real-Time, Internal Use Cases

| Use Case | Enterprise Example | SLO (p99) – TTFT | SLO (p99) – ITL / Token | SLO (p99) – Request Latency | Notes |
|----------|-------------------|------------------|-------------------------|----------------------------|-------|
| Content Generation | Marketing copy / ad text generator | ≤ 600 ms | ≤ 200 ms | — | Internal use → latency less critical |
| Code Generation | Boilerplate / API integration generator | ≤ 500 ms | ≤ 150 ms | — | Developer-facing; moderate interactivity |
| Code Completion | IDE plugin for autocomplete | — | — | ≤2s | Prioritizes low total latency over per-token speed |

#### Offline / Batch Use Cases

| Use Case | Enterprise Example | Throughput SLO | Latency SLO | Notes |
|----------|-------------------|----------------|-------------|-------|
| Summarization | Batch review summarization | ≥ 100 req/s | — | Focused on throughput, not per-request speed |
| Analysis | Data analysis pipeline | ≥ 150 req/s | — | Optimized for bulk offline processing |

<!-- markdownlint-enable MD013 MD060 -->
