# Phase 2: Load Generator Abstraction - COMPLETE ✅

**Status**: Implementation complete, tested via CLI, ready for EC2 validation  
**Date**: June 2026  
**Branch**: `feature/openshift-backend-abstraction`

## Summary

Phase 2 adds a unified abstraction layer for load generator tools (GuideLLM, vLLM bench, MTEB), following the exact same pattern as Phase 1's backend abstraction. This enables:

- **Unified Interface**: Switch between load generators without changing playbooks
- **Standardized Metrics**: Common format for all load generator outputs
- **Extensibility**: Easy to add new load generators (MLPerf, custom tools)
- **Ansible Integration**: Seamless integration via `loadgen-command.yml` task
- **Backward Compatibility**: Opt-in, graceful fallback to traditional approaches

## Implementation

### Directory Structure
```
automation/test-execution/
├── shared/loadgens/              # Load generator abstraction module
│   ├── __init__.py              # Registry and factory functions
│   ├── __main__.py              # Module entry point
│   ├── base.py                  # Abstract interfaces
│   ├── cli.py                   # CLI for Ansible integration
│   ├── guidellm_loadgen.py      # GuideLLM implementation
│   ├── vllm_bench_loadgen.py    # vLLM bench implementation
│   └── mteb_loadgen.py          # MTEB implementation
├── ansible/roles/
│   ├── common/tasks/
│   │   └── loadgen-command.yml  # Ansible integration task
│   └── benchmark_embedding/tasks/
│       └── baseline-with-loadgen.yml  # Example integration
└── docs/
    └── LOADGEN_USAGE_GUIDE.md   # Comprehensive documentation
```

### Load Generators Implemented

#### 1. GuideLLM
- **Version**: 0.6.0
- **Container**: `ghcr.io/vllm-project/guidellm:v0.6.0`
- **Workloads**: chat, rag, code, summarization, reasoning, embedding
- **Profiles**: sweep, synchronous, concurrent, throughput, constant, poisson
- **Output**: JSON, HTML, CSV with full benchmark reports

#### 2. vLLM bench
- **Version**: 0.20.0
- **Container**: `vllm/vllm-openai-cpu:v0.20.0`
- **Workloads**: All generative + embedding
- **Features**: Backend switching (openai vs openai-embeddings), request rate control
- **Output**: JSON with throughput, latency, TTFT, TPOT metrics

#### 3. MTEB
- **Version**: 1.0
- **Container**: `quay.io/vllm-cpu-perf-eval/vllm-mteb:latest`
- **Workloads**: embedding only
- **Features**: Task presets (quick/standard/comprehensive), custom task lists
- **Output**: JSON with quality metrics (accuracy, retrieval scores)

### Core Components

#### Base Classes (`base.py`)
```python
@dataclass
class LoadGenConfig:
    """Standardized configuration for all load generators"""
    target_url: str
    model: str
    workload_type: str = "chat"
    max_requests: int = 1000
    max_seconds: int = 600
    rate: Optional[str] = None
    output_path: str = "/results"
    dataset: Optional[str] = None
    extra_args: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LoadGenMetrics:
    """Standardized metrics from all load generators"""
    requests_total: int = 0
    requests_successful: int = 0
    requests_failed: int = 0
    throughput_rps: float = 0.0
    throughput_tps: float = 0.0
    latency_mean_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    ttft_mean_ms: float = 0.0
    tpot_mean_ms: float = 0.0
    duration_seconds: float = 0.0
    raw_metrics: Dict = {}

class LoadGenerator(ABC):
    """Abstract interface for load generators"""
    @abstractmethod
    def get_command(self, config: LoadGenConfig) -> List[str]: pass
    @abstractmethod
    def get_container_image(self) -> str: pass
    @abstractmethod
    def get_env_vars(self, config: LoadGenConfig) -> Dict[str, str]: pass
    @abstractmethod
    def parse_results(self, results_path: str) -> LoadGenMetrics: pass
    @abstractmethod
    def validate_config(self, config: LoadGenConfig) -> None: pass
    @abstractmethod
    def supports_workload(self, workload_type: str) -> bool: pass
```

#### CLI Interface (`cli.py`)
```bash
# List available load generators
python3 -m shared.loadgens list
# Returns: ["guidellm", "vllm_bench", "mteb"]

# Get load generator info
python3 -m shared.loadgens get-loadgen guidellm

# Generate configuration
python3 -m shared.loadgens get-config guidellm \
  --target http://localhost:8000 \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --workload chat \
  --max-requests 100

# Parse results
python3 -m shared.loadgens parse-results guidellm /results/output.json
```

#### Ansible Integration (`loadgen-command.yml`)
```yaml
- name: Generate load generator configuration
  ansible.builtin.include_role:
    name: common
    tasks_from: loadgen-command
  vars:
    loadgen_name: "vllm_bench"
    loadgen_config:
      target_url: "http://{{ vllm_host }}:{{ vllm_port }}"
      model: "{{ test_model }}"
      workload_type: "embedding"
      max_requests: 250
      rate: "inf"
      output_path: "/results/baseline.json"

# Output variables:
# - loadgen_abstraction_used: true/false
# - loadgen_cmd: command as list
# - loadgen_env: environment variables
# - loadgen_image: container image
# - loadgen_output_format: output format
```

## Testing

### CLI Tests (All Passing ✅)

