# Load Generator Abstraction Layer - Usage Guide

## Overview

The load generator abstraction provides a unified interface for different benchmarking tools:
- **GuideLLM**: Full-featured LLM benchmarking (generative + embedding workloads)
- **vLLM bench**: Built-in vLLM bench serve (generative + embedding workloads)
- **MTEB**: Massive Text Embedding Benchmark (embedding quality evaluation)

## Architecture

```
ansible/roles/common/tasks/loadgen-command.yml  ← Ansible integration
                                                ↓
shared/loadgens/cli.py                          ← CLI interface
                                                ↓
shared/loadgens/
  ├── base.py                                   ← Abstract interfaces
  ├── guidellm_loadgen.py                       ← GuideLLM implementation
  ├── vllm_bench_loadgen.py                     ← vLLM bench implementation
  └── mteb_loadgen.py                           ← MTEB implementation
```

## Load Generators

### GuideLLM
**Purpose**: Comprehensive LLM benchmarking with multiple profiles
**Container**: `ghcr.io/vllm-project/guidellm:v0.7.1`
**Workloads**: chat, rag, code, summarization, reasoning, embedding
**Profiles**: sweep, synchronous, concurrent, throughput, constant, poisson
**Output**: JSON, HTML, CSV

### vLLM bench
**Purpose**: Built-in vLLM benchmarking tool
**Container**: `vllm/vllm-openai-cpu:v0.25.1`
**Workloads**: All generative + embedding
**Output**: JSON with throughput, latency, TTFT, TPOT metrics

### MTEB
**Purpose**: Embedding model quality evaluation
**Container**: `quay.io/vllm-cpu-perf-eval/vllm-mteb:latest`
**Workloads**: embedding only
**Task Presets**: quick, standard, comprehensive
**Output**: JSON with quality metrics (accuracy, retrieval scores)

## CLI Usage

### List available load generators
```bash
python3 -m shared.loadgens list
# Returns: ["guidellm", "vllm_bench", "mteb"]
```

### Get load generator information
```bash
python3 -m shared.loadgens get-loadgen guidellm
```

**Output**:
```json
{
  "name": "guidellm",
  "version": "0.7.1",
  "image": "ghcr.io/vllm-project/guidellm:v0.7.1",
  "output_format": "json",
  "supported_workloads": {
    "chat": true,
    "rag": true,
    "code": true,
    "summarization": true,
    "embedding": true
  }
}
```

### Generate load generator configuration
```bash
python3 -m shared.loadgens get-config guidellm \
  --target http://localhost:8000 \
  --model "TinyLlama/TinyLlama-1.1B-Chat-v1.0" \
  --workload chat \
  --max-requests 100 \
  --max-seconds 300 \
  --rate "10,20,40" \
  --output-path /results \
  --extra-args '{"profile": "sweep"}'
```

**Output**:
```json
{
  "command": [...],
  "env": {
    "GUIDELLM_TARGET": "http://localhost:8000",
    "GUIDELLM_MODEL": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    ...
  },
  "image": "ghcr.io/vllm-project/guidellm:v0.7.1",
  "output_format": "json"
}
```

### Parse load generator results
```bash
python3 -m shared.loadgens parse-results guidellm /path/to/results.json
```

**Output**:
```json
{
  "requests_total": 100,
  "requests_successful": 100,
  "requests_failed": 0,
  "throughput_rps": 12.5,
  "throughput_tps": 625.0,
  "latency_mean_ms": 45.2,
  "latency_p50_ms": 42.1,
  "latency_p95_ms": 68.3,
  "latency_p99_ms": 85.7,
  "ttft_mean_ms": 12.3,
  "tpot_mean_ms": 2.1,
  "duration_seconds": 8.0
}
```

## Ansible Integration

### Using the load generator abstraction task

Include the `loadgen-command.yml` task to generate configuration:

