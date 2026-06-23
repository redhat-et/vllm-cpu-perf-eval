# Backend Abstraction Layer

This directory implements a pluggable backend system that allows the benchmarking framework to work with multiple inference engines while maintaining a consistent interface.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Benchmark Orchestration Layer                  │
│  (Ansible playbooks, Python scripts - backend-agnostic)     │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │   Backend Interface   │
         │   (Abstract Class)    │
         └───────────┬───────────┘
                     │
      ┌──────────────┼──────────────┬──────────────┐
      │              │              │              │
┌─────▼─────┐  ┌────▼────┐  ┌──────▼──────┐  ┌───▼────┐
│   vLLM    │  │  TGI    │  │ llama.cpp   │  │ Custom │
│  Backend  │  │ Backend │  │   Backend   │  │Backend │
└───────────┘  └─────────┘  └─────────────┘  └────────┘
```

## Current Backends

### vLLM
- **Status**: Implemented (skeleton)
- **Container**: `vllm/vllm-openai-cpu:v0.20.0`
- **API**: OpenAI-compatible
- **Features**: Prefix caching, tensor parallelism, quantization

### TGI (Planned)
- **Status**: Not started
- **Container**: `ghcr.io/huggingface/text-generation-inference`
- **API**: Custom HuggingFace API

### llama.cpp (Planned)
- **Status**: Not started
- **Container**: TBD
- **API**: Custom API

## Adding a New Backend

### Step 1: Implement the Interface

Create a new file `<backend>_backend.py`:

```python
from .base import InferenceBackend, BackendConfig, BackendMetrics

class MyBackend(InferenceBackend):
    @property
    def name(self) -> str:
        return "mybackend"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def get_start_command(self, config: BackendConfig) -> List[str]:
        # Return CLI arguments for container start
        pass
    
    def get_container_image(self) -> str:
        # Return container image URL
        return "myorg/mybackend:v1.0.0"
    
    def parse_metrics(self, metrics_data: Dict) -> BackendMetrics:
        # Parse backend-specific metrics to standard format
        pass
    
    def health_check_endpoint(self) -> str:
        return "/health"
    
    def models_endpoint(self) -> str:
        return "/v1/models"
```

### Step 2: Register the Backend

Add to `__init__.py`:

```python
from .mybackend_backend import MyBackend

BACKENDS = {
    "vllm": vLLMBackend,
    "mybackend": MyBackend,  # Add here
}
```

### Step 3: Use the Backend

```python
from shared.backends import get_backend

backend = get_backend("mybackend")
config = BackendConfig(model="meta-llama/Llama-3.2-1B")
cmd = backend.get_start_command(config)
```

## Standard Metrics

All backends must provide these core metrics:

| Metric | Unit | Description |
|--------|------|-------------|
| `ttft_mean` | ms | Time to First Token (mean) |
| `tpot_mean` | ms | Time Per Output Token (mean) |
| `e2e_mean` | ms | End-to-End latency (mean) |
| `requests_per_second` | req/s | Request throughput |
| `tokens_per_second` | tok/s | Token throughput |
| `memory_mb` | MB | Memory usage |
| `cpu_percent` | % | CPU utilization |

Optional metrics (backend-specific):
- `kv_cache_usage` - KV cache utilization (vLLM)
- `prefix_cache_hit_rate` - Prefix cache hit rate (vLLM)

## Files

- **`base.py`** - Abstract base class and data structures
- **`vllm_backend.py`** - vLLM implementation
- **`__init__.py`** - Backend registry and factory functions
- **`README.md`** - This file

## Migration Status

### Phase 1: Foundation (Weeks 1-6)

- [x] Week 1: Create backend structure
  - [x] Abstract base class
  - [x] vLLM skeleton implementation
  - [x] Backend registry
- [x] Week 2: Complete vLLM backend
  - [x] Migrate metrics parsing from `log_to_mlflow.py`
  - [x] Implement `parse_metrics()` fully
  - [x] Add unit tests (26 tests passing)
- [x] Week 3: Ansible integration ✅ COMPLETE
  - [x] Create `backend-command.yml` task for role integration
  - [x] Add CLI path handling with `chdir` support
  - [x] Test backend abstraction with test playbook
  - [x] Verify fallback to hardcoded command works
  - [x] Create `convert-args-to-dict.yml` helper task
  - [x] Integrate into `vllm_server` role `start-llm.yml`
  - [x] Add rescue blocks for graceful fallback
- [ ] Week 4: Complete role refactoring (in progress)
  - [ ] Update `start-embedding.yml` to use backend abstraction
  - [ ] Make roles backend-agnostic
  - [ ] Backward compatibility testing with bash scripts
- [ ] Week 5-6: Second backend (TGI)
  - [ ] Implement `TGIBackend`
  - [ ] Test with TGI containers
  - [ ] Integration tests

### Phase 2: OpenShift Support (Weeks 7-11)

See `OPENSHIFT_BACKEND_ANALYSIS.md` for complete roadmap.

## Design Decisions

### Why Abstract Class over Duck Typing?

Python's `abc.ABC` enforces the interface contract at import time, catching missing methods early rather than at runtime.

### Why Dataclasses?

`BackendConfig` and `BackendMetrics` use `@dataclass` for:
- Automatic `__init__`, `__repr__`, `__eq__`
- Type hints
- Immutability (when frozen)
- Clear, self-documenting structure

### Metrics Parsing Strategy

Each backend implements its own `parse_metrics()` because:
- Metric names differ (vLLM: `vllm:ttft_ms`, TGI: `tgi_request_duration`)
- Metric formats differ (histogram vs gauge)
- Some backends may not expose all metrics

The abstraction standardizes the OUTPUT, not the parsing logic.

## Testing

### Unit Tests (TODO)

```bash
pytest automation/test-execution/shared/backends/
```

### Integration Tests (TODO)

Test with real containers:

```bash
# vLLM backend
pytest automation/test-execution/ansible/tests/integration/test_vllm_backend.py

# TGI backend
pytest automation/test-execution/ansible/tests/integration/test_tgi_backend.py
```

## Related Documentation

- `OPENSHIFT_BACKEND_ANALYSIS.md` - Full architecture and roadmap
- `automation/test-execution/ansible/README.md` - Ansible integration
- `docs/environment-variables.md` - Configuration reference
