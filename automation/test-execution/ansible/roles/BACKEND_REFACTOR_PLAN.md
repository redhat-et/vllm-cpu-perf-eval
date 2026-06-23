# Backend Abstraction Refactor Plan

## Goal
Refactor Ansible roles to use the backend abstraction layer while maintaining 100% backward compatibility with existing bash script workflows.

## Critical Constraints

1. **DO NOT BREAK** existing bash scripts (run-rhaiis-concurrent-load.sh)
2. Environment variables must continue working: VLLM_CPU_START, VLLM_NUMA_NODE, GUIDELLM_CPUS, GUIDELLM_NUMA_NODE
3. All existing inventory files and group_vars must work unchanged
4. No behavioral changes to current vLLM workflows

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Existing Playbooks (llm-benchmark.yml, embedding-*.yml)   │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴──────────────┐
         │   inference_server role   │  ← New unified entry point
         │  (backend-agnostic)       │
         └───────────┬──────────────┘
                     │
                     │ backend = {{ backend_name | default('vllm') }}
                     │
      ┌──────────────┼──────────────┬──────────────┐
      │              │              │              │
┌─────▼─────┐  ┌────▼────┐  ┌──────▼──────┐  ┌───▼────┐
│   vllm    │  │  tgi    │  │ llama.cpp   │  │ custom │
│  _server  │  │ _server │  │   _server   │  │_server │
└───────────┘  └─────────┘  └─────────────┘  └────────┘
     │
     │ Uses backend abstraction CLI:
     │ python3 -m shared.backends get-command vllm --model ... --extra-args '{...}'
     │
     ▼
┌────────────────────────────────────────┐
│  shared.backends.vllm_backend.py       │
│  - get_start_command()                 │
│  - get_container_image()               │
│  - parse_metrics()                     │
└────────────────────────────────────────┘
```

## Refactoring Strategy

### Phase 1: Add Backend Selection Layer (Week 3)

1. **Create `inference_server` role** (new unified entry point)
   - Reads `backend_name` variable (default: `vllm`)
   - Delegates to backend-specific role: `{{ backend_name }}_server`
   - Preserves all existing variables unchanged

2. **Extract vLLM command generation to backend abstraction**
   - Create task: `tasks/build-backend-command.yml`
   - Calls: `python3 -m shared.backends get-command vllm ...`
   - Populates `backend_cmd` and `backend_env` facts
   - Falls back to current hardcoded logic if backend CLI not available

3. **Backward Compatibility Testing**
   - Run existing bash scripts unchanged
   - Verify NUMA environment variables work
   - Confirm metrics collection unchanged

### Phase 2: Refactor vllm_server Role (Week 4)

#### Current Structure
```
vllm_server/
├── tasks/
│   ├── main.yml                 # Entry point
│   ├── start-llm.yml            # LLM-specific start
│   ├── start-embedding.yml      # Embedding-specific start
│   ├── clean-restart.yml
│   └── download-model.yml
└── defaults/
    └── main.yml
```

#### Refactored Structure
```
vllm_server/
├── tasks/
│   ├── main.yml                 # Entry point (minimal changes)
│   ├── backend-command.yml      # NEW: Uses backend abstraction
│   ├── start-llm.yml            # MODIFIED: Uses backend_cmd from abstraction
│   ├── start-embedding.yml      # MODIFIED: Uses backend_cmd from abstraction
│   ├── clean-restart.yml        # UNCHANGED
│   └── download-model.yml       # UNCHANGED
└── defaults/
    └── main.yml                 # UNCHANGED
```

#### Key Changes in `start-llm.yml`

**Before (Hardcoded):**
```yaml
- name: Build vLLM command arguments
  ansible.builtin.set_fact:
    vllm_cmd: >-
      --model {{ test_model }}
      --host {{ vllm_server.host }}
      --port {{ vllm_server.port }}
      {{ vllm_args_merged | join(' ') }}
      {% if core_cfg.tensor_parallel | int > 1 %}-tp {{ core_cfg.tensor_parallel }}{% endif %}
```

**After (Backend Abstraction):**
```yaml
- name: Include backend command generation
  ansible.builtin.include_tasks: backend-command.yml
  vars:
    backend_config:
      model: "{{ test_model }}"
      host: "{{ vllm_server.host }}"
      port: "{{ vllm_server.port }}"
      dtype: "{{ model_dtype | default('bfloat16') }}"
      tensor_parallel: "{{ core_cfg.tensor_parallel | default(1) }}"
      extra_args: "{{ vllm_extra_args_dict }}"  # Convert from list to dict

