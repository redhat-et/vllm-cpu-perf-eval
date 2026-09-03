# LM Eval Benchmarking Guide

Comprehensive guide for running
[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)
accuracy benchmarks against vLLM CPU deployments.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Task Presets](#task-presets)
- [Understanding Results](#understanding-results)
- [Dashboard Analysis](#dashboard-analysis)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

### What Does This Suite Measure?

The **lm-eval** suite answers quality questions that throughput benchmarks cannot:

- "Does this model understand commonsense reasoning?" (HellaSwag, WinoGrande)
- "How well does it handle grade-school science?" (ARC-Easy, ARC-Challenge)
- "Can it solve math word problems?" (GSM8K)
- "Does it avoid common false beliefs?" (TruthfulQA)

### Prerequisites

**System:**

- cpueval installed (`./cpueval install`)
- DUT + load generator configured (`DUT_HOSTNAME`, `LOADGEN_HOSTNAME`)
- Podman or Docker on both hosts
- **lm-eval container image built locally** (see below)

**Software:**

- vLLM CPU container (default upstream image, or RHAIIS via `VLLM_CONTAINER_IMAGE`)
- lm-eval 0.4.7 in `quay.io/vllm-cpu-perf-eval/lm-eval:latest` (build locally)

**Tokens:**

- `HF_TOKEN` for gated models (Llama, some Granite variants)

### Build the lm-eval Container

The default image is not always pre-pushed to Quay.io. Build before your first run:

```bash
cd container-images/lm-eval
./build.sh
```

See [container-images/lm-eval/README.md](../container-images/lm-eval/README.md) for
image details and version pins.

## Quick Start

```bash
# 1. Environment
export DUT_HOSTNAME=<dut-host>
export LOADGEN_HOSTNAME=<loadgen-host>
export HF_TOKEN=<token>   # if testing gated models

# 2. Verify setup
./cpueval doctor

# 3. Build lm-eval image (one-time)
cd container-images/lm-eval && ./build.sh && cd -

# 4. Smoke test
./cpueval --suite lm-eval --models quick --cores 8 --limit 50

# 5. View results
./cpueval dashboard start
# Navigate to 🎯 LM Eval at http://localhost:8501
```

### Full Matrix (Production)

```bash
./cpueval --suite lm-eval
# 6 models × 3 cores × 4 default tasks — plan several hours
```

Narrow scope for iterative testing:

```bash
./cpueval --suite lm-eval --models small --cores 16 --tasks hellaswag,arc_easy
```

## Task Presets

| Preset | Tasks | Scoring | API | Typical runtime |
| --- | --- | --- | --- | --- |
| `default` | hellaswag, winogrande, arc_easy, arc_challenge | Log-prob MC (`acc`, `acc_norm`) | `/v1/completions` | Moderate |
| `math` | gsm8k | Generation (`exact_match`) | `/v1/chat/completions` | Slow |
| `truthful` | truthfulqa_mc1, truthfulqa_mc2 | Log-prob MC | `/v1/completions` | Moderate |

### Task Reference

| Task | What it tests |
| --- | --- |
| **hellaswag** | Commonsense sentence completion |
| **winogrande** | Pronoun / referent resolution |
| **arc_easy** | Grade-school science (easier) |
| **arc_challenge** | Grade-school science (harder) |
| **gsm8k** | Grade-school math word problems (multi-step) |
| **truthfulqa_mc1** | Truthfulness — single best answer |
| **truthfulqa_mc2** | Truthfulness — any correct answer |

Custom tasks:

```bash
./cpueval --suite lm-eval --models quick --tasks piqa,boolq --cores 8 --limit 100
```

## Understanding Results

### Result Files

Base path: `results/lm-eval/<model>/<test-run-id>/`

| File | Description |
| --- | --- |
| `test-metadata.json` | Model, tasks, cores, dtype, KV cache, container images, timestamp |
| `results_<timestamp>.json` | Per-task scores from lm-evaluation-harness |
| `logs/` | vLLM server and lm-eval client logs |

### Key Metrics

| Metric | Use for |
| --- | --- |
| **acc** | Standard multiple-choice accuracy |
| **acc_norm** | Multiple-choice with length normalisation — **prefer for MC comparisons** |
| **exact_match (flexible)** | GSM8K — headline math score |
| **exact_match (strict)** | GSM8K — strict string match |

Scores are fractions (0.65 = 65% correct). The dashboard displays them as
percentages.

### What to Expect

- **Multiple-choice tasks:** Strong small models often score 0.55–0.75 on
  hellaswag/arc_easy; arc_challenge is harder (0.30–0.50 is common)
- **GSM8K:** Scores are typically much lower; generation is slower and more
  variable
- **Core count:** Accuracy should not change materially with CPU core count —
  if it does, investigate run stability before comparing models
- **Limit flag:** `--limit 50` gives directional smoke-test scores, not
  publishable benchmark numbers

### cpueval results CLI

```bash
# List recent runs (includes [lm-eval] prefix)
./cpueval results --list

# --last shows throughput tables (benchmarks.json) — not lm-eval accuracy
# Use the Streamlit LM Eval page for accuracy summaries
```

## Dashboard Analysis

Launch the dashboard:

```bash
./cpueval dashboard start
# or
cd automation/test-execution/dashboard-examples/vllm_dashboard && ./launch-dashboard.sh
```

Open **🎯 LM Eval** and set the results path to `results/lm-eval/` (or your
custom location).

### Dashboard Sections

1. **Summary** — Latest scores per model/task with filters for cores and tasks
2. **Model Comparison** — Side-by-side bar or line charts for a selected task
3. **Accuracy Heatmap** — Model × task report card (when multiple models/tasks)
4. **All Results** — Raw table export

Use the **"How to Read These Results"** expander on the page for plain-language
task and metric descriptions.

### Recommended Workflow

1. Run smoke test with `--limit 50` to validate environment
2. Run targeted comparison: `--models small --cores 16 --tasks default`
3. Open LM Eval dashboard; compare models on acc_norm
4. For math: re-run with `--tasks math --batch-size 1 --limit 100`
5. Export or screenshot heatmap for reports

See [Dashboards Quickstart](dashboards-quickstart.md#lm-eval-accuracy) for more
detail.

## Advanced Configuration

### RHAIIS / Custom vLLM Image

```bash
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./cpueval --suite lm-eval --models quick --cores 16 --limit 50
```

Pull the RHAIIS image on the DUT before running (Ansible cannot pull
authenticated registry images).

### CPU Pinning

```bash
./cpueval --suite lm-eval \
  --models quick \
  --cores 32 \
  --extra vllm_cpus=64-95 \
  --extra guidellm_cpus=0-31 \
  --limit 50
```

`guidellm_cpus` pins the **lm-eval client container** on the load generator
(same variable name as GuideLLM suites).

### Custom lm-eval Image

```bash
export LM_EVAL_IMAGE=my-registry/lm-eval:custom
./cpueval --suite lm-eval --models quick --cores 8 --limit 50
```

Or via CLI: `--extra lm_eval_image=my-registry/lm-eval:custom`

### Ansible Direct

```bash
cd automation/test-execution/ansible
ansible-playbook -i inventory/hosts.yml lm-eval-benchmark.yml \
  -e "test_model=Qwen/Qwen3-0.6B" \
  -e "requested_cores=16" \
  -e "lm_eval_tasks=hellaswag,arc_easy" \
  -e "lm_eval_limit=100"
```

See [Ansible Test Execution](ansible/test-execution.md) for playbook details.

### Tagging Runs

```bash
./cpueval --suite lm-eval --models quick --cores 8 --tag baseline-v1 --limit 50
# Result ID: baseline-v1-Qwen3-0.6B-8C-<timestamp>
```

## Troubleshooting

### lm-eval image not found

```bash
cd container-images/lm-eval && ./build.sh
# Or set a custom image: --extra lm_eval_image=<your-image>
```

### Task dataset load errors

The bundled image patches hellaswag/winogrande dataset paths for
`datasets` ≥ 3.x. If a custom task fails, check lm-eval logs in
`results/lm-eval/<model>/<run-id>/logs/`.

### GSM8K very slow or OOM

- Use `--limit 50` for smoke tests
- Set `--batch-size 1`
- Ensure sufficient RAM for the model + KV cache (`--kv-cache-space`, default 40 GiB)

### Gated model access denied

```bash
export HF_TOKEN=hf_xxxxx
```

### Scores differ across core counts

Accuracy should be deterministic for a given model/task. Large variance suggests:

- Incomplete runs (check logs)
- Different `--limit` values
- Model warmup or timeout issues — increase `VLLM_HEALTH_TIMEOUT`

### No data in dashboard

1. Confirm results exist: `ls results/lm-eval/*/`
2. Set results path in dashboard sidebar to `results/lm-eval/`
3. Ensure `results_*.json` is present in the run directory

## Best Practices

1. **Always build the lm-eval image** before the first run on a new machine
2. **Smoke test first:** `--models quick --cores 8 --limit 50`
3. **Use acc_norm** for multiple-choice model comparisons
4. **Pin cores** on dual-socket systems to avoid NUMA noise in wall-clock time
   (scores should still match)
5. **Tag regression runs** with `--tag` when comparing vLLM versions
6. **Do not confuse accuracy with throughput** — run concurrent-load separately
   for serving performance

## Related Documentation

- [LM Eval Test Suite](../tests/lm-eval/lm-eval.md) — Methodology and matrix
- [Scripts Reference](scripts-reference.md#run-lm-eval-suitesh) — Runner options
- [cpueval CLI](cpueval-cli.md) — Suite commands
- [Environment Variables](environment-variables.md#lm-evaluation-harness) — Env reference
- [Reporting Guide](methodology/reporting.md#lm-evaluation-harness-results) — Result formats for reports
- [LM Eval Container](../container-images/lm-eval/README.md) — Image build
