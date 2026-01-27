# vLLM + guidellm Test Matrix

## Overview

This document defines the test matrix for benchmarking vLLM inference
performance with guidellm on Intel Xeon platforms. The matrix covers different
vLLM versions, deployment topologies, and OpenMP configurations.

## Test Configuration

### Common Parameters

- **Model**: `meta-llama/Llama-3.2-1B-Instruct`
- **Platform**: Intel Xeon with NUMA isolation (see
  [deterministic setup](deterministic-guidellm-benchmarking-xeon.md))
- **Test Profile**: sweep (guidellm)
- **Test Duration**: 600 seconds max per sweep point
- **Max Requests**: 2000 per sweep point

### Variable Dimensions

1. **vLLM Version**
   - v0.13.0 (with AMX optimizations)
   - v0.14.0 (with AMX optimizations)

2. **Deployment Topology**
   - Single host (vLLM + guidellm containers on same bare-metal host)
   - Dual host (vLLM on host A, guidellm on host B)

3. **OpenMP Configuration**
   - Default OMP flags (vLLM defaults)
   - Custom OMP flags:
     - `VLLM_CPU_OMP_THREADS_BIND=nobind`
     - `OMP_PLACES="{0:8}"`
     - `OMP_PROC_BIND=true`
     - `OMP_NUM_THREADS=8`

4. **Core Count** (vLLM container)
   - 8 cores
   - 16 cores
   - 24 cores
   - 32 cores
   - 64 cores
   - 96 cores

## Test Matrix

### High Priority Tests (v0.13.0 Baseline)

Focus: v0.13.0 with varied core counts and configurations

| Test ID | vLLM Ver | Topology | OMP Config | Cores | Notes                |
|---------|----------|----------|------------|-------|----------------------|
| T01     | 0.13.0   | Single   | Default    | 8     | 8 cores              |
| T02     | 0.13.0   | Single   | Default    | 16    | 16 cores             |
| T03     | 0.13.0   | Single   | Default    | 24    | 24 cores             |
| T04     | 0.13.0   | Single   | Default    | 32    | 32 cores             |
| T05     | 0.13.0   | Single   | Default    | 64    | 64 cores             |
| T06     | 0.13.0   | Single   | Default    | 96    | 96 cores             |
| T07     | 0.13.0   | Single   | Custom     | 8     | Custom OMP, 8        |
| T08     | 0.13.0   | Single   | Custom     | 16    | Custom OMP, 16       |
| T09     | 0.13.0   | Single   | Custom     | 24    | Custom OMP, 24       |
| T10     | 0.13.0   | Single   | Custom     | 32    | Custom OMP, 32       |
| T11     | 0.13.0   | Single   | Custom     | 64    | Custom OMP, 64       |
| T12     | 0.13.0   | Single   | Custom     | 96    | Custom OMP, 96       |
| T13     | 0.13.0   | Dual     | Default    | 8     | Dual, 8              |
| T14     | 0.13.0   | Dual     | Default    | 16    | Dual, 16             |
| T15     | 0.13.0   | Dual     | Default    | 24    | Dual, 24             |
| T16     | 0.13.0   | Dual     | Default    | 32    | Dual, 32             |
| T17     | 0.13.0   | Dual     | Default    | 64    | Dual, 64             |
| T18     | 0.13.0   | Dual     | Default    | 96    | Dual, 96             |
| T19     | 0.13.0   | Dual     | Custom     | 8     | Dual, custom, 8      |
| T20     | 0.13.0   | Dual     | Custom     | 16    | Dual, custom, 16     |
| T21     | 0.13.0   | Dual     | Custom     | 24    | Dual, custom, 24     |
| T22     | 0.13.0   | Dual     | Custom     | 32    | Dual, custom, 32     |
| T23     | 0.13.0   | Dual     | Custom     | 64    | Dual, custom, 64     |
| T24     | 0.13.0   | Dual     | Custom     | 96    | Dual, custom, 96     |

