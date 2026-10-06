# Operating-Point Probes

Fixed-concurrency probes that characterise embedding serving at three load
regimes without a full saturation sweep.

## When to use

- **`scenario=operating_point`** — probes only (~15–25 min per model)
- **`scenario=all`** — same probes after a latency sweep; peak concurrency is
  taken from the sweep result with highest `request_throughput`

Playbook default when `scenario` is omitted: **`operating_point`**.

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
  --random-input-len 512 \
  --max-concurrency <N>
```

The `benchmark_embedding` role wraps this in a container on the load generator
(or DUT in dut-only mode), with readiness checks on `/v1/embeddings` before probes.

## Outputs

`results/embedding/<model>/<run>/operating_point/conc-<N>.json`

Key fields: `request_throughput`, `total_token_throughput`, `mean_e2el_ms`,
`median_e2el_ms`, `p99_e2el_ms`, `completed`, `duration`.

## Interpretation

- **conc=1** — best-case latency baseline for SLO planning
- **conc=8** — light parallel load; latency should remain modest
- **conc=peak** — highest sustained RPS in the probe set; compare across core counts
  and models on the Embedding Metrics dashboard

## See also

- [Embedding suite overview](embedding-models.md)
- [Latency sweep](latency-concurrent.md)
- [Legacy saturation sweep](baseline-sweep.md)
