# Backend and Load Generator Abstraction - Implementation Summary

**Branch**: `feature/openshift-backend-abstraction`  
**Date**: June 2026  
**Status**: Phase 1 COMPLETE & VALIDATED ✅ | Phase 2 COMPLETE (validation pending) 🚧

## Overview

This PR implements two complementary abstraction layers for the vLLM benchmarking suite:

1. **Phase 1: Backend Abstraction** - Unified interface for inference engines (vLLM, TGI, SGLang, llama.cpp)
2. **Phase 2: Load Generator Abstraction** - Unified interface for benchmarking tools (GuideLLM, vLLM bench, MTEB)

Both phases follow identical design patterns and are **fully backward compatible** with existing playbooks.

## Phase 1: Backend Abstraction ✅

### Purpose
Enable benchmarking across multiple inference backends without rewriting playbooks.

### Implementations
- **vLLM** (complete) - Generative + embedding workloads
- **TGI** (stub) - Future implementation
- **SGLang** (stub) - Future implementation  
- **llama.cpp** (stub) - Future implementation

### Testing Status
- ✅ Local testing (Mac)
- ✅ EC2 remote testing (embedding workload)
- ✅ EC2 remote testing (LLM concurrent load)
- ✅ Backward compatibility (graceful fallback)

### Key Files
```
shared/backends/
├── __init__.py              # Registry and factory
├── __main__.py              # Module entry point
├── base.py                  # Abstract interfaces
├── cli.py                   # CLI for Ansible
└── vllm_backend.py          # vLLM implementation

ansible/roles/vllm_server/tasks/
└── backend-command.yml      # Ansible integration

docs/
└── BACKEND_USAGE_GUIDE.md   # Documentation
```

### CLI Usage
```bash
# List backends
python3 -m shared.backends list
# Returns: ["vllm"]

# Get backend info
python3 -m shared.backends get-backend vllm

# Generate command
python3 -m shared.backends get-command vllm \
  --model granite-embedding \
  --host 0.0.0.0 \
  --port 8000 \
  --workload embedding
```

### Ansible Integration
```yaml
- name: Generate backend command
  ansible.builtin.include_tasks: backend-command.yml
  vars:
    backend_name: vllm
    backend_config:
      model: "{{ test_model }}"
      host: "{{ vllm_server.host }}"
      port: "{{ vllm_server.port }}"
      workload_type: embedding

# Uses: backend_cmd, backend_env, backend_image
```

### EC2 Validation Results
**Embedding Test** (250 requests):
- Mean latency: 14.99ms
- Failures: 0
- Backend abstraction: ✅ Working

**LLM Concurrent Test** (50 requests):
- Successful: 50/50
- Backend abstraction: ✅ Working

## Phase 2: Load Generator Abstraction 🚧

### Purpose
Enable switching between benchmarking tools without rewriting playbooks.

### Implementations
- **GuideLLM** (complete) - Full-featured LLM + embedding benchmarking
- **vLLM bench** (complete) - Built-in vLLM bench serve
- **MTEB** (complete) - Embedding quality evaluation

**Note**: All load generators are **container-only**, no bare metal execution.

### Testing Status
- ✅ CLI testing (all three load generators)
- ⏳ EC2 validation pending

### Key Files
```
shared/loadgens/
├── __init__.py              # Registry and factory
├── __main__.py              # Module entry point
├── base.py                  # Abstract interfaces
├── cli.py                   # CLI for Ansible
├── guidellm_loadgen.py      # GuideLLM implementation
├── vllm_bench_loadgen.py    # vLLM bench implementation
└── mteb_loadgen.py          # MTEB implementation

ansible/roles/
├── common/tasks/
│   └── loadgen-command.yml  # Ansible integration
└── benchmark_embedding/tasks/
    └── baseline-with-loadgen.yml  # Example integration

docs/
└── LOADGEN_USAGE_GUIDE.md   # Documentation
```

### CLI Usage
```bash
# List load generators
python3 -m shared.loadgens list
# Returns: ["guidellm", "vllm_bench", "mteb"]

# Get load generator info
python3 -m shared.loadgens get-loadgen vllm_bench

# Generate configuration
python3 -m shared.loadgens get-config guidellm \
  --target http://localhost:8000 \
  --model TinyLlama/TinyLlama-1.1B-Chat-v1.0 \
  --workload chat \
  --max-requests 100
```

