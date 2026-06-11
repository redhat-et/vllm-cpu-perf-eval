#!/usr/bin/env bash
#
# Extract Benchmark Timings for All Configurations
# Processes all benchmarks.json files and extracts timing data to test-metadata.json
#
# Usage:
#   ./extract-all-timings.sh MODEL WORKLOAD TEST_RUN_ID RESULTS_DIR SCRIPTS_DIR
#
# Arguments:
#   MODEL        - Model name (e.g., "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
#   WORKLOAD     - Workload type (e.g., "chat")
#   TEST_RUN_ID  - Test run identifier (e.g., "20260303-155156")
#   RESULTS_DIR  - Base directory containing results
#   SCRIPTS_DIR  - Base scripts directory (defaults to automation/test-execution/scripts)

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "Error: Missing required arguments"
  echo "Usage: $0 MODEL WORKLOAD TEST_RUN_ID RESULTS_DIR SCRIPTS_DIR"
  exit 1
fi

MODEL="$1"
WORKLOAD="$2"
TEST_RUN_ID="$3"
RESULTS_DIR="$4"
SCRIPTS_DIR="$5"

# Convert model name to safe directory name
MODEL_DIR="${MODEL//\//__}"

# Path to results
RESULTS_PATH="${RESULTS_DIR}/${MODEL_DIR}/${WORKLOAD}-${TEST_RUN_ID}"

echo "Extracting benchmark timings..."
echo "  Results path: ${RESULTS_PATH}"

# Check if Python script exists
EXTRACTOR_SCRIPT="${SCRIPTS_DIR}/ansible/extract_benchmark_timings.py"
if [[ ! -f "$EXTRACTOR_SCRIPT" ]]; then
  echo "Error: Script not found: $EXTRACTOR_SCRIPT"
  exit 1
fi

# Process all benchmarks.json files
processed_count=0
for benchmarks_file in "${RESULTS_PATH}"/*/benchmarks.json; do
  if [[ -f "$benchmarks_file" ]]; then
    metadata_file="${benchmarks_file%benchmarks.json}test-metadata.json"

    if [[ -f "$metadata_file" ]]; then
      config_dir=$(basename "$(dirname "$benchmarks_file")")
      echo "  Processing: ${config_dir}"

      if python3 "$EXTRACTOR_SCRIPT" "$benchmarks_file" "$metadata_file"; then
        ((processed_count++))
      else
        echo "  ⚠ Warning: Failed to process ${config_dir}"
      fi
    else
      echo "  ⚠ Warning: Metadata file not found for $(basename "$(dirname "$benchmarks_file")")"
    fi
  fi
done

if [[ $processed_count -eq 0 ]]; then
  echo "  ℹ No benchmark files found to process"
else
  echo "✓ Processed $processed_count configuration(s)"
fi
