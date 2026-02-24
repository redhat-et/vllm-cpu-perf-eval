# Tests Directory

This directory contains all test suites organized by test type.

## Structure

```text
tests/
├── concurrent-load/           # Concurrent load testing
│   ├── compose.yaml           # Docker/Podman compose file
│   ├── model-matrix.yaml      # Which models run which scenarios
│   └── test-scenarios/        # Test scenario definitions
│       ├── concurrent-8.yaml
│       ├── concurrent-16.yaml
│       └── ...
├── scalability/               # Sweep and throughput tests
│   ├── compose.yaml
│   ├── model-matrix.yaml
│   └── test-scenarios/
│       ├── sweep.yaml
│       ├── synchronous.yaml
│       └── ...
├── resource-contention/       # Resource sharing tests
└── embedding-models/          # Embedding model performance tests
    ├── README.md              # Detailed embedding test documentation
    ├── scenarios/             # Baseline and latency test scenarios
    └── scripts/               # Bash scripts for test execution
```

## Test ID Naming Convention

All test cases use a hierarchical naming scheme for easy identification and tracking:

**Format:**
- Concurrent Load: `CONC-{model}-{workload}`
- Scalability: `SCALE-{TYPE}-{model}-{workload}`
- Resource Contention: `CONT-{TYPE}-{model}-{workload}`
- Embedding: `EMB-{TYPE}-{model}-{workload}`

**Components:**

- **Suite Prefix**: `CONC` (Concurrent Load), `SCALE` (Scalability), `CONT` (Resource Contention), `EMB` (Embedding)
- **Type** (not used for CONC suite): `SWEEP`, `SYNC` (Synchronous), `POISSON`, `BASELINE`, `LATENCY`
- **Model**: Short abbreviation (e.g., `LLAMA32`, `QWEN06`, `GRANITE32`, `GRANITE-EN`, `GRANITE-ML`)
- **Workload**: `CHAT`, `RAG`, `CODE`, `SUMM`, `EMB` (embedding), `EMB512` (512-token embedding)

**Examples:**

- `CONC-LLAMA32-CHAT`: Concurrent Load suite, Llama-3.2-1B, Chat workload
- `SCALE-SWEEP-QWEN06-CODE`: Scalability suite, Sweep test, Qwen3-0.6B, CodeGen workload
- `SCALE-POISSON-GRANITE32-CHAT`: Scalability suite, Poisson distribution, Granite-3.2-2B, Chat
- `EMB-BASELINE-GRANITE-EN-EMB512`: Embedding suite, Baseline test, Granite English model
- `EMB-LATENCY-GRANITE-ML-EMB512`: Embedding suite, Latency test, Granite Multilingual model

See individual test suite README files for complete test case listings.

## Test Suites

### Test Suite: Concurrent Load

Tests model performance under various concurrent request loads.

- **Concurrency levels**: 8, 16, 32, 64, 96, 128
- **Metrics focus**: P95 latency, TTFT, throughput
- **Goal**: Understand how models scale with parallel requests

### Test Suite: Scalability

Characterizes maximum throughput and performance curves.

- **Test types**: Sweep, Synchronous baseline, Poisson distribution
- **Metrics focus**: Maximum capacity, saturation points
- **Goal**: Determine optimal operating range

### Test Suite: Resource Contention (Planned)

Multi-tenant and resource sharing scenarios.

### Embedding Models

Performance evaluation for embedding models on CPU.

- **Test types**: Baseline (sweep), Latency (concurrent)
- **Metrics focus**: Request throughput (RPS), P95/P99 latency
- **Goal**: Establish baseline performance and optimal concurrency levels
- **Architecture**: Two-node (DUT + Load Generator)

See [embedding-models/embedding-models.md](embedding-models/embedding-models.md) for detailed documentation.

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
