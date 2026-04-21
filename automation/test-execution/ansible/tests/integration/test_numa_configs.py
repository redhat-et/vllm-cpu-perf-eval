#!/usr/bin/env python3
"""Integration tests for NUMA configuration and allocation."""
import pytest
import sys
from pathlib import Path

# Add filter_plugins to path for cpu_utils
sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent / "filter_plugins")
)

from cpu_utils import allocate_cores_multi_numa  # noqa: E402


@pytest.mark.integration
@pytest.mark.requires_numa
class TestNumaAllocation:
    """Test NUMA node allocation with real system topology."""

    def test_single_numa_allocation(self, numa_topology, skip_if_single_numa):
        """Test single NUMA node allocation (TP=1)."""
        # Create test topology based on actual system
        test_topology = {
            "node_count": numa_topology["node_count"],
            "total_physical_cores": 96,  # Simplified for test
            "nodes": [],
            "allocation_policy": {
                "housekeeping": {
                    "strategy": "reserve_node" if numa_topology["node_count"] >= 3 else "minimal_reservation",
                    "reserved_node": 0
                },
                "workload": {
                    "prefer_same_numa": True,
                    "allow_multi_numa": True,
                    "use_physical_cores_only": True
                }
            }
        }

        # Create simplified nodes (32 cores each)
        for i in range(numa_topology["node_count"]):
            base_cpu = i * 32
            test_topology["nodes"].append({
                "id": i,
                "physical_cores": 32,
                "physical_cpus": f"{base_cpu}-{base_cpu + 31}",
                "physical_cpus_list": ",".join(str(base_cpu + j) for j in range(32)),
            })

        # Test single NUMA allocation (32 cores)
        result = allocate_cores_multi_numa(test_topology, requested_cores=32)

        assert result["tensor_parallel"] == 1
        assert len(result["allocated_nodes"]) == 1
        assert result["cores_per_node"] == [32]
        assert result["allocation_strategy"] == "single_numa"
        assert result["omp_threads_bind"] is None
        assert result["omp_num_threads"] == 32

    def test_multi_numa_tp2(self, numa_topology, skip_if_single_numa):
        """Test 2-NUMA allocation with TP=2."""
        # Create test topology
        test_topology = {
            "node_count": numa_topology["node_count"],
            "total_physical_cores": 96,
            "nodes": [],
            "allocation_policy": {
                "housekeeping": {
                    "strategy": "reserve_node" if numa_topology["node_count"] >= 3 else "minimal_reservation",
                    "reserved_node": 0
                },
                "workload": {
                    "prefer_same_numa": True,
                    "allow_multi_numa": True,
                    "use_physical_cores_only": True
                }
            }
        }

        for i in range(numa_topology["node_count"]):
            base_cpu = i * 32
            test_topology["nodes"].append({
                "id": i,
                "physical_cores": 32,
                "physical_cpus": f"{base_cpu}-{base_cpu + 31}",
                "physical_cpus_list": ",".join(str(base_cpu + j) for j in range(32)),
            })

        # Test 64-core allocation (should use 2 NUMA nodes with TP=2)
        result = allocate_cores_multi_numa(test_topology, requested_cores=64)

        assert result["tensor_parallel"] == 2
        assert len(result["allocated_nodes"]) == 2
        assert result["cores_per_node"] == [32, 32]
        assert result["allocation_strategy"] == "multi_numa_tp2"
        assert result["omp_num_threads"] == 32
        assert result["omp_threads_bind"] is not None
        assert "|" in result["omp_threads_bind"]  # Multi-instance binding

    @pytest.mark.slow
    def test_multi_numa_tp4(self, numa_topology, skip_if_single_numa):
        """Test 4-NUMA allocation with TP=4."""
        if numa_topology["node_count"] < 5:
            pytest.skip("Test requires at least 5 NUMA nodes (1 reserved + 4 for workload)")

        test_topology = {
            "node_count": numa_topology["node_count"],
            "total_physical_cores": 192,
            "nodes": [],
            "allocation_policy": {
                "housekeeping": {
                    "strategy": "reserve_node",
                    "reserved_node": 0
                },
                "workload": {
                    "prefer_same_numa": True,
                    "allow_multi_numa": True,
                    "use_physical_cores_only": True
                }
            }
        }

        for i in range(numa_topology["node_count"]):
            base_cpu = i * 32
            test_topology["nodes"].append({
                "id": i,
                "physical_cores": 32,
                "physical_cpus": f"{base_cpu}-{base_cpu + 31}",
                "physical_cpus_list": ",".join(str(base_cpu + j) for j in range(32)),
            })

        # Test 96-core allocation (should use 4 NUMA nodes with TP=4)
        result = allocate_cores_multi_numa(test_topology, requested_cores=96)

        assert result["tensor_parallel"] == 4
        assert len(result["allocated_nodes"]) == 4
        assert sum(result["cores_per_node"]) == 96
        assert result["allocation_strategy"] == "multi_numa_tp4"
        assert result["omp_threads_bind"] is not None
        assert result["omp_threads_bind"].count("|") == 3  # 4 instances = 3 separators


