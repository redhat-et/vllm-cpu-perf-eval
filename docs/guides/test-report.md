# Test Report

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
configuration options (URL). Supported file formats are: json, yaml, csv, html
and console. By default, json, csv and html are generated in the current
directory.

### Output Results - HTML Example Graphs

Opening the `benchmarks.html` file in a web-browser presents a GuideLLM
Workload Report. The webpage contains sections for Workload Details, Metrics
Summary and Metrics Details. Example graphs from the Metrics Details section
are shown below:

#### Latency Graphs

TODO

#### Throughput Graphs

TODO

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
