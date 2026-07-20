# Test Suite: RAG (Retrieval-Augmented Generation)

Dedicated test suite for characterizing RAG workload performance on CPU.

## Why a Dedicated RAG Suite

CPU inference is **prefill-bound** — TTFT scales roughly linearly with input
token count, making long-context RAG requests disproportionately expensive
compared to GPU. The existing single-point `rag` workload (ISL=7680, OSL=512)
provides one data point. This suite provides three dimensions of analysis:

1. **Context length sensitivity** — how TTFT degrades as retrieved context
   grows from 1K to 8K tokens
2. **Variable distribution impact** — realistic retrieval patterns where
   queries pull different numbers of document chunks
3. **Core count scaling** — how RAG performance changes across CPU
   configurations (16, 32, 64 cores)

## Test Phases

### Phase 1: Context Scaling (Baseline)

Runs three fixed-point RAG workload tiers sequentially to measure TTFT
scaling with input context length:

<!-- markdownlint-disable MD013 -->

| Workload | ISL | OSL | Total | max-model-len | Scenario |
| --- | --- | --- | --- | --- | --- |
| `rag_short` | 1,024 | 256 | 1,280 | 2,048 | 1-2 retrieved chunks |
| `rag_medium` | 4,096 | 384 | 4,480 | 8,192 | 4-8 retrieved chunks |
| `rag_long` | 7,680 | 512 | 8,192 | 8,320 | Full context fill |

<!-- markdownlint-enable MD013 -->

All tiers run with `--no-enable-prefix-caching` (baseline mode).

### Phase 2: Variable Distribution (Baseline)

Runs `rag_var` — a variable-length workload that simulates realistic
retrieval patterns:

- **ISL**: mean=4096, stdev=2048, range 1024-7680
- **OSL**: mean=256, stdev=128, range 64-512
- **ISL:OSL ratio**: ~16:1 (prefill-heavy, typical of RAG)

The high ISL variance (50% of mean) reflects real-world RAG where different
queries pull different numbers of document chunks.

### Phase 3: Prefix Caching (Production)

Runs `rag_var` with `--enable-prefix-caching`.

> **Limitation**: With synthetic text, each request gets unique random tokens
> so prefix caching has no effect. This phase establishes a structural
> baseline. Meaningful caching results will require file-based datasets with
> shared document prefixes (a future enhancement).

## Model Eligibility

Models are automatically filtered by context length:

| Model | Context | rag_short | rag_medium | rag_long | rag_var |
| --- | --- | --- | --- | --- | --- |
| TinyLlama-1.1B | 2,048 | Yes | - | - | - |
| granite-3.2-2b | 4,096 | Yes | - | - | - |
| Llama-3.2-1B | 8,192 | Yes | Yes | Yes | Yes |
| Llama-3.2-3B | 8,192 | Yes | Yes | Yes | Yes |
| Qwen3-0.6B | 8,192 | Yes | Yes | Yes | Yes |
| Qwen2.5-3B | 8,192 | Yes | Yes | Yes | Yes |
| gpt-oss-20b | 128,000 | Yes | Yes | Yes | Yes |

The playbook accepts `model_max_context` to override context length
filtering (default: 8192).

## Concurrency Levels

Default: `[1, 2, 4, 8, 16]`

Lower than the standard `[1, 2, 4, 8, 16, 32]` because:

- At ISL=7680 on CPU, a single prefill may take 2-10 seconds depending
  on model size and core count
- At concurrency=32, you would have 32 x 7680 = 245,760 input tokens
  in-flight simultaneously, creating KV cache memory pressure
- Production RAG systems typically handle 1-16 concurrent users

Override with `-e "rag_concurrency=[1,2,4,8]"`.

## Running Tests

### Quick Start (Single Core Count)

```bash
cd automation/test-execution/ansible

ansible-playbook -i inventory/hosts.yml llm-benchmark-rag-suite.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "requested_cores=32"
```

### Core Count Sweep

