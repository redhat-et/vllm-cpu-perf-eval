# Getting Started with Integration Tests

## What We've Built

A complete integration test framework with:

- **2-tier structure**: `smoke/` and `integration/` with pytest markers
- **Shared fixtures**: Reusable test infrastructure in `conftest.py`
- **Helper modules**: Container and metrics validation utilities
- **Example tests**: NUMA configs and container operations
- **CI workflow**: GitHub Actions for automated testing

## Quick Start

### 1. Install Dependencies

```bash
# From repository root
pip install pytest ansible pyyaml

# Optional: Install container runtime if not already installed
# podman (recommended) or docker
```

### 2. Run Your First Tests

```bash
cd automation/test-execution/ansible/tests

# Run all integration tests (fast ones only)
pytest -m "integration and not slow" -v

# Run specific test file
pytest integration/test_numa_configs.py -v

# Run specific test
pytest integration/test_numa_configs.py::TestNumaConfigCombinations::test_auto_tp_calculation -v
```

### 3. Test Markers Reference

| Marker | Purpose | Usage |
|--------|---------|-------|
| `smoke` | Fast validation (< 30s total) | `pytest -m smoke` |
| `unit` | Unit tests | `pytest -m unit` |
| `integration` | Component integration tests | `pytest -m integration` |
| `e2e` | End-to-end workflows | `pytest -m e2e` |
| `slow` | Long-running tests (> 1min) | `pytest -m "integration and not slow"` |
| `requires_numa` | Multi-NUMA hardware needed | `pytest -m "integration and not requires_numa"` |
| `requires_container` | Container runtime needed | Auto-skips if unavailable |

## Current Test Coverage

### ✅ Implemented

1. **NUMA Configuration Tests** (`test_numa_configs.py`)
   - Single NUMA allocation (TP=1)
   - Multi-NUMA TP=2, TP=4
   - Invalid TP value handling
   - Auto TP calculation
   - Insufficient cores error handling

2. **Container Operations** (`test_container_operations.py`)
   - Basic container lifecycle
   - CPU affinity settings
   - Environment variables
   - Container cleanup

3. **Test Infrastructure**
   - Shared fixtures (paths, container runtime, Ansible, NUMA)
   - Helper modules (container operations, metrics validation)
   - pytest configuration with markers
   - GitHub Actions workflow

### 🚧 TODO (Next Steps)

