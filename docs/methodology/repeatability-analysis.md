---
layout: default
title: Repeatability Analysis
---

## Benchmark Repeatability Analysis

## Overview

The `analyze_repeatability.py` script analyzes benchmark consistency across multiple runs using the Coefficient of Variation (CV) metric. It helps you understand how repeatable your benchmark results are and identify which configurations provide the most stable measurements.

## Quick Start

```bash
# Analyze all results and generate a markdown report
./analyze_repeatability.py ../../../results/llm -o repeatability_report.md

# Generate both markdown and JSON reports
./analyze_repeatability.py ../../../results/llm -o report.md -j report.json

# Analyze specific model with verbose output
./analyze_repeatability.py ../../../results/llm/meta-llama/Llama-3.2-1B-Instruct -o llama_report.md -v
```

## What It Does

The script:

1. **Scans** your results directory for all benchmark runs
2. **Groups** runs by configuration (platform, model, workload, cores, tensor parallelism, concurrency)
3. **Calculates** statistics for each metric:
   - Mean value across runs
   - Standard deviation
   - Coefficient of Variation (CV %)
   - Repeatability grade
4. **Generates** comprehensive reports with:
   - Detailed CV tables for each configuration
   - Overall repeatability rankings
   - Letter grades (A+ to C)

## Coefficient of Variation (CV)

CV is calculated as:

```
CV = (Standard Deviation / Mean) × 100%
```

### Interpretation

| CV Range | Grade | Meaning |
|----------|-------|---------|
| CV < 1% | Excellent | Highly repeatable, ideal for regression testing |
| CV 1-3% | Good | Repeatable, suitable for performance comparisons |
| CV 3-5% | Acceptable | Moderate variance, acceptable for most use cases |
| CV > 5% | Poor | High variance, results may not be reliable |

### Letter Grades

Overall configuration grades based on average CV:

- **A+**: CV < 0.5% - Exceptional repeatability
- **A**: CV < 1.0% - Excellent repeatability
- **A-**: CV < 2.0% - Very good repeatability
- **B+**: CV < 3.0% - Good repeatability
- **B**: CV < 5.0% - Acceptable repeatability
- **B-**: CV < 7.5% - Below average repeatability
- **C**: CV ≥ 7.5% - Poor repeatability

## Metrics Analyzed

The script analyzes the following metrics:

1. **Request Latency** (Mean, P90, P95)
   - End-to-end request completion time
   - Unit: seconds (s)

2. **Time to First Token (TTFT)** (Mean, P90, P95)
   - Time until first token is generated
   - Unit: milliseconds (ms)

3. **Time per Output Token (TPoT)** (Mean, P90, P95)
   - Inter-token latency
   - Unit: milliseconds (ms)

4. **Output Throughput** (Mean only)
   - Tokens generated per second
   - Unit: tokens/s (tok/s)

## Requirements

### Multiple Runs Required

The script requires **at least 2 runs** of the same configuration to calculate CV. A configuration is defined by:

- Platform (e.g., "Intel SPR")
- Model (e.g., "meta-llama/Llama-3.2-1B-Instruct")
- Workload (e.g., "chat")
- Core count (e.g., 16)
- Tensor parallelism (e.g., 1)
- vLLM version (e.g., "v0.6.3")
- Concurrency level (e.g., 8)

### Running Multiple Tests

To collect data for repeatability analysis, run the same benchmark multiple times:

```bash
# Run the same test 3 times for repeatability analysis
for i in {1..3}; do
  ansible-playbook llm-benchmark-auto.yml \
    -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
    -e "workload_type=chat" \
    -e "requested_cores=16"

  # Optional: add small delay between runs
  sleep 60
done

# Then analyze repeatability
cd automation/test-execution/ansible/scripts
./analyze_repeatability.py ../../../results/llm -o repeatability_report.md
```

## Output Format

### Markdown Report

The markdown report includes:

1. **Overview** - Explanation of CV methodology
2. **Per-Configuration Tables** - Detailed CV analysis for each configuration
3. **Overall Rankings** - Configurations ranked by average CV

Example table:

```markdown
### Request Latency (Mean) Repeatability

| Configuration | Stat | Conc 1 | Conc 8 | Conc 16 |
|---------------|------|--------|--------|---------|
| 16-core       | Mean | 6.42s (±0.13%) | 7.74s (±0.04%) | 9.02s (±0.18%) |
| 16-core       | P90  | 6.43s (±0.12%) | 7.74s (±0.05%) | 9.02s (±0.21%) |
| 16-core       | P95  | 6.44s (±0.14%) | 7.75s (±0.04%) | 9.03s (±0.19%) |
```

### JSON Report

The JSON report provides machine-readable data for further analysis or integration with other tools:

```json
{
  "Intel_SPR_meta-llama_Llama-3.2-1B-Instruct_chat_16c_TP1_v0.6.3_conc8": {
    "platform": "Intel SPR",
    "model": "meta-llama/Llama-3.2-1B-Instruct",
    "workload": "chat",
    "cores": 16,
    "tensor_parallel": 1,
    "vllm_version": "v0.6.3",
    "concurrency": 8,
    "metrics": {
      "request_latency_mean": {
        "mean": {
          "value": 7.74,
          "std": 0.003,
          "cv": 0.04,
          "n_runs": 3,
          "grade": "Excellent"
        }
      }
    }
  }
}
```

## Use Cases

### 1. Validate Test Environment

Use repeatability analysis to ensure your test environment is stable:

```bash
# Run 5 identical tests
for i in {1..5}; do
  ansible-playbook llm-benchmark-auto.yml -e "test_model=..." -e "workload_type=chat" -e "requested_cores=16"
done

# Check repeatability
./analyze_repeatability.py ../../../results/llm -o validation_report.md

# Look for CV < 1% to confirm stable environment
```

### 2. Compare Configuration Stability

Compare how different hardware configurations affect repeatability:

```bash
# Run multiple tests on different core counts
for cores in 16 32 64; do
  for run in {1..3}; do
    ansible-playbook llm-benchmark-auto.yml \
      -e "test_model=meta-llama/Llama-3.2-1B-Instruct" \
      -e "workload_type=chat" \
      -e "requested_cores=$cores"
  done
done

# Analyze and compare
./analyze_repeatability.py ../../../results/llm -o core_comparison.md

# Check rankings to see which core count has best repeatability
```

### 3. Regression Testing

Establish baseline repeatability for detecting real performance changes:

```bash
# Baseline: Run tests 3x before code change
for i in {1..3}; do
  ansible-playbook llm-benchmark-auto.yml -e "..."
done

./analyze_repeatability.py ../../../results/llm -o baseline_repeatability.md

# After code change: New performance difference should exceed baseline CV
```

### 4. Benchmark Publishing

Ensure results are repeatable before publishing:

- **Requirement**: CV < 3% for all critical metrics
- **Best practice**: Run 3+ iterations
- **Report**: Include CV values in published data

## Command-Line Options

```
usage: analyze_repeatability.py [-h] [-o OUTPUT] [-j JSON_OUTPUT] [-v] results_dir

positional arguments:
  results_dir           Path to results directory

options:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Output markdown file (default: repeatability_report.md)
  -j JSON_OUTPUT, --json-output JSON_OUTPUT
                        Optional JSON output file
  -v, --verbose         Verbose output
```

## Troubleshooting

### "No benchmark results found"

- Ensure the results directory exists and contains `benchmarks.json` files
- Check that `test-metadata.json` files are present alongside benchmark files

### "No configurations with multiple runs found"

- You need at least 2 runs of the same configuration
- Verify that test parameters (model, workload, cores, etc.) match exactly
- Check that runs are grouped in the same model directory

### High CV values (> 5%)

Possible causes:
- System not idle during tests
- Background processes affecting performance
- Thermal throttling
- NUMA instability (especially with TP > 1)
- Network latency variation (external endpoint mode)

Solutions:
- Ensure system is idle and dedicated to testing
- Use deterministic settings (see deterministic-benchmarking.md)
- Add warmup time between runs
- Monitor system metrics during tests

## Integration with Dashboard

To add repeatability metrics to the dashboard, you can:

1. **Generate JSON output** for programmatic access
2. **Load CV data** in dashboard using the JSON report
3. **Visualize** CV trends across configurations

Example integration:

```python
import json
import pandas as pd

# Load repeatability analysis
with open('repeatability_report.json') as f:
    cv_data = json.load(f)

# Convert to DataFrame for visualization
cv_records = []
for config_id, config_data in cv_data.items():
    for metric_name, metric_data in config_data['metrics'].items():
        cv_records.append({
            'configuration': f"{config_data['cores']}c TP={config_data['tensor_parallel']}",
            'concurrency': config_data['concurrency'],
            'metric': metric_name,
            'cv': metric_data['mean']['cv'],
            'grade': metric_data['mean']['grade']
        })

df_cv = pd.DataFrame(cv_records)

# Now you can plot CV trends, filter by grade, etc.
```

## Best Practices

1. **Run at least 3 iterations** for meaningful statistics
2. **Use identical test parameters** across runs
3. **Ensure system stability** (idle, no thermal throttling)
4. **Document test conditions** (date, environment, setup)
5. **Compare CV values** when evaluating configuration changes
6. **Publish CV data** alongside performance results
7. **Set acceptance criteria** (e.g., CV < 3% for production configs)

## Related Documentation

- [Deterministic Benchmarking Guide](../../../../docs/platform-setup/x86/intel/deterministic-benchmarking.md)
- [Manual Sweep Methodology](../../../../docs/methodology/manual-sweep.md)
- [Dashboard Documentation](../../../dashboard-examples/README.md)