```yaml
- name: Generate load generator configuration
  ansible.builtin.include_role:
    name: common
    tasks_from: loadgen-command
  vars:
    loadgen_name: "guidellm"  # or "vllm_bench", "mteb"
    loadgen_config:
      target_url: "http://{{ bench_config.vllm_host }}:{{ bench_config.vllm_port }}"
      model: "{{ test_model }}"
      workload_type: "chat"
      max_requests: 1000
      max_seconds: 600
      rate: "10,20,40"
      output_path: "/results"
      dataset: "random"  # optional
      extra_args:  # optional, load generator-specific
        profile: "sweep"
```

### Output variables

The task sets these facts:

```yaml
loadgen_abstraction_used: true  # or false if abstraction unavailable
loadgen_cmd: [...]              # Command as list
loadgen_env: {...}              # Environment variables
loadgen_image: "..."            # Container image
loadgen_output_format: "json"   # Output format
```

### Example: Running with the abstraction

```yaml
- name: Generate configuration
  ansible.builtin.include_role:
    name: common
    tasks_from: loadgen-command
  vars:
    loadgen_name: "vllm_bench"
    loadgen_config:
      target_url: "http://localhost:8000"
      model: "{{ test_model }}"
      workload_type: "embedding"
      max_requests: 250
      rate: "inf"
      output_path: "/results/baseline.json"

- name: Run if abstraction available
  when: loadgen_abstraction_used | default(false)
  ansible.builtin.command:
    cmd: >
      podman run --rm --network host
      -v {{ results_dir }}:{{ results_dir }}:z
      {{ loadgen_image }}
      {{ loadgen_cmd | join(' ') }}
  environment: "{{ loadgen_env }}"
```

### Graceful fallback

The abstraction layer provides graceful fallback if the module is unavailable:

```yaml
- name: Generate configuration
  ansible.builtin.include_role:
    name: common
    tasks_from: loadgen-command
  vars:
    loadgen_name: "guidellm"
    loadgen_config: {...}

- name: Use abstraction if available
  when: loadgen_abstraction_used
  block:
    - name: Run with abstraction
      # Use loadgen_cmd, loadgen_env, loadgen_image
      ...

- name: Fallback to traditional approach
  when: not loadgen_abstraction_used
  block:
    - name: Run traditional commands
      # Original implementation
      ...
```

## Load Generator-Specific Configuration

### GuideLLM extra_args
```yaml
extra_args:
  profile: "sweep"              # sweep, synchronous, concurrent, throughput
  processor: "model-name"       # Tokenizer to use
  warmup: 0.1                   # Warmup percentage
  cooldown: 30                  # Cooldown seconds
  max_concurrency: 128          # Max concurrent requests
  saturation_threshold: 0.98    # Saturation detection threshold
```

### vLLM bench extra_args
```yaml
extra_args:
  random-input-len: 512         # Random input length
  endpoint: "/v1/embeddings"    # API endpoint
  HF_TOKEN: "hf_..."            # Hugging Face token
```

### MTEB extra_args
```yaml
extra_args:
  task_preset: "quick"          # quick, standard, comprehensive
  tasks: "TaskA,TaskB"          # Or specific task list
  languages: "eng"              # Language codes
  batch_size: 32                # Batch size
  HF_TOKEN: "hf_..."            # Hugging Face token
```

## Configuration Object

All load generators use the standardized `LoadGenConfig`:

```python
@dataclass
class LoadGenConfig:
    target_url: str               # Target endpoint URL
    model: str                    # Model name
    workload_type: str = "chat"   # Workload type
    max_requests: int = 1000      # Maximum requests
    max_seconds: int = 600        # Maximum duration
    rate: Optional[str] = None    # Request rate(s)
    output_path: str = "/results" # Output path
    dataset: Optional[str] = None # Dataset name/path
    extra_args: Dict = {}         # Load generator-specific args
```

## Metrics Object

All load generators return standardized `LoadGenMetrics`:

