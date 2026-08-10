
# cpueval CLI

Matrix-first CLI for running comprehensive CPU benchmarks. Most suites run full test matrices by default—no `--model` required!

## Philosophy

- **Matrix suites** run complete test matrices (models × cores × workloads/scenarios) by default
- **Easy overrides** to narrow scope when needed
- **Single-shot suites** for targeted deep testing

## Quick Start

```bash
# Matrix suites - run full matrices (no --model required!)
./cpueval --suite rhaiis-sweep           # 60 combinations: 5 models × 3 cores × 4 workloads
./cpueval --suite embedding              # 30 combinations: 5 models × 3 cores × 2 scenarios
./cpueval --suite offline-batch          # 33 runs: use-cases 3
./cpueval --suite audio                  # Default: all models, transcription-throughput scenario, 32 cores

# Override to narrow
./cpueval --suite rhaiis-sweep --models tiny --cores 8
./cpueval --suite embedding --models quick --cores 4

# Single-shot suites (--model required)
./cpueval --suite chat-smoke --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --cores 8

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

## Shell Completion

cpueval supports tab-completion for bash, zsh, and fish. Run once after installation:

```bash
./cpueval --install-completion
```

Restart your shell (or run `exec zsh` / `exec bash`) and completion is active.

**What completes:**

| Typing… | Completes with… |
|---------|-----------------|
| `cpueval run --suite <TAB>` | `audio`, `chat-smoke`, `concurrent-load`, … |
| `cpueval run --suite ch<TAB>` | `chat-smoke` |
| `cpueval run --model <TAB>` | model names discovered from `results/llm/` and `results/audio-models/` |
| `cpueval run --models Red<TAB>` | `RedHatAI/…` models |
| `cpueval run --profile <TAB>` | profile names from `automation/cli/profiles/` |
| `cpueval show <TAB>` | all suite names |

> **Note:** `--model` completion lists models you have already benchmarked (i.e. those with a results directory). It does not enumerate all possible HuggingFace model IDs.

**Show the completion script without installing** (useful for custom shell setups):

```bash
./cpueval --show-completion
```

**PATH requirement:** The `cpueval` command must be on your `PATH` for completion to work (the completion script calls `cpueval` internally). The simplest way is to add the repo root:

```bash
# Add to ~/.zshrc or ~/.bashrc
export PATH="$PATH:/path/to/vllm-cpu-perf-eval"
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

**External endpoint mode** (test existing vLLM server or load balancer):

```bash
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://your-vllm-host:8000
```

Or pass the URL per run with `--endpoint-url` (sets both variables automatically):

```bash
./cpueval --suite concurrent-load \
  --models tiny --cores 8 --workloads chat \
  --endpoint-url http://your-vllm-host:8080
```

### Scale-out workflow (nginx load balancer)

Use this when multiple vLLM instances sit behind a load balancer (for example after
`start-vllm-scaleout.yml` from the scale-out playbooks). cpueval does not deploy the
stack today — point benchmarks at the LB URL instead of a single managed instance.

```bash
# 1. Deploy scale-out on the DUT (Ansible; see docs/vllm-scaleout.md when merged)
ansible-playbook -i inventory/hosts.yml start-vllm-scaleout.yml \
  -e "scaleout_num_instances=3 scaleout_cores_per_instance=16"

# 2. Benchmark through the load balancer (port 8080 by default)
./cpueval --suite concurrent-load \
  --models tiny \
  --cores 32 \
  --workloads chat \
  --endpoint-url http://<DUT_HOSTNAME>:8080 \
  --skip-doctor

# 3. Narrow matrix while validating a new instance count
./cpueval --suite concurrent-load \
  --models TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 8 \
  --workload chat \
  --endpoint-url http://<DUT_HOSTNAME>:8080 \
  --extra guidellm_profile=synchronous \
  --extra guidellm_max_seconds=120 \
  --skip-doctor

# 4. Tear down when done
ansible-playbook -i inventory/hosts.yml stop-vllm-scaleout.yml
```

In external mode, `--cores`, `--vllm-cpus`, `--vllm-cpu-start`, and `--profile` pinning
are ignored (the endpoint manages its own CPUs). GuideLLM still runs on the load
generator with normal inventory settings.

> **Note:** `--vllm-cpu-start` is deprecated. Use `--vllm-cpus RANGE` instead to
> specify an explicit CPU set (e.g., `--vllm-cpus 64-95`). The legacy option still
> works but will emit a deprecation warning.

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

