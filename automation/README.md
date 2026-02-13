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

# Run entire test phase
ansible-playbook playbooks/run-phase.yml -e "phase=phase-1-concurrent"

# Run specific model
ansible-playbook playbooks/run-model.yml \
  -e "model_name=llama-3.2-1b" \
  -e "phase=phase-1-concurrent"

# Distributed testing across multiple nodes
ansible-playbook playbooks/distributed-tests.yml
```

### Using Bash Scripts (Test Execution)

```bash
# Run a phase
automation/test-execution/bash/run-phase.sh phase-1-concurrent

# Run a single model
automation/test-execution/bash/run-model.sh llama-3.2-1b phase-1-concurrent
```

## Results Analysis

Generate reports and compare test results.

```bash
cd automation/analysis

# Generate HTML report
python generate-report.py \
  --input ../../results/phase-1/ \
  --format html \
  --output ../../results/reports/phase-1-report.html

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
