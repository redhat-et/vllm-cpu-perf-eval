#!/usr/bin/env python3
"""
Unit tests for cpu_utils.py custom Jinja2 filters.
Run with: python -m pytest test_cpu_utils.py -v
Or without pytest: python3 test_cpu_utils.py
"""

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    # Mock pytest.raises for fallback tests
    class pytest:
        class raises:
            def __init__(self, exc):
                self.exc = exc
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

from cpu_utils import (
    cpu_list_to_range,
    extract_primary_cpus,
    extract_all_cpus,
    extract_numa_nodes,
    merge_cpu_ranges,
    allocate_cores_multi_numa,
    VALID_TP_VALUES,
)

try:
    from ansible.errors import AnsibleFilterError
except ImportError:
    # Fallback if ansible not installed
    class AnsibleFilterError(Exception):
        pass


# ============================================================================
# Test Helper Functions
# ============================================================================

def create_numa_topology(num_nodes, cores_per_node=32):
    """Helper to create test NUMA topology.

    Args:
        num_nodes: Number of NUMA nodes
        cores_per_node: Physical cores per node (default: 32)

    Returns:
        dict: NUMA topology dictionary with nodes and allocation policy
    """
    nodes = []
    for i in range(num_nodes):
        base_cpu = i * cores_per_node
        physical_cpus_list = ','.join(str(base_cpu + j) for j in range(cores_per_node))
        nodes.append({
            'id': i,
            'physical_cores': cores_per_node,
            'physical_cpus': f"{base_cpu}-{base_cpu + cores_per_node - 1}",
            'physical_cpus_list': physical_cpus_list,
            'all_cpus': f"{base_cpu}-{base_cpu + cores_per_node - 1}",
            'all_cpus_list': physical_cpus_list,
        })

    return {
        'node_count': num_nodes,
        'total_physical_cores': num_nodes * cores_per_node,
        'nodes': nodes,
        'allocation_policy': {
            'housekeeping': {
                'strategy': 'reserve_node' if num_nodes >= 3 else 'minimal_reservation',
                'reserved_node': 0
            },
            'workload': {
                'prefer_same_numa': True,
                'allow_multi_numa': True,
                'use_physical_cores_only': True
            }
        }
    }


# ============================================================================
# Test Classes
# ============================================================================

class TestCpuListToRange:
    """Test cpu_list_to_range filter."""

    def test_consecutive_range(self):
        """Test consecutive CPU list converts to range."""
        assert cpu_list_to_range([0, 1, 2, 3]) == "0-3"

    def test_multiple_ranges(self):
        """Test multiple ranges are created correctly."""
        assert cpu_list_to_range([0, 1, 2, 3, 8, 9, 10, 11]) == "0-3,8-11"

    def test_single_cpus(self):
        """Test single CPUs without ranges."""
        assert cpu_list_to_range([0, 5, 10]) == "0,5,10"

    def test_mixed_ranges_and_singles(self):
        """Test mixed ranges and single CPUs."""
        assert cpu_list_to_range([0, 1, 2, 5, 10, 11, 20]) == "0-2,5,10-11,20"

    def test_string_input(self):
        """Test string comma-separated input."""
        assert cpu_list_to_range("0,1,2,3,8,9,10") == "0-3,8-10"

    def test_empty_list(self):
        """Test empty list returns empty string."""
        assert cpu_list_to_range([]) == ""

    def test_empty_string(self):
        """Test empty string returns empty string."""
        assert cpu_list_to_range("") == ""

    def test_unordered_input(self):
        """Test unordered input is sorted."""
        assert cpu_list_to_range([3, 1, 2, 0, 10, 8, 9]) == "0-3,8-10"

    def test_duplicate_cpus(self):
        """Test duplicate CPUs are handled."""
        assert cpu_list_to_range([0, 1, 1, 2, 2, 3]) == "0-3"

    def test_single_cpu(self):
        """Test single CPU."""
        assert cpu_list_to_range([5]) == "5"

    def test_invalid_type(self):
        """Test invalid type raises error."""
        with pytest.raises(AnsibleFilterError):
            cpu_list_to_range(123)