Suite definition: .../automation/cli/src/cpueval/suites/rhaiis-sweep.yaml
Edit that file to change permanent defaults.
```

> **Tip:** The suite YAML path is printed at the bottom of every `show` output. Edit it to
> permanently change defaults; use CLI flags (e.g. `--cores`) to override for a single run.

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

### Execute benchmarks

> `cpueval run --suite …` is also accepted for backward compatibility.

**Common options:**
- `--suite`/`-s` (required); Suite name
- `--model`/`-m`; Model ID (overrides suite default)
- `--cores`/`-c`; CPU core count
- `--workload`/`-w`; Workload type
- `--scenario`; Test scenario (audio suites)
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

`--dry-run` prints the underlying command without executing (ansible-playbook for ansible suites, bash script for script suites):

```text
ansible-playbook -i .../inventory/hosts.yml .../llm-benchmark-auto.yml \
  -e workload_type=chat \
  -e test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  -e requested_cores=16
```

**Audio Examples:**

```bash
# Transcription throughput test (single model)
./cpueval --suite audio \
  --models openai/whisper-small \
  --scenario transcription-throughput \
  --cores 32

# Quick audio test (single model)
./cpueval --suite audio \
  --models openai/whisper-tiny \
  --scenario quick-test \
  --cores 16
```

**Embedding Example:**

```bash
./cpueval --suite embedding \
  --model RedHatAI/granite-embedding-english-r2 \
  --cores 16
```

**Offline Batch Example:**

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

# Fast smoke test (minimal tokens)
./cpueval --suite offline-batch \
  --mode run_test \
  --model RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4 \
  --dataset random \
  --num-prompts 3 \
  --cores 8 \
  --input-len 32 \
  --output-len 16

# Technical benchmarks
./cpueval --suite offline-batch --mode batch-scaling --model <model> --cores 16

# RHAIIS container image
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
./cpueval --suite offline-batch --mode use-cases --runs 3 --models all
```

**Offline-batch flags:** `--mode`, `--runs`, `--use-case`, `--models`/`--model`,
`--cores`, `--dataset`, `--num-prompts`, `--input-len`, `--output-len`.
Escape hatch: `--extra args="..."`.

**Core Sweep (Multiple Core Counts):**

```bash
# Test with multiple core counts in one run
./cpueval --suite concurrent-load \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --extra core_sweep_counts="[8,16,32,64]" \
  --workload chat

# Single core count (use --cores for clarity)
./cpueval --suite concurrent-load \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 16 \
  --workload chat
```

**RHAIIS Quantized Models:**

```bash
# RHAIIS models work with standard concurrent-load suite
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0

./cpueval --suite concurrent-load \
  --model RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 \
  --cores 16 \
  --workload chat

# Core sweep with RHAIIS
./cpueval --suite concurrent-load \
  --model RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16 \
  --extra core_sweep_counts="[8,16,32]" \
  --workload chat
```

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

Pass the profile name (without `.yaml`) — cpueval looks it up in
`automation/cli/profiles/`. You can also pass a relative or absolute path to a
file anywhere on disk.

```bash
# Built-in profile (resolved from automation/cli/profiles/)
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --profile dual-socket-split

# Custom profile by path
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --profile ~/my-profiles/my-server.yaml
```

**Built-in profiles:**

| Profile | Use case |
|---------|----------|
| `dual-socket-split` | Dual-socket system — vLLM pinned to socket 1 (cores 64–95, NUMA 1), GuideLLM pinned to socket 0 (cores 0–31, NUMA 0) |

> **`vllm_cpus` vs `--cores`:** When a profile (or `--vllm-cpus`) sets `vllm_cpus`,
> it specifies a **fixed CPU set** for vLLM regardless of `--cores`. For example,
> `--profile dual-socket-split --cores 8` pins vLLM to all 32 cores in `64-95`, not
> 8 cores starting at 64. Use `vllm_cpus` when you want an explicit range; use
> `--cores` alone when you want count-based auto-allocation. The two modes are
> mutually exclusive: `vllm_cpus` always wins.

To list profiles available:

```bash
./cpueval profiles
```

**Advanced: extra vars:**

```bash
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --extra vllm_cpu_start=64 \
  --extra vllm_numa_node=1

# Or from a file (path relative to your current working directory, or absolute)
./cpueval --suite concurrent-load \
  --model meta-llama/Llama-3.2-1B-Instruct \
  --cores 32 \
  --extra-vars-file my-config.yaml        # relative to CWD
  # --extra-vars-file /path/to/my-config.yaml  # or absolute
```

