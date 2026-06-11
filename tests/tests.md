---
layout: default
title: Tests
---

## Tests Directory

This directory contains all test suites organized by test type.

## Structure

```text
tests/
├── concurrent-load/           # Concurrent load testing (online/server)
│   └── concurrent-load.md     # Test documentation
├── scalability/               # Sweep and throughput tests
│   └── scalability.md         # Test documentation
├── offline-batch/             # Offline batch processing tests
│   └── offline-batch.md       # Test scenarios and documentation
├── resource-contention/       # Resource sharing tests (planned)
└── embedding-models/          # Embedding model performance tests
    ├── embedding-models.md    # Detailed embedding test documentation
    ├── baseline-sweep.md      # Baseline sweep test scenario
    └── latency-concurrent.md  # Latency concurrent test scenario
```

## Test ID Naming Convention

All test cases use a hierarchical naming scheme for easy identification and tracking:

**Format:**
- Concurrent Load: `CONC-{model}-{workload}`
- Scalability: `SCALE-{TYPE}-{model}-{workload}`
- Offline Batch: `OFFLINE-{USE-CASE}-{model}`
- Resource Contention: `CONT-{TYPE}-{model}-{workload}`
- Embedding: `EMB-{TYPE}-{model}-{workload}`

**Components:**

- **Suite Prefix**: `CONC` (Concurrent Load), `SCALE` (Scalability), `OFFLINE` (Offline Batch), `CONT` (Resource Contention), `EMB` (Embedding)
- **Type** (not used for CONC suite): `SWEEP`, `SYNC` (Synchronous), `POISSON`, `BASELINE`, `LATENCY`
- **Use Case** (offline batch): `SUMM` (Summarization), `CLASS` (Classification), `TRANS` (Translation), `ENTITY` (Entity Extraction), `DATAGEN` (Dataset Generation), `ETL` (ETL Pipelines), `CODEGEN` (Code Generation)
- **Model**: Short abbreviation (e.g., `LLAMA32`, `QWEN06`, `GRANITE32`, `GRANITE-EN`, `GRANITE-ML`)
- **Workload**: `CHAT`, `RAG`, `CODE`, `SUMM`, `EMB` (embedding), `EMB512` (512-token embedding)

**Examples:**

- `CONC-LLAMA32-CHAT`: Concurrent Load suite, Llama-3.2-1B, Chat workload
- `SCALE-SWEEP-QWEN06-CODE`: Scalability suite, Sweep test, Qwen3-0.6B, CodeGen workload
- `SCALE-POISSON-GRANITE32-CHAT`: Scalability suite, Poisson distribution, Granite-3.2-2B, Chat
- `OFFLINE-SUMM-LLAMA38`: Offline Batch suite, Summarization use case, Llama-3.1-8B
- `OFFLINE-CLASS-QWEN38`: Offline Batch suite, Classification use case, Qwen3-8B
- `EMB-BASELINE-GRANITE-EN-EMB512`: Embedding suite, Baseline test, Granite English model
- `EMB-LATENCY-GRANITE-ML-EMB512`: Embedding suite, Latency test, Granite Multilingual model

See individual test suite README files for complete test case listings.

## Test Suites

### Test Suite: Concurrent Load

Tests model performance under various concurrent request loads.

- **Concurrency levels**: 1, 2, 4, 8, 16, 32
- **Metrics focus**: P95 latency, TTFT, throughput
- **Goal**: Understand how models scale with parallel requests

### Test Suite: Scalability

Characterizes maximum throughput and performance curves.

- **Test types**: Sweep, Synchronous baseline, Poisson distribution
- **Metrics focus**: Maximum capacity, saturation points
- **Goal**: Determine optimal operating range

### Test Suite: Offline Batch

Tests vLLM batch processing performance using the native Python API (not server mode).

- **Test types**: Use cases (7 scenarios), Technical benchmarks (batch/core/I/O scaling)
- **Metrics focus**: Throughput (req/s, tokens/s), total batch time, processing capacity
- **Goal**: Optimize bulk processing for ETL, dataset generation, document processing
- **Use cases**: Summarization, Classification, Translation, Entity Extraction, Dataset Generation, ETL Pipelines, Code Generation

See [Offline Batch Test Suite](offline-batch/offline-batch.md) for detailed documentation.

### Test Suite: Resource Contention (Planned)

Multi-tenant and resource sharing scenarios.

### Embedding Models

Performance evaluation for embedding models on CPU.

- **Test types**: Baseline (sweep), Latency (concurrent)
- **Metrics focus**: Request throughput (RPS), P95/P99 latency
- **Goal**: Establish baseline performance and optimal concurrency levels
- **Architecture**: Two-node (DUT + Load Generator)

See [Embedding Models Test Suite](embedding-models/embedding-models.md) for detailed documentation.

## Running Tests

### With Docker/Podman Compose

```bash
# Run entire test suite
cd tests/concurrent-load
docker compose up  # or podman-compose up

# Run specific model and scenario
MODEL_NAME=llama-3.2-1b SCENARIO=concurrent-8 docker compose up
```

### With Ansible

```bash
# Run entire test suite
cd automation/test-execution/ansible
ansible-playbook playbooks/run-suite.yml -e "test_suite=concurrent-load"

# Run specific model
ansible-playbook playbooks/run-model.yml \
  -e "model_name=llama-3.2-1b" \
  -e "test_suite=concurrent-load"
```

### With Bash Wrappers

```bash
# Run a test suite
automation/test-execution/bash/run-suite.sh concurrent-load

# Run a single model
automation/test-execution/bash/run-model.sh llama-3.2-1b concurrent-load
```

## Model Matrix

Model definitions are centralized in the `models/` directory (e.g.,
`models/embedding-models/model-matrix.yaml`), which defines which models run
which test scenarios. This allows flexible testing without duplicating
model configurations across test suites.

Example:

```yaml
matrix:
  test_suite: "concurrent-load"
  llm_models:
    - model: "llama-3.2-1b"
      scenarios:
        - concurrent-8
        - concurrent-16
        - concurrent-32
```

## Results

Test results are written to the `results/` directory, organized by:

- Test Suite
- Model
- Host (for distributed testing)

See `docs/methodology/reporting.md` for result formats and analysis.
