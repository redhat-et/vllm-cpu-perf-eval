# Audio Model Testing Suite

Comprehensive test suite for evaluating audio model performance on vLLM CPU deployments.

## Overview

This test suite provides automated benchmarking for:
- **Audio Transcription (ASR)** - Speech-to-text conversion
- **Audio Translation** - Speech translation to text
- **Audio Chat** - Multimodal audio + text conversations

### Key Questions Answered

This test suite covers **two distinct usage patterns**:

**1. Offline Batch Processing:**
- "I have N audio files on disk - how long to transcribe them all?"
- Focus: Total completion time, maximum throughput
- Use cases: Post-call transcription, media archive processing, batch ETL

**2. Online Serving:**
- "How many concurrent users can submit audio for real-time transcription?"
- Focus: Per-request latency (P50, P95, P99), concurrent user experience
- Use cases: Live transcription API, voice assistant backend, streaming services

Plus comprehensive coverage of scalability, format impact, and sustained load behavior.

## Test Scenarios

| Scenario | Primary Focus | Serving Pattern | Use Case |
|----------|--------------|-----------------|----------|
| **[transcription-throughput](transcription-throughput.yaml)** | Total time to process N files | **Both** (Offline + Online) | Batch processing + concurrent user simulation |
| **[transcription-latency](transcription-latency.yaml)** | Per-request latency under load | **Online Serving** | Real-time transcription, SLA validation |
| **[audio-duration-scaling](audio-duration-scaling.yaml)** | Performance vs audio length | **Offline Batch** | Capacity planning, workload optimization |
| **[constant-rate-stress](constant-rate-stress.yaml)** | Sustained load stability | **Online Serving** | Production readiness, resource planning |
| **[format-comparison](format-comparison.yaml)** | Audio format impact | **Offline Batch** | Bandwidth optimization, quality tradeoffs |

### Understanding Test Profiles

**GuideLLM Profiles Explained:**

- **`synchronous`** - Sequential processing (one request at a time)
  - **Serving pattern:** Offline batch baseline
  - **Measures:** Total time for N files processed serially
  - **Analogy:** Single-threaded batch job

- **`concurrent` with `rate: N`** - Maintains N concurrent requests
  - **Serving pattern:** Online serving simulation
  - **Measures:** Latency under N concurrent users
  - **Analogy:** N users simultaneously using a web API
  - **Important:** This is NOT parallel batch processing - it simulates continuous concurrent load

- **`throughput`** - Maximum request rate the server can sustain
  - **Serving pattern:** Capacity test (applies to both)
  - **Measures:** Maximum files/sec, maximum audio_seconds/sec
  - **Analogy:** Stress test to find breaking point

### Which Test Should I Run?

**Use Case: "I have 1000 audio files from call recordings, need to transcribe them all overnight"**
→ **Offline batch processing**
→ Run: `transcription-throughput` (focus on sequential + max-throughput stages)
→ Key metric: Total wall-clock time, files/second

**Use Case: "Building a real-time transcription API for customer calls"**
→ **Online serving**
→ Run: `transcription-latency` + `constant-rate-stress`
→ Key metrics: P95 latency, concurrent user capacity, sustained load stability

**Use Case: "Need to support both batch exports and live API"**
→ **Both patterns**
→ Run: `transcription-throughput` (all stages) + `transcription-latency`
→ Analyze offline (sequential, max-throughput) and online (concurrent-N) results separately

## Quick Start

### Prerequisites

1. **Ensure Ansible is configured:**
   ```bash
   cd automation/test-execution/ansible
   ansible-galaxy collection install -r requirements.yml
   ```

2. **Verify system access:**
   ```bash
   ansible -i inventory/hosts.yml all -m ping
   ```

3. **Container runtime:**
   - Podman installed on load generator host
   - GuideLLM runs in container (ghcr.io/vllm-project/guidellm:v0.6.0)
   - No need to install guidellm on host

### Run Your First Test

**Option 1: Managed Mode (vLLM started by Ansible)**

```bash
cd automation/test-execution/ansible

# Transcription throughput test (answers: how long for N files?)
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32"

# Quick test with custom file count
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-tiny" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32" \
  -e "audio_num_files=10"  # Override to 10 files per stage
```

**Option 2: External Endpoint (vLLM already running)**

