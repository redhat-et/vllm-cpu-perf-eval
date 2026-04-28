# vLLM CPU Performance Evaluation

Comprehensive performance evaluation framework for vLLM on CPU platforms.

This repository provides a complete testing methodology, automation tools, and
platform configurations for evaluating vLLM inference performance on CPU-based
systems.

## Quick Start

See the [Quick Start Guide](docs/getting-started.md)

## Repository Structure

```text
vllm-cpu-perf-eval/
├── README.md                           # This file
│
├── models/                             # Centralized model definitions
│   ├── models.md                       # Comprehensive model documentation
│   ├── llm-models/                     # LLM model configurations
│   │   ├── model-matrix.yaml          # LLM model test mappings
│   │   └── llm-models.md              # Redirects to models.md
│   └── embedding-models/               # Embedding model configurations
│       └── model-matrix.yaml          # Embedding model test mappings
│
├── tests/                              # Test suites and scenarios
│   ├── tests.md                        # Test suite overview
│   ├── concurrent-load/                # Test Suite 1: Concurrent load testing
│   │   ├── concurrent-load.md         # Suite documentation
│   │   └── *.yaml                     # Test scenario definitions
│   ├── scalability/                    # Test Suite 2: Scalability testing
│   │   ├── scalability.md             # Suite documentation
│   │   └── *.yaml                     # Test scenario definitions
│   ├── resource-contention/            # Test Suite 3: Resource contention
│   │   ├── resource-contention.md     # Suite documentation
│   │   └── *.yaml                     # Test scenario definitions (planned)
│   └── embedding-models/               # Embedding model test scenarios
│       ├── embedding-models.md        # Embedding test documentation
│       ├── baseline-sweep.yaml        # Baseline performance tests
│       └── latency-concurrent.yaml    # Latency tests
│
├── automation/                         # Automation framework
│   ├── test-execution/                 # Test orchestration
│   │   ├── ansible/                   # Ansible playbooks (primary)
│   │   │   ├── ansible.md             # Ansible documentation
│   │   │   ├── inventory/             # Host configurations
│   │   │   ├── filter_plugins/        # Custom Ansible filters
│   │   │   ├── roles/                 # Ansible roles
│   │   │   ├── tests/                 # Ansible tests
│   │   │   └── *.yml                  # Playbook files
│   │   └── bash/                      # Bash automation scripts
│   │       └── embedding/             # Embedding test scripts
│   ├── platform-setup/                 # Platform configuration
│   │   └── bash/                      # Platform setup scripts
│   │       └── intel/                 # Intel-specific setup
│   └── utilities/                      # Helper utilities
│       ├── health-checks/             # Health check scripts
│       └── log-monitoring/            # Log analysis tools
│
├── docs/                               # Documentation
│   ├── docs.md                         # Documentation index
│   ├── methodology/                    # Test methodology
│   │   └── overview.md                # Testing approach and metrics
│   └── platform-setup/                 # Platform setup guides
│
├── results/                            # Test results (gitignored)
│   ├── llm/                           # LLM test results
│   └── results.md                     # Results documentation
│
├── utils/                              # Utility scripts and tools
│
└── Configuration Files
    ├── .pre-commit-config.yaml        # Pre-commit hooks configuration
    ├── .yamllint.yaml                 # YAML linting rules
    ├── .markdownlint-cli2.yaml        # Markdown linting rules
    └── .gitignore                     # Git ignore patterns
```

**Key Directories:**

