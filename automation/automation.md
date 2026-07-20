# Automation Directory

This directory contains all automation scripts and playbooks for platform setup
and test execution.

## Structure

```text
automation/
├── platform-setup/            # System configuration automation
│   └── bash/                 # Shell scripts for setup
├── test-execution/           # Test orchestration automation
│   ├── ansible/              # Ansible playbooks for running tests
│   ├── bash/                 # Shell scripts for running tests
│   ├── dashboard-examples/   # Streamlit dashboard for results
│   ├── grafana/              # Grafana dashboards for live monitoring
│   ├── mlflow/               # MLflow experiment tracking
│   └── scripts/              # Python/bash helper scripts
└── utilities/                # Helper scripts
    ├── health-checks/        # Health check scripts
    └── log-monitoring/       # Log analysis tools
```

## Platform Setup

Configure your system for deterministic performance testing.

### Using Ansible (Recommended)

```bash
cd automation/test-execution/ansible

# Configure DUT and Load Generator hosts
ansible-playbook -i inventory/hosts.yml setup-platform.yml
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

Run performance tests using Ansible playbooks.

### Using Ansible

```bash
cd automation/test-execution/ansible

# Run a single LLM test
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores=16"

# Run concurrent load test suite (all 3 phases)
ansible-playbook -i inventory/hosts.yml llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=chat" \
  -e "requested_cores=32"
```

## Results Analysis

View results using the Streamlit dashboard:

```bash
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh
# Open http://localhost:8501
```

See [Dashboards Quick Start](../docs/dashboards-quickstart.md) for details.

## Documentation

- Getting started: [docs/getting-started.md](../docs/getting-started.md)
- Platform setup: [docs/platform-setup/](../docs/platform-setup/)
- Ansible guide: [docs/ansible/](../docs/ansible/)
- Dashboards: [docs/dashboards-quickstart.md](../docs/dashboards-quickstart.md)
