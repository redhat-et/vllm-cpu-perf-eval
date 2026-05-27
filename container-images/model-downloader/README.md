# HuggingFace Model Downloader Container

Lightweight container for downloading HuggingFace models to a cache volume for vLLM deployment.

## Features

- Based on Red Hat UBI 10 Python 3.12 minimal image
- Pre-installed `huggingface_hub` library
- Supports gated models via `HF_TOKEN`
- Resume interrupted downloads
- Reusable across single-instance and multi-instance deployments

## Building the Image

```bash
cd container-images/model-downloader

# Build
podman build -t quay.io/octo-et/vllm-cpu-perf-eval:model-downloader .

# Push to quay.io
podman push quay.io/octo-et/vllm-cpu-perf-eval:model-downloader
```

## Usage

### Using environment variables (recommended for automation)

Downloads model specified by `MODEL_NAME` to `LOCAL_DIR`:

```bash
podman run --rm \
  -v /path/to/models:/models \
  -e MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  -e LOCAL_DIR=/models \
  quay.io/octo-et/vllm-cpu-perf-eval:model-downloader
```

### Direct cache download

Downloads to HuggingFace cache inside the container volume:

```bash
podman run --rm \
  -v hf-cache:/root/.cache/huggingface \
  quay.io/octo-et/vllm-cpu-perf-eval:model-downloader \
  /usr/local/bin/download_model.py TinyLlama/TinyLlama-1.1B-Chat-v1.0
```

Or using environment variable:

```bash
podman run --rm \
  -v hf-cache:/root/.cache/huggingface \
  -e MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  quay.io/octo-et/vllm-cpu-perf-eval:model-downloader
```

### With HuggingFace token (for gated models)

```bash
podman run --rm \
  -v /var/models:/models \
  -e MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct \
  -e LOCAL_DIR=/models \
  -e HF_TOKEN=hf_your_token_here \
  quay.io/octo-et/vllm-cpu-perf-eval:model-downloader
```

### Download to specific directory

Using command line:

```bash
podman run --rm \
  -v /var/models:/models \
  quay.io/octo-et/vllm-cpu-perf-eval:model-downloader \
  /usr/local/bin/download_model.py \
  TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --local-dir /models
```

## Integration with Ansible

Used by `roles/common/tasks/preload-model.yml` for automatic model pre-caching.

## Image Details

- **Base Image**: `registry.access.redhat.com/ubi10/python-312-minimal:10.2-1779803286`
- **Size**: ~200MB
- **Registry**: `quay.io/octo-et/vllm-cpu-perf-eval:model-downloader`
- **Python**: 3.12
- **Dependencies**: `huggingface_hub`
