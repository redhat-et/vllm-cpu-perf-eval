
# Test Suites

This page is the central reference for all benchmark suites in the
vLLM CPU Performance Evaluation framework. Use it to find which suite to
run, how to run it, and where to read the detailed methodology.

## Quick Reference

| Suite | Type | Status | cpueval command | Detailed docs |
| --- | --- | --- | --- | --- |
| Concurrent Load | Matrix | Validated | `cpueval run --suite concurrent-load` | [Concurrent Load](../tests/concurrent-load/concurrent-load.md) |
| RHAIIS Sweep | Matrix | Validated | `cpueval run --suite rhaiis-sweep` | [RHAIIS Testing](../tests/concurrent-load/rhaiis-testing.md) |
| Scalability | Manual/Ansible | WIP | Ansible playbooks | [Scalability](../tests/scalability/scalability.md) |
| Offline Batch | Matrix | Validated | `cpueval run --suite offline-batch` | [Offline Batch](../tests/offline-batch/offline-batch.md) |
| Embedding | Matrix | Validated | `cpueval run --suite embedding` | [Embedding Models](../tests/embedding-models/embedding-models.md) |
| Audio | Matrix | Validated | `cpueval run --suite audio` | [Audio Models](../tests/audio-models/) |
| Chat Smoke | Single-shot | Validated | `cpueval run --suite chat-smoke --model <model>` | [cpueval CLI](cpueval-cli.md) |
| Resource Contention | Planned | Planned | — | [Resource Contention](../tests/resource-contention/resource-contention.md) |

**Status legend:** Validated = production-ready, WIP = in progress, Planned = not yet implemented.

## How to Choose a Suite

| Your goal | Recommended suite | Example command |
| --- | --- | --- |
| LLM serving under concurrency | `concurrent-load` | `./cpueval run --suite concurrent-load` |
| RHAIIS model matrix sweep | `rhaiis-sweep` | `./cpueval run --suite rhaiis-sweep` |
| Bulk/offline document processing | `offline-batch` | `./cpueval run --suite offline-batch` |
| Embedding throughput and latency | `embedding` | `./cpueval run --suite embedding` |
| Audio transcription (Whisper) | `audio` | `./cpueval run --suite audio --scenario quick-test` |
| Maximum throughput curves | `scalability` | Ansible playbooks (see [Scalability](../tests/scalability/scalability.md)) |
| Quick sanity check | `chat-smoke` or `health` | `./cpueval run --suite chat-smoke --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8` |

## cpueval Workflow

A typical session looks like this:

```bash
# 1. List available suites
./cpueval list

# 2. Inspect a suite's defaults before running
./cpueval show rhaiis-sweep

# 3. Verify your environment
./cpueval doctor

# 4. Preview the underlying command (no execution)
./cpueval run --suite chat-smoke \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8 --dry-run

# 5. Run the benchmark
./cpueval run --suite chat-smoke \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8

# 6. View results
./cpueval results --last
```

### `./cpueval list` output

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                      ┃ Type         ┃ Runner     ┃ Description          ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ embedding                 │ Matrix       │ script     │ Embedding model      │
│                           │              │            │ performance -        │
│                           │              │            │ baseline + latency   │
│ concurrent-load           │ Matrix       │ script     │ Upstream LLM         │
│                           │              │            │ concurrent load      │
│ rhaiis-sweep              │ Matrix       │ script     │ RHAIIS model         │
│                           │              │            │ concurrent load      │
│ offline-batch             │ Matrix       │ script     │ Offline batch        │
│                           │              │            │ processing           │
│ audio                     │ Matrix       │ script     │ Audio model          │
│                           │              │            │ benchmarking         │
│ chat-smoke                │ Single       │ ansible    │ Quick LLM chat test  │
│ health                    │ Single       │ ansible    │ Health check         │
└───────────────────────────┴──────────────┴────────────┴──────────────────────┘

Legend: Matrix = full test matrix by default, Single = requires --model
```

### `./cpueval show rhaiis-sweep` output

```text
Suite: rhaiis-sweep

