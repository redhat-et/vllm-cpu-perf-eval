#!/usr/bin/env python3
"""
Custom Jinja2 filters for CPU topology manipulation in Ansible.
Replaces awk/shell scripts with native Python for better maintainability.
"""

try:
    from ansible.errors import AnsibleFilterError
except ImportError:
    # Fallback for testing without Ansible installed
    class AnsibleFilterError(Exception):
        """Fallback exception class for filter errors."""
        pass


def cpu_list_to_range(cpu_list):
    """
    Convert a list of CPU IDs to a compact range string.

    Args:
        cpu_list: List of integers or comma-separated string

    Returns:
        String with CPU ranges (e.g., "0-3,8-11,16")

    Examples:
        [0,1,2,3,8,9,10,11,16] -> "0-3,8-11,16"
        "0,1,2,3,8,9,10,11,16" -> "0-3,8-11,16"
    """
    if not cpu_list:
        return ""

    # Handle string input (comma-separated)
    if isinstance(cpu_list, str):
        if not cpu_list.strip():
            return ""
        cpu_list = [int(x.strip()) for x in cpu_list.split(',') if x.strip()]

    # Handle list input
    if not isinstance(cpu_list, list):
        raise AnsibleFilterError(f"cpu_list_to_range expects list or string, got {type(cpu_list)}")

    if not cpu_list:
        return ""

    # Convert to sorted list of integers
    try:
        cpus = sorted(set(int(cpu) for cpu in cpu_list))
    except (ValueError, TypeError) as e:
        raise AnsibleFilterError(f"Invalid CPU list format: {e}")

    if not cpus:
        return ""

    # Build ranges
    ranges = []
    start = cpus[0]
    prev = cpus[0]

    for cpu in cpus[1:]:
        if cpu == prev + 1:
            # Continue current range
            prev = cpu
        else:
            # End current range, start new one
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{prev}")
            start = cpu
            prev = cpu

    # Add final range
    if start == prev:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{prev}")

    return ','.join(ranges)


def extract_primary_cpus(lscpu_data, numa_node):
    """
    Extract primary CPUs (first thread per core) for a given NUMA node.

    Args:
        lscpu_data: String output from lscpu -e=CPU,NODE,CORE
        numa_node: NUMA node number to filter by

    Returns:
        Comma-separated string of primary CPU IDs

    Example:
        lscpu_data = "0 0 0\n1 0 0\n2 0 1\n3 0 1\n64 2 32\n65 2 32"
        extract_primary_cpus(lscpu_data, 2) -> "64"
    """
    if not lscpu_data or not isinstance(lscpu_data, str):
        return ""

    # Parse lscpu output: CPU NODE CORE
    core_min_cpu = {}

    for line in lscpu_data.strip().split('\n'):
        parts = line.split()
        if len(parts) < 3:
            continue

        try:
            cpu = int(parts[0])
            node = int(parts[1])
            core = int(parts[2])
        except (ValueError, IndexError):
            continue

        # Filter by NUMA node
        if node != int(numa_node):
            continue

        # Track minimum CPU per core (primary thread)
        if core not in core_min_cpu or cpu < core_min_cpu[core]:
            core_min_cpu[core] = cpu

    # Return sorted list of primary CPUs
    primary_cpus = sorted(core_min_cpu.values())
    return ','.join(str(cpu) for cpu in primary_cpus)


def extract_all_cpus(lscpu_data, numa_node):
    """
    Extract all CPUs (primary + SMT threads) for a given NUMA node.

    Args:
        lscpu_data: String output from lscpu -e=CPU,NODE,CORE
        numa_node: NUMA node number to filter by

    Returns:
        Comma-separated string of all CPU IDs

    Example:
        lscpu_data = "0 0 0\n1 0 0\n2 0 1\n3 0 1"
        extract_all_cpus(lscpu_data, 0) -> "0,1,2,3"
    """
    if not lscpu_data or not isinstance(lscpu_data, str):
        return ""

    cpus = []

    for line in lscpu_data.strip().split('\n'):
        parts = line.split()
        if len(parts) < 2:
            continue

        try:
            cpu = int(parts[0])
            node = int(parts[1])
        except (ValueError, IndexError):
            continue

        # Filter by NUMA node
        if node == int(numa_node):
            cpus.append(cpu)

    # Return sorted list
    cpus.sort()
    return ','.join(str(cpu) for cpu in cpus)


