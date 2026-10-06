# Legacy Baseline Saturation Sweep (Deprecated)

!!! warning "Deprecated"
    New runs should use **[operating-point probes](operating-point.md)** and/or the
    **[latency concurrency sweep](latency-concurrent.md)** via `scenario=operating_point`,
    `scenario=latency`, or `scenario=all`.

    The load-fraction sweep (`request-rate inf`, then 25% / 50% / 75% of max) is
    **no longer produced** by `embedding-benchmark.yml`.

## Historical behaviour

Older automation and `run-baseline.sh` generated:

```text
results/.../baseline/
├── sweep-inf.json
├── sweep-25pct.json
├── sweep-50pct.json
└── sweep-75pct.json
```

Some result trees under `results/embedding-models/` use this layout.

## Reading legacy results

- **Streamlit Embedding Metrics** — “Legacy Saturation Sweep” section (`sweep-*` files)
- **`view_results.py`** — still lists `baseline` / `sweep-*` rows in the terminal table

## Migration

| Old | New |
| --- | --- |
| `scenario=baseline` | `scenario=operating_point` (or `all` for full workflow) |
| Saturation curve from load % | Latency sweep + operating-point peak probe |
| `baseline/conc-*` (some trees) | `operating_point/conc-*` |

See the [Embedding Models Guide](../../docs/embedding-models.md#test-scenarios).