@pytest.mark.integration
class TestNumaConfigCombinations:
    """Test various NUMA configuration combinations."""

    def test_invalid_tp_value_fails(self, numa_topology):
        """Invalid TP value should raise error."""
        from cpu_utils import AnsibleFilterError

        test_topology = {
            "node_count": 3,
            "total_physical_cores": 96,
            "nodes": [
                {"id": i, "physical_cores": 32, "physical_cpus": f"{i*32}-{i*32+31}"}
                for i in range(3)
            ],
            "allocation_policy": {
                "housekeeping": {"strategy": "reserve_node", "reserved_node": 0},
                "workload": {"prefer_same_numa": True, "allow_multi_numa": True}
            }
        }

        with pytest.raises(AnsibleFilterError) as exc_info:
            allocate_cores_multi_numa(test_topology, requested_cores=64, requested_tp=3)

        assert "Invalid tensor_parallel: 3" in str(exc_info.value)
        assert "Valid values: [1, 2, 4, 8]" in str(exc_info.value)

    def test_insufficient_cores_fails(self, numa_topology):
        """Requesting more cores than available should fail."""
        from cpu_utils import AnsibleFilterError

        test_topology = {
            "node_count": 2,
            "total_physical_cores": 64,
            "nodes": [
                {"id": 0, "physical_cores": 32, "physical_cpus": "0-31"},
                {"id": 1, "physical_cores": 32, "physical_cpus": "32-63"},
            ],
            "allocation_policy": {
                "housekeeping": {"strategy": "minimal_reservation", "reserved_node": 0},
                "workload": {"prefer_same_numa": True, "allow_multi_numa": True}
            }
        }

        with pytest.raises(AnsibleFilterError) as exc_info:
            allocate_cores_multi_numa(test_topology, requested_cores=128)

        assert "Cannot allocate 128 cores" in str(exc_info.value)

    def test_auto_tp_calculation(self, numa_topology):
        """Test automatic TP calculation prefers smaller TP values."""
        test_topology = {
            "node_count": 6,
            "total_physical_cores": 192,
            "nodes": [
                {"id": i, "physical_cores": 32, "physical_cpus": f"{i*32}-{i*32+31}"}
                for i in range(6)
            ],
            "allocation_policy": {
                "housekeeping": {"strategy": "reserve_node", "reserved_node": 0},
                "workload": {"prefer_same_numa": True, "allow_multi_numa": True}
            }
        }

        # 64 cores could use TP=2 (32 cores/node) or TP=4 (16 cores/node)
        # Should prefer TP=2 (fewer instances, more cores per instance)
        result = allocate_cores_multi_numa(test_topology, requested_cores=64)

        assert result["tensor_parallel"] == 2
        assert result["cores_per_node"] == [32, 32]
