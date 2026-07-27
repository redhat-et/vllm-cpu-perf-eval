# cpueval - CPU Benchmarking CLI

Thin CLI wrapper for running full test matrices with easy overrides.

## Philosophy

**Matrix-first**: Most suites run comprehensive test matrices by default (models × cores × workloads). No `--model` required.

**Easy overrides**: Narrow the scope with simple flags when needed.

## Quick Start

```bash
# Matrix suites - run full test matrix (no --model required!)
./cpueval run --suite rhaiis-sweep           # 60 combinations: 5 models × 3 cores × 4 workloads
./cpueval run --suite embedding              # 20+ combinations: 5 models × 4 cores × scenarios
./cpueval run --suite offline-batch          # 55 runs: use-cases mode

# Override to narrow scope
./cpueval run --suite rhaiis-sweep --models tiny --cores 8
./cpueval run --suite embedding --models quick --cores 4

# Single-shot suites (require --model)
./cpueval run --suite chat-smoke --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 16

# Explore
./cpueval list                    # Shows Matrix vs Single type
./cpueval show rhaiis-sweep       # View default matrix
./cpueval results --last          # View results
```

## Installation

The `./cpueval` launcher automatically creates a virtual environment and installs dependencies on first run.

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
./cpueval run --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --vllm-cpu-start 96 \
  --vllm-numa 1 \
  --guidellm-cpus 0-31 \
  --guidellm-numa 0 \
  --extra guidellm_profile=concurrent \
  --extra guidellm_rate="[1,2,4,8,16,32]" \
  --extra test_name=EPYC-NO-SMT

# Or run full RHAIIS matrix (60 combinations)
./cpueval run --suite rhaiis-sweep \
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

### doctor - Health checks
```bash
# Full check (including host ping)
./cpueval doctor

# Skip ping (faster, good for CI)
./cpueval doctor --no-ping
```

### run - Execute benchmarks

**Common options:**
- `--suite/-s` (required) - Suite name
- `--model/-m` - Model ID
- `--cores/-c` - CPU core count
- `--workload/-w` - Workload type
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

# Transcription latency test
./cpueval run --suite audio \
  --model openai/whisper-medium \
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
./cpueval run --suite embedding \
  --model RedHatAI/granite-embedding-english-r2 \
  --cores 16
```

**RHAIIS Quantized Models:**

RHAIIS quantized models work with the standard concurrent-load suite:

```bash
# Test RHAIIS model with custom container
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

./cpueval run --suite concurrent-load \
  --model RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 \
  --cores 16 \
  --workload chat

# Test tiny quantized model
./cpueval run --suite concurrent-load \
  --model RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 \
  --cores 8 \
  --workload chat

# Core sweep with RHAIIS
./cpueval run --suite concurrent-load \
  --model RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 \
  --extra core_sweep_counts="[8,16,32]" \
  --workload chat
```

**Offline Batch Processing:**

```bash
# Offline batch processing (high-throughput static workloads)
./cpueval run --suite offline-batch \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 32 \
  --extra dataset_name=random \
  --extra num_prompts=100

# RHAIIS offline batch
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./cpueval run --suite offline-batch \
  --model RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 \
  --cores 16 \
  --extra dataset_name=sonnet
```

**Multi-model RHAIIS Sweeps:**

```bash
# Via cpueval (wraps bash script)
./cpueval run --suite rhaiis-sweep \
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

> **Customizing profiles:** Copy `automation/cli/profiles/dual-socket-split.yaml` to your project directory, modify the CPU pinning parameters, and use `--profile path/to/your-profile.yaml`

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

# Just convert, don't view
./cpueval results --last --convert --no-view
```

### dashboard - Launch Streamlit dashboard

```bash
./cpueval dashboard
```

## Available Suites

| Suite | Runner | Description |
|-------|--------|-------------|
| `concurrent-load` | ansible | 3-phase concurrent load testing (baseline, realistic, production) |
| `chat-smoke` | ansible | Quick auto-configured LLM chat test |
| `embedding` | ansible | Embedding model performance tests |
| `audio` | ansible | Audio model benchmarking (ASR, transcription, translation) |
| `offline-batch` | ansible | Offline batch processing (high-throughput static workloads) |
| `rhaiis-sweep` | script | Multi-model sweep for RHAIIS quantized models |
| `setup-platform` | ansible | Platform setup and configuration |
| `health` | ansible | Health check for DUT and load generator |

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
ansible-galaxy collection install containers.podman
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
# Tier 1 workloads: chat, code, summarization, rag
./cpueval run --suite concurrent-load \
  --extra models=all \
  --extra cores="8,16,32" \
  --extra workloads="chat,code,summarization,rag" \
  --extra phase=1

# ~6 models × 3 cores × 4 workloads = 72 tests (~6-8 hours)
```

**Day 3: Offline Batch Processing**
```bash
# All 11 enterprise use-cases, 3 runs each = 33 tests
./cpueval run --suite offline-batch \
  --extra args="use-cases 3"

# Enterprise Tier Priorities:
#   Tier 1 (Must-have): Summarization, Classification, RAG Batch, Entity Extraction
#   Tier 2 (High value): Long-Doc Summary, ETL, Short Labeling  
#   Tier 3 (Valuable): Code Gen, Translation, Dataset Gen
#   Tier 4 (Deprioritize): Shared-Prefix

# Run specific tier:
./cpueval run --suite offline-batch \
  --extra args="use-case-sweep summarization all 8,16,32 3"
```

**Day 4: Embedding Models**
```bash
# Small + fast models: all-MiniLM (22M), granite-english (109M)
./cpueval run --suite embedding \
  --extra models=small \
  --extra cores="8,16,32"

# ~2 models × 3 cores × 2 scenarios (baseline+latency) = 12 tests (~4-6 hours)
```

**Day 5: Audio Workloads**
```bash
# Whisper models: tiny, small, medium
./cpueval run --suite audio \
  --extra models=all \
  --extra scenarios=transcription-throughput \
  --extra cores="32"

# 3 models × 1 scenario × 1 core = 3 tests (~3-4 hours)
```

### Quick Smoke Test (AWS)

Verify everything works before starting week-long runs:

```bash
# 3-5 minute smoke test
./cpueval run --suite chat-smoke \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 8 \
  --skip-doctor
```

