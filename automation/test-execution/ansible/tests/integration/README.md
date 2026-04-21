# Integration Tests

Integration tests for the vLLM CPU performance evaluation framework. These tests validate component interactions, container operations, NUMA configurations, and end-to-end workflows.

## Directory Structure

```text
integration/
├── README.md              # This file
├── __init__.py
├── conftest.py            # Shared pytest fixtures
├── fixtures/              # Test data and configs
├── helpers/               # Helper utilities
│   ├── container_helper.py
│   └── metrics_validator.py
├── test_numa_configs.py          # NUMA allocation tests
├── test_container_operations.py  # Container lifecycle tests
├── test_config_combinations.py   # Config matrix tests (TODO)
├── test_model_inference.py       # Model loading tests (TODO)
└── test_e2e_workflows.py         # End-to-end tests (TODO)
```

## Test Categories

### Integration Tests (`@pytest.mark.integration`)
Tests that verify 2+ components working together:
- NUMA allocation with cpu_utils filters
- Container operations with CPU/NUMA affinity
- Ansible playbook execution
- Model configuration validation

**Duration**: 30 seconds - 5 minutes per test
**Requirements**: Container runtime (podman/docker)

### E2E Tests (`@pytest.mark.e2e` + `@pytest.mark.integration`)
Full user workflow tests:
- Platform setup → vLLM start → benchmark → results collection
- Complete concurrent load test workflow
- Multi-NUMA benchmark scenarios

**Duration**: 5-30+ minutes per test
**Requirements**: Container runtime, sufficient CPU cores, models downloaded

### Hardware-Specific Tests
Some tests require specific hardware:
- `@pytest.mark.requires_numa`: Multi-NUMA system required
- `@pytest.mark.requires_container`: Podman or Docker required
- `@pytest.mark.slow`: Long-running tests (> 1 minute)

## Running Tests

### Quick Start

```bash
# Install dependencies
pip install pytest ansible pyyaml

# Run all integration tests (fast subset)
cd automation/test-execution/ansible/tests
pytest -m "integration and not slow"

# Run with verbose output
pytest -m integration -v

# Run specific test file
pytest integration/test_numa_configs.py
```

### Test Selection

```bash
# Only fast integration tests
pytest -m "integration and not slow"

# Only E2E tests
pytest -m e2e

# Integration tests excluding E2E
pytest -m "integration and not e2e"

# Tests requiring NUMA hardware
pytest -m requires_numa

# Skip NUMA-dependent tests (for single-NUMA CI)
pytest -m "integration and not requires_numa"

# Specific test class
pytest integration/test_numa_configs.py::TestNumaAllocation

# Specific test method
pytest integration/test_numa_configs.py::TestNumaAllocation::test_single_numa_allocation
```

### Development Workflow

**Pre-commit** (run locally before pushing):
```bash
pytest -m "integration and not slow and not e2e"
# ~2-5 minutes
```

**PR Validation** (CI runs this):
```bash
pytest -m "integration and not e2e and not requires_numa"
# ~5-10 minutes on single-NUMA CI runner
```

**Nightly/Release** (full test suite):
```bash
pytest -m integration
# ~30-60 minutes with all tests
```

## Writing New Tests

### Test Structure

```python
#!/usr/bin/env python3
"""Integration tests for [feature]."""
import pytest

@pytest.mark.integration
class TestMyFeature:
    """Test [feature] integration."""

    def test_basic_functionality(self, fixture1, fixture2):
        """Test basic [feature] behavior."""
        # Test implementation

    @pytest.mark.slow
    def test_comprehensive_check(self):
        """Test comprehensive [feature] validation."""
        # Longer test implementation
```

### Using Fixtures

Common fixtures available in `conftest.py`:

```python
# Path fixtures
def test_with_paths(repo_root, ansible_dir, models_dir):
    playbook = ansible_dir / "health-check.yml"
    model_config = models_dir / "llm-models" / "model-matrix.yaml"

# Container fixtures
def test_container(container_runtime, cleanup_containers):
    # container_runtime is "podman" or "docker"
    # cleanup_containers automatically cleans up on test end

# Ansible fixtures
def test_playbook(ansible_runner, ansible_inventory):
    result = ansible_runner("health-check.yml")
    assert result.returncode == 0

# NUMA fixtures
def test_numa(numa_topology, skip_if_single_numa):
    # numa_topology has actual system NUMA info
    # skip_if_single_numa auto-skips on single-NUMA systems

# Utility fixtures
def test_server(wait_for_port, wait_for_health):
    assert wait_for_port(8000, timeout=30)
    assert wait_for_health("http://localhost:8000/health")
```

