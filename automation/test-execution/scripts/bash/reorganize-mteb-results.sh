#!/bin/bash
# ==============================================================================
# Reorganize MTEB Results to Clean Directory Structure
# ==============================================================================
# This script reorganizes MTEB results from the nested structure to a flat one.
#
# From: results/mteb/MODEL/TIMESTAMP/no_model_name_available/no_revision_available/*.json
# To:   results/mteb/MODEL/TIMESTAMP/TaskName/test.json
#
# Usage:
#   ./reorganize-mteb-results.sh [results_dir]
#
# ==============================================================================

set -euo pipefail

RESULTS_DIR="${1:-results/mteb}"

if [[ ! -d "${RESULTS_DIR}" ]]; then
    echo "Error: Directory not found: ${RESULTS_DIR}"
    exit 1
fi

echo "Reorganizing MTEB results in: ${RESULTS_DIR}"
echo ""

# Find all run directories with nested structure
while IFS= read -r -d '' nested_dir; do
    echo "Processing: ${nested_dir}"

    # Get parent directory (timestamp directory)
    test_run_dir="$(dirname "$(dirname "${nested_dir}")")"

    # Process each task JSON file
    for task_file in "${nested_dir}"/*.json; do
        [[ -e "${task_file}" ]] || continue

        filename="$(basename "${task_file}")"

        # Skip metadata files
        if [[ "${filename}" == "model_meta.json" ]]; then
            continue
        fi

        # Extract task name
        task_name="${filename%.json}"

        # Create task directory
        task_dir="${test_run_dir}/${task_name}"
        mkdir -p "${task_dir}"

        # Transform JSON structure
        # From: {scores: {test: [{metrics...}]}}
        # To:   {test: {metrics...}}
        if command -v jq &> /dev/null; then
            # Extract first element from scores.test array and put it under 'test' key
            if jq -e '.scores.test[0]' "${task_file}" > /dev/null 2>&1; then
                jq '{test: .scores.test[0]}' "${task_file}" > "${task_dir}/test.json"
                echo "  ✓ Created ${task_dir}/test.json"
            else
                # If already in correct format, just copy
                cp "${task_file}" "${task_dir}/test.json"
                echo "  ✓ Copied ${task_dir}/test.json (already in correct format)"
            fi
        else
            echo "  ! jq not found, copying file as-is"
            cp "${task_file}" "${task_dir}/test.json"
        fi
    done

    # Remove the nested directory after successful reorganization
    echo "  ✓ Cleaning up nested directory"
    rm -rf "$(dirname "${nested_dir}")"
    echo ""

done < <(find "${RESULTS_DIR}" -type d -path "*/no_model_name_available/no_revision_available" -print0)

echo "Reorganization complete!"
echo ""
echo "Results are now in the format:"
echo "  results/mteb/MODEL/TIMESTAMP/TaskName/test.json"
