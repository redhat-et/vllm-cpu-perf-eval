
# Tests Directory

> **For the complete test suite reference**, see the
> [Test Suites Overview](../docs/test-suites.md) — it includes cpueval
> commands, a suite selection guide, status table, and links to all detailed
> methodology docs below.

This directory contains per-suite methodology and configuration documentation.
# Test Suites

| Suite | Documentation | cpueval suite |
| --- | --- | --- |
| Concurrent Load | [concurrent-load.md](concurrent-load/concurrent-load.md) | `concurrent-load` |
| RHAIIS Sweep | [rhaiis-testing.md](concurrent-load/rhaiis-testing.md) | `rhaiis-sweep` |
| Scalability | [scalability.md](scalability/scalability.md) | Ansible |
| Offline Batch | [offline-batch.md](offline-batch/offline-batch.md) | `offline-batch` |
| Embedding | [embedding-models.md](embedding-models/embedding-models.md) | `embedding` |
| Audio | [audio-models/](audio-models/) | `audio` |
| CVE Scanning / VLoc Bench | [cve-scanning.md](cve-scanning/cve-scanning.md) | Ansible |
| Resource Contention | [resource-contention.md](resource-contention/resource-contention.md) | Planned |

Sub-pages for embedding: [baseline-sweep.md](embedding-models/baseline-sweep.md),
[latency-concurrent.md](embedding-models/latency-concurrent.md).
# Test ID Naming Convention

All test cases use a hierarchical naming scheme:

- **Concurrent Load**: `CONC-{model}-{workload}`
- **Scalability**: `SCALE-{TYPE}-{model}-{workload}`
- **Offline Batch**: `OFFLINE-{USE-CASE}-{model}`
- **Embedding**: `EMB-{TYPE}-{model}-{workload}`

**Components:**

- **Suite Prefix**: `CONC` (Concurrent Load), `SCALE` (Scalability), `OFFLINE` (Offline Batch), `CVE` (CVE Scanning), `CONT` (Resource Contention), `EMB` (Embedding)
- **Type** (not used for CONC suite): `SWEEP`, `SYNC` (Synchronous), `POISSON`, `BASELINE`, `LATENCY`
- **Use Case** (offline batch): `SUMM` (Summarization), `CLASS` (Classification), `TRANS` (Translation), `ENTITY` (Entity Extraction), `DATAGEN` (Dataset Generation), `ETL` (ETL Pipelines), `CODEGEN` (Code Generation), `LONGSUM` (Long-Doc Summarization), `RAG` (Batch RAG), `PREFIX` (Shared-Prefix), `LABEL` (Ultra-Short Labeling)
- **Model**: Short abbreviation (e.g., `LLAMA32`, `QWEN06`, `GRANITE32`, `GRANITE-EN`, `GRANITE-ML`)
- **Workload**: `CHAT`, `RAG`, `CODE`, `SUMM`, `EMB` (embedding), `EMB512` (512-token embedding)

**Examples:**

- `CONC-LLAMA32-CHAT`: Concurrent Load suite, Llama-3.2-1B, Chat workload
- `SCALE-SWEEP-QWEN06-CODE`: Scalability suite, Sweep test, Qwen3-0.6B, CodeGen workload
- `SCALE-POISSON-GRANITE32-CHAT`: Scalability suite, Poisson distribution, Granite-3.2-2B, Chat
- `OFFLINE-SUMM-LLAMA38`: Offline Batch suite, Summarization use case, Llama-3.1-8B
- `OFFLINE-CLASS-QWEN38`: Offline Batch suite, Classification use case, Qwen3-8B
- `CVE-VLOC-GRANITE1B`: CVE Scanning suite, VLoc localization, Granite-4.0-1B
- `CVE-CAP-ANTARES1B`: CVE Scanning suite, Capacity proxy, Antares-1B
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

- **Test types**: Use cases (11 scenarios), Technical benchmarks (batch/core/I/O scaling, KV-cache capacity, context scaling)
- **Metrics focus**: Throughput (req/s, tokens/s), total batch time, processing capacity
- **Goal**: Optimize bulk processing for ETL, dataset generation, document processing
- **Use cases**: Summarization, Classification, Translation, Entity Extraction, Dataset Generation, ETL Pipelines, Code Generation, Long-Document Summarization, Batch RAG, Shared-Prefix/Template Batch, Ultra-Short Labeling

See [Offline Batch Test Suite](offline-batch/offline-batch.md) for detailed documentation.

### Test Suite: CVE Scanning / VLoc Bench

Evaluates LLM vulnerability localization using the Cisco VLoc Bench harness.

- **Online track**: VLoc Bench agent loop (Docker sandbox + tool calls) against vLLM-served models
- **Offline track**: `vllm bench throughput` capacity proxy with representative I/O shapes
- **Metrics focus**: File F1, Precision, Recall (online); tok/s, items/hr (offline)
- **Model families**: Granite-4.0 (baseline), Qwen3.5-9B, Antares (specialized)
- **Goal**: Evaluate vulnerability localization quality and model capacity on CPU

See [CVE Scanning Test Suite](cve-scanning/cve-scanning.md) for detailed documentation.

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

```bash
# Recommended: cpueval CLI
./cpueval --suite <suite-name> [options]

# Ansible
cd automation/test-execution/ansible
ansible-playbook llm-benchmark-auto.yml -e "test_model=<model>"

# Bash wrappers (from automation/test-execution/)
cd ..
./bash/run-suite.sh concurrent-load
```

See [cpueval CLI](../docs/cpueval-cli.md) and
[Ansible Test Execution](../docs/ansible/test-execution.md) for details.

## Results

Test results are written to `results/`, organized by suite, model, and host.
See [Reporting Guide](../docs/methodology/reporting.md).
