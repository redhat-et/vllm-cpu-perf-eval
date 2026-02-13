# vLLM Performance Evaluation Guide - CPU Inferencing

<!-- markdownlint-disable MD033 -->
<span style="color: red">Current status: Draft</span>
<!-- markdownlint-enable MD033 -->

## Contributors

<!-- markdownlint-disable MD060 -->

| Name |
| --- |
| Maryam Tahhan |
| John Harrigan |
| Mark Kurtz |
| Tyler Michael Smith |
| Anton Ivanov |
| Luigi Mario Zuccarelli |
| Paul Power |

<!-- markdownlint-enable MD060 -->

## Introduction

This guide outlines the methodology, tools, and procedures for evaluating the
performance of the vLLM framework (CPU Mode) when running Small Language Models
(SLMs), Tiny Models, and Embedding models. This evaluation is structured into
multiple phases, with each phase incorporating specific models, test scenarios,
and performance goals.

### Primary Goals

The primary goals of this performance evaluation effort are to:

- **Establish Baseline Performance for CPU inferencing in vLLM:** Determine the
  fundamental performance characteristics (latency and throughput) of vLLM's
  CPU inferencing capabilities for various SLMs
- **Identify Optimal Operating Points:** Find the sweet spot between throughput
  and latency for different workload types
- **Characterize Architectural Differences:** Understand performance
  characteristics across different model architectures

### Future Stages

Future stages will incorporate the following goals:

- Establish which models work on CPU
- Establish guidance on coexistence of CPU inference loads and enterprise
  compute/service loads
- Assess the performance impact of using a subset of cores and/or NUMA nodes
- Measure configuration impact of vLLM CPU tuning and quantization parameters

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
| --- | --- | --- |
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
| --- | --- |
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
| --- | --- | --- |
| **Sweep** | Runs synchronous (min), throughput (max) benchmarks, and then runs a series of benchmarks equally spaced between the two rates. The number of benchmarks is set by `--rate` (default is 10). | • Full load–latency curve (end-to-end scalability profile)<br>• Determines optimal operating point before saturation |
| **Synchronous** | Runs a single stream of requests one at a time | • Baseline model response latency (no concurrency)<br>• Measures raw end-to-end response time per request<br>• Establishes performance floor before parallel load |
| **Throughput** | Issues all requests concurrently to fully saturate the model/server. Equivalent to a "max load" test | • Maximum throughput capacity of the serving system<br>• Identifies saturation point where latency begins to increase sharply<br>• Useful for sizing instances or cores |
| **Constant** | Sends requests at a fixed, steady rate (RPS), regardless of completion time. | • Stability of serving performance under steady, controlled load<br>• Queueing effects when request arrival exceeds processing rate |
| **Poisson** | Sends requests according to a Poisson process (random intervals, same average rate). Simulates unpredictable real-world traffic | • System responsiveness to bursty or stochastic traffic<br>• Latency jitter and recovery time after spikes |
| **Concurrent** | Runs a fixed number of streams of requests in parallel | • Scalability with concurrency<br>• Measures how latency and throughput scale as more users or parallel sessions connect |

<!-- markdownlint-enable MD013 -->

## Testing Phases

Testing is organized into multiple phases, each with specific goals and test
scenarios. For detailed test case specifications, models under test, and
execution instructions, see the README in each phase directory.

### Phase 1: Concurrent Load Testing

**Goal:** Measure P95 latency and throughput scaling under concurrent load

- Tests 8 LLM models + 2 embedding models
- Concurrency levels: {8, 16, 32, 64, 96, 128} for LLMs
- Concurrency levels: {4, 8, 16, 32, 64} for embeddings
- Workloads: Chat, RAG, CodeGen, Summarization, Embedding

**📚 See [Phase 1 Test Documentation](../../tests/phase-1-concurrent/) for
complete test specifications**

### Phase 2: Scalability and Performance Testing

**Goal:** Characterize maximum throughput and generate load-latency curves

- Sweep tests for full performance curves
- Synchronous baseline tests
- Poisson tests for bursty traffic
- Focus on max throughput (OTPS/TTPS), TTFT scaling, and KV cache efficiency

**📚 See [Phase 2 Test Documentation](../../tests/phase-2-scalability/) for
complete test specifications**

### Phase 3: Resource Contention Testing (Planned)

**Goal:** Test platform stability with resource sharing and noisy neighbors

- Fractional core allocation
- NUMA node isolation
- Co-located workloads
- Multi-tenant scenarios

**📚 See [Phase 3 Test Documentation](../../tests/phase-3-resource-contention/)
for status and planned tests**

### Phase 4: Configuration Tuning (Future)

**Goal:** Measure configuration impact of vLLM CPU tuning and quantization

- KV cache size variations
- Quantization methods (AWQ, GPTQ)
- Thread binding strategies
- Batch size optimization

## Related Documentation

- **[Metrics Guide](metrics.md)** - Definitions of all measured metrics
- **[Test Reporting](reporting.md)** - Test report structure and formats
- **[Manual Sweep Testing](manual-sweep.md)** - Detailed manual testing
  procedures
- **[Platform Setup](../platform-setup/)** - System configuration for
  deterministic testing
- **[Test Execution](../../tests/)** - Actual test implementations and
  scenarios
