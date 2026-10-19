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

### Why combine EPP with LMCache?

EPP and LMCache address different halves of the same problem.

**EPP alone** routes each request to the instance most likely to have a local KV-cache
hit, which is efficient — but creates a tension: strong prefix affinity can overload
one instance while others sit idle, and rerouting to a less-loaded instance pays a
full recompute cost because the target has a cold cache.

**LMCache alone** gives every instance access to a shared KV pool, eliminating
redundant recomputation — but without EPP, routing is still blind to local cache
state, so every request checks the shared pool even when a local hit would be faster.

**Together** they eliminate the affinity-vs-load trade-off: EPP scores each backend
across three tiers in order of cost —

| Tier | Source | Cost | EPP weight |
|---|---|---|---|
| **Local hit** | Instance's own KV cache | ~0 (in-process memory) | 3 |
| **Shared hit** | lmcache-server L1 pool (POSIX SHM, zero-copy) | ~RAM bandwidth | 2 |
| **Miss** | Full KV recompute | CPU prefill time | 0 |

Concretely:
- **Popular prefixes scale freely.** Once any instance computes a KV block (e.g., a
  shared system prompt), it lands in the lmcache-server pool.  EPP can spread the next
  N identical requests across all instances — each gets a shared-pool hit with no
  recompute and no hot-spotting.
- **Rerouting is cheap.** When instance 1 is queued, EPP routes to instance 2 knowing
  it gets a pool hit instead of a cold miss.  Without LMCache, that reroute paid full
  prefill cost.
- **Cold-start instances warm up instantly.** A newly started instance has an empty
  local cache but can immediately serve warm traffic from the shared pool while it
  builds local state.
- **No redundant compute across instances.** In a 5-instance deployment, the same
  prefix could otherwise be computed 5 times.  With LMCache, compute it once — all 5
  instances benefit.

