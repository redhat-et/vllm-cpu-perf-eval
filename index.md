---
layout: default
title: vLLM CPU Performance Evaluation
---

Comprehensive performance evaluation framework for vLLM on CPU platforms.

This site provides complete testing methodology, automation tools, and platform configurations for evaluating vLLM inference performance on CPU-based systems.

## Quick Links

<div class="quick-links">
  <div class="link-card">
    <h3>🚀 Getting Started</h3>
    <p>Configure your test environment and run your first benchmark</p>
    <a href="docs/getting-started">Quick Start Guide →</a>
  </div>

  <div class="link-card">
    <h3>📊 Test Methodology</h3>
    <p>Understand the testing approach, metrics, and 3-phase strategy</p>
    <a href="docs/methodology/overview">Testing Methodology →</a>
  </div>

  <div class="link-card">
    <h3>⚖️ vLLM Scale-Out</h3>
    <p>Deploy multiple vLLM instances with nginx load balancing</p>
    <a href="docs/vllm-scaleout">Scale-Out Guide →</a>
  </div>

  <div class="link-card">
    <h3>🧪 Test Suites</h3>
    <p>Explore concurrent load, scalability, and embedding model tests</p>
    <a href="tests/tests">Test Suites Overview →</a>
  </div>

  <div class="link-card">
    <h3>🤖 Models</h3>
    <p>View supported models and selection rationale</p>
    <a href="models/models">Model Catalog →</a>
  </div>

  <div class="link-card">
    <h3>📊 Visualization</h3>
    <p>Monitor tests live with Grafana or analyze results with Streamlit</p>
    <a href="automation/test-execution/grafana/README">Grafana & Streamlit →</a>
  </div>
</div>

## Key Features

### 🎯 3-Phase Testing Methodology
- **Phase 1**: Baseline performance with fixed tokens
- **Phase 2**: Realistic variability simulation
- **Phase 3**: Production conditions with caching

> Currently implemented for [Concurrent Load Tests](tests/concurrent-load/concurrent-load)

### 🔧 Comprehensive Automation
- **Ansible playbooks** for platform setup and test execution
- **Distributed testing** across multiple nodes
- **Docker/Podman** support with auto-detection
- **Rootless** container runtime support

### 📈 Multiple Test Suites

| Test Suite | Status | Focus |
|------------|--------|-------|
| [Concurrent Load](tests/concurrent-load/concurrent-load) | ✅ Validated | P95 latency scaling with concurrent requests |
| [Scalability](tests/scalability/scalability) | 🚧 WIP | Maximum throughput and load-latency curves |
| [Embedding Models](tests/embedding-models/embedding-models) | 🚧 WIP | Embedding-specific performance |
| Resource Contention | 📋 Planned | Multi-tenant and resource sharing |

### 🏗️ Multi-Platform Support
- Intel Xeon (Ice Lake, Sapphire Rapids, Granite Rapids)
- AMD EPYC
- ARM64 (planned)

## Documentation

### Core Documentation
- **[Testing Methodology](docs/methodology/overview)** - Complete testing approach
- **[3-Phase Testing](docs/methodology/testing-phases)** - Baseline, realistic, and production phases
- **[Metrics Guide](docs/methodology/metrics)** - Metric definitions and SLOs
- **[Test Reporting](docs/methodology/reporting)** - Report structure and formats

### Test Suites
- **[Concurrent Load](tests/concurrent-load/concurrent-load)** - Concurrent request testing ✅
- **[Scalability](tests/scalability/scalability)** - Throughput and sweep testing 🚧
- **[Embedding Models](tests/embedding-models/embedding-models)** - Embedding performance 🚧
- **[Resource Contention](tests/resource-contention/resource-contention)** - Multi-tenant testing 📋

### Automation & Setup
- **[Getting Started](docs/getting-started)** - Quick start guide with Ansible
- **[Platform Setup](docs/platform-setup/x86/intel/deterministic-benchmarking)** - Intel platform configuration
- **[Models](models/models)** - Model definitions and selection

### Visualization & Monitoring
- **[Grafana Monitoring](automation/test-execution/grafana/README)** - Real-time metrics with Prometheus and Grafana
- **[Streamlit Dashboard](automation/test-execution/dashboard-examples/README)** - Post-test analysis and comparison

## Model Coverage

### LLM Models (9 total)
- **Llama-3.2** (1B, 3B) - Meta's efficient small language models
- **TinyLlama-1.1B** - Compact Llama architecture
- **OPT** (125M, 1.3B) - Facebook's open pre-trained transformers
- **Granite-3.2-2B** - IBM's enterprise model
- **Qwen3-0.6B, Qwen2.5-3B** - Alibaba's efficient models
- **GPT-OSS-20B** - 21B parameter Mixture-of-Experts model

### Embedding Models (2 total)
- **granite-embedding-english-r2** - English-optimized embeddings
- **granite-embedding-278m-multilingual** - Multilingual support

See [Model Catalog](models/models) for complete specifications.

## Workload Types

| Workload | Input:Output Tokens | Use Case |
|----------|-------------------|----------|
| **Chat** | 512:512 | Interactive conversations |
| **RAG** | 8192:512 | Retrieval-augmented generation |
| **Code** | 1024:1024 | Code generation |
| **Summarization** | 2048:256 | Document summarization |
| **Reasoning** | 256:2048 | Complex reasoning tasks |

## Key Metrics

### Primary Metrics
- **Inter-Token Latency (ITL)** - Time between consecutive tokens
- **Time to First Token (TTFT)** - Time from request to first token
- **Total Tokens Throughput** - Combined prompt and output token rate
- **Request Success Rate** - Percentage of successful requests

### Performance Metrics
- **Request Rate** - Requests processed per second
- **End-to-End Latency** - Total request completion time
- **P95/P99 Latency** - Tail latency percentiles

See [Metrics Guide](docs/methodology/metrics) for detailed definitions.

## Requirements

### System Requirements
- **CPU**: Intel Xeon (Ice Lake+) or AMD EPYC
- **Memory**: 64GB+ RAM recommended
- **OS**: Ubuntu 22.04+, RHEL 9+, or Fedora 38+
- **Storage**: 500GB+ for models and results

### Software Requirements
- Python 3.10+
- Docker 24.0+ or Podman 4.0+
- Ansible 2.14+ (for automation)
- GuideLLM v0.5.0+
- vLLM

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run pre-commit checks: `pre-commit run --all-files`
5. Submit a pull request

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Run manually
pre-commit run --all-files
```

## Support

- **Documentation**: Browse this site for comprehensive guides
- **Repository**: [GitHub Repository](https://github.com/redhat-et/vllm-cpu-perf-eval)
- **Issues**: [Report Issues](https://github.com/redhat-et/vllm-cpu-perf-eval/issues)

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) - High-performance LLM inference engine
- [GuideLLM](https://github.com/vllm-project/guidellm) - LLM benchmarking tool
- Intel and AMD for CPU optimization guidance
