#!/bin/bash
# ==============================================================================
# Upstream LLM Concurrent Load Test Suite
# ==============================================================================
# Run concurrent load benchmarks on upstream LLM models across different
# core counts and workload types.
#
# Prerequisites:
#   - Models defined in models/llm-models/model-matrix.yaml with test_suites: concurrent-load
#   - HF_TOKEN environment variable for gated models (Llama 3.x)
#
# Usage:
#   ./run-concurrent-load-suite.sh [options]
#
# Options:
#   --models LIST           Comma-separated model IDs or preset (all|llama|tiny|granite|qwen)
#                           Default: all
#   --cores LIST            Comma-separated core counts
#                           Default: 8,16,32
#   --workloads LIST        Comma-separated workloads (chat|code|summarization|rag)
#                           Default: chat (or per-model default_workloads)
#   --phase PHASE           Test phase (1|2|3|all)
#                           Default: 1 (Phase 1: baseline tests only)
#   --skip-models LIST      Comma-separated models to skip
#   --continue-on-error     Continue testing if a model/workload fails
#   --dry-run               Show what would run without executing
#   -h, --help              Show this help
#
# Model Presets:
#   all     - All 6 models with concurrent-load support (includes gated models)
#   llama   - Llama 3.2 models (1B, 3B) - GATED, requires HF_TOKEN
#   tiny    - TinyLlama 1.1B
#   granite - IBM Granite 3.2-2B
#   qwen    - Qwen3 0.6B
#
# Examples:
#   # Run all models, default workloads, all core counts (Phase 1)
#   export HF_TOKEN=hf_xxxxx  # For gated Llama models
#   ./run-concurrent-load-suite.sh
#
#   # Quick test with TinyLlama
#   ./run-concurrent-load-suite.sh --models tiny --cores 8 --workloads chat
#
#   # Test specific model
#   ./run-concurrent-load-suite.sh --models "meta-llama/Llama-3.2-1B-Instruct"
#
# ==============================================================================

set -euo pipefail

trap 'echo -e "\n\nInterrupted by user. Exiting..."; exit 130' SIGINT SIGTERM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
while [[ ! -d "${REPO_ROOT}/.git" ]] && [[ "${REPO_ROOT}" != "/" ]]; do
    REPO_ROOT="$(dirname "${REPO_ROOT}")"
done

if [[ ! -d "${REPO_ROOT}/.git" ]]; then
    echo "ERROR: Could not find repository root"
    exit 1
fi

cd "${REPO_ROOT}"

# All models from model-matrix.yaml with test_suites: concurrent-load
ALL_MODELS=(
    "meta-llama/Llama-3.2-1B-Instruct"
    "meta-llama/Llama-3.2-3B-Instruct"
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    "ibm-granite/granite-3.2-2b-instruct"
    "Qwen/Qwen3-0.6B"
    # Skip gpt-oss-20b (hypothetical 20B model - too large for typical CPU testing)
)

PRESET_LLAMA=(
    "meta-llama/Llama-3.2-1B-Instruct"
    "meta-llama/Llama-3.2-3B-Instruct"
)

PRESET_TINY=(
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
)

PRESET_GRANITE=(
    "ibm-granite/granite-3.2-2b-instruct"
)

PRESET_QWEN=(
    "Qwen/Qwen3-0.6B"
)

# Default configuration
MODELS_INPUT="all"
CORES_INPUT="8,16,32"
WORKLOADS_INPUT=""  # Empty = use per-model default_workloads
PHASE="1"
CONTINUE_ON_ERROR=false
DRY_RUN=false
SKIP_MODELS_INPUT=""

show_help() {
    sed -n '/^# ===/,/^set -/p' "$0" | sed '$d' | sed '1,3d;$d' | sed 's/^# //; s/^#//'
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --models)
            MODELS_INPUT="$2"
            shift 2
            ;;
        --cores)
            CORES_INPUT="$2"
            shift 2
            ;;
        --workloads)
            WORKLOADS_INPUT="$2"
            shift 2
            ;;
        --phase)
            PHASE="$2"
            shift 2
            ;;
        --skip-models)
            SKIP_MODELS_INPUT="$2"
            shift 2
            ;;
        --continue-on-error)
            CONTINUE_ON_ERROR=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Expand model presets
MODELS=()
MODELS_INPUT_LOWER=$(echo "$MODELS_INPUT" | tr '[:upper:]' '[:lower:]')
case "$MODELS_INPUT_LOWER" in
    all)
        MODELS=("${ALL_MODELS[@]}")
        ;;
    llama)
        MODELS=("${PRESET_LLAMA[@]}")
        ;;
    tiny)
        MODELS=("${PRESET_TINY[@]}")
        ;;
    granite)
        MODELS=("${PRESET_GRANITE[@]}")
        ;;
    qwen)
        MODELS=("${PRESET_QWEN[@]}")
        ;;
    *)
        IFS=',' read -ra MODELS <<< "$MODELS_INPUT"
        ;;
