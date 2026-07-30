---
title: MTEB Troubleshooting
parent: MTEB Quality Testing
grand_parent: Documentation
nav_order: 3
layout: default
---

## MTEB Results Not Showing in Dashboard

### Issue
MTEB results are generated but not visible in the embedding dashboard.

### Root Cause
MTEB's output directory structure may differ from the expected format. MTEB creates results under:
```
results/mteb/MODEL/TIMESTAMP/no_model_name_available/no_revision_available/TaskName.json
```

Instead of the simpler expected structure:
```
results/mteb/MODEL/TIMESTAMP/TaskName/test.json
```

### Solution
The dashboard (`pages/3_📊_Embedding_Metrics.py`) has been updated to handle both formats automatically. The `load_mteb_data()` function now:

1. Scans for `run_summary.json` files to find test runs
2. Looks for task results in multiple locations:
   - `TaskName/test.json` subdirectories (expected format)
   - `no_model_name_available/no_revision_available/*.json` (actual MTEB output)
3. Handles different JSON structures:
   - Direct `test` object with metrics
   - MTEB's `scores.test[0]` structure with aggregated metrics

### Verification

After updating the dashboard code, verify MTEB results are loading:

```bash
# 1. Check MTEB results exist
ls -la results/mteb/

# 2. Run the dashboard
cd automation/test-execution/dashboard-examples/vllm_dashboard
streamlit run Home.py

# 3. Navigate to "📊 Embedding Metrics" page
# 4. Check the status message shows loaded MTEB results
```

You should see a message like:
```
✓ Loaded XX performance test results and YY MTEB quality results
```

### Alternative: Reorganizing Results (Optional)

If you prefer the cleaner directory structure, you can manually reorganize results:

```bash
# Navigate to a test run directory
cd results/mteb/RedHatAI__granite-embedding-english-r2/20260603-120835/

# Move results out of nested directory
mv no_model_name_available/no_revision_available/*.json .

# For each task result file, create subdirectory
for file in *.json; do
  if [ "$file" != "run_summary.json" ] && [ "$file" != "model_meta.json" ]; then
    task_name="${file%.json}"
    mkdir -p "$task_name"

    # Create test.json with simplified structure
    jq '{test: .scores.test[0]}' "$file" > "$task_name/test.json"
  fi
done

# Clean up
rm -rf no_model_name_available/
rm *.json  # Keep only run_summary.json
```

## Future Improvements

The MTEB wrapper sets `model_name` and `revision` attributes correctly. However, MTEB's internal behavior for organizing results may depend on:

1. The MTEB library version (currently using MTEB 2.12.30+)
2. How MTEB constructs `ModelMeta` objects internally
3. Whether the model is from HuggingFace Hub vs. a vLLM server endpoint

Potential fixes:
- Explicitly construct and set `mteb_model_meta` object with proper model/revision
- Use MTEB's model name resolution API if available
- Post-process results with a conversion script