class TestExtractPrimaryCpus:
    """Test extract_primary_cpus filter."""

    def test_simple_extraction(self):
        """Test extracting primary CPUs from NUMA node."""
        lscpu_data = """0 0 0
1 0 0
2 0 1
3 0 1
64 2 32
65 2 32
66 2 33
67 2 33"""
        result = extract_primary_cpus(lscpu_data, 2)
        assert result == "64,66"

    def test_single_thread_per_core(self):
        """Test when there's only one thread per core."""
        lscpu_data = """0 0 0
1 0 1
2 0 2
3 0 3"""
        result = extract_primary_cpus(lscpu_data, 0)
        assert result == "0,1,2,3"

    def test_empty_input(self):
        """Test empty input returns empty string."""
        assert extract_primary_cpus("", 0) == ""

    def test_node_not_found(self):
        """Test NUMA node not in data returns empty."""
        lscpu_data = """0 0 0
1 0 1"""
        assert extract_primary_cpus(lscpu_data, 5) == ""

    def test_malformed_lines_ignored(self):
        """Test malformed lines are ignored."""
        lscpu_data = """0 0 0
invalid line
1 0 0
2 0 1"""
        result = extract_primary_cpus(lscpu_data, 0)
        assert result == "0,2"


class TestExtractAllCpus:
    """Test extract_all_cpus filter."""

    def test_all_cpus_extraction(self):
        """Test extracting all CPUs including SMT."""
        lscpu_data = """0 0 0
1 0 0
2 0 1
3 0 1
64 2 32
65 2 32"""
        result = extract_all_cpus(lscpu_data, 0)
        assert result == "0,1,2,3"

    def test_multiple_numa_nodes(self):
        """Test filtering by NUMA node."""
        lscpu_data = """0 0 0
1 1 1
2 0 2
3 1 3"""
        assert extract_all_cpus(lscpu_data, 0) == "0,2"
        assert extract_all_cpus(lscpu_data, 1) == "1,3"

    def test_empty_input(self):
        """Test empty input returns empty string."""
        assert extract_all_cpus("", 0) == ""


class TestExtractNumaNodes:
    """Test extract_numa_nodes filter."""

    def test_multiple_nodes(self):
        """Test extracting multiple NUMA nodes."""
        lscpu_data = """0 0 0
64 2 32
32 1 16"""
        result = extract_numa_nodes(lscpu_data)
        assert result == ['0', '1', '2']

    def test_single_node(self):
        """Test single NUMA node."""
        lscpu_data = """0 0 0
1 0 1
2 0 2"""
        result = extract_numa_nodes(lscpu_data)
        assert result == ['0']

    def test_empty_input(self):
        """Test empty input returns empty list."""
        assert extract_numa_nodes("") == []

    def test_duplicate_nodes(self):
        """Test duplicate nodes are deduplicated."""
        lscpu_data = """0 0 0
1 0 1
2 1 2
3 1 3
4 0 4"""
        result = extract_numa_nodes(lscpu_data)
        assert result == ['0', '1']


class TestMergeCpuRanges:
    """Test merge_cpu_ranges filter."""

    def test_merge_consecutive_ranges(self):
        """Test merging consecutive ranges."""
        assert merge_cpu_ranges(["0-3", "4-7"]) == "0-7"

    def test_merge_overlapping_ranges(self):
        """Test merging overlapping ranges."""
        assert merge_cpu_ranges(["0-5", "3-8"]) == "0-8"

    def test_merge_separate_ranges(self):
        """Test merging separate ranges."""
        assert merge_cpu_ranges(["0-3", "16-19"]) == "0-3,16-19"

    def test_merge_mixed_format(self):
        """Test merging mixed range and single CPUs."""
        assert merge_cpu_ranges(["0-3", "5", "7-9"]) == "0-3,5,7-9"

    def test_empty_list(self):
        """Test empty list returns empty string."""
        assert merge_cpu_ranges([]) == ""

    def test_invalid_range_format(self):
        """Test invalid range format raises error."""
        with pytest.raises(AnsibleFilterError):
            merge_cpu_ranges(["0-3-5"])


