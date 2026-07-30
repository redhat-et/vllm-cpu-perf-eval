# Hello RHAIIS: Deploy, Chat, and Benchmark LLM Inference on RHEL CPU

You can run a large language model on CPU inside a container on RHEL, send it a chat
request, and measure its performance with reproducible benchmarks — all in about twenty
minutes. This guide walks through that path using **Red Hat AI Inference (RHAIIS) 3.5**
and the [vLLM CPU Performance Evaluation](https://github.com/redhat-et/vllm-cpu-perf-eval)
framework's `cpueval` CLI.

**What you'll do:**

1. Pull and run the RHAIIS CPU container with Podman
2. Verify inference with the OpenAI-compatible API
3. Benchmark throughput and latency with `cpueval`

**What you'll need:**

- A RHEL 9 (or compatible) host with Podman
- x86_64 CPU with AVX2 (Intel Xeon or AMD EPYC recommended)
- At least 8 CPU cores and 16 GB RAM (32 GB+ for 8B models)
- Red Hat registry credentials (`registry.redhat.io`)
- Optional: a [Hugging Face token](https://huggingface.co/settings/tokens) for gated models

!!! tip "Single-machine setup"
    Everything in this guide runs on one RHEL host. You do not need a separate load
    generator or cloud VMs to get started.

---

## Why RHAIIS on CPU?

RHAIIS ships enterprise-hardened vLLM images optimized for Intel and AMD server CPUs.
Running inference on CPU is a practical choice when you want to:

- Evaluate models before committing GPU capacity
- Serve smaller or quantized models at the edge or in cost-sensitive environments
- Benchmark CPU platforms with a standardized, reproducible methodology

The manual steps below mirror the
[official RHAIIS CPU inference documentation](https://docs.redhat.com/en/documentation/red_hat_ai_inference/3.5/html/getting_started/about-cpu-inference_getting-started).
The benchmarking section connects that deployment to the open-source
[vllm-cpu-perf-eval](https://github.com/redhat-et/vllm-cpu-perf-eval) project.

---

## Step 1 — Authenticate and pull the RHAIIS image

Log in to the Red Hat container registry and pull the CPU inference image.

!!! note "Image tags: GA vs early access"
    RHAIIS 3.4 is generally available at `registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0`.

    RHAIIS 3.5 is currently available as an early-access image:

    `registry.redhat.io/rhaii-early-access/vllm-cpu-rhel9:3.5.0-ea.2`

    Use the 3.5 tag below if you are following this guide for 3.5; substitute the
    3.4 tag if you are on GA.

```bash
# Log in with your Red Hat account (Customer Portal or registry service account)
podman login registry.redhat.io

# Pull the RHAIIS 3.5 CPU image for RHEL 9
podman pull registry.redhat.io/rhaii-early-access/vllm-cpu-rhel9:3.5.0-ea.2
```

!!! warning "Use sudo consistently"
    Root and non-root users have separate Podman credential stores. If you use `sudo
    podman login`, also use `sudo podman pull` and `sudo podman run`. Mixing root and
    non-root commands will cause authentication failures.

Create a cache directory so model weights persist across container restarts:

```bash
mkdir -p ~/rhaii-cache
```

If you plan to use gated models (for example, Meta Llama), export your Hugging Face
token now:

```bash
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## Step 2 — Start the inference server

Start vLLM inside the RHAIIS container. We use **TinyLlama** (1.1B parameters) because
it downloads quickly, fits comfortably in 16 GB RAM, and is the model Red Hat
documents for CPU hello-world scenarios.

```bash
podman run --rm -it \
  --name rhaiis-hello \
  --security-opt=label=disable \
  --shm-size=4g \
  -p 8000:8000 \
  --userns=keep-id:uid=1001 \
  --env "HUGGING_FACE_HUB_TOKEN=${HF_TOKEN:-}" \
  --env "HF_HUB_OFFLINE=0" \
  --env "VLLM_CPU_KVCACHE_SPACE=4" \
  -v ~/rhaii-cache:/opt/app-root/src/.cache:Z \
  registry.redhat.io/rhaii-early-access/vllm-cpu-rhel9:3.5.0-ea.2 \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0
```

### What these flags do

| Flag | Purpose |
|------|---------|
| `--security-opt=label=disable` | Required on SELinux-enforced RHEL when bind-mounting volumes |
| `--shm-size=4g` | Shared memory for vLLM worker processes; increase to `8g` for larger models |
| `--userns=keep-id:uid=1001` | Maps your host UID to the vLLM process user inside the container |
| `VLLM_CPU_KVCACHE_SPACE=4` | Allocates 4 GB for the CPU KV cache; increase for 8B models |
| `-v ~/rhaii-cache:...:Z` | Persists downloaded model weights; `:Z` sets SELinux context |
| `--model TinyLlama/...` | Hugging Face model ID served by vLLM |

!!! info "LD_PRELOAD on RHAIIS 3.5"
    RHAIIS 3.4 required setting `LD_PRELOAD=/usr/lib64/libomp.so` on the **host** for
    optimal performance. RHAIIS 3.5 bakes this into the container image, so you do not
    need to set it manually.

The first startup downloads model weights from Hugging Face. On a typical connection
this takes a few minutes. Wait until you see the server listening on port 8000:

```text
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Leave this terminal open, or re-run the container in detached mode:

```bash
podman run -d \
  --name rhaiis-hello \
  --security-opt=label=disable \
  --shm-size=4g \
  -p 8000:8000 \
  --userns=keep-id:uid=1001 \
  --env "HUGGING_FACE_HUB_TOKEN=${HF_TOKEN:-}" \
  --env "HF_HUB_OFFLINE=0" \
  --env "VLLM_CPU_KVCACHE_SPACE=4" \
  -v ~/rhaii-cache:/opt/app-root/src/.cache:Z \
  registry.redhat.io/rhaii-early-access/vllm-cpu-rhel9:3.5.0-ea.2 \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0
```

---

## Step 3 — Chat with your model

Open a second terminal on the same host. RHAIIS exposes an **OpenAI-compatible REST
API** on port 8000.

### Health check

```bash
curl -s http://localhost:8000/health
```

Expected response:

```text
{"status":"ok"}
```

### List loaded models

```bash
curl -s http://localhost:8000/v1/models | python3 -m json.tool
```

You should see `TinyLlama/TinyLlama-1.1B-Chat-v1.0` in the response.

### Send a chat completion

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "messages": [
      {"role": "user", "content": "Explain CPU inference in one sentence."}
    ],
    "max_tokens": 64,
    "temperature": 0.7
  }' | python3 -m json.tool
```

You should get a JSON response with generated text in `choices[0].message.content`.

### Optional: use the OpenAI Python SDK

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

response = client.chat.completions.create(
    model="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    messages=[{"role": "user", "content": "What is vLLM?"}],
    max_tokens=100,
)

print(response.choices[0].message.content)
```

At this point you have a working RHAIIS deployment. The next step is to measure it.

---

## Step 4 — Install the benchmarking toolchain

Clone the vLLM CPU Performance Evaluation repository and install its dependencies.

```bash
# System packages (RHEL 9)
sudo dnf install -y ansible-core python3-pip git

# Clone the evaluation framework
git clone https://github.com/redhat-et/vllm-cpu-perf-eval.git
cd vllm-cpu-perf-eval

# Install Ansible collections
ansible-galaxy collection install -r automation/test-execution/ansible/requirements.yml

# cpueval creates a virtualenv on first run — no manual pip install needed
./cpueval list
```

Configure environment variables. For a single-machine setup, point both the DUT
(inference server) and load generator at this host:

```bash
export DUT_HOSTNAME=$(hostname -f)
export LOADGEN_HOSTNAME=$(hostname -f)
export ANSIBLE_SSH_USER=$USER

# Use the RHAIIS image you pulled in Step 1
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii-early-access/vllm-cpu-rhel9:3.5.0-ea.2

# Hugging Face token (if using gated models)
export HF_TOKEN=${HF_TOKEN:-}
```

Set up passwordless SSH to yourself so Ansible can orchestrate tests locally:

```bash
# Generate a key if you don't have one
test -f ~/.ssh/id_ed25519 || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519

# Authorize local SSH
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Verify
ssh -o StrictHostKeyChecking=no $USER@$DUT_HOSTNAME 'echo connected'
```

Run a health check:

```bash
./cpueval doctor
```

You should see green checkmarks for Ansible, inventory, environment variables, and host
connectivity.

---

## Step 5 — Run your first benchmark

`cpueval` wraps Ansible playbooks and test scripts so you can run standardized
benchmarks without writing YAML by hand.

### Stop the manual container first

If you started RHAIIS manually in Step 2, stop it before running managed-mode
benchmarks — both use port 8000:

```bash
podman stop rhaiis-hello
podman rm rhaiis-hello 2>/dev/null || true
```

### Quick chat smoke test

The `chat-smoke` suite deploys vLLM via Ansible, runs a GuideLLM concurrent-load
benchmark, and collects results:

```bash
./cpueval run --suite chat-smoke \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 8 \
  --workload chat
```

This test pins vLLM to 8 CPU cores, warms up the server, sweeps concurrency levels,
and writes results under `results/llm/`.

Preview the underlying Ansible command without running it:

```bash
./cpueval run --suite chat-smoke \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --cores 8 \
  --dry-run
```

### View results

```bash
./cpueval results --last
```

Example output:

```text
Results: results/llm/TinyLlama__TinyLlama-1.1B-Chat-v1.0/chat-.../8cores-...

┌───────────┬────────────────────────────────────┐
│ Model     │ TinyLlama/TinyLlama-1.1B-Chat-v1.0 │
│ Workload  │ chat                               │
│ Cores     │ 8                                  │
└───────────┴────────────────────────────────────┘

┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Concurrency ┃ Req/s ┃   Tok/s ┃ TTFT (ms) ┃ TPOT (ms) ┃ Requests ┃
┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ 1           │  0.10 │  106.37 │     53.48 │     19.34 │    26/26 │
│ 8           │  0.65 │  689.12 │     89.21 │     22.15 │  192/192 │
│ 32          │  1.47 │ 1585.99 │    199.50 │     41.36 │  384/384 │
└─────────────┴───────┴─────────┴───────────┴───────────┴──────────┘
```

Key metrics:

| Metric | What it measures |
|--------|------------------|
| **TTFT** | Time to first token — perceived responsiveness |
| **TPOT** | Time per output token — generation speed |
| **Tok/s** | Aggregate throughput across all concurrent requests |
| **Req/s** | Request completion rate |

!!! tip "Explore results in a dashboard"
    Run `./cpueval dashboard start` and open `http://localhost:8501` in your browser
    for interactive charts.

---

## Step 6 — Benchmark RHAIIS quantized models

Once the smoke test passes, try a RHAIIS-optimized model. The `rhaiis-sweep` suite runs
a matrix of models, core counts, and workloads — narrowed here to keep runtime
reasonable:

```bash
./cpueval run --suite rhaiis-sweep \
  --models tiny \
  --cores 8 \
  --workloads chat
```

This runs concurrent-load tests against `RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4`
using the RHAIIS container image you configured.

For a full production sweep (5 models × 3 core counts × 4 workloads = 60 tests), see
the [RHAIIS concurrent load testing guide](../../tests/concurrent-load/rhaiis-testing.md).

```bash
# Full matrix — expect several hours
export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii-early-access/vllm-cpu-rhel9:3.5.0-ea.2
./cpueval run --suite rhaiis-sweep
```

!!! warning "Test duration matters"
    Production benchmarks use 600-second (10-minute) test windows for stable P95/P99
    latency. Shorter runs are fine for smoke tests but will show more variance in
    tail latency. See the
    [RHAIIS testing guide](../../tests/concurrent-load/rhaiis-testing.md#erratic-p95p99-spikes-in-results)
    for details.

---

## Alternative: benchmark a server you already started

If you want to benchmark the manually deployed container from Step 2 **without** letting
Ansible restart it, use external endpoint mode:

```bash
export VLLM_ENDPOINT_MODE=external
export VLLM_ENDPOINT_URL=http://localhost:8000
export LOADGEN_HOSTNAME=localhost

./cpueval run --suite chat-smoke \
  --workload chat \
  --extra ansible_connection=local \
  --extra guidellm_use_container=false
```

In external mode, `cpueval` sends load to your running server and skips vLLM
deployment. The `--extra` flags tell Ansible to run GuideLLM locally without SSH or
containers.

---

## Troubleshooting

### Container fails to start (SELinux)

On RHEL with SELinux enforcing, you need both `--security-opt=label=disable` and the
`:Z` suffix on volume mounts. Without them, Podman cannot write to the cache directory.

### Model download fails

- Verify network access from the container (`HF_HUB_OFFLINE=0`)
- For gated models, set `HUGGING_FACE_HUB_TOKEN` / `HF_TOKEN`
- Accept the model license on [huggingface.co](https://huggingface.co) before pulling

### Poor latency / low throughput

- **RHAIIS 3.4:** ensure `export LD_PRELOAD=/usr/lib64/libomp.so` on the host
- **RHAIIS 3.5:** this is set inside the container automatically
- Increase `VLLM_CPU_KVCACHE_SPACE` for larger models (try `8` for 8B models)
- On dual-socket systems, pin vLLM and GuideLLM to separate NUMA nodes for production
  benchmarks (see the [RHAIIS testing guide](../../tests/concurrent-load/rhaiis-testing.md#numasocket-configuration))

### Ansible cannot connect to localhost

Ensure passwordless SSH is configured (Step 4) and that `DUT_HOSTNAME` resolves:

```bash
ssh $USER@$(hostname -f) 'echo ok'
```

### Port 8000 already in use

Stop any running vLLM container or process:

```bash
podman ps | grep 8000
podman stop <container-id>
```

---

## What to explore next

| Topic | Link |
|-------|------|
| Full `cpueval` CLI reference | [cpueval CLI Guide](../cpueval-cli.md) |
| RHAIIS model matrix and workloads | [RHAIIS Testing Guide](../../tests/concurrent-load/rhaiis-testing.md) |
| Test methodology and metrics | [Methodology Overview](../methodology/overview.md) |
| Platform tuning for deterministic benchmarks | [Getting Started](../getting-started.md) |
| Embedding and audio model benchmarks | [Test Suites](../test-suites.md) |

---

## Summary

| Step | Command / action | Outcome |
|------|------------------|---------|
| 1 | `podman pull` RHAIIS 3.5 CPU image | Container image ready |
| 2 | `podman run ... --model TinyLlama/...` | vLLM serving on `:8000` |
| 3 | `curl .../v1/chat/completions` | Confirmed inference works |
| 4 | `git clone` + `./cpueval doctor` | Benchmark toolchain ready |
| 5 | `./cpueval run --suite chat-smoke` | Latency and throughput measured |
| 6 | `./cpueval run --suite rhaiis-sweep` | RHAIIS model comparison |

From a single `podman run` to reproducible benchmark numbers — that is the path from
hello world to production-grade CPU inference evaluation.
