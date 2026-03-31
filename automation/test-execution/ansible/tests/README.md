# Test Suite

This directory contains tests for the vLLM CPU performance evaluation framework.

## Test Organization

```text
tests/
├── unit/               # Unit tests for filter plugins and utilities
│   └── test_cpu_utils.py
├── smoke/              # Smoke tests for configuration validation
│   ├── test_playbook_syntax.py
│   ├── test_model_matrix.py
│   └── test_container_config.py
├── pytest.ini          # Pytest configuration
└── README.md           # This file
```

## Test Markers

- **smoke**: Quick validation tests (< 30 seconds total)
- **integration**: Tests requiring containers or external services
- **slow**: Tests that take significant time (image pulls, container starts)
- **unit**: Unit tests for individual components

## Running Tests

### Quick Start

```bash
# Install dependencies
pip install pytest ansible pyyaml

# Run all tests
cd automation/test-execution/ansible/tests
pytest

# Run only smoke tests (fast)
pytest -m smoke

# Run only unit tests
pytest -m unit

# Run with verbose output
pytest -v

# Run specific test file
pytest smoke/test_model_matrix.py
```

### Test Categories

**Smoke Tests** (Run these first - they're fast!)

```bash
# All smoke tests
pytest -m smoke

# Just playbook syntax validation
pytest smoke/test_playbook_syntax.py

# Just model matrix validation
pytest smoke/test_model_matrix.py

# Just container configuration
pytest smoke/test_container_config.py -m "smoke and not slow"
```

**Unit Tests**

```bash
# CPU utilities tests
pytest unit/test_cpu_utils.py
```

**Integration Tests** (Coming soon)

```bash
# All integration tests
pytest -m integration
```

### Running in CI

The GitHub workflow automatically runs:

1. **Unit tests** - On every PR and push
2. **Smoke tests** - On every PR and push
3. **Integration tests** - On demand or scheduled

See [.github/workflows/unit-tests.yml](../../../../.github/workflows/unit-tests.yml)

## Writing New Tests

### Smoke Tests

Smoke tests should:

- Run quickly (< 5 seconds each)
- Validate configuration and syntax
- Not require external services or infrastructure
- Use the `@pytest.mark.smoke` decorator

Example:

```python
import pytest

@pytest.mark.smoke
class TestMyConfig:
    def test_config_valid(self):
        """Config file should be valid YAML."""
        # Test implementation
```

### Marking Slow Tests

Tests that require image pulls or significant time:

```python
import pytest

@pytest.mark.smoke
@pytest.mark.slow
class TestContainerImage:
    def test_image_pullable(self):
        """Verify container image can be pulled."""
        # This might take 30-60 seconds
```

### Integration Tests

Integration tests should:

- Test interactions between components
- Clean up resources after running
- Use fixtures for setup/teardown
- Use the `@pytest.mark.integration` decorator

## Test Dependencies

**Required**:

- pytest
- ansible
- pyyaml

**Optional** (for container tests):

- podman or docker

Install all dependencies:

```bash
pip install pytest ansible pyyaml
```

## Continuous Integration

Tests run automatically on:

- Pull requests
- Pushes to main branch
- Manual workflow dispatch

### GitHub Actions Workflows

- **unit-tests.yml**: Runs unit and smoke tests
- **integration-tests.yml**: Runs integration tests (coming soon)

## Troubleshooting

### Ansible Not Found

```bash
pip install ansible
```

### Container Runtime Not Available

Container tests will be skipped if podman/docker is not available. This is expected on systems without container runtimes.

### Import Errors

Make sure you're running tests from the `tests/` directory:

```bash
cd automation/test-execution/ansible/tests
pytest
```

### YAML Parsing Errors

Ensure your YAML files are properly formatted:

```bash
# Validate YAML files
python -c "import yaml; yaml.safe_load(open('file.yml'))"
```

## Coverage

To run tests with coverage:

```bash
pip install pytest-cov
pytest --cov=../filter_plugins --cov-report=html
```

View coverage report at `htmlcov/index.html`.
