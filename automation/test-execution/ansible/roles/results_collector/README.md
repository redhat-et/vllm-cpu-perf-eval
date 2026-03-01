# Results Collector Role

Collects vLLM server logs and system metrics from DUT hosts.

## Overview

This role provides flexible log collection that can save logs to any destination directory. It supports both journald-based log collection (preferred) and container logs (fallback), along with system metrics snapshots.

## Features

- ✅ **Flexible destination paths** - Save logs alongside test results or to separate directory
- ✅ **Customizable journald tags** - Query specific workload logs using custom identifiers
- ✅ **Fallback mechanism** - Tries journald first, falls back to container logs
- ✅ **System metrics collection** - CPU info, memory usage, container stats
- ✅ **Consistent naming** - Configurable log file prefixes

## Usage

### Basic Usage (Default Destination)

```yaml
- hosts: dut
  become: true
  roles:
    - role: results_collector
```

This saves logs to: `results/logs/{hostname}/`

### Custom Destination (Recommended)

```yaml
- hosts: dut
  become: true
  roles:
    - role: results_collector
      vars:
        log_collection_dest: "{{ playbook_dir }}/../../../results/llm/{{ test_model | replace('/', '__') }}/{{ workload_type }}-{{ test_run_id }}/"
        journald_identifier: "vllm-{{ workload_type }}-{{ core_configuration.cores }}c-tp{{ core_configuration.tensor_parallel }}"
        log_filename_prefix: "vllm-server"
```

This saves logs alongside test results in: `results/llm/Qwen__Qwen2.5-3B-Instruct/chat-20260301-173309/`

### Example: LLM Benchmark Integration

```yaml
- name: "Collect Logs from DUT"
  hosts: dut
  become: true
  vars:
    test_run_id: "{{ hostvars['localhost']['test_run_id'] }}"
    core_configuration: "{{ hostvars['localhost']['core_configuration'] }}"

  roles:
    - role: results_collector
      vars:
        log_collection_dest: "{{ playbook_dir }}/../../../results/llm/{{ test_model | replace('/', '__') }}/{{ workload_type }}-{{ test_run_id }}/"
        journald_identifier: "vllm-{{ workload_type }}-{{ core_configuration.cores }}c-tp{{ core_configuration.tensor_parallel }}"
        log_filename_prefix: "vllm-server"
        journald_time_range: "1 hour ago"
```

## Role Variables

### Required Variables

None - all variables have sensible defaults.

### Optional Variables (defined in `defaults/main.yml`)

| Variable | Default | Description |
|----------|---------|-------------|
| `log_collection_dest` | `results/logs/{hostname}/` | Destination directory for collected logs |
| `journald_identifier` | `vllm-*` | Journald tag/identifier to query |
| `log_filename_prefix` | `vllm-server` | Prefix for saved log files |
| `collect_journald_logs` | `true` | Whether to collect journald logs |
| `collect_container_logs` | `true` | Whether to collect container logs (fallback) |
| `collect_system_metrics` | `true` | Whether to collect system metrics |
| `journald_time_range` | `1 hour ago` | Time range for journald queries |

### Global Variables (from inventory)

| Variable | Description |
|----------|-------------|
| `log_dir` | Temporary directory on DUT for staging logs (typically `/tmp/vllm-logs`) |
| `vllm_container_name` | Container name for podman logs fallback |
| `container_runtime.engine` | Container runtime type (`podman` or `docker`) |

## Collected Files

The role collects and saves these files to `log_collection_dest`:

1. **`{log_filename_prefix}.log`** - vLLM server logs from journald or container
2. **`system-metrics.log`** - System snapshot including:
   - CPU information (lscpu)
   - Memory usage (free -h)
   - Container stats (podman stats)

## Log Collection Strategy

### Journald (Primary)

The role first attempts to collect logs from journald using the specified `journald_identifier`:

```bash
journalctl -t <journald_identifier> --since '<journald_time_range>' --no-pager
```

**Advantages:**
- Persistent across container restarts
- Standardized systemd integration
- Supports structured logging

### Container Logs (Fallback)

If journald logs are empty or unavailable, falls back to container logs:

```bash
podman logs <vllm_container_name>
```