def extract_numa_nodes(lscpu_data):
    """
    Extract unique NUMA node numbers from lscpu data.

    Args:
        lscpu_data: String output from lscpu -e=CPU,NODE,CORE

    Returns:
        Sorted list of NUMA node numbers (as strings)

    Example:
        lscpu_data = "0 0 0\n64 2 32\n32 1 16"
        extract_numa_nodes(lscpu_data) -> ['0', '1', '2']
    """
    if not lscpu_data or not isinstance(lscpu_data, str):
        return []

    nodes = set()

    for line in lscpu_data.strip().split('\n'):
        parts = line.split()
        if len(parts) < 2:
            continue

        try:
            node = int(parts[1])
            nodes.add(node)
        except (ValueError, IndexError):
            continue

    # Return sorted list as strings (for consistency with Ansible)
    return [str(n) for n in sorted(nodes)]


def merge_cpu_ranges(range_list):
    """
    Merge multiple CPU range strings into one.

    Args:
        range_list: List of CPU range strings

    Returns:
        Single merged CPU range string

    Example:
        ["0-3", "8-11", "4-7"] -> "0-11"
        ["0-3", "16-19"] -> "0-3,16-19"
    """
    if not range_list:
        return ""

    # Parse all ranges to CPU list
    all_cpus = []

    for cpu_range in range_list:
        if not cpu_range or not isinstance(cpu_range, str):
            continue

        for part in cpu_range.split(','):
            part = part.strip()
            if not part:
                continue

            if '-' in part:
                # Range format: "0-3"
                try:
                    start, end = part.split('-', 1)
                    all_cpus.extend(range(int(start), int(end) + 1))
                except (ValueError, IndexError):
                    raise AnsibleFilterError(f"Invalid CPU range format: {part}")
            else:
                # Single CPU
                try:
                    all_cpus.append(int(part))
                except ValueError:
                    raise AnsibleFilterError(f"Invalid CPU number: {part}")

    # Convert back to range format
    return cpu_list_to_range(all_cpus)


def extract_size_value(size_str):
    """
    Extract numeric value from size string (removing unit suffix).

    vLLM's VLLM_CPU_KVCACHE_SPACE expects just the numeric value (e.g., 40 for 40GB),
    not the full bytes conversion.

    Args:
        size_str: Size string with unit (e.g., "40GiB", "1024MiB") or integer

    Returns:
        Integer or float representing the numeric value without unit

    Examples:
        "40GiB" -> 40
        "1GiB" -> 1
        "512MiB" -> 512
        1024 -> 1024
    """
    # If already a number, return as-is
    if isinstance(size_str, (int, float)):
        return size_str

    if not isinstance(size_str, str):
        raise AnsibleFilterError(
            f"extract_size_value expects string or number, got {type(size_str)}"
        )

    size_str = size_str.strip()

    # Try to parse the number and unit
    import re
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([A-Za-z]+)?$', size_str)

    if match:
        value = match.group(1)
        # Return as int if no decimal, otherwise float
        if '.' in value:
            return float(value)
        return int(value)

    # Try parsing as plain number
    try:
        value_float = float(size_str)
        return int(value_float) if value_float.is_integer() else value_float
    except ValueError:
        raise AnsibleFilterError(
            f"Invalid size format: {size_str}. Expected: '40GiB', '1024', etc."
        )


# Valid tensor parallelism values (powers of 2, capped at 8)
VALID_TP_VALUES = [1, 2, 4, 8]


