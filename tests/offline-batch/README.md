# Offline Batch Test Scenarios

This directory contains **test scenario specifications** for offline batch benchmarking with vLLM. These YAML files document the test scenarios, expected configurations, and metrics we want to capture.

## Purpose

These files serve as:
1. **Documentation** of test scenarios and their configurations
2. **Specification** for what metrics to capture
3. **Reference** for implementing tests in the actual test suite
4. **Future framework** - potential declarative test runner configuration

## Test Scenarios

### 1. Document Summarization (`document-summarization.yaml`)

Real-world use case: Processing large batches of documents for summarization (support tickets, articles, reports).

**Key Parameters:**
- Batch sizes: 100-1000 documents
- Input: 512-1024 tokens (typical document length)
- Output: 128-256 tokens (summary length)
- Focus: Throughput optimization for production workloads

**Current Implementation:**
```bash
# Via run-offline-batch-suite.sh
./run-offline-batch-suite.sh run_test all sonnet 1000 16
```

### 2. Batch Size Scaling (`batch-size-scaling.yaml`)

Performance characterization: Find optimal batch size for throughput vs memory tradeoff.

**Key Parameters:**
- Batch sizes: 1, 10, 25, 50, 100, 250, 500, 1000
- Fixed input/output: 512→256 tokens
- Focus: Identify sweet spot for batch processing

**Current Implementation:**
```bash
# Via run-offline-batch-suite.sh
./run-offline-batch-suite.sh batch-scaling <model> 16
```

### 3. Input/Output Variation (`input-output-variation.yaml`)

Understanding how token lengths affect performance.

**Key Parameters:**
- Input lengths: 128, 256, 512, 1024, 2048 tokens
- Output lengths: 64, 128, 256, 512, 1024 tokens
- Focus: Characterize prefill vs decode performance

**Current Implementation:**
```bash
# Via run-offline-batch-suite.sh
./run-offline-batch-suite.sh input-scaling <model> 16
./run-offline-batch-suite.sh output-scaling <model> 16
```

## Relationship to Implementation

The actual test implementation uses:

**Ansible Playbook:**
- `automation/test-execution/ansible/llm-benchmark-offline-batch.yml`
- Takes parameters: model, dataset, num_prompts, cores, input_len, output_len
- Runs `vllm bench throughput` command
- Collects metrics and saves results

**Bash Test Suite:**
- `automation/test-execution/scripts/bash/run-offline-batch-suite.sh`
- Implements the scenarios defined in these YAML files
- Provides convenient commands: `use-cases`, `batch-scaling`, `input-scaling`, etc.
- Supports multiple models and iterations

**Dashboard:**
- `dashboard-examples/vllm_dashboard/pages/4_📦_Offline_Batch.py`
- Visualizes results from tests
- Shows processing capacity, time estimates, scaling curves

## Metrics Captured

All tests capture these metrics (as specified in YAML files):

**Primary Metrics:**
- `throughput_requests_per_sec` - How many requests/second
- `throughput_tokens_per_sec` - Total tokens/second (input + output)
- `throughput_output_tokens_per_sec` - Output tokens/second
- `total_time_sec` - Total processing time
- `avg_time_per_request_sec` - Average time per request

**Detailed Metrics:**
- `prefill_throughput_tokens_per_sec` - Prefill phase speed
- `decode_throughput_tokens_per_sec` - Decode phase speed
- `max_kv_cache_usage_percent` - Peak KV cache usage
- `avg_prefix_cache_hit_rate_percent` - Prefix cache efficiency

**Efficiency Metrics:**
- `tokens_per_sec_per_core` - Resource efficiency
- `items_per_hour` - Processing capacity

## Using the YAML Specifications

While these YAML files aren't directly executed, they serve as the specification for:

1. **What scenarios to test** - The bash script implements these scenarios
2. **What metrics to capture** - The Ansible playbook extracts these metrics
3. **Success criteria** - What constitutes a valid test
4. **Expected configurations** - Standard test configurations

## Running Tests

See [README-offline-batch.md](../../automation/test-execution/scripts/bash/README-offline-batch.md) for:
- How to run the test suite
- Available commands and options
- Example workflows
- Results interpretation

## Future Work

These YAML files could be used to:
- Build a declarative test runner that directly reads these configs
- Auto-generate Ansible tasks from YAML specifications
- Validate test results against specified success criteria
- Generate test reports with expected vs actual metrics
