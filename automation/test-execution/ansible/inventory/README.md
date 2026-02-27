# Ansible Inventory Configuration

This directory contains the Ansible inventory configuration for vLLM CPU performance testing.

## Structure

```
inventory/
├── hosts.yml                    # Host definitions and SSH configuration
├── group_vars/                  # Configuration organized by logical groups
│   ├── all/                     # Variables applied to all hosts
│   │   ├── infrastructure.yml   # Platform setup, container runtime, health check
│   │   ├── endpoints.yml        # vLLM server and endpoint mode configuration
│   │   ├── benchmark-tools.yml  # GuideLLM and vllm_bench settings
│   │   ├── credentials.yml      # HuggingFace token setup
│   │   ├── test-workloads.yml   # Test configurations (embedding, chat, etc.)
│   │   └── hardware-profiles.yml # CPU/NUMA allocation templates
│   ├── dut/                     # DUT-specific overrides
│   │   └── main.yml
│   └── load_generator/          # Load generator-specific overrides
│       └── main.yml
└── examples/                    # Example configurations (coming soon)
```

## Quick Start

### 1. Configure Hosts

**Option A: Environment Variables (Recommended - No file edits)**

```bash
export DUT_HOSTNAME=192.168.1.100
export LOADGEN_HOSTNAME=192.168.1.200
export ANSIBLE_SSH_USER=ec2-user
export ANSIBLE_SSH_KEY=~/.ssh/my-key.pem
export HF_TOKEN=hf_xxxxx  # If using gated models
```

The inventory file automatically uses these environment variables with sensible defaults if not set.

**Option B: Edit hosts.yml directly**

Edit `hosts.yml` to set your DUT and load generator connection details:

```yaml
all:
  children:
    dut:
      hosts:
        vllm-server:
          ansible_host: 192.168.1.100        # ⚠️ Change to your DUT IP

    load_generator:
      hosts:
        guidellm-client:
          ansible_host: 192.168.1.200        # ⚠️ Change to your load gen IP
```

Common settings like `ansible_user` and `ansible_ssh_private_key_file` are configured in the `all.vars` section.

### 2. Configure Settings (Optional)

Most settings have sensible defaults, but you can customize them in `group_vars/all/`:

**Common Customizations:**

```yaml
# group_vars/all/benchmark-tools.yml
benchmark_tool:
  guidellm:
    use_container: true              # Set false to run guidellm from PATH
    max_requests: 500                # Adjust for your testing needs

  vllm_bench:
    use_container: true              # Set false to run vllm bench from PATH
    num_prompts: 250                 # 250=quick, 500=balanced, 1000=production

# group_vars/all/endpoints.yml
vllm_endpoint:
  mode: "managed"                    # Or "external" for cloud/k8s endpoints
  external:
    url: "http://my-vllm.example.com:8000"  # Used when mode=external
```

### 3. Set Credentials (If Using Gated Models)

```bash
# For meta-llama models
export HF_TOKEN=hf_xxxxx

# For public models (OPT, Qwen, Granite), no token needed
```

### 4. Test Configuration

```bash
# Verify inventory loads correctly
ansible-inventory -i inventory/hosts.yml --list | head -50

# Test connectivity
ansible -i inventory/hosts.yml all -m ping
```

## Configuration Files Reference

### hosts.yml

**Purpose:** Host definitions and SSH connectivity
**Contains:** ansible_host, ansible_user, SSH keys, bench_config
**When to edit:** When adding/changing test machines

### group_vars/all/infrastructure.yml

**Purpose:** System-level infrastructure settings
**Contains:**
- Platform setup (NUMA balancing, THP, preemption)
- Container runtime (Podman settings, security options)
- Health check timeouts

**When to edit:** When tuning system-level performance or container behavior

### group_vars/all/endpoints.yml

**Purpose:** vLLM server and endpoint configuration
**Contains:**
- vLLM server settings (host, port, container name)
- Endpoint mode (managed vs external)
- External endpoint configuration (URL, API key)

**When to edit:** When testing against external/cloud vLLM deployments

### group_vars/all/benchmark-tools.yml

**Purpose:** Benchmark tool configuration
**Contains:**
- GuideLLM settings (profile, concurrency, duration, execution mode)
- vllm_bench settings (num_prompts, execution mode)

**When to edit:** When adjusting benchmark parameters or switching container/host modes

### group_vars/all/credentials.yml

**Purpose:** Authentication credentials
**Contains:**
- HuggingFace token configuration (source, env var name)

**Security:** Consider adding this to `.gitignore` if storing secrets
**When to edit:** When changing credential sources (env → file → vault)

### group_vars/all/test-workloads.yml

