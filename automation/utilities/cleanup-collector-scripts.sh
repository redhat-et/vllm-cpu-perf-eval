#!/bin/bash
# Cleanup script to remove orphaned collect_vllm_metrics.py files from results directories
# These files were created by an older version of the vllm_metrics_collector role

RESULTS_DIR="${1:-results/llm}"

if [ ! -d "$RESULTS_DIR" ]; then
    echo "Error: Results directory not found: $RESULTS_DIR"
    echo "Usage: $0 [results_directory]"
    exit 1
fi

echo "Cleaning up collect_vllm_metrics.py files from results directories..."
echo "Searching in: $RESULTS_DIR"
echo

# Find and count scripts
SCRIPT_COUNT=$(find "$RESULTS_DIR" -name "collect_vllm_metrics.py" -type f | wc -l)

if [ "$SCRIPT_COUNT" -eq 0 ]; then
    echo "✓ No orphaned scripts found. Results directories are clean!"
    exit 0
fi

echo "Found $SCRIPT_COUNT orphaned script(s):"
find "$RESULTS_DIR" -name "collect_vllm_metrics.py" -type f

echo
read -p "Delete these files? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    find "$RESULTS_DIR" -name "collect_vllm_metrics.py" -type f -delete
    echo "✓ Deleted $SCRIPT_COUNT file(s)"

    # Calculate space saved (rough estimate: ~5KB per script)
    SPACE_SAVED=$((SCRIPT_COUNT * 5))
    echo "✓ Freed ~${SPACE_SAVED}KB of disk space"
else
    echo "Cleanup cancelled."
fi
