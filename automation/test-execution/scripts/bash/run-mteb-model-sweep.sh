#!/bin/bash
# ==============================================================================
# MTEB Model Sweep - Run Quality Tests on All Embedding Models
# ==============================================================================
# This script runs MTEB quality benchmarks on all supported embedding models
# from the RedHatAI Intel Xeon-compatible collection.
#
# Usage:
#   ./run-mteb-model-sweep.sh [options]
#
# Options:
#   --task-preset PRESET    MTEB task preset (quick|comprehensive|retrieval|etc)
#                           Default: quick
#   --vllm-mode MODE        vLLM execution mode (managed|external)
#                           Default: managed
#   --endpoint URL          External vLLM endpoint (for external mode)
#   --cores NUM             Number of cores for vLLM (managed mode)
#                           Default: 4 (most efficient for quality tests)
#   --models LIST           Comma-separated list of models to test
#                           Default: all models
#   --skip-models LIST      Comma-separated list of models to skip
#   --dry-run               Show what would be run without executing
#   --continue-on-error     Continue testing other models if one fails
#   --container-image IMG   Container image to use (or set MTEB_CONTAINER_IMAGE)
#                           Default: quay.io/vllm-cpu-perf-eval/vllm-mteb:latest
#   -h, --help              Show this help message
#
# Examples:
#   # Run quick tests on all models
#   ./run-mteb-model-sweep.sh
#
#   # Run comprehensive tests on all models
#   ./run-mteb-model-sweep.sh --task-preset comprehensive
#
#   # Test only specific models
#   ./run-mteb-model-sweep.sh \
#     --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2"
#
#   # Skip large models
#   ./run-mteb-model-sweep.sh --skip-models "RedHatAI/Qwen3-Embedding-8B"
#
#   # Use external vLLM endpoint
#   ./run-mteb-model-sweep.sh \
#     --vllm-mode external \
#     --endpoint http://production-vllm:8000
#
#   # Use local container image instead of quay.io
#   export MTEB_CONTAINER_IMAGE=vllm-mteb:latest
#   ./run-mteb-model-sweep.sh --task-preset quick
#
# ==============================================================================

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAYBOOK_DIR="${SCRIPT_DIR}/../../ansible"

# Default configuration
TASK_PRESET="quick"
VLLM_MODE="managed"
ENDPOINT_URL=""
REQUESTED_CORES=4  # Use most efficient core count for quality tests
CONTINUE_ON_ERROR=false
DRY_RUN=false
# Use environment variable or default to quay.io
CONTAINER_IMAGE="${MTEB_CONTAINER_IMAGE:-quay.io/vllm-cpu-perf-eval/vllm-mteb:latest}"

# All supported embedding models
ALL_MODELS=(
    "RedHatAI/all-MiniLM-L6-v2"
    "RedHatAI/nomic-embed-text-v1.5"
    "RedHatAI/granite-embedding-english-r2"
    "RedHatAI/embeddinggemma-300m"
    "RedHatAI/Qwen3-Embedding-8B"
)

MODELS_TO_TEST=()
MODELS_TO_SKIP=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

show_help() {
    sed -n '/^# ===/,/^# ===/p' "$0" | sed 's/^# //; s/^#//'
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --task-preset)
            TASK_PRESET="$2"
            shift 2
            ;;
        --vllm-mode)
            VLLM_MODE="$2"
            shift 2
            ;;
        --endpoint)
            ENDPOINT_URL="$2"
            shift 2
            ;;
        --cores)
            REQUESTED_CORES="$2"
            shift 2
            ;;
        --models)
            IFS=',' read -ra MODELS_TO_TEST <<< "$2"
            shift 2
            ;;
        --skip-models)
            IFS=',' read -ra MODELS_TO_SKIP <<< "$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --continue-on-error)
            CONTINUE_ON_ERROR=true
            shift
            ;;
        --container-image)
            CONTAINER_IMAGE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate configuration
if [[ "${VLLM_MODE}" == "external" && -z "${ENDPOINT_URL}" ]]; then
    log_error "External mode requires --endpoint URL"
    exit 1
fi

if [[ "${VLLM_MODE}" != "managed" && "${VLLM_MODE}" != "external" ]]; then
    log_error "Invalid vllm-mode: ${VLLM_MODE}. Must be 'managed' or 'external'"
    exit 1
fi