- **[models/](models/models.md)** - Model definitions reused across all test suites
- **[tests/](tests/tests.md)** - Test suite definitions organized by testing focus
- **[automation/test-execution/ansible/](automation/test-execution/ansible/ansible.md)** - Ansible playbooks for test execution
- **[docs/](docs/docs.md)** - Comprehensive testing methodology and guides
- **results/** - Local test results (gitignored, see [results.md](results/results.md))

See individual directory markdown files for detailed information.

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
- AMD EPYC
- ARM64 (planned)

### Comprehensive Automation

- **Ansible playbooks** for platform setup and test execution
- **Bash scripts** for manual operation
- **Docker/Podman Compose** for containerized testing
- **Distributed testing** across multiple nodes

### Multiple Test Suites

- **Concurrent Load**: Concurrent load testing
- **Scalability**: Scalability and sweep testing
- **Resource Contention**: Resource contention testing (planned)

### Enhanced Concurrent Load Testing

- ⏱️ **Time-based testing** - Consistent 10-minute tests across CPU types
- 1️⃣ **Single-user baseline** - Concurrency=1 for efficiency calculations
- 📊 **Variable workloads** - Realistic traffic simulation with statistical variance
- 🔄 **Prefix caching control** - Baseline vs production comparison
- 🎯 **3-phase testing** - Baseline → Realistic → Production methodology
- 🚀 **Large model support** - Added gpt-oss-20b (21B MoE) for scalability testing

See [3-Phase Testing Strategy](docs/methodology/testing-phases.md) for details.

## Documentation

- **[Ansible Testing](automation/test-execution/ansible/ansible.md)** - Complete Ansible usage guide
- **[Methodology](docs/methodology/overview.md)** - Testing methodology and metrics
- **[Platform Setup](docs/platform-setup/x86/intel/deterministic-benchmarking.md)** - Intel platform configuration
- **[Models](models/models.md)** - Model definitions and selection
- **[Tests](tests/tests.md)** - Test suite documentation

Full documentation index: [docs/docs.md](docs/docs.md)

## Test Suites

> **⚠️ IMPORTANT: Validation Status and Availability**
>
> **✅ SUPPORTED (Fully Validated):**
> - **Concurrent Load Testing (Phase 1 & Phase 2)** - Ready for use
>   - Playbooks: `llm-benchmark-concurrent-load.yml`, `llm-benchmark-auto.yml`
>   - Documentation: [tests/concurrent-load/concurrent-load.md](tests/concurrent-load/concurrent-load.md)
>
> **🚧 NOT YET SUPPORTED (Blocked from End User Execution):**
>
> The following test suites are work in progress and are **automatically blocked**
> to prevent end users from running them until they are fully validated:
>
> - **Scalability** - Work in progress; blocked by default
>   - Playbook: `llm-core-sweep-auto.yml` (will fail with error message)
>   - Contains: sweep, synchronous, poisson tests
>
> - **Embedding Models** - Work in progress; blocked by default
>   - Playbook: `embedding-benchmark.yml` (will fail with error message)
>   - Scripts: `run-baseline.sh`, `run-latency.sh`, `run-all.sh` (will exit with error)
>
> - **Resource Contention** - Planned; not yet implemented
>   - No test files exist yet
>
> **Bypass for Development/Testing Only:**
>
> If you need to run unsupported tests for development or testing purposes:
> - Ansible: Add `-e "allow_unsupported_tests=true"` to your playbook command
> - Bash: Export `ALLOW_UNSUPPORTED_TESTS=true` before running scripts
>
> **Note:** Unsupported tests are provided as-is with no guarantees they will
> work without modification. Only use them if you understand the risks and are
> willing to troubleshoot issues independently.

### Test Suite: Concurrent Load

Tests model performance under various concurrent request loads.

- Concurrency levels: 1, 2, 4, 8, 16, 32
- 7 LLM models + 2 embedding models
- Focus: P95 latency, TTFT, throughput scaling

### Test Suite: Scalability

> **🚧 NOT YET SUPPORTED** - This test suite is blocked by default.
> See validation status above for details.

Characterizes maximum throughput and performance curves.

- Sweep tests for capacity discovery
- Synchronous baseline tests
- Poisson distribution tests
- Focus: Maximum capacity, saturation points

### Test Suite: Resource Contention

> **📋 PLANNED** - Not yet implemented.

Multi-tenant and resource sharing scenarios.

## Models

Current model coverage:

**LLM Models (7 total):**

- Llama-3.2 (1B, 3B) - Prefill-heavy
- TinyLlama-1.1B - Balanced small-scale
- Granite-3.2-2B - Balanced enterprise
- Qwen3-0.6B, Qwen2.5-3B - High-efficiency balanced

**Embedding Models:**

> **🚧 NOT YET SUPPORTED** - Embedding model tests are blocked by default.
> These models are defined but testing is not yet validated.

- granite-embedding-english-r2
- granite-embedding-278m-multilingual

See [models/models.md](models/models.md) for complete model definitions,
selection rationale, and how to add new models.

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
- GuideLLM v0.5.0+
- vLLM

See [Ansible Documentation](automation/test-execution/ansible/ansible.md) for
setup and configuration instructions.

## Container Runtime Support

This repository supports both Docker and Podman:

- **Docker**: Traditional container runtime
- **Podman**: Daemonless, rootless-capable alternative
- **Auto-detection**: Automatically uses available runtime

The Ansible playbooks automatically detect and use the available container runtime.
For manual configuration, see the [vllm_server role](automation/test-execution/ansible/roles/vllm_server/)
documentation.

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
- [GuideLLM](https://github.com/vllm-project/guidellm) - LLM benchmarking tool
- Intel and AMD for CPU optimization guidance
