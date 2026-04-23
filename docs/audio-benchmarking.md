# Audio Model Benchmarking Guide

Comprehensive guide for benchmarking audio models (ASR, translation, chat) on vLLM CPU deployments.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Test Scenarios](#test-scenarios)
- [Understanding Results](#understanding-results)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

### What Audio Models Are Supported?

- **Audio Transcription (ASR)** - Speech-to-text (Whisper family)
- **Audio Translation** - Speech-to-text translation
- **Audio Chat** - Multimodal audio + text conversations (Ultravox)

### Key Questions Answered

**Offline Batch Processing:**
- "I have 1000 audio files - how long to transcribe them all?"
- "What's my maximum throughput (files/second)?"
- "How does audio duration affect processing time?"

**Online Serving:**
- "How many concurrent users can my transcription API support?"
- "What's the P95 latency under 10 concurrent users?"
- "Can the system handle sustained load without degradation?"

### Prerequisites

**System Requirements:**
- vLLM 0.19.0+ with audio support
- Audio dependencies: `librosa`, `soundfile`, `ffmpeg-python`
- Podman (containerized mode) or direct Python install (host mode)
- Network connectivity between load generator and vLLM server

**AWS/Cloud Users:**
- Security groups must allow TCP port 8000 between instances
- For VPC deployments, use private IPs for better performance
- See [Troubleshooting: Network Connectivity](#network-connectivity) below

## Quick Start

### 1. Configure Hosts

```bash
# Set connection variables
export DUT_HOSTNAME=your-vllm-server-hostname
export LOADGEN_HOSTNAME=your-load-generator-hostname
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_SSH_KEY=~/.ssh/your-key.pem
export HF_TOKEN=$(cat ~/hf_token)  # If using gated models

# For AWS VPC (optional but recommended):
export DUT_PRIVATE_IP=172.31.x.x  # Private IP for faster benchmarking
```

### 2. Run First Test

```bash
cd automation/test-execution/ansible

# Quick test (5 files per stage, ~2 minutes)
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-tiny" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32" \
  -e "audio_num_files=5"

# Production test (100 files per stage)
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32"
```

### 3. View Results

```bash
# Results location
ls results/audio-models/openai__whisper-tiny/transcription-throughput-*/

# Launch Streamlit dashboard
cd automation/test-execution/dashboard-examples/vllm_dashboard
./launch-dashboard.sh
# Open http://localhost:8501 and set results path to audio-models
```

## Test Scenarios

### Transcription Throughput

**Purpose:** Measure total time and throughput for processing N audio files

**Use Cases:**
- Batch processing: "How long for 100 call recordings?"
- API capacity: "How many concurrent users can we support?"

**Stages:**
1. **Sequential** - Process files one-by-one (offline batch baseline)
2. **Concurrent-2/4/8** - Simulate 2/4/8 concurrent users (online serving)
3. **Max-throughput** - Find maximum files/second capacity

**Example:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=64" \
  -e "audio_num_files=100"
```

**Key Metrics:**
- Sequential stage: Total time for batch processing
- Concurrent stages: Per-request latency (P50, P95, P99)
- Max-throughput: Files/second, audio_seconds/second

### Transcription Latency

**Purpose:** Measure latency under different concurrent loads (online serving focus)

**Use Cases:**
- SLA validation: "Can we guarantee <200ms P95 latency?"
- Capacity planning: "How many concurrent users before latency degrades?"

**Example:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-latency" \
  -e "requested_cores=32"
```

### Audio Duration Scaling

**Purpose:** Understand how processing time scales with audio length

**Use Cases:**
- Capacity planning: "If average call is 5 minutes, how many/hour?"
- Performance optimization: "Is processing time linear with audio duration?"

**Example:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=audio-duration-scaling" \
  -e "requested_cores=32"
```

### Constant Rate Stress

**Purpose:** Validate sustained load stability (production readiness)

**Use Cases:**
- Production validation: "Can we handle 10 req/s continuously?"
- Memory leak detection: "Does performance degrade over time?"

**Example:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=constant-rate-stress" \
  -e "requested_cores=64"
```

### Format Comparison

**Purpose:** Compare performance across different audio formats

**Use Cases:**
- Bandwidth optimization: "MP3 vs WAV - which is faster?"
- Quality tradeoffs: "Does higher quality improve accuracy?"

**Example:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=format-comparison" \
  -e "requested_cores=32"
```

## Understanding Results

### Result Directory Structure

```
results/audio-models/openai__whisper-small/transcription-throughput-20260423-103307/
├── sequential/               # Offline batch baseline
│   ├── benchmarks.json      # Full GuideLLM results
│   ├── benchmarks.csv       # Summary CSV
│   └── guidellm.log         # Benchmark logs
├── concurrent-2/             # 2 concurrent users
│   ├── benchmarks.json
│   └── benchmarks.csv
├── concurrent-4/             # 4 concurrent users
├── concurrent-8/             # 8 concurrent users
├── max-throughput/           # Maximum capacity
├── vllm-metrics.json         # vLLM server metrics
└── test-metadata.json        # Test configuration
```

### Key Metrics Explained

**Throughput Metrics:**
- `requests_per_second.successful.mean`: Average files/second
- `requests_per_second.successful.p50/p95/p99`: Percentile throughput

**Latency Metrics:**
- `end_to_end_latency.mean`: Average request time
- `end_to_end_latency.p95/p99`: Tail latency (SLA validation)

**Success Metrics:**
- `request_totals.successful`: Completed requests
- `request_totals.errored`: Failed requests
- Success rate = successful / (successful + errored)

**Audio-Specific Metrics (if available):**
- `audio_seconds`: Total audio duration processed
- `audio_throughput`: Audio seconds per wall-clock second
- Real-time factor = processing_time / audio_duration

### Example Interpretation

```
Stage: sequential
  Duration: 1.17s
  Successful: 5 requests
  Throughput: 4.26 req/s

Stage: concurrent-8
  Duration: 0.45s
  Successful: 5 requests
  Throughput: 11.02 req/s
  Speedup: 2.6x vs sequential
```

**Interpretation:**
- Sequential: Baseline 4.26 files/sec
- Concurrent-8: 2.6x speedup with 8 concurrent requests
- System scales well with concurrency
- Can handle ~11 files/sec or ~11 concurrent users

## Advanced Configuration

### CPU Optimization

**Auto-calculated (recommended):**
```bash
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-medium" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=64"
# TP and OMP auto-calculated based on cores
```

**Manual tuning:**
```bash
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-medium" \
  -e "requested_cores=64" \
  -e "requested_tensor_parallel=2" \
  -e "omp_num_threads=31" \
  -e "vllm_dtype=bfloat16"
```

### CPU Allocation Formula

```
Container cores:    requested_cores (e.g., 32)
├── Control plane:  2 cores (scheduler, KV cache, async ops)
└── Worker threads: (requested_cores - 2) / tensor_parallel

Examples:
  cores=32, TP=1 → OMP=30
  cores=64, TP=2 → OMP=31 per rank
  cores=16, TP=1 → OMP=14
```

### Using Different Models

**Whisper Models:**
```bash
# Tiny (fastest, 39M params)
-e "test_model=openai/whisper-tiny"

# Small (balanced, 244M params)
-e "test_model=openai/whisper-small"

# Medium (best quality, 769M params)
-e "test_model=openai/whisper-medium"
```

**Audio Chat Models:**
```bash
-e "test_model=fixie-ai/ultravox-v0_5-llama-3_2-1b"
-e "test_scenario=audio-chat"
```

### Non-Container Mode

**Requirements:**
```bash
# Install GuideLLM with audio support
pip install guidellm[audio,recommended]

# Ensure vLLM is running separately
```

**Run without containers:**
```bash
ansible-playbook audio-benchmark.yml \
  -e "test_scenario=transcription-throughput" \
  -e "guidellm_use_container=false" \
  -e "ansible_become=false"
```

## Troubleshooting

### Network Connectivity

**Symptom:** Load generator cannot reach vLLM server
```
FAILED: Verify load generator can reach vLLM server
Status: -1 (timeout)
```

**Root Cause:** Firewall/security group blocking port 8000

**Solution 1: Fix Security Group (AWS/Cloud)**
```bash
# Add inbound rule to vLLM server security group:
# - Protocol: TCP
# - Port: 8000
# - Source: Load generator security group or IP
```

**Solution 2: Use Private IP (AWS VPC)**
```bash
# Get DUT private IP (from vLLM server):
hostname -I

# Set environment variable:
export DUT_PRIVATE_IP=172.31.x.x

# Update inventory/hosts.yml:
bench_config:
  vllm_host: "{{ lookup('env', 'DUT_PRIVATE_IP') | default(hostvars['vllm-server']['ansible_host'], true) }}"
```

**Verification:**
```bash
# From load generator:
ssh ec2-user@$LOADGEN_HOSTNAME
curl -v http://$DUT_HOSTNAME:8000/health
curl -v http://$DUT_PRIVATE_IP:8000/health
```

### Missing Audio Dependencies

**Symptom:** vLLM server fails to start with audio models
```
ModuleNotFoundError: No module named 'librosa'
ModuleNotFoundError: No module named 'soundfile'
```

**Root Cause:** vLLM v0.19.0 image doesn't include audio dependencies

**Solution:** Playbook automatically builds custom image with audio deps

The playbook detects this and builds `localhost/vllm-audio-cpu:v0.19.0` with:
- librosa
- soundfile
- ffmpeg-python

**Manual verification:**
```bash
# Check if audio image exists
podman images | grep vllm-audio-cpu

# Verify dependencies
podman run --rm --entrypoint python3 \
  localhost/vllm-audio-cpu:v0.19.0 \
  -c 'import librosa; import soundfile; print("OK")'
```

**Force rebuild:**
```bash
# Remove existing image
podman rmi localhost/vllm-audio-cpu:v0.19.0

# Re-run playbook (will rebuild)
```

### Multiple vLLM Containers Running

**Symptom:** Port 8000 already in use, or multiple containers running

**Root Cause:** Previous test didn't clean up containers

**Solution:** Playbook now automatically stops all `vllm-*` containers

**Manual cleanup:**
```bash
# On vLLM server (DUT):
podman ps -a | grep vllm-
podman stop $(podman ps -a --filter "name=vllm-" --format "{{.Names}}")
podman rm $(podman ps -a --filter "name=vllm-" --format "{{.Names}}")
```

### Dataset Download Issues

**Symptom:** Benchmark hangs at "Downloading data"
```
Downloading data: 65% ... (very slow)
```

**Root Cause:** Downloading entire LibriSpeech dataset (2620 samples, 48 tar files)

**Solution:** Playbook now limits dataset samples to `2 × max_requests`

For `max_requests=100`, only 200 samples are loaded (avoids full download).

**Manual override:**
```bash
# Test with fewer files
-e "audio_num_files=10"  # Loads only 20 samples
```

### GuideLLM Backend Validation Failed

**Symptom:** GuideLLM exits during startup
```
RuntimeError: Backend validation request failed.
Could not connect to the server or validate the backend configuration.
```

**Possible Causes:**
1. vLLM server not fully started (wait longer)
2. Network connectivity (see [Network Connectivity](#network-connectivity))
3. Audio endpoint not available (missing audio support)

**Diagnostics:**
```bash
# Check vLLM is running
podman ps | grep vllm-audio

# Check vLLM logs
sudo journalctl -t vllm-audio-openai__whisper-tiny -f

# Test endpoints manually
curl http://$DUT_HOSTNAME:8000/health
curl http://$DUT_HOSTNAME:8000/v1/models
curl -X OPTIONS http://$DUT_HOSTNAME:8000/v1/audio/transcriptions
```

**Pre-flight checks (automatically run):**
- Load generator → vLLM health check
- Audio endpoint accessibility test

### Low Throughput

**Symptom:** Much lower throughput than expected

**Possible Causes:**
1. Insufficient CPU cores
2. Tensor parallelism not optimal
3. vLLM server throttled by control plane

**Solutions:**
```bash
# Increase cores
-e "requested_cores=64"

# Try different TP settings
-e "requested_tensor_parallel=1"  # vs 2

# Check if OMP threads auto-calculated correctly
# Should be: (cores - 2) / TP
```

**Diagnostics:**
```bash
# Check vLLM CPU usage
ssh $DUT_HOSTNAME
top -H -p $(pgrep -f vllm-audio)

# Check container resource limits
podman inspect vllm-audio-* | jq '.[].HostConfig.CpusetCpus'
```

### Results Not Fetched

**Symptom:** Results directory empty on controller (local machine)

**Root Cause:** Ansible fetch tasks failed

**Check:**
```bash
# On load generator:
ssh $LOADGEN_HOSTNAME
ls -la /path/to/results/audio-models/.../*/benchmarks.json
```

**Solution:**
```bash
# Fetch manually
scp -r $LOADGEN_HOSTNAME:/path/to/results/audio-models ./results/
```

## Best Practices

### 1. Start with Quick Tests

```bash
# Quick validation (5 files, 2 minutes)
-e "audio_num_files=5"

# Then scale up for production
-e "audio_num_files=100"
```

### 2. Use Private IPs in Cloud/VPC

```bash
# AWS VPC: Use private IPs for 10x lower latency
export DUT_PRIVATE_IP=172.31.x.x
```

### 3. Verify Pre-flight Checks

Watch for these in playbook output:
```
✓ Load Generator → vLLM Connectivity: PASS
✓ Audio Endpoint Pre-flight Check: PASS
```

### 4. Monitor vLLM Logs

```bash
# In separate terminal during benchmark:
ssh $DUT_HOSTNAME
sudo journalctl -t vllm-audio-* -f
```

### 5. Clean Up Between Tests

```bash
# Playbook now auto-cleans, but verify:
podman ps -a | grep vllm-
# Should show only current test container
```

### 6. Organize Results

```bash
# Results auto-organized by timestamp:
transcription-throughput-20260423-103307/
├── sequential/
├── concurrent-2/
└── ...

# Export to CSV for analysis
cp results/audio-models/.../*/benchmarks.csv /analysis/
```

### 7. Document Your Configuration

```bash
# Save test metadata
cat results/audio-models/.../test-metadata.json

{
  "model": "openai/whisper-small",
  "scenario": "transcription-throughput",
  "cores": 32,
  "tensor_parallel": 1,
  "timestamp": "20260423-103307"
}
```

## Reference

- **Audio Test Suite:** [tests/audio-models/README.md](../tests/audio-models/README.md)
- **Model Matrix:** [models/audio-models/model-matrix.yaml](../models/audio-models/model-matrix.yaml)
- **Ansible Playbook:** [automation/test-execution/ansible/audio-benchmark.yml](../automation/test-execution/ansible/audio-benchmark.yml)
- **GuideLLM Audio Docs:** [GuideLLM Audio Guide](https://github.com/vllm-project/guidellm/tree/main/docs/guides/multimodal/audio.md)
- **vLLM Audio Support:** [vLLM Audio Documentation](https://docs.vllm.ai/en/latest/usage/audio.html)
