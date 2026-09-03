
# LM Evaluation Harness (lm-eval)

Accuracy benchmarks for LLM models on vLLM CPU using the
[EleutherAI lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness).

> **Comprehensive guide:** See [LM Eval Benchmarking Guide](../../docs/lm-eval-benchmarking.md)
> for setup, task presets, dashboard usage, and troubleshooting.

## Overview

The **lm-eval** suite measures **model quality** (accuracy on standard NLP
benchmarks), not serving throughput or latency. Each test:

1. Starts a vLLM CPU container on the DUT with the target model
2. Runs the lm-eval container against the vLLM OpenAI-compatible API
3. Writes per-task accuracy scores to `results/lm-eval/`

**Key differences from concurrent-load:**

| Aspect | lm-eval | Concurrent Load |
| --- | --- | --- |
| **Primary metric** | Accuracy (`acc`, `exact_match`) | Throughput, TTFT, P95 latency |
| **Workload** | Fixed benchmark datasets | Synthetic chat/RAG/code prompts |
| **Core scaling** | Scores should be stable across cores | Performance varies with cores |
| **Client** | lm-eval harness container | GuideLLM |

## Quick Start

```bash
# One-time: build the lm-eval container image
cd container-images/lm-eval && ./build.sh

# Smoke test (~5–15 min depending on hardware)
./cpueval --suite lm-eval --models quick --cores 8 --limit 50

# View results in the Streamlit dashboard
./cpueval dashboard start
# Open the 🎯 LM Eval page at http://localhost:8501
```

## cpueval Entry Point

```bash
./cpueval --suite lm-eval [options]
```

| Option | Description | Default |
| --- | --- | --- |
| `--models` | Preset (`all`, `quick`, `small`, `medium`) or model list | `all` |
| `--cores` | Comma-separated core counts | `8,16,32` |
| `--tasks` | Task preset or comma-separated task names | `default` |
| `--limit` | Max examples per task (smoke tests) | none (full dataset) |
| `--batch-size` | lm-eval batch size | `16` |
| `--dtype` | Model dtype (`bfloat16`, `float16`, `float32`) | `bfloat16` |
| `--tag` | Label prepended to result run ID | none |

