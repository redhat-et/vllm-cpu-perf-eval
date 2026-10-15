# Operating-Point Probes

Fixed-concurrency probes that characterise embedding serving at three load
regimes across all workload shapes, without a full saturation sweep.

## When to use

- **`scenario=operating_point`** — probes only (~20–45 min per model, across all shapes)
- **`scenario=all`** — same probes after a latency sweep; peak concurrency is
  taken from the chunk shape sweep result with highest `request_throughput`

Playbook default when `scenario` is omitted: **`operating_point`**.

## Workload shapes

Probes run for each of the three input-length shapes:

| Shape | Input tokens | Use case |
| --- | --- | --- |
| `query` | 64 | Semantic search queries, classifiers |
| `chunk` | 512 | RAG document chunks — standard baseline |
| `document` | 1536 | Long-form corpus ingestion |

## Probe design

| Probe | `--max-concurrency` | Characterises |
| --- | --- | --- |
| Sequential | 1 | Minimum latency, no queuing |
| Light load | 8 | Interactive / low-traffic |
| Peak | From sweep or default 32 | Throughput-oriented operating point |

Ansible builds levels as `[1, 8, peak]` with **`unique`** so duplicate probes are
skipped when peak is 1 or 8.

Override peak without a latency sweep:

```bash
-e "scenario=operating_point" -e "op_peak_concurrency=64"
```

## Tooling

```bash
vllm bench serve \
  --backend openai-embeddings \
  --endpoint /v1/embeddings \
  --model <model> \
  --num-prompts 1000 \
  --random-input-len <64|512|1536> \
  --max-concurrency <N>
```

The `benchmark_embedding` role wraps this in a container on the load generator
(or DUT in dut-only mode), with readiness checks on `/v1/embeddings` before probes.

## Outputs

`results/embedding/<model>/<run>/operating_point/<shape>/conc-<N>.json`

Key fields: `request_throughput`, `total_token_throughput`, `mean_e2el_ms`,
`median_e2el_ms`, `p99_e2el_ms`, `completed`, `duration`.

## Interpretation

- **conc=1** — best-case latency per shape; query shape shows lowest absolute latency
- **conc=8** — light parallel load; compare latency penalty across shapes
- **conc=peak** — compare throughput across shapes: query peaks highest RPS, document peaks lowest RPS but reveals attention compute ceiling

## See also

- [Embedding suite overview](embedding-models.md)
- [Latency sweep](latency-concurrent.md)
- [Legacy saturation sweep](baseline-sweep.md)
