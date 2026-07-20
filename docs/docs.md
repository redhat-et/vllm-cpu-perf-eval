# Documentation

Comprehensive documentation for vLLM CPU performance evaluation.

## Quick Links

- **New users**: Start with [Getting Started](getting-started.md)
- **Running tests**: See [Test Execution Guide](ansible/test-execution.md)
- **Platform setup**: See [Platform Setup](platform-setup/)
- **Understanding results**: See [Metrics Guide](methodology/metrics.md)
- **Experiment tracking**: See [MLflow Integration](mlflow.md)
- **Dashboards**: See [Dashboards Quick Start](dashboards-quickstart.md)
- **Terminal viewer**: See [Terminal Results Viewer](terminal-results-viewer.md)
- **Metrics collection**: See [Metrics Collection Guide](metrics-collection.md)

## Documentation Structure

```text
docs/
├── getting-started.md        # Quick start guide
├── dashboards-quickstart.md  # Streamlit dashboard guide
├── terminal-results-viewer.md # Terminal results viewer
├── metrics-collection.md     # vLLM metrics collection
├── mlflow.md                 # MLflow experiment tracking
├── environment-variables.md  # Environment variable reference
├── scripts-reference.md      # Scripts reference
│
├── methodology/              # Testing methodologies
│   ├── overview.md           # Performance evaluation overview
│   ├── metrics.md            # Metrics definitions
│   ├── reporting.md          # Test report structure
│   ├── testing-phases.md     # 3-phase testing methodology
│   ├── ietf-alignment.md     # IETF benchmarking alignment
│   └── manual-sweep.md       # Manual sweep testing guide
│
├── ansible/                  # Ansible documentation
│   ├── test-execution.md     # Using Ansible for tests
│   └── model-predownload.md  # Model pre-download guide
│
└── platform-setup/           # Platform configuration
    └── x86/intel/
        └── deterministic-benchmarking.md
```

## Documentation by Topic

### For New Users

1. [Getting Started](getting-started.md) - Setup and run your first test
2. [Dashboards Quick Start](dashboards-quickstart.md) - View results in
   Streamlit
3. [Terminal Results Viewer](terminal-results-viewer.md) - Quick
   results in the terminal

### For Test Execution

1. [Test Execution with Ansible](ansible/test-execution.md) - Automated test
   orchestration
2. [Testing Methodology](methodology/overview.md) - Performance evaluation
   approach
3. [3-Phase Testing](methodology/testing-phases.md) - Baseline, realistic,
   and production phases

### For Platform Setup

1. [Intel Xeon Setup](platform-setup/x86/intel/deterministic-benchmarking.md)
   \- Intel-specific tuning

### For Understanding Results

1. [Metrics Guide](methodology/metrics.md) - Metrics definitions and
   interpretation
2. [Reporting Guide](methodology/reporting.md) - Report structure and formats
3. [IETF Alignment](methodology/ietf-alignment.md) - IETF benchmarking
   alignment

### For Results Analysis

1. [MLflow Experiment Tracking](mlflow.md) - Track and compare experiments
2. [Interactive Dashboards](dashboards-quickstart.md) - Visualize results
3. [Terminal Results Viewer](terminal-results-viewer.md) - Quick
   terminal output
4. [Metrics Collection Guide](metrics-collection.md) - Server-side metrics

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

| Document | Status |
| --- | --- |
| getting-started.md | ✅ Complete |
| methodology/overview.md | ✅ Complete |
| methodology/metrics.md | ✅ Complete |
| methodology/reporting.md | ✅ Complete |
| methodology/testing-phases.md | ✅ Complete |
| methodology/ietf-alignment.md | ✅ Complete |
| methodology/manual-sweep.md | ✅ Complete |
| platform-setup/x86/intel/deterministic-benchmarking.md | ✅ Complete |
| ansible/test-execution.md | ✅ Complete |
| ansible/model-predownload.md | ✅ Complete |
| mlflow.md | ✅ Complete |
| dashboards-quickstart.md | ✅ Complete |
| terminal-results-viewer.md | ✅ Complete |
| metrics-collection.md | ✅ Complete |

<!-- markdownlint-enable MD013 -->

Legend:
- ✅ Complete
- 📝 Planned
- 🚧 In Progress