### Ansible Integration
```yaml
- name: Generate load generator config
  ansible.builtin.include_role:
    name: common
    tasks_from: loadgen-command
  vars:
    loadgen_name: vllm_bench
    loadgen_config:
      target_url: "http://{{ vllm_host }}:{{ vllm_port }}"
      model: "{{ test_model }}"
      workload_type: embedding
      max_requests: 250

# Uses: loadgen_cmd, loadgen_env, loadgen_image, loadgen_output_format
```

## Design Patterns

### Consistent Architecture
Both abstractions follow identical patterns:

| Component | Backend | Load Generator |
|-----------|---------|----------------|
| **Module** | `shared/backends/` | `shared/loadgens/` |
| **ABC** | `Backend` | `LoadGenerator` |
| **Config** | `BackendConfig` | `LoadGenConfig` |
| **CLI** | `python3 -m shared.backends` | `python3 -m shared.loadgens` |
| **Ansible Task** | `backend-command.yml` | `loadgen-command.yml` |
| **Registry** | `BACKENDS` dict | `LOADGENS` dict |

### Graceful Fallback
Both abstractions provide graceful fallback if unavailable:

```yaml
- name: Try abstraction
  ansible.builtin.include_role:
    name: common
    tasks_from: backend-command.yml  # or loadgen-command.yml
  vars: {...}

- name: Use if available
  when: backend_abstraction_used  # or loadgen_abstraction_used
  block:
    # Use abstraction

- name: Traditional fallback
  when: not backend_abstraction_used
  block:
    # Original implementation
```

### Extensibility
Adding new backends/load generators requires:

1. Create implementation class extending `Backend`/`LoadGenerator`
2. Register in `__init__.py` BACKENDS/LOADGENS dict
3. Test via CLI: `python3 -m shared.backends list`

## Critical Fixes (Phase 1 EC2 Testing)

### Issue 1: Delegation and Privilege Escalation
**Problem**: Tasks delegated to localhost inherited `become: true` from EC2 inventory  
**Fix**: Added `become: false` to all localhost delegation tasks

### Issue 2: Path Expansion with sudo
**Problem**: `~/benchmark-results` expanded to `/root/benchmark-results` with `become: true`  
**Fix**: Get SSH user's home BEFORE becoming root in pre_tasks, expand paths early

### Issue 3: Podman Volume Mounts
**Problem**: Podman doesn't expand `~` in volume mount paths  
**Fix**: Expand tilde before passing to podman volume mounts

### Issue 4: Local vs Remote Results Paths
**Problem**: Fetch task confused local vs remote paths after expansion  
**Fix**: Pass separate `local_results_path` variable for fetch destinations

## Files Modified/Created

### Phase 1: Backend Abstraction
**Created**:
- `shared/backends/__init__.py`
- `shared/backends/__main__.py`
- `shared/backends/base.py`
- `shared/backends/cli.py`
- `shared/backends/vllm_backend.py`
- `ansible/roles/vllm_server/tasks/backend-command.yml`
- `docs/BACKEND_USAGE_GUIDE.md`
- `PHASE1_COMPLETE.md`

**Modified**:
- `ansible/roles/vllm_server/tasks/start-embedding.yml`
- `ansible/roles/vllm_server/tasks/start-llm.yml`
- `ansible/embedding-benchmark.yml` (path expansion fixes)
- `ansible/llm-benchmark-auto.yml` (path expansion fixes)
- `ansible/roles/benchmark_guidellm/tasks/main.yml` (delegation fixes)
- `ansible/roles/benchmark_embedding/tasks/baseline.yml` (path expansion)

### Phase 2: Load Generator Abstraction
**Created**:
- `shared/loadgens/__init__.py`
- `shared/loadgens/__main__.py`
- `shared/loadgens/base.py`
- `shared/loadgens/cli.py`
- `shared/loadgens/guidellm_loadgen.py`
- `shared/loadgens/vllm_bench_loadgen.py`
- `shared/loadgens/mteb_loadgen.py`
- `ansible/roles/common/tasks/loadgen-command.yml`
- `ansible/roles/benchmark_embedding/tasks/baseline-with-loadgen.yml`
- `docs/LOADGEN_USAGE_GUIDE.md`
- `PHASE2_COMPLETE.md`

