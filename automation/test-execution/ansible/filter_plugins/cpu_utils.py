#!/usr/bin/env python3
"""
Custom Jinja2 filters for CPU topology manipulation in Ansible.
Replaces awk/shell scripts with native Python for better maintainability.
"""

import re
from dataclasses import dataclass
from collections import defaultdict
from typing import List, Set, Dict, Optional, Union, Sequence
try:
    from ansible.errors import AnsibleFilterError
except ImportError:
    # Fallback for testing without Ansible installed
    class AnsibleFilterError(Exception):
        """Fallback exception class for filter errors."""
        pass

_SIZE_PATTERN = re.compile(r'^(\d+(?:\.\d+)?)\s*([A-Za-z]+)?$')

@dataclass(frozen=True)
class CpuInfo:
    """Represents CPU topology information."""
    cpu: int
    node: int
    core: int

class LscpuParseError(AnsibleFilterError):
    """Raised when lscpu data cannot be parsed."""
    pass

class LscpuParser:
    """
    Parser for lscpu -e=CPU,NODE,CORE output.
    
    Parses once and provides efficient queries for CPU topology.
    """
    
    def __init__(self, lscpu_data: str):
        """
        Initialize parser with lscpu output data.
        
        Args:
            lscpu_data: String output from lscpu -e=CPU,NODE,CORE
        
        Raises:
            LscpuParseError: If data format is invalid
        """
        if not isinstance(lscpu_data, str):
            raise LscpuParseError(
                f"Expected string input, got {type(lscpu_data).__name__}"
            )

        self.__cpu_entries: List[CpuInfo] = []
        @property
        def cpu_entries(self) -> Sequence[CpuInfo]:
            return tuple(self.__cpu_entries)

        self._cpu_entries: List[CpuInfo] = []
        self._numa_nodes: Set[int] = set()
        self._node_to_cpus: Dict[int, List[int]] = defaultdict(list)
        self._node_core_to_min_cpu: Dict[int, Dict[int, int]] = defaultdict(dict)
        
        self._parse(lscpu_data)
    
    def _parse(self, lscpu_data: str) -> None:
        """Parse lscpu data and build indices."""
        if not lscpu_data.strip():
            return
        
        for line_num, line in enumerate(lscpu_data.strip().split('\n'), 1):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) < 3:
                raise LscpuParseError(
                    f"Line {line_num}: Expected 3 columns (CPU NODE CORE), "
                    f"got {len(parts)}: '{line}'"
                )
            
            try:
                cpu = int(parts[0])
                node = int(parts[1])
                core = int(parts[2])
            except ValueError as e:
                raise LscpuParseError(
                    f"Line {line_num}: Invalid numeric value in '{line}': {e}"
                )
            
            entry = CpuInfo(cpu=cpu, node=node, core=core)
            self._cpu_entries.append(entry)
           
            self._node_to_cpus[node].append(cpu)
            
            # Index by NUMA node and core for primary CPU tracking
            if node not in self._node_core_to_min_cpu:
                self._node_core_to_min_cpu[node] = {}
            
            core_dict = self._node_core_to_min_cpu[node]
            if core not in core_dict or cpu < core_dict[core]:
                core_dict[core] = cpu
            
            self._numa_nodes.add(node)
    
    def get_primary_cpus(self, numa_node: int) -> List[int]:
        """
        Get primary CPUs (first thread per core) for a NUMA node.
        
        Args:
            numa_node: NUMA node number
        
        Returns:
            Sorted list of primary CPU IDs
        """
        if numa_node not in self._node_core_to_min_cpu:
            return []
        
        return sorted(self._node_core_to_min_cpu[numa_node].values())
    
    def get_all_cpus(self, numa_node: int) -> List[int]:
        """
        Get all CPUs for a NUMA node.
        
        Args:
            numa_node: NUMA node number
        
        Returns:
            Sorted list of all CPU IDs
        """
        cpus = self._node_to_cpus.get(numa_node, [])
        return sorted(cpus)
    
    def get_numa_nodes(self) -> List[int]:
        """
        Get all unique NUMA node numbers.
        
        Returns:
            Sorted list of NUMA node numbers
        """
        return sorted(self._numa_nodes)
    
    def is_empty(self) -> bool:
        """Check if parser contains no data."""
        return len(self._cpu_entries) == 0