```bash
# Point to existing vLLM server
export VLLM_ENDPOINT_URL=http://your-vllm-host:8000

ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_scenario=transcription-throughput" \
  -e vllm_endpoint.mode=external \
  -e vllm_endpoint.external.url=$VLLM_ENDPOINT_URL \
  -e "audio_num_files=50"  # Optional: override file count
```

## Detailed Usage

### Test Scenario: Transcription Throughput

**Answers:** How long to transcribe 100 audio files? (Offline batch + Online serving patterns)

```bash
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32" \
  -e "requested_tensor_parallel=1"
```

**What it measures (5 stages):**

1. **Sequential** (`profile: synchronous`) - **OFFLINE BATCH BASELINE**
   - Process 100 files one at a time, serially
   - Answers: "How long if I process files one-by-one?"
   - Metric focus: Total wall-clock time

2. **Concurrent-2/4/8** (`profile: concurrent`, `rate: 2/4/8`) - **ONLINE SERVING**
   - Simulate 2/4/8 concurrent users continuously submitting audio
   - Answers: "What's the latency when N users are using the API simultaneously?"
   - Metric focus: Per-request latency (P50, P95, P99), concurrent user experience
   - **NOT** parallel batch processing - this maintains continuous concurrent load

3. **Max-throughput** (`profile: throughput`, `rate: 50`) - **CAPACITY TEST**
   - Maintains 50 concurrent request streams to saturate server
   - Answers: "What's the maximum files/second this server can sustain?"
   - Metric focus: Maximum files/sec, maximum audio_seconds/sec
   - Use for: Capacity planning, finding server limits
   - **Note:** `rate: 50` is configurable in scenario YAML - increase for load balancer/multi-instance setups

**Key Distinction:**
- **Offline batch:** "I have 100 files on disk, transcribe them all ASAP" → Use sequential (baseline) and max-throughput results
- **Online serving:** "How many users can use my transcription API concurrently?" → Use concurrent-N results

**Results location:**
```
results/audio-models/openai__whisper-small/transcription-throughput-20260422-110932/
├── sequential/               # Offline batch baseline
│   ├── benchmarks.json
│   └── benchmarks.csv
├── concurrent-2/             # Online: 2 concurrent users
│   ├── benchmarks.json
│   └── benchmarks.csv
├── concurrent-4/             # Online: 4 concurrent users
│   ├── benchmarks.json
│   └── benchmarks.csv
├── concurrent-8/             # Online: 8 concurrent users
│   ├── benchmarks.json
│   └── benchmarks.csv
├── max-throughput/           # Maximum capacity test
│   ├── benchmarks.json
│   └── benchmarks.csv
├── vllm-metrics.json
└── test-metadata.json
```

Results are organized by timestamp (`{scenario}-{YYYYMMDD-HHMMSS}`) to prevent overwriting on subsequent runs.

### Test Scenario: Transcription Latency

**Serving Pattern:** **ONLINE SERVING** (Real-time API use case)

**Answers:** What is latency under different concurrent loads?

```bash
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-latency" \
  -e "requested_cores=32"
```

**What it measures:**
- Baseline latency (single user, no contention)
- Latency under light/medium/heavy concurrent load (2/5/10 users)
- P50/P95/P99 latency percentiles
- Latency degradation vs concurrent user count

**Use case:** SLA validation for real-time transcription APIs (e.g., "Can we guarantee <200ms P95 latency for up to 10 concurrent users?")

### Test Scenario: Audio Duration Scaling

**Serving Pattern:** **OFFLINE BATCH** (Sequential processing)

**Answers:** How does processing time scale with audio length?

```bash
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=audio-duration-scaling" \
  -e "requested_cores=32"
```

**What it measures:**
- Processing time for short (1-5s) clips
- Medium (5-15s) clips
- Long (15-30s) clips
- Full-length (no truncation)
- Linear vs non-linear scaling (is it O(n) with audio duration?)

**Use case:** Capacity planning - "If our average audio file is 30 seconds, how many can we process per hour?"

### Test Scenario: Constant Rate Stress

**Serving Pattern:** **ONLINE SERVING** (Sustained production load)

**Answers:** Can the system handle sustained load? Any memory leaks or degradation?

```bash
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=constant-rate-stress" \
  -e "requested_cores=64" \
  -e "requested_tensor_parallel=2"
```

**What it measures:**
- Sustained load at 2, 5, 10 req/s (5 min each)
- Extended duration test (15 min)
- Latency stability over time (does P95 degrade after 10 minutes?)
- Memory growth/leaks (resource exhaustion detection)
- Error rates under sustained load