Description: RHAIIS model concurrent load sweep - full test matrix by default
Runner: script
Type: Matrix suite (runs full test matrix by default)

Default Parameters:
  models: all
  cores: 8,16,32
  workloads: chat,code,summarization,rag
  phase: 1

This suite runs the full matrix by default.
Use CLI flags to narrow the scope:
  --models <preset|list> to select specific models
  --cores <list> to select specific core counts
  --workloads <list> to select specific workloads
```

### `./cpueval doctor` output

```text
cpueval system health check

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                ┃ Status       ┃ Details                                ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ansible-playbook     │ ✓            │ unknown                                │
│ Ansible collections  │ ✗            │ containers.podman collection not found │
│ Inventory file       │ ✓            │ .../ansible/inventory/hosts.yml        │
│ Environment vars     │ ✗            │ Missing: DUT_HOSTNAME, LOADGEN_HOSTNAME│
└──────────────────────┴──────────────┴────────────────────────────────────────┘

✗ Some checks failed

Tip: Set required environment variables:
  export DUT_HOSTNAME=<dut-host>
  export LOADGEN_HOSTNAME=<loadgen-host>
```

### `./cpueval run --dry-run` output

Shows the underlying Ansible command without executing:

```text
ansible-playbook -i .../inventory/hosts.yml .../llm-benchmark-auto.yml \
  -e workload_type=chat \
  -e test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  -e requested_cores=8
```

### `./cpueval results --last` output

```text
Results: results/llm/Qwen__Qwen2.5-0.5B-Instruct/chat-20260729-165311/32cores-numa2-tp1

┌───────────┬────────────────────────────┐
│ Model     │ Qwen/Qwen2.5-0.5B-Instruct │
│ Workload  │ chat                       │
│ Timestamp │ 2026-07-29T17:26:30+01:00  │
│ Cores     │ 32                         │
└───────────┴────────────────────────────┘

┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Concurrency ┃ Req/s ┃   Tok/s ┃ TTFT (ms) ┃ TPOT (ms) ┃ Requests ┃
┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ 1           │  0.10 │  106.37 │     53.48 │     19.34 │    26/26 │
│ 8           │  0.67 │  710.55 │    142.20 │     23.14 │  168/168 │
│ 32          │  1.47 │ 1585.99 │    199.50 │     41.36 │  384/384 │
└─────────────┴───────┴─────────┴───────────┴───────────┴──────────┘
```

## cpueval CLI Suites

The recommended entry point is the [cpueval CLI](cpueval-cli.md). Suites are
defined in `automation/cli/src/cpueval/suites/`.

### Matrix Suites (run full test matrix by default)

These suites run a complete matrix of models, cores, and workloads/scenarios
without requiring `--model`.

| Suite | Default matrix | Description |
| --- | --- | --- |
| `rhaiis-sweep` | 5 models × 3 cores × 4 workloads | RHAIIS quantized model concurrent load sweep |
| `concurrent-load` | all models × 3 cores × 4 workloads (use `--models`/`--workload` to narrow) | Upstream LLM concurrent load sweep |
| `embedding` | 5 models × 3 cores × 2 scenarios | Embedding model performance matrix |
| `offline-batch` | 11 use-cases × 3 runs | Offline batch processing |
| `audio` | all models × `transcription-throughput` × 32 cores (override with `--scenario`, `--cores`) | Audio model benchmarking (Whisper ASR) |

```bash
# Run full matrices
./cpueval run --suite rhaiis-sweep
./cpueval run --suite concurrent-load
./cpueval run --suite embedding
./cpueval run --suite offline-batch
./cpueval run --suite audio

