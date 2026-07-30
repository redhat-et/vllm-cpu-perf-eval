---
title: Documentation
layout: default
---

# Documentation

Central index for the vLLM CPU Performance Evaluation framework.

## Start Here

| I want to… | Go to |
| --- | --- |
| Set up and run my first benchmark | [Getting Started](getting-started.md) |
| See all supported test suites | **[Test Suites](test-suites.md)** |
| Run benchmarks from the CLI | [cpueval CLI](cpueval-cli.md) |
| Find supported models | [Model Catalog](../models/models.md) |
| View and analyze results | [Dashboards Quickstart](dashboards-quickstart.md) |

## Documentation Map

### Getting Started

| Page | Description |
| --- | --- |
| [getting-started.md](getting-started.md) | Environment setup and first run |
| [cpueval-cli.md](cpueval-cli.md) | CLI reference (recommended entry point) |
| [test-suites.md](test-suites.md) | Central test suite reference |

### Test Suites & Models

| Page | Description |
| --- | --- |
| [test-suites.md](test-suites.md) | All suites, cpueval commands, and status |
| [embedding-models.md](embedding-models.md) | Embedding model setup guide |
| [audio-benchmarking.md](audio-benchmarking.md) | Audio model setup guide |
| [models/models.md](../models/models.md) | Model catalog and selection rationale |
| [tests/](../tests/tests.md) | Per-suite methodology docs |

### Running Tests

| Page | Description |
| --- | --- |
| [ansible/test-execution.md](ansible/test-execution.md) | Ansible playbook automation |
| [ansible/model-predownload.md](ansible/model-predownload.md) | Model pre-download guide |
| [scripts-reference.md](scripts-reference.md) | Utility scripts |
| [environment-variables.md](environment-variables.md) | Configuration reference |

### Methodology & Results

| Page | Description |
| --- | --- |
| [methodology/overview.md](methodology/overview.md) | Testing approach |
| [methodology/metrics.md](methodology/metrics.md) | Metric definitions |
| [methodology/reporting.md](methodology/reporting.md) | Result formats |
| [dashboards-quickstart.md](dashboards-quickstart.md) | Streamlit visualization |
| [mlflow.md](mlflow.md) | Experiment tracking |
| [terminal-results-viewer.md](terminal-results-viewer.md) | CLI results viewer |

### MTEB Quality Testing

| Page | Description |
| --- | --- |
| [mteb-sweep-guide.md](mteb-sweep-guide.md) | MTEB quick start |
| [mteb-timing-guide.md](mteb-timing-guide.md) | Test duration planning |
| [mteb-troubleshooting.md](mteb-troubleshooting.md) | Common issues |

### Configuration

| Page | Description |
| --- | --- |
| [platform-setup/x86/intel/deterministic-benchmarking.md](platform-setup/x86/intel/deterministic-benchmarking.md) | Intel platform tuning |
| [vllm-kv-cache-configuration.md](vllm-kv-cache-configuration.md) | KV cache settings |

## By Role

### New Users

1. [Getting Started](getting-started.md) — Setup and first benchmark
2. [Test Suites](test-suites.md) — Choose the right suite
3. [cpueval CLI](cpueval-cli.md) — Run benchmarks
4. [Dashboards Quickstart](dashboards-quickstart.md) — View results

### Running Benchmarks

1. [Test Suites](test-suites.md) — Suite overview and quick reference
2. [cpueval CLI](cpueval-cli.md) — CLI commands and options
3. [Ansible Test Execution](ansible/test-execution.md) — Playbook automation
4. [Scripts Reference](scripts-reference.md) — Utility scripts

### Understanding Results

1. [Metrics Guide](methodology/metrics.md) — Metric definitions
2. [Reporting Guide](methodology/reporting.md) — Result formats
3. [Dashboards Quickstart](dashboards-quickstart.md) — Visualization
4. [MLflow Integration](mlflow.md) — Experiment tracking

### Platform & Configuration

1. [Intel Platform Setup](platform-setup/x86/intel/deterministic-benchmarking.md)
2. [Environment Variables](environment-variables.md)
3. [vLLM KV Cache Configuration](vllm-kv-cache-configuration.md)

### Quality Testing (MTEB)

1. [MTEB Quick Start](mteb-sweep-guide.md)
2. [MTEB Timing Guide](mteb-timing-guide.md)
3. [MTEB Troubleshooting](mteb-troubleshooting.md)

## Contributing to Documentation

Documentation is written in Markdown. Run pre-commit checks before committing:

```bash
pre-commit run --all-files
```
