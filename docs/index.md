---
title: vLLM CPU Performance Evaluation
---

Comprehensive performance evaluation framework for vLLM on CPU platforms, with support for both generative and embedding models.

## Quick Start

- **[Getting Started](getting-started.md)** - Set up your environment and run your first benchmarks
- **[Embedding Models](embedding-models.md)** - Test embedding models with performance and quality metrics
- **[Dashboards Quickstart](dashboards-quickstart.md)** - Visualize and analyze your results

## Features

### Performance Testing
- **Automated Ansible playbooks** for consistent, reproducible benchmarks
- **Multi-scenario testing**: inference, chat, embedding workloads
- **Comprehensive metrics**: throughput, latency (P50, P95, P99), resource utilization
- **Core scaling analysis**: measure efficiency across different CPU configurations

### Quality Testing (MTEB)
- **[MTEB Integration](https://github.com/redhat-et/vllm-cpu-perf-eval/tree/main/container-images/vllm-mteb)** - Embedding quality evaluation
- **Classification, Retrieval, Clustering, STS** task types
- **Pre-configured task presets** for quick validation or comprehensive analysis
- **Container-based deployment** for easy integration with existing workflows

### Visualization & Analysis
- **Interactive Streamlit dashboards** with Plotly visualizations
- **MLflow integration** for experiment tracking
- **Performance vs Quality trade-off analysis**
- **Export capabilities** for custom analysis

## Architecture

This framework supports three execution modes:

1. **Managed Mode** (2-node): Orchestrator + DUT for full automation
2. **DUT-Only Mode** (1-node): Everything on one system
3. **External Mode**: Test existing vLLM/RHAIIS endpoints

See [Methodology](methodology/overview.md) for details.

## Documentation

### Getting Started
- [Installation Guide](getting-started.md)
- [Quick Start Tutorial](getting-started.md#quick-start)
- [Embedding Models Testing](embedding-models.md)

### MTEB Quality Testing
- [MTEB Quick Start Guide](mteb-sweep-guide.md) - Run quality tests quickly
- [MTEB Timing Reference](mteb-timing-guide.md) - Understand test duration and planning
- [MTEB Troubleshooting](mteb-troubleshooting.md) - Resolve common issues

### Testing
- [Ansible Automation](ansible/test-execution.md)
- [Test Suites Overview](https://github.com/redhat-et/vllm-cpu-perf-eval/tree/main/tests)
- [Model Support](https://github.com/redhat-et/vllm-cpu-perf-eval/blob/main/models/models.md)

### Analysis
- [Dashboard Quickstart](dashboards-quickstart.md)
- [MLflow Tracking](mlflow.md)
- [Metrics Collection](metrics-collection.md)

### Methodology
- [Overview](methodology/overview.md)
- [Testing Phases](methodology/testing-phases.md)
- [Metrics Guide](methodology/metrics.md)
- [Reporting](methodology/reporting.md)

### Configuration
- [vLLM KV Cache Configuration Guide](vllm-kv-cache-configuration.md) - Understanding max_model_len, KV cache size, and block_size for optimal CPU performance

## Container Images

Pre-built containers available on Quay.io:
- **MTEB Benchmarking**: `quay.io/vllm-cpu-perf-eval/vllm-mteb:latest`
- **Model Downloader**: `quay.io/vllm-cpu-perf-eval/model-downloader:latest`

## Contributing

This project uses:
- **Ansible** for automation
- **Streamlit** for dashboards
- **MLflow** for experiment tracking
- **MTEB** for quality evaluation

See the [repository](https://github.com/redhat-et/vllm-cpu-perf-eval) for contribution guidelines.

## License

This project is licensed under the Apache License 2.0.
