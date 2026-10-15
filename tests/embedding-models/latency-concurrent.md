# Latency Concurrency Sweep

Measures throughput and end-to-end latency at fixed **max-concurrency** levels
(`request-rate inf`) across three input-length shapes to map the full operating
envelope of an embedding model.

## When to use

```bash
-e "scenario=latency"
```

Or as the first phase of **`scenario=all`** (recommended), which feeds peak
concurrency into [operating-point probes](operating-point.md).

## Workload shapes

Each sweep runs all three shapes across the full concurrency range:

| Shape | Input tokens | Use case |
| --- | --- | --- |
| `query` | 64 | Semantic search queries, classifiers — latency-sensitive |
| `chunk` | 512 | RAG document chunks — standard throughput baseline |
| `document` | 1536 | Long-form corpus ingestion — compute/memory saturation |

Override shapes with a one-element list to run a single custom length:
```bash
-e "embedding_workload_shapes=[{'name':'custom','input_len':256}]"
```

Peak concurrency detection (`scenario=all`) uses the **chunk** shape results as the
canonical reference. Override with `-e "embedding_peak_shape=query"` if needed.

## Concurrency levels

Defined in `benchmark_embedding/tasks/latency.yml`:

**16, 24, 32, 48, 64, 96, 128, 192, 256, 384**

Results are written per shape:
`results/embedding/<model>/<run>/latency/<shape>/concurrent-<N>.json`

## Configuration

| Parameter | Default |
| --- | --- |
| Backend | `openai-embeddings` |
| Endpoint | `/v1/embeddings` |
| `num_prompts` | 1000 (`benchmark-tools.yml`) |
| `embedding_workload_shapes` | query/64, chunk/512, document/1536 |
| `embedding_peak_shape` | `chunk` |
| `guidellm_max_seconds` | 300 (hang guard: `timeout 2×` per bench command) |
| Default `kv_cache_space` | 4GiB (group vars; override per model in matrix) |

Readiness: POST `/v1/embeddings` before the sweep starts (warmup uses chunk shape).

## Metrics

Primary: `request_throughput`, `p99_e2el_ms`, `median_e2el_ms`, `completed`.

When `scenario=all`, Ansible selects **`cal_peak_concurrency`** as the level with
maximum `request_throughput` in the chunk shape results (skipping `completed=0` runs).

## Interpretation

- Plot **RPS vs concurrency per shape** — shorter inputs peak at higher concurrency
- Plot **P99 vs concurrency per shape** — query shape shows lowest latency; document shape shows bandwidth ceiling
- The `document/384` data point is the effective offline-batch throughput upper bound
- Compare models and core counts on the Embedding Metrics **Concurrent Load** tab

## Example

```bash
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=ibm-granite/granite-embedding-278m-multilingual" \
  -e "scenario=latency" \
  -e "requested_cores=32"
```

## See also

- [Embedding suite overview](embedding-models.md)
- [Operating-point probes](operating-point.md)
- [Embedding Models Guide](../../docs/embedding-models.md)
