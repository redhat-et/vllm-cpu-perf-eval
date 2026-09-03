# vLLM CPU Performance Evaluation

Comprehensive performance evaluation framework for vLLM on CPU platforms.

This site provides testing methodology, automation tools, and platform
configurations for evaluating vLLM inference performance on CPU-based systems.

## Quick Links

<div class="quick-links">
  <div class="link-card">
    <h3>Getting Started</h3>
    <p>Install with <code>./cpueval install</code>, then run your first benchmark</p>
    <a href="docs/getting-started/">Quick Start Guide →</a>
  </div>

  <div class="link-card">
    <h3>Test Suites</h3>
    <p>All supported benchmarks, cpueval commands, and suite documentation</p>
    <a href="docs/test-suites/">Test Suites Overview →</a>
  </div>

  <div class="link-card">
    <h3>cpueval CLI</h3>
    <p>Install, doctor, and run benchmark suites from one command</p>
    <a href="docs/cpueval-cli/">CLI Guide →</a>
  </div>

  <div class="link-card">
    <h3>Models</h3>
    <p>Supported LLM, embedding, and audio models</p>
    <a href="models/models/">Model Catalog →</a>
  </div>

  <div class="link-card">
    <h3>Results</h3>
    <p>Analyze results with dashboards and experiment tracking</p>
    <a href="docs/dashboards-quickstart/">Dashboards Guide →</a>
  </div>

  <div class="link-card">
    <h3>Methodology</h3>
    <p>Testing approach, metrics, and 3-phase strategy</p>
    <a href="docs/methodology/overview/">Testing Methodology →</a>
  </div>
</div>

## Test Suites at a Glance

| Suite | Status | Focus |
| --- | --- | --- |
| [Concurrent Load](tests/concurrent-load/concurrent-load/) | Validated | P95 latency under concurrent requests |
| [Offline Batch](tests/offline-batch/offline-batch/) | Validated | Bulk document processing |
| [Embedding Models](tests/embedding-models/embedding-models/) | Validated | Embedding throughput and latency |
| [Audio Models](tests/audio-models/) | Validated | Whisper ASR performance |
| [LM Eval](tests/lm-eval/lm-eval.md) | WIP | LLM accuracy (hellaswag, arc, gsm8k, …) |
| [Scalability](tests/scalability/scalability/) | WIP | Maximum throughput and sweep curves |
| [Resource Contention](tests/resource-contention/resource-contention/) | Planned | Multi-tenant scenarios |

See the [Test Suites Overview](docs/test-suites/) for cpueval commands,
suite selection guidance, and links to detailed documentation.

## Key Features

- **cpueval CLI** — Matrix-first benchmarking across 9 test suites
- **3-Phase Testing** — Baseline, realistic, and production methodology
- **Ansible automation** — Reproducible, distributed test execution
- **MTEB integration** — Embedding quality evaluation
- **Streamlit dashboards** — Interactive results analysis
- **MLflow tracking** — Experiment comparison and history

Browse the full [Documentation](docs/) index or use the sidebar
navigation to explore guides by topic.