def allocate_cores_multi_numa(numa_topology, requested_cores, requested_tp=None):
    """
    Multi-NUMA core allocation with automatic tensor parallelism calculation.

    Intelligently allocates cores across NUMA nodes when requested cores exceed
    single-node capacity. Auto-calculates optimal TP value (powers of 2, max 8)
    or validates user-provided TP.

    Args:
        numa_topology: Topology dict with nodes inventory and allocation policy
        requested_cores: Total physical cores to allocate
        requested_tp: Optional user override for tensor parallelism (must be valid)

    Returns:
        dict: Allocation configuration with:
            - allocated_nodes: List of NUMA node IDs used
            - cores_per_node: List of cores allocated per node
            - cpuset_cpus: CPU pinning string (e.g., "32-63,64-95")
            - cpuset_mems: NUMA memory binding string (e.g., "1,2")
            - tensor_parallel: TP value (1, 2, 4, or 8)
            - omp_num_threads: Threads per TP instance
            - omp_threads_bind: OMP binding string or None

    Raises:
        AnsibleFilterError: If allocation impossible or TP invalid

    Examples:
        64 cores on 3-node system → TP=2, 32 cores from 2 nodes
        96 cores on 6-node system → TP=4, 24 cores from 4 nodes
    """
    # Validate input
    if not isinstance(numa_topology, dict):
        raise AnsibleFilterError("numa_topology must be a dictionary")

    if not isinstance(requested_cores, int) or requested_cores <= 0:
        raise AnsibleFilterError(f"requested_cores must be positive integer, got {requested_cores}")

    # Validate requested_tp if provided
    if requested_tp is not None:
        # Handle Ansible's omit type - treat as None for auto-calculation
        if str(type(requested_tp).__name__) == '_OmitType':
            requested_tp = None
        else:
            try:
                requested_tp = int(requested_tp)
            except (ValueError, TypeError) as e:
                raise AnsibleFilterError(
                    f"Invalid tensor_parallel type: {type(requested_tp)}. Expected integer. Error: {e}"
                )

            if requested_tp not in VALID_TP_VALUES:
                raise AnsibleFilterError(
                    f"Invalid tensor_parallel: {requested_tp}. Valid values: {VALID_TP_VALUES}"
                )

    # Extract nodes and policy
    nodes = numa_topology.get('nodes', [])
    allocation_policy = numa_topology.get('allocation_policy', {})
    housekeeping_policy = allocation_policy.get('housekeeping', {})
    housekeeping_node = housekeeping_policy.get('reserved_node', 0)

    # Determine available nodes (exclude housekeeping if strategy is reserve_node)
    housekeeping_strategy = housekeeping_policy.get('strategy', 'reserve_node')

    if housekeeping_strategy == 'reserve_node' and len(nodes) >= 3:
        # Reserve entire node 0 for housekeeping (3+ node systems)
        available_nodes = [n for n in nodes if n['id'] != housekeeping_node]
    else:
        # Use all nodes (2-node or single-node systems)
        available_nodes = nodes

    if not available_nodes:
        raise AnsibleFilterError("No available NUMA nodes for workload allocation")

    # If user provided TP, use it; otherwise auto-calculate
    if requested_tp is not None:
        result = allocate_with_fixed_tp(available_nodes, requested_cores, requested_tp)
    else:
        result = allocate_with_auto_tp(available_nodes, requested_cores)

    return result


def allocate_with_auto_tp(available_nodes, requested_cores):
    """
    Auto-calculate optimal TP and allocate cores across NUMA nodes.

    Tries TP values in ascending order (1, 2, 4, 8) to minimize cross-NUMA
    traffic. Returns first valid configuration found.

    Args:
        available_nodes: List of available NUMA node dicts
        requested_cores: Total cores to allocate

    Returns:
        dict: Allocation configuration

    Raises:
        AnsibleFilterError: If no valid allocation possible
    """
    if not available_nodes:
        raise AnsibleFilterError("No available NUMA nodes")

    max_cores_per_node = max(n['physical_cores'] for n in available_nodes)
    num_available_nodes = len(available_nodes)

    # Try each TP value in ascending order
    for tp in VALID_TP_VALUES:
        # Skip if we don't have enough nodes
        if tp > num_available_nodes:
            continue

        # Skip if cores don't divide evenly
        if requested_cores % tp != 0:
            continue

        cores_per_node = requested_cores // tp

        # Check if each node can provide this many cores
        if cores_per_node <= max_cores_per_node:
            # Valid configuration found
            selected_nodes = available_nodes[:tp]
            return build_allocation(selected_nodes, cores_per_node, tp)

    # No valid allocation found - generate helpful error
    valid_allocations = calculate_valid_allocations(available_nodes)
    total_available = sum(n['physical_cores'] for n in available_nodes)

    raise AnsibleFilterError(
        f"Cannot allocate {requested_cores} cores with valid TP values.\n"
        f"Available: {total_available} cores across {num_available_nodes} NUMA nodes.\n"
        f"Valid allocations: {valid_allocations}"
    )


