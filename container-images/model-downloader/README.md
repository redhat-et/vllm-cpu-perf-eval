# HuggingFace Model & Dataset Downloader Container

Lightweight container for downloading HuggingFace models and datasets for vLLM deployment and benchmarking.

## Features

- Based on Red Hat UBI 10 Python 3.12 minimal image
- Pre-installed `huggingface_hub` and `datasets` libraries
- Supports gated models/datasets via `HF_TOKEN`
- Resume interrupted downloads
- Download from direct URLs or HuggingFace
- Unified CLI with subcommands for models and datasets
- Backwards-compatible with previous script names
- Reusable across single-instance and multi-instance deployments

## Building the Image

```bash
cd container-images/model-downloader

# Build
podman build -t quay.io/vllm-cpu-perf-eval/model-downloader:latest .

# Or use the build script
./build.sh

# Push to quay.io
podman push quay.io/vllm-cpu-perf-eval/model-downloader:latest
```

## Quick Start

The container uses a unified `download.py` script with two subcommands:

```bash
# Download a model
podman run --rm \
  -v $(pwd)/models:/models \
  -e MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  -e LOCAL_DIR=/models \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  model

# Download a dataset
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  -e DATASET_NAME=sonnet \
  -e OUTPUT_PATH=/datasets/sonnet.txt \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset
```

## Model Downloads

### Using environment variables (recommended)

```bash
podman run --rm \
  -v /path/to/models:/models \
  -e MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  -e LOCAL_DIR=/models \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  model
```

### Using command line arguments

```bash
podman run --rm \
  -v /var/models:/models \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  model TinyLlama/TinyLlama-1.1B-Chat-v1.0 --local-dir /models
```

### To HuggingFace cache

Downloads to cache inside the container (share volume between containers):

```bash
podman run --rm \
  -v hf-cache:/root/.cache/huggingface \
  -e MODEL_NAME=TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  model
```

### With HuggingFace token (for gated models)

```bash
podman run --rm \
  -v /var/models:/models \
  -e MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct \
  -e LOCAL_DIR=/models \
  -e HF_TOKEN=hf_your_token_here \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  model
```

## Dataset Downloads

### Standard datasets (sonnet)

Download vLLM's standard sonnet benchmark dataset:

```bash
# Using environment variables
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  -e DATASET_NAME=sonnet \
  -e OUTPUT_PATH=/datasets/sonnet.txt \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset

# Using command line
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset sonnet --output /datasets/sonnet.txt
```

### Download from URL

```bash
# Using environment variables
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  -e DATASET_URL=https://example.com/my-dataset.txt \
  -e OUTPUT_PATH=/datasets/my-dataset.txt \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset

# Using command line
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset --url https://example.com/data.txt --output /datasets/data.txt
```

### HuggingFace datasets

Download ShareGPT conversations (first 1000):

```bash
# Using environment variables
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  -e HF_DATASET=anon8231489123/ShareGPT_Vicuna_unfiltered \
  -e HF_SPLIT=train[:1000] \
  -e OUTPUT_PATH=/datasets/sharegpt-1k.json \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset

# Using command line
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset --hf-dataset anon8231489123/ShareGPT_Vicuna_unfiltered \
          --hf-split train[:1000] \
          --output /datasets/sharegpt-1k.json
```

Download CNN/DailyMail for summarization:

```bash
podman run --rm \
  -v $(pwd)/datasets:/datasets \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  dataset --hf-dataset cnn_dailymail \
          --hf-config 3.0.0 \
          --hf-split test[:1000] \
          --output /datasets/cnn-1k.json
```

## Backwards Compatibility

The container maintains backwards compatibility with previous script names:

```bash
# Old style (still works)
podman run --rm -v $(pwd)/models:/models \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  /usr/local/bin/download_model.py TinyLlama/TinyLlama-1.1B-Chat-v1.0

# New unified style (recommended)
podman run --rm -v $(pwd)/models:/models \
  quay.io/vllm-cpu-perf-eval/model-downloader:latest \
  model TinyLlama/TinyLlama-1.1B-Chat-v1.0
```

## Local Usage (without container)

```bash
# Models
python download.py model meta-llama/Llama-3.1-8B-Instruct --local-dir /models

# Datasets
python download.py dataset sonnet --output /datasets/sonnet.txt
python download.py dataset --url https://example.com/data.txt -o /datasets/data.txt
python download.py dataset --hf-dataset cnn_dailymail --hf-config 3.0.0 -o /datasets/cnn.json
```

## Integration with Ansible

- **Models**: Used by `roles/common/tasks/preload-model.yml` for automatic model pre-caching
- **Datasets**: Can be used in offline batch benchmark playbooks for dataset preparation

## Image Details

- **Base Image**: `registry.access.redhat.com/ubi10/python-312-minimal:10.2-1779803286`
- **Size**: ~250MB (with datasets library)
- **Registry**: `quay.io/vllm-cpu-perf-eval/model-downloader:latest`
- **Python**: 3.12
- **Dependencies**: `huggingface_hub`, `datasets`

## Available Scripts

- `/usr/local/bin/download.py` - Unified download CLI (model and dataset subcommands)