See the [full TODO list](#whats-next) below.

## Project Structure

```
tests/
├── pytest.ini                      # Pytest configuration with markers
├── unit/                           # Unit tests
│   └── test_cpu_utils.py          # CPU utils filter tests
├── smoke/                          # Fast validation tests
│   ├── test_playbook_syntax.py
│   ├── test_model_matrix.py
│   └── test_container_config.py
└── integration/                    # Integration & E2E tests
    ├── README.md                   # Detailed integration docs
    ├── GETTING_STARTED.md         # This file
    ├── conftest.py                # Shared fixtures
    ├── fixtures/                  # Test data (TODO)
    ├── helpers/                   # Utility modules
    │   ├── container_helper.py    # Container operations
    │   └── metrics_validator.py   # Metrics validation
    ├── test_numa_configs.py       # ✅ NUMA tests
    ├── test_container_operations.py  # ✅ Container tests
    ├── test_config_combinations.py   # TODO
    ├── test_model_inference.py       # TODO
    ├── test_playbook_execution.py    # TODO
    ├── test_results_validation.py    # TODO
    └── test_e2e_workflows.py         # TODO
```

## Example: Writing a New Test

Let's write a simple integration test:

```python
#!/usr/bin/env python3
"""Integration test for my feature."""
import pytest

@pytest.mark.integration
class TestMyFeature:
    """Test my feature integration."""

    def test_basic_functionality(self, ansible_dir, container_runtime):
        """Test basic feature works."""
        # Use fixtures from conftest.py
        playbook = ansible_dir / "my-playbook.yml"
        assert playbook.exists()

        # Test implementation
        assert container_runtime in ["podman", "docker"]

    @pytest.mark.slow
    def test_comprehensive_check(self, temp_results_dir):
        """Test comprehensive validation."""
        # This test takes longer
        # Marked as 'slow' so it can be skipped in fast runs
        pass
```

Save as `integration/test_my_feature.py` and run:

```bash
pytest integration/test_my_feature.py -v
```

## Running Tests in Different Scenarios

### Local Development

```bash
# Fast feedback loop
pytest -m "integration and not slow" -v

# Run with specific marker combination
pytest -m "integration and not e2e and not requires_numa" -v

# Run only NUMA tests (if you have multi-NUMA hardware)
pytest -m requires_numa -v
```

### Pre-Commit

```bash
# Run before committing
pytest -m "smoke or (integration and not slow and not e2e)" -v
# Takes ~2-5 minutes
```

### CI/CD

Different workflows for different scenarios:

**Pull Request** (runs automatically):
```yaml
pytest -m "integration and not slow and not e2e and not requires_numa"
# ~5-10 minutes on single-NUMA runner
```

**Nightly** (scheduled):
```yaml
pytest -m "integration and not requires_numa"
# ~30-60 minutes, includes slow tests
```

**Manual E2E** (workflow_dispatch):
```yaml
pytest -m "e2e and not requires_numa"
# ~10-30 minutes, full workflows
```

## Using Fixtures

### Container Fixtures

```python
def test_with_container(container_runtime, cleanup_containers):
    from integration.helpers.container_helper import run_container

    result = run_container(
        runtime=container_runtime,
        image="busybox:latest",
        name="my-test-container",
        command=["sleep", "30"]
    )

    container_id = result.stdout.strip()
    cleanup_containers(container_id)  # Auto-cleanup on test end

    # Your test logic
```

### NUMA Fixtures

```python
def test_numa_aware(numa_topology, skip_if_single_numa):
    # Test automatically skips on single-NUMA systems

    num_nodes = numa_topology["node_count"]
    assert num_nodes >= 2

    # Test multi-NUMA logic
```

### Ansible Fixtures

```python
def test_playbook(ansible_runner, temp_results_dir):
    result = ansible_runner(
        "health-check.yml",
        extra_vars={"results_dir": str(temp_results_dir)}
    )

    assert result.returncode == 0
```

## Debugging Tests

### View Full Output

```bash
# Show detailed output including print statements
pytest integration/test_numa_configs.py -v -s

# Show full traceback
pytest integration/test_numa_configs.py -v --tb=long
```

### Run Specific Test

```bash
# Run one test method
pytest integration/test_numa_configs.py::TestNumaAllocation::test_single_numa_allocation -v

# Run one test class
pytest integration/test_numa_configs.py::TestNumaAllocation -v
```

### See Which Tests Would Run

```bash
# Collect tests without running
pytest -m integration --collect-only

# See what markers do
pytest -m "integration and not slow" --collect-only
```

## What's Next?

### PR #3 TODO List

- [ ] **Config Combinations** (`test_config_combinations.py`)
  - Single NUMA + TP=1
  - Multi-NUMA + TP=[2,4,8]
  - Different workload types
  - KV cache format validation
  - Prefix caching enabled/disabled

- [ ] **Model Inference** (`test_model_inference.py`)
  - Load minimal models (TinyLlama, OPT-125M)
  - Verify model serves
  - Send test inference requests
  - Validate response format
  - Test different dtypes

- [ ] **Playbook Execution** (`test_playbook_execution.py`)
  - `health-check.yml` execution
  - `llm-benchmark-concurrent-load.yml` (minimal config)
  - Server start/stop workflow
  - Playbook idempotency

- [ ] **Results Validation** (`test_results_validation.py`)
  - Benchmark results structure
  - Metrics validation (TTFT, TPOT, throughput, latency)
  - Results collector role
  - CSV/JSON export formats

- [ ] **E2E Workflows** (`test_e2e_workflows.py`)
  - Platform setup → vLLM start → benchmark → results → cleanup
  - Concurrent load workflow with TinyLlama
  - Multi-NUMA benchmark scenario

- [ ] **Error Scenarios** (`test_error_scenarios.py`)
  - Invalid configurations
  - Missing models
  - Network failures
  - Container crashes

### Test Fixtures to Add

- [ ] Minimal model configs in `fixtures/`
- [ ] Test workload definitions
- [ ] Expected benchmark outputs
- [ ] Sample playbook inventory files

### Documentation

- [ ] Add examples for each test type
- [ ] Document CI/CD workflow triggers
- [ ] Add troubleshooting section
- [ ] Create contribution guide for tests

## Getting Help

- **Integration test docs**: [integration/README.md](README.md)
- **Pytest docs**: <https://docs.pytest.org/>
- **Fixture reference**: See `conftest.py`
- **Helper modules**: See `helpers/` directory

## Summary

You now have:
- ✅ 2-tier test structure with markers
- ✅ Shared fixtures for common operations
- ✅ Helper utilities for containers and metrics
- ✅ Example integration tests
- ✅ CI workflow configured
- ✅ Clear path forward for remaining tests

Start by running the existing tests, then add new tests following the patterns shown in `test_numa_configs.py` and `test_container_operations.py`.
