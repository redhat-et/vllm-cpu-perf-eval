#!/bin/bash
# Fix MTEB results directory structure for dashboard compatibility
# Converts root-level JSON files to TaskName/test.json subdirectories

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
RESULTS_DIR="${RESULTS_DIR:-$REPO_ROOT/results/mteb}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Fixing MTEB Results Structure"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results directory: $RESULTS_DIR"
echo ""

if [ ! -d "$RESULTS_DIR" ]; then
    echo "Error: MTEB results directory not found: $RESULTS_DIR"
    exit 1
fi

fixed_count=0

# Find all test run directories (timestamp directories starting with 20)
for run_dir in "$RESULTS_DIR"/*/20*; do
    if [ ! -d "$run_dir" ]; then
        continue
    fi

    echo "Checking: $run_dir"

    # Process nested structure: no_model_name_available/no_revision_available/*.json
    nested_dir="$run_dir/no_model_name_available/no_revision_available"
    if [ -d "$nested_dir" ]; then
        echo "  Found nested structure, reorganizing..."

        for json_file in "$nested_dir"/*.json; do
            if [ ! -f "$json_file" ]; then
                continue
            fi

            task_name=$(basename "$json_file" .json)

            # Skip metadata files
            if [ "$task_name" = "model_meta" ]; then
                mv "$json_file" "$run_dir/" 2>/dev/null || true
                continue
            fi

            # Create TaskName/test.json structure
            mkdir -p "$run_dir/$task_name"
            mv "$json_file" "$run_dir/$task_name/test.json"
            echo "    ✓ $task_name/test.json"
            ((fixed_count++))
        done

        # Remove nested directories
        rm -rf "$run_dir/no_model_name_available"
    fi

    # Process root-level JSON files (from previous incorrect reorganization)
    for json_file in "$run_dir"/*.json; do
        if [ ! -f "$json_file" ]; then
            continue
        fi

        task_name=$(basename "$json_file" .json)

        # Skip summary and metadata files
        if [ "$task_name" = "run_summary" ] || [ "$task_name" = "model_meta" ]; then
            continue
        fi

        # Create TaskName/test.json structure if not already exists
        if [ ! -d "$run_dir/$task_name" ]; then
            echo "  Fixing root-level file: $task_name"
            mkdir -p "$run_dir/$task_name"
            mv "$json_file" "$run_dir/$task_name/test.json"
            echo "    ✓ $task_name/test.json"
            ((fixed_count++))
        fi
    done
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ Fixed $fixed_count task result files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Expected structure: results/mteb/MODEL/TIMESTAMP/TaskName/test.json"
echo ""
echo "Next steps:"
echo "  1. Restart the Streamlit dashboard"
echo "  2. Navigate to 📊 Embedding Metrics → 🎯 MTEB Quality"
echo "  3. Results should now be visible"