```python
@dataclass
class LoadGenMetrics:
    requests_total: int = 0
    requests_successful: int = 0
    requests_failed: int = 0
    throughput_rps: float = 0.0       # Requests per second
    throughput_tps: float = 0.0       # Tokens per second
    latency_mean_ms: float = 0.0      # Mean latency
    latency_p50_ms: float = 0.0       # P50 latency
    latency_p95_ms: float = 0.0       # P95 latency
    latency_p99_ms: float = 0.0       # P99 latency
    ttft_mean_ms: float = 0.0         # Time to first token
    tpot_mean_ms: float = 0.0         # Time per output token
    duration_seconds: float = 0.0     # Total duration
    raw_metrics: Dict = {}            # Original metrics
```

**Note**: Not all load generators populate all fields. For example, MTEB focuses on quality metrics, not performance metrics.

## Adding New Load Generators

To add a new load generator:

1. **Create implementation** in `shared/loadgens/yourloadgen.py`:
```python
from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics

class YourLoadGen(LoadGenerator):
    @property
    def name(self) -> str:
        return "yourloadgen"

    @property
    def version(self) -> str:
        return "1.0"

    def get_command(self, config: LoadGenConfig) -> List[str]:
        # Return command list
        pass

    def get_container_image(self) -> str:
        return "your/container:tag"

    def get_env_vars(self, config: LoadGenConfig) -> Dict[str, str]:
        # Return environment variables
        pass

    def parse_results(self, results_path: str) -> LoadGenMetrics:
        # Parse results to standard metrics
        pass

    def validate_config(self, config: LoadGenConfig) -> None:
        # Validate configuration
        pass

    def supports_workload(self, workload_type: str) -> bool:
        # Return True if workload is supported
        pass
```

1. **Register** in `shared/loadgens/__init__.py`:

```python
from .yourloadgen import YourLoadGen

LOADGENS = {
    "guidellm": GuideLLMLoadGen,
    "vllm_bench": VLLMBenchLoadGen,
    "mteb": MTEBLoadGen,
    "yourloadgen": YourLoadGen,  # Add here
}
```

1. **Test** via CLI:
```bash
python3 -m shared.loadgens list
python3 -m shared.loadgens get-loadgen yourloadgen
```

## Comparison with Backend Abstraction

Both abstractions follow the same pattern:

| Aspect | Backend Abstraction | Load Generator Abstraction |
|--------|---------------------|----------------------------|
| **Purpose** | Inference engines | Benchmarking tools |
| **Implementations** | vLLM, TGI, SGLang, llama.cpp | GuideLLM, vLLM bench, MTEB |
| **CLI** | `python3 -m shared.backends` | `python3 -m shared.loadgens` |
| **Ansible Task** | `backend-command.yml` | `loadgen-command.yml` |
| **Config Class** | `BackendConfig` | `LoadGenConfig` |
| **Output Class** | N/A | `LoadGenMetrics` |
| **Workload Types** | generative, embedding | chat, rag, code, embedding, etc. |

## Benefits

1. **Unified Interface**: Switch between load generators without changing playbooks
2. **Standardized Metrics**: Common format for all load generator outputs
3. **Graceful Fallback**: Works with or without abstraction layer
4. **Extensible**: Easy to add new load generators
5. **Container-Ready**: Generates container images and environment variables
6. **Ansible-Native**: Integrates seamlessly with existing roles

## Migration Path

The load generator abstraction is **opt-in and backward compatible**:

1. Existing playbooks continue working unchanged
2. New playbooks can use the abstraction via `loadgen-command.yml`
3. Roles can provide both traditional and abstraction-based paths
4. See `benchmark_embedding/tasks/baseline-with-loadgen.yml` for example

## See Also

- [Backend Abstraction Usage Guide](BACKEND_USAGE_GUIDE.md)
- [Phase 1 & 2 Implementation Summary](../PHASE1_COMPLETE.md)
- Load generator source: `automation/test-execution/shared/loadgens/`
