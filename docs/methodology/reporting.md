---
layout: default
title: Reporting
---

## Test Report

Test results should be recorded and shared with Red Hat in the form of a test
report. The test report should layout the following information:

- Relevant HW, BIOS, SW and OS configuration details.
- Test Settings and Test Results (per test case).

## Test Settings

<!-- markdownlint-disable MD013 MD060 -->

Benchmark results should provide test configuration details per test case:

| Information | Description |
|-------------|-------------|
| vLLM serving command | |
| guidellm testing command | |

<!-- markdownlint-enable MD013 MD060 -->

## Test-run Results

### Workload/GuideLLM Outputs

GuideLLM describes output types, console and file-based, their sections and
configuration options. Supported file formats are: json, yaml, csv, and
console. By default, json and csv are generated in the current directory.

> **Note:** HTML output is available in GuideLLM but not currently enabled in
> this test environment. See [GuideLLM issue #627](https://github.com/vllm-project/guidellm/issues/627)
> for details.

## IETF-Required Disclosures

Per the [IETF LLM benchmarking methodology](ietf-alignment.md), test reports
must include the following disclosures. These are automatically recorded in
`test-metadata.json` for each test run.

<!-- markdownlint-disable MD013 MD060 -->

| Disclosure | Field in test-metadata.json | Description |
|------------|---------------------------|-------------|
| SUT Boundary | `sut_boundary` | Level of the system under test (e.g., `model_engine`) |
| Tokenizer | `tokenizer`, `tokenizer_source` | Tokenizer used and its source (e.g., HuggingFace) |
| Streaming Protocol | `streaming_protocol` | How tokens are streamed to the client (e.g., SSE) |
| Clock Synchronization | `clock_sync_method` | How clocks are synchronized between DUT and load generator |
| Model Precision | `model_precision` | Data type used for inference (e.g., `bfloat16`, `auto`) |
| Quantization Method | `quantization_method` | Quantization applied to the model (e.g., `none`, `awq`) |
| Load Model | `load_model` | Open-loop or closed-loop traffic generation |
| Arrival Pattern | `arrival_pattern` | Specific load profile (e.g., `concurrent`, `poisson`) |
| Container Images | `vllm_container_image`, `guidellm_container_image` | Exact container images used for vLLM and GuideLLM |

<!-- markdownlint-enable MD013 MD060 -->

## Other Configuration Details

Test results should report system configuration details including:

<!-- markdownlint-disable MD013 MD060 -->

### Hardware & BIOS Information

| Information | Description |
|-------------|-------------|
| Baseboard | Model/Vendor |
| Architecture / MicroArchitecture | e.g., Intel Sapphire Rapids, AMD Zen 4 |
| Sockets & Cores per Socket | Physical count |
| Instruction Set Architecture (ISA) | List all supported and enabled ISAs (e.g., AVX512, AMX, VNNI, AVX512_BF16). |
| L3 Cache | Size (MB) |
| Hyperthreading | Status: Enabled / Disabled |
| Base/All-Core Max/Maximum Frequency | Values (GHz) |
| NUMA nodes | Count |
| Sub-NUMA Clustering (SNC) | Status: Enabled/Disabled/Mode (e.g., SNC4) |
| Installed Memory | Size (GB) and Speed (MT/s) and Channel Count |
| Hugepage size | Size (MB/GB) and Status: Enabled/Disabled |
| BIOS version | Value |
| TDP | Value (W) |

### OS & Software Settings

Test results should also provide OS and Software details including:

| Information | Description |
|-------------|-------------|
| Operating System & Kernel Version | Value |
| OS Tuning Parameters | List relevant OS-level tunings (e.g., tuned profile, latency optimization). |
| Automatic NUMA Balancing | Status: Enabled/Disabled |
| Power and performance policy | Value (e.g., Performance, Balance) |
| Frequency Governor & Driver | Value (e.g., performance, intel_pstate) |
| Guidellm version | value |
| vLLM version | value |

<!-- markdownlint-enable MD013 MD060 -->
