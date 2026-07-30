---
title: cpueval CLI
parent: Getting Started
grand_parent: Documentation
nav_order: 2
layout: default
---

# cpueval CLI

Matrix-first CLI for running comprehensive CPU benchmarks. Most suites run full test matrices by default—no `--model` required!

## Philosophy

- **Matrix suites** run complete test matrices (models × cores × workloads/scenarios) by default
- **Easy overrides** to narrow scope when needed
- **Single-shot suites** for targeted deep testing

## Quick Start

```bash
# Matrix suites - run full matrices (no --model required!)
./cpueval run --suite rhaiis-sweep           # 60 combinations: 5 models × 3 cores × 4 workloads
./cpueval run --suite embedding              # 30 combinations: 5 models × 3 cores × 2 scenarios
./cpueval run --suite offline-batch          # 33 runs: use-cases 3
./cpueval run --suite audio                  # Configurable matrix

# Override to narrow
./cpueval run --suite rhaiis-sweep --models tiny --cores 8
./cpueval run --suite embedding --models quick --cores 4

# Single-shot suites (--model required)
./cpueval run --suite chat-smoke --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8
./cpueval run --suite concurrent-load --model meta-llama/Llama-3.2-1B-Instruct --cores 32

# Explore
./cpueval list                    # Shows Matrix vs Single type
./cpueval show rhaiis-sweep       # View default matrix
./cpueval results --last          # View results
```

## Installation

The `./cpueval` launcher automatically creates a virtual environment on first run. For manual installation:

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

# Optional
export ANSIBLE_SSH_USER=<user>
export ANSIBLE_SSH_KEY=<path-to-key>
```

**External endpoint mode** (test existing vLLM server):

```bash
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-vllm-host:8000
```

## Commands

### list - Show available suites

```bash
./cpueval list
```

Example output:

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                      ┃ Type         ┃ Runner     ┃ Description          ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ rhaiis-sweep              │ Matrix       │ script     │ RHAIIS model         │
│                           │              │            │ concurrent load      │
│ embedding                 │ Matrix       │ script     │ Embedding model      │
│                           │              │            │ performance          │
│ offline-batch             │ Matrix       │ script     │ Offline batch        │
│                           │              │            │ processing           │
│ audio                     │ Matrix       │ script     │ Audio model          │
│                           │              │            │ benchmarking         │
│ concurrent-load           │ Matrix       │ script     │ LLM concurrent load  │
│ chat-smoke                │ Single       │ ansible    │ Quick LLM chat test  │
│ health                    │ Single       │ ansible    │ Health check         │
└───────────────────────────┴──────────────┴────────────┴──────────────────────┘

Legend: Matrix = full test matrix by default, Single = requires --model
```

### show - Suite details

```bash
./cpueval show <suite-name>

# Examples
./cpueval show rhaiis-sweep
./cpueval show embedding
```

Example output (`./cpueval show rhaiis-sweep`):

```text
Suite: rhaiis-sweep

Description: RHAIIS model concurrent load sweep - full test matrix by default
Runner: script
Type: Matrix suite (runs full test matrix by default)

Default Parameters:
  models: all
  cores: 8,16,32
  workloads: chat,code,summarization,rag
  phase: 1

Parameter Mappings:
  --models → --models
  --cores → --cores
  --workloads → --workloads
  --workload → --workloads
```

### doctor - Health checks

```bash
# Full check (including host ping)
./cpueval doctor

# Skip ping (faster, good for CI)
./cpueval doctor --no-ping
```

Example output:

```text
cpueval system health check

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                ┃ Status       ┃ Details                                ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ansible-playbook     │ ✓            │ unknown                                │
│ Ansible collections  │ ✗            │ containers.podman collection not found │
│ Inventory file       │ ✓            │ .../ansible/inventory/hosts.yml        │
│ Environment vars     │ ✗            │ Missing: DUT_HOSTNAME, LOADGEN_HOSTNAME│
└──────────────────────┴──────────────┴────────────────────────────────────────┘

✗ Some checks failed
```

Verifies:
- ansible-playbook available
- Ansible collections installed (containers.podman)
- Inventory file exists
- Required environment variables set
- Host connectivity (unless --no-ping)

