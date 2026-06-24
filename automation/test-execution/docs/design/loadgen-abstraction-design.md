# Load Generator Abstraction Design

## Goal

Support multiple load generator tools (GuideLLM, MLPerf, MTEB, etc.) with a consistent interface, similar to the backend abstraction for inference engines.

## Current State

**Current Load Generator:** GuideLLM only
- Hardcoded in Ansible roles (`benchmark_guidellm`, `benchmark_embedding`)
- CLI commands specific to GuideLLM
- Metrics parsing specific to GuideLLM JSON format
- Workload configuration tied to GuideLLM

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Benchmark Orchestration Layer                  │
│         (Ansible playbooks - loadgen-agnostic)              │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┴──────────────┐
         │  LoadGen Interface       │
         │  (Abstract Class)        │
         └───────────┬──────────────┘
                     │
      ┌──────────────┼──────────────┬──────────────┐
      │              │              │              │
┌─────▼─────┐  ┌────▼────┐  ┌──────▼──────┐  ┌───▼────┐
│ GuideLLM  │  │ MLPerf  │  │    MTEB     │  │ Custom │
│  LoadGen  │  │ LoadGen │  │  LoadGen    │  │LoadGen │
└───────────┘  └─────────┘  └─────────────┘  └────────┘
     │              │              │
     │              │              │
┌────▼──────────────▼──────────────▼───────────────┐
│          Inference Backend Layer                 │
│     (vLLM, TGI, llama.cpp - already abstracted)  │
└──────────────────────────────────────────────────┘
```

## Design

### 1. LoadGen Abstraction Layer

**Location:** `automation/test-execution/shared/loadgens/`

```
shared/loadgens/
├── __init__.py          # Registry and factory
├── base.py              # Abstract base class
├── guidellm_loadgen.py  # GuideLLM implementation
├── mlperf_loadgen.py    # MLPerf implementation (future)
├── mteb_loadgen.py      # MTEB implementation (future)
├── cli.py               # CLI for Ansible integration
├── __main__.py          # Make package executable
├── tests/
│   ├── test_guidellm.py
│   ├── test_mlperf.py
│   └── test_mteb.py
└── README.md
```

### 2. Base Interface

```python
# shared/loadgens/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

class WorkloadType(Enum):
    """Standard workload types across all load generators."""
    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"
    RETRIEVAL = "retrieval"

@dataclass
class LoadGenConfig:
    """Configuration for load generator."""
    endpoint_url: str
    workload_type: WorkloadType
    
    # Common parameters
    requests: Optional[int] = None
    duration: Optional[int] = None
    rate: Optional[int] = None
    max_concurrency: Optional[int] = None
    
    # Workload-specific
    input_length: Optional[int] = None
    output_length: Optional[int] = None
    dataset: Optional[str] = None
    
    # Extra args specific to load generator
    extra_args: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LoadGenMetrics:
    """Standardized metrics across all load generators."""
    # Latency metrics (milliseconds)
    ttft_mean: float
    ttft_p50: float
    ttft_p95: float
    ttft_p99: float
    
    tpot_mean: float
    tpot_p50: float
    tpot_p95: float
    tpot_p99: float
    
    e2e_mean: float
    e2e_p50: float
    e2e_p95: float
    e2e_p99: float
    
    # Throughput metrics
    requests_per_second: float
    tokens_per_second: float
    
    # Success metrics
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    
    # Task-specific metrics (optional)
    accuracy: Optional[float] = None  # For MTEB
    recall_at_k: Optional[Dict[int, float]] = None  # For retrieval
    
    # Raw metrics for downstream processing
    raw_metrics: Dict[str, Any] = field(default_factory=dict)

class LoadGenerator(ABC):
    """Abstract base class for load generators."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Load generator name (e.g., 'guidellm', 'mlperf')."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Load generator version."""
        pass
    
    @abstractmethod
    def get_run_command(self, config: LoadGenConfig) -> List[str]:
        """Generate command-line arguments to run the load generator.
        
        Args:
            config: Load generator configuration
            
        Returns:
            List of command arguments (e.g., ['--url', 'http://...', '--requests', '100'])
        """
        pass
    
    @abstractmethod
    def parse_metrics(self, results_file: str) -> LoadGenMetrics:
        """Parse load generator results file to standard metrics.
        
        Args:
            results_file: Path to results file (JSON, CSV, etc.)
            
        Returns:
            LoadGenMetrics with standardized fields
        """
        pass
    
    @abstractmethod
    def supports_workload(self, workload_type: WorkloadType) -> bool:
        """Check if load generator supports this workload type.
        
        Args:
            workload_type: Workload type to check
            
        Returns:
            True if supported, False otherwise
        """
        pass
    
    def get_container_image(self) -> str:
        """Get container image for this load generator.
        
        Returns:
            Container image URL (optional, can run natively)
        """
        return ""
    
    def get_install_command(self) -> List[str]:
        """Get command to install load generator.
        
        Returns:
            List of install commands (e.g., ['pip', 'install', 'guidellm'])
        """
        return []