### Low Priority Tests (v0.14.0 Extended)

Focus: v0.14.0 comparison and validation (lower priority)

| Test ID | vLLM Ver | Topology | OMP Config | Cores | Notes                |
|---------|----------|----------|------------|-------|----------------------|
| T25     | 0.14.0   | Single   | Default    | 8     | v0.14, 8             |
| T26     | 0.14.0   | Single   | Default    | 16    | v0.14, 16            |
| T27     | 0.14.0   | Single   | Default    | 24    | v0.14, 24            |
| T28     | 0.14.0   | Single   | Default    | 32    | v0.14, 32            |
| T29     | 0.14.0   | Single   | Default    | 64    | v0.14, 64            |
| T30     | 0.14.0   | Single   | Default    | 96    | v0.14, 96            |
| T31     | 0.14.0   | Single   | Custom     | 8     | v0.14, custom, 8     |
| T32     | 0.14.0   | Single   | Custom     | 16    | v0.14, custom, 16    |
| T33     | 0.14.0   | Single   | Custom     | 24    | v0.14, custom, 24    |
| T34     | 0.14.0   | Single   | Custom     | 32    | v0.14, custom, 32    |
| T35     | 0.14.0   | Single   | Custom     | 64    | v0.14, custom, 64    |
| T36     | 0.14.0   | Single   | Custom     | 96    | v0.14, custom, 96    |
| T37     | 0.14.0   | Dual     | Default    | 8     | v0.14, dual, 8       |
| T38     | 0.14.0   | Dual     | Default    | 16    | v0.14, dual, 16      |
| T39     | 0.14.0   | Dual     | Default    | 24    | v0.14, dual, 24      |
| T40     | 0.14.0   | Dual     | Default    | 32    | v0.14, dual, 32      |
| T41     | 0.14.0   | Dual     | Default    | 64    | v0.14, dual, 64      |
| T42     | 0.14.0   | Dual     | Default    | 96    | v0.14, dual, 96      |
| T43     | 0.14.0   | Dual     | Custom     | 8     | v0.14, dual, cust, 8 |
| T44     | 0.14.0   | Dual     | Custom     | 16    | v0.14, dual, cust,16 |
| T45     | 0.14.0   | Dual     | Custom     | 24    | v0.14, dual, cust,24 |
| T46     | 0.14.0   | Dual     | Custom     | 32    | v0.14, dual, cust,32 |
| T47     | 0.14.0   | Dual     | Custom     | 64    | v0.14, dual, cust,64 |
| T48     | 0.14.0   | Dual     | Custom     | 96    | v0.14, dual, cust,96 |

**Total Test Cases**: 48

### Priority Rationale

- **High Priority (24 tests)**: Complete v0.13.0 characterization across all
  core counts (8, 16, 24, 32, 64, 96), topologies, and OMP configurations
- **Low Priority (24 tests)**: v0.14.0 validation for version comparison

## Detailed Test Configurations

### Single Host Topology

Both vLLM and guidellm run as containers on the same bare-metal host,
isolated to separate NUMA nodes.

**System Requirements**:

- Minimum 3 NUMA nodes
- Node 0: Housekeeping (kernel, IRQs, services)
- Node 1: guidellm container
- Node 2: vLLM container

**Networking**: `--network=host` for both containers (localhost communication)

### Dual Host Topology

vLLM and guidellm run on separate physical hosts.

**System Requirements**:

- Host A (vLLM): Minimum 2 NUMA nodes
  - Node 0: Housekeeping
  - Node 1: vLLM container
- Host B (guidellm): Minimum 2 NUMA nodes
  - Node 0: Housekeeping
  - Node 1: guidellm container

**Networking**: Direct network connection between hosts

## Test Execution Examples

### Core Count Configuration

The core count is controlled by adjusting the `--cpuset-cpus` parameter and
the `VLLM_CPU_OMP_THREADS_BIND` environment variable. Examples below show
how to configure for different core counts.