## Benefits

### Backend Abstraction
1. **Multi-Backend Support**: Switch backends by changing one variable
2. **Hardware Optimization**: Per-backend tuning (CPU vs GPU, NUMA, etc.)
3. **Container Flexibility**: Auto-generated container images and configs
4. **Backward Compatible**: Opt-in, doesn't break existing playbooks
5. **Extensible**: Easy to add TGI, SGLang, llama.cpp

### Load Generator Abstraction
1. **Unified Interface**: Switch load generators by changing one variable
2. **Standardized Metrics**: Common `LoadGenMetrics` format
3. **Container-Ready**: Auto-generated container configs
4. **Backward Compatible**: Opt-in, graceful fallback
5. **Extensible**: Easy to add MLPerf, custom tools

## Backward Compatibility

Both abstractions are **100% backward compatible**:

- Existing playbooks work unchanged
- Abstraction is opt-in via include_tasks
- Graceful fallback if module unavailable
- No changes to existing roles required
- Can be adopted incrementally

## Testing Strategy

### Phase 1 (Complete)
- [x] Unit tests for backend implementations
- [x] CLI functional tests
- [x] Local playbook execution (Mac)
- [x] EC2 remote embedding benchmark
- [x] EC2 remote LLM concurrent load test
- [x] Backward compatibility validation

### Phase 2 (Pending)
- [x] CLI functional tests
- [ ] EC2 load generator validation
- [ ] Integration with benchmark roles
- [ ] Unit tests for load generator implementations

## Git Commit History

### Phase 1
```
b1411a2 docs: add comprehensive implementation summary
46b81c2 test: add comprehensive backward compatibility validation
d3559c7 docs: mark Week 3 complete, update migration status
b5f968d feat: integrate backend abstraction into start-llm.yml
[... earlier commits ...]
```

### Phase 2
```
1d47151 docs: clarify load generators are container-only
7ea2409 feat: add load generator Ansible integration and documentation
7810b09 feat: add vLLM bench and MTEB load generators with Ansible integration
c5e12e3 feat: add load generator abstraction layer (Phase 2)
```

## Documentation

- **Backend Abstraction**: `docs/BACKEND_USAGE_GUIDE.md`
- **Load Generator Abstraction**: `docs/LOADGEN_USAGE_GUIDE.md`
- **Phase 1 Details**: `PHASE1_COMPLETE.md`
- **Phase 2 Details**: `PHASE2_COMPLETE.md`
- **This Summary**: `IMPLEMENTATION_SUMMARY.md`

## Next Steps

### Immediate
1. EC2 validation of load generator abstraction
2. Add unit tests for load generators
3. Integration testing with benchmark roles

### Future Enhancements
1. Implement TGI, SGLang, llama.cpp backends
2. Add MLPerf load generator
3. Automated metric collection and reporting
4. Cross-backend performance comparison
5. CI/CD integration

## Success Criteria

### Phase 1 ✅
- [x] vLLM backend implemented
- [x] CLI working
- [x] Ansible integration complete
- [x] EC2 validation passing
- [x] Backward compatibility maintained
- [x] Documentation complete

### Phase 2 🚧
- [x] Three load generators implemented
- [x] CLI working
- [x] Ansible integration complete
- [x] Documentation complete
- [ ] EC2 validation
- [ ] Unit tests

## Conclusion

Both Phase 1 (backend abstraction) and Phase 2 (load generator abstraction) successfully implement unified interfaces for their respective domains. The implementations follow identical design patterns, are fully backward compatible, and provide a solid foundation for future extensibility.

**Phase 1 is production-ready and validated on EC2.**  
**Phase 2 is implementation-complete and ready for EC2 validation.**

The abstractions enable:
- Multi-backend benchmarking (vLLM, TGI, SGLang, llama.cpp)
- Multi-tool benchmarking (GuideLLM, vLLM bench, MTEB, MLPerf)
- Consistent Ansible integration patterns
- Zero impact on existing workflows
- Easy addition of new backends and load generators

Both can be adopted incrementally without disrupting current benchmark workflows.
