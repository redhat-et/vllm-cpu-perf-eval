# Tests Directory

This directory contains all test scenarios organized by testing phase.

## Structure

```text
tests/
├── phase-1-concurrent/         # Concurrent load testing
│   ├── compose.yaml           # Docker/Podman compose file
│   ├── model-matrix.yaml      # Which models run which scenarios
│   └── test-scenarios/        # Test scenario definitions
│       ├── concurrent-8.yaml
│       ├── concurrent-16.yaml
│       └── ...
├── phase-2-scalability/       # Sweep and throughput tests
│   ├── compose.yaml
│   ├── model-matrix.yaml
│   └── test-scenarios/
│       ├── sweep.yaml
│       ├── synchronous.yaml
│       └── ...
├── phase-3-resource-contention/  # Future: Resource sharing tests
└── embedding-models/          # Embedding model performance tests
    ├── README.md              # Detailed embedding test documentation
    ├── scenarios/             # Baseline and latency test scenarios
    └── scripts/               # Bash scripts for test execution
```

## Test ID Naming Convention

All test cases use a hierarchical naming scheme for easy identification and tracking:

**Format:** `P{phase}-{TYPE}-{model}-{workload}`

**Components:**

- **Phase**: `P1` (Concurrent), `P2` (Scalability), `P3` (Resource Contention), `EMB` (Embedding)
- **Type**: `CONC` (Concurrent), `SWEEP`, `SYNC` (Synchronous), `POISSON`, `BASELINE`, `LATENCY`
- **Model**: Short abbreviation (e.g., `LLAMA32`, `QWEN06`, `GRANITE32`, `GRANITE-EN`, `GRANITE-ML`)
- **Workload**: `CHAT`, `RAG`, `CODE`, `SUMM`, `EMB512` (512-token embedding)

**Examples:**

- `P1-CONC-LLAMA32-CHAT`: Phase 1, Concurrent, Llama-3.2-1B, Chat workload
- `P2-SWEEP-QWEN06-CODE`: Phase 2, Sweep test, Qwen3-0.6B, CodeGen workload
- `P2-POISSON-GRANITE32-CHAT`: Phase 2, Poisson distribution, Granite-3.2-2B, Chat
- `EMB-BASELINE-GRANITE-EN-EMB512`: Embedding, Baseline test, Granite English model
- `EMB-LATENCY-GRANITE-ML-EMB512`: Embedding, Latency test, Granite Multilingual model

See individual phase README files for complete test case listings.

## Test Phases

### Phase 1: Concurrent Load Testing

Tests model performance under various concurrent request loads.

- **Concurrency levels**: 8, 16, 32, 64, 96, 128
- **Metrics focus**: P95 latency, TTFT, throughput
- **Goal**: Understand how models scale with parallel requests

### Phase 2: Scalability Testing

Characterizes maximum throughput and performance curves.

- **Test types**: Sweep, Synchronous baseline, Poisson distribution
- **Metrics focus**: Maximum capacity, saturation points
- **Goal**: Determine optimal operating range

### Phase 3: Resource Contention (Planned)

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
# Run entire phase
cd tests/phase-1-concurrent
docker compose up  # or podman-compose up

# Run specific model and scenario
MODEL_NAME=llama-3.2-1b SCENARIO=concurrent-8 docker compose up
```

### With Ansible

```bash
# Run entire phase
cd automation/test-execution/ansible
ansible-playbook playbooks/run-phase.yml -e "phase=phase-1-concurrent"

# Run specific model
ansible-playbook playbooks/run-model.yml \
  -e "model_name=llama-3.2-1b" \
  -e "phase=phase-1-concurrent"
```

### With Bash Wrappers

```bash
# Run a phase
automation/test-execution/bash/run-phase.sh phase-1-concurrent

# Run a single model
automation/test-execution/bash/run-model.sh llama-3.2-1b phase-1-concurrent
```

## Model Matrix

Model definitions are centralized in the `models/` directory (e.g.,
`models/embedding-models/model-matrix.yaml`), which defines which models run
which test scenarios. This allows flexible testing without duplicating
model configurations across test phases.

Example:

```yaml
matrix:
  phase: "phase-1"
  llm_models:
    - model: "llama-3.2-1b"
      scenarios:
        - concurrent-8
        - concurrent-16
        - concurrent-32
```

## Results

Test results are written to the `results/` directory, organized by:

- Phase
- Model
- Host (for distributed testing)

See `docs/methodology/reporting.md` for result formats and analysis.