**Important**: Adjust CPU ranges based on your system's NUMA topology
(`lscpu -e=CPU,NODE,CORE`). Examples assume CPUs are allocated from a single
NUMA node.

### T01: vLLM 0.13.0, Single Host, Default OMP, 8 Cores

#### T01: vLLM Container (8 cores)

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=64-71 \
  --cpuset-mems=2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=64-70 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T01: guidellm Container

```bash
mkdir -p /tmp/results/T01
chmod 777 /tmp/results/T01
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-63 \
  --cpuset-mems=1 \
  -v "/tmp/results/T01:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

### T02: vLLM 0.13.0, Single Host, Default OMP, 16 Cores

#### T02: vLLM Container (16 cores)

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=64-79 \
  --cpuset-mems=2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=64-78 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T02: guidellm Container

```bash
mkdir -p /tmp/results/T02
chmod 777 /tmp/results/T02
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-63 \
  --cpuset-mems=1 \
  -v "/tmp/results/T02:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

### T03: vLLM 0.13.0, Single Host, Default OMP, 24 Cores

#### T03: vLLM Container (24 cores)

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=64-87 \
  --cpuset-mems=2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=64-86 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T03: guidellm Container

```bash
mkdir -p /tmp/results/T03
chmod 777 /tmp/results/T03
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-63 \
  --cpuset-mems=1 \
  -v "/tmp/results/T03:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

### T04: vLLM 0.13.0, Single Host, Default OMP, 32 Cores

**NOTE**: This test uses 32 cores which fits within a single NUMA node.
Tests T05 (32 cores) and T06 (64 cores) will span multiple NUMA nodes and
may show different performance characteristics due to cross-NUMA memory
access.

#### T04: vLLM Container (32 cores)

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=64-95 \
  --cpuset-mems=2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=64-94 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T04: guidellm Container

```bash
mkdir -p /tmp/results/T04
chmod 777 /tmp/results/T04
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-63 \
  --cpuset-mems=1 \
  -v "/tmp/results/T04:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

### T05: vLLM 0.13.0, Single Host, Default OMP, 32 Cores

**NOTE**: This test spans multiple NUMA nodes (requires 32 cores). Use
`--cpuset-mems=1,2` to allow memory allocation from both nodes.

#### T05: vLLM Container (32 cores)

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=48-79 \
  --cpuset-mems=1,2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=48-78 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T05: guidellm Container

```bash
mkdir -p /tmp/results/T05
chmod 777 /tmp/results/T05
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-47 \
  --cpuset-mems=1 \
  -v "/tmp/results/T05:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

### T06: vLLM 0.13.0, Single Host, Default OMP, 64 Cores

**NOTE**: This test spans multiple NUMA nodes (requires 64 cores). Use
`--cpuset-mems=1,2` to allow memory allocation from both nodes.

#### T06: vLLM Container (64 cores)

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=32-95 \
  --cpuset-mems=1,2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=32-94 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T06: guidellm Container

```bash
mkdir -p /tmp/results/T06
chmod 777 /tmp/results/T06
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=0-31 \
  --cpuset-mems=0 \
  -v "/tmp/results/T06:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

### T07: vLLM 0.13.0, Single Host, Custom OMP, 8 Cores

#### T07: vLLM Container (Custom OMP, 8 cores)

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=64-71 \
  --cpuset-mems=2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=nobind \
  -e OMP_PLACES="{0:8}" \
  -e OMP_PROC_BIND=true \
  -e OMP_NUM_THREADS=8 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T07: guidellm Container

```bash
mkdir -p /tmp/results/T07
chmod 777 /tmp/results/T07
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-63 \
  --cpuset-mems=1 \
  -v "/tmp/results/T07:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

### T17: vLLM 0.13.0, Dual Host, Default OMP, 64 Cores

#### T17 Host A: vLLM Container

```bash
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=64-127 \
  --cpuset-mems=1 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=64-126 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.13.0 \
  meta-llama/Llama-3.2-1B-Instruct \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### T17 Host B: guidellm Container

