# Ansible Playbooks

Organized playbook structure for vLLM performance testing automation.

## Directory Structure

```text
playbooks/
├── embedding/                    # Embedding model tests
│   ├── run-tests.yml            # Main test execution
│   ├── run-core-sweep.yml       # Core count performance sweep
│   └── tasks/                   # Reusable task files
│       ├── baseline.yml         # Baseline sweep tests
│       ├── latency.yml          # Latency/concurrency tests
│       └── core-iteration.yml   # Single core count iteration
├── llm/                         # LLM generative model tests (future)
│   ├── run-phase-1.yml
│   ├── run-phase-2.yml
│   └── tasks/
├── common/                      # Shared playbooks
│   ├── start-vllm-server.yml    # Start vLLM container on DUT
│   ├── health-check.yml         # Wait for vLLM to be ready
│   └── collect-logs.yml         # Collect logs from DUT
└── README.md                    # This file
```

## Usage

### Embedding Tests

#### Basic Test Execution

```bash
cd automation/test-execution/ansible

# Run complete embedding test suite
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml

# Run baseline test only
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=baseline"

# Run latency test only
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=latency"

# Test specific model
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "test_model=ibm-granite/granite-embedding-english-r2"
```

#### Core Count Sweep

```bash
# Test with default core counts (8, 16, 32, 64)
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/embedding-hosts.yml

# Test with custom core counts
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/embedding-hosts.yml \
  -e "test_core_counts=[8,16,24,32,40,48,56,64]"

# Core sweep with latency tests
ansible-playbook playbooks/embedding/run-core-sweep.yml \
  -i inventory/embedding-hosts.yml \
  -e "scenario=latency" \
  -e "test_core_counts=[16,32,64]"
```

### Common Playbooks

Common playbooks can be imported by other playbooks or run standalone.

```bash
# Health check only
ansible-playbook playbooks/common/health-check.yml \
  -i inventory/embedding-hosts.yml

# Collect logs only
ansible-playbook playbooks/common/collect-logs.yml \
  -i inventory/embedding-hosts.yml
```

## Playbook Details

### Embedding Playbooks

#### run-tests.yml

Main playbook for embedding model performance tests.

**Variables:**
- `scenario`: Test type - `baseline` or `latency` (default: baseline)
- `test_model`: Model to test (default: granite-embedding-278m-multilingual)
- `cleanup_after_test`: Stop vLLM after tests (default: false)

**Workflow:**
1. Start vLLM server on DUT with containerized deployment
2. Wait for vLLM health check
3. Run specified test scenario from load generator
4. Collect results and logs
5. Optional cleanup

#### run-core-sweep.yml

Test vLLM performance across different CPU core allocations.

**Variables:**
- `test_core_counts`: List of core counts to test (default: [8, 16, 32, 64])
- `scenario`: Test type - `baseline` or `latency` (default: baseline)
- `test_model`: Model to test

**Workflow:**
For each core count:
1. Deploy vLLM with specific CPU pinning
2. Health check
3. Run test scenario
4. Collect results with core count metadata
5. Stop container and prepare for next iteration

### Task Files

Task files are included by main playbooks and are not meant to be run directly.

#### baseline.yml

Runs baseline performance sweep test:
- Find max throughput (`--request-rate inf`)
- Test at 25%, 50%, 75% of max

**Output:**
- `sweep-inf.json`
- `sweep-25pct.json`
- `sweep-50pct.json`
- `sweep-75pct.json`

#### latency.yml

Runs latency scaling tests with concurrency levels:
- 16, 32, 64, 128, 196

**Output:**
- `concurrent-16.json`
- `concurrent-32.json`
- `concurrent-64.json`
- `concurrent-128.json`
- `concurrent-196.json`

#### core-iteration.yml

Single iteration for core count sweep. Handles:
- CPU pinning configuration
- vLLM container deployment
- Test execution
- Result collection
- Container cleanup

## Inventory Requirements

Playbooks expect inventory with these groups:

