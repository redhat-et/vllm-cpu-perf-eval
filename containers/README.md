# Containers Directory

Container definitions and configurations for vLLM and GuideLLM.

## Structure

```text
containers/
├── guidellm/              # GuideLLM benchmarking container
│   ├── Containerfile
│   └── entrypoint.sh
└── vllm/                  # vLLM inference server container
    ├── Containerfile.cpu
    ├── entrypoint.sh
    └── scripts/
```

## Container Runtimes

All container files are compatible with both Docker and Podman:

- **Containerfile**: Works with `docker build` and `podman build`
- **compose.yaml**: Works with `docker compose` and `podman-compose`
- **Rootless**: Full support for Podman rootless mode

## Building Containers

### Using Docker

```bash
# Build vLLM container
docker build -f containers/vllm/Containerfile.cpu -t vllm-cpu:local .

# Build GuideLLM container
docker build -f containers/guidellm/Containerfile -t guidellm:local .
```

### Using Podman

```bash
# Build vLLM container
podman build -f containers/vllm/Containerfile.cpu -t vllm-cpu:local .

# Build GuideLLM container
podman build -f containers/guidellm/Containerfile -t guidellm:local .
```

## Using Pre-built Images

The test configurations use pre-built images by default:

- **vLLM**: `vllm/vllm-cpu:latest`
- **GuideLLM**: `neuralmagic/guidellm:latest`

To use custom images, set environment variables:

```bash
export VLLM_IMAGE=vllm-cpu:local
export GUIDELLM_IMAGE=guidellm:local
```

## Container Optimizations

### CPU Pinning

Containers are configured to run on isolated CPU cores for deterministic
performance:

```yaml
services:
  vllm-server:
    cpuset: "0-31"  # NUMA node 0
    mem_limit: "64g"
```

### SELinux Labels (Podman)

Volume mounts include `:z` flag for SELinux compatibility:

```yaml
volumes:
  - ./models:/models:ro,z
```

### Rootless Mode (Podman)

Enable rootless mode by setting:

```bash
export PODMAN_USERNS=keep-id
```

## Documentation

- Docker guide: `docs/containers/docker-guide.md`
- Podman guide: `docs/containers/podman-guide.md`
- Runtime comparison: `docs/containers/runtime-comparison.md`
- Container tuning: `docs/containers/container-tuning.md`
