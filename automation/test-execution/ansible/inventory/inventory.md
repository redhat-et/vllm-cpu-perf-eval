# Inventory Files

## Quick Start - Use `hosts.yml`

**For most users**: Edit **[hosts.yml](hosts.yml)** and change only these values:

```yaml
dut:
  hosts:
    my-dut:
      ansible_host: 192.168.1.10              # ⚠️ Change to your DUT IP
      ansible_user: ec2-user                  # ⚠️ Change if different
      ansible_ssh_private_key_file: ~/.ssh/your-key.pem  # ⚠️ Change to your key

load_generator:
  hosts:
    my-loadgen:
      ansible_host: 192.168.1.20              # ⚠️ Change to your Load Gen IP
      ansible_user: ec2-user                  # ⚠️ Change if different
      ansible_ssh_private_key_file: ~/.ssh/your-key.pem  # ⚠️ Change to your key
      bench_config:
        vllm_host: 192.168.1.10               # ⚠️ Should match DUT IP
```

**That's it!** Everything else is pre-configured.

## Inventory Files Overview

| File | Purpose | When to Use |
|------|---------|-------------|
| **[hosts.yml](hosts.yml)** | **Main inventory** - All-in-one configuration | **Use this for all testing** ✅ |
| [test-configurations.yml](test-configurations.yml) | Test configs only (imported by hosts.yml) | Reference only |
| [example-full-config.yml](example-full-config.yml) | Complete example with all options | Reference/template for advanced users |
| [embedding-hosts.yml](embedding-hosts.yml) | Legacy embedding-specific inventory | Reference only |

## Using hosts.yml

### 1. Edit the IP Addresses

```bash
# Edit the inventory file
vi inventory/hosts.yml

# Or use your favorite editor
code inventory/hosts.yml
```

Change these sections:
- `ansible_host` - Your actual IP addresses
- `ansible_user` - Your SSH username (ec2-user, ubuntu, root, etc.)
- `ansible_ssh_private_key_file` - Path to your SSH key
- `vllm_host` under load_generator - Should match DUT IP

### 2. Test Connectivity

```bash
# Verify Ansible can reach your hosts
ansible -i inventory/hosts.yml all -m ping

# Expected output:
# my-dut | SUCCESS => { "ping": "pong" }
# my-loadgen | SUCCESS => { "ping": "pong" }
```

### 3. Run Tests

```bash
# Set HuggingFace token
export HF_TOKEN=hf_xxxxx

# Run a simple auto-configured test
ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test-auto.yml \
  -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
  -e "workload_type=summarization" \
  -e "requested_cores=16"
```

## What's Included in hosts.yml

✅ **All test configurations**:
- Embedding models
- LLM workloads (summarization, chat, code, rag)
- vLLM arguments (`--dtype=bfloat16`, `--no_enable_prefix_caching`)

✅ **All core configurations**:
- 8, 16, 32, 64, 96, 128 cores
- Single and multi-socket
- Tensor parallelism (TP=1,2,3,4)

✅ **Platform setup options**:
- NUMA balancing configuration
- THP defrag settings
- Kernel tuning parameters

✅ **Container runtime settings**:
- Podman/Docker configuration
- Security options
- Network settings

## Advanced Configuration

### Customize Test Configurations

Edit the `test_configs` section in [hosts.yml](hosts.yml):

```yaml
test_configs:
  my_custom_test:
    workload_type: "summarization"
    isl: 2048              # Custom input length
    osl: 512               # Custom output length
    backend: "openai-completions"
    vllm_args:
      - "--dtype=bfloat16"
      - "--my-custom-arg"   # Add your custom args
    kv_cache_space: "50GiB"
```

Then use it:
```bash
ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test.yml \
  -e "workload_type=my_custom_test" \
  ...
```

### Customize Core Configurations

Edit the `core_configs` section in [hosts.yml](hosts.yml):

```yaml
core_configs:
  - name: "my-custom-24cores"
    cores: 24
    cpuset_cpus: "0-23"           # Match your hardware
    cpuset_mems: "0"
    tensor_parallel: 1
    # Optional OMP tuning
    omp_num_threads: 24
    omp_threads_bind: "0-23"
```

Then use it:
```bash
ansible-playbook -i inventory/hosts.yml \
  playbooks/llm/run-guidellm-test.yml \
  -e "core_config_name=my-custom-24cores" \
  ...
```

## Other Inventory Files (Reference)

### test-configurations.yml

Contains only test and core configurations, separate from host information.

**When to use**: If you want to maintain host info separately from test configs.

### example-full-config.yml

Comprehensive example showing all possible configuration options.

**When to use**: As a reference for advanced configurations or edge cases.

### embedding-hosts.yml

Legacy inventory file specific to embedding model testing.

**When to use**: Reference only. Use `hosts.yml` instead.

## Migration from Other Inventories

If you have existing inventory files:

1. Copy your host information (IP, user, SSH key) to `hosts.yml`
2. Copy any custom test or core configurations to `hosts.yml`
3. Use `hosts.yml` for all future tests

## Troubleshooting

### SSH Connection Failed

```bash
# Test SSH manually first
ssh -i ~/.ssh/your-key.pem ec2-user@192.168.1.10

# Check SSH key permissions
chmod 600 ~/.ssh/your-key.pem

# Add -vvv for verbose output
ansible -i inventory/hosts.yml all -m ping -vvv
```

### Wrong HuggingFace Token

```bash
# Verify token is set
echo $HF_TOKEN

# Set it if missing
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Test token works
huggingface-cli whoami
```

### NUMA Detection Issues

```bash
# Manually check NUMA on DUT
ssh your-dut lscpu -e=CPU,NODE,CORE

# Run NUMA detection playbook
ansible-playbook -i inventory/hosts.yml \
  playbooks/common/tasks/detect-numa-topology.yml
```

## Best Practices

1. **Version control**: Keep `hosts.yml` in version control with placeholder IPs
2. **Secrets**: Never commit SSH keys or HF tokens to version control
3. **Testing**: Test connectivity before running full benchmarks
4. **Documentation**: Document any custom configurations you add

## Quick Reference

```bash
# Test connectivity
ansible -i inventory/hosts.yml all -m ping

# Platform setup (one-time)
ansible-playbook -i inventory/hosts.yml playbooks/common/setup-platform.yml

# Auto-config test
ansible-playbook -i inventory/hosts.yml playbooks/llm/run-guidellm-test-auto.yml \
  -e "test_model=MODEL" -e "workload_type=WORKLOAD" -e "requested_cores=N"

# Manual-config test
ansible-playbook -i inventory/hosts.yml playbooks/llm/run-guidellm-test.yml \
  -e "test_model=MODEL" -e "workload_type=WORKLOAD" -e "core_config_name=CONFIG"

# Core sweep
ansible-playbook -i inventory/hosts.yml playbooks/llm/run-core-sweep-auto.yml \
  -e "test_model=MODEL" -e "workload_type=WORKLOAD" -e "requested_cores_list=[8,16,32]"
```