### run - Execute benchmarks

**Common options:**
- `--suite/-s` (required) - Suite name
- `--model/-m` - Model ID (overrides suite default)
- `--cores/-c` - CPU core count
- `--workload/-w` - Workload type
- `--scenario` - Test scenario (audio suites)
- `--dry-run` - Print command without running
- `--skip-doctor` - Skip health checks

**LLM Examples:**

```bash
# Quick chat smoke test
./cpueval run --suite chat-smoke \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 16 \
  --workload chat

# Full 3-phase concurrent load test
./cpueval run --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --workload summarization

# Dry run to see command
./cpueval run --suite concurrent-load \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 16 \
  --dry-run
```

`--dry-run` prints the underlying Ansible command without executing:

```text
ansible-playbook -i .../inventory/hosts.yml .../llm-benchmark-auto.yml \
  -e workload_type=chat \
  -e test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  -e requested_cores=16
```

**Audio Examples:**

```bash
# Transcription throughput test
./cpueval run --suite audio \
  --model openai/whisper-small \
  --scenario transcription-throughput \
  --cores 32

# Quick audio test
./cpueval run --suite audio \
  --model openai/whisper-tiny \
  --scenario quick-test \
  --cores 16
```

**Embedding Example:**

```bash
./cpueval run --suite embedding \
  --model RedHatAI/granite-embedding-english-r2 \
  --cores 16
```

**Offline Batch Example:**

```bash
# Default: all 11 use cases, 3 runs each
./cpueval run --suite offline-batch

# All use cases, all RedHatAI models, 5 runs each
./cpueval run --suite offline-batch --mode use-cases --runs 5 --models all

# Single use case with core sweep
./cpueval run --suite offline-batch \
  --mode use-case-sweep \
  --use-case summarization \
  --models all \
  --cores 8,16,24,32 \
  --runs 3

# Fast smoke test (minimal tokens)
./cpueval run --suite offline-batch \
  --mode run_test \
  --model RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 \
  --dataset random \
  --num-prompts 3 \
  --cores 8 \
  --input-len 32 \
  --output-len 16

# Technical benchmarks
./cpueval run --suite offline-batch --mode batch-scaling --model <model> --cores 16

# RHAIIS container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./cpueval run --suite offline-batch --mode use-cases --runs 3 --models all
```

**Offline-batch flags:** `--mode`, `--runs`, `--use-case`, `--models`/`--model`,
`--cores`, `--dataset`, `--num-prompts`, `--input-len`, `--output-len`.
Escape hatch: `--extra args="..."`.

**Core Sweep (Multiple Core Counts):**

```bash
# Test with multiple core counts in one run
./cpueval run --suite concurrent-load \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --extra core_sweep_counts="[8,16,32,64]" \
  --workload chat

# Single core count (use --cores for clarity)
./cpueval run --suite concurrent-load \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 16 \
  --workload chat
```

**RHAIIS Quantized Models:**

```bash
# RHAIIS models work with standard concurrent-load suite
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

./cpueval run --suite concurrent-load \
  --model RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 \
  --cores 16 \
  --workload chat

# Core sweep with RHAIIS
./cpueval run --suite concurrent-load \
  --model RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 \
  --extra core_sweep_counts="[8,16,32]" \
  --workload chat
```

### CPU Pinning

**Simple pinning via CLI flags:**

```bash
./cpueval run --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --vllm-cpu-start 64 \
  --vllm-numa 1 \
  --guidellm-cpus 0-31 \
  --guidellm-numa 0
```

**Using a profile:**

```bash
./cpueval run --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --profile dual-socket-split
```

**Advanced: extra vars:**

```bash
./cpueval run --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --extra vllm_cpu_start=64 \
  --extra vllm_numa_node=1

# Or from a file
./cpueval run --suite concurrent-load \
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
```

Example output (`./cpueval results --last`):

