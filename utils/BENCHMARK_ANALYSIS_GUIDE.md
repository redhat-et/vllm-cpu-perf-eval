# Benchmark Analysis Guide

This guide explains how to analyze guidellm sweep test results for vLLM
CPU performance evaluation.

## Overview

The `utils/analyze_benchmark_results.py` script processes guidellm benchmark
CSV files and generates comprehensive performance reports including
visualizations and statistical summaries.

## Prerequisites

### Required Python Packages

```bash
python3 -m pip install pandas matplotlib seaborn numpy
```

### Data Structure

The script expects benchmark results in the following directory structure:

```text
/Users/Xeon-single-platform/
├── T01-llama-8c-nopreempt/
│   ├── benchmarks.json
│   └── T01-llama-8c-nopreempt.csv
├── T01-tinyllama-8c-nopreempt/
│   ├── benchmarks.json
│   └── T01-tinyllama-8c-nopreempt.csv
└── ...
```

**Naming Convention:** `T##-{model}-{cores}c-nopreempt/`

- `T##`: Test number (e.g., T01, T02)
- `{model}`: Model name (llama, tinyllama)
- `{cores}`: Number of cores (8, 16, 24, 32)

## Usage

### Basic Usage

Run the analysis script from the project root:

```bash
# Use default directories
python3 utils/analyze_benchmark_results.py

# Specify custom data directory
python3 utils/analyze_benchmark_results.py /path/to/benchmark/data

# Specify custom output directory
python3 utils/analyze_benchmark_results.py --output-dir my_reports

# Both custom directories
python3 utils/analyze_benchmark_results.py /path/to/data --output-dir \
  my_reports
```

**Command Line Arguments:**

- `data_dir` (optional): Path to directory containing benchmark results
  (default: `/Users/Xeon-single-platform`)
- `--output-dir` (optional): Directory for output reports
  (default: `benchmark_reports`)
- `--help`: Show help message

This will:

1. Load all benchmark CSV files from the specified data directory
2. Extract performance metrics (mean and P95 values)
3. Generate visualizations and tables
4. Save all outputs to the specified output directory

### Output Directory Structure

After running, the `benchmark_reports/` directory will contain:

```text
benchmark_reports/
├── performance_overview.png              # 6-panel overview
├── requests_sec_mean_comparison.png      # Requests/sec (Mean & P95)
├── throughput_tokens_sec_mean_comparison.png  # Throughput
├── ttft_mean_comparison.png              # TTFT (Mean & P95)
├── tpot_mean_comparison.png              # TPOT (Mean & P95)
├── latency_mean_comparison.png           # Request Latency
├── concurrency_mean_comparison.png       # Concurrency
├── performance_summary_combined.csv      # Combined Mean & P95 metrics
├── performance_summary_mean.csv          # Mean values only
├── performance_summary_p95.csv           # P95 values only
├── performance_summary.txt               # Formatted text report
└── pivot_tables.txt                      # Pivot tables by model/cores
```

## Understanding the Metrics

### Metrics Tracked

All metrics include both **Mean** and **P95** (95th percentile) values:

