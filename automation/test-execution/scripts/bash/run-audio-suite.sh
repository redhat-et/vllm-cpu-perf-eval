#!/bin/bash
# ==============================================================================
# Audio Model Benchmarking Suite
# ==============================================================================
# Run audio benchmarks (Whisper ASR) across models, scenarios, and core counts.
#
# Prerequisites:
#   - Models defined in models/audio-models/model-matrix.yaml
#   - vLLM v0.20.0 or v0.25.1 with VLLM_USE_V2_MODEL_RUNNER=0 workaround
#
# Usage:
#   ./run-audio-suite.sh [options]
#
# Options:
#   --models LIST           Comma-separated models or preset (all|whisper-small|whisper-tiny)
#                           Default: all
#   --scenarios LIST        Comma-separated scenarios or "all"
#                           Default: transcription-throughput
#   --cores LIST            Comma-separated core counts
#                           Default: 32
#   --skip-models LIST      Comma-separated models to skip
#   --continue-on-error     Continue if a test fails
#   --dry-run               Show commands without running
#   -h, --help              Show this help
#
# Model Presets:
#   all            - All Whisper models (tiny, small, medium)
#   whisper-tiny   - openai/whisper-tiny
#   whisper-small  - openai/whisper-small
#   whisper-medium - openai/whisper-medium
#
# Scenarios:
#   transcription-throughput, transcription-latency, audio-duration-scaling,
#   constant-rate-stress, format-comparison, transcription-quality, quick-test
#
# Examples:
#   # Run all Whisper models, throughput scenario, 32 cores
#   ./run-audio-suite.sh
#
#   # Quick test
#   ./run-audio-suite.sh --models whisper-tiny --scenarios quick-test --cores 32
#
#   # Full matrix
#   ./run-audio-suite.sh --models all --scenarios all --cores "8,16,32"
#
# ==============================================================================

set -euo pipefail

trap 'echo -e "\n\nInterrupted. Exiting..."; exit 130' SIGINT SIGTERM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
while [[ ! -d "${REPO_ROOT}/.git" ]] && [[ "${REPO_ROOT}" != "/" ]]; do
    REPO_ROOT="$(dirname "${REPO_ROOT}")"
done

cd "${REPO_ROOT}"

# Whisper models with non-empty test_scenarios
ALL_MODELS=(
    "openai/whisper-tiny"
    "openai/whisper-small"
    "openai/whisper-medium"
)

ALL_SCENARIOS=(
    "transcription-throughput"
    "transcription-latency"
    "audio-duration-scaling"
    "constant-rate-stress"
    "format-comparison"
    "transcription-quality"
    "quick-test"
)

# Defaults
MODELS_INPUT="all"
SCENARIOS_INPUT="transcription-throughput"
CORES_INPUT="32"
SKIP_MODELS_INPUT=""
CONTINUE_ON_ERROR=false
DRY_RUN=false

show_help() {
    sed -n '/^# ===/,/^set -/p' "$0" | sed '$d' | sed '1,3d;$d' | sed 's/^# //; s/^#//'
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --models) MODELS_INPUT="$2"; shift 2 ;;
        --scenarios) SCENARIOS_INPUT="$2"; shift 2 ;;
        --cores) CORES_INPUT="$2"; shift 2 ;;
        --skip-models) SKIP_MODELS_INPUT="$2"; shift 2 ;;
        --continue-on-error) CONTINUE_ON_ERROR=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown: $1"; show_help; exit 1 ;;
    esac
done

# Expand models
MODELS=()
MODELS_LOWER=$(echo "$MODELS_INPUT" | tr '[:upper:]' '[:lower:]')
case "$MODELS_LOWER" in
    all) MODELS=("${ALL_MODELS[@]}") ;;
    whisper-tiny) MODELS=("openai/whisper-tiny") ;;
    whisper-small) MODELS=("openai/whisper-small") ;;
    whisper-medium) MODELS=("openai/whisper-medium") ;;
    *) IFS=',' read -ra MODELS <<< "$MODELS_INPUT" ;;
esac