def cpu_list_to_range(cpu_list: Union[List[int], str]) -> str:
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
        try:
            cpu_list = [
                int(x.strip()) 
                for x in cpu_list.split(',') 
                if x.strip()
            ]
        except ValueError as e:
            raise AnsibleFilterError(
                f"Invalid CPU ID in string '{cpu_list}': {e}"
            )

    if not isinstance(cpu_list, list):
        raise AnsibleFilterError(
            f"cpu_list_to_range expects list or string, got {type(cpu_list).__name__}"
        )

    if not cpu_list:
        return ""
    # Convert to sorted list of unique integers
    try:
        cpus = sorted(set(int(cpu) for cpu in cpu_list))
    except (ValueError, TypeError) as e:
        raise AnsibleFilterError(
            f"Invalid CPU list format - expected integers: {e}"
        )

    if not cpus:
        return ""
    # Build ranges
    ranges = []
    start = cpus[0]
    prev = cpus[0]
    for cpu in cpus[1:]:
        if cpu == prev + 1:
            prev = cpu
        else:
            ranges.append(_format_range(start, prev))
            start = cpu
            prev = cpu
    # Add final range
    ranges.append(_format_range(start, prev))
    return ','.join(ranges)

def _format_range(start: int, end: int) -> str:
    """Format a single CPU range."""
    return str(start) if start == end else f"{start}-{end}"

def extract_primary_cpus(lscpu_data: str, numa_node: Union[int, str]) -> str:
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
    
    try:
        numa_node_int = int(numa_node)
    except (ValueError, TypeError) as e:
        raise AnsibleFilterError(
            f"Invalid NUMA node '{numa_node}': expected integer, got error: {e}"
        )
    
    try:
        parser = LscpuParser(lscpu_data)
        primary_cpus = parser.get_primary_cpus(numa_node_int)
        return ','.join(str(cpu) for cpu in primary_cpus)
    except LscpuParseError as e:
        raise AnsibleFilterError(f"Failed to parse lscpu data: {e}")

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
    
    try:
        numa_node_int = int(numa_node)
    except (ValueError, TypeError) as e:
        raise AnsibleFilterError(
            f"Invalid NUMA node '{numa_node}': expected integer, got error: {e}"
        )
    
    try:
        parser = LscpuParser(lscpu_data)
        cpus = parser.get_all_cpus(numa_node_int)
        return ','.join(str(cpu) for cpu in cpus)
    except LscpuParseError as e:
        raise AnsibleFilterError(f"Failed to parse lscpu data: {e}")

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
    
    try:
        parser = LscpuParser(lscpu_data)
        nodes = parser.get_numa_nodes()
        return [str(n) for n in nodes]
    except LscpuParseError as e:
        raise AnsibleFilterError(f"Failed to parse lscpu data: {e}")

def merge_cpu_ranges(range_list: List[str]) -> str:
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
    for idx, cpu_range in enumerate(range_list):
        if not cpu_range or not isinstance(cpu_range, str):
            continue
        for part in cpu_range.split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                try:
                    start, end = part.split('-', 1)
                    start_int = int(start)
                    end_int = int(end)
                    if end_int < start_int:
                        raise AnsibleFilterError(
                            f"Invalid range at index {idx}: '{part}' - "
                            f"end ({end_int}) is less than start ({start_int})"
                        )
                    all_cpus.extend(range(start_int, end_int + 1))
                except ValueError as e:
                    if "Invalid range" in str(e):
                        raise
                    raise AnsibleFilterError(
                        f"Invalid CPU range format at index {idx}: '{part}' - {e}"
                    )
            else:
                try:
                    all_cpus.append(int(part))
                except ValueError as e:
                    raise AnsibleFilterError(
                        f"Invalid CPU number at index {idx}: '{part}' - {e}"
                    )
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
            f"extract_size_value expects string or number, got {type(size_str).__name__}"
        )

    size_str = size_str.strip()
    
    if not size_str:
        raise AnsibleFilterError(
            "extract_size_value received empty string"
        )
    
    # Try to parse the number and unit
    match = _SIZE_PATTERN.match(size_str)
    if match:
        value = match.group(1)
        # Return as int if no decimal, otherwise float
        return float(value) if '.' in value else int(value)
    # Try parsing as plain number
    try:
        value_float = float(size_str)
        return int(value_float) if value_float.is_integer() else value_float
    except ValueError:
        raise AnsibleFilterError(
            f"Invalid size format: '{size_str}'. Expected: '40GiB', '1024', etc."
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
