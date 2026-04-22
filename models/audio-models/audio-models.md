---
layout: default
title: Audio Models
---

## Audio Models for vLLM CPU Performance Testing

This document describes the audio model configurations used for benchmarking automatic speech recognition (ASR), translation, and audio chat tasks on vLLM CPU deployments.

## Overview

Audio models are tested across three primary task types:
- **Transcription (ASR)** - Speech-to-text conversion
- **Translation** - Speech translation to text
- **Audio Chat** - Multimodal audio + text conversations

## Model Selection

### Whisper Models (ASR & Translation)

| Model | Parameters | Task Focus | CPU Suitability | Use Case |
|-------|-----------|------------|----------------|----------|
| **whisper-tiny** | 39M | Transcription/Translation | ✅ Excellent | Quick transcription, low latency |
| **whisper-small** | 244M | Transcription/Translation | ✅ Good | Balanced speed/quality (recommended baseline) |
| **whisper-medium** | 769M | Transcription/Translation | ⚠️ Moderate | High quality transcription |

**Selection Rationale:**
- **whisper-small** provides best balance for CPU benchmarking
- Covers range of model sizes for scalability analysis
- Standard models widely used in production

### Audio Chat Models

| Model | Parameters | Task Focus | CPU Suitability | Use Case |
|-------|-----------|------------|----------------|----------|
| **ultravox-v0_5-llama-3_2-1b** | 1B | Audio + Text Chat | ✅ Good | Multimodal conversational AI |

**Selection Rationale:**
- Multimodal capability (audio + text)
- Based on Llama 3.2 architecture (alignment with LLM tests)
- Reasonable size for CPU deployment

## Supported Endpoints

### Audio Transcription
- **Endpoint**: `/v1/audio/transcriptions`
- **Format**: OpenAI-compatible ASR API
- **Models**: All Whisper variants

### Audio Translation
- **Endpoint**: `/v1/audio/translations`
- **Format**: OpenAI-compatible translation API
- **Models**: All Whisper variants

### Audio Chat
- **Endpoint**: `/v1/chat/completions`
- **Format**: OpenAI-compatible chat API with audio support
- **Models**: Ultravox and other audio-capable chat models

## Test Datasets

### LibriSpeech ASR
- **Dataset ID**: `openslr/librispeech_asr`
- **Split**: `test` (clean and other)
- **Language**: English
- **Audio Duration**: 5-15 seconds per clip
- **Use Case**: Standard ASR baseline benchmarking

**Why LibriSpeech:**
- Industry-standard ASR benchmark
- Clean, well-labeled audio
- Diverse speakers
- Good for reproducible testing

### Common Voice
- **Dataset ID**: `mozilla-foundation/common_voice_11_0`
- **Split**: `test`
- **Language**: Multiple (en for testing)
- **Audio Duration**: 3-10 seconds per clip
- **Use Case**: Real-world diversity testing

**Why Common Voice:**
- Real-world speaker diversity
- Multiple accents and recording conditions
- Good for robustness testing

## Audio Preprocessing Configurations

### Format Presets

| Preset | Format | Bitrate | Sample Rate | Mono | Use Case |
|--------|--------|---------|-------------|------|----------|
| **mp3_64k** | MP3 | 64kbps | 16kHz | Yes | Bandwidth-constrained, mobile |
| **wav_16k** | WAV | N/A | 16kHz | Yes | Standard ASR (recommended) |
| **flac_16k** | FLAC | N/A | 16kHz | Yes | Lossless, archival |

**Recommendations:**
- **Default**: WAV 16kHz mono (standard ASR quality)
- **Bandwidth-limited**: MP3 64kbps (minimal impact on accuracy)
- **Quality-critical**: FLAC 16kHz (lossless preservation)

### Duration Buckets

Test scenarios can truncate or filter audio by duration:

| Bucket | Max Duration | Use Case |
|--------|--------------|----------|
| **short** | 5 seconds | Quick utterances, low latency testing |
| **medium** | 30 seconds | Voice messages, typical interactions |
| **long** | 120 seconds | Meetings, extended recordings |
| **unlimited** | No limit | Full audio, real-world distribution |

## Model Configuration Details

Full configuration details are in [`model-matrix.yaml`](model-matrix.yaml), which defines:

- Model IDs and HuggingFace paths
- Recommended vLLM settings (dtype, max_model_len)
- Supported endpoints
- Test scenario mappings
- Dataset configurations
- Audio preprocessing options

## Test Scenario Mappings

Each model is tested across scenarios that stress different performance aspects:

### Whisper Models

**All Whisper variants run:**
- **transcription-throughput** - Batch processing time (primary metric)
- **transcription-latency** - Per-request latency under load
- **audio-duration-scaling** - Performance vs audio length
- **constant-rate-stress** - Sustained load stability (larger models only)

### Audio Chat Model Tests