class TestRealWorldScenarios:
    """Test real-world scenarios from vLLM benchmarking."""

    def test_3_numa_node_system(self):
        """Test typical 3 NUMA node system allocation."""
        lscpu_data = """0 0 0
1 0 0
2 0 1
3 0 1
32 1 16
33 1 16
34 1 17
35 1 17
64 2 32
65 2 32
66 2 33
67 2 33"""

        # Extract NUMA nodes
        nodes = extract_numa_nodes(lscpu_data)
        assert nodes == ['0', '1', '2']

        # Housekeeping: all CPUs on node 0
        house_cpus = extract_all_cpus(lscpu_data, 0)
        assert house_cpus == "0,1,2,3"
        house_range = cpu_list_to_range(house_cpus)
        assert house_range == "0-3"

        # GuideLLM: primary CPUs on node 1
        guide_cpus = extract_primary_cpus(lscpu_data, 1)
        assert guide_cpus == "32,34"
        guide_range = cpu_list_to_range(guide_cpus)
        assert guide_range == "32,34"

        # vLLM: primary CPUs on node 2
        vllm_cpus = extract_primary_cpus(lscpu_data, 2)
        assert vllm_cpus == "64,66"
        vllm_range = cpu_list_to_range(vllm_cpus)
        assert vllm_range == "64,66"

    def test_auto_core_allocation(self):
        """Test auto core allocation from detected topology."""
        # vLLM node has primary CPUs: 64,65,66,67,68,69,70,71
        vllm_cpus_list = "64,65,66,67,68,69,70,71"

        # Request 4 cores
        requested = 4
        cpus = vllm_cpus_list.split(',')[:requested]
        allocated_range = cpu_list_to_range(cpus)

        assert allocated_range == "64-67"

    def test_large_range_conversion(self):
        """Test converting large CPU lists."""
        # 96 core system, consecutive CPUs
        cpus = list(range(0, 96))  # Consecutive CPUs 0-95
        result = cpu_list_to_range(cpus)

        # Should create a single range
        assert result == "0-95"
        assert len(result) < len(','.join(str(c) for c in cpus))  # Compressed


class TestMultiNumaAllocation:
    """Test multi-NUMA allocation with auto-TP calculation."""

    def test_single_numa_32cores(self):
        """32 cores on 3-node system → single NUMA, TP=1."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=32)

        assert result['tensor_parallel'] == 1
        assert result['allocated_nodes'] == [1]  # Node 0 reserved
        assert result['cores_per_node'] == [32]
        assert result['cpuset_cpus'] == "32-63"
        assert result['cpuset_mems'] == "1"
        assert result['omp_num_threads'] == 32
        assert result['omp_threads_bind'] is None
        assert result['allocation_strategy'] == "single_numa"

    def test_multi_numa_64cores(self):
        """64 cores on 3-node system → 2 nodes, TP=2."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=64)

        assert result['tensor_parallel'] == 2
        assert result['allocated_nodes'] == [1, 2]
        assert result['cores_per_node'] == [32, 32]
        assert result['cpuset_cpus'] == "32-63,64-95"
        assert result['cpuset_mems'] == "1,2"
        assert result['omp_num_threads'] == 32
        assert result['omp_threads_bind'] == "32-63|64-95"
        assert result['allocation_strategy'] == "multi_numa_tp2"

    def test_multi_numa_96cores_tp4(self):
        """96 cores on 6-node system → 4 nodes, TP=4."""
        topology = create_numa_topology(num_nodes=6, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=96)

        assert result['tensor_parallel'] == 4
        assert result['allocated_nodes'] == [1, 2, 3, 4]
        assert result['cores_per_node'] == [24, 24, 24, 24]
        assert result['cpuset_cpus'] == "32-55,64-87,96-119,128-151"
        assert result['cpuset_mems'] == "1,2,3,4"
        assert result['omp_num_threads'] == 24
        assert result['omp_threads_bind'] == "32-55|64-87|96-119|128-151"
        assert result['allocation_strategy'] == "multi_numa_tp4"

    def test_invalid_tp_override(self):
        """TP=3 should raise AnsibleFilterError."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)

        with pytest.raises(AnsibleFilterError) as exc_info:
            allocate_cores_multi_numa(topology, requested_cores=64, requested_tp=3)

        assert "Invalid tensor_parallel: 3" in str(exc_info.value)
        assert "Valid values: [1, 2, 4, 8]" in str(exc_info.value)

    def test_non_divisible_cores(self):
        """33 cores should fail with helpful error (not divisible by valid TP)."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)

        with pytest.raises(AnsibleFilterError) as exc_info:
            allocate_cores_multi_numa(topology, requested_cores=33)

        error_msg = str(exc_info.value)
        assert "Cannot allocate 33 cores" in error_msg
        assert "Valid allocations:" in error_msg

    def test_insufficient_cores(self):
        """Request exceeding capacity should fail."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)

        with pytest.raises(AnsibleFilterError) as exc_info:
            # Only 64 cores available (node 0 reserved), request 128
            allocate_cores_multi_numa(topology, requested_cores=128)

        error_msg = str(exc_info.value)
        assert "Cannot allocate 128 cores" in error_msg

    def test_auto_tp_prefers_smaller(self):
        """64 cores with options TP=2 or TP=4 should choose TP=2."""
        topology = create_numa_topology(num_nodes=6, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=64)

        # Should prefer TP=2 (32 cores/node) over TP=4 (16 cores/node)
        assert result['tensor_parallel'] == 2
        assert result['cores_per_node'] == [32, 32]

    def test_user_tp_override_valid(self):
        """User TP override should be respected if valid."""
        topology = create_numa_topology(num_nodes=6, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=64, requested_tp=4)

        assert result['tensor_parallel'] == 4
        assert result['allocated_nodes'] == [1, 2, 3, 4]
        assert result['cores_per_node'] == [16, 16, 16, 16]

    def test_user_tp_override_invalid_not_divisible(self):
        """User TP that doesn't divide evenly should fail."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)

        with pytest.raises(AnsibleFilterError) as exc_info:
            # 51 cores doesn't divide by TP=2
            allocate_cores_multi_numa(topology, requested_cores=51, requested_tp=2)

        assert "not evenly divisible" in str(exc_info.value)

    def test_user_tp_override_exceeds_nodes(self):
        """User TP exceeding available nodes should fail."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)

        with pytest.raises(AnsibleFilterError) as exc_info:
            # TP=8 but only 2 nodes available (node 0 reserved)
            allocate_cores_multi_numa(topology, requested_cores=64, requested_tp=8)

        assert "only 2 available NUMA nodes" in str(exc_info.value)

    def test_single_numa_node_system(self):
        """Single-NUMA system uses all nodes (no reservation)."""
        topology = create_numa_topology(num_nodes=1, cores_per_node=96)
        result = allocate_cores_multi_numa(topology, requested_cores=64)

        assert result['tensor_parallel'] == 1
        assert result['allocated_nodes'] == [0]  # Single node, use it
        assert result['cores_per_node'] == [64]
        assert result['cpuset_cpus'] == "0-63"
        assert result['cpuset_mems'] == "0"

    def test_two_numa_node_system(self):
        """2-NUMA system doesn't reserve node 0."""
        topology = create_numa_topology(num_nodes=2, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=64)

        # Should use both nodes (no reservation on 2-node systems)
        assert result['tensor_parallel'] == 2
        assert result['allocated_nodes'] == [0, 1]
        assert result['cores_per_node'] == [32, 32]


