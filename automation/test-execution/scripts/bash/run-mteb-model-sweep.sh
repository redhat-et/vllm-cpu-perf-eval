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
#   --task-preset PRESET    MTEB task preset (quick|comprehensive|full|etc)
#                           Default: quick
#   --vllm-mode MODE        vLLM execution mode (managed|dut-only|external)
#                           Default: managed (or VLLM_MODE / VLLM_ENDPOINT_MODE)
#   --endpoint URL          External vLLM endpoint (for external mode)
#   --cores NUM             Number of cores for vLLM (managed/dut-only)
#                           Default: 32
#   --vllm-cpus RANGE       Explicit CPU set for vLLM (e.g., 0-31)
#   --models LIST           Comma-separated models or preset (all|quick|small|medium|large)
#                           Default: all models
#   --skip-models LIST      Comma-separated list of models to skip
#   --dry-run               Show what would be run without executing
#   --continue-on-error     Continue testing other models if one fails
#   --yes                   Skip interactive confirmation prompt
#   --container-image IMG   MTEB container image (or set MTEB_CONTAINER_IMAGE)
#                           Default: quay.io/vllm-cpu-perf-eval/vllm-mteb:latest
#   -h, --help              Show this help message
#
# Environment Variables:
#   VLLM_MODE / VLLM_ENDPOINT_MODE   managed, dut-only, or external
#   VLLM_ENDPOINT_URL                External endpoint URL
#   VLLM_CONTAINER_IMAGE             vLLM/RHAIIS server image
#   MTEB_CONTAINER_IMAGE             MTEB runner container image
#   VLLM_CPUS                        Same as --vllm-cpus
#   HF_TOKEN                         HuggingFace token for gated models
#
# Examples:
#   # Quick smoke test on all models (default task preset: quick)
#   ./run-mteb-model-sweep.sh
#
#   # Full quality sweep via cpueval
#   ./cpueval --suite mteb --extra task_preset=full --vllm-cpus 0-31 --cores 32 \
#     --extra vllm_mode=dut-only
#
#   # DUT-only on a single host
#   export VLLM_MODE=dut-only
#   ./run-mteb-model-sweep.sh --cores 32 --vllm-cpus 0-31
#
#   # External vLLM endpoint
#   ./run-mteb-model-sweep.sh --vllm-mode external \
#     --endpoint http://production-vllm:8000
#
# ==============================================================================

set -euo pipefail

trap 'echo -e "\n\nInterrupted by user. Exiting..."; exit 130' SIGINT SIGTERM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
if command -v git >/dev/null 2>&1 && GIT_ROOT="$(git -C "${SCRIPT_DIR}" rev-parse --show-toplevel 2>/dev/null)"; then
    REPO_ROOT="${GIT_ROOT}"
else
    while [[ ! -d "${REPO_ROOT}/.git" && ! -f "${REPO_ROOT}/.git" ]] && [[ "${REPO_ROOT}" != "/" ]]; do
        REPO_ROOT="$(dirname "${REPO_ROOT}")"
    done
fi

if [[ ! -f "${REPO_ROOT}/automation/test-execution/ansible/mteb-benchmark.yml" ]]; then
    echo "ERROR: Not in repository root or structure has changed"
    exit 1
fi

export ANSIBLE_CONFIG="${REPO_ROOT}/automation/test-execution/ansible/ansible.cfg"

# Default configuration
TASK_PRESET="quick"
VLLM_MODE="${VLLM_MODE:-${VLLM_ENDPOINT_MODE:-managed}}"
ENDPOINT_URL="${VLLM_ENDPOINT_URL:-}"
REQUESTED_CORES="${REQUESTED_CORES:-32}"
VLLM_CPUS="${VLLM_CPUS:-}"
CONTINUE_ON_ERROR=false
DRY_RUN=false
ASSUME_YES=false
MODELS_INPUT=""
CONTAINER_IMAGE="${MTEB_CONTAINER_IMAGE:-quay.io/vllm-cpu-perf-eval/vllm-mteb:latest}"

