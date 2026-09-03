# vLLM CPU Performance Evaluation

[![Tests](https://github.com/redhat-et/vllm-cpu-perf-eval/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/redhat-et/vllm-cpu-perf-eval/actions/workflows/unit-tests.yml)
[![cpueval CLI Tests](https://github.com/redhat-et/vllm-cpu-perf-eval/actions/workflows/cpueval-tests.yml/badge.svg)](https://github.com/redhat-et/vllm-cpu-perf-eval/actions/workflows/cpueval-tests.yml)
[![pre-commit](https://github.com/redhat-et/vllm-cpu-perf-eval/actions/workflows/pre-commit.yaml/badge.svg)](https://github.com/redhat-et/vllm-cpu-perf-eval/actions/workflows/pre-commit.yaml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://redhat-et.github.io/vllm-cpu-perf-eval/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Performance evaluation framework for [vLLM](https://github.com/vllm-project/vllm) on CPU
platforms — methodology, automation, and platform configurations for reproducible
inference benchmarking.

## Quick Start

The recommended entry point is the **cpueval CLI** — it wraps Ansible playbooks and
suite scripts so you can run full test matrices without hand-writing playbook commands.

```bash
git clone https://github.com/redhat-et/vllm-cpu-perf-eval.git
cd vllm-cpu-perf-eval

# System packages, Ansible collections, and tab completion
./cpueval install

# Set up your test hosts
export DUT_HOSTNAME=<dut-host>
export LOADGEN_HOSTNAME=<loadgen-host>

# Verify environment, then run a quick sanity check
./cpueval doctor
./cpueval --suite chat-smoke --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8

# Explore suites and view results
./cpueval list
./cpueval results --last
```

See the [Getting Started Guide](docs/getting-started.md) and
[cpueval CLI reference](docs/cpueval-cli.md) for full setup instructions.

## Test Suites

| Suite | Status | Entry point |
| --- | --- | --- |
| [Concurrent Load](tests/concurrent-load/concurrent-load.md) | Validated | `./cpueval --suite concurrent-load` |
| [RHAIIS Sweep](tests/concurrent-load/rhaiis-testing.md) | Validated | `./cpueval --suite rhaiis-sweep` |
| [Offline Batch](tests/offline-batch/offline-batch.md) | Validated | `./cpueval --suite offline-batch` |
| [Embedding](tests/embedding-models/embedding-models.md) | Validated | `./cpueval --suite embedding` |
| [Audio](tests/audio-models/) | Validated | `./cpueval --suite audio` |
| [LM Eval](tests/lm-eval/lm-eval.md) | WIP | `./cpueval --suite lm-eval` |
| [Scalability](tests/scalability/scalability.md) | WIP | Ansible playbooks |
| [Resource Contention](tests/resource-contention/resource-contention.md) | Planned | — |

Full suite reference, selection guide, and status details:
[docs/test-suites.md](docs/test-suites.md)

Unsupported suites (e.g. scalability) are blocked by default. For development only,
pass `-e "allow_unsupported_tests=true"` to Ansible or set `ALLOW_UNSUPPORTED_TESTS=true`.

## Key Features

- **cpueval CLI** — Matrix-first benchmarking across 9 suites
- **3-phase testing** — Baseline, realistic, and production methodology ([details](docs/methodology/testing-phases.md))
- **Ansible automation** — Distributed test execution on DUT + load generator
- **Docker or Podman** — Auto-detected container runtime with rootless Podman support
- **MTEB integration** — Embedding quality evaluation ([guide](docs/mteb-sweep-guide.md))
- **Results tooling** — [Streamlit dashboards](docs/dashboards-quickstart.md) and [MLflow](docs/mlflow.md) tracking

## Documentation

| Topic | Link |
| --- | --- |
| Documentation index | [docs/index.md](docs/index.md) |
| Getting started | [docs/getting-started.md](docs/getting-started.md) |
| cpueval CLI | [docs/cpueval-cli.md](docs/cpueval-cli.md) |
| Ansible playbooks | [automation/test-execution/ansible/ansible.md](automation/test-execution/ansible/ansible.md) |
| Model catalog | [models/models.md](models/models.md) |
| Methodology & metrics | [docs/methodology/overview.md](docs/methodology/overview.md) |
| Platform setup (Intel) | [docs/platform-setup/x86/intel/deterministic-benchmarking.md](docs/platform-setup/x86/intel/deterministic-benchmarking.md) |

## Repository Layout

| Path | Purpose |
| --- | --- |
| `automation/` | Ansible playbooks, cpueval CLI, dashboards, MLflow |
| `docs/` | Guides and methodology (source for the published site) |
| `models/` | Model definitions and test matrices |
| `tests/` | Per-suite methodology and scenario configs |
| `results/` | Local benchmark output (gitignored) |
| `logs/` | Execution logs (gitignored) |

## Requirements

- **Hardware:** Intel Xeon (Ice Lake+) or AMD EPYC; 64 GB+ RAM recommended
- **OS:** Ubuntu 22.04+, RHEL 9+, or Fedora 38+
- **Software:** Python 3.10+, Docker 24+ or Podman 4+, Ansible 2.14+, vLLM, GuideLLM

On the control machine, `./cpueval install` installs Ansible, Galaxy collections,
and shell completion. See [Getting Started](docs/getting-started.md) for
control-machine and DUT setup.

## Contributing

1. Fork the repository and create a feature branch
2. Make your changes
3. Run pre-commit checks: `pre-commit run --all-files`
4. Open a pull request

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg
```

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

Model weights, container images, and other third-party assets referenced by
this project remain under their respective licenses.

## Support

- **Issues:** [github.com/redhat-et/vllm-cpu-perf-eval/issues](https://github.com/redhat-et/vllm-cpu-perf-eval/issues)
- **Discussions:** [github.com/redhat-et/vllm-cpu-perf-eval/discussions](https://github.com/redhat-et/vllm-cpu-perf-eval/discussions)

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) — High-performance LLM inference
- [GuideLLM](https://github.com/vllm-project/guidellm) — LLM benchmarking tool