**Precedence:** suite defaults → profile → CLI flags → --extra → --extra-vars-file

### profiles - List CPU pinning profiles

```bash
./cpueval profiles
```

Lists all profiles available in `automation/cli/profiles/`, showing their name and
file path. Use the name with `--profile` when running a suite.

Example output:

```text
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name                      ┃ Path                                             ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ dual-socket-split         │ .../automation/cli/profiles/dual-socket-split... │
└───────────────────────────┴──────────────────────────────────────────────────┘
```

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
| `concurrent-load` | all models × 3 cores × 4 workloads (60 tests) | Upstream LLM concurrent load sweep |
| `embedding` | 5 models × 3 cores × 2 scenarios | Embedding model performance matrix (30 tests) |
| `offline-batch` | 11 use-cases × 3 runs | Offline batch processing suite (33 tests) |
| `audio` | all models × `transcription-throughput` × 32 cores | Audio model benchmarking (Whisper ASR) |

### Single-Shot Suites (require `--model`)

| Suite | Description |
|-------|-------------|
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

## Testing custom models

Every suite accepts an arbitrary HuggingFace model ID — no changes to any YAML files are needed.

### LLM suites (concurrent-load, rhaiis-sweep, chat-smoke, offline-batch)

Pass any HuggingFace model ID directly:

```bash
# Single-shot test
./cpueval --suite chat-smoke \
  --model my-org/my-llm-model \
  --cores 32 \
  --workload chat

# Concurrent load against a custom model
./cpueval --suite concurrent-load \
  --model my-org/my-llm-model \
  --cores 16 \
  --workload chat

# Offline batch — use-cases mode (comma-separated list also works)
./cpueval --suite offline-batch \
  --mode use-cases \
  --models my-org/my-llm-model \
  --runs 3

# Offline batch — single benchmark mode
./cpueval --suite offline-batch \
  --mode batch-scaling \
  --model my-org/my-llm-model \
  --cores 32
```

> **Gated models:** set `export HF_TOKEN=hf_xxxxx` before running.

### Audio suite

Whisper is the default but any vLLM-compatible audio model works. Non-Whisper models
typically need a larger `max_model_len` (Whisper's encoder cap is 448 tokens) and
may require an explicit `dtype`:

```bash
# Whisper model — defaults work, no overrides needed
./cpueval --suite audio \
  --models openai/whisper-small \
  --scenario transcription-throughput \
  --cores 32

# Non-Whisper audio model — override max_model_len and dtype
./cpueval --suite audio \
  --models fixie-ai/ultravox-v0_5-llama-3_2-1b \
  --extra dtype=bfloat16 \
  --extra max_model_len=2048 \
  --scenario transcription-throughput \
  --cores 32
```

| Extra var | Bash flag | When to use |
|---|---|---|
| `dtype=float16\|bfloat16\|auto` | `--dtype` | Non-Whisper models that recommend a specific dtype |
| `max_model_len=N` | `--max-model-len` | Any model whose max sequence length differs from Whisper's 448 |

### Embedding suite

```bash
./cpueval --suite embedding \
  --model my-org/my-embedding-model \
  --cores 16
```

### Optional: register the model for KV cache metadata

Running with a custom model ID works immediately. To also get accurate KV cache
sizing (rather than the 40 GiB fallback) and include the model in future
`--models all` sweeps, add an entry to the relevant model matrix:

- LLM models: [models/llm-models/model-matrix.yaml](../models/llm-models/model-matrix.yaml)
- Embedding models: [models/embedding-models/model-matrix.yaml](../models/embedding-models/model-matrix.yaml)
- Audio models: [models/audio-models/model-matrix.yaml](../models/audio-models/model-matrix.yaml)

See [models/models.md](../models/models.md) for the full schema and instructions.

## Creating Custom Suites

You can also edit an existing suite YAML directly to change its permanent defaults
(e.g. to add a new core count or workload to the default matrix) rather than creating
a new suite from scratch.

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

## Architecture

cpueval is a **thin wrapper** that:
- Generates `ansible-playbook` commands from suite definitions;
- Streams stdout/stderr (no log hiding);
- Does **NOT** reimplement deploy/GuideLLM/vLLM logic;
- Provides progressive disclosure for CPU pinning.

**Design principles:**
- Thin wrapper only (subprocess invocation, not Python reimplementation);
- Suites are YAML data, not hard-coded;
- Env-based inventory;
- Progressive disclosure (simple `--cores`, advanced pinning optional).

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
