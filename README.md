# vLLM CPU Performance Evaluation

Comprehensive performance testing framework for vLLM on CPU platforms.

This repository provides a complete testing methodology, automation tools, and
platform configurations for evaluating vLLM inference performance on CPU-based
systems.

## Quick Start

```bash
# 1. Setup your platform (Ansible recommended)
cd automation/platform-setup/ansible
ansible-playbook playbooks/site.yml -i inventory/hosts.yml

# 2. Run a test phase
cd ../../test-execution/ansible
ansible-playbook playbooks/run-phase.yml -e "phase=phase-1-concurrent"

# 3. Generate report
cd ../analysis
python generate-report.py --input ../../results/phase-1/ --format html
```

See [Quick Start Guide](docs/getting-started/quick-start.md) for detailed
instructions.

## Repository Structure

```text
vllm-cpu-perf-eval/
├── models/                  # Centralized model definitions
├── tests/                   # Test scenarios organized by phase
│   ├── phase-1-concurrent/
│   ├── phase-2-scalability/
│   └── phase-3-resource-contention/
├── containers/              # Container definitions (Docker/Podman)
├── automation/              # Automation scripts and playbooks
│   ├── platform-setup/      # System configuration
│   ├── test-execution/      # Test orchestration
│   ├── analysis/            # Results analysis
│   └── utilities/           # Helper scripts
├── results/                 # Test results (gitignored)
├── configs/                 # Shared configurations
├── docs/                    # Documentation
└── examples/                # Example configurations
```

See individual directory README files for detailed information.

## Key Features

### Flexible Container Runtime Support

- **Docker** or **Podman** - Use either runtime
- **Auto-detection** - Automatically detects available runtime
- **Rootless support** - Full Podman rootless compatibility

### Centralized Model Management

- Define models once, use across all test phases
- Easy to add new models
- Model matrix for flexible test configuration

### Multi-Platform Support

- Intel Xeon (Ice Lake, Sapphire Rapids)
- AMD EPYC (planned)
- ARM64 (planned)

### Comprehensive Automation

- **Ansible playbooks** for platform setup and test execution
- **Bash scripts** for manual operation
- **Docker/Podman Compose** for containerized testing
- **Distributed testing** across multiple nodes

### Multiple Test Phases

- **Phase 1**: Concurrent load testing
- **Phase 2**: Scalability and sweep testing
- **Phase 3**: Resource contention (planned)

## Testing Workflow

### 1. Platform Setup

Configure your system for deterministic performance testing:

```bash
# With Ansible (recommended)
cd automation/platform-setup/ansible
ansible-playbook playbooks/site.yml

# With bash script
cd automation/platform-setup/bash/intel
sudo ./setup-guidellm-platform.sh --apply
```

See [Platform Setup Guide](docs/platform-setup/) for details.

### 2. Run Tests

Execute performance tests using Ansible or Docker/Podman:

```bash
# Ansible - Run entire phase
cd automation/test-execution/ansible
ansible-playbook playbooks/run-phase.yml -e "phase=phase-1-concurrent"

# Docker/Podman - Run specific test
cd tests/phase-1-concurrent
MODEL_NAME=llama-3.2-1b SCENARIO=concurrent-8 docker compose up
```

See [Test Execution Guide](docs/ansible/test-execution.md) for details.

### 3. Analyze Results

Generate reports and compare results:

```bash
cd automation/analysis
python generate-report.py \
  --input ../../results/phase-1/ \
  --format html \
  --output ../../results/reports/phase-1.html
```

See [Reporting Guide](docs/methodology/reporting.md) for details.

## Documentation

- **[Getting Started](docs/getting-started/)** - Quick start guides
- **[Methodology](docs/methodology/)** - Testing methodology and metrics
- **[Platform Setup](docs/platform-setup/)** - Platform configuration guides
- **[Containers](docs/containers/)** - Docker/Podman guides
- **[Ansible](docs/ansible/)** - Ansible playbook documentation
- **[Reference](docs/reference/)** - Schema and CLI reference

Full documentation index: [docs/docs.md](docs/docs.md)

## Test Phases

### Phase 1: Concurrent Load Testing

Tests model performance under various concurrent request loads.

- Concurrency levels: 8, 16, 32, 64, 96, 128
- 8 LLM models + 2 embedding models
- Focus: P95 latency, TTFT, throughput scaling

### Phase 2: Scalability Testing

Characterizes maximum throughput and performance curves.

- Sweep tests for capacity discovery
- Synchronous baseline tests
- Poisson distribution tests
- Focus: Maximum capacity, saturation points

### Phase 3: Resource Contention (Planned)

Multi-tenant and resource sharing scenarios.

## Models

Current model coverage:

**LLM Models:**

- Llama-3.2 (1B, 3B)
- TinyLlama-1.1B
- OPT (125M, 1.3B)
- Granite-3.0-2B
- Qwen2.5 (0.5B, 3B)

**Embedding Models:**

- BGE-base-en-v1.5
- BGE-large-en-v1.5

See [models/models.md](models/models.md) for model definitions and how to
add new models.

## Requirements

### System Requirements

- **CPU**: Intel Xeon (Ice Lake or newer) or AMD EPYC
- **Memory**: 64GB+ RAM recommended
- **OS**: Ubuntu 22.04+, RHEL 9+, or Fedora 38+
- **Storage**: 500GB+ for models and results

### Software Requirements

- Python 3.10+
- Docker 24.0+ or Podman 4.0+
- Ansible 2.14+ (for automation)
- GuideLLM
- vLLM

See [docs/getting-started/quick-start.md](docs/getting-started/quick-start.md)
for installation instructions.

## Container Runtime Support

This repository supports both Docker and Podman:

- **Docker**: Traditional container runtime
- **Podman**: Daemonless, rootless-capable alternative
- **Auto-detection**: Automatically uses available runtime

Set runtime preference:

```bash
# Use Docker
export CONTAINER_RUNTIME=docker

# Use Podman
export CONTAINER_RUNTIME=podman

# Auto-detect (default)
export CONTAINER_RUNTIME=auto
```

See [Container Guide](docs/containers/) for details.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run pre-commit checks: `pre-commit run --all-files`
5. Submit a pull request

### Pre-commit Hooks

This repository uses [pre-commit](https://pre-commit.com/) to ensure code
quality.

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Run manually
pre-commit run --all-files
```

## License

[Add license information]

## Support

- **Documentation**: See [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/YOUR_ORG/vllm-cpu-perf-eval/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_ORG/vllm-cpu-perf-eval/discussions)

## Acknowledgments

- [vLLM](https://github.com/vllm-project/vllm) - High-performance LLM
  inference engine
- [GuideLLM](https://github.com/neuralmagic/guidellm) - LLM benchmarking tool
- Intel and AMD for CPU optimization guidance