```

### 3. GuideLLM Implementation

```python
# shared/loadgens/guidellm_loadgen.py

from typing import List, Dict, Any
from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics, WorkloadType
import json

class GuideLLMLoadGen(LoadGenerator):
    """GuideLLM load generator implementation."""
    
    @property
    def name(self) -> str:
        return "guidellm"
    
    @property
    def version(self) -> str:
        return "0.3.0"  # Current GuideLLM version
    
    def get_run_command(self, config: LoadGenConfig) -> List[str]:
        """Generate GuideLLM CLI arguments."""
        cmd = [
            "--target", config.endpoint_url,
        ]
        
        # Backend type mapping
        backend_map = {
            WorkloadType.CHAT: "openai-chat",
            WorkloadType.COMPLETION: "openai-completions",
            WorkloadType.EMBEDDING: "openai-embeddings",
        }
        if config.workload_type in backend_map:
            cmd.extend(["--backend", backend_map[config.workload_type]])
        
        # Request parameters
        if config.requests:
            cmd.extend(["--requests", str(config.requests)])
        if config.duration:
            cmd.extend(["--max-seconds", str(config.duration)])
        if config.rate:
            cmd.extend(["--rate", str(config.rate)])
        if config.max_concurrency:
            cmd.extend(["--max-concurrency", str(config.max_concurrency)])
        
        # Workload parameters
        if config.input_length:
            cmd.extend(["--prompt-tokens", str(config.input_length)])
        if config.output_length:
            cmd.extend(["--output-tokens", str(config.output_length)])
        
        # Extra args
        for key, value in config.extra_args.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])
        
        return cmd
    
    def parse_metrics(self, results_file: str) -> LoadGenMetrics:
        """Parse GuideLLM JSON results."""
        with open(results_file) as f:
            data = json.load(f)
        
        # Extract benchmarks array
        benchmarks = data.get("benchmarks", [])
        if not benchmarks:
            raise ValueError("No benchmarks found in results")
        
        bench = benchmarks[0]  # Use first benchmark
        stats = bench.get("result", {}).get("stats", {})
        
        return LoadGenMetrics(
            ttft_mean=stats.get("ttft_per_token_stats", {}).get("mean", 0) * 1000,
            ttft_p50=stats.get("ttft_per_token_stats", {}).get("p50", 0) * 1000,
            ttft_p95=stats.get("ttft_per_token_stats", {}).get("p95", 0) * 1000,
            ttft_p99=stats.get("ttft_per_token_stats", {}).get("p99", 0) * 1000,
            
            tpot_mean=stats.get("tpot_per_token_stats", {}).get("mean", 0) * 1000,
            tpot_p50=stats.get("tpot_per_token_stats", {}).get("p50", 0) * 1000,
            tpot_p95=stats.get("tpot_per_token_stats", {}).get("p95", 0) * 1000,
            tpot_p99=stats.get("tpot_per_token_stats", {}).get("p99", 0) * 1000,
            
            e2e_mean=stats.get("end_to_end_latency_stats", {}).get("mean", 0) * 1000,
            e2e_p50=stats.get("end_to_end_latency_stats", {}).get("p50", 0) * 1000,
            e2e_p95=stats.get("end_to_end_latency_stats", {}).get("p95", 0) * 1000,
            e2e_p99=stats.get("end_to_end_latency_stats", {}).get("p99", 0) * 1000,
            
            requests_per_second=stats.get("request_throughput_mean", 0),
            tokens_per_second=stats.get("token_throughput_mean", 0),
            
            total_requests=stats.get("num_requests", 0),
            successful_requests=stats.get("num_requests", 0),  # GuideLLM doesn't track failures separately
            failed_requests=0,
            success_rate=100.0,
            
            raw_metrics=data,
        )
    
    def supports_workload(self, workload_type: WorkloadType) -> bool:
        """GuideLLM supports chat, completion, and embedding."""
        return workload_type in [
            WorkloadType.CHAT,
            WorkloadType.COMPLETION,
            WorkloadType.EMBEDDING,
        ]
    
    def get_install_command(self) -> List[str]:
        return ["pip", "install", "guidellm"]
```

### 4. MTEB Implementation (Future)

```python
# shared/loadgens/mteb_loadgen.py

from typing import List, Dict, Any
from .base import LoadGenerator, LoadGenConfig, LoadGenMetrics, WorkloadType
import json