### Test Markers

Always add appropriate markers:

```python
@pytest.mark.integration          # All integration tests
@pytest.mark.e2e                 # End-to-end workflows
@pytest.mark.slow                # Tests > 1 minute
@pytest.mark.requires_numa       # Multi-NUMA hardware needed
@pytest.mark.requires_container  # Container runtime needed
```

### Example: NUMA Test

```python
@pytest.mark.integration
@pytest.mark.requires_numa
class TestNumaAllocation:
    def test_multi_numa_tp2(self, numa_topology, skip_if_single_numa):
        """Test 2-NUMA allocation with TP=2."""
        # Test will auto-skip on single-NUMA systems
        # numa_topology provides actual system info
```

### Example: Container Test

```python
@pytest.mark.integration
@pytest.mark.requires_container
class TestContainerOps:
    def test_start_stop(self, container_runtime, cleanup_containers):
        """Test container lifecycle."""
        from .helpers.container_helper import run_container, stop_container

        result = run_container(
            runtime=container_runtime,
            image="busybox:latest",
            name="test-container",
            command=["sleep", "30"]
        )

        container_id = result.stdout.strip()
        cleanup_containers(container_id)  # Auto-cleanup

        assert stop_container(container_runtime, container_id)
```

### Example: E2E Test

```python
@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.slow
class TestFullWorkflow:
    def test_benchmark_workflow(
        self,
        ansible_runner,
        temp_results_dir,
        minimal_vllm_config,
    ):
        """Test complete benchmark workflow."""
        # 1. Setup
        # 2. Start vLLM
        # 3. Run benchmark
        # 4. Validate results
        # 5. Cleanup
```

## Helper Modules

### container_helper.py

Utilities for container operations:
- `run_container()` - Start containers with configs
- `get_container_status()` - Check container state
- `get_container_logs()` - Retrieve logs
- `stop_container()` - Stop containers
- `remove_container()` - Remove containers

### metrics_validator.py

Utilities for validating benchmark results:
- `validate_benchmark_output()` - Check JSON structure
- `validate_results_structure()` - Check directory layout
- `extract_key_metrics()` - Parse metrics from output
- `assert_metrics_within_range()` - Validate metric ranges
- `compare_metrics()` - Compare against baseline

## Troubleshooting

### Container Runtime Not Found

```bash
# Install podman (preferred) or docker
sudo dnf install podman    # Fedora/RHEL
sudo apt install podman    # Ubuntu
```

Tests will auto-skip if no container runtime is available.

### NUMA Tests Failing

NUMA tests require multi-NUMA hardware. They auto-skip on single-NUMA systems:

```bash
# Run only non-NUMA tests
pytest -m "integration and not requires_numa"
```

### Slow Tests Timing Out

Increase timeouts in test code or skip slow tests:

```bash
# Skip slow tests
pytest -m "integration and not slow"
```

### Container Image Pull Failures

Some tests require container images. Skip them if images aren't available:

```bash
# Tests will auto-skip if images can't be pulled
pytest -m integration
```

Or pre-pull images:

```bash
podman pull busybox:latest
podman pull vllm/vllm-openai:latest
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Integration Tests

on: [pull_request, push]

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install pytest ansible pyyaml
      - name: Run integration tests
        run: |
          cd automation/test-execution/ansible/tests
          pytest -m "integration and not slow and not requires_numa"
```

### Test Matrix

Different test suites for different scenarios:

| Suite | Markers | Duration | When |
|-------|---------|----------|------|
| Fast | `integration and not slow and not e2e` | 2-5 min | Every PR |
| Standard | `integration and not e2e` | 5-10 min | PR merge |
| Full | `integration` | 30-60 min | Nightly |
| E2E | `e2e` | 10-30 min | Pre-release |

## Adding New Tests

1. Create test file: `test_<feature>.py`
2. Add appropriate markers (`@pytest.mark.integration`, etc.)
3. Use shared fixtures from `conftest.py`
4. Add helpers to `helpers/` if needed
5. Update this README with test description
6. Run tests locally before committing:
   ```bash
   pytest integration/test_<feature>.py -v
   ```

## Future Enhancements

- [ ] Add `test_config_combinations.py` for matrix testing
- [ ] Add `test_model_inference.py` for model loading
- [ ] Add `test_e2e_workflows.py` for full workflows
- [ ] Add `test_playbook_execution.py` for Ansible playbooks
- [ ] Add `test_results_validation.py` for results collection
- [ ] Add `test_error_scenarios.py` for error handling
- [ ] Add performance baseline tracking
- [ ] Add test result artifacts to CI
