# cpueval - CPU Benchmarking CLI

Thin CLI wrapper for running full test matrices with easy overrides.

## Philosophy

**Matrix-first**: Most suites run comprehensive test matrices by default (models × cores × workloads). No `--model` required.

**Easy overrides**: Narrow the scope with simple flags when needed.

## Quick Start

```bash
# Matrix suites - run full test matrix (no --model required!)
./cpueval --suite rhaiis-sweep           # 60 combinations: 5 models × 3 cores × 4 workloads
./cpueval --suite embedding              # 30 combinations: 5 models × 3 cores × 2 scenarios
./cpueval --suite offline-batch          # 33 runs: use-cases 3

# Override to narrow scope
./cpueval --suite rhaiis-sweep --models tiny --cores 8
./cpueval --suite embedding --models quick --cores 4

# Single-shot suites (require --model)
./cpueval --suite chat-smoke --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 16

# Explore
./cpueval list                    # Shows Matrix vs Single type
./cpueval show rhaiis-sweep       # View default matrix
./cpueval results --last          # View results
```

## Installation

The `./cpueval` launcher automatically creates a virtual environment and installs
dependencies on first run. It requires Python 3.10+; on RHEL 9 / UBI 9 it will
install `python3.12` via dnf if `python3` is 3.9.

For manual installation:
```bash
cd automation/cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Environment Setup

**Managed mode** (default - vLLM on DUT, tests from load generator):
```bash
export DUT_HOSTNAME=<dut-host>
export LOADGEN_HOSTNAME=<loadgen-host>
export HF_TOKEN=<token>  # for gated models
```

**External endpoint mode** (test existing vLLM server):
```bash
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-vllm-host:8000
```

Optional:
```bash
export ANSIBLE_SSH_USER=<user>
export ANSIBLE_SSH_KEY=<path-to-key>
export VLLM_CONTAINER_IMAGE=<custom-image>
```

## Before vs After

**Before** (complex Ansible loops):
```bash
# Manual loops, long command lines
for workload in chat chat_lite summarization; do
    ansible-playbook -i inventory/hosts.yml llm-benchmark-auto.yml \
      -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
      -e "workload_type=$workload" \
      -e "requested_cores=32" \
      -e "vllm_cpu_start=96" \
      -e "vllm_numa_node=1" \
      -e "guidellm_cpus=0-31" \
      -e "guidellm_numa_node=0" \
      -e "guidellm_profile=concurrent" \
      -e "guidellm_rate=[1,2,4,8,16,32]" \
      -e "guidellm_max_seconds=300" \
      -e "vllm_caching_mode=baseline" \
      -e "test_name=EPYC-NO-SMT"
done
```

**After** (simple cpueval):
```bash
# Clean, simple - matrix runs automatically
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --vllm-cpu-start 96 \
  --vllm-numa 1 \
  --guidellm-cpus 0-31 \
  --guidellm-numa 0 \
  --extra guidellm_profile=concurrent \
  --extra guidellm_rate="[1,2,4,8,16,32]" \
  --extra test_name=EPYC-NO-SMT

# Or run full concurrent-load matrix (60 combinations: all models × 3 cores × 4 workloads)
./cpueval --suite concurrent-load \
  --vllm-cpu-start 96 \
  --vllm-numa 1 \
  --guidellm-cpus 0-31 \
  --guidellm-numa 0
```

## Commands

### list - Show available suites
```bash
./cpueval list
```

### show - Display suite details
```bash
./cpueval show concurrent-load
./cpueval show audio
```

### install - Install prerequisites
```bash
# Full install: system packages (dnf) + Ansible collections + shell completion
./cpueval install

# Skip system packages if already installed
./cpueval install --skip-system-deps

# Skip tab-completion setup
./cpueval install --skip-completion

# Preview without executing
./cpueval install --dry-run
```

On RHEL/Fedora this installs `ansible-core`, `python3-pip`, `git` via `dnf` and
the required Ansible Galaxy collections. On macOS/Ubuntu the dnf step is
soft-skipped with a `brew`/`apt` one-liner hint; install Ansible manually then
re-run `./cpueval install --skip-system-deps`.

Shell completion is installed for bash/zsh and registered for both `cpueval`
and `./cpueval`. Restart the shell (`exec bash` or `exec zsh`) once, then
`./cpueval <TAB>` completes commands. Use `--skip-completion` to opt out.

### doctor - Health checks
```bash
# Full check (including host ping)
./cpueval doctor

# Skip ping (faster, good for CI)
./cpueval doctor --no-ping
```

### Execute benchmarks

> `cpueval run --suite …` is also accepted for backward compatibility.

**Common options:**
- `--suite`/`-s` (required); Suite name
- `--model`/`-m`; Model ID
- `--cores`/`-c`; CPU core count
- `--workload`/`-w`; Workload type
- `--dry-run`; Print command without running
- `--skip-doctor`; Skip health checks

**LLM Examples:**

```bash
# Quick chat smoke test
./cpueval --suite chat-smoke \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 16 \
  --workload chat