class TestOmpBinding:
    """Test OMP binding string generation."""


    def test_single_numa_no_binding(self):
        """TP=1 should return None for omp_threads_bind."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=32)

        assert result['tensor_parallel'] == 1
        assert result['omp_threads_bind'] is None

    def test_multi_numa_tp2_binding(self):
        """TP=2 should generate 'range1|range2'."""
        topology = create_numa_topology(num_nodes=3, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=64)

        assert result['tensor_parallel'] == 2
        assert result['omp_threads_bind'] == "32-63|64-95"

    def test_multi_numa_tp4_binding(self):
        """TP=4 should generate 'r1|r2|r3|r4'."""
        topology = create_numa_topology(num_nodes=6, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=96)

        assert result['tensor_parallel'] == 4
        assert result['omp_threads_bind'] == "32-55|64-87|96-119|128-151"

    def test_multi_numa_tp8_binding(self):
        """TP=8 should generate binding for 8 instances."""
        topology = create_numa_topology(num_nodes=10, cores_per_node=32)
        result = allocate_cores_multi_numa(topology, requested_cores=192)

        assert result['tensor_parallel'] == 8
        # Each TP gets 24 cores
        expected_binding = "32-55|64-87|96-119|128-151|160-183|192-215|224-247|256-279"
        assert result['omp_threads_bind'] == expected_binding


class TestValidTpValues:
    """Test TP value constraints."""

    def test_valid_tp_values_constant(self):
        """Verify VALID_TP_VALUES is correct."""
        assert VALID_TP_VALUES == [1, 2, 4, 8]

if __name__ == "__main__":
    # Run tests if pytest not available
    import sys

    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        print("pytest not available, running basic tests...")

        # Basic smoke tests
        test = TestCpuListToRange()
        test.test_consecutive_range()
        test.test_multiple_ranges()
        test.test_string_input()
        print("✓ TestCpuListToRange passed")

        test2 = TestExtractPrimaryCpus()
        test2.test_simple_extraction()
        print("✓ TestExtractPrimaryCpus passed")

        test3 = TestExtractAllCpus()
        test3.test_all_cpus_extraction()
        print("✓ TestExtractAllCpus passed")

        test4 = TestExtractNumaNodes()
        test4.test_multiple_nodes()
        print("✓ TestExtractNumaNodes passed")

        test5 = TestMergeCpuRanges()
        test5.test_merge_consecutive_ranges()
        print("✓ TestMergeCpuRanges passed")

        test6 = TestRealWorldScenarios()
        test6.test_3_numa_node_system()
        test6.test_auto_core_allocation()
        print("✓ TestRealWorldScenarios passed")

        print("\n✓ All basic tests passed!")
        sys.exit(0)