```yaml
all:
  children:
    dut:                          # Device Under Test
      hosts:
        embedding-dut-01:
          ansible_host: <IP>
          vllm_server:
            port: 8000
            container_runtime: podman
            container_image: vllm/vllm-openai:latest

    load_generator:               # Load Generator
      hosts:
        embedding-loadgen-01:
          ansible_host: <IP>
          bench_config:
            vllm_host: <DUT_IP>
            vllm_port: 8000
```

See [inventory/embedding-hosts.yml](../inventory/embedding-hosts.yml) for complete example.

## Variables

### Common Variables

Available in all playbooks:

- `log_dir`: Log directory on DUT (default: /var/log/vllm-embedding-tests)
- `model_cache_dir`: Hugging Face cache (default: /var/lib/vllm-models)
- `health_check.timeout`: Max wait for vLLM (default: 300s)
- `health_check.interval`: Check interval (default: 5s)

### Embedding-Specific Variables

- `vllm_env.VLLM_CPU_KVCACHE_SPACE`: KV cache size (default: 1GiB)
- `bench_config.results_dir`: Results storage (default: /var/tmp/embedding-results)

## Best Practices

### 1. Use Inventory Variables

Define hardware-specific settings in inventory:

```yaml
dut:
  hosts:
    my-dut:
      hardware:
        cores: 64
        numa_nodes: 2
      vllm_env:
        OMP_NUM_THREADS: "64"
```

### 2. Tag Results

All playbooks automatically tag results with metadata including:
- Test run ID
- Model name
- Timestamp
- Configuration details

### 3. Keep vLLM Running for Debugging

```bash
ansible-playbook playbooks/embedding/run-tests.yml \
  -i inventory/embedding-hosts.yml \
  -e "cleanup_after_test=false"
```

Then monitor logs:
```bash
automation/utilities/log-monitoring/monitor-vllm-logs.sh \
  --mode remote --remote-host <dut-ip>
```

### 4. Parallel Model Testing

Test multiple models sequentially:

```bash
for model in \
  "ibm-granite/granite-embedding-english-r2" \
  "ibm-granite/granite-embedding-278m-multilingual"; do
  ansible-playbook playbooks/embedding/run-tests.yml \
    -i inventory/embedding-hosts.yml \
    -e "test_model=$model"
done
```

## Results Location

Results are fetched to the Ansible controller:

```text
results/embedding-models/
├── <model-name>/
│   ├── baseline/
│   └── latency/
└── core-sweep-<timestamp>/
    ├── 8cores/
    ├── 16cores/
    ├── 32cores/
    └── 64cores/
```

## Troubleshooting

### Playbook fails at health check

```bash
# Check vLLM container on DUT
ssh <dut-ip> "podman ps -a | grep vllm"
ssh <dut-ip> "podman logs vllm-embedding-server"

# Check network connectivity
ping <dut-ip>
nc -zv <dut-ip> 8000
```

### Container won't start

```bash
# Check system resources on DUT
ssh <dut-ip> "free -h"
ssh <dut-ip> "df -h"

# Check for existing containers
ssh <dut-ip> "podman ps -a"

# Check journald logs
ssh <dut-ip> "journalctl -t vllm-embedding -n 100"
```

### Tests timeout

Increase timeouts in inventory:

```yaml
health_check:
  timeout: 600  # 10 minutes
  interval: 10  # 10 seconds
```

## Adding New Test Types

To add a new test type (e.g., `stress`):

1. Create task file: `embedding/tasks/stress.yml`
2. Add test logic using existing tasks as template
3. Update `run-tests.yml` to support new scenario
4. Update this README

## Future Enhancements

- [ ] Ansible roles for vLLM server and load generator
- [ ] LLM generative model playbooks
- [ ] Multi-DUT support for distributed testing
- [ ] Automated result analysis and reporting
- [ ] Integration with CI/CD pipelines

## References

- [Ansible Documentation](https://docs.ansible.com/)
- [Podman Ansible Collection](https://docs.ansible.com/ansible/latest/collections/containers/podman/index.html)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Embedding Tests Documentation](../../../tests/embedding-models/README.md)
