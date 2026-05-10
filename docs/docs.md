# Documentation

Comprehensive documentation for vLLM CPU performance evaluation.

## Quick Links

- **New users**: Start with [Getting Started](getting-started/quick-start.md)
- **Running tests**: See [Test Execution Guide](ansible/test-execution.md)
- **Platform setup**: See [Platform Setup](platform-setup/)
- **Understanding results**: See [Metrics Guide](methodology/metrics.md)

## Documentation Structure

```text
docs/
├── getting-started/          # Quick start guides
│   ├── quick-start.md       # 5-minute getting started
│   ├── adding-models.md     # How to add new models
│   ├── creating-tests.md    # How to create test scenarios
│   └── interpreting-results.md
│
├── methodology/             # Testing methodologies
│   ├── overview.md          # Performance evaluation overview
│   ├── metrics.md           # Metrics definitions
│   ├── reporting.md         # Test report structure
│   ├── repeatability-analysis.md # Benchmark repeatability using CV
│   └── (manual-sweep.md)    # Manual sweep testing guide
│
├── platform-setup/          # Platform configuration
│   ├── x86/intel/
│   │   └── deterministic-benchmarking.md
│   ├── ansible-guide.md     # Using Ansible for setup
│   └── bash-guide.md        # Using bash scripts
│
├── containers/              # Container runtime guides
│   ├── getting-started.md   # Container basics
│   ├── docker-guide.md      # Docker-specific guide
│   ├── podman-guide.md      # Podman-specific guide
│   ├── runtime-comparison.md # Docker vs Podman
│   └── rootless-containers.md
│
├── ansible/                 # Ansible documentation
│   ├── test-execution.md    # Using Ansible for tests
│   ├── distributed-testing.md
│   └── playbook-reference.md
│
└── reference/               # Reference documentation
    ├── model-yaml-schema.md
    ├── test-yaml-schema.md
    ├── matrix-yaml-schema.md
    └── cli-reference.md
```text

## Documentation by Topic

### For New Users

1. [Quick Start Guide](getting-started/quick-start.md) - Get up and running
   in 5 minutes
2. [Running Your First Test](getting-started/running-first-test.md) - Execute
   a simple test
3. [Interpreting Results](getting-started/interpreting-results.md) - Understand
   test output

### For Test Execution

1. [Container Getting Started](containers/getting-started.md) - Docker/Podman
   basics
2. [Test Execution with Ansible](ansible/test-execution.md) - Automated test
   orchestration
3. [Distributed Testing](ansible/distributed-testing.md) - Multi-node testing

### For Platform Setup

1. [Platform Setup Overview](platform-setup/platform-setup.md) - Platform configuration
   overview
2. [Intel Xeon Setup](platform-setup/x86/intel/deterministic-benchmarking.md) -
   Intel-specific tuning
3. [Ansible Setup Guide](platform-setup/ansible-guide.md) - Automated platform
   configuration

### For Understanding Results

1. [Metrics Guide](methodology/metrics.md) - Metrics definitions and
   interpretation
2. [Reporting Guide](methodology/reporting.md) - Report structure and formats
3. [Performance Evaluation Overview](methodology/overview.md) - Testing
   methodology
4. [Repeatability Analysis](methodology/repeatability-analysis.md) - Analyzing
   benchmark consistency with CV

### Reference Documentation

1. [Model Configuration Schema](reference/model-yaml-schema.md) - Model YAML
   format
2. [Test Scenario Schema](reference/test-yaml-schema.md) - Test YAML format
3. [CLI Reference](reference/cli-reference.md) - Command-line tool reference

## Contributing to Documentation

Documentation is written in Markdown and follows these conventions:

- Use ATX-style headers (`#` not `===`)
- Maximum line length: 80 characters
- Code blocks must specify language
- Tables must be properly formatted

Run pre-commit checks before committing:

```bash
pre-commit run --all-files
```text

## Documentation Status

<!-- markdownlint-disable MD013 -->

| Document | Status | Last Updated |
| --- | --- | --- |
| methodology/overview.md | ✅ Complete | 2024-02-08 |
| methodology/metrics.md | ✅ Complete | 2024-02-08 |
| methodology/reporting.md | ✅ Complete | 2024-02-08 |
| methodology/repeatability-analysis.md | ✅ Complete | 2026-05-05 |
| platform-setup/x86/intel/deterministic-benchmarking.md | ✅ Complete | (current) |
| ansible/test-execution.md | ✅ Complete | 2026-04-28 |
| containers/* | 📝 Planned | - |
| ansible/distributed-testing.md | 📝 Planned | - |
| ansible/playbook-reference.md | 📝 Planned | - |
| getting-started/* | 📝 Planned | - |
| reference/* | 📝 Planned | - |

<!-- markdownlint-enable MD013 -->

Legend:
- ✅ Complete
- 📝 Planned
- 🚧 In Progress
