---
layout: default
title: vLLM Scale-Out Deployment
---

## vLLM Scale-Out Deployment

Deploy and test multiple vLLM instances with nginx load balancing for performance testing at scale.

## Overview

The scale-out deployment allows you to run N vLLM instances on a single DUT with configurable:

- **Number of instances** (1-10)
- **Cores per instance** (8, 16, or 32 cores)
- **SMT/HyperThreading** (enable/disable)
- **Prefix caching** (enable/disable)
- **Load balancing policy** (round-robin, least connections, IP hash)

### Architecture

```
┌─────────────────────────────────────────┐
│  Load Generator Host                    │
│  • GuideLLM concurrent tests            │
└─────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│  DUT Host (Remote)                      │
│  ┌───────────────────────────────────┐  │
│  │ Nginx LB (port 8080)              │  │
│  └───────────────────────────────────┘  │
│         │                               │
│    ┌────┼────┐                         │
│    ▼    ▼    ▼                         │
│  [vLLM][vLLM][vLLM]  (N instances)    │
│  32core 32core 32core                 │
└─────────────────────────────────────────┘
```

**Key Points:**
- All vLLM instances run on **one DUT host** (different CPU cores)
- Nginx runs on **same DUT host** (via podman-compose)  
- GuideLLM runs on **load_generator host** (remote)
- Same deployment pattern as existing single-instance benchmarks

---

## Quick Start

### Prerequisites

On the DUT:
```bash
pip3 install podman-compose
```

### Deploy

```bash
cd automation/test-execution/ansible

# Deploy with defaults (5 instances × 32 cores, least connections)
ansible-playbook start-vllm-scaleout.yml
```

### Test

```bash
# Health check
curl http://DUT_IP:8080/health

# Run concurrent benchmarks from load_generator
ansible-playbook llm-benchmark-concurrent-load.yml
```

### Stop

```bash
ansible-playbook stop-vllm-scaleout.yml
```

---

## Configuration

### Parameters

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `scaleout_num_instances` | 5 | 1-10 | Number of vLLM instances |
| `scaleout_cores_per_instance` | 32 | 8, 16, 32 | CPU cores per instance |
| `scaleout_enable_smt` | false | true/false | Enable SMT/HT cores |
| `scaleout_enable_prefix_caching` | true | true/false | Enable prefix caching |
| `scaleout_nginx_policy` | least_conn | round_robin, least_conn, ip_hash | Load balancing |

### Load Balancing Policies

- **`round_robin`** - Even distribution (best for uniform requests)
- **`least_conn`** - Route to least busy (best for mixed workloads) ⭐ Recommended
- **`ip_hash`** - Session affinity (best for stateful operations)

### Example Configuration

Edit `inventory/hosts.yml`:

```yaml
all:
  children:
    dut:
      hosts:
        vllm-server:
          ansible_host: 192.168.1.101
      vars:
        scaleout_num_instances: 5
        scaleout_cores_per_instance: 32
        scaleout_nginx_policy: "least_conn"
        test_model: "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
```

See `inventory/examples/vllm-scaleout-deployment.yml` for complete example.

---

## Usage Examples

### Custom Instance Count

```bash
# Deploy 3 instances with 16 cores each
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_num_instances=3 scaleout_cores_per_instance=16"
```

### Different Load Balancing

```bash
# Use round-robin policy
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_nginx_policy=round_robin"
```

### Enable SMT Cores

```bash
# Deploy 8 instances with 8 cores each + SMT
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_num_instances=8 scaleout_cores_per_instance=8 scaleout_enable_smt=true"
```

### Disable Prefix Caching

```bash
ansible-playbook start-vllm-scaleout.yml \
  -e "scaleout_enable_prefix_caching=false"
```

---

## Testing & Benchmarking

### Concurrent Load Testing

```bash
# Standard concurrent test
ansible-playbook llm-benchmark-concurrent-load.yml

# Auto benchmark sweep
ansible-playbook llm-benchmark-auto.yml

# Custom parameters
ansible-playbook llm-benchmark-concurrent-load.yml \
  -e "concurrent_users=50" \
  -e "test_duration=300"
```

### Test Multiple Configurations

```bash
#!/bin/bash
# Test different instance counts
for n in 3 5 8; do
  ansible-playbook start-vllm-scaleout.yml -e "scaleout_num_instances=$n"
  ansible-playbook llm-benchmark-concurrent-load.yml
  ansible-playbook collect-sweep-results.yml
  ansible-playbook stop-vllm-scaleout.yml
  sleep 30
done
```

---

## Management

### View Status

