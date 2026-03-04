#!/usr/bin/env bash
#
# Copy GuideLLM Logs to Final Results Directory
# Copies all guidellm.log files from source directories to final results location
#
# Usage:
#   ./copy-guidellm-logs.sh MODEL WORKLOAD TEST_RUN_ID BENCH_RESULTS_DIR FINAL_RESULTS_DIR
#
# Arguments:
#   MODEL              - Model name (e.g., "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
#   WORKLOAD           - Workload type (e.g., "chat")
#   TEST_RUN_ID        - Test run identifier (e.g., "20260303-155156")
#   BENCH_RESULTS_DIR  - Source directory containing benchmark results
#   FINAL_RESULTS_DIR  - Destination directory for final results

set -euo pipefail

if [[ $# -ne 5 ]]; then
  echo "Error: Missing required arguments"
  echo "Usage: $0 MODEL WORKLOAD TEST_RUN_ID BENCH_RESULTS_DIR FINAL_RESULTS_DIR"
  exit 1
fi

MODEL="$1"
WORKLOAD="$2"
TEST_RUN_ID="$3"
BENCH_RESULTS_DIR="$4"
FINAL_RESULTS_DIR="$5"

# Convert model name to safe directory name
MODEL_DIR="${MODEL//\//__}"

# Source and destination paths
SOURCE_PATH="${BENCH_RESULTS_DIR}/${MODEL_DIR}/${WORKLOAD}-${TEST_RUN_ID}"
DEST_PATH="${FINAL_RESULTS_DIR}/${MODEL_DIR}/${WORKLOAD}-${TEST_RUN_ID}"

echo "Copying GuideLLM logs..."
echo "  Source: ${SOURCE_PATH}"
echo "  Destination: ${DEST_PATH}"

# Find and copy all guidellm.log files
copied_count=0
for log_file in "${SOURCE_PATH}"/*/guidellm.log; do
  if [[ -f "$log_file" ]]; then
    config_dir=$(basename "$(dirname "$log_file")")
    dest_dir="${DEST_PATH}/${config_dir}"

    mkdir -p "$dest_dir"
    cp "$log_file" "$dest_dir/"

    echo "  ✓ Copied: ${config_dir}/guidellm.log"
    ((copied_count++))
  fi
done

if [[ $copied_count -eq 0 ]]; then
  echo "  ℹ No guidellm.log files found"
else
  echo "✓ Copied $copied_count log file(s)"
fi
