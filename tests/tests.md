---
layout: default
title: Tests
---

# Tests Directory

> **For the complete test suite reference**, see the
> [Test Suites Overview](../docs/test-suites.md) — it includes cpueval
> commands, a suite selection guide, status table, and links to all detailed
> methodology docs below.

This directory contains per-suite methodology and configuration documentation.

## Test Suites

| Suite | Documentation | cpueval suite |
| --- | --- | --- |
| Concurrent Load | [concurrent-load.md](concurrent-load/concurrent-load.md) | `concurrent-load` |
| RHAIIS Sweep | [rhaiis-testing.md](concurrent-load/rhaiis-testing.md) | `rhaiis-sweep` |
| Scalability | [scalability.md](scalability/scalability.md) | Ansible |
| Offline Batch | [offline-batch.md](offline-batch/offline-batch.md) | `offline-batch` |
| Embedding | [embedding-models.md](embedding-models/embedding-models.md) | `embedding` |
| Audio | [audio-models/](audio-models/) | `audio` |
| Resource Contention | [resource-contention.md](resource-contention/resource-contention.md) | Planned |

Sub-pages for embedding: [baseline-sweep.md](embedding-models/baseline-sweep.md),
[latency-concurrent.md](embedding-models/latency-concurrent.md).

## Test ID Naming Convention

All test cases use a hierarchical naming scheme:

- **Concurrent Load**: `CONC-{model}-{workload}`
- **Scalability**: `SCALE-{TYPE}-{model}-{workload}`
- **Offline Batch**: `OFFLINE-{USE-CASE}-{model}`
- **Embedding**: `EMB-{TYPE}-{model}-{workload}`

See the [Test Suites Overview](../docs/test-suites.md#test-id-naming-convention)
for examples and the full prefix table.

## Running Tests

```bash
# Recommended: cpueval CLI
./cpueval run --suite <suite-name> [options]

# Ansible
cd automation/test-execution/ansible
ansible-playbook llm-benchmark-auto.yml -e "test_model=<model>"

# Bash wrappers
automation/test-execution/bash/run-suite.sh concurrent-load
```

See [cpueval CLI](../docs/cpueval-cli.md) and
[Ansible Test Execution](../docs/ansible/test-execution.md) for details.

## Results

Test results are written to `results/`, organized by suite, model, and host.
See [Reporting Guide](../docs/methodology/reporting.md).