# Concurrent load sweep (narrowed to single model/workload)
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --workload summarization

# Dry run to see command
./cpueval --suite concurrent-load \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 16 \
  --dry-run
```

**Audio Examples:**

```bash
# Transcription throughput test
./cpueval --suite audio \
  --models openai/whisper-small \
  --scenario transcription-throughput \
  --cores 32

# Quick audio test
./cpueval --suite audio \
  --models openai/whisper-tiny \
  --scenario quick-test \
  --cores 16

# Transcription latency test
./cpueval --suite audio \
  --models openai/whisper-medium \
  --scenario transcription-latency \
  --cores 64
```

Available audio scenarios:
- `transcription-throughput` - High-throughput ASR
- `transcription-latency` - Low-latency ASR
- `transcription-quality` - Quality-focused ASR
- `audio-duration-scaling` - Variable audio lengths
- `format-comparison` - Audio format comparison
- `constant-rate-stress` - Stress testing
- `quick-test` - Fast smoke test

**Embedding Example:**

```bash
./cpueval --suite embedding \
  --model RedHatAI/granite-embedding-english-r2 \
  --cores 16
```

**RHAIIS Quantized Models:**

RHAIIS quantized models work with the standard concurrent-load suite:

```bash
# Test RHAIIS model with custom container
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

./cpueval --suite concurrent-load \
  --model RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 \
  --cores 16 \
  --workload chat

# Test tiny quantized model
./cpueval --suite concurrent-load \
  --model RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 \
  --cores 8 \
  --workload chat

# Core sweep with RHAIIS
./cpueval --suite concurrent-load \
  --model RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 \
  --extra core_sweep_counts="[8,16,32]" \
  --workload chat
```

**Offline Batch Processing:**

```bash
# Default: all 11 use cases, 3 runs each
./cpueval --suite offline-batch

# All use cases, all RedHatAI models, 5 runs each
./cpueval --suite offline-batch --mode use-cases --runs 5 --models all

# Single use case with core sweep
./cpueval --suite offline-batch \
  --mode use-case-sweep \
  --use-case summarization \
  --models all \
  --cores 8,16,24,32 \
  --runs 3

# Single test configuration
./cpueval --suite offline-batch \
  --mode run_test \
  --model all \
  --dataset sonnet \
  --num-prompts 1000 \
  --cores 16

# RHAIIS container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./cpueval --suite offline-batch --mode use-cases --runs 3 --models all
```

**Offline-batch flags:** `--mode`, `--runs`, `--use-case`, `--models`/`--model`,
`--cores`, `--dataset`, `--num-prompts`. Escape hatch: `--extra args="..."`.

**Multi-model RHAIIS Sweeps:**

```bash
# Via cpueval (wraps bash script)
./cpueval --suite rhaiis-sweep \
  --extra models=llama \
  --extra cores="8,16,32" \
  --extra workloads="chat,rag"

# Or run bash script directly
automation/test-execution/scripts/bash/run-rhaiis-concurrent-load.sh \
  --models llama \
  --cores 8,16,32 \
  --workloads chat,rag \
  --phase 1
```

Model presets: `all` | `llama` | `qwen` | `tiny`

### CPU Pinning

**Simple pinning via CLI flags:**

```bash
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --vllm-cpu-start 64 \
  --vllm-numa 1 \
  --guidellm-cpus 0-31 \
  --guidellm-numa 0
```

**Using a profile:**

```bash
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --profile dual-socket-split
```

> **Customizing profiles:** Copy `automation/cli/profiles/dual-socket-split.yaml` to your project directory, modify the CPU pinning parameters, and use `--profile path/to/your-profile.yaml`

**Advanced: extra vars:**

```bash
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --extra vllm_cpu_start=64 \
  --extra vllm_numa_node=1

# Or from a file
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --extra-vars-file my-config.yaml
```

**Precedence:** suite defaults → profile → CLI flags → --extra → --extra-vars-file

### results - View benchmark results

```bash
# Show last run
./cpueval results --last

# Show specific result
./cpueval results results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-20260623-154515/8cores-single-socket

# List recent results
./cpueval results --list
./cpueval results --list --limit 20

# Open dashboard
./cpueval results --open

# Convert results
./cpueval results --convert

# Just convert, don't view
./cpueval results --last --convert --no-view
```

### dashboard - Manage Streamlit dashboard

```bash
# Start dashboard in background (port 8501)
./cpueval dashboard start

