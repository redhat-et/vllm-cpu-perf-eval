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
        }
