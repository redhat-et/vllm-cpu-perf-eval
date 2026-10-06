# Latency Concurrency Sweep

Measures throughput and end-to-end latency at fixed **max-concurrency** levels
(`request-rate inf`) to map the full operating envelope of an embedding model.

## When to use

```bash
-e "scenario=latency"
```

Or as the first phase of **`scenario=all`** (recommended), which feeds peak
concurrency into [operating-point probes](operating-point.md).

## Concurrency levels

Defined in `benchmark_embedding/tasks/latency.yml`:

**16, 24, 32, 48, 64, 96, 128, 192, 256, 384**

Each level writes
`results/embedding/<model>/<run>/latency/concurrent-<N>.json`.

## Configuration

| Parameter | Default |
| --- | --- |
| Backend | `openai-embeddings` |
| Endpoint | `/v1/embeddings` |
| `num_prompts` | 1000 (`benchmark-tools.yml`) |
| `embedding_random_input_len` | 512 |
| `guidellm_max_seconds` | 300 (hang guard: `timeout 2×` per bench command) |
| Default `kv_cache_space` | 4GiB (group vars; override per model in matrix) |

Readiness: POST `/v1/embeddings` before the sweep starts.

## Metrics

Primary: `request_throughput`, `p99_e2el_ms`, `median_e2el_ms`, `completed`.

When `scenario=all`, Ansible selects **`cal_peak_concurrency`** as the level
with maximum `request_throughput` (skipping runs with `completed=0`).

## Interpretation

- Plot **RPS vs concurrency** — look for the knee where gains flatten
- Plot **P99 vs concurrency** — identify when latency violates SLOs
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