# Determine which models to test
if [[ ${#MODELS_TO_TEST[@]} -eq 0 ]]; then
    MODELS_TO_TEST=("${ALL_MODELS[@]}")
fi

# Filter out skipped models
if [[ ${#MODELS_TO_SKIP[@]} -gt 0 ]]; then
    FILTERED_MODELS=()
    for model in "${MODELS_TO_TEST[@]}"; do
        skip=false
        for skip_model in "${MODELS_TO_SKIP[@]}"; do
            if [[ "${model}" == "${skip_model}" ]]; then
                skip=true
                break
            fi
        done
        if [[ "${skip}" == false ]]; then
            FILTERED_MODELS+=("${model}")
        fi
    done
    MODELS_TO_TEST=("${FILTERED_MODELS[@]}")
fi

# Display configuration
log_info "MTEB Model Sweep Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Task Preset:     ${TASK_PRESET}"
echo "Container Image: ${CONTAINER_IMAGE}"
echo "vLLM Mode:       ${VLLM_MODE}"
if [[ "${VLLM_MODE}" == "external" ]]; then
    echo "Endpoint URL:    ${ENDPOINT_URL}"
else
    echo "Cores:           ${REQUESTED_CORES}"
fi
echo "Continue on err: ${CONTINUE_ON_ERROR}"
echo "Dry Run:         ${DRY_RUN}"
echo ""
echo "Models to test (${#MODELS_TO_TEST[@]}):"
for model in "${MODELS_TO_TEST[@]}"; do
    echo "  - ${model}"
done
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Confirm execution
if [[ "${DRY_RUN}" == false ]]; then
    read -p "Proceed with MTEB sweep? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
fi

# Results tracking
RESULTS_FILE="${SCRIPT_DIR}/mteb-sweep-results-$(date +%Y%m%d-%H%M%S).log"
SUCCESSFUL_MODELS=()
FAILED_MODELS=()

# Run MTEB test for a single model
run_mteb_test() {
    local model="$1"
    local model_safe="${model//\//__}"

    log_info "Starting MTEB test for: ${model}"

    # Build ansible-playbook command
    local cmd=(
        ansible-playbook
        -i inventory/hosts.yml
        mteb-benchmark.yml
        -e "test_model=${model}"
        -e "mteb_task_preset=${TASK_PRESET}"
        -e "vllm_mode=${VLLM_MODE}"
    )

    if [[ "${VLLM_MODE}" == "managed" ]]; then
        cmd+=(-e "requested_cores=${REQUESTED_CORES}")
    else
        cmd+=(-e "vllm_endpoint_url=${ENDPOINT_URL}")
    fi

    # Add trust_remote_code only for models that require it
    if [[ "${model}" == *"nomic-embed-text"* ]]; then
        cmd+=(-e "trust_remote_code=true")
    fi

    if [[ "${DRY_RUN}" == true ]]; then
        log_info "DRY RUN: Would execute:"
        echo "  cd ${PLAYBOOK_DIR} && ${cmd[*]}"
        return 0
    fi

    # Execute (change to playbook directory to ensure ansible.cfg is used)
    local start_time=$(date +%s)
    if (cd "${PLAYBOOK_DIR}" && MTEB_CONTAINER_IMAGE="${CONTAINER_IMAGE}" "${cmd[@]}") 2>&1 | tee -a "${RESULTS_FILE}"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "✓ ${model} completed in ${duration}s"
        SUCCESSFUL_MODELS+=("${model}")
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_error "✗ ${model} failed after ${duration}s"
        FAILED_MODELS+=("${model}")
        return 1
    fi
}

# Main execution loop
log_info "Starting MTEB model sweep at $(date)"
echo ""

# Sequential execution
for model in "${MODELS_TO_TEST[@]}"; do
    if ! run_mteb_test "${model}"; then
        if [[ "${CONTINUE_ON_ERROR}" == false ]]; then
            log_error "Test failed for ${model}, aborting sweep"
            exit 1
        fi
    fi
    echo ""
done

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "MTEB Model Sweep Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Completed at: $(date)"
echo "Total models: ${#MODELS_TO_TEST[@]}"
echo "Successful:   ${#SUCCESSFUL_MODELS[@]}"
echo "Failed:       ${#FAILED_MODELS[@]}"
echo ""

if [[ ${#SUCCESSFUL_MODELS[@]} -gt 0 ]]; then
    log_success "Successful models:"
    for model in "${SUCCESSFUL_MODELS[@]}"; do
        echo "  ✓ ${model}"
    done
    echo ""
fi

if [[ ${#FAILED_MODELS[@]} -gt 0 ]]; then
    log_error "Failed models:"
    for model in "${FAILED_MODELS[@]}"; do
        echo "  ✗ ${model}"
    done
    echo ""
fi

if [[ "${DRY_RUN}" == false ]]; then
    echo "Detailed log: ${RESULTS_FILE}"
    echo ""

    # Check results directory
    RESULTS_DIR="${PLAYBOOK_DIR}/../../../results/mteb"
    if [[ -d "${RESULTS_DIR}" ]]; then
        log_info "Results location: ${RESULTS_DIR}"
        log_info "View in dashboard or run:"
        echo "  cd ${PLAYBOOK_DIR}/../dashboard-examples/vllm_dashboard"
        echo "  streamlit run Home.py"
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Exit with appropriate status
if [[ ${#FAILED_MODELS[@]} -gt 0 ]]; then
    exit 1
else
    exit 0
fi
