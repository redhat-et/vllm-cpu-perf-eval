
View benchmark results directly in the terminal without launching a
dashboard.

## TL;DR

```bash
cd automation/test-execution/ansible

# View LLM (GuideLLM) results
ansible-playbook view-results.yml \
  -e "results_path=results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-20260428-124238/32cores-numa3-tp1/"

# View embedding (vllm bench serve) results
ansible-playbook view-results.yml \
  -e "results_path=results/embedding/BAAI__bge-small-en-v1.5/20260710-143022/"

# Auto-display after benchmark runs
ansible-playbook -i inventory/hosts.yml llm-benchmark.yml \
  -e "show_results=true" ...
```

## Overview

The terminal results viewer (`view_results.py`) prints a compact summary
table of benchmark results to stdout. It auto-detects whether the results
are from an LLM (GuideLLM) or embedding (vllm bench serve) run and
formats the output accordingly.

**Purpose:** Quick post-run review without switching windows

**Requirements:**
- Python 3.6+ (stdlib only, no pip install needed)
- Works offline, no network access

**When to use:**
- Quick glance at results in the same terminal where you ran the test
- CI/CD pipelines where a browser is not available
- Comparing a single run before diving into the Streamlit dashboard

For full interactive analysis with charts, filtering, and multi-run
comparisons, use the
[Streamlit dashboard](dashboards-quickstart.md) instead.

## Usage

### View Existing Results

Use the `view-results.yml` playbook to display results from any
previous benchmark run:

```bash
cd automation/test-execution/ansible

# LLM results (relative path from project root)
ansible-playbook view-results.yml \
  -e "results_path=results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-20260428-124238/32cores-numa3-tp1/"

# Embedding results
ansible-playbook view-results.yml \
  -e "results_path=results/embedding/BAAI__bge-small-en-v1.5/20260710-143022/"

# Absolute paths also work
ansible-playbook view-results.yml \
  -e "results_path=/home/user/benchmark-results/..."

# Suppress metadata header
ansible-playbook view-results.yml \
  -e "results_path=..." -e "no_header=true"
```

The playbook auto-detects the result format:

| Directory contents | Detected as |
|--------------------|-------------|
| Contains `benchmarks.json` | LLM |
| Contains `baseline/` or `latency/` subdirs | Embedding |
| Contains `sweep-*.json` or `concurrent-*.json` | Embedding |

### Auto-Display After Benchmark Runs

All three benchmark playbooks support automatic result display via the
`show_results` variable:

```bash
# LLM single-config test
ansible-playbook -i inventory/hosts.yml llm-benchmark.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=chat" \
  -e "core_config_name=32cores-numa3-tp1" \
  -e "show_results=true"

# LLM auto (multi-config sweep)
ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "show_results=true"

# Embedding test
ansible-playbook -i inventory/hosts.yml embedding-benchmark.yml \
  -e "test_model=BAAI/bge-small-en-v1.5" \
  -e "scenario=all" \
  -e "show_results=true"
```

The summary is displayed after results are fetched to the local machine
but before log collection. It runs with `failed_when: false` so it
never blocks the pipeline.

## Output Format

### LLM Results

<!-- markdownlint-disable MD013 -->

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 vLLM CPU Benchmark Results — LLM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Model:    TinyLlama/TinyLlama-1.1B-Chat-v1.0
 Workload: chat | Cores: 32 | Platform: Intel Xeon 6975P
 vLLM: 0.18.0 | Caching: baseline | Date: 2026-04-28
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Conc │    Tok/s │     TTFT (ms)        │     ITL (ms)         │   E2E Latency (ms)         │  Reqs │ Err
       │   (mean) │   med    p95     p99  │   med    p95    p99  │     med      p95      p99  │       │
  ─────┼──────────┼──────────────────────-┼──────────────────────┼───────────────────────────--┼───────┼────
     1 │    125.3 │    85     92      98  │   8.1    9.2     11  │    4120     4350     4580  │    15 │   0
     8 │    986.2 │   292    950    1200  │   8.3    9.8     12  │    7247     8120     8950  │    56 │   0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

<!-- markdownlint-enable MD013 -->

**Columns:**

<!-- markdownlint-disable MD013 -->

