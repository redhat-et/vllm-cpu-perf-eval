# vllm-cpu-perf-eval

Performance evaluation guide for vLLM on CPU platforms.

---

## Development Setup

### Pre-commit Hooks

This repository uses [pre-commit](https://pre-commit.com/) to ensure code
quality and consistency. Pre-commit hooks run automatically before each
commit to check for common issues.

#### Installation

1. Install pre-commit:

   ```bash
   pip install pre-commit
   ```

2. Install the git hook scripts:

   ```bash
   pre-commit install
   ```

   To also enable commit message linting:

   ```bash
   pre-commit install --hook-type commit-msg
   ```

#### Running Pre-commit Manually

To run all hooks on all files:

```bash
pre-commit run --all-files
```

To run hooks only on staged files:

```bash
pre-commit run
```

To run a specific hook:

```bash
pre-commit run <hook-id> --all-files
```

#### Updating Hooks

To update hooks to their latest versions:

```bash
pre-commit autoupdate
```