Set `scaleout_lmcache_backend=remote` to enable; see [LMCache](#lmcache-cross-instance-kv-sharing) for sizing
and configuration details.

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
| `scaleout_cores_per_instance` | 32 | 4, 8, 16, 24, 32 | CPU cores per instance (embedding often uses **4**) |
| `scaleout_routing_policy` | `intelligent` | `intelligent`, `round_robin` | Routing mode |
| `scaleout_vllm_base_port` | 8000 | any | First vLLM instance port |
| `scaleout_envoy_port` | 8081 | any | Client-facing Envoy port |
| `scaleout_enable_smt` | false | true/false | Enable SMT/HT cores |
| `scaleout_enable_prefix_caching` | true | true/false | Enable vLLM prefix caching |
| `scaleout_vllm_gpu_memory_utilization` | 0.9 | 0.0–1.0 | Fraction of system RAM vLLM reserves for KV cache |

`scaleout_vllm_gpu_memory_utilization` mirrors vLLM's `--gpu-memory-utilization` flag.
On the CPU backend it controls RAM, not GPU memory.  The default 0.9 is fine for
baseline deployments but **must be reduced when LMCache is active** — the lmcache-server
pre-allocates its L1 pool before vLLM starts, reducing available RAM.  See
[Memory Sizing for LMCache](#memory-sizing-for-lmcache) below.

Defaults shown are the Ansible playbook defaults (large server, cores pinned from 32).
The `cpueval` CLI suite (`vllm-scaleout`) uses lighter defaults — 2 instances × 24 cores
from core 0 — for quicker CLI-driven runs; override either with `-e`/`--extra` as needed.

### Model / Task Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `scaleout_model_name` | from `test_model` | HuggingFace model ID or local path |
| `scaleout_vllm_runner` / `scaleout_vllm_convert` | (auto) | vLLM 0.31+: `pooling` + `embed` for embedding models (not `--task embed`) |
| `scaleout_vllm_task` | (auto) | Legacy/explicit task (e.g. `transcription` for Whisper where supported) |
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
The vLLM CPU backend uses the V1 engine exclusively.  The connector works on CPU,
but the deployment has CPU-specific requirements: all containers must share the
host IPC namespace (`ipc: host` + `pid: host`), `/dev/shm` must be sized for the
KV objects, and the LBHNC layout detection in older lmcache releases was broken
on CPU (fixed in lmcache 0.5.x — if you hit a `StopIteration` at startup, set
`scaleout_lmcache_mp_transfer_mode=vllm_driven`).

`lmcache` is not bundled in the vLLM CPU image.  When `scaleout_lmcache_backend=remote`
the role **automatically builds a custom image** (`vllm-cpu-lmcache:<tag>`) with lmcache
pre-installed before bringing up the compose stack.  The build is skipped on subsequent
runs if the image already exists locally.  See [LMCache Image Build](#lmcache-image-build).

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

### LMCache Image Build

When `scaleout_lmcache_backend=remote`, the role:

1. Copies `automation/test-execution/containers/vllm-cpu-lmcache/Containerfile` to the DUT.
2. Checks whether `vllm-cpu-lmcache:<base-tag>` already exists locally.
3. Builds it if absent — `FROM docker.io/vllm/vllm-openai-cpu:<tag>` + `pip install lmcache` — and smoke-tests the import.
4. Overrides `scaleout_vllm_image` to the built image for the compose deployment.

**Build variables:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `scaleout_vllm_base_image` | `docker.io/vllm/vllm-openai-cpu:v0.32.0` | Upstream registry image (never overwritten by role tasks) |
| `scaleout_vllm_image` | `= scaleout_vllm_base_image` | Runtime image in the compose stack; overridden to `scaleout_lmcache_image_tag` when building |
| `scaleout_lmcache_build_image` | `true` | Set `false` to skip the build and use `scaleout_vllm_image` as-is |
| `scaleout_lmcache_image_tag` | `localhost/vllm-cpu-lmcache:<base-tag>-lmcache<version>` | Tag for the built image |
| `scaleout_lmcache_version` | `0.5.5` | lmcache PyPI version to bake in |

The build runs **once** and is then cached.  If you upgrade the base vLLM image or pin
a different lmcache version, delete the old image (`podman rmi localhost/vllm-cpu-lmcache:<base-tag>-lmcache<version>`)
before the next run so the role rebuilds.

If the smoke-test inside the Containerfile fails (`import lmcache` or the
`LMCacheMPConnector` import raises), the lmcache version is incompatible with
this vLLM release — try a newer `scaleout_lmcache_version`.

### Memory Sizing for LMCache

The lmcache-server allocates its L1 pool **before** the vLLM instances start.
That memory is already claimed when vLLM checks available RAM against its
`--gpu-memory-utilization` limit (which controls CPU RAM on the CPU backend,
despite the GPU-sounding name).  With the default 0.9 utilization each instance
requests 0.9 × total_RAM — typically more than what's left after the pool.

**Rule of thumb:**

```
gpu_memory_utilization ≤ (total_ram_GB - lmcache_l1_gb - os_overhead_GB)
                         / (total_ram_GB × num_instances)
```

Example — 92 GB host, 10 GB pool, 4 GB OS overhead, 2 instances:

```
(92 - 10 - 4) / (92 × 2) ≈ 0.42  →  use 0.4
```

Set `scaleout_vllm_gpu_memory_utilization` accordingly.  The vLLM startup log
confirms the actual KV cache reservation:

```
Auto set (24.67/92.37) GiB for KV cache on node 0, with 36.95 GiB requested
```

If vLLM exits immediately after KV cache allocation with
`Available memory … is less than desired CPU memory utilization`, the value is
still too high — reduce it further.

### lmcache-server Readiness

The vLLM instances wait for the lmcache-server's TCP RPC port to be accepting
connections before starting.  This prevents the `LMCacheMPConnector` from trying
to register with a server that is still running `pip install lmcache` or
initialising its pool:

```
Waiting for lmcache-server on port 5555...
  lmcache-server not ready, retrying in 5s...
lmcache-server ready.
```

The wait loop is embedded in the container entrypoint and retries every 5 seconds
indefinitely.  The Ansible health-check timeout is 40 minutes to accommodate
first-run model compilation on CPU (inductor traces the model once, caches the
result, then subsequent starts are fast).

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
| `scaleout_lmcache_kv_failure_policy` | `fail` | `fail` (exit on connector error) or `recompute` (log error, fall back) |
| `scaleout_vllm_gpu_memory_utilization` | 0.9 | Fraction of system RAM reserved per vLLM instance — **reduce for multi-instance + LMCache** |

**Sizing `lruCapacityPerServer`:** the EPP tracks pool state via an LRU index
sized in KV blocks.  A rough formula:

```
lruCapacityPerServer = (server_l1_size_gb × 1024) / avg_kv_block_size_mb
```

For most CPU embedding models, `avg_kv_block_size_mb ≈ 0.5–1 MB`, giving
10,000–20,000 blocks for a 10 GB pool.

**`scaleout_lmcache_kv_failure_policy`:** use `recompute` when debugging connector
issues — vLLM logs the actual LMCache error and continues serving requests
(without cross-instance caching) instead of entering a crash/restart loop.  Set
back to `fail` for production runs so a silent connector failure is not masked.

### Quick Start

```bash
# Minimum — LMCache with default 10 GB pool, no hugepages
# (image is built automatically on first run)
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_lmcache_backend=remote \
      scaleout_vllm_gpu_memory_utilization=0.4"

# Recommended — LMCache + 1 GB hugepages
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_lmcache_backend=remote \
      scaleout_lmcache_server_l1_size_gb=20 \
      scaleout_lmcache_hugepages_enabled=true \
      scaleout_lmcache_hugepages_1g_count=20 \
      scaleout_vllm_gpu_memory_utilization=0.4"

# Full benchmark — deploy, test, teardown (causal-LM models only)
ansible-playbook llm-benchmark-scaleout.yml \
  -e "scaleout_lmcache_backend=remote \
      scaleout_lmcache_hugepages_enabled=true \
      scaleout_vllm_gpu_memory_utilization=0.4"

# Debug connector failures — vLLM starts, logs error, falls back to recompute
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_lmcache_backend=remote \
      scaleout_lmcache_kv_failure_policy=recompute \
      scaleout_vllm_gpu_memory_utilization=0.4"
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
ansible-playbook llm-benchmark-scaleout.yml \
  -e "scaleout_lmcache_backend=none scaleout_enable_prefix_caching=true"

# LMCache — shared pool, intelligent EPP routing
ansible-playbook llm-benchmark-scaleout.yml \
  -e "scaleout_lmcache_backend=remote scaleout_lmcache_hugepages_enabled=true"
```

LMCache benefits are largest for workloads with **shared prefixes across
requests** — long system prompts, multi-turn conversations, batch generation
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

Use **`embedding-benchmark-scaleout.yml`** (not `llm-benchmark-scaleout.yml`). The
playbook deploys Envoy/EPP/vLLM, runs **vllm-bench** against
`http://<DUT>:8081/v1`, copies per-instance metrics into the repo
`results/embedding/…` tree, then tears down.

| LLM scale-out | Embedding scale-out |
|---------------|-------------------|
| `llm-benchmark-scaleout.yml` | `embedding-benchmark-scaleout.yml` |
| GuideLLM (`benchmarks.json`) | vllm-bench (`operating_point/`, `latency/`) |
| `guidellm_cpus`, `guidellm_numa_node` | `vllm_bench_cpus`, `vllm_bench_numa_node` |
| `workload_type=chat` (etc.) | Not used |
| Generative model IDs | Embedding model IDs (e.g. `RedHatAI/granite-embedding-english-r2`) |

Set **`scaleout_vllm_max_model_len`** for embedding models (default in playbook:
512). The embedding scale-out playbook sets **`scaleout_vllm_runner=pooling`**,
**`scaleout_vllm_convert=embed`**, and **`scaleout_enable_prefix_caching=false`**
(vLLM 0.31 removed `--task embed`; prefix caching must stay off for pooling
models or the engine fails with `HybridKVCacheCoordinator requires at least one
cacheable group`).

#### Functional / smoke testing

For pipeline validation (deploy → health check → short bench → metrics → metadata →
teardown), keep the default **`scenario=operating_point`** (no full latency sweep),
reduce prompts, and cap peak concurrency so probes run only at **conc=1** and
**conc=8** (`op_peak_concurrency=8`).

Run from the repo root (adjust inventory path if needed):

```bash
# Baseline — intelligent EPP routing (functional)
ansible-playbook \
  -i automation/test-execution/ansible/inventory/hosts.yml \
  automation/test-execution/ansible/embedding-benchmark-scaleout.yml \
  -e "test_model=RedHatAI/granite-embedding-english-r2" \
  -e "scaleout_num_instances=2" \
  -e "scaleout_cores_per_instance=4" \
  -e "scaleout_start_core=0" \
  -e "scaleout_routing_policy=intelligent" \
  -e "scaleout_vllm_max_model_len=512" \
  -e "vllm_bench_cpus=48-71" \
  -e "vllm_bench_numa_node=0" \
  -e "scenario=operating_point" \
  -e "num_prompts=64" \
  -e "op_peak_concurrency=8" \
  -e "hf_token=${HF_TOKEN}"
```

With `scaleout_start_core=0` and two instances × 4 cores, vLLM uses **0–7**;
pin vllm-bench on a disjoint range (e.g. **48–71**) so load-gen does not share
instance CPUs.

To functionally validate **LMCache**, use the LLM playbook instead — LMCache
requires causal-LM models (see [LMCache](#lmcache-cross-instance-kv-sharing)):

```bash
# LMCache functional smoke — small causal-LM model, 2 instances, short chat run
# (LMCache cannot be used with embedding/pooling models — the role pre-flight
# rejects that combination)
ansible-playbook \
  -i automation/test-execution/ansible/inventory/hosts.yml \
  automation/test-execution/ansible/llm-benchmark-scaleout.yml \
  -e "test_model=RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4" \
  -e "workload_type=chat" \
  -e "scaleout_num_instances=2" \
  -e "scaleout_cores_per_instance=4" \
  -e "scaleout_start_core=0" \
  -e "scaleout_routing_policy=round_robin" \
  -e "guidellm_cpus=48-71" \
  -e "guidellm_numa_node=0" \
  -e "guidellm_max_seconds=120" \
  -e "guidellm_max_requests=32" \
  -e "hf_token=${HF_TOKEN}" \
  -e "scaleout_lmcache_backend=remote" \
  -e "scaleout_lmcache_server_l1_size_gb=10" \
  -e "scaleout_lmcache_hugepages_enabled=true" \
  -e "scaleout_vllm_gpu_memory_utilization=0.4" \
  -e "scaleout_lmcache_kv_failure_policy=recompute"
```

**Benchmark scenario** (`scenario` or env `SCENARIO`):

| Value | Use |
|-------|-----|
| `operating_point` | Default; probes at conc 1, 8, and peak — best for smoke |
| `latency` | Concurrency sweep only |
| `all` | Full latency sweep then operating-point probes — performance runs |

For production-style embedding scale-out benchmarks, use `scenario=all` and
restore default `num_prompts` / `op_peak_concurrency` (see
[Operating-point probes](../tests/embedding-models/operating-point.md)).

**Deploy-only smoke** (no vllm-bench, manual curl):

```bash
cd automation/test-execution/ansible
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_model_name=RedHatAI/granite-embedding-english-r2 \
      scaleout_vllm_max_model_len=512 scaleout_num_instances=2"
curl -s "http://<DUT>:8081/v1/models" | jq .
# … single /v1/embeddings request …
ansible-playbook stop-vllm-scaleout.yml
```

#### What to verify after a functional run

| Area | Expected |
|------|----------|
| **Playbook** | Succeeds through finalize; no **container restart** warning at end |
| **Results** | `results/embedding/<model>__…>/<test_run_id>/` matches `test-metadata.json` |
| **`test-metadata.json`** | `deployment_type: scaleout`, `model_name`, `num_instances`, `routing_policy`, `lmcache_backend`, shared `test_run_id` |
| **Client bench** | `operating_point/conc-1.json`, `conc-8.json` (with `op_peak_concurrency=8`) |
| **Server metrics** | `vllm-metrics-instance-*.json`; `container-stats-*.jsonl` when collectors enabled |
| **EPP** | `epp-metrics.json` for **intelligent** runs; absent for **round_robin** (no EPP) |
| **LMCache run** | Pool up; optional `curl http://<DUT>:8088/metrics`; vLLM logs clean or explicit `recompute` fallback |
| **Dashboard** | Streamlit **Scale-Out Routing** → **Compare embedding runs** (not LLM compare) |

Quick endpoint checks (on DUT or via SSH tunnel):

```bash
curl -s "http://<DUT>:8081/v1/models" | jq .
curl -s "http://<DUT>:8000/metrics" | grep -E 'num_requests_running|prefix_cache' | head
# intelligent routing only:
curl -s "http://<DUT>:9090/metrics" | head
```

Inventory must define **`dut`** and **`load_generator`** the same way as LLM
scale-out (all-in-one or split host). External mode always targets Envoy on the
DUT host (`scaleout_envoy_port`, default 8081).

**cpueval:** `./cpueval --suite embedding-scaleout --model … --num-instances 2`
runs the same Ansible playbook; pass extra Ansible vars with repeated `-e` /
suite overrides as documented in [cpueval CLI](cpueval-cli.md).

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
- **Compare embedding runs** tab (vllm-bench E2E/RPS; separate from LLM GuideLLM metrics)

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

### vLLM Crashes After KV Cache Allocation (LMCache)

Symptom: vLLM loads the model and allocates the KV cache, then the worker process
dies silently — no Python traceback, just:

```
LMCache INFO: Wrapping 32 KV cache tensors for IPC (kv_wrap.py:62)
Worker proc VllmWorker-0 died unexpectedly, shutting down executor.
RuntimeError: cancelled
```

**Root cause:** `lmcache_driven` transfer mode works by exposing each vLLM
instance's KV cache tensors as POSIX shared-memory handles that the lmcache-server
reads zero-copy.  POSIX shm objects (`/dev/shm/psm_*`) are scoped to the
**IPC namespace** of the process that creates them.  By default each container
has a private IPC namespace, so the handles the vLLM worker creates are invisible
to the lmcache-server container — `shm_open()` returns `ENOENT` and the worker
dies with SIGBUS.

**Fix:** ensure `ipc: host` is set on both the vLLM instance services and the
lmcache-server service in the compose stack.  With `ipc: host` all containers
share the **host** IPC namespace and can see each other's `/dev/shm` objects.

The role sets `ipc: host` automatically when `scaleout_lmcache_backend=remote`.
The host `/dev/shm` must be large enough to hold all per-instance KV caches
simultaneously:

```
/dev/shm required ≥ num_instances × (gpu_memory_utilization × total_ram_GB)
```

Example (2 instances × 0.4 × 92 GB ≈ 74 GB):

```bash
# Check current host /dev/shm size
df -h /dev/shm

# Resize if needed (does not persist across reboot)
sudo mount -t tmpfs -o remount,size=80G /dev/shm

# To persist, add to /etc/fstab:
# tmpfs /dev/shm tmpfs defaults,size=80G 0 0
```

### OOM: "Available memory less than desired CPU memory utilization"

The lmcache-server pre-allocates its L1 pool (`scaleout_lmcache_server_l1_size_gb`)
**before** vLLM starts.  That memory is already gone when vLLM calculates how much
RAM it can use.  With the default `gpu_memory_utilization=0.9` each instance
requests ≈ 83 GB on a 92 GB host — which is already over-committed once the pool
is in use.

Reduce `scaleout_vllm_gpu_memory_utilization` to leave room for the pool:

```
utilization ≤ (total_ram_GB - lmcache_l1_gb - os_overhead_GB) / (total_ram_GB × num_instances)
```

```bash
# Example: 92 GB host, 10 GB pool, 2 instances → (92-10-4)/(92×2) ≈ 0.42
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_lmcache_backend=remote scaleout_vllm_gpu_memory_utilization=0.4"
```

### LMCache Connector Fails on Startup — Silent Crash Loop

If the vLLM engine crashes during connector initialisation and the container
restarts silently, use `scaleout_lmcache_kv_failure_policy=recompute` to surface
the actual error.  With this policy vLLM logs the LMCache error, falls back to
recomputing KV blocks without cross-instance caching, and stays up so you can
inspect `podman logs`:

```bash
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_lmcache_backend=remote \
      scaleout_lmcache_kv_failure_policy=recompute \
      scaleout_vllm_gpu_memory_utilization=0.4"

# Then tail the logs to see the LMCache error
podman logs -f vllm-instance-1 2>&1 | grep -i -E "lmcache|error|fail"
```

Common errors surfaced this way:

| Error | Cause | Fix |
|-------|-------|-----|
| `shm_open ENOENT` | Containers in separate IPC namespaces | Ensure `ipc: host` on all LMCache services |
| `FileExistsError: File exists: '/lmcache_kv_N_0'` | (1) Stale SHM from prior crash — run the stop/cleanup playbook to wipe `/dev/shm/lmcache_kv_*`; (2) concurrent PID namespace collision — two containers recycled the same PID simultaneously (see [PID Namespace Collision](#pid-namespace-collision-between-concurrent-instances-lmcache)) | Handled automatically by the role (`pid: host`); for manual restarts see linked section |
| `Input should be 'recompute' or 'fail'` | Invalid `kv_load_failure_policy` value | Only `recompute` or `fail` are valid — not `ignore` |
| `Import error: LMCacheMPConnector` | lmcache not installed in image | Run with `scaleout_lmcache_build_image=true` (default) |
| Worker killed with no traceback | `/dev/shm` too small for KV cache wrapping | Resize host `/dev/shm` (see above) |

### Stale POSIX SHM Objects Between Test Runs

LMCache names each KV-cache SHM object after the vLLM worker PID:
`/dev/shm/lmcache_kv_<pid>_<index>`.  With `ipc: host` these objects live in the
**host's** `/dev/shm` and **persist after a container crash**.  On the next start,
if the container reuses the same PID (common in isolated PID namespaces), `shm_open`
fails with:

```
FileExistsError: [Errno 17] File exists: '/lmcache_kv_189_0'
```

In addition to `lmcache_kv_*` objects, crashed vLLM workers leave behind:

| SHM pattern | Left by |
|---|---|
| `/dev/shm/lmcache_kv_*` | LMCache KV backing store (one per instance) |
| `/dev/shm/__KMP_REGISTERED_LIB_*` | OpenMP runtime registration (one per worker PID) |
| `/dev/shm/sem.mp-*` | Python multiprocessing semaphores (ring buffer, ZMQ) |
| `/dev/shm/psm_*` | PSM/InfiniBand shared state |

**The Ansible playbook handles this automatically**: `tasks/main.yml` stops and
removes all running containers first, then cleans the SHM namespace.  The order
matters — stopping containers before unlinking SHM prevents a subtle race where
the lmcache-server (still alive, still holding an mmap fd to the SHM) detects the
unlinked name and recreates the file before the new container starts, which causes
the same EEXIST failure.

If you manually restart containers without going through the playbook, follow the
same order:

```bash
# 1. Stop containers FIRST (so no running process can recreate SHM files)
sudo podman stop $(sudo podman ps -q --filter name=vllm-) 2>/dev/null || true
sudo podman rm   $(sudo podman ps -aq --filter name=vllm-) 2>/dev/null || true

# 2. Then wipe all stale SHM objects
sudo rm -f /dev/shm/lmcache_kv_* \
           /dev/shm/__KMP_REGISTERED_LIB_* \
           /dev/shm/sem.mp-* \
           /dev/shm/psm_*

# Confirm only system objects remain (libpod_lock, envoy_shared_memory_0)
ls /dev/shm/
```

The `restart: "no"` policy set by the role (when `scaleout_lmcache_backend=remote`)
prevents containers from auto-restarting after a crash and accumulating stale SHM
objects that cause every subsequent start to fail immediately.

### PID Namespace Collision Between Concurrent Instances (LMCache)

**Symptom**: `FileExistsError: [Errno 17] File exists: '/lmcache_kv_265_0'` at startup
even though `/dev/shm/` was clean before the run.

**Root cause**: LMCache names each KV-cache SHM segment after the vLLM *worker process*
PID — `/dev/shm/lmcache_kv_<pid>_<index>`.  PID is only unique within a single PID
namespace.  Each container gets its own isolated PID namespace by default, and all
namespaces independently recycle low PIDs starting from 1.

When two vLLM instance containers start at the same time and lmcache is already
installed (so the entrypoint's `pip check` exits in milliseconds rather than spawning
the many subprocesses that `pip install` would), both workers follow an almost identical
startup path and land on the same PID — typically 265.  Both then call:

```c
shm_open("/lmcache_kv_265_0", O_CREAT | O_EXCL, ...)
```

One wins; the other gets `EEXIST` and the worker crashes.

The **first run often succeeds by luck**: when lmcache is not yet cached, `pip install`
spawns enough subprocesses to push each container's workers to different PIDs.  Once
lmcache is installed the entrypoint completes in milliseconds and both workers get
identical PID sequences — the collision becomes deterministic.

**Current workaround — `pid: host`**: sharing the host PID namespace gives every
process a unique host-level PID across all containers, making the SHM names unique by
construction.  The role sets `pid: host` automatically when
`scaleout_lmcache_backend=remote`.

**Kubernetes limitation**: `hostPID: true` is blocked by Pod Security Admission
(`restricted` and `baseline` policies) in most clusters.  `shareProcessNamespace: true`
within a single pod avoids `hostPID` but forces all instances into one pod — this
defeats independent pod scheduling and multi-node scale-out.  Using separate nodes
works (each node has its own `/dev/shm`) but prevents the zero-copy SHM transfer that
makes `lmcache_driven` mode fast.

**Upstream fix (proposed — [lmcache/v1/platform/devices/cpu/shm.py](https://github.com/LMCache/LMCache))**:
Replace `os.getpid()` with a process-stable unique identifier that is independent of
the PID namespace:

```python
# Added module-level constant (replaces the os.getpid() call in migrate_to_shm_and_wrap)
_LMCACHE_INSTANCE_ID: str = (
    os.environ.get("LMCACHE_INSTANCE_ID") or uuid.uuid4().hex[:16]
)

# SHM name construction changes from:
#   shm_name = "%s%d_%d" % (SHM_NAME_PREFIX, os.getpid(), next(_CPU_SHM_COUNTER))
# To:
    shm_name = "%s%s_%d" % (SHM_NAME_PREFIX, _LMCACHE_INSTANCE_ID, next(_CPU_SHM_COUNTER))
```

In Kubernetes, inject the pod UID via the Downward API so each pod gets a guaranteed
unique token without any code changes:

```yaml
env:
- name: LMCACHE_INSTANCE_ID
  valueFrom:
    fieldRef:
      fieldPath: metadata.uid   # guaranteed unique cluster-wide
```

This makes `lmcache_driven` mode work correctly with any PID namespace configuration,
any container runtime, and any number of pods on the same node — with or without
`hostPID: true`.  Until the fix is merged upstream, `pid: host` (set automatically
by this role) is the workaround for bare-metal / Podman deployments.

| Deployment | Workaround | Notes |
|---|---|---|
| Bare metal / Podman | `pid: host` (current) | Role sets this automatically |
| k8s `restricted`/`baseline` PSA | `LMCACHE_INSTANCE_ID` via Downward API | Requires the upstream fix |
| k8s `privileged` PSA | `hostPID: true` | Works but broad privilege; avoid if possible |
| Multi-node (pods on different nodes) | None needed | Each node has its own `/dev/shm` |

### Health Check Timeout on First Run (LMCache)

The first time vLLM starts with a new model on CPU it runs `torch.compile` /
inductor tracing, which can take **20–40 minutes** before the `/health` endpoint
responds.  The role extends the health-check timeout to 40 minutes
(`scaleout_health_check_retries=240`, 10 s delay) to accommodate this.

If the Ansible task still times out, confirm the container is alive and actively
compiling (not in a restart loop):

```bash
podman ps                          # check restart count
podman logs -f vllm-instance-1    # watch for "Warming up done"
```

Subsequent runs hit the inductor cache and start in 1–3 minutes.

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
| `tasks/main.yml` | Deployment tasks (image build, hugepages, compose up, health checks) |
| `tasks/cleanup.yml` | Cleanup tasks (imported by stop playbook; removes all containers including lmcache-server) |
| `templates/docker-compose.yml.j2` | Container orchestration (vLLM instances, lmcache-server, EPP, Envoy) |
| `templates/envoy.yaml.j2` | Envoy config (routing policy conditional) |
| `templates/epp-config.yaml.j2` | EPP plugin config (scorer weights) |
| `templates/epp-endpoints.yaml.j2` | EPP worker inventory (live-reloadable) |

### Container Images

`containers/`

| Path | Purpose |
|---|---|
| `vllm-cpu-lmcache/Containerfile` | Builds `vllm-cpu-lmcache:<tag>` — the vLLM CPU base image with lmcache pre-installed and smoke-tested. Used automatically when `scaleout_lmcache_backend=remote`. |

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