| Column | Source | Unit |
|--------|--------|------|
| Conc | `config.strategy.streams` or `max_concurrency` | count |
| Tok/s | `metrics.tokens_per_second.successful.mean` | tokens/sec |
| TTFT | `metrics.time_to_first_token_ms.successful` | ms |
| ITL | `metrics.inter_token_latency_ms.successful` | ms |
| E2E Latency | `metrics.request_latency.successful` | ms (from s) |
| Reqs | `scheduler_metrics.requests_made.successful` | count |
| Err | `scheduler_metrics.requests_made.errored` | count |

<!-- markdownlint-enable MD013 -->

Rows are sorted by concurrency level ascending.

### Embedding Results

<!-- markdownlint-disable MD013 -->

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 vLLM CPU Benchmark Results — Embedding
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Model:    BAAI/bge-small-en-v1.5
 Scenario: all | Cores: N/A | Platform: Intel Xeon 6975P
 vLLM: 0.8.5.post1 | Prompts: 250 | Input len: 512 | Date: 2026-07-10
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

       Type │    Label │        RPS │        Tok/s │        E2E Latency (ms)                          │   Reqs │  Dur(s)
            │          │            │              │       mean        med        std        p99       │        │
  ──────────┼──────────┼────────────┼──────────────┼──────────────────────────────────────────────────-┼────────┼────────
   baseline │      inf │      52.10 │      26675.2 │       19.1       18.5        3.2       32.4      │    250 │    4.8
   baseline │    25pct │      13.03 │       6671.0 │       19.2       18.6        3.1       31.9      │    250 │   19.2
 concurrent │        2 │      51.90 │      26576.0 │       38.2       37.5        5.8       58.1      │    250 │    4.8
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

<!-- markdownlint-enable MD013 -->

**Columns:**

<!-- markdownlint-disable MD013 -->

| Column | Source | Unit |
|--------|--------|------|
| Type | `baseline` (sweep) or `concurrent` | - |
| Label | `inf`, `25pct`, `2`, etc. | - |
| RPS | `request_throughput` | req/sec |
| Tok/s | `total_token_throughput` | tokens/sec |
| E2E Latency | `mean_e2el_ms`, `median_e2el_ms`, etc. | ms |
| Reqs | `completed` | count |
| Dur(s) | `duration` | seconds |

<!-- markdownlint-enable MD013 -->

Rows are sorted: baseline first (inf, then by percentage), then
concurrent by concurrency count.

## Metadata Header

When `test-metadata.json` exists alongside the results, the viewer
displays a header block with:

- **Model name** and workload type (LLM) or scenario (embedding)
- **Platform** (CPU model, cleaned up for readability)
- **Core count**, **vLLM version**, and **test date**

Use `--no-header` to suppress this block.

## When to Use What

| Scenario | Terminal Viewer | Streamlit |
|----------|-----------------|-----------|
| Quick post-run check | Best | Overkill |
| CI/CD pipeline | Only option | N/A |
| Compare multiple runs | N/A | Best |
| Interactive exploration | N/A | Best |
| Share results in a ticket | Copy-paste table | Screenshot |
| Deep metric analysis | N/A | Best |

## Troubleshooting

### "Could not detect result format"

The script could not find `benchmarks.json` (LLM) or embedding
result files at the given path. Verify you are pointing at the
correct results directory:

```bash
# LLM: should contain benchmarks.json
ls <path>/benchmarks.json

# Embedding: subdirectory layout
ls <path>/baseline/ <path>/latency/

# Embedding: top-level file layout
ls <path>/sweep-*.json <path>/concurrent-*.json
```

### Missing columns show "-"

A dash (`-`) indicates the metric was not present in the result file.
This can happen with older result formats or partial runs.

### Ansible does not show results

Ensure `show_results=true` is passed as an extra variable:

```bash
ansible-playbook ... -e "show_results=true"
```

The display tasks are gated by this variable and default to `false`.

## Related Documentation

- [Dashboards Quick Start](dashboards-quickstart.md) - Interactive
  Streamlit dashboard for full analysis
- [Scripts Reference](scripts-reference.md) - All available scripts
- [Test Execution with Ansible](ansible/test-execution.md) - Running
  benchmarks
