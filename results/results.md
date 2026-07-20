# Results Directory

This directory stores test execution results. It is gitignored except for this
README.

## Structure

Results are organized by model, then by workload-timestamp, then by core
configuration:

```text
results/
├── llm/                                          # LLM generative model results
│   ├── <model>/                                  # Model name (/ replaced with __)
│   │   └── <workload>-<YYYYMMDD-HHMMSS>/         # Workload type + test run timestamp
│   │       └── <core-config>/                    # Core configuration name
│   │           ├── benchmarks.json               # GuideLLM benchmark results
│   │           ├── benchmarks.csv                # GuideLLM results (CSV)
│   │           ├── test-metadata.json            # Test configuration and IETF metadata
│   │           ├── vllm-metrics.json             # vLLM server Prometheus metrics
│   │           ├── vllm-server.log               # vLLM server logs
│   │           ├── guidellm.log                  # GuideLLM execution log
│   │           ├── system-metrics.log            # System-level metrics
│   │           └── metrics-collector.log         # Metrics collection log
│   │
│   └── ...                                       # Additional models
│
├── audio-models/                                 # Audio model results (e.g. Whisper)
│   └── <model>/
│       └── ...
│
└── results.md                                    # This file
```

**Example:**

```text
results/llm/
├── meta-llama__Llama-3.2-1B-Instruct/
│   ├── chat-20260421-094807/
│   │   └── 16cores-numa0-tp1/
│   │       ├── benchmarks.json
│   │       ├── benchmarks.csv
│   │       ├── test-metadata.json
│   │       ├── vllm-metrics.json
│   │       ├── vllm-server.log
│   │       ├── guidellm.log
│   │       ├── system-metrics.log
│   │       └── metrics-collector.log
│   └── chat-20260421-101101/
│       └── 16cores-numa0-tp1/
│           └── ...
│
└── TinyLlama__TinyLlama-1.1B-Chat-v1.0/
    ├── chat-20260428-124238/
    │   └── ...
    └── chat-20260428-130000/
        └── ...
```

## Result Files

<!-- markdownlint-disable MD013 MD060 -->

| File | Format | Description |
|------|--------|-------------|
| `benchmarks.json` | JSON | GuideLLM benchmark results — percentile latencies (P50–P99.9), throughput, per-request data |
| `benchmarks.csv` | CSV | Same data in CSV format for spreadsheet import |
| `test-metadata.json` | JSON | Test configuration, IETF metadata (SUT boundary, tokenizer, load model), timing, sample counts |
| `vllm-metrics.json` | JSON | vLLM server Prometheus metrics (queue depth, cache usage, token rates) |
| `vllm-server.log` | Text | vLLM server stdout/stderr logs |
| `guidellm.log` | Text | GuideLLM execution log |
| `system-metrics.log` | Text | System-level resource metrics collected during the test |
| `metrics-collector.log` | Text | Log from the metrics collection process |

<!-- markdownlint-enable MD013 MD060 -->

## Viewing Results

The recommended way to view and analyze results is via the **Streamlit
dashboard**:

```bash
# One-time setup
cd automation/test-execution/dashboard-examples
./setup.sh

# Launch dashboard
cd vllm_dashboard
./launch-dashboard.sh

# Open http://localhost:8501
```

The dashboard provides client metrics (throughput, latency percentiles),
server metrics (queue depth, cache usage), platform comparison, and CSV
export. See the [Dashboards Quick Start](../docs/dashboards-quickstart.md)
for the full guide.
