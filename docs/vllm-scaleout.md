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
```

`test-metadata.json` for scale-out runs contains:

```json
{
  "deployment_type": "scaleout",
  "num_instances": 5,
  "routing_policy": "intelligent",
  "epp_scorer_weights": { "prefix_cache": 3, "queue": 2, "kv_cache": 2, "lru": 2 },
  "scaleout_envoy_port": 8081,
  "cores_per_instance": 32
}
```

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
| `scaleout_cores_per_instance` | 32 | 8, 16, 32 | CPU cores per instance |
| `scaleout_routing_policy` | `intelligent` | `intelligent`, `round_robin` | Routing mode |
| `scaleout_vllm_base_port` | 8000 | any | First vLLM instance port |
| `scaleout_envoy_port` | 8081 | any | Client-facing Envoy port |
| `scaleout_enable_smt` | false | true/false | Enable SMT/HT cores |
| `scaleout_enable_prefix_caching` | true | true/false | Enable vLLM prefix caching |

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
