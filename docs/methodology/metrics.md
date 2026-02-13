# Collected Metrics

## Guidellm Metrics

GuideLLM documents the key metrics measured/reported and how to interpret
them (URL). For purposes of vLLM performance evaluation on CPU-mode specific
workloads this Table provides the key metrics, along with a description.

### Key Metrics: Workload/Client-side

<!-- markdownlint-disable MD013 MD060 -->

| METRIC (unit) | DESCRIPTION |
|---------------|-------------|
| **Primary Metrics** | |
| Inter-Token Latency (ms) | (ITL) - Average time between generating consecutive tokens in the output, excluding the first token. |
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