- name: Start inference server
  containers.podman.podman_container:
    name: "{{ vllm_container_name }}"
    image: "{{ backend_image }}"  # From backend abstraction
    command: "{{ backend_cmd }}"  # From backend abstraction
    env: "{{ backend_env | combine(vllm_env_vars) }}"  # Merge backend + custom env
    # ... rest unchanged
```

#### New Task: `backend-command.yml`

```yaml
---
# Generate backend command using abstraction layer
# Inputs:
#   - backend_name (default: vllm)
#   - backend_config (dict with model, host, port, etc.)
# Outputs:
#   - backend_cmd (list of command args)
#   - backend_env (dict of environment variables)
#   - backend_image (container image URL)

- name: Check if backend abstraction is available
  ansible.builtin.stat:
    path: "{{ playbook_dir }}/../shared/backends/__init__.py"
  register: backend_module
  delegate_to: localhost

- name: Generate command using backend abstraction
  ansible.builtin.command:
    cmd: >-
      python3 -m shared.backends get-command {{ backend_name | default('vllm') }}
      --model "{{ backend_config.model }}"
      --host "{{ backend_config.host }}"
      --port {{ backend_config.port }}
      --dtype "{{ backend_config.dtype }}"
      --max-tokens {{ backend_config.max_tokens | default(512) }}
      --tensor-parallel {{ backend_config.tensor_parallel | default(1) }}
      --extra-args '{{ backend_config.extra_args | to_json }}'
  register: backend_result
  delegate_to: localhost
  when: backend_module.stat.exists

- name: Parse backend command result
  ansible.builtin.set_fact:
    backend_data: "{{ backend_result.stdout | from_json }}"
  when: backend_module.stat.exists

- name: Set backend facts
  ansible.builtin.set_fact:
    backend_cmd: "{{ backend_data.command | join(' ') }}"
    backend_env: "{{ backend_data.env }}"
    backend_image: "{{ backend_data.image }}"
  when: backend_module.stat.exists

# Fallback to hardcoded vLLM command if backend abstraction unavailable
- name: Fallback to hardcoded vLLM command
  ansible.builtin.set_fact:
    backend_cmd: >-
      --model {{ backend_config.model }}
      --host {{ backend_config.host }}
      --port {{ backend_config.port }}
      --dtype {{ backend_config.dtype }}
      --max-model-len {{ backend_config.max_tokens }}
      {% if backend_config.tensor_parallel | int > 1 %}
      -tp {{ backend_config.tensor_parallel }}
      {% endif %}
    backend_env: {}
    backend_image: "{{ container_runtime.image }}"
  when: not backend_module.stat.exists
```

## Migration Checklist

### Week 3 Tasks ✅ COMPLETE
- [x] Create `backend-command.yml` task
- [x] Add CLI path handling with `chdir` support  
- [x] Create test playbook (test-backend-command.yml)
- [x] Verify fallback mechanism works
- [x] Create `convert-args-to-dict.yml` helper
- [x] Integrate into `start-llm.yml` with rescue blocks
- [x] Update container image handling to use `effective_container_image`
- [x] Add backend status to debug output

### Week 4 Tasks (In Progress)
- [ ] Test with bash scripts (NUMA env vars work)
- [ ] Refactor `start-embedding.yml` to use backend abstraction
- [ ] Test all workload types (chat, code, summarization, rag, embedding)
- [ ] Test all core counts (8, 16, 32)
- [ ] Test tensor parallelism (1, 2, 4)
- [ ] Verify metrics collection unchanged
- [ ] Document new `backend_name` variable

### Backward Compatibility Tests
- [ ] `./run-rhaiis-concurrent-load.sh --models tiny --cores 8 --workloads chat`
- [ ] NUMA environment variables: `VLLM_CPU_START=24 VLLM_NUMA_NODE=1 GUIDELLM_CPUS=0-23 GUIDELLM_NUMA_NODE=0 ansible-playbook ...`
- [ ] Custom container image: `VLLM_CONTAINER_IMAGE=... ansible-playbook ...`
- [ ] Embedding tests: `ansible-playbook embedding-benchmark.yml`

## Benefits

1. **Pluggable Backends**: Easy to add TGI, llama.cpp, etc.
2. **Centralized Command Logic**: vLLM command generation in one place (Python)
3. **Testable**: Backend CLI has unit tests
4. **Gradual Migration**: Old playbooks work unchanged until explicitly updated
5. **No Breaking Changes**: All environment variables, inventory files work as-is

## Risks

1. **Complexity**: Two layers (Ansible + Python) for command generation
2. **Debugging**: Harder to trace command generation
3. **Dependencies**: Requires Python backend module installed

## Mitigation

- Fallback to hardcoded command if backend module unavailable
- Clear error messages when backend abstraction fails
- Document both approaches (backend abstraction vs hardcoded)
