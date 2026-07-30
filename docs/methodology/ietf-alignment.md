# IETF LLM Benchmarking Alignment

This document describes how the vLLM CPU Performance Evaluation project aligns
with the IETF LLM benchmarking drafts, maps our terminology to the standard,
and identifies known gaps.

## Referenced IETF Drafts

<!-- markdownlint-disable MD013 MD060 -->

| Draft | Title | Status |
|-------|-------|--------|
| [draft-gaikwad-llm-benchmarking-methodology-00](https://datatracker.ietf.org/doc/draft-gaikwad-llm-benchmarking-methodology/) | Benchmarking Methodology for Large Language Models | Active |
| [draft-gaikwad-llm-benchmarking-profiles-00](https://datatracker.ietf.org/doc/draft-gaikwad-llm-benchmarking-profiles/) | Benchmarking Profiles for Large Language Models | Active |
| [draft-gaikwad-llm-benchmarking-terminology-00](https://datatracker.ietf.org/doc/draft-gaikwad-llm-benchmarking-terminology/) | Benchmarking Terminology for Large Language Models | Active |

<!-- markdownlint-enable MD013 MD060 -->

## SUT Boundary

The IETF profiles draft defines four System Under Test (SUT) boundaries:

1. **Model Engine** — the inference runtime only
2. **AI Gateway** — model engine + API gateway / load balancer
3. **AI Firewall** — gateway + input/output guardrails
4. **Compound System** — full application (RAG pipeline, agents, etc.)

This project tests at the **Model Engine** level: vLLM serving a single model
on CPU, accessed directly by the load generator (GuideLLM) over HTTP. There is
no gateway, guardrail, or retrieval layer in the measurement path.

The `sut_boundary` field in `test-metadata.json` records this as
`"model_engine"`.

## Terminology Mapping

<!-- markdownlint-disable MD013 MD060 -->

| Project Term | IETF Term | Notes |
|--------------|-----------|-------|
| ISL (Input Sequence Length) | Input Token Count | Both refer to prompt length in tokens |
| OSL (Output Sequence Length) | Output Token Count | Both refer to generated tokens |
| ITL (Inter-Token Latency) | TBT (Time Between Tokens) | ITL is client-side measurement; IETF TBT is server-side. Our ITL approximates TBT since we test locally with minimal network latency |
| TTFT (Time to First Token) | TTFT | Same definition |
| E2E Latency | Request Latency | Same: time from request submission to complete response |
| Total Tokens Throughput | Output Token Throughput | IETF separates input vs output token throughput |
| concurrent profile | Closed-loop / Fixed-concurrency | Fixed number of parallel request streams |
| synchronous profile | Closed-loop / Single-stream | Special case: concurrency = 1 |
| throughput profile | Closed-loop / Max-concurrency | Saturate the system |
| poisson profile | Open-loop / Poisson | Random inter-arrival times, fixed average rate |
| constant profile | Open-loop / Constant | Fixed inter-arrival time |
| sweep profile | Multi-rate sweep | Not a single IETF load model; runs sync + throughput + interpolated rates |
| DUT (Device Under Test) | SUT (System Under Test) | Our DUT is the server running vLLM |
| Load Generator | Load Generator | Same concept |

<!-- markdownlint-enable MD013 MD060 -->

## Implemented IETF Tests

<!-- markdownlint-disable MD013 MD060 -->

| IETF Test | Status | How We Cover It |
|-----------|--------|-----------------|
| Baseline Latency | Implemented | Phase 1 baseline tests with `synchronous` profile |
| Throughput Saturation | Implemented | `throughput` profile, sweep tests |
| Fixed-Concurrency Scaling | Implemented | `concurrent` profile with rates [1,2,4,8,16,32] |
| Open-Loop Poisson | Implemented | `poisson` profile (added to validation allowlist) |
| Constant-Rate | Implemented | `constant` profile (added to validation allowlist) |
| Long Context Scaling | Implemented | `context_scaling_1k/4k/8k` workloads |
| Variable Token Distribution | Implemented | Phase 2 realistic tests (`chat_var`, `code_var`, `summarization_var`) |
| Prefix Caching Impact | Implemented | Phase 3 production tests with `--enable-prefix-caching` |
| Scheduling Fairness | Not implemented | Requires per-request scheduling delay instrumentation |
| Memory Pressure | Not implemented | Requires memory-limited test configurations |
| Multi-Run Confidence Intervals | Not implemented | Currently single-run; future work |
| Guardrail Overhead | N/A | Out of scope (Model Engine boundary) |

<!-- markdownlint-enable MD013 MD060 -->

## Compliance Status

<!-- markdownlint-disable MD013 MD060 -->

| IETF Requirement | Level | Status | Notes |
|-----------------|-------|--------|-------|
| Report SUT boundary | MUST | Done | `sut_boundary` in test-metadata.json |
| Report tokenizer | MUST | Done | `tokenizer` and `tokenizer_source` in metadata |
| Report streaming protocol | MUST | Done | `streaming_protocol` in metadata |
| Report clock sync method | SHOULD | Done | `clock_sync_method` in metadata |
| Report model precision | MUST | Done | `model_precision` in metadata |
| Report quantization method | MUST | Done | `quantization_method` in metadata |
| Report load model (open/closed) | MUST | Done | `load_model` and `arrival_pattern` in metadata |
| Report random seed | SHOULD | Done | `random_seed` in metadata |
| P50/P90/P95/P99 percentiles | MUST | Done | Prometheus template exports all four |
| P99.9 percentile | SHOULD | Done | Exported for TTFT and ITL (requires sufficient samples) |
| Minimum 1000 samples for P99 | MUST | Partial | `max_requests` raised to 10000; `ietf_sample_warning` flags insufficient samples |
| Minimum 10000 samples for P99.9 | SHOULD | Partial | `max_seconds: 600` is binding for CPU; warning emitted if not met |
| Warmup exclusion | MUST | Done | GuideLLM `--warmup` excludes initial requests/time from metrics |
| Separate DUT and load generator | MUST | Done | Testbed uses separate nodes on same network segment |

<!-- markdownlint-enable MD013 MD060 -->

## Known Gaps

1. **Scheduling Fairness** — IETF methodology includes tests for fair
   request scheduling under load. We do not instrument per-request scheduling
   delay from vLLM's internal queue.

2. **Memory Pressure Tests** — IETF suggests testing under constrained
   memory to observe degradation. Our tests use generous KV cache allocations.

3. **Multi-Run Confidence Intervals** — IETF recommends multiple runs with
   statistical confidence intervals. We currently run single iterations per
   configuration.

4. **Output Token Throughput vs Total Token Throughput** — IETF separates
   input and output token throughput. GuideLLM reports combined
   `tokens_per_second` (total). Output-only throughput
   (`output_tokens_per_second`) is available in raw results but not yet
   exported to Prometheus.

5. **Server-Side TBT** — IETF distinguishes client-side ITL from
   server-side TBT. We report ITL (client-measured). For single-machine
   tests, the difference is negligible.

## Related Documentation

- [Metrics Guide](metrics.md)
- [Testing Phases](testing-phases.md)
- [Test Reporting](reporting.md)
- [Overview](overview.md)
