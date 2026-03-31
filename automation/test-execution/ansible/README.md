# Ansible Playbook Structure

## Overview

This directory contains Ansible playbooks for automated vLLM performance testing with CPU core configuration sweeps.

## Quick Start

### Prerequisites

#### 1. Ansible Collections (Control Machine)

**On the machine where you run Ansible** (your local machine or jump host), install the required collections:

```bash
# Navigate to the ansible directory
cd automation/test-execution/ansible

# Install required Ansible collections
ansible-galaxy collection install -r requirements.yml

# Or install individually
ansible-galaxy collection install containers.podman ansible.posix
```

**Ansible Version Compatibility:**
- **Ansible 2.14.x**: Uses `requirements.yml` with pinned versions (containers.podman 1.9.x, ansible.posix 1.4.x-1.5.x)
- **Ansible 2.15+**: Recommended for latest features and security updates

To install Ansible:

```bash
# Via DNF (RHEL/CentOS)
sudo dnf install ansible-core

# Via pip
pip3 install --upgrade ansible-core
```

#### 2. System Packages (Target System)

**Option 1: Automated setup (Recommended)**

Use the platform setup playbook to install all required packages and configure optimal performance settings:

```bash
ansible-playbook -i inventory/hosts.yml setup-platform.yml
```

This installs: `podman`, `numactl`, `tuned`, `kernel-tools`, and configures CPU isolation, performance governor, and systemd CPU pinning.

**Option 2: Manual installation**

If you prefer manual setup, install the required packages:

```bash
# Install required system utilities (RHEL/CentOS/Fedora)
sudo dnf install -y podman rsync python3 numactl
```

#### 3. Verify Installation

```bash
# On control machine: Check Ansible collections
ansible-galaxy collection list

# On target system: Verify system packages
podman --version
rsync --version
```

## Playbook Hierarchy

### Single Test Playbooks ✅

| Playbook | Purpose | Config Type | Status |
|----------|---------|-------------|---------|
| **llm-benchmark-auto.yml** | Single LLM test | Auto (provide core count) | ✅ Working |
| **llm-benchmark.yml** | Single LLM test | Manual (pre-defined config) | ✅ Working |
| **embedding-benchmark.yml** | Single embedding test | Manual | ⚠️ Needs updates |

### Core Sweep Orchestration ✅

| Component | Purpose | Type | Status |
|----------|---------|------|---------|
| **llm-core-sweep-auto.yml** | Auto sweep (Ansible interface) | Ansible playbook | ✅ Working |
| **scripts/run-core-sweep.sh** | Auto sweep (direct CLI) | Bash script | ✅ Working |
| **llm-benchmark-auto.yml** | Single iteration playbook (with shared test_run_id) | Ansible | ✅ Working |
| **collect-sweep-results.yml** | Results collection | Ansible | ✅ Working |

## Core Sweep Architecture

### How It Works

Core sweeps are orchestrated using a **bash script** that calls a simplified playbook multiple times. This approach works around Ansible's limitation that task files cannot contain playbook-level constructs (hosts:, roles:).

### Components

1. **run-core-sweep.sh** - Main orchestrator
   - Loops over core counts
   - Calls llm-benchmark-auto.yml for each iteration
   - Maintains single test_run_id across all iterations
   - Calls collect-sweep-results.yml at the end

2. **llm-benchmark-auto.yml** - Unified playbook for single and sweep tests
   - Accepts optional test_run_id parameter
   - Auto-generates test_run_id if not provided (single test mode)
   - Uses provided test_run_id when passed in (sweep iteration mode)
   - Results go to `workload-runid/cores_N/` subdirectories in sweep mode

3. **collect-sweep-results.yml** - Results collector
   - Fetches all results from sweep
   - Copies GuideLLM logs for all configurations
   - Extracts per-benchmark timings for all configurations

### Common Tasks

**Location:** `playbooks/common/tasks/`

- **`detect-numa-topology.yml`** - Detects NUMA topology on DUT
- **`allocate-cores-from-count.yml`** - Allocates cores from detected topology
- **`setup-hf-token-optional.yml`** - Sets up HuggingFace token
- **`setup-vllm-api-key.yml`** - Sets up vLLM API key

### Helper Scripts

**Location:** `scripts/`

- **`extract_benchmark_timings.py`** - Extracts per-benchmark timing data from benchmarks.json

## Test Metadata Features ✅

All test playbooks now include:

1. **Test Metadata** (`test-metadata.json`)
   - Test run ID
   - Configuration details (cores, CPUs, NUMA, TP)
   - Model and workload info
   - Timestamp
   - Test duration (total and per-benchmark)
   - Configuration type (auto/manual)

2. **GuideLLM Logs** (`guidellm.log`)
   - Full execution logs
   - Automatically copied to results

3. **Per-Benchmark Timings**
   - Individual benchmark durations
   - Warmup/cooldown times
   - Request counts (successful/total)
   - Automatically extracted and added to metadata

## Usage Examples

### Single Test (Auto Mode)

```bash
ansible-playbook llm-benchmark-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores=16" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,8,16]"
```

### Core Sweep (Auto Mode) - RECOMMENDED

**Option 1: Via Ansible playbook (maintains consistent interface)**
```bash
ansible-playbook llm-core-sweep-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores_list=[2,4,8,16]"
```

**Option 2: Direct bash script (simpler for CLI use)**
```bash
./scripts/run-core-sweep.sh \
  TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  chat \
  "2,4,8,16"
```

**With additional parameters:**
```bash
ansible-playbook llm-core-sweep-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores_list=[8,16,32,64]" \
  -e "guidellm_profile=concurrent" \
  -e "guidellm_rate=[1,8,16]"
```

**With verbosity (shows detailed task execution):**
```bash
# Option 1: Via Ansible playbook
ansible-playbook llm-core-sweep-auto.yml \
  -e "test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  -e "workload_type=chat" \
  -e "requested_cores_list=[8,16]" \
  -e "inner_verbosity=-vv"

# Option 2: Via bash script
./scripts/run-core-sweep.sh \
  TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  chat \
  "8,16" \
  -vv
```

## Results Structure

### Single Test Results

```
results/llm/
└── {model_name}/
    └── {workload}-{runid}/
        ├── benchmarks.json      # GuideLLM results
        ├── benchmarks.csv
        ├── benchmarks.html
        ├── guidellm.log         # ✅ Execution logs
        ├── test-metadata.json   # ✅ Test metadata + timings
        ├── vllm-server.log      # Server logs
        └── system-metrics.log   # System metrics
```

### Core Sweep Results

```
results/llm/
└── {model_name}/
    └── {workload}-{runid}/
        ├── cores_2/
        │   ├── benchmarks.json
        │   ├── benchmarks.csv
        │   ├── benchmarks.html
        │   ├── guidellm.log
        │   ├── test-metadata.json
        │   ├── vllm-server.log
        │   └── system-metrics.log
        ├── cores_4/
        │   └── (same structure)
        ├── cores_8/
        │   └── (same structure)
        └── cores_16/
            └── (same structure)
```

> **Note:** `benchmarks.html` files shown in the directory structures above are
> not currently generated. HTML output is available in GuideLLM but not enabled
> in this environment. See [GuideLLM issue #627](https://github.com/vllm-project/guidellm/issues/627).
> JSON and CSV formats are fully functional.

## Design Decisions

### Why Bash Orchestration Instead of Pure Ansible?

Ansible has architectural limitations:
- Task files cannot contain playbook-level constructs (`hosts:`, `roles:`, `import_playbook`)
- Loops with `include_role` have limitations around delegation and become privileges
- Bash orchestration provides clearer control flow and is easier to debug

Benefits of the bash approach:
- Each iteration is a complete, independent playbook run
- Easier to parallelize in the future (run multiple core counts concurrently)
- Simpler error handling and recovery
- More flexibility for complex sweep patterns

## Extensibility for Embedding Tests

To extend for embedding tests:
1. Update `embedding-benchmark-auto.yml` to accept optional test_run_id (same pattern as llm-benchmark-auto.yml)
2. Create `scripts/run-embedding-sweep.sh` (similar to run-core-sweep.sh)
3. Update `collect-sweep-results.yml` to handle embedding benchmark format
4. Set `benchmark_type: "embedding"` to route to appropriate benchmark role

## Recent Improvements

1. **Localhost Configuration** - Fixed sudo password errors on delegated tasks
2. **Log Collection** - GuideLLM logs now copied to final results
3. **Duration Extraction** - Test duration added to metadata (HH:MM:SS and seconds)
4. **Per-Benchmark Timings** - Detailed timing data for each benchmark iteration
5. **Core Sweep Orchestration** - Bash wrapper for reliable multi-configuration testing
