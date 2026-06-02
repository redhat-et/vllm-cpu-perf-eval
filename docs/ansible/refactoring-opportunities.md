# Refactoring Opportunities: Common Patterns Across Playbooks

## Overview

Analysis of common patterns between `embedding-benchmark.yml` and LLM playbooks (`llm-benchmark-auto.yml`, `llm-core-sweep-auto.yml`, `llm-benchmark-concurrent-load.yml`) to identify refactoring opportunities.

## 1. ✅ **Health Check** - Already Refactored!

**Status**: Health check logic already exists in [health-check.yml](../../automation/test-execution/ansible/health-check.yml)

**Current Duplication**:
- `embedding-benchmark.yml` duplicates health check logic in Phase 2a and 2b
- LLM playbooks likely also duplicate or should be using this

**Refactor Action**:
```yaml
# Instead of duplicating health check in embedding-benchmark.yml
# Replace Phase 2a and 2b with:

- ansible.builtin.import_playbook: health-check.yml
```

**Benefits**:
- Single source of truth for health checks
- Automatic vLLM version detection
- Backend detection
- Consistent error handling
- ~50 lines removed from embedding-benchmark.yml

## 2. 🔄 **Mode Detection and Terminology**

**Issue**: Inconsistent terminology between playbooks

| Playbook | Variable Name | Values | Source |
|----------|---------------|--------|---------|
| LLM playbooks | `vllm_mode` | `managed`, `external` | `vllm_endpoint.mode` |
| Embedding playbook | `execution_mode` | `managed`, `dut-only`, `external` | `EXECUTION_MODE` env or `vllm_endpoint.mode` |

**Problems**:
1. Different variable names (`vllm_mode` vs `execution_mode`)
2. Embedding has extra mode (`dut-only`) not in LLM
3. Embedding reads from env variable, LLM doesn't

**Recommended Approach**:

### Option A: Unify to `vllm_mode` (Preferred)
```yaml
# Standard across all playbooks
vllm_mode: "{{ lookup('env', 'VLLM_MODE') | default(vllm_endpoint.mode | default('managed'), true) }}"

# Values:
# - managed: vLLM on DUT, tests from load_generator
# - dut-only: Both vLLM and tests on DUT (new, embedding-specific initially)
# - external: Tests against existing vLLM endpoint
```

**Benefits**:
- Consistent with existing LLM playbooks
- Single variable to check everywhere
- Easy to extend `dut-only` to LLM playbooks later

### Option B: Keep Separate (Not Recommended)
- Different semantics: `vllm_mode` = where is vLLM, `execution_mode` = where do tests run
- More confusing for users
- Harder to maintain

## 3. 🔄 **External Endpoint Configuration**

**Current Implementation Comparison**:

### LLM Playbooks (Better):
```yaml
- name: Parse external endpoint URL
  ansible.builtin.set_fact:
    external_endpoint_parsed: "{{ vllm_endpoint.external.url | urlsplit }}"

- name: Override bench_config for external endpoint
  ansible.builtin.set_fact:
    bench_config: "{{ bench_config | combine({
      'vllm_host': external_endpoint_parsed.hostname,
      'vllm_port': external_endpoint_parsed.port | default(8000) | int
    }) }}"
```

### Embedding Playbook (Regex-based):
```yaml
- name: Parse external endpoint URL
  ansible.builtin.set_fact:
    external_host: "{{ vllm_endpoint.external.url | regex_replace('^https?://', '') | regex_replace(':[0-9]+$', '') }}"
    external_port: "{{ vllm_endpoint.external.url | regex_search(':([0-9]+)', '\\1') | first | default('8000', true) }}"

- name: Override bench_config for external mode
  ansible.builtin.set_fact:
    bench_config: "{{ bench_config | combine({'vllm_host': external_host, 'vllm_port': external_port | int}) }}"
```

**Refactor Action**:
Create `roles/common/tasks/configure-external-endpoint.yml`:

```yaml
---
# Configure bench_config for external vLLM endpoint
# Requires: vllm_endpoint.external.url

- name: Validate external endpoint URL
  ansible.builtin.assert:
    that:
      - vllm_endpoint.external.url is defined
      - vllm_endpoint.external.url is not none
      - vllm_endpoint.external.url | length > 0
    fail_msg: "External endpoint URL is required when mode=external"

- name: Parse external endpoint URL
  ansible.builtin.set_fact:
    external_endpoint_parsed: "{{ vllm_endpoint.external.url | urlsplit }}"

- name: Override bench_config for external endpoint
  ansible.builtin.set_fact:
    bench_config: "{{ bench_config | combine({
      'vllm_host': external_endpoint_parsed.hostname,
      'vllm_port': external_endpoint_parsed.port | default(8000) | int
    }) }}"

- name: Setup API key if enabled
  ansible.builtin.include_role:
    name: common
    tasks_from: setup-vllm-api-key
  when: vllm_endpoint.external.api_key.enabled | default(false) | bool
```

**Usage**:
```yaml
pre_tasks:
  - name: Configure external endpoint
    ansible.builtin.include_role:
      name: common
      tasks_from: configure-external-endpoint
    when: vllm_mode == 'external'
```

**Benefits**:
- Use Ansible's `urlsplit` filter (cleaner than regex)
- Handles HTTPS URLs properly
- API key support included
- Single source of truth

## 4. 🔄 **Mode-based Play Execution Pattern**

**Current Issue**: Both playbooks duplicate plays for different modes

### Current Pattern (Duplicative):
```yaml
# Phase 3a - DUT-only mode
- name: "Phase 3a - Run Tests (DUT-only)"
  hosts: dut
  pre_tasks:
    - ansible.builtin.set_fact:
        is_dut_only: "{{ vllm_mode == 'dut-only' }}"
    - ansible.builtin.meta: end_play
      when: not is_dut_only
  roles:
    - role: benchmark_embedding

# Phase 3b - Managed/External modes  
- name: "Phase 3b - Run Tests (Managed/External)"
  hosts: load_generator
  pre_tasks:
    - ansible.builtin.set_fact:
        is_managed_or_external: "{{ vllm_mode in ['managed', 'external'] }}"
    - ansible.builtin.meta: end_play
      when: not is_managed_or_external
  roles:
    - role: benchmark_embedding
```

### Better Pattern (Shared Task):
Create `roles/common/tasks/set-test-host.yml`:

```yaml
---
# Determine which host group to run tests on based on vllm_mode
# Sets: test_host_group variable

- name: Determine test execution host
  ansible.builtin.set_fact:
    test_host_group: >-
      {%- if vllm_mode == 'dut-only' -%}
        dut
      {%- else -%}
        load_generator
      {%- endif -%}
  delegate_to: localhost
  delegate_facts: true
  run_once: true
```

**Then use with `add_host` pattern** (more advanced):
```yaml
- name: Configure test execution
  hosts: localhost
  tasks:
    - ansible.builtin.include_role:
        name: common
        tasks_from: set-test-host
    
    - name: Create dynamic test group
      ansible.builtin.add_host:
        name: "{{ hostvars[groups[test_host_group][0]]['ansible_host'] }}"
        groups: test_executor

- name: Run tests
  hosts: test_executor
  roles:
    - role: benchmark_embedding
```

**Benefits**:
- Single play instead of multiple mode-specific plays
- Easier to add new modes
- Less code duplication

## 5. 🔄 **Validation Task Sets**

**Common Pattern**: Both playbooks validate similar things

### Current Duplication:
```yaml
# In embedding-benchmark.yml:
- name: Validate execution mode
  ansible.builtin.assert:
    that:
      - execution_mode in ['managed', 'dut-only', 'external']

- name: Validate external endpoint configuration
  ansible.builtin.assert:
    that:
      - vllm_endpoint.external.url is defined
      - vllm_endpoint.external.url | length > 0
  when: execution_mode == 'external'

# In llm-benchmark-auto.yml:
- name: Validate required variables (managed mode)
  ansible.builtin.assert:
    that:
      - test_model is defined
      - workload_type is defined
  when: vllm_mode == 'managed'

- name: Validate required variables (external mode)
  ansible.builtin.assert:
    that:
      - workload_type is defined
  when: vllm_mode == 'external'
```

### Refactor Action:
Create `roles/common/tasks/validate-vllm-mode.yml`:

