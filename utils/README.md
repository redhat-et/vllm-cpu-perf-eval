# Utils

This directory contains utility scripts for benchmark analysis and reporting.

## Scripts

### analyze_benchmark_results.py

Analyzes guidellm sweep test results and generates comprehensive performance
reports.

**Usage:**

```bash
# From project root
python3 utils/analyze_benchmark_results.py
```

**What it does:**

- Parses guidellm CSV benchmark results
- Extracts mean and P95 metrics for:
  - Requests/second
  - Throughput (tokens/sec)
  - Time to First Token (TTFT)
  - Time per Output Token (TPOT)
  - Request Latency
  - Concurrency
- Generates visualizations (PNG charts)
- Creates summary tables (CSV and TXT)
- Outputs all reports to `benchmark_reports/` directory

**Requirements:**

```bash
pip install pandas matplotlib seaborn numpy
```

**Full Documentation:**
See [BENCHMARK_ANALYSIS_GUIDE.md](BENCHMARK_ANALYSIS_GUIDE.md) for complete
usage instructions, customization options, and troubleshooting.

## Directory Structure

```text
utils/
├── README.md                        # This file
├── BENCHMARK_ANALYSIS_GUIDE.md      # Complete guide for benchmark analysis
└── analyze_benchmark_results.py    # Benchmark analysis script
```

## Adding New Utilities

When adding new utility scripts to this directory:

1. Add a clear docstring at the top of the file
2. Update this README with usage instructions
3. Add any new dependencies to requirements (if needed)
4. Follow the existing code style and patterns