```text
Results: results/llm/Qwen__Qwen2.5-0.5B-Instruct/chat-20260729-165311/32cores-numa2-tp1

┌───────────┬────────────────────────────┐
│ Model     │ Qwen/Qwen2.5-0.5B-Instruct │
│ Workload  │ chat                       │
│ Timestamp │ 2026-07-29T17:26:30+01:00  │
│ Cores     │ 32                         │
└───────────┴────────────────────────────┘

┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Concurrency ┃ Req/s ┃   Tok/s ┃ TTFT (ms) ┃ TPOT (ms) ┃ Requests ┃
┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ 1           │  0.10 │  106.37 │     53.48 │     19.34 │    26/26 │
│ 8           │  0.67 │  710.55 │    142.20 │     23.14 │  168/168 │
│ 32          │  1.47 │ 1585.99 │    199.50 │     41.36 │  384/384 │
└─────────────┴───────┴─────────┴───────────┴───────────┴──────────┘
```

Example output (`./cpueval results --list`):

```text
Recent results (10)

  Qwen__Qwen2.5-0.5B-Instruct/chat-20260729-165311/32cores-numa2-tp1
  Qwen__Qwen2.5-0.5B-Instruct/summarization-20260729-165210/32cores-numa0-tp1
  Qwen__Qwen2.5-0.5B-Instruct/chat-20260729-161939/16cores-numa2-tp1
  ...
```

Results display includes:
- Model, workload, timestamp, cores
- **All concurrency points** (not just first)
- Requests/sec, Tokens/sec, TTFT (ms), TPOT (ms)
- Request success/total counts

### dashboard - Manage Streamlit dashboard

```bash
# Start dashboard in background (port 8501)
./cpueval dashboard start

# Stop running dashboard
./cpueval dashboard stop
```

Launches the interactive results dashboard in your browser. You can also open it
via `./cpueval results --open`.

## Available Suites

### Matrix Suites (run full test matrix by default)

| Suite | Default Matrix | Description |
|-------|----------------|-------------|
| `rhaiis-sweep` | 5 models × 3 cores × 4 workloads | RHAIIS model concurrent load sweep (60 tests) |
| `embedding` | 5 models × 3 cores × 2 scenarios | Embedding model performance matrix (30 tests) |
| `offline-batch` | 11 use-cases × 3 runs | Offline batch processing suite (33 tests) |
| `audio` | Configurable (models × scenarios × cores) | Audio model benchmarking (Whisper ASR) |

### Single-Shot Suites (require `--model`)

| Suite | Description |
|-------|-------------|
| `concurrent-load` | 3-phase concurrent load testing of one model (baseline, realistic, production) |
| `chat-smoke` | Quick auto-configured LLM chat test |
| `setup-platform` | Platform setup and configuration |
| `health` | Health check for DUT and load generator |

## Audio Test Scenarios

Available scenarios for the `audio` suite (`--scenario` flag):

- `transcription-throughput` - High-throughput ASR
- `transcription-latency` - Low-latency ASR
- `transcription-quality` - Quality-focused ASR
- `audio-duration-scaling` - Variable audio lengths
- `format-comparison` - Audio format comparison
- `constant-rate-stress` - Stress testing
- `quick-test` - Fast smoke test

## Creating Custom Suites

Create a YAML file in `automation/cli/suites/`:

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
./cpueval run --suite concurrent-load --model my-model --cores 32 --profile my-profile
```

## Architecture

cpueval is a **thin wrapper** that:
- Generates `ansible-playbook` commands from suite definitions
- Streams stdout/stderr (no log hiding)
- Does **NOT** reimplement deploy/GuideLLM/vLLM logic
- Provides progressive disclosure for CPU pinning

**Design principles:**
- Thin wrapper only (subprocess invocation, not Python reimplementation)
- Suites are YAML data, not hard-coded
- Env-based inventory
- Progressive disclosure (simple `--cores`, advanced pinning optional)

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

## Development

```bash
cd automation/cli

# Install in dev mode with test dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_results.py::test_extract_metrics_guidellm_v06 -v
```

## See Also

- [Test Suites Overview](test-suites.md) - All supported suites and how to choose
- [Getting Started Guide](getting-started.md) - Overall framework setup
- [Ansible Test Execution](ansible/test-execution.md) - Underlying playbooks
- [Dashboards Quickstart](dashboards-quickstart.md) - Results visualization
- [Terminal Results Viewer](terminal-results-viewer.md) - Alternative results viewer