PRESET_QUICK=(
    "RedHatAI/all-MiniLM-L6-v2"
)

PRESET_SMALL=(
    "RedHatAI/all-MiniLM-L6-v2"
    "RedHatAI/granite-embedding-english-r2"
)

PRESET_MEDIUM=(
    "RedHatAI/nomic-embed-text-v1.5"
    "RedHatAI/embeddinggemma-300m"
)

PRESET_LARGE=(
    "RedHatAI/Qwen3-Embedding-8B"
)

ALL_MODELS=(
    "RedHatAI/all-MiniLM-L6-v2"
    "RedHatAI/nomic-embed-text-v1.5"
    "RedHatAI/granite-embedding-english-r2"
    "RedHatAI/embeddinggemma-300m"
    "RedHatAI/Qwen3-Embedding-8B"
)

MODELS_TO_TEST=()
MODELS_TO_SKIP=()

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

show_help() {
    sed -n '/^# ===/,/^# ===/p' "$0" | sed 's/^# //; s/^#//'
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --task-preset)      TASK_PRESET="$2"; shift 2 ;;
        --vllm-mode)        VLLM_MODE="$2"; shift 2 ;;
        --endpoint)         ENDPOINT_URL="$2"; shift 2 ;;
        --cores)            REQUESTED_CORES="$2"; shift 2 ;;
        --vllm-cpus)        VLLM_CPUS="$2"; shift 2 ;;
        --models)           MODELS_INPUT="$2"; shift 2 ;;
        --skip-models)      IFS=',' read -ra MODELS_TO_SKIP <<< "$2"; shift 2 ;;
        --dry-run)          DRY_RUN=true; shift ;;
        --continue-on-error) CONTINUE_ON_ERROR=true; shift ;;
        --container-image)  CONTAINER_IMAGE="$2"; shift 2 ;;
        --yes)              ASSUME_YES=true; shift ;;
        -h|--help)          show_help; exit 0 ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

if [[ "${VLLM_MODE}" == "external" && -z "${ENDPOINT_URL}" ]]; then
    log_error "External mode requires --endpoint URL or VLLM_ENDPOINT_URL"
    exit 1
fi

if [[ "${VLLM_MODE}" != "managed" && "${VLLM_MODE}" != "external" && "${VLLM_MODE}" != "dut-only" ]]; then
    log_error "Invalid vllm-mode: ${VLLM_MODE}. Must be managed, dut-only, or external"
    exit 1
fi

resolve_models() {
    local input="$1"
    case "${input}" in
        all|"")
            MODELS_TO_TEST=("${ALL_MODELS[@]}")
            ;;
        quick)
            MODELS_TO_TEST=("${PRESET_QUICK[@]}")
            ;;
        small)
            MODELS_TO_TEST=("${PRESET_SMALL[@]}")
            ;;
        medium)
            MODELS_TO_TEST=("${PRESET_MEDIUM[@]}")
            ;;
        large)
            MODELS_TO_TEST=("${PRESET_LARGE[@]}")
            ;;
        *)
            IFS=',' read -ra MODELS_TO_TEST <<< "${input}"
            ;;
    esac
}

if [[ -n "${MODELS_INPUT}" ]]; then
    resolve_models "${MODELS_INPUT}"