esac

# Parse skip list
SKIP_MODELS=()
if [[ -n "$SKIP_MODELS_INPUT" ]]; then
    IFS=',' read -ra SKIP_MODELS <<< "$SKIP_MODELS_INPUT"
fi

# Filter out skipped models
FINAL_MODELS=()
for model in "${MODELS[@]}"; do
    skip=false
    if [[ ${#SKIP_MODELS[@]} -gt 0 ]]; then
        for skip_model in "${SKIP_MODELS[@]}"; do
            if [[ "$model" == "$skip_model" ]]; then
                skip=true
                break
            fi
        done
    fi
    if [[ "$skip" == false ]]; then
        FINAL_MODELS+=("$model")
    fi
done

# Parse cores
IFS=',' read -ra CORES <<< "$CORES_INPUT"

# Parse workloads (empty = use model defaults)
WORKLOADS=()
if [[ -n "$WORKLOADS_INPUT" ]]; then
    IFS=',' read -ra WORKLOADS <<< "$WORKLOADS_INPUT"
else
    # Default: chat for all models
    WORKLOADS=("chat")
fi

# Calculate phase skip flags
SKIP_PHASE_1="false"
SKIP_PHASE_2="true"
SKIP_PHASE_3="true"

case "$PHASE" in
    1)
        SKIP_PHASE_1="false"
        SKIP_PHASE_2="true"
        SKIP_PHASE_3="true"
        ;;
    2)
        SKIP_PHASE_1="true"
        SKIP_PHASE_2="false"
        SKIP_PHASE_3="true"
        ;;
    3)
        SKIP_PHASE_1="true"
        SKIP_PHASE_2="true"
        SKIP_PHASE_3="false"
        ;;
    all)
        SKIP_PHASE_1="false"
        SKIP_PHASE_2="false"
        SKIP_PHASE_3="false"
        ;;
esac

echo "========================================="
echo "Upstream LLM Concurrent Load Test Suite"
echo "========================================="
echo "Models: ${#FINAL_MODELS[@]}"
echo "Cores: ${CORES[*]}"
echo "Workloads: ${WORKLOADS[*]}"
echo "Phase: $PHASE"
echo "Continue on error: $CONTINUE_ON_ERROR"
echo "Dry run: $DRY_RUN"
echo "========================================="
echo

TOTAL_TESTS=$((${#FINAL_MODELS[@]} * ${#CORES[@]} * ${#WORKLOADS[@]}))
CURRENT_TEST=0
FAILED_TESTS=0

for model in "${FINAL_MODELS[@]}"; do
    for cores in "${CORES[@]}"; do
        for workload in "${WORKLOADS[@]}"; do
            ((CURRENT_TEST++))

            echo "[$CURRENT_TEST/$TOTAL_TESTS] Testing: $model | $workload | ${cores} cores"

            CMD=(
                "ansible-playbook"
                "-i" "automation/test-execution/ansible/inventory/hosts.yml"
                "automation/test-execution/ansible/llm-benchmark-concurrent-load.yml"
                "-e" "test_model=$model"
                "-e" "base_workload=$workload"
                "-e" "requested_cores=$cores"
                "-e" "skip_phase_1=$SKIP_PHASE_1"
                "-e" "skip_phase_2=$SKIP_PHASE_2"
                "-e" "skip_phase_3=$SKIP_PHASE_3"
            )

            if [[ "$DRY_RUN" == true ]]; then
                echo "  DRY-RUN: ${CMD[*]}"
            else
                echo "  Running: ${CMD[*]}"
                if "${CMD[@]}"; then
                    echo "  ✓ Success"
                else
                    echo "  ✗ Failed"
                    ((FAILED_TESTS++))
                    if [[ "$CONTINUE_ON_ERROR" == false ]]; then
                        echo "Stopping due to failure (use --continue-on-error to continue)"
                        exit 1
                    fi
                fi
            fi
            echo
        done
    done
done

echo "========================================="
echo "Summary"
echo "========================================="
echo "Total tests: $TOTAL_TESTS"
echo "Failed: $FAILED_TESTS"
echo "Success rate: $(( (TOTAL_TESTS - FAILED_TESTS) * 100 / TOTAL_TESTS ))%"

if [[ $FAILED_TESTS -gt 0 ]]; then
    exit 1
fi