# Stop running dashboard
./cpueval dashboard stop
```

## Available Suites

| Suite | Type | Runner | Description |
|-------|------|--------|-------------|
| `concurrent-load` | Matrix | script | Upstream LLM concurrent load sweep (60 tests: all models × 3 cores × 4 workloads) |
| `rhaiis-sweep` | Matrix | script | RHAIIS quantized model sweep (60 tests: 5 models × 3 cores × 4 workloads) |
| `embedding` | Matrix | script | Embedding model performance matrix (30 tests: 5 models × 3 cores × 2 scenarios) |
| `offline-batch` | Matrix | script | Offline batch processing (33 tests: 11 use-cases × 3 runs) |
| `audio` | Matrix | script | Audio model benchmarking — all models × transcription-throughput × 32 cores |
| `chat-smoke` | Single | ansible | Quick auto-configured LLM chat test (requires --model) |
| `setup-platform` | Single | ansible | Platform setup and configuration |
| `health` | Single | ansible | Health check for DUT and load generator |

## Creating Custom Suites

Create a YAML file in `automation/cli/src/cpueval/suites/`:

```yaml
name: my-suite
description: My custom suite
runner: ansible  # or 'script'
target: my-playbook.yml

defaults:
  test_model: my-model
  requested_cores: 16

param_mappings:
  model: test_model
  cores: requested_cores
  workload: workload_type
```

## Creating CPU Pinning Profiles

Create a YAML file in `automation/cli/profiles/`:

```yaml
# profiles/my-profile.yaml
vllm_cpu_start: 64
vllm_numa_node: 1
guidellm_cpus: "0-31"
guidellm_numa_node: 0
```

Use it:
```bash
./cpueval --suite concurrent-load --model my-model --cores 32 --profile my-profile
```

## Troubleshooting

**Health check failures:**
```bash
# Check what's failing
./cpueval doctor

# Common fixes
export DUT_HOSTNAME=my-dut
export LOADGEN_HOSTNAME=my-loadgen
export HF_TOKEN=hf_xxxxx

# Test connectivity
ansible -i automation/test-execution/ansible/inventory/hosts.yml all -m ping
```

**No results found:**
```bash
# List results to find the right path
./cpueval results --list

# Check results directories
ls -la results/llm/
ls -la results/audio-models/
```

**Module import errors:**
```bash
# Recreate venv
rm -rf automation/cli/.venv
./cpueval list  # Will recreate venv
```

**Ansible collection missing:**
```bash
./cpueval install --skip-system-deps
```

## Development

```bash
cd automation/cli

# Install in dev mode with test dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_results.py::test_extract_metrics_guidellm_v06 -v

# Format code (if using black/isort)
black src/cpueval/
isort src/cpueval/
```

## Architecture

```
cpueval (thin wrapper)
├── Invokes existing Ansible playbooks
├── Streams stdout/stderr
├── Does NOT reimplement deploy/GuideLLM/vLLM logic
└── Provides progressive disclosure for CPU pinning
```

**Design principles:**
- Thin wrapper only
- Suites are YAML data, not hard-coded
- Prefer env-based inventory
- Progressive disclosure (simple --cores, advanced pinning optional)
- Subprocess invocation, not Python reimplementation

## Enterprise Testing Strategy

### Practical 1-Week Test Plan

For comprehensive RHAIIS validation with results by end of week:

**Day 1-2: Online Inference (Concurrent Load)**
```bash
# Tier 1 workloads: chat, code, summarization, rag (60 combinations)
./cpueval --suite rhaiis-sweep \
  --models all \
  --cores "8,16,32" \
  --workloads "chat,code,summarization,rag" \
  --phase 1

# 5 models × 3 cores × 4 workloads = 60 tests (~5-7 hours)
```

**Day 3: Offline Batch Processing**
```bash
# All 11 enterprise use-cases, 3 runs each = 33 tests
./cpueval --suite offline-batch

# Enterprise Tier Priorities:
#   Tier 1 (Must-have): Summarization, Classification, RAG Batch, Entity Extraction
#   Tier 2 (High value): Long-Doc Summary, ETL, Short Labeling
#   Tier 3 (Valuable): Code Gen, Translation, Dataset Gen
#   Tier 4 (Deprioritize): Shared-Prefix

# Run specific use case:
./cpueval --suite offline-batch \
  --mode use-case-sweep \
  --use-case summarization \
  --models all \
  --cores 8,16,32 \
  --runs 3
```

**Day 4: Embedding Models**
```bash
# All 5 embedding models (default: all)
./cpueval --suite embedding \
  --models all \
  --cores "8,16,32"

# 5 models × 3 cores × 2 scenarios (baseline+latency) = 30 tests (~6-8 hours)

# Or just small/fast models:
./cpueval --suite embedding \
  --models small \
  --cores "8,16,32"
# 2 models × 3 cores × 2 scenarios = 12 tests (~4-6 hours)
```

**Day 5: Audio Workloads**
```bash
# Whisper models: tiny, small, medium
./cpueval --suite audio \
  --models all \
  --scenarios transcription-throughput \
  --cores "32"

# 3 models × 1 scenario × 1 core = 3 tests (~3-4 hours)
```

### Quick Smoke Test (AWS)

Verify everything works before starting week-long runs:

```bash
# 3-5 minute smoke test
./cpueval --suite chat-smoke \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 8 \
  --skip-doctor
```