# Narrow scope with overrides
./cpueval run --suite rhaiis-sweep --models tiny --cores 8
./cpueval run --suite concurrent-load --models tiny --workload chat --cores 32
./cpueval run --suite embedding --models quick --cores 4
```

### Single-Shot Suites (require `--model`)

| Suite | Description |
| --- | --- |
| `chat-smoke` | Quick auto-configured LLM chat test |
| `setup-platform` | Platform setup and configuration |
| `health` | Health check for DUT and load generator |

```bash
./cpueval run --suite chat-smoke \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8
```

List all suites: `./cpueval list` · Show suite details: `./cpueval show <suite>`

## Test Suite Documentation

Each suite has detailed methodology, metrics, and configuration in the
`tests/` directory.

### LLM Online Serving

- **[Concurrent Load](../tests/concurrent-load/concurrent-load.md)** —
  P95 latency and throughput under increasing concurrency (1–32 streams).
  Implements the [3-phase testing methodology](methodology/testing-phases.md).
- **[RHAIIS Testing](../tests/concurrent-load/rhaiis-testing.md)** —
  RHAIIS quantized model testing, NUMA configuration, and known issues.
- **[Scalability](../tests/scalability/scalability.md)** — Maximum throughput,
  load-latency curves, and sweep testing (WIP).

### Offline & Batch Processing

- **[Offline Batch](../tests/offline-batch/offline-batch.md)** — Bulk document
  processing via the vLLM Python API. 11 use-case scenarios (summarization,
  classification, translation, ETL, etc.).
- [Offline Batch Methodology](methodology/offline-batch.md) — Detailed usage
  and metrics interpretation.

### Embedding Models

- **[Embedding Models](../tests/embedding-models/embedding-models.md)** —
  Comprehensive embedding performance testing.
- **[Baseline Sweep](../tests/embedding-models/baseline-sweep.md)** — Throughput
  scaling across concurrency levels.
- **[Latency Concurrent](../tests/embedding-models/latency-concurrent.md)** —
  Latency under concurrent load.
- [Embedding Models Guide](embedding-models.md) — Setup, RHAIIS images, and
  troubleshooting.

### Audio Models

- **[Audio Models](../tests/audio-models/)** — Whisper ASR throughput, latency,
  duration scaling, format comparison, and stress testing.
- [Audio Benchmarking Guide](audio-benchmarking.md) — Comprehensive guide with
  troubleshooting.

### Planned

- **[Resource Contention](../tests/resource-contention/resource-contention.md)**
  — Multi-tenant and resource sharing scenarios (planned).

## Test ID Naming Convention

All test cases use a hierarchical naming scheme:

| Prefix | Suite |
| --- | --- |
| `CONC` | Concurrent Load |
| `SCALE` | Scalability |
| `OFFLINE` | Offline Batch |
| `CONT` | Resource Contention |
| `EMB` | Embedding |

**Examples:**

- `CONC-LLAMA32-CHAT` — Concurrent load, Llama-3.2-1B, chat workload
- `OFFLINE-SUMM-LLAMA38` — Offline batch, summarization, Llama-3.1-8B
- `EMB-BASELINE-GRANITE-EN-EMB512` — Embedding baseline, Granite English

See individual suite docs for complete test case listings.

## Running Tests

### Recommended: cpueval CLI

```bash
./cpueval run --suite <suite-name> [options]
```

See [cpueval CLI Guide](cpueval-cli.md) for full options, CPU pinning, and
profiles.

### Ansible Playbooks

```bash
cd automation/test-execution/ansible
ansible-playbook llm-benchmark-auto.yml -e "test_model=<model>"
```

See [Ansible Test Execution](ansible/test-execution.md).

### Bash Wrappers

```bash
automation/test-execution/bash/run-suite.sh concurrent-load
automation/test-execution/bash/run-model.sh llama-3.2-1b concurrent-load
```

See [Scripts Reference](scripts-reference.md).

## Model Matrix

Model-to-suite mappings are centralized in `models/`:

- `models/llm-models/model-matrix.yaml` — LLM models and scenarios
- `models/embedding-models/model-matrix.yaml` — Embedding models
- `models/audio-models/model-matrix.yaml` — Audio models

See the [Model Catalog](../models/models.md) for supported models and
selection rationale.

## Results

Test results are written to `results/`, organized by suite, model, and host.

- [Reporting Guide](methodology/reporting.md) — Result formats and analysis
- [Dashboards Quickstart](dashboards-quickstart.md) — Streamlit visualization
- [MLflow Integration](mlflow.md) — Experiment tracking
- [Terminal Results Viewer](terminal-results-viewer.md) — Quick CLI output