**Purpose:** Predefined test workload configurations
**Contains:**
- Embedding workload (512:1 tokens)
- LLM workloads (chat, summarization, code, RAG)
- Backend types and vLLM arguments

**When to edit:** When adding new workload types or adjusting token lengths

### group_vars/all/hardware-profiles.yml

**Purpose:** CPU/NUMA allocation templates
**Contains:**
- Core configurations (8c, 16c, 32c, 64c, 96c, 128c)
- Tensor parallelism settings
- OMP thread configuration

**When to edit:** When testing new hardware or core count configurations

## Common Scenarios

### Scenario 1: Local Development (Mac with Podman)

```yaml
# hosts.yml
load_generator:
  hosts:
    my-loadgen:
      ansible_host: localhost
      ansible_connection: local

# group_vars/all/benchmark-tools.yml (use ARM container)
benchmark_tool:
  vllm_bench:
    container_image: "quay.io/mtahhan/vllm:arm-base-cpu"
```

### Scenario 2: Testing Public Models (No HF Token)

```yaml
# No configuration needed! Just run tests with public models:
# - facebook/opt-125m
# - Qwen/Qwen3-0.6B
# - ibm-granite/granite-3.2-2b-instruct
```

The framework will automatically skip token setup for these models.

### Scenario 3: External vLLM Endpoint (AWS/K8s)

```yaml
# group_vars/all/endpoints.yml
vllm_endpoint:
  mode: "external"
  external:
    url: "http://my-vllm-lb.example.com:8000"
    api_key:
      enabled: true
      source: "env"
      env_var: "VLLM_API_KEY"
```

Then run tests normally - playbooks will skip vLLM container management.

### Scenario 4: Host-Based Execution (No Containers)

```yaml
# group_vars/all/benchmark-tools.yml
benchmark_tool:
  guidellm:
    use_container: false  # Requires: pip install guidellm

  vllm_bench:
    use_container: false  # Requires: pip install vllm
```

Useful for CI/CD environments or when avoiding container overhead.

## Variable Precedence

Ansible loads variables in this order (later overrides earlier):

1. `group_vars/all/*.yml` - Global defaults
2. `group_vars/dut/main.yml` - DUT-specific overrides
3. `group_vars/load_generator/main.yml` - Load gen overrides
4. `hosts.yml` host vars - Per-host overrides
5. Command-line `-e` flags - Runtime overrides

Example:
```bash
# Override num_prompts at runtime
ansible-playbook ... -e "benchmark_tool={'vllm_bench': {'num_prompts': 1000}}"
```

## Migration from Old hosts.yml

If you have an existing monolithic `hosts.yml`:

1. **Backup your current configuration:**
   ```bash
   cp hosts.yml hosts.yml.backup
   ```

2. **Extract your host-specific values:**
   - `ansible_host` values
   - `ansible_user` settings
   - SSH key paths
   - Any custom overrides you made

3. **Update the new `hosts.yml` with your values**

4. **Verify:**
   ```bash
   ansible-inventory -i inventory/hosts.yml --list | jq '.all.vars' > new.json
   ansible-inventory -i inventory/hosts.yml.backup --list | jq '.all.vars' > old.json
   diff new.json old.json  # Should show no differences in variable values
   ```

## Troubleshooting

### Variables not loading

```bash
# Check what Ansible sees
ansible-inventory -i inventory/hosts.yml --list

# Check for YAML syntax errors
ansible-inventory -i inventory/hosts.yml --list --yaml
```

### Precedence issues

```bash
# See which file defines a variable
ansible-inventory -i inventory/hosts.yml --host my-dut --yaml

# Test with verbose output
ansible-playbook -i inventory/hosts.yml playbook.yml -vvv
```

### Group vars not found

Ensure directory structure matches exactly:
```
inventory/
├── hosts.yml
└── group_vars/
    └── all/
        └── *.yml
```

Ansible looks for `group_vars/` in the same directory as the inventory file.

## Best Practices

1. **Never commit credentials:** Add `group_vars/all/credentials.yml` to `.gitignore` if storing secrets
2. **Use environment variables for secrets:** `export HF_TOKEN=...` instead of hardcoding
3. **Keep hosts.yml minimal:** Only host definitions and SSH config
4. **Document custom values:** Add comments explaining non-obvious settings
5. **Test after changes:** Run `ansible-inventory --list` to verify
6. **Use consistent formatting:** Follow YAML best practices (2-space indent, quotes for strings with special chars)

## See Also

- [Main README](../../../../README.md) - Project overview and usage
- [Playbook Documentation](../playbooks/README.md) - How to run tests
- [Model Matrix](../../../../models/) - Available models and their gating status