```bash
mkdir -p /tmp/results/T17
chmod 777 /tmp/results/T17
export HF_TOKEN=<hf_token>
export VLLM_HOST_IP=<host-a-ip-address>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-63 \
  --cpuset-mems=1 \
  -v "/tmp/results/T17:/results:z" \
  -e GUIDELLM_TARGET=http://${VLLM_HOST_IP}:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/guidellm:saturation-fix
```

## Metrics to Collect

Guidellm standard metrics + report.

## Test Execution Order

### Phase 1: High Priority (v0.13.0 Complete)

Execute all v0.13.0 tests (T01-T24) to establish complete baseline:

1. **Single Host, Default OMP** (Core count sweep):
   - T01: 8 cores
   - T02: 16 cores
   - T03: 24 cores
   - T04: 32 cores
   - T05: 64 cores
   - T06: 96 cores

2. **Single Host, Custom OMP** (Core count sweep):
   - T07: 8 cores
   - T08: 16 cores
   - T09: 24 cores
   - T10: 32 cores
   - T11: 64 cores
   - T12: 96 cores

3. **Dual Host, Default OMP** (Core count sweep):
   - T13: 8 cores
   - T14: 16 cores
   - T15: 24 cores
   - T16: 32 cores
   - T17: 64 cores
   - T18: 96 cores

4. **Dual Host, Custom OMP** (Core count sweep):
   - T19: 8 cores
   - T20: 16 cores
   - T21: 24 cores
   - T22: 32 cores
   - T23: 64 cores
   - T24: 96 cores

### Phase 2: Low Priority (v0.14.0 Comparison)

Execute v0.14.0 tests (T25-T48) as needed for version comparison:

1. **Single Host, Default OMP**:
   - T25-T30: 8, 16, 24, 32, 64, 96 cores

2. **Single Host, Custom OMP**:
   - T31-T36: 8, 16, 24, 32, 64, 96 cores

3. **Dual Host, Default OMP**:
   - T37-T42: 8, 16, 24, 32, 64, 96 cores

4. **Dual Host, Custom OMP**:
   - T43-T48: 8, 16, 24, 32, 64, 96 cores

## Validation Checklist

Before each test run:

- [ ] System isolation configured (see deterministic setup guide)
- [ ] Housekeeping CPUs properly assigned
- [ ] NUMA nodes verified and isolated
- [ ] IRQ affinity set to housekeeping CPUs
- [ ] No unexpected processes on isolated CPUs
- [ ] Frequency governor set to performance
- [ ] Model downloaded and cached
- [ ] HF_TOKEN exported if model requires authentication
- [ ] Results directory created with proper permissions

## Results Directory Structure

```text
/tmp/results/
├── T01/  # v0.13.0, Single, Default, 8 cores
│   ├── results.html
│   ├── results.json
│   └── results.csv
├── T02/  # v0.13.0, Single, Default, 16 cores
│   ├── results.html
│   ├── results.json
│   └── results.csv
├── T03/  # v0.13.0, Single, Default, 24 cores
│   ├── results.html
│   ├── results.json
│   └── results.csv
...
└── T48/  # v0.14.0, Dual, Custom, 96 cores
    ├── results.html
    ├── results.json
    └── results.csv
```

## Notes

- All tests assume the system has been configured following the
  [deterministic setup guide](deterministic-guidellm-benchmarking-xeon.md)
- CPU and memory pinning values in examples are placeholders - adjust based on
  your system topology (`lscpu -e=CPU,NODE,CORE`)
- For reproducible results, run each test multiple times (3-5 iterations)
  (MT: not an option for us right now)
- Ensure system is idle between test runs to avoid thermal throttling,
  do a full restart of vllm and guidellm for each run.
- Document system configuration (CPU model, memory, kernel version) with
  results