elif [[ ${#MODELS_TO_TEST[@]} -eq 0 ]]; then
    MODELS_TO_TEST=("${ALL_MODELS[@]}")
fi

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

if [[ ${#MODELS_TO_TEST[@]} -eq 0 ]]; then
    log_error "No models selected after applying filters"
    exit 1
fi

log_info "MTEB Model Sweep Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Task Preset:     ${TASK_PRESET}"
echo "MTEB Image:      ${CONTAINER_IMAGE}"
echo "vLLM Mode:       ${VLLM_MODE}"
if [[ "${VLLM_MODE}" == "external" ]]; then
    echo "Endpoint URL:    ${ENDPOINT_URL}"
else
    echo "Cores:           ${REQUESTED_CORES}"
    [[ -n "${VLLM_CPUS}" ]] && echo "vLLM CPUs:       ${VLLM_CPUS}"
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

if [[ "${DRY_RUN}" == false && "${ASSUME_YES}" == false && -t 0 ]]; then
    read -p "Proceed with MTEB sweep? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
fi

RESULTS_FILE="${SCRIPT_DIR}/mteb-sweep-results-$(date +%Y%m%d-%H%M%S).log"
SUCCESSFUL_MODELS=()
FAILED_MODELS=()

run_mteb_test() {
    local model="$1"

    log_info "Starting MTEB test for: ${model}"

    local cmd=(
        ansible-playbook
        -i "automation/test-execution/ansible/inventory/hosts.yml"
        "automation/test-execution/ansible/mteb-benchmark.yml"
        -e "test_model=${model}"
        -e "mteb_task_preset=${TASK_PRESET}"
        -e "vllm_mode=${VLLM_MODE}"
    )

    if [[ "${VLLM_MODE}" == "managed" || "${VLLM_MODE}" == "dut-only" ]]; then
        cmd+=(-e "requested_cores=${REQUESTED_CORES}")
        [[ -n "${VLLM_CPUS}" ]] && cmd+=(-e "vllm_cpus=${VLLM_CPUS}")
    else
        cmd+=(-e "vllm_endpoint_url=${ENDPOINT_URL}")
    fi

    if [[ -n "${VLLM_CONTAINER_NAME:-}" ]]; then
        cmd+=(-e "vllm_container_name=${VLLM_CONTAINER_NAME}")
    fi
    if [[ -n "${VLLM_PORT:-}" ]]; then
        cmd+=(-e "vllm_port=${VLLM_PORT}")
    fi
    if [[ -n "${VLLM_NUMA_NODES:-}" ]]; then
        cmd+=(-e "vllm_numa_nodes=${VLLM_NUMA_NODES}")
    fi

    if [[ "${model}" == *"nomic-embed-text"* ]]; then
        cmd+=(-e "trust_remote_code=true")
    fi

    if [[ "${DRY_RUN}" == true ]]; then
        log_info "DRY RUN: Would execute:"
        echo "  cd ${REPO_ROOT} && VLLM_MODE=${VLLM_MODE} MTEB_CONTAINER_IMAGE=${CONTAINER_IMAGE} ${cmd[*]}"
        return 0
    fi

    local start_time
    start_time=$(date +%s)
    if (
        cd "${REPO_ROOT}" &&
        VLLM_MODE="${VLLM_MODE}" \
        MTEB_CONTAINER_IMAGE="${CONTAINER_IMAGE}" \
        "${cmd[@]}"
    ) 2>&1 | tee -a "${RESULTS_FILE}"; then
        local end_time duration
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        log_success "✓ ${model} completed in ${duration}s"
        SUCCESSFUL_MODELS+=("${model}")
        return 0
    fi

    local end_time duration
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    log_error "✗ ${model} failed after ${duration}s"
    FAILED_MODELS+=("${model}")
    return 1
}

log_info "Starting MTEB model sweep at $(date)"
echo ""

for model in "${MODELS_TO_TEST[@]}"; do
    if ! run_mteb_test "${model}"; then
        if [[ "${CONTINUE_ON_ERROR}" == false ]]; then
            log_error "Test failed for ${model}, aborting sweep"
            exit 1
        fi
    fi
    echo ""
done

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
    RESULTS_DIR="${REPO_ROOT}/results/mteb"
    if [[ -d "${RESULTS_DIR}" ]]; then
        log_info "Results location: ${RESULTS_DIR}"
        log_info "View in dashboard or run:"
        echo "  cd ${REPO_ROOT}/automation/test-execution/dashboard-examples/vllm_dashboard"
        echo "  streamlit run Home.py"
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ ${#FAILED_MODELS[@]} -gt 0 ]]; then
    exit 1
fi

exit 0