**Ultravox runs:**
- **audio-chat-throughput** - Multimodal conversation throughput
- **audio-chat-latency** - Response time characteristics

## CPU Optimization Parameters

Audio models have specific CPU tuning parameters:

| Parameter | Default | Description | Impact |
|-----------|---------|-------------|--------|
| `vllm_dtype` | float16 | Model precision | Memory & speed |
| `vllm_max_model_len` | 448 | Max sequence length (Whisper) | Context capacity |
| `vllm_kvcache_space` | 2GiB | KV cache allocation | Batch size |
| `requested_cores` | Required | CPU cores to allocate | Throughput |
| `requested_tensor_parallel` | Auto | Tensor parallelism (1,2,4,8) | Model parallelism |
| `omp_num_threads` | Auto | OpenMP threads | CPU utilization |

**Auto-calculation:**
- `tensor_parallel` = largest power of 2 that divides cores
- `omp_num_threads` = cores / tensor_parallel

**Example:**
```bash
requested_cores=64  # → TP=2, OMP=32
→ requested_tensor_parallel=2 (auto)
→ omp_num_threads=32 (auto)
```

## Performance Expectations

### Whisper-small (Baseline)

**Expected Performance (32 cores, sequential):**
- Throughput: ~10 files/sec
- Real-time factor: ~0.1-0.2 (5-10x faster than real-time)
- Latency: 80-150ms per file (for 6-second audio)

**Scaling (concurrent):**
- 4 workers: ~3.5x speedup
- 8 workers: ~6x speedup (if cores available)

### Optimization Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Real-time factor | < 1.0 | Faster than real-time processing |
| P99 latency | < 500ms | Acceptable for interactive use |
| Throughput | > 100 audio_sec/sec | Efficient batch processing |
| Error rate | < 0.1% | Production reliability |

## Model Reuse Across Tests

Audio models are reused across test scenarios to enable:
- Direct performance comparison
- Scalability analysis (sequential → concurrent → max throughput)
- Format impact analysis (MP3 vs WAV vs FLAC)
- Duration scaling characterization

## Adding New Audio Models

To add a new audio model:

1. **Update [`model-matrix.yaml`](model-matrix.yaml)**:
   ```yaml
   audio_models:
     - name: "new-model"
       model_id: "org/new-model"
       task_type: "transcription|translation|audio_chat"
       supported_endpoints: ["/v1/audio/..."]
       test_scenarios: ["transcription-throughput", ...]
       recommended_settings:
         dtype: "float16"
         max_model_len: 448
   ```

2. **Verify model compatibility**:
   - Model must support OpenAI-compatible audio endpoints
   - Must run on vLLM (check vLLM supported models list)

3. **Run baseline test**:
   ```bash
   ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
     -e "test_model=org/new-model" \
     -e "test_scenario=transcription-throughput" \
     -e "requested_cores=32" \
     -e "audio_num_files=10"  # Optional: override number of files (default from scenario YAML)
   ```

4. **Document results** and update this file with performance expectations

## Running Audio Benchmarks

### Basic Usage

```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-tiny" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32"
```

### Optional Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `audio_num_files` | Override number of audio files to process per stage | From scenario YAML | `-e "audio_num_files=10"` |
| `vllm_dtype` | Model precision | `auto` (vLLM chooses) | `-e "vllm_dtype=float16"` |
| `vllm_max_model_len` | Max sequence length | `448` | `-e "vllm_max_model_len=512"` |
| `vllm_kvcache_space` | KV cache allocation | `2GiB` | `-e "vllm_kvcache_space=4GiB"` |
| `requested_tensor_parallel` | Tensor parallelism | Auto (1 or 2) | `-e "requested_tensor_parallel=2"` |
| `omp_num_threads` | OpenMP threads | Auto | `-e "omp_num_threads=30"` |

### Examples

**Quick test with 10 files:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-tiny" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=32" \
  -e "audio_num_files=10"
```

**Production test with 100 files:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_model=openai/whisper-small" \
  -e "test_scenario=transcription-throughput" \
  -e "requested_cores=64" \
  -e "audio_num_files=100"
```

**External vLLM endpoint:**
```bash
ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \
  -e "test_scenario=transcription-throughput" \
  -e vllm_endpoint.mode=external \
  -e vllm_endpoint.external.url=http://your-vllm-host:8000 \
  -e "audio_num_files=50"
```

## See Also

- **[Audio Test Scenarios](../../tests/audio-models/README.md)** - Detailed test documentation
- **[Audio Benchmark Playbook](../../automation/test-execution/ansible/audio-benchmark.yml)** - Ansible automation
- **[Model Matrix YAML](model-matrix.yaml)** - Full configuration reference
- **[GuideLLM Audio Guide](https://github.com/vllm-project/guidellm/tree/main/docs/guides/multimodal/audio.md)** - GuideLLM documentation