class MTEBLoadGen(LoadGenerator):
    """MTEB (Massive Text Embedding Benchmark) load generator."""
    
    @property
    def name(self) -> str:
        return "mteb"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    def get_run_command(self, config: LoadGenConfig) -> List[str]:
        """Generate MTEB CLI arguments."""
        cmd = [
            "--endpoint", config.endpoint_url,
            "--task", config.extra_args.get("task", "classification"),
            "--dataset", config.dataset or "mteb/banking77",
        ]
        
        # MTEB-specific args
        if "batch_size" in config.extra_args:
            cmd.extend(["--batch-size", str(config.extra_args["batch_size"])])
        
        return cmd
    
    def parse_metrics(self, results_file: str) -> LoadGenMetrics:
        """Parse MTEB JSON results."""
        with open(results_file) as f:
            data = json.load(f)
        
        # MTEB returns accuracy/recall metrics, not latency
        # We'll populate what we can
        return LoadGenMetrics(
            ttft_mean=0,  # Not applicable to MTEB
            ttft_p50=0,
            ttft_p95=0,
            ttft_p99=0,
            tpot_mean=0,
            tpot_p50=0,
            tpot_p95=0,
            tpot_p99=0,
            e2e_mean=data.get("avg_latency_ms", 0),
            e2e_p50=0,
            e2e_p95=0,
            e2e_p99=0,
            requests_per_second=data.get("throughput", 0),
            tokens_per_second=0,
            total_requests=data.get("total_samples", 0),
            successful_requests=data.get("total_samples", 0),
            failed_requests=0,
            success_rate=100.0,
            accuracy=data.get("accuracy", 0),
            recall_at_k=data.get("recall_at_k", {}),
            raw_metrics=data,
        )
    
    def supports_workload(self, workload_type: WorkloadType) -> bool:
        """MTEB supports embedding, classification, and retrieval."""
        return workload_type in [
            WorkloadType.EMBEDDING,
            WorkloadType.CLASSIFICATION,
            WorkloadType.RETRIEVAL,
        ]
    
    def get_install_command(self) -> List[str]:
        return ["pip", "install", "mteb"]
```

### 5. Registry and Factory

```python
# shared/loadgens/__init__.py

from typing import Dict, Type
from .base import LoadGenerator
from .guidellm_loadgen import GuideLLMLoadGen

LOADGENS: Dict[str, Type[LoadGenerator]] = {
    "guidellm": GuideLLMLoadGen,
    # "mlperf": MLPerfLoadGen,  # Future
    # "mteb": MTEBLoadGen,      # Future
}

def get_loadgen(name: str) -> LoadGenerator:
    """Get load generator by name."""
    if name not in LOADGENS:
        available = ", ".join(LOADGENS.keys())
        raise ValueError(f"Unknown load generator: {name}. Available: {available}")
    return LOADGENS[name]()

def list_loadgens() -> list:
    """List available load generators."""
    return list(LOADGENS.keys())
```

### 6. CLI for Ansible Integration

```python
# shared/loadgens/cli.py

import sys
import json
import argparse
from . import get_loadgen, list_loadgens
from .base import LoadGenConfig, WorkloadType

def cmd_list():
    """List all available load generators."""
    loadgens = list_loadgens()
    print(json.dumps(loadgens, indent=2))

def cmd_get_loadgen(name: str):
    """Get load generator information."""
    loadgen = get_loadgen(name)
    info = {
        "name": loadgen.name,
        "version": loadgen.version,
        "install_command": loadgen.get_install_command(),
        "container_image": loadgen.get_container_image(),
        "supported_workloads": [
            wt.value for wt in WorkloadType
            if loadgen.supports_workload(wt)
        ],
    }
    print(json.dumps(info, indent=2))

def cmd_get_command(
    name: str,
    endpoint_url: str,
    workload_type: str,
    requests: int = None,
    duration: int = None,
    rate: int = None,
    input_length: int = None,
    output_length: int = None,
    extra_args: str = None,
):
    """Get run command for load generator."""
    loadgen = get_loadgen(name)
    
    extra = {}
    if extra_args:
        extra = json.loads(extra_args)
    
    config = LoadGenConfig(
        endpoint_url=endpoint_url,
        workload_type=WorkloadType(workload_type),
        requests=requests,
        duration=duration,
        rate=rate,
        input_length=input_length,
        output_length=output_length,
        extra_args=extra,
    )
    
    cmd = loadgen.get_run_command(config)
    
    result = {
        "command": cmd,
        "install_command": loadgen.get_install_command(),
    }
    print(json.dumps(result, indent=2))