```bash
$ python3 -m shared.loadgens list
["guidellm", "vllm_bench", "mteb"]

$ python3 -m shared.loadgens get-loadgen vllm_bench
{
  "name": "vllm_bench",
  "version": "0.20.0",
  "image": "vllm/vllm-openai-cpu:v0.20.0",
  "output_format": "json",
  "supported_workloads": {
    "chat": true,
    "rag": true,
    "code": true,
    "summarization": true,
    "embedding": true
  }
}

$ python3 -m shared.loadgens get-loadgen mteb
{
  "name": "mteb",
  "version": "1.0",
  "image": "quay.io/vllm-cpu-perf-eval/vllm-mteb:latest",
  "output_format": "json",
  "supported_workloads": {
    "chat": false,
    "rag": false,
    "code": false,
    "summarization": false,
    "embedding": true
  }
}
```

### EC2 Testing
Status: **Pending** - requires actual deployment testing

## Design Patterns

### Same as Backend Abstraction
Both Phase 1 (backends) and Phase 2 (load generators) follow identical patterns:

| Pattern | Backend | Load Generator |
|---------|---------|----------------|
| **Module Structure** | `shared/backends/` | `shared/loadgens/` |
| **ABC Pattern** | `Backend` abstract class | `LoadGenerator` abstract class |
| **Config Class** | `BackendConfig` | `LoadGenConfig` |
| **Output Class** | N/A | `LoadGenMetrics` |
| **CLI** | `python3 -m shared.backends` | `python3 -m shared.loadgens` |
| **Ansible Task** | `backend-command.yml` | `loadgen-command.yml` |
| **Registry** | `BACKENDS` dict | `LOADGENS` dict |
| **Factory** | `get_backend()` | `get_loadgen()` |

### Graceful Fallback
```yaml
# Try abstraction first
- name: Try load generator abstraction
  ansible.builtin.include_role:
    name: common
    tasks_from: loadgen-command
  vars:
    loadgen_name: "vllm_bench"
    loadgen_config: {...}

# Use if available
- name: Use abstraction
  when: loadgen_abstraction_used
  block:
    - name: Run with generated config
      # Use loadgen_cmd, loadgen_env, loadgen_image

# Fallback if unavailable
- name: Traditional approach
  when: not loadgen_abstraction_used
  block:
    - name: Run traditional commands
      # Original implementation
```

## Benefits

1. **Unified Interface**: Switch load generators by changing one variable
2. **Standardized Metrics**: Common `LoadGenMetrics` format for all outputs
3. **Container-Ready**: Automatic image and environment variable generation
4. **Extensible**: Add new load generators by implementing `LoadGenerator` ABC
5. **Ansible-Native**: Integrates seamlessly with existing roles
6. **Backward Compatible**: Opt-in, doesn't break existing playbooks
7. **Consistent with Phase 1**: Same patterns as backend abstraction

## Future Enhancements

### Additional Load Generators
- **MLPerf**: Standard ML benchmarking suite
- **Custom Load Generators**: Organization-specific tools
- **Cloud Provider Tools**: AWS, Azure, GCP benchmark utilities

### Enhancements
- Automatic result parsing and metric collection
- Cross-load-generator metric comparison
- Benchmark report generation
- Integration with CI/CD pipelines

## Comparison: Phase 1 vs Phase 2

| Aspect | Phase 1: Backends | Phase 2: Load Generators |
|--------|-------------------|--------------------------|
| **Purpose** | Inference engines | Benchmarking tools |
| **Implementations** | vLLM, TGI, SGLang, llama.cpp | GuideLLM, vLLM bench, MTEB |
| **Config** | Model, host, port, hardware | Target, model, workload, limits |
| **Output** | Command, env vars, image | Command, env vars, image, metrics |
| **Tested** | EC2 (embedding + LLM) ✅ | CLI only (EC2 pending) |
| **Status** | COMPLETE & VALIDATED | COMPLETE (validation pending) |

## Documentation

- **Usage Guide**: `docs/LOADGEN_USAGE_GUIDE.md`
  - CLI usage examples
  - Ansible integration patterns
  - Load generator-specific configuration
  - Adding new load generators
  - Migration guide

- **Example Integration**: `ansible/roles/benchmark_embedding/tasks/baseline-with-loadgen.yml`
  - Demonstrates abstraction usage
  - Shows graceful fallback pattern
  - Side-by-side comparison with traditional approach

## Git Commits

```
c5e12e3 feat: add load generator abstraction layer (Phase 2)
7810b09 feat: add vLLM bench and MTEB load generators with Ansible integration
7ea2409 feat: add load generator Ansible integration and documentation
```

## Next Steps

1. **Add Tests**: Create `test_loadgens.py` similar to `test_backends_integration.py`
2. **EC2 Validation**: Test on remote deployment with actual workloads
3. **Integration**: Optionally integrate into more benchmark roles
4. **MLPerf**: Add MLPerf load generator if needed
5. **Metrics Collection**: Automated metric parsing and reporting

## Success Criteria

- [x] Three load generators implemented (GuideLLM, vLLM bench, MTEB)
- [x] Abstract base classes defined
- [x] CLI interface working
- [x] Ansible integration task created
- [x] Documentation complete
- [x] Example integration provided
- [ ] Unit tests added
- [ ] EC2 validation complete

## Conclusion

Phase 2 successfully implements the load generator abstraction layer, mirroring the design patterns from Phase 1. The implementation provides a unified interface for multiple benchmarking tools while maintaining full backward compatibility with existing playbooks.

The abstraction is **opt-in** and **ready for use**, with comprehensive documentation and examples. It can be adopted incrementally across benchmark roles as needed.

**Both Phase 1 (backends) and Phase 2 (load generators) are now complete and ready for testing/validation on EC2.**
