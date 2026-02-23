# Automation Directory

This directory contains all automation scripts and playbooks for platform setup
and test execution.

## Structure

```text
automation/
├── platform-setup/            # System configuration automation
│   ├── ansible/              # Ansible playbooks for setup
│   └── bash/                 # Shell scripts for setup
├── test-execution/           # Test orchestration automation
│   ├── ansible/              # Ansible playbooks for running tests
│   └── bash/                 # Shell scripts for running tests
├── analysis/                 # Results analysis scripts
│   ├── generate-report.py
│   ├── compare-results.py
│   └── templates/
└── utilities/                # Helper scripts
```

## Platform Setup

Configure your system for deterministic performance testing.

### Using Ansible (Recommended)

```bash
cd automation/platform-setup/ansible

# Configure all nodes
ansible-playbook playbooks/site.yml -i inventory/hosts.yml

# Configure specific platform
ansible-playbook playbooks/configure-intel.yml
```

### Using Bash Scripts (Platform Setup)

```bash
cd automation/platform-setup/bash/intel

# Check current configuration
./setup-guidellm-platform.sh --check

# Apply configuration
sudo ./setup-guidellm-platform.sh --apply
```

## Test Execution

Run performance tests using container-based workflows.

### Using Ansible (Recommended for automation)

```bash
cd automation/test-execution/ansible

# Run entire test suite
ansible-playbook playbooks/run-suite.yml -e "test_suite=concurrent-load"

# Run specific model
ansible-playbook playbooks/run-model.yml \
  -e "model_name=llama-3.2-1b" \
  -e "test_suite=concurrent-load"

# Distributed testing across multiple nodes
ansible-playbook playbooks/distributed-tests.yml
```

**Note:** The `phase` parameter is deprecated. Use `test_suite` with the new suite names:
`concurrent-load`, `scalability`, `resource-contention`.

### Using Bash Scripts (Test Execution)

```bash
# Run a test suite
automation/test-execution/bash/run-suite.sh concurrent-load

# Run a single model
automation/test-execution/bash/run-model.sh llama-3.2-1b concurrent-load
```

## Results Analysis

Generate reports and compare test results.

```bash
cd automation/analysis

# Generate HTML report
python generate-report.py \
  --input ../../results/by-suite/concurrent-load/ \
  --format html \
  --output ../../results/reports/concurrent-load-report.html

# Compare multiple test runs
python compare-results.py \
  --baseline results/baseline.json \
  --current results/current.json
```

## Container Runtime Support

All automation supports both Docker and Podman:

- **Auto-detection**: Automatically detects available runtime
- **Explicit selection**: Set `CONTAINER_RUNTIME=docker` or `podman`
- **Per-host configuration**: Set runtime preference in Ansible inventory

## Documentation

- Platform setup: `docs/platform-setup/`
- Ansible guide: `docs/ansible/`
- Container guide: `docs/containers/`
- Getting started: `docs/getting-started/`