```bash
ansible-playbook -i inventory/hosts.yml llm-benchmark-rag-suite.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "rag_core_counts=[16,32,64]"
```

This runs all 3 phases for each core count (up to 4 core counts
supported).

### Skip Individual Phases

```bash
# Context scaling only (skip variable + caching)
ansible-playbook -i inventory/hosts.yml llm-benchmark-rag-suite.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "requested_cores=32" \
  -e "skip_variable=true" \
  -e "skip_caching=true"

# Variable distribution only
ansible-playbook -i inventory/hosts.yml llm-benchmark-rag-suite.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "requested_cores=32" \
  -e "skip_context_scaling=true" \
  -e "skip_caching=true"
```

### Using the Concurrent Load Pipeline

The `rag` and `rag_var` workloads also work through the standard
concurrent load pipeline:

```bash
ansible-playbook -i inventory/hosts.yml \
  llm-benchmark-concurrent-load.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "base_workload=rag" \
  -e "requested_cores=32"
```

This runs: Phase 1 (`rag`), Phase 2 (`rag_var`), Phase 3 (`rag_var`
with prefix caching).

## CPU-Specific Insights

### TTFT Scaling

On CPU, TTFT scales roughly linearly with input token count because
prefill is compute-bound on the attention computation. The context
scaling phase (rag_short -> rag_medium -> rag_long) directly measures
this relationship. Expect:

- `rag_medium` TTFT to be ~4x `rag_short` TTFT
- `rag_long` TTFT to be ~7.5x `rag_short` TTFT

Significant deviation suggests memory bandwidth saturation or
NUMA effects.

### KV Cache Memory Pressure

Longer contexts consume more KV cache memory per concurrent request.
At `rag_long` (8192 tokens) with concurrency=16:

- Small models (1B): ~11 GiB KV cache
- Medium models (3B): ~36 GiB KV cache

Monitor for OOM or throughput degradation at higher concurrency.

### Core Count Scaling

Use `-e "rag_core_counts=[16,32,64]"` to measure:

- Whether doubling cores halves TTFT (ideal linear scaling)
- The point of diminishing returns (memory bandwidth bound)
- NUMA boundary effects (e.g., 32 cores on 1 socket vs 2)

## Key Metrics

| Metric | Phase | What It Measures |
| --- | --- | --- |
| TTFT (P50/P95) | Phase 1 | Context length sensitivity |
| TTFT scaling ratio | Phase 1 | Linearity of TTFT vs ISL |
| Throughput (req/s) | All | Overall serving capacity |
| P95 E2E Latency | Phase 2 | Variable workload tail latency |
| ITL (P95) | All | Decode performance under load |

## Results

Results follow the standard structure:

```text
results/llm/<model>/<workload>-<timestamp>/<core-config>/
  benchmarks.json     # GuideLLM raw results
  benchmarks.csv      # Tabular results
  test-metadata.json  # Test configuration and metadata
```

View results using the Streamlit dashboard. See
[Dashboards Quick Start](../../docs/dashboards-quickstart.md).

## Known Limitations

1. **No prefix sharing simulation** — GuideLLM generates unique synthetic
   text per request. Real RAG workloads share document prefixes across
   queries (e.g., same retrieved document for different questions).
   Prefix caching tests (Phase 3) are structural only until file-based
   datasets are supported.

2. **No batch heterogeneity testing** — Real RAG systems often batch
   requests with very different context lengths (one query retrieves 1
   chunk, another retrieves 8). The current suite tests each tier
   independently, not mixed in a single batch.

3. **Core count sweep limit** — The playbook supports up to 4 core
   counts per run due to Ansible's `import_playbook` not supporting
   loops. For more core counts, run the playbook multiple times with
   different `-e "requested_cores=N"` values.

## Related Documentation

- [Concurrent Load Testing](../concurrent-load/concurrent-load.md)
- [Testing Methodology](../../docs/methodology/overview.md)
- [3-Phase Testing](../../docs/methodology/testing-phases.md)
- [Model Definitions](../../models/models.md)