**Use case:** Production readiness validation - "Can this deployment handle 10 req/s continuously for hours without degradation?"

### Test Scenario: Format Comparison

**Serving Pattern:** **OFFLINE BATCH** (Sequential processing)

**Answers:** Which audio format provides best performance/bandwidth tradeoff?

```bash
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=format-comparison" \
  -e "requested_cores=32"
```

**What it measures:**
- MP3 (64kbps, 128kbps) - lossy compression
- WAV (uncompressed, 8kHz/16kHz/48kHz) - raw audio
- FLAC (lossless) - lossless compression
- Stereo vs Mono channel impact
- Decoding overhead vs network transfer time

**Use case:** Bandwidth optimization - "Should we send 64kbps MP3 or 16kHz WAV? Does higher quality improve accuracy or just waste bandwidth?"

## Advanced Configuration

### CPU Optimization

**Auto-calculated (recommended):**
```bash
# Tensor parallel and OMP threads auto-calculated
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-medium" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=64"
```

**Manual configuration:**
```bash
# Fine-tune CPU parameters
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-medium" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=64" \
  -e "requested_tensor_parallel=2" \
  -e "omp_num_threads=32" \
  -e "vllm_dtype=bfloat16" \
  -e "vllm_max_model_len=448" \
  -e "vllm_kvcache_space=4GiB"
```

### Parameters Explained

| Parameter | Description | Default | Impact |
|-----------|-------------|---------|--------|
| `requested_cores` | Total CPU cores to allocate | Required | Higher = more throughput |
| `audio_num_files` | Number of audio files per stage | From scenario YAML | Override file count for all stages |
| `requested_tensor_parallel` | Tensor parallelism degree (1,2) | Auto (1 or 2) | Parallel model execution |
| `omp_num_threads` | OpenMP threads per TP rank | Auto | CPU thread utilization |
| `vllm_dtype` | Model precision | `auto` (vLLM chooses) | Memory & speed tradeoff |
| `vllm_max_model_len` | Max sequence length | `448` (Whisper) | Memory usage |
| `vllm_kvcache_space` | KV cache memory | `2GiB` | Batch size capacity |

**🔧 CPU Allocation Breakdown (Auto-Calculated)**

The playbook automatically reserves 2 cores for vLLM's internal control plane. When you specify `requested_cores=32`:

```
Container Allocation:  cores 0-31 (32 total)
├── Control Plane:     2 cores (scheduler, KV cache, async ops)
└── Worker Threads:    30 cores (OMP_NUM_THREADS=30)
    └── Per TP rank:   30/TP cores
```

**Formula:**
```python
OMP_NUM_THREADS = (requested_cores - 2) / tensor_parallel

Examples:
  requested_cores=32, TP=1 → OMP=30 (reserve 2 for control plane)
  requested_cores=64, TP=2 → OMP=31 (reserve 2 for control plane)
  requested_cores=8,  TP=1 → OMP=6  (reserve 2 for control plane)
```

**Why reserve 2 cores from OMP?**
- **vLLM control plane threads** need CPU time for:
  - Main Python thread (GIL, request dispatcher, scheduler)
  - KV cache manager (memory allocation, cache eviction)
  - Async operations (network I/O, tokenization, preprocessing)
- **Without reservation**: OMP workers saturate all cores, starving control plane
- **With reservation**: Control plane gets dedicated CPU capacity, stable performance

### Container and Execution Mode

**Default behavior (containerized):**
- vLLM runs in container (podman)
- GuideLLM runs in container (ghcr.io/vllm-project/guidellm:v0.6.0)
- Requires sudo access for container management

**Override for non-root execution:**
```bash
# Run without containers and without sudo
ansible-playbook audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32" \
  -e "guidellm_use_container=false" \
  -e "ansible_become=false"

# Prerequisites for host mode:
#   pip install guidellm[audio,recommended]
#   vLLM must be running separately
```

**Use cases for non-container mode:**
- Development/testing environments
- Systems without podman/docker
- Running as non-root user without sudo
- Custom vLLM installations

### Using Different Models

**Whisper models:**
```bash
# Tiny (fastest, 39M params)
-e "test_model=openai/whisper-tiny"

# Small (balanced, 244M params)
-e "test_model=openai/whisper-small"

# Medium (high quality, 769M params)
-e "test_model=openai/whisper-medium"
```

