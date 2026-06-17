# CSV Import Guide for Streamlit Dashboards

## Overview

The vLLM Performance Dashboards now support importing CSV data files directly into the dashboard interface. This allows you to:
- Import pre-processed benchmark results
- Merge CSV data with directory-scanned results
- Share and analyze benchmark data without file structure dependencies

## Quick Start

### Method 1: Sidebar Upload (Individual Dashboards)

1. **Navigate to the dashboard** (Client Metrics or Embedding Metrics)
2. **Look for "📥 Import CSV"** section in the sidebar
3. **Click "Browse files"** and select your CSV file
4. **Click "🔄 Reload Data"** to refresh the dashboard with imported data

### Method 2: Dedicated Import Page (All Data Types)

1. **Navigate to "📥 Import Data"** page in the sidebar
2. **Upload one or more CSV files**
3. **Preview the data** to verify it loaded correctly
4. **Click "Use [filename] in Dashboard"** to make it available to other pages
5. **Navigate to the appropriate dashboard** to view the data

## Supported CSV Formats

### Embedding Performance CSV

Required columns for embedding metrics:
```
model, platform, vllm_version, vllm_mode, requested_cores, input_length
test_type, parameter, request_rate, max_concurrency
request_throughput_rps, token_throughput_tps, rps_per_core
mean_latency_ms, median_latency_ms, p99_latency_ms
```

Example: `embedding-results.csv`

### LLM Performance CSV

Required columns for LLM metrics:
```
model, platform, workload, cores, backend, vllm_version
concurrency, request_rate
throughput_mean, throughput_p50, throughput_p95, throughput_p99
ttft_mean, ttft_p50, ttft_p95, ttft_p99
itl_mean, itl_p50, itl_p95, itl_p99
e2e_mean, e2e_p50, e2e_p95, e2e_p99
```

Example: `Xeon-1-instance-32-core-llm-metrics_full_data.csv`

## Features

### Data Merging
- Imported CSV data is automatically merged with directory-scanned results
- Duplicate detection based on test_run_id (if available)
- Combined data appears in all visualizations

### Data Persistence
- CSV data persists within the browser session
- Use "❌ Clear imported CSV" button to remove imported data
- Reload browser page to clear all session data

### Export Processed Data
- After importing and filtering, export merged/filtered results
- Navigate to "📥 Export Data" expander at bottom of dashboard
- Click "Download CSV" to save processed results

## Example Workflows

### Workflow 1: Analyze Pre-Processed Results

```bash
# You have: embedding-results.csv from previous test runs
# Goal: Visualize in dashboard without file structure

1. Open dashboard: http://localhost:8501
2. Go to "📊 Embedding Metrics" page
3. In sidebar, under "📥 Import CSV", upload embedding-results.csv
4. Click "🔄 Reload Data"
5. Apply filters and view visualizations
```

### Workflow 2: Compare Directory Data + CSV Data

```bash
# You have: Live results in results/embedding/ + CSV from external source
# Goal: Compare both datasets

1. Dashboard automatically loads results/embedding/
2. Upload external CSV in sidebar
3. Click "🔄 Reload Data"
4. Both datasets appear in filters and charts
5. Use model/platform filters to isolate specific comparisons
```

### Workflow 3: Share Results with Team

```bash
# You have: Benchmark results you want to share
# Goal: Share CSV instead of entire directory structure

1. Run benchmarks normally
2. Navigate to dashboard
3. Go to "📥 Export Data" expander
4. Download CSV with filtered results
5. Share CSV file with team
6. Team can import CSV directly in their dashboard
```

## Troubleshooting

### CSV Not Loading

**Problem**: Upload shows error
- **Check**: CSV format matches expected columns
- **Check**: No special characters in column names
- **Fix**: Open CSV in text editor, verify header row

### Data Not Appearing After Upload

**Problem**: Uploaded but charts are empty
- **Check**: Click "🔄 Reload Data" after upload
- **Check**: Filters may be excluding imported data
- **Fix**: Reset filters to "All" to see all data

### Wrong Data Type Detected

**Problem**: Import page shows "Unknown" data type
- **Check**: CSV has required columns for the data type
- **Fix**: Rename columns to match expected format (see above)

### Session Lost After Refresh

**Problem**: Imported data disappears on page reload
- **Cause**: Session state is browser-only (expected behavior)
- **Fix**: Re-upload CSV or use directory-based loading for persistence

## Technical Details

### Implementation

The CSV import feature uses Streamlit's session state to store imported dataframes:

```python
# Data is stored in st.session_state with specific keys:
st.session_state['imported_embedding_performance']  # Embedding data
st.session_state['imported_llm_performance']        # LLM data
```

### File Locations

```
automation/test-execution/dashboard-examples/vllm_dashboard/
├── pages/
│   ├── 1_📊_Client_Metrics.py      # LLM CSV import
│   ├── 3_📊_Embedding_Metrics.py   # Embedding CSV import
│   └── 4_📥_Import_Data.py         # Universal CSV import page
└── Home.py
```

### Data Flow

```
CSV File → File Uploader → pd.read_csv() → st.session_state → 
pd.concat() with directory data → Filters → Visualizations
```

## Best Practices

1. **Column Names**: Use exact column names from template CSVs
2. **Data Validation**: Preview data in Import page before using
3. **Memory Management**: Clear imported data when switching datasets
4. **Export Results**: Download filtered/merged results for archival
5. **Large Files**: For very large CSVs (>100MB), use directory loading instead

## Column Mapping Reference

If your CSV has different column names, rename them to match:

### Embedding CSV Mapping
```python
# Your CSV → Expected Name
'req_per_sec' → 'request_throughput_rps'
'tok_per_sec' → 'token_throughput_tps'
'latency_avg' → 'mean_latency_ms'
'latency_p99' → 'p99_latency_ms'
```

### LLM CSV Mapping
```python
# Your CSV → Expected Name
'avg_throughput' → 'throughput_mean'
'time_to_first_token' → 'ttft_mean'
'inter_token_latency' → 'itl_mean'
'end_to_end_latency' → 'e2e_mean'
```

## Support

For issues or questions:
1. Check column names match expected format
2. Verify CSV is properly formatted (comma-separated, UTF-8)
3. Look at example CSVs in the repository
4. Check dashboard logs in terminal

## Future Enhancements

Planned features:
- [ ] Auto-detect and map column names
- [ ] Support for Excel (.xlsx) files
- [ ] Persistent storage (database backend)
- [ ] Batch CSV import (multiple files at once)
- [ ] CSV validation with detailed error messages