# Expand scenarios
SCENARIOS=()
SCENARIOS_LOWER=$(echo "$SCENARIOS_INPUT" | tr '[:upper:]' '[:lower:]')
if [[ "$SCENARIOS_LOWER" == "all" ]]; then
    SCENARIOS=("${ALL_SCENARIOS[@]}")
else
    IFS=',' read -ra SCENARIOS <<< "$SCENARIOS_INPUT"
fi

# Parse cores
IFS=',' read -ra CORES <<< "$CORES_INPUT"

# Filter skipped
SKIP_MODELS=()
if [[ -n "$SKIP_MODELS_INPUT" ]]; then
    IFS=',' read -ra SKIP_MODELS <<< "$SKIP_MODELS_INPUT"
fi

FINAL_MODELS=()
for m in "${MODELS[@]}"; do
    skip=false
    if [[ ${#SKIP_MODELS[@]} -gt 0 ]]; then
        for sm in "${SKIP_MODELS[@]}"; do
            [[ "$m" == "$sm" ]] && skip=true && break
        done
    fi
    [[ "$skip" == false ]] && FINAL_MODELS+=("$m")
done

echo "==============================="
echo "Audio Benchmarking Suite"
echo "==============================="
echo "Models: ${#FINAL_MODELS[@]}"
echo "Scenarios: ${#SCENARIOS[@]}"
echo "Cores: ${CORES[*]}"
echo "Dry run: $DRY_RUN"
echo "==============================="
echo

TOTAL=$((${#FINAL_MODELS[@]} * ${#SCENARIOS[@]} * ${#CORES[@]}))

if [[ $TOTAL -eq 0 ]]; then
    echo "Error: Empty benchmark matrix (0 tests to run)"
    echo "All models may have been filtered out by --models and --skip-models"
    exit 1
fi

CURRENT=0
FAILED=0

for model in "${FINAL_MODELS[@]}"; do
    for scenario in "${SCENARIOS[@]}"; do
        for cores in "${CORES[@]}"; do
            ((++CURRENT))
            echo "[$CURRENT/$TOTAL] $model | $scenario | ${cores} cores"

            CMD=(
                "ansible-playbook"
                "-i" "automation/test-execution/ansible/inventory/hosts.yml"
                "automation/test-execution/ansible/audio-benchmark.yml"
                "-e" "test_model=$model"
                "-e" "test_scenario=$scenario"
                "-e" "requested_cores=$cores"
                "-e" '{"vllm_env_vars": {"VLLM_USE_V2_MODEL_RUNNER": "0"}}'
            )

            # Parallel instance overrides — set env vars to run multiple instances
            # simultaneously on the same host (each with its own container, port, NUMA nodes):
            #   VLLM_CONTAINER_NAME=vllm-0 VLLM_PORT=8000 VLLM_NUMA_NODES="0,1" ./run-audio-suite.sh
            # See README "VLLM_NUMA_NODE vs VLLM_NUMA_NODES" for the distinction between the two.
            if [[ -n "${VLLM_CONTAINER_NAME:-}" ]]; then
                CMD+=(-e "vllm_container_name=${VLLM_CONTAINER_NAME}")
            fi
            if [[ -n "${VLLM_PORT:-}" ]]; then
                CMD+=(-e "vllm_port=${VLLM_PORT}")
            fi
            if [[ -n "${VLLM_NUMA_NODES:-}" ]]; then
                CMD+=(-e "vllm_numa_nodes=${VLLM_NUMA_NODES}")
            fi
            if [[ -n "${VLLM_NUMA_NODE:-}" ]]; then
                CMD+=(-e "vllm_numa_node=${VLLM_NUMA_NODE}")
            fi

            if [[ "$DRY_RUN" == true ]]; then
                echo "  DRY-RUN: ${CMD[*]}"
            else
                if "${CMD[@]}"; then
                    echo "  ✓ Success"
                else
                    echo "  ✗ Failed"
                    ((++FAILED))
                    if [[ "$CONTINUE_ON_ERROR" == false ]]; then
                        echo "Stopping (use --continue-on-error)"
                        exit 1
                    fi
                fi
            fi
            echo
        done
    done
done

echo "==============================="
echo "Summary: $((TOTAL - FAILED))/$TOTAL passed"
[[ $FAILED -gt 0 ]] && exit 1
exit 0