**Audio chat models:**
```bash
-e "test_model=fixie-ai/ultravox-v0_5-llama-3_2-1b"
-e "test_scenario=audio-chat"
```

### Using Different Datasets

**LibriSpeech (default):**
- Clean English speech
- Good for baseline benchmarks

**Common Voice (more diversity):**

Edit the test scenario YAML file:
```yaml
dataset:
  name: "mozilla-foundation/common_voice_11_0"
  config: "en"
  split: "test"
  audio_column: "audio"
```

**Custom dataset:**
- Must be HuggingFace dataset or local JSON/CSV
- Must have audio column with supported format

## Results Analysis

### Understanding Metrics

**Audio-specific metrics:**
- `audio_seconds`: Total duration of audio processed
- `audio_samples`: Raw sample count
- `audio_bytes`: Payload size
- `audio_tokens`: Model tokens (if reported)

**Performance metrics:**
- `Request throughput (req/s)`: Files per second
- `Audio throughput (audio_seconds/s)`: Audio seconds processed per wall-clock second
- `Real-time factor`: processing_time / audio_duration
  - < 1.0 = Faster than real-time ✅
  - = 1.0 = Real-time processing
  - > 1.0 = Slower than real-time ⚠️

**Latency metrics:**
- `Mean E2E latency`: Average request time
- `P95/P99 latency`: Tail latency (SLA validation)
- `TTFT`: Time to first token (if supported)

### Example Results Interpretation

**Transcription Throughput Results:**
```
Sequential:     10 files/sec,  80 audio_seconds/sec
Concurrent (4): 35 files/sec, 280 audio_seconds/sec
Speedup:        3.5x (near-linear scaling)
Real-time factor: 0.125 (8x faster than real-time)
```

**Interpretation:**
- Sequential baseline: 10 files/sec
- Concurrency helps significantly (3.5x speedup)
- Processing 8x faster than real-time
- Can handle 35 simultaneous users or batch 35 files

## Troubleshooting

### Common Issues

**Issue:** GuideLLM container image pull fails
```bash
# Solution: Check container registry access
podman pull ghcr.io/vllm-project/guidellm:v0.6.0

# Or set custom image
export GUIDELLM_CONTAINER_IMAGE=your-registry/guidellm:tag
```

**Issue:** Audio encoding errors
```bash
# Solution: Check dataset audio column format
# Supported: HF Audio feature, WAV/MP3/FLAC files, URLs, numpy/torch arrays
```

**Issue:** vLLM server won't start
```bash
# Check container logs
podman logs vllm-audio-<test_run_id>

# Check journald logs
journalctl -t vllm-audio-<test_run_id> -f

# Common causes:
# - Insufficient memory
# - Model download failed
# - Port already in use
```

**Issue:** Low throughput
```bash
# Try increasing cores or tensor parallel
-e "requested_cores=64" \
-e "requested_tensor_parallel=2"
```

**Issue:** Host-mode execution (non-container)
```bash
# Set use_container to false in group_vars
# Then install guidellm on load generator host:
pip install guidellm[audio,recommended]
```

## Integration with Existing Tests

The audio test suite follows the same patterns as LLM and embedding tests:

```
vllm-cpu-perf-eval/
├── models/
│   ├── llm-models/
│   ├── embedding-models/
│   └── audio-models/          # ← New
│       └── model-matrix.yaml
├── tests/
│   ├── concurrent-load/
│   ├── embedding-models/
│   └── audio-models/          # ← New
│       ├── transcription-throughput.yaml
│       ├── transcription-latency.yaml
│       └── ...
└── automation/test-execution/ansible/
    ├── llm-benchmark-auto.yml
    ├── embedding-benchmark.yml
    └── audio-benchmark.yml    # ← New
```

## Next Steps

1. **Run baseline test** to establish performance baseline
2. **Optimize CPU settings** based on results
3. **Run comprehensive suite** for production validation
4. **Compare results** across different models/configurations
5. **Integrate into CI/CD** for regression testing

## Reference

- **GuideLLM Audio Docs:** [guidellm/docs/guides/multimodal/audio.md](https://github.com/vllm-project/guidellm/tree/main/docs/guides/multimodal/audio.md)
- **Supported Models:** See [models/audio-models/model-matrix.yaml](../../models/audio-models/model-matrix.yaml)
- **Test Scenarios:** All YAML files in this directory
- **Ansible Playbook:** [automation/test-execution/ansible/audio-benchmark.yml](../../automation/test-execution/ansible/audio-benchmark.yml)
