#!/bin/bash
# Examples of using the MLflow logging playbook

# Set your MLflow tracking URI (optional, defaults to http://localhost:5000)
export MLFLOW_TRACKING_URI=http://localhost:5000

# ==============================================================================
# Example 1: Log a single test result
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "benchmarks_file=../../../results/llm/meta-llama__Llama-3.1-8B-Instruct/chat-20250501-120000/128c/benchmarks.json" \
  -e "metadata_file=../../../results/llm/meta-llama__Llama-3.1-8B-Instruct/chat-20250501-120000/128c/test-metadata.json"

# ==============================================================================
# Example 2: Log with custom experiment name
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "benchmarks_file=results/llm/model/workload/128c/benchmarks.json" \
  -e "metadata_file=results/llm/model/workload/128c/test-metadata.json" \
  -e "experiment_name=Production-Llama-Tests"

# ==============================================================================
# Example 3: Log with detailed per-load-point metrics
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "benchmarks_file=results/llm/model/workload/128c/benchmarks.json" \
  -e "metadata_file=results/llm/model/workload/128c/test-metadata.json" \
  -e "log_per_load_point=true"

# ==============================================================================
# Example 4: Batch import ALL results
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "batch_import=true"

# ==============================================================================
# Example 5: Batch import with filters (by model)
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "batch_import=true" \
  -e "model_filter=Llama-3.1-8B"

# ==============================================================================
# Example 6: Batch import with filters (by workload)
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "batch_import=true" \
  -e "workload_filter=chat"

# ==============================================================================
# Example 7: Batch import with multiple filters
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "batch_import=true" \
  -e "model_filter=Llama" \
  -e "workload_filter=chat" \
  -e "results_directory=/custom/path/to/results"

# ==============================================================================
# Example 8: Use with remote MLflow server
# ==============================================================================

ansible-playbook log-to-mlflow.yml \
  -e "benchmarks_file=results/benchmarks.json" \
  -e "metadata_file=results/test-metadata.json" \
  -e "mlflow_tracking_uri=http://mlflow-server.example.com:5000"

# ==============================================================================
# Example 9: Log latest test result
# ==============================================================================

# Find the most recent test result and log it
LATEST_BENCH=$(find ../../../results/llm -name "benchmarks.json" -type f -printf '%T@ %p\n' | sort -rn | head -1 | cut -d' ' -f2)
LATEST_META="${LATEST_BENCH%/*}/test-metadata.json"

ansible-playbook log-to-mlflow.yml \
  -e "benchmarks_file=${LATEST_BENCH}" \
  -e "metadata_file=${LATEST_META}"

# ==============================================================================
# Example 10: Import all results from today
# ==============================================================================

# This would require enhancing the playbook with date filtering
# For now, use a script to filter by date and call the playbook

find ../../../results/llm -name "benchmarks.json" -type f -mtime -1 | while read bench; do
    meta="${bench%/*}/test-metadata.json"
    if [ -f "$meta" ]; then
        ansible-playbook log-to-mlflow.yml \
          -e "benchmarks_file=${bench}" \
          -e "metadata_file=${meta}"
    fi
done
