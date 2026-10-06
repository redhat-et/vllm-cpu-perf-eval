# Embedding Models Performance Testing

Performance and quality evaluation for embedding models on vLLM CPU platforms
using `vllm bench serve` (`openai-embeddings` backend).

!!! tip "Canonical guide"
    For setup (RHAIIS images, modes, troubleshooting, MTEB), see the
    **[Embedding Models Guide](../../docs/embedding-models.md)** on this site.
    This page focuses on **what the suite measures** and how it maps to automation.

## Overview

The embedding suite characterises:

- **Throughput and latency** across a concurrency sweep (`scenario=latency`)
- **Fixed operating-point probes** at conc=1, 8, and peak (`scenario=operating_point`)
- **End-to-end workflow** — latency sweep, peak detection, then probes (`scenario=all`)

Results are written under `results/embedding/<model>/<timestamp>/`.

## Quick start

```bash
# From repository root
./cpueval install
export DUT_HOSTNAME=<dut-ip>
export LOADGEN_HOSTNAME=<loadgen-ip>   # omit for dut-only

# Full workflow (suite default: scenario=all)
./cpueval --suite embedding --models quick --cores 16

# Or Ansible directly (playbook default: scenario=operating_point)
cd automation/test-execution/ansible
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "scenario=all"
```

See [cpueval CLI](../../docs/cpueval-cli.md) and
[run-embedding-suite.sh](../../automation/test-execution/scripts/bash/run-embedding-suite.sh)
(`--help`) for presets (`granite-ml`, `quick`, …) and flags.

## Test scenarios

| `scenario` | What runs | Typical duration |
| --- | --- | --- |
| `latency` | Concurrency sweep only | ~40–60 min / model |
| `operating_point` | Three probes (1, 8, peak) | ~15–25 min / model |
| `all` | Latency → peak detection → operating-point | ~60–90 min / model |

`baseline` is accepted as a **deprecated alias** for `operating_point` in
`run-embedding-suite.sh` only.

**Methodology detail:**

- [Operating-point probes](operating-point.md)
- [Latency concurrency sweep](latency-concurrent.md)
- [Legacy load-fraction sweep](baseline-sweep.md) (older result trees only)

Default concurrency levels for `latency`:
**16, 24, 32, 48, 64, 96, 128, 192, 256, 384**.

Operating-point peak concurrency comes from the latency sweep when
`scenario=all`; otherwise defaults to **32** (`op_peak_concurrency` override).

## Execution modes

| Mode | Description |
| --- | --- |
| **managed** (default) | vLLM on DUT; `vllm bench serve` on load generator |
| **dut-only** | vLLM and bench on one node (`VLLM_MODE=dut-only`) |
| **external** | Bench against an existing `/v1/embeddings` endpoint |

## Repository layout

```text
tests/embedding-models/
├── embedding-models.md      # This page
├── operating-point.md       # Operating-point methodology
├── latency-concurrent.md    # Latency sweep methodology
└── baseline-sweep.md        # Legacy saturation sweep (deprecated)

models/embedding-models/model-matrix.yaml   # Models, KV cache hints, scenarios

automation/test-execution/
├── ansible/embedding-benchmark.yml
├── scripts/bash/run-embedding-suite.sh
└── dashboard-examples/vllm_dashboard/   # Embedding Metrics page
```

Legacy bash helpers under `automation/test-execution/bash/embedding/` target the
old load-fraction sweep; prefer Ansible or `run-embedding-suite.sh`.

## Models

Default `cpueval --suite embedding` matrix uses five RedHatAI models; the
**`granite-ml`** preset adds IBM/Microsoft multilingual models and Harrier.

See [model-matrix.yaml](../../models/embedding-models/model-matrix.yaml) and the
[Embedding Models Guide](../../docs/embedding-models.md#supported-embedding-models).

## Results layout

```text
results/embedding/<model-name>/<timestamp>/
├── operating_point/
│   ├── conc-1.json
│   ├── conc-8.json
│   └── conc-{N}.json          # peak probe
├── latency/
│   └── concurrent-{N}.json    # sweep levels
├── container-stats.jsonl        # optional CPU/memory time series
├── test-metadata.json
└── vllm-server.log              # managed / dut-only
```

Legacy runs may still have `baseline/sweep-*.json`; dashboards and
`view_results.py` continue to read them.

## Test case IDs (matrix)

| Test ID | Scenario | Focus |
| --- | --- | --- |
| `EMB-OP-GRANITE-EN-EMB512` | operating_point | English encoder throughput/latency probes |
| `EMB-LATENCY-GRANITE-ML-EMB512` | latency | Multilingual concurrency envelope |
| `EMB-ALL-*` | all | Full latency + operating-point workflow |

See [model-matrix.yaml](../../models/embedding-models/model-matrix.yaml) for the
full mapping.

## Analysis

- **Streamlit:** [Dashboards quick start](../../docs/dashboards-quickstart.md)
  → Embedding Metrics (operating-point, latency, container stats)
- **Terminal:** [Terminal results viewer](../../docs/terminal-results-viewer.md)
- **Quality:** [MTEB guide](../../docs/mteb-sweep-guide.md) (`cpueval --suite mteb`)

## Related links

- [Embedding Models Guide](../../docs/embedding-models.md)
- [Test suites overview](../../docs/test-suites.md)
- [Ansible embedding playbook](../../automation/test-execution/ansible/embedding-benchmark.yml)
