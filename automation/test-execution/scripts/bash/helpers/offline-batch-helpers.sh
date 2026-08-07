#!/bin/bash
# Shared helpers for run-offline-batch-suite.sh.
# Sourced by the suite script and the unit test harness.

# ANSI colors — safe to define when sourced from any context.
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Count completed results for a model/use_case/cores/dataset/num_prompts combination.
# Only existing results.json files count; failed or partial runs are excluded.
# Requires: REPO_ROOT set to the repository root.
count_existing_results() {
    local model="$1"
    local ansible_use_case="$2"
    local cores="$3"
    local dataset="$4"
    local num_prompts="$5"
    local sanitized_model="${model//\//__}"
    local results_base="${REPO_ROOT}/results/llm/${sanitized_model}"

    if [[ ! -d "$results_base" ]]; then
        echo 0
        return
    fi

    local file_list
    file_list=$(find "$results_base" \
        -path "*/${cores}cores-${dataset}-${num_prompts}prompts/results.json" 2>/dev/null)
    if [[ -z "$file_list" ]]; then
        echo 0
        return
    fi
    local count
    count=$(echo "$file_list" | xargs grep -l "\"use_case\": \"${ansible_use_case}\"" 2>/dev/null | wc -l | tr -d ' ') || true
    echo "${count:-0}"
}

# cap_prompts N — return N capped at OFFLINE_BATCH_MAX_PROMPTS (0 or unset = no cap)
cap_prompts() {
    local n=$1
    if [[ "${OFFLINE_BATCH_MAX_PROMPTS:-0}" -gt 0 && "$n" -gt "$OFFLINE_BATCH_MAX_PROMPTS" ]]; then
        echo "$OFFLINE_BATCH_MAX_PROMPTS"
    else
        echo "$n"
    fi
}

# Run a single config with skip/resume logic.
# Skips if existing results >= runs (unless OFFLINE_BATCH_FORCE=1).
# Resumes partial runs, preserving correct run_display numbering.
# Returns 0 if all runs succeeded or were skipped, 1 if any run failed.
# Requires: count_existing_results, run_test (provided by caller), OFFLINE_BATCH_FORCE.
# Args: model ansible_use_case dataset num_prompts cores runs [extra_args...]
run_with_resume() {
    local model="$1" ansible_use_case="$2" dataset="$3" num_prompts="$4"
    local cores="$5" runs="$6"
    shift 6

    local existing_runs=0 remaining=$runs

    if [[ "${OFFLINE_BATCH_FORCE:-0}" != "1" ]]; then
        existing_runs=$(count_existing_results "$model" "$ansible_use_case" "$cores" "$dataset" "$num_prompts")
        remaining=$((runs - existing_runs))
        if [[ $remaining -le 0 ]]; then
            echo "  Cores: $cores - SKIP ($existing_runs/$runs runs already complete)"
            return 0
        fi
        if [[ $existing_runs -gt 0 ]]; then
            echo "  Cores: $cores ($existing_runs/$runs done, running $remaining more)"
        else
            echo "  Cores: $cores"
        fi
    else
        echo "  Cores: $cores (force: running all $runs)"
    fi

    local run_failed=0
    for run in $(seq 1 $remaining); do
        local run_display=$((existing_runs + run))
        echo "    Run $run_display/$runs..."
        if ! run_test "$model" "$dataset" "$num_prompts" "$cores" "$@"; then
            echo -e "${RED}    FAILED: Run $run_display/$runs${NC}"
            run_failed=1
        fi
    done
    return $run_failed
}