```yaml
---
# Validate vLLM mode configuration
# Requires: vllm_mode variable

- name: Validate vLLM mode value
  ansible.builtin.assert:
    that:
      - vllm_mode in ['managed', 'dut-only', 'external']
    fail_msg: |
      Invalid vllm_mode: {{ vllm_mode }}
      Supported modes: managed, dut-only, external

- name: Validate external endpoint when in external mode
  ansible.builtin.assert:
    that:
      - vllm_endpoint.external.url is defined
      - vllm_endpoint.external.url is not none
      - vllm_endpoint.external.url | length > 0
    fail_msg: |
      External mode requires vllm_endpoint.external.url
      Set via: export VLLM_ENDPOINT_URL=http://your-vllm-host:8000
      Or in inventory: vllm_endpoint.external.url
  when: vllm_mode == 'external'

- name: Warn if cores specified in external mode
  ansible.builtin.debug:
    msg:
      - "⚠️  Warning: requested_cores={{ requested_cores }} specified but not used in external mode"
      - "   External endpoints have their own CPU allocation - core count will be ignored"
  when:
    - vllm_mode == 'external'
    - requested_cores is defined
    - requested_cores | int > 0

- name: Override core count to 0 for external mode
  ansible.builtin.set_fact:
    requested_cores: 0
  when: vllm_mode == 'external'
```

## 6. 🔄 **Results Collection Pattern**

**Current**: Each playbook implements its own results collection

### Refactor Action:
Create `roles/common/tasks/collect-results.yml`:

```yaml
---
# Collect test results from remote host
# Parameters:
#   - results_source_dir: Source directory on remote host
#   - results_dest_dir: Destination on localhost
#   - test_run_id: Test run identifier

- name: Ensure local results directory exists
  ansible.builtin.file:
    path: "{{ results_dest_dir }}"
    state: directory
    mode: "0755"
  delegate_to: localhost

- name: Fetch results to local machine
  ansible.posix.synchronize:
    src: "{{ results_source_dir }}/"
    dest: "{{ results_dest_dir }}/"
    mode: pull
    recursive: true
```

## Summary of Refactoring Priority

| Priority | Refactor | Effort | Impact | Lines Saved |
|----------|----------|--------|--------|-------------|
| 🔥 High | Health check → use health-check.yml | Low | High | ~100 |
| 🔥 High | External endpoint parsing → urlsplit | Low | Medium | ~20 |
| 🟡 Medium | Unify vllm_mode/execution_mode | Medium | High | N/A (consistency) |
| 🟡 Medium | Validation tasks → common role | Medium | Medium | ~50 |
| 🟢 Low | Results collection → common task | Low | Low | ~30 |
| 🟢 Low | Dynamic host selection pattern | High | Low | ~50 |

## Implementation Plan

### Phase 1 (Quick Wins - Do Now)
1. ✅ Replace embedding health check with `import_playbook: health-check.yml`
2. ✅ Update embedding external URL parsing to use `urlsplit`
3. ✅ Unify terminology: `execution_mode` → `vllm_mode`

### Phase 2 (Medium-term)
4. Create `roles/common/tasks/validate-vllm-mode.yml`
5. Create `roles/common/tasks/configure-external-endpoint.yml`
6. Update all playbooks to use common validation

### Phase 3 (Long-term)
7. Create dynamic host selection pattern
8. Consolidate results collection
9. Document common task library

## Breaking Changes

### Renaming `execution_mode` → `vllm_mode`
**Impact**: Users who set `EXECUTION_MODE` environment variable

**Migration**:
```bash
# Old (still works via backwards compatibility):
export EXECUTION_MODE=managed

# New (recommended):
export VLLM_MODE=managed
```

**Backwards Compatibility**:
```yaml
vllm_mode: "{{ lookup('env', 'VLLM_MODE') | default(lookup('env', 'EXECUTION_MODE') | default(vllm_endpoint.mode | default('managed'), true), true) }}"
```

## Files to Create

```
automation/test-execution/ansible/roles/common/tasks/
├── validate-vllm-mode.yml         # Mode validation
├── configure-external-endpoint.yml # External endpoint setup
├── collect-results.yml             # Results fetching
└── set-test-host.yml               # Dynamic host selection
```

## References

- [health-check.yml](../../automation/test-execution/ansible/health-check.yml) - Existing common health check
- [endpoints.yml](../../automation/test-execution/ansible/inventory/group_vars/all/endpoints.yml) - Endpoint configuration
