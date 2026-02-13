# Phase 3: Resource Contention Testing

Tests platform stability under real-world server deployment scenarios.

## Overview

Phase 3 focuses on resource contention scenarios including fractional core
allocation, NUMA node isolation, and "noisy neighbor" effects. This phase
evaluates how vLLM CPU inference performs when sharing resources with other
workloads.

## Status

**Planned** - Not yet implemented

## Goals (Planned)

- Test fractional core allocation (subset of available cores)
- Measure NUMA node isolation effects
- Evaluate "noisy neighbor" scenarios
- Assess performance with co-located enterprise workloads
- Determine optimal resource partitioning strategies

## Planned Test Scenarios

### Fractional Core Allocation

- Test with 25%, 50%, 75% of total cores
- Compare performance vs full core allocation
- Identify minimum viable core count per model

### NUMA Node Isolation

- Test workload on single NUMA node
- Cross-NUMA node communication overhead
- NUMA-aware vs NUMA-oblivious allocation

### Noisy Neighbor Tests

- vLLM inference + CPU-intensive workload
- vLLM inference + memory-intensive workload
- vLLM inference + I/O-intensive workload
- Multiple vLLM instances on same system

### Multi-Tenant Scenarios

- Multiple models served simultaneously
- Resource quotas and cgroup limits
- Priority-based scheduling

## Implementation Status

This phase is planned for future implementation. The following will be added:

- [ ] Test scenario definitions
- [ ] Docker/Podman compose configurations
- [ ] Ansible playbooks for resource allocation
- [ ] Noisy neighbor workload generators
- [ ] cgroup/systemd resource limit configs
- [ ] NUMA topology-aware test configurations

## Contributing

If you'd like to help design or implement Phase 3 tests, please:

1. Review existing Phase 1 and Phase 2 test patterns
2. Consult [platform setup docs](../../docs/platform-setup/x86/intel/deterministic-benchmarking.md)
3. Open an issue or PR with proposed test scenarios

## Related Documentation

- [Phase 1 Tests](../phase-1-concurrent/) - Concurrent load testing
- [Phase 2 Tests](../phase-2-scalability/) - Scalability testing
- [Platform Setup](../../docs/platform-setup/) - CPU isolation and NUMA
  configuration
- [Testing Methodology](../../docs/methodology/overview.md) - Overall test
  strategy