See [cpueval CLI](../../docs/cpueval-cli.md) and
[Scripts Reference](../../docs/scripts-reference.md#run-lm-eval-suitesh) for
full options.

## Default Test Matrix

| Dimension | Default |
| --- | --- |
| Models | 6 models (0.6B–3B): Qwen3-0.6B, TinyLlama, Granite-3.2-2B, Llama-3.2-1B, Qwen2.5-3B, Llama-3.2-3B |
| Cores | 8, 16, 32 |
| Tasks | `hellaswag`, `winogrande`, `arc_easy`, `arc_challenge` |

**Total:** 6 models × 3 cores = **18 runs** (full default matrix).

Narrow with overrides:

```bash
./cpueval --suite lm-eval --models quick --cores 8 --limit 50
./cpueval --suite lm-eval --models small --tasks math --cores 16 --limit 50 --batch-size 1
./cpueval --suite lm-eval --models quick --tasks truthful --cores 16 --limit 50
```

## Task Presets

| Preset | Tasks | API backend | Notes |
| --- | --- | --- | --- |
| `default` | hellaswag, winogrande, arc_easy, arc_challenge | Completions (log-prob MC) | Fast baseline accuracy sweep |
| `math` | gsm8k | Chat completions (generation) | Slower; use `--limit` for smoke tests |
| `truthful` | truthfulqa_mc1, truthfulqa_mc2 | Completions (log-prob MC) | Truthfulness / hallucination tendency |

Custom tasks: pass any
[lm-eval task name](https://github.com/EleutherAI/lm-evaluation-harness/tree/main/lm_eval/tasks)
as a comma-separated list via `--tasks`.

## Model Presets

| Preset | Models |
| --- | --- |
| `quick` | Qwen/Qwen3-0.6B |
| `small` | Qwen3-0.6B, TinyLlama-1.1B, Granite-3.2-2B |
| `medium` | Llama-3.2-1B, Qwen2.5-3B, Llama-3.2-3B |
| `all` | All six models above |

## Metrics

| Metric | Tasks | Meaning |
| --- | --- | --- |
| `acc` | Multiple-choice (hellaswag, arc, …) | Fraction of questions answered correctly |
| `acc_norm` | Multiple-choice | Length-normalised accuracy (preferred for MC comparison) |
| `exact_match` (flexible) | gsm8k | Correct after normalising answer formatting |
| `exact_match` (strict) | gsm8k | Exact string match |

**Interpretation:**

- Scores are 0.0–1.0 (displayed as percentages in the dashboard)
- Accuracy should be **stable across core counts** for the same model — large
  swings usually indicate a configuration or run issue, not hardware scaling
- GSM8K scores are typically lower than multiple-choice tasks; use
  `--batch-size 1` for generation tasks if memory is tight

## Results Layout

```text
results/lm-eval/
└── <model>/                          # / replaced with __
    └── <test-run-id>/                # e.g. Qwen3-0.6B-8C-20260101-120000
        ├── test-metadata.json        # Run config (model, tasks, cores, dtype, …)
        ├── results_<timestamp>.json  # lm-eval harness output (per-task scores)
        └── logs/                     # vLLM and lm-eval container logs
```

**Viewing results:**

- **Streamlit dashboard** (recommended): 🎯 LM Eval page — see
  [Dashboards Quickstart](../../docs/dashboards-quickstart.md#lm-eval-accuracy)
- **`cpueval results --list`**: Lists runs with `[lm-eval]` prefix
- **Terminal viewer**: Not supported for accuracy JSON — use the dashboard

## Test ID Naming Convention

| Prefix | Suite |
| --- | --- |
| `LMEVAL` | LM Evaluation Harness |

**Examples:**

- `LMEVAL-HELLASWAG-QWEN06` — HellaSwag on Qwen3-0.6B
- `LMEVAL-GSM8K-GRANITE32` — GSM8K on Granite-3.2-2B
- `LMEVAL-TRUTHFUL-LLAMA32` — TruthfulQA on Llama-3.2-1B

Run IDs are auto-generated from model name, core count, and timestamp (with
optional `--tag` prefix).

## When to Use This Suite

**Use lm-eval when you need to:**

- Compare model quality across platforms or vLLM versions
- Validate that a quantised or optimised build preserves accuracy
- Track regression on standard benchmarks (hellaswag, arc, gsm8k, …)
- Assess truthfulness tendencies (TruthfulQA)

**Use concurrent-load instead when you need:**

- Throughput (tokens/sec) under concurrency
- TTFT / TPOT / P95 latency
- Serving capacity planning

## Architecture

```text
Control node (Ansible)
    │
    ├── DUT: vLLM CPU container (model serving)
    │
    └── Load generator: lm-eval container (benchmark client)
            │
            └── HTTP → vLLM /v1/completions or /v1/chat/completions
```

Ansible playbook: `automation/test-execution/ansible/lm-eval-benchmark.yml`

Suite runner: `automation/test-execution/scripts/bash/run-lm-eval-suite.sh`

## Related Documentation

- [LM Eval Benchmarking Guide](../../docs/lm-eval-benchmarking.md) — Full setup and troubleshooting
- [Scripts Reference](../../docs/scripts-reference.md#run-lm-eval-suitesh) — Runner script options
- [cpueval CLI](../../docs/cpueval-cli.md) — Matrix suite commands
- [Dashboards Quickstart](../../docs/dashboards-quickstart.md#lm-eval-accuracy) — Results visualization
- [Environment Variables](../../docs/environment-variables.md#lm-evaluation-harness) — Configuration reference
- [LM Eval Container](../../container-images/lm-eval/README.md) — Image build details