On the DUT:
```bash
# Container status
podman ps

# Service logs
podman logs vllm-nginx-lb -f           # Nginx (see load distribution)
podman logs vllm-instance-1 -f         # Specific vLLM instance

# Nginx stats
curl http://localhost:8080/nginx_status
```

### Restart Deployment

```bash
podman-compose -f /tmp/vllm-scaleout/docker-compose.yml restart
```

### Stop Deployment

```bash
# Stop (keep model cache)
ansible-playbook stop-vllm-scaleout.yml

# Stop and remove everything
ansible-playbook stop-vllm-scaleout.yml -e "scaleout_cleanup_volumes=true"
```

---

## Common Scenarios

### Scenario 1: Test Instance Scaling

Compare performance with 3, 5, and 8 instances:

```bash
for n in 3 5 8; do
  ansible-playbook start-vllm-scaleout.yml -e "scaleout_num_instances=$n"
  ansible-playbook llm-benchmark-concurrent-load.yml
  ansible-playbook stop-vllm-scaleout.yml
done
```

### Scenario 2: Test Core Allocation

Compare 8 vs 16 vs 32 cores per instance:

```bash
for cores in 8 16 32; do
  ansible-playbook start-vllm-scaleout.yml -e "scaleout_cores_per_instance=$cores"
  ansible-playbook llm-benchmark-concurrent-load.yml
  ansible-playbook stop-vllm-scaleout.yml
done
```

### Scenario 3: Test Load Balancing Policies

```bash
for policy in round_robin least_conn; do
  ansible-playbook start-vllm-scaleout.yml -e "scaleout_nginx_policy=$policy"
  ansible-playbook llm-benchmark-concurrent-load.yml
  ansible-playbook stop-vllm-scaleout.yml
done
```

### Scenario 4: Test Prefix Caching Impact

```bash
for caching in true false; do
  ansible-playbook start-vllm-scaleout.yml -e "scaleout_enable_prefix_caching=$caching"
  ansible-playbook llm-benchmark-concurrent-load.yml
  ansible-playbook stop-vllm-scaleout.yml
done
```

---

## Troubleshooting

### Deployment Fails

**Check prerequisites:**
```bash
podman-compose --version
lscpu  # Verify sufficient cores available
```

**Check for conflicts:**
```bash
podman ps | grep -E "8000|8080"  # Check port usage
```

### Instance Won't Start

```bash
# Check logs
podman logs vllm-instance-1

# Common issues:
# - Insufficient memory
# - Model download failure (need HF token?)
# - CPU core conflicts
```

### Nginx Not Distributing

```bash
# Verify nginx configuration
podman exec vllm-nginx-lb nginx -t

# Check upstream status
curl http://localhost:8080/nginx_status

# View load distribution
podman logs vllm-nginx-lb | grep "upstream"
```

### Can't Connect from Load Generator

```bash
# On DUT, check firewall
firewall-cmd --add-port=8080/tcp --permanent
firewall-cmd --reload

# Test locally first
curl http://localhost:8080/health
```

---

## Performance Tips

1. **Match cores to NUMA nodes** - Use `lscpu --extended` to view topology
2. **Disable SMT for vLLM** - Usually provides better single-thread performance
3. **Enable prefix caching** - Significant speedup for repeated prompts
4. **Use least_conn policy** - Best for mixed workloads
5. **Monitor memory** - Each instance needs adequate RAM for the model
6. **Test incrementally** - More instances isn't always better (overhead vs parallelism)

---

## Files & Directories

### Playbooks

- `automation/test-execution/ansible/start-vllm-scaleout.yml` - Deploy scale-out
- `automation/test-execution/ansible/stop-vllm-scaleout.yml` - Cleanup

### Configuration

- `inventory/group_vars/all/vllm-scaleout.yml` - Default settings
- `inventory/examples/vllm-scaleout-deployment.yml` - Example inventory

### Role

- `roles/vllm_scaleout/` - Ansible role for deployment
  - `defaults/main.yml` - Default variables
  - `tasks/main.yml` - Deployment tasks
  - `templates/` - Jinja2 templates for docker-compose and nginx

---

## Related Documentation

- [Getting Started Guide](getting-started.md) - Initial setup
- [Methodology Overview](methodology/overview.md) - Testing methodology
- [Metrics Collection](metrics-collection.md) - Performance metrics

For detailed Ansible documentation, see:
- [Full Ansible Guide](https://github.com/redhat-et/vllm-cpu-perf-eval/blob/main/automation/test-execution/ansible/ansible.md)
- [Configuration Reference](https://github.com/redhat-et/vllm-cpu-perf-eval/blob/main/automation/test-execution/ansible/inventory/group_vars/all/vllm-scaleout.yml)