def main():
    parser = argparse.ArgumentParser(description="Load generator abstraction CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    subparsers.add_parser("list", help="List available load generators")
    
    parser_loadgen = subparsers.add_parser("get-loadgen", help="Get load generator info")
    parser_loadgen.add_argument("name", help="Load generator name")
    
    parser_cmd = subparsers.add_parser("get-command", help="Get run command")
    parser_cmd.add_argument("name", help="Load generator name")
    parser_cmd.add_argument("--endpoint-url", required=True)
    parser_cmd.add_argument("--workload-type", required=True)
    parser_cmd.add_argument("--requests", type=int)
    parser_cmd.add_argument("--duration", type=int)
    parser_cmd.add_argument("--rate", type=int)
    parser_cmd.add_argument("--input-length", type=int)
    parser_cmd.add_argument("--output-length", type=int)
    parser_cmd.add_argument("--extra-args")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == "list":
            cmd_list()
        elif args.command == "get-loadgen":
            cmd_get_loadgen(args.name)
        elif args.command == "get-command":
            cmd_get_command(
                args.name,
                args.endpoint_url,
                args.workload_type,
                args.requests,
                args.duration,
                args.rate,
                args.input_length,
                args.output_length,
                args.extra_args,
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Migration Strategy

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create `shared/loadgens/` structure
- [ ] Implement `base.py` with abstract classes
- [ ] Implement `guidellm_loadgen.py` (migrate existing logic)
- [ ] Add unit tests
- [ ] Create CLI tool

### Phase 2: Ansible Integration (Weeks 3-4)
- [ ] Create `loadgen-command.yml` task (similar to `backend-command.yml`)
- [ ] Refactor `benchmark_guidellm` role to use abstraction
- [ ] Refactor `benchmark_embedding` role to use abstraction
- [ ] Backward compatibility testing

### Phase 3: Additional Load Generators (Weeks 5-8)
- [ ] Implement MTEB load generator
- [ ] Implement MLPerf load generator
- [ ] Integration testing
- [ ] Documentation

## Benefits

1. **Pluggable Load Generators** - Easy to add MLPerf, MTEB, etc.
2. **Standardized Metrics** - All load generators return same format
3. **Unified Interface** - Consistent API across tools
4. **Testability** - Unit tests for each load generator
5. **Backward Compatible** - Existing GuideLLM workflows unchanged

## Example Usage

```bash
# List available load generators
python3 -m shared.loadgens list
# ["guidellm", "mteb", "mlperf"]

# Get GuideLLM info
python3 -m shared.loadgens get-loadgen guidellm
# {"name": "guidellm", "version": "0.3.0", "supported_workloads": ["chat", "completion", "embedding"]}

# Generate GuideLLM command
python3 -m shared.loadgens get-command guidellm \
  --endpoint-url http://localhost:8000/v1 \
  --workload-type chat \
  --requests 100 \
  --input-length 512 \
  --output-length 512
# {"command": ["--target", "http://...", "--backend", "openai-chat", ...]}

# Generate MTEB command
python3 -m shared.loadgens get-command mteb \
  --endpoint-url http://localhost:8000/embeddings \
  --workload-type classification \
  --extra-args '{"task": "banking77", "batch_size": 32}'
# {"command": ["--endpoint", "http://...", "--task", "classification", ...]}
```

## Ansible Integration

```yaml
- name: Generate load generator command
  ansible.builtin.include_role:
    name: loadgen
    tasks_from: loadgen-command
  vars:
    loadgen_name: "{{ loadgen | default('guidellm') }}"
    loadgen_config:
      endpoint_url: "http://{{ vllm_host }}:{{ vllm_port }}/v1"
      workload_type: "chat"
      requests: 100
      input_length: 512
      output_length: 512

- name: Run load generator
  ansible.builtin.command:
    cmd: "guidellm {{ loadgen_cmd }}"
  register: loadgen_result
```

## Future Enhancements

1. **Distributed Load Generation** - Support for multi-node load generation
2. **Real-time Metrics** - Stream metrics during test execution
3. **Adaptive Rate Control** - Automatically adjust rate based on latency
4. **Dataset Integration** - Built-in support for common datasets
5. **Comparison Reports** - Side-by-side comparison of load generators

## Compatibility Matrix

| Load Generator | Chat | Completion | Embedding | Classification | Retrieval |
|---------------|------|------------|-----------|----------------|-----------|
| GuideLLM      | ✓    | ✓          | ✓         | ✗              | ✗         |
| MTEB          | ✗    | ✗          | ✓         | ✓              | ✓         |
| MLPerf        | ✓    | ✓          | ✗         | ✗              | ✗         |

## Notes

- Similar architecture to backend abstraction (proven pattern)
- Graceful fallback to hardcoded GuideLLM if abstraction unavailable
- CLI integration for Ansible compatibility
- Standard metrics across all load generators
- Load generator-specific metrics in `raw_metrics` field
