---
layout: default
title: vLLM Scale-Out Deployment (llm-d)
---

## vLLM Scale-Out Deployment

Deploy and benchmark multiple vLLM instances with intelligent routing via
[llm-d](https://llm-d.ai) (EPP + Envoy) — no Kubernetes required.

## Overview

The scale-out deployment runs N vLLM instances on a single DUT with configurable:

- **Number of instances** (1-10)
- **Cores per instance** (8, 16, or 32 cores)
- **SMT/HyperThreading** (enable/disable)
- **Prefix caching** (enable/disable)
- **Routing policy** (`intelligent` EPP or `round_robin` — benchmarkable)
- **Test type** (online inference, embedding, audio/ASR)

### Architecture

```
┌─────────────────────────────────────────┐
│  Load Generator Host                    │
│  • GuideLLM concurrent tests            │
└─────────────────────────────────────────┘
              │
              ▼ :8081
┌─────────────────────────────────────────┐
│  DUT Host (Remote)                      │
│  ┌───────────────────────────────────┐  │
│  │ Envoy proxy (:8081)               │  │
│  └──────────────┬────────────────────┘  │
│                 │ gRPC ext_proc         │
│  ┌──────────────▼────────────────────┐  │
│  │ EPP — Endpoint Picker             │  │
│  │ Scores by: prefix-cache + queue   │  │
│  │           + KV utilisation        │  │
│  └──────┬────────────────────────────┘  │
│         │ x-gateway-destination-endpoint│
│    ┌────▼────┐ ┌────────┐ ┌────────┐   │
│    │ vLLM 1  │ │ vLLM 2  │ │ vLLM N │  │
│    │ :8000   │ │ :8001   │ │ :800N  │  │
│    │ 32 core │ │ 32 core │ │32 core │  │
│    └─────────┘ └─────────┘ └────────┘  │
└─────────────────────────────────────────┘
```

**Key Points:**
- All vLLM instances run on **one DUT host** with host networking, each on a sequential port
- EPP (Endpoint Picker) makes routing decisions using vLLM `/metrics` data
- GuideLLM connects to **Envoy at port 8081** (same API as single-instance port 8000)
- `round_robin` mode skips the EPP entirely — useful for benchmarking routing overhead

### Routing Modes

| Policy | Component | Selection Strategy |
|---|---|---|
| `intelligent` (default) | EPP + Envoy | Prefix-cache hits (3×) + queue depth (2×) + KV utilisation (2×) |
| `round_robin` | Envoy only | Even distribution across all instances; EPP not started |

Use both in separate runs to measure the overhead and benefit of intelligent routing.

---

## Deployment Modes

The scale-out playbooks support three inventory configurations:

| Mode | DUT | Load Generator | Notes |
|------|-----|----------------|-------|
| **Fully local** | `localhost` | `localhost` | Everything on one machine; simplest for development/CI |
| **Single test host** | remote host | same remote host | Controller is a separate machine; DUT handles both vLLM and GuideLLM |
| **Multi-host** | GPU/CPU server | separate loadgen | Classic production split; highest isolation |

In all modes the integrated benchmark playbooks (`embedding-benchmark-scaleout.yml` etc.)
point GuideLLM at `http://DUT:8081` and scrape per-instance metrics from the controller
→ `http://DUT:800N/metrics`. If `groups['dut'][0]` is `localhost`, scraping happens
locally with zero extra network hops.

---

## Results Directory Structure

Scale-out runs use the same directory layout as single-instance runs:

```
results/
  embedding/
    RedHatAI__granite-embedding-english-r2/
      scaleout-20261006-120000/        ← test_run_id has "scaleout-" prefix
        test-metadata.json             ← includes deployment_type, num_instances, routing_policy
        latency/                       ← GuideLLM results
        vllm-metrics-instance-1.json   ← per-backend vLLM Prometheus time-series
        vllm-metrics-instance-2.json
        …
        epp-metrics.json               ← EPP routing metrics (intelligent routing only)
        container-stats-scaleout.jsonl ← container CPU + memory (all instances, EPP, Envoy)
```

`test-metadata.json` for scale-out runs contains:

```json
{
  "deployment_type": "scaleout",
  "num_instances": 5,
  "routing_policy": "intelligent",
  "epp_scorer_weights": { "prefix_cache": 3, "queue": 2, "kv_cache": 2, "lru": 2 },
  "scaleout_envoy_port": 8081,
  "cores_per_instance": 32,
  "container_restarts_detected": false,
  "restarted_containers": []
}
```

`container_restarts_detected` / `restarted_containers` are set by the all-in-one
benchmark playbooks: containers use `restart: unless-stopped`, so a mid-benchmark
crash would otherwise restart silently and skew results. Restarts are flagged in the
playbook output and recorded here for post-hoc filtering of unreliable runs.

The **🖥️ Server Metrics** dashboard page (page 2) detects scale-out runs by the
`deployment_type` field and shows a summary with a link to page 8 for full analysis.
The **🔀 ScaleOut Routing** page (page 8) reads the `vllm-metrics-instance-*.json` files
directly for per-backend load charts and routing policy comparison.

---

## Quick Start

### Prerequisites

On the DUT:
```bash
pip3 install podman-compose
```

### Deploy

```bash
cd automation/test-execution/ansible

# Deploy with defaults (5 instances × 32 cores, intelligent EPP routing)
ansible-playbook start-vllm-scaleout.yml

# Custom instance count and routing policy
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_num_instances=3 scaleout_cores_per_instance=16 scaleout_routing_policy=round_robin"
```

Deployment validates itself before reporting success: it fails fast if `podman-compose up`
errors, verifies all requested CPU cores exist and that container cpuset pinning took
effect, and sends an end-to-end smoke request through Envoy (and EPP when intelligent
routing is enabled) so routing misconfigurations surface before benchmarking. A failed
deploy tears itself down automatically. Smoke requests are skipped for transcription
(`--task transcription`) models, which need audio input.

### Benchmark (all-in-one)

```bash
# Embedding benchmark — deploy, test, teardown
ansible-playbook embedding-benchmark-scaleout.yml \
  -e "scaleout_num_instances=3"

# LLM inference benchmark
ansible-playbook llm-benchmark-scaleout.yml

# Audio/ASR benchmark (Whisper models)
ansible-playbook audio-benchmark-scaleout.yml \
  -e "scaleout_model_name=openai/whisper-large-v3"
```

### Health Check

```bash
# Inference endpoint (via Envoy)
curl http://DUT_IP:8081/health
curl http://DUT_IP:8081/v1/models

# Envoy admin (cluster status, live stats)
curl http://DUT_IP:19000/ready
curl http://DUT_IP:19000/stats | grep -E "upstream|cx_total"

# EPP Prometheus metrics (routing decisions)
curl http://DUT_IP:9090/metrics | grep -E "epp|endpoint"
```

### Stop

```bash
# Stop (keep HF model cache)
ansible-playbook stop-vllm-scaleout.yml

# Stop and remove everything including model cache
ansible-playbook stop-vllm-scaleout.yml -e "scaleout_purge_model_cache=true"
```

---

## Configuration

### Core Parameters

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `scaleout_num_instances` | 5 | 1-10 | Number of vLLM instances |
| `scaleout_cores_per_instance` | 32 | 8, 16, 24, 32 | CPU cores per instance |
| `scaleout_routing_policy` | `intelligent` | `intelligent`, `round_robin` | Routing mode |
| `scaleout_vllm_base_port` | 8000 | any | First vLLM instance port |
| `scaleout_envoy_port` | 8081 | any | Client-facing Envoy port |
| `scaleout_enable_smt` | false | true/false | Enable SMT/HT cores |
| `scaleout_enable_prefix_caching` | true | true/false | Enable vLLM prefix caching |

Defaults shown are the Ansible playbook defaults (large server, cores pinned from 32).
The `cpueval` CLI suite (`vllm-scaleout`) uses lighter defaults — 2 instances × 24 cores
from core 0 — for quicker CLI-driven runs; override either with `-e`/`--extra` as needed.

### Model / Task Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `scaleout_model_name` | from `test_model` | HuggingFace model ID or local path |
| `scaleout_vllm_task` | (auto) | vLLM `--task` flag; set `embed` for encoder-only or `transcription` for Whisper |
| `scaleout_vllm_max_model_len` | (model default) | Cap context window; 512 recommended for embedding |

### EPP Scorer Weights (intelligent routing only)

| Parameter | Default | Effect |
|-----------|---------|--------|
| `scaleout_epp_prefix_cache_weight` | 3 | Steer to backend with matching KV cache prefix |
| `scaleout_epp_queue_weight` | 2 | Steer away from busy backends |
| `scaleout_epp_kv_cache_weight` | 2 | Steer away from high KV pressure |
| `scaleout_epp_lru_weight` | 2 | LRU fallback for cache misses |

Set all weights to 1 for load-aware round-robin (EPP running, but no strong affinity).

---

## LMCache: Cross-Instance KV Sharing

### Overview

By default, each vLLM instance holds its own independent KV cache.  The EPP
routes requests with prefix affinity to maximise per-instance cache hits, but
any request that lands on the wrong instance still recomputes from scratch.

**LMCache adds a shared pool** — a central in-memory KV block store that every
instance can read from and write to.  When an instance misses in its local KV
cache it checks the shared pool before recomputing; when it evicts a block it
pushes it to the pool for others.

This is implemented via vLLM's V1 KV connector API (`--kv-transfer-config`).
The vLLM CPU backend uses the V1 engine exclusively and the connector is fully
supported — there are no CPU-specific restrictions.  `lmcache` is not bundled
in the vLLM image; the role pip-installs it at container start-up if absent.

### Architecture with LMCache

```
┌─────────────────────────────────────────────────────────────┐
│  Load Generator Host                                        │
│  • GuideLLM concurrent tests                                │
└─────────────────────────────────────────────────────────────┘
              │
              ▼ :8081
┌─────────────────────────────────────────────────────────────┐
│  DUT Host                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Envoy proxy (:8081)                                  │   │
│  └──────────────────┬──────────────────────────────────┘   │
│                     │ gRPC ext_proc                         │
│  ┌──────────────────▼──────────────────────────────────┐   │
│  │ EPP — two-tier prefix scoring                        │   │
│  │  Tier 1: local-prefix-cache-scorer  (weight 3)       │   │
│  │  Tier 2: lmcache-prefix-cache-scorer (weight 2)      │   │
│  │  + queue-scorer (2) + kv-utilisation (2) + LRU (2)  │   │
│  └────┬──────────────────────────────────────────────── ┘  │
│       │ x-gateway-destination-endpoint                      │
│  ┌────▼────┐ ┌─────────┐ ┌─────────┐                      │
│  │ vLLM 1  │ │ vLLM 2  │ │ vLLM N  │                      │
│  │ :8000   │ │ :8001   │ │ :800N   │                      │
│  │ LMCacheMP│ │ LMCacheMP│ │ LMCacheMP│                     │
│  │ Connector│ │ Connector│ │ Connector│                     │
│  └────┬────┘ └────┬────┘ └────┬────┘                      │
│       │           │           │  lmcache_driven             │
│       │      POSIX shared memory handles (zero-copy)        │
│       └───────────┴──────────┬────────────────────────     │
│                               ▼                             │
│  ┌────────────────────────────────────────────────────┐    │
│  │ lmcache-server (:5555)                             │    │
│  │ Shared in-memory KV pool (L1: 10 GB default)       │    │
│  │ Backed by 1 GB hugepages (if enabled)              │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### How LMCache and llm-d Routing Work Together

The EPP and LMCache operate at different layers and complement each other:

**EPP (routing layer)** decides *which* vLLM instance receives each request
before inference starts.  It maintains an approximate index of which blocks are
cached where, using two scorers in LMCache mode:

| Scorer | Tracks | Weight |
|--------|--------|--------|
| `local-prefix-cache-scorer` | Blocks in each instance's own vLLM KV cache | 3 (highest) |
| `lmcache-prefix-cache-scorer` | Blocks in the shared lmcache pool | 2 |
| `queue-scorer` | Request queue depth per backend | 2 |
| `kv-cache-utilization-scorer` | KV memory pressure per backend | 2 |
| `no-hit-lru-scorer` | LRU fallback (cold start) | 2 |

**LMCache (cache layer)** acts *during* inference when vLLM looks up KV blocks.
After the EPP has selected an instance, that instance resolves the request:

```
Request lands on vLLM instance N
  │
  ├── Local KV cache HIT  →  use it immediately (fastest, no IPC)
  │
  ├── Local KV cache MISS → LMCacheMPConnector checks the shared pool
  │     ├── Pool HIT  →  load block via POSIX shared-memory handle (zero-copy)
  │     │               (~RAM bandwidth, microsecond IPC overhead)
  │     └── Pool MISS →  recompute prefix from scratch
  │                       → store block in local KV cache
  │                       → push block to shared pool for other instances
  └── Response returned to client
```

**Why PYTHONHASHSEED=123 matters:** vLLM uses Python's `hash()` to derive KV
block addresses from token sequences.  Without a fixed seed each process uses a
different hash, so instance A and instance B assign different addresses to the
same prefix — the pool index becomes incoherent and cross-instance hits are
impossible.  All containers share `PYTHONHASHSEED=123`.

**Why vLLM prefix caching must be disabled:** vLLM's own prefix caching
(`--enable-prefix-caching`) operates on the same KV block structures that
LMCacheMPConnector manages.  Running both simultaneously causes double-tracking
and correctness issues.  `--no-enable-prefix-caching` and
`--disable-hybrid-kv-cache-manager` are set automatically when
`scaleout_lmcache_backend=remote`.  `scaleout_enable_prefix_caching` is ignored.

### Hugepages

The lmcache-server allocates a shared memory pool (default 10 GB) that all N
vLLM instances `mmap` concurrently.  With default 4 KB pages a 10 GB pool
requires ~2.6 million TLB entries per process — far beyond any modern CPU TLB
(~1 K–4 K entries).  Every TLB miss triggers a page-table walk, adding latency
and bus traffic under high-concurrency inference.

| Page size | TLB entries for 10 GB pool | Outcome |
|-----------|---------------------------|---------|
| 4 KB (default) | 2,621,440 | Heavy TLB thrashing under load |
| 2 MB (THP) | 5,120 | Significant improvement, no config needed |
| **1 GB** | **10** | **TLB pressure eliminated** |

**1 GB hugepages** (`scaleout_lmcache_hugepages_enabled=true`):

1. Requires `pdpe1gb` CPUID flag — present on all modern Intel Xeon and AMD EPYC.
2. Must be pre-allocated before memory becomes fragmented (early in the OS
   lifecycle, or at boot via `hugepages=N` in the kernel command line).
3. The role allocates pages, mounts `hugetlbfs` at `/dev/hugepages1G`, and binds
   it into the lmcache-server container.
4. The lmcache server uses them if it calls `mmap(MAP_HUGETLB | MAP_HUGE_1GB)`
   internally; this is version-dependent.
5. **Transparent Hugepages (`THP=always`) is always enabled as a baseline** —
   the kernel promotes eligible 2 MB regions automatically with no app changes,
   benefiting both the shared pool and each instance's vLLM KV cache space.

For best results, pre-allocate hugepages at boot by adding to the kernel command
line:

```
hugepagesz=1G hugepages=<N>
```

where N ≥ `scaleout_lmcache_server_l1_size_gb`.  Runtime allocation
(`nr_hugepages`) succeeds only when the system has not yet been fragmented by
other workloads — reboot if the allocation falls short.

### LMCache Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `scaleout_lmcache_backend` | `none` | `none` (disabled) or `remote` (lmcache-server) |
| `scaleout_lmcache_server_port` | 5555 | RPC port vLLM instances connect to |
| `scaleout_lmcache_server_http_port` | 8088 | HTTP metrics / bench port |
| `scaleout_lmcache_server_l1_size_gb` | 10 | Shared in-memory pool size (GB) |
| `scaleout_lmcache_lru_capacity_per_server` | 10000 | EPP LRU index size (blocks) — set manually |
| `scaleout_lmcache_scorer_weight` | 2 | EPP weight for the lmcache pool tier scorer |
| `scaleout_lmcache_hugepages_enabled` | false | Pre-allocate 1 GB hugepages + enable THP |
| `scaleout_lmcache_hugepages_1g_count` | `= l1_size_gb` | Number of 1 GB pages to pre-allocate |

**Sizing `lruCapacityPerServer`:** the EPP tracks pool state via an LRU index
sized in KV blocks.  A rough formula:

```
lruCapacityPerServer = (server_l1_size_gb × 1024) / avg_kv_block_size_mb
```

For most CPU embedding models, `avg_kv_block_size_mb ≈ 0.5–1 MB`, giving
10,000–20,000 blocks for a 10 GB pool.

### Quick Start

```bash
# Minimum — LMCache with default 10 GB pool, no hugepages
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_lmcache_backend=remote"

# Recommended — LMCache + 1 GB hugepages (pre-allocate N pages ≥ pool size)
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_lmcache_backend=remote \
      scaleout_lmcache_server_l1_size_gb=20 \
      scaleout_lmcache_hugepages_enabled=true \
      scaleout_lmcache_hugepages_1g_count=20"

# Full benchmark — deploy, test, teardown
ansible-playbook embedding-benchmark-scaleout.yml \
  -e "scaleout_lmcache_backend=remote \
      scaleout_lmcache_hugepages_enabled=true"
```

### LMCache Observability

```bash
# lmcache-server HTTP metrics
curl http://DUT_IP:8088/metrics

# LMCache metrics on each vLLM instance (reported via PROMETHEUS_MULTIPROC_DIR)
curl http://DUT_IP:8000/metrics | grep lmcache

# Hugepages status
cat /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages   # allocated
cat /sys/kernel/mm/hugepages/hugepages-1048576kB/free_hugepages # available
cat /sys/kernel/mm/transparent_hugepage/enabled                  # THP state
```

Key LMCache Prometheus metrics:

| Metric | What it shows |
|--------|---------------|
| `lmcache:retrieve_hit_rate` | Pool hit rate per vLLM instance |
| `lmcache:local_storage_usage` | Pool utilisation (pool fill level) |
| `lmcache:local_cache_usage` | Per-instance local KV cache utilisation |

### Comparing LMCache vs Baseline

Run the same workload with and without LMCache to measure the benefit:

```bash
# Baseline — per-instance prefix caching, intelligent EPP routing
ansible-playbook embedding-benchmark-scaleout.yml \
  -e "scaleout_lmcache_backend=none scaleout_enable_prefix_caching=true"

# LMCache — shared pool, intelligent EPP routing
ansible-playbook embedding-benchmark-scaleout.yml \
  -e "scaleout_lmcache_backend=remote scaleout_lmcache_hugepages_enabled=true"
```

LMCache benefits are largest for workloads with **shared prefixes across
requests** — RAG system prompts, batch embedding with repeated document prefixes,
or any scenario where the prefix hit rate is currently limited by requests being
spread across instances.

---

## Benchmarking Routing Policies

To directly compare intelligent EPP routing vs round-robin:

```bash
# Round-robin baseline (no EPP)
ansible-playbook embedding-benchmark-scaleout.yml \
  -e "scaleout_routing_policy=round_robin scaleout_num_instances=5"

# EPP intelligent routing (default)
ansible-playbook embedding-benchmark-scaleout.yml \
  -e "scaleout_routing_policy=intelligent scaleout_num_instances=5"
```

Then open the **Scale-Out Routing** page in the Streamlit dashboard to compare
load distribution and prefix-cache hit rates side by side.

### EPP Weight Tuning

```bash
# Emphasise queue depth over prefix cache (high-concurrency, short requests)
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_epp_prefix_cache_weight=1 scaleout_epp_queue_weight=4"

# Emphasise prefix cache (RAG workloads with shared system prompts)
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_epp_prefix_cache_weight=5 scaleout_epp_queue_weight=1"
```

---

## Test Types

### Online Inference (LLM)

```bash
ansible-playbook llm-benchmark-scaleout.yml
ansible-playbook llm-benchmark-scaleout.yml \
  -e "scaleout_model_name=RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
```

### Embedding

```bash
ansible-playbook embedding-benchmark-scaleout.yml \
  -e "scaleout_model_name=RedHatAI/granite-embedding-english-r2 \
      scaleout_vllm_max_model_len=512"
```

### Audio / ASR (Whisper)

Prefix caching is not effective for audio — EPP scoring still runs but will rely
on queue-depth and KV utilisation rather than prefix hits. `round_robin` is a
reasonable default for Whisper workloads.

```bash
ansible-playbook audio-benchmark-scaleout.yml \
  -e "scaleout_model_name=openai/whisper-large-v3 \
      scaleout_vllm_task=transcription \
      scaleout_enable_prefix_caching=false \
      scaleout_routing_policy=round_robin"
```

---

## Observability

### Live Metrics (Prometheus + Grafana)

Use `grafana/prometheus/prometheus-scaleout.yml` with the SSH tunnels described
in that file to scrape all vLLM instances, the EPP, and Envoy simultaneously.

### Post-Test Analysis (Streamlit)

Open the **🔀 Scale-Out Routing** page in the Streamlit dashboard
(`dashboard-examples/vllm_dashboard`) to visualise:

- Per-backend load distribution over time
- Prefix-cache hit rates per backend (EPP steering effectiveness)
- Routing balance score
- Side-by-side comparison of intelligent vs round-robin runs

### Key Endpoints

| Endpoint | Purpose |
|---|---|
| `http://DUT:8081/v1/...` | Client inference API (Envoy) |
| `http://DUT:19000/ready` | Envoy readiness |
| `http://DUT:19000/stats` | Envoy full stats |
| `http://DUT:19000/clusters` | Upstream cluster health |
| `http://DUT:9090/metrics` | EPP Prometheus metrics (routing decisions) |
| `http://DUT:8000/metrics` | vLLM instance 1 metrics |
| `http://DUT:800N/metrics` | vLLM instance N metrics |

---

## Management

### View Status

```bash
# All containers
podman ps

# Service logs
podman logs vllm-envoy -f          # Envoy access log
podman logs vllm-epp -f            # EPP routing decisions
podman logs vllm-instance-1 -f     # vLLM instance 1
```

### Restart Deployment

```bash
podman-compose -f /tmp/vllm-scaleout/docker-compose.yml restart
```

### Update Endpoints Without Restart (intelligent mode)

The EPP watches `/tmp/vllm-scaleout/epp-endpoints.yaml` and live-reloads on
atomic rename. To add/remove a backend without restarting:

```bash
# Edit endpoints and atomically replace
cp /tmp/vllm-scaleout/epp-endpoints.yaml /tmp/epp-endpoints.yaml.tmp
vim /tmp/epp-endpoints.yaml.tmp
mv /tmp/epp-endpoints.yaml.tmp /tmp/vllm-scaleout/epp-endpoints.yaml
# EPP logs: "endpoints file changed, reloading"
```

---

## Troubleshooting

### Deployment Fails

```bash
# Check prerequisites
podman-compose --version
lscpu  # Verify sufficient cores available
podman ps -a  # Check for conflicting containers

# Check port conflicts
ss -tlnp | grep -E "8000|8081|9002|9090|19000"
```

### EPP Won't Start

```bash
podman logs vllm-epp
# Common issues:
# - vLLM instances not yet ready (EPP starts scraping immediately)
# - Port 9002 already in use
# - Missing /etc/epp/config.yaml or endpoints.yaml
```

### Envoy Not Routing

```bash
# Check EPP health
curl http://localhost:9003   # gRPC health port (returns empty 200)

# Check Envoy cluster status
curl http://localhost:19000/clusters | grep -E "epp|cx_active"

# Confirm ext_proc filter is loading
curl http://localhost:19000/config_dump | grep ext_proc
```

### Can't Connect from Load Generator

```bash
# On DUT, open the Envoy port through the firewall
firewall-cmd --add-port=8081/tcp --permanent
firewall-cmd --reload

# Test locally first
curl http://localhost:8081/health
```

---

## Files & Directories

### Playbooks

| File | Purpose |
|---|---|
| `start-vllm-scaleout.yml` | Deploy scale-out (lifecycle only) |
| `stop-vllm-scaleout.yml` | Teardown |
| `embedding-benchmark-scaleout.yml` | Deploy + embedding benchmark + teardown |
| `llm-benchmark-scaleout.yml` | Deploy + LLM inference benchmark + teardown |
| `audio-benchmark-scaleout.yml` | Deploy + audio/ASR benchmark + teardown |

### Configuration Files

| File | Purpose |
|---|---|
| `inventory/group_vars/all/vllm-scaleout.yml` | Default settings |
| `inventory/examples/vllm-scaleout-deployment.yml` | Example inventory |

### Role

`roles/vllm_scaleout/`

| Path | Purpose |
|---|---|
| `defaults/main.yml` | All configurable variables |
| `tasks/main.yml` | Deployment tasks |
| `tasks/cleanup.yml` | Cleanup tasks (imported by stop playbook) |
| `templates/docker-compose.yml.j2` | Container orchestration |
| `templates/envoy.yaml.j2` | Envoy config (routing policy conditional) |
| `templates/epp-config.yaml.j2` | EPP plugin config (scorer weights) |
| `templates/epp-endpoints.yaml.j2` | EPP worker inventory (live-reloadable) |

### Observability Files

| File | Purpose |
|---|---|
| `grafana/prometheus/prometheus-scaleout.yml` | Prometheus config for scale-out |
| `dashboard-examples/vllm_dashboard/pages/8_🔀_ScaleOut_Routing.py` | Streamlit routing analysis page |

---

## Related Documentation

- [Getting Started Guide](getting-started.md)
- [Methodology Overview](methodology/overview.md)
- [Metrics Collection](metrics-collection.md)
- [llm-d No-Kubernetes Guide](https://llm-d.ai/docs/infrastructure/no-kubernetes-deployment)