def allocate_with_fixed_tp(available_nodes, requested_cores, tp):
    """
    Allocate cores with user-specified TP value.

    Args:
        available_nodes: List of available NUMA node dicts
        requested_cores: Total cores to allocate
        tp: User-specified tensor parallelism

    Returns:
        dict: Allocation configuration

    Raises:
        AnsibleFilterError: If allocation not possible with specified TP
    """
    max_cores_per_node = max(n['physical_cores'] for n in available_nodes)
    num_available_nodes = len(available_nodes)

    # Validate enough nodes
    if tp > num_available_nodes:
        raise AnsibleFilterError(
            f"Cannot use TP={tp} with only {num_available_nodes} available NUMA nodes"
        )

    # Validate even distribution
    if requested_cores % tp != 0:
        raise AnsibleFilterError(
            f"Cannot allocate {requested_cores} cores with TP={tp} (not evenly divisible)"
        )

    cores_per_node = requested_cores // tp

    # Validate node capacity
    if cores_per_node > max_cores_per_node:
        raise AnsibleFilterError(
            f"Cannot allocate {cores_per_node} cores per node (max {max_cores_per_node} per node)"
        )

    # Build allocation
    selected_nodes = available_nodes[:tp]
    return build_allocation(selected_nodes, cores_per_node, tp)


def build_allocation(selected_nodes, cores_per_node, tp):
    """
    Build final allocation configuration with CPU pinning and OMP binding.

    Args:
        selected_nodes: List of NUMA node dicts to use
        cores_per_node: Cores to allocate from each node
        tp: Tensor parallelism value

    Returns:
        dict: Complete allocation configuration
    """
    cpuset_cpus_parts = []
    omp_bind_parts = []
    cpuset_mems_parts = []

    for node in selected_nodes:
        # Get physical CPU list for this node
        physical_cpus_str = node.get('physical_cpus_list', '')
        if not physical_cpus_str:
            physical_cpus_str = node.get('physical_cpus', '')

        physical_cpus_list = physical_cpus_str.split(',')

        # Take first N physical cores
        allocated_cpus = [int(cpu.strip()) for cpu in physical_cpus_list[:cores_per_node]]

        # Convert to range format
        cpu_range = cpu_list_to_range(allocated_cpus)

        cpuset_cpus_parts.append(cpu_range)
        omp_bind_parts.append(cpu_range)
        cpuset_mems_parts.append(str(node['id']))

    return {
        'allocated_nodes': [n['id'] for n in selected_nodes],
        'cores_per_node': [cores_per_node] * len(selected_nodes),
        'cpuset_cpus': ','.join(cpuset_cpus_parts),
        'cpuset_mems': ','.join(cpuset_mems_parts),
        'tensor_parallel': tp,
        'omp_num_threads': cores_per_node,
        'omp_threads_bind': '|'.join(omp_bind_parts) if tp > 1 else None,
        'allocation_strategy': f"multi_numa_tp{tp}" if tp > 1 else "single_numa"
    }


def calculate_valid_allocations(available_nodes):
    """
    Calculate and format valid core/TP combinations for error messages.

    Args:
        available_nodes: List of available NUMA node dicts

    Returns:
        str: Formatted list of valid allocations (e.g., "32 cores (TP=1), 64 cores (TP=2)")
    """
    if not available_nodes:
        return "none"

    max_cores = max(n['physical_cores'] for n in available_nodes)
    num_nodes = len(available_nodes)
    total_cores = sum(n['physical_cores'] for n in available_nodes)

    valid = []
    seen_core_counts = set()

    for tp in VALID_TP_VALUES:
        if tp > num_nodes:
            break

        # Calculate possible core counts for this TP
        for cores_per_node in range(1, max_cores + 1):
            total = cores_per_node * tp
            if total <= total_cores and total not in seen_core_counts:
                valid.append(f"{total} cores (TP={tp})")
                seen_core_counts.add(total)

    # Sort by total cores and limit to first 10 suggestions
    valid_sorted = sorted(valid, key=lambda x: int(x.split()[0]))
    return ', '.join(valid_sorted[:10])


class FilterModule:
    """Ansible filter plugin registration."""

    def filters(self):
        return {
            'cpu_list_to_range': cpu_list_to_range,
            'extract_primary_cpus': extract_primary_cpus,
            'extract_all_cpus': extract_all_cpus,
            'extract_numa_nodes': extract_numa_nodes,
            'merge_cpu_ranges': merge_cpu_ranges,
            'extract_size_value': extract_size_value,
            'allocate_cores_multi_numa': allocate_cores_multi_numa,
        }