**Use cases:**
- Container not configured with journald driver
- Testing in environments without systemd
- Collecting logs from stopped containers

## Examples by Workload Type

### LLM Generative Models

```yaml
journald_identifier: "vllm-chat-16c-tp1"
log_collection_dest: "results/llm/Qwen__Qwen2.5-3B-Instruct/chat-20260301-173309/"
```

### Embedding Models

```yaml
journald_identifier: "vllm-embedding"
log_collection_dest: "results/embedding/granite-embedding-278m/baseline-20260301-120000/"
```

### Auto-Configured Tests

```yaml
journald_identifier: "vllm-{{ workload_type }}-{{ core_configuration.cores }}c-tp{{ core_configuration.tensor_parallel }}"
log_collection_dest: "{{ playbook_dir }}/../../../results/llm/{{ test_model | replace('/', '__') }}/{{ workload_type }}-{{ test_run_id }}/"
```

## Migration from Old Approach

### Before (Inline Code - 60+ lines)

```yaml
- name: Get vLLM logs from journald
  ansible.builtin.command:
    cmd: "journalctl -t vllm-{{ workload_type }}-{{ core_configuration.cores }}c-tp{{ core_configuration.tensor_parallel }} --no-pager"
  register: vllm_logs

- name: Save vLLM logs
  ansible.builtin.copy:
    content: "{{ vllm_logs.stdout }}"
    dest: "{{ log_dir }}/vllm-server.log"

- name: Collect system metrics
  ansible.builtin.shell: |
    echo "=== CPU Info ===" > {{ log_dir }}/system-metrics.log
    # ... 15+ more lines

- name: Fetch logs
  ansible.builtin.fetch:
    src: "{{ log_dir }}/vllm-server.log"
    dest: "results/llm/..."
```

### After (Role-Based - 8 lines)

```yaml
- role: results_collector
  vars:
    log_collection_dest: "results/llm/{{ test_model | replace('/', '__') }}/{{ workload_type }}-{{ test_run_id }}/"
    journald_identifier: "vllm-{{ workload_type }}-{{ core_configuration.cores }}c-tp{{ core_configuration.tensor_parallel }}"
    log_filename_prefix: "vllm-server"
```

## Benefits of Consolidated Approach

1. **DRY Principle** - 60+ lines of duplicated code eliminated
2. **Consistency** - All playbooks use the same log collection mechanism
3. **Co-location** - Logs saved alongside test results (better UX)
4. **Flexibility** - Easy to customize destination and journald tags
5. **Maintainability** - Single role to update for all playbooks

## Troubleshooting

### No logs collected

**Symptom:** Warning message "No vLLM logs found in journald or container"

**Causes:**
1. Wrong `journald_identifier` - Check container's `--log-opt tag=` value
2. Container not running when logs collected
3. Journald not configured on system
4. Time range too restrictive

**Solutions:**
- Verify journald tag: `journalctl -t <identifier> --no-pager | head`
- Check container exists: `podman ps -a | grep vllm`
- Expand time range: `journald_time_range: "2 hours ago"`
- Enable container log fallback: `collect_container_logs: true`

### Logs in wrong location

**Symptom:** Logs not appearing in expected directory

**Cause:** `log_collection_dest` not set correctly

**Solution:** Verify path includes `playbook_dir` reference:
```yaml
log_collection_dest: "{{ playbook_dir }}/../../../results/llm/..."
```

### System metrics missing

**Symptom:** Only vLLM logs collected, no system-metrics.log

**Cause:** `collect_system_metrics` disabled or commands failed

**Solution:**
- Check variable: `collect_system_metrics: true`
- Verify commands available: `lscpu`, `free`, `podman stats`

## Dependencies

- **Ansible Collections:**
  - `ansible.builtin`
  - `containers.podman` (for container log collection)

- **System Commands:**
  - `journalctl` (systemd)
  - `lscpu` (util-linux)
  - `free` (procps)
  - `podman` or `docker` (container runtime)

## Files

- `tasks/main.yml` - Role entry point
- `tasks/collect-vllm-logs.yml` - Log collection logic
- `defaults/main.yml` - Default variable values
- `README.md` - This file

## Author

vLLM CPU Performance Evaluation Project

## License

Same as parent project
