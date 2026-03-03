# vLLM CPU Performance Evaluation Container

UBI 9-based container image for running vLLM CPU performance benchmarks.

## Quick Start

```bash
# Pull the image
podman pull quay.io/redhat-et/vllm-cpu-perf-eval:latest

# Run interactively
podman run -it --rm quay.io/redhat-et/vllm-cpu-perf-eval:latest

# Run a benchmark
podman run --rm \
  -v $(pwd)/results:/opt/vllm-perf/results \
  quay.io/redhat-et/vllm-cpu-perf-eval:latest \
  guidellm --help
```

## Supported Architectures

- linux/amd64
- linux/arm64

## Included Tools

- vLLM (CPU-optimized)
- GuideLLM
- NumPy, Pandas, psutil

## Environment Variables

- `OMP_NUM_THREADS`: OpenMP thread count (not set by container; user must set at runtime based on available cores)
- `VLLM_CPU_KVCACHE_SPACE`: KV cache size in GB (default: 40)

## Building Locally

```bash
podman build -t vllm-cpu-perf-eval:local -f Containerfile .
```

## Testing

```bash
./tests/test-container.sh
```