| Metric | Description | Direction | Unit |
| ------ | ----------- | --------- | ---- |
| **Requests/sec** | Requests processed per second | ↑ Higher | req/s |
| **Throughput** | Output tokens per second | ↑ Higher | tokens/s |
| **TTFT** | Time to First Token latency | ↓ Lower | ms |
| **TPOT** | Time per Output Token | ↓ Lower | ms |
| **Latency** | Overall request latency | ↓ Lower | seconds |
| **Concurrency** | Concurrent requests (Little's Law) | Info | count |

**Note on Concurrency:** The concurrency metric follows **Little's Law**:
`Concurrency = Throughput × Latency`. High concurrency values (e.g., 20+)
indicate many requests are being processed simultaneously, which occurs when
latency is high. As you add more cores and reduce latency, concurrency
naturally decreases. This is expected behavior and indicates the system is
processing requests faster.

### Chart Indicators

Each chart title includes directional indicators:

- **↑** = Higher is better (throughput, requests/sec)
- **↓** = Lower is better (latency, TTFT, TPOT)
- No indicator = Informational only (concurrency)

### Mean vs P95

- **Mean**: Average value across all requests
  - Good for understanding typical performance
  - Useful for capacity planning

- **P95**: 95th percentile - 95% of requests perform at or better than
  this value
  - Shows worst-case performance for most users
  - Critical for SLA compliance
  - Reveals performance outliers and tail latency

## Customization

### Changing Data Source

You can specify a custom data directory using the command line:

```bash
python3 utils/analyze_benchmark_results.py /path/to/your/benchmark/data
```

Alternatively, you can edit the default path in
`utils/analyze_benchmark_results.py`:

```python
# In parse_args() function
parser.add_argument(
    'data_dir',
    nargs='?',
    default='/path/to/your/data',  # Change this default
    ...
)
```

### Adding Custom Metrics

To extract additional metrics from guidellm CSV:

1. Add metric extraction in `extract_metrics()`:

   ```python
   # Add to extract_metrics() function
   new_metric_mean = row[('Category', 'Metric Name', 'Mean')]
   new_metric_p95 = extract_p95_from_percentiles(
       row[('Category', 'Metric Name', 'Percentiles')])

   metric = {
       # ... existing metrics ...
       'new_metric_mean': float(new_metric_mean),
       'new_metric_p95': new_metric_p95,
   }
   ```

1. Add to visualization in `create_comparison_plots()`:

   ```python
   metrics = [
       # ... existing metrics ...
       ('new_metric_mean', 'new_metric_p95', 'New Metric Name ↑',
        'Y-axis Label', True),  # True = higher is better
   ]
   ```

### Modifying Chart Styles

Chart appearance is controlled by matplotlib/seaborn settings:

```python
# At top of file
sns.set_style("whitegrid")  # Options: darkgrid, white, dark, ticks
plt.rcParams['figure.figsize'] = (14, 8)  # Adjust size

# In create_comparison_plots()
# Change colors:
color='#5B9BD5'  # Llama (blue)
color='#ED7D31'  # TinyLlama (orange)
```

## Troubleshooting

### Import Errors

```bash
# Error: ModuleNotFoundError: No module named 'pandas'
python3 -m pip install pandas matplotlib seaborn numpy
```

### File Not Found

```bash
# Error: CSV file not found for T01-llama-8c-nopreempt
# Check directory structure and naming convention
ls -la /Users/Xeon-single-platform/
```

### Empty Results

```bash
# Error: No results found!
# Verify CSV files are not empty and contain data
head -20 /Users/Xeon-single-platform/T01-llama-8c-nopreempt/*.csv
```

### Permission Errors

```bash
# Make script executable
chmod +x utils/analyze_benchmark_results.py

# Or run with python3
python3 utils/analyze_benchmark_results.py
```

## Running New Benchmarks

### Using guidellm

1. **Setup guidellm** (refer to guidellm documentation at
   `/Users/mtahhan/git-workspace/guidellm`)

1. **Run sweep test**:

   ```bash
   guidellm \
     --target http://localhost:8000 \
     --data "prompt_tokens=256,output_tokens=128" \
     --profile sweep \
     --max-seconds 600 \
     --max-requests 2000 \
     --outputs json,csv,html \
     --output-dir /Users/Xeon-single-platform/T05-llama-40c-nopreempt/
   ```

1. **Analyze results**:

   ```bash
   python3 utils/analyze_benchmark_results.py
   ```

### Benchmark Best Practices

1. **Warmup**: Allow vLLM server to warm up before benchmarking
2. **Isolation**: Run on dedicated hardware without interference
3. **Consistency**: Use same test parameters across runs
4. **Multiple runs**: Run tests multiple times and compare results
5. **Resource monitoring**: Track CPU, memory, and I/O during tests

## Example Workflow

```bash
# 1. Clean previous results
rm -rf benchmark_reports/

# 2. Run analysis
python3 utils/analyze_benchmark_results.py

# 3. View results
open benchmark_reports/performance_overview.png
cat benchmark_reports/performance_summary.txt

# 4. Open in spreadsheet (for further analysis)
open benchmark_reports/performance_summary_combined.csv
```

## Performance Interpretation Guide

### Optimal Core Count

Based on the data:

- **Llama Model**: Optimal at 24-32 cores
  - Throughput plateaus around 400 tokens/s
  - TTFT reduces by 63% from 8→32 cores

- **TinyLlama Model**: Optimal at 16 cores
  - Achieves peak throughput earlier
  - Minimal gains beyond 16 cores

### Scaling Efficiency

Calculate scaling efficiency:

```text
Efficiency = (Throughput at N cores / Throughput at baseline) /
             (N cores / baseline cores)
```

Example:

- Llama @ 32c vs 8c: (401/242) / (32/8) = 0.41 (41% efficient)
- TinyLlama @ 16c vs 8c: (403/399) / (16/8) = 0.50 (50% efficient)

### SLA Compliance

Check if P95 latency meets requirements:

- **Low Latency SLA** (<500ms): TinyLlama @ 16+ cores
- **Medium Latency SLA** (<2s): TinyLlama @ any config
- **High Throughput SLA** (>400 tok/s): Either model @ 16+ cores

## Additional Resources

- **guidellm Documentation**: `/Users/mtahhan/git-workspace/guidellm`
- **vLLM Documentation**: <https://docs.vllm.ai/>
- **Benchmark Results**: `/Users/Xeon-single-platform/`

## Support

For issues or questions:

1. Check this guide
2. Review the script comments in `utils/analyze_benchmark_results.py`
3. Examine guidellm output logs
4. Verify data directory structure and file contents
