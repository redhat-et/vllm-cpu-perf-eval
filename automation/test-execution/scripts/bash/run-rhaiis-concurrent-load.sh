#!/bin/bash
# ==============================================================================
# RHAIIS LLM Concurrent Load Test Suite
# ==============================================================================
# Run concurrent load benchmarks on RHAIIS quantized models across different
# core counts and workload types.
#
# Prerequisites:
#   - RHAIIS vLLM container image must be pulled on the DUT:
#     podman pull registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
#   - Set VLLM_CONTAINER_IMAGE to use custom image:
#     export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
#
# Usage:
#   ./run-rhaiis-concurrent-load.sh [options]
#
# Options:
#   --models LIST           Comma-separated models or preset (all|llama|qwen|tiny)
#                           Default: all
#   --cores LIST            Comma-separated core counts
#                           Default: 8,16,32
#   --workloads LIST        Comma-separated workloads (chat|code|summarization|rag)
#                           Default: chat,code,summarization,rag
#   --phase PHASE           Test phase (1|2|3|all)
#                           Default: 1 (Phase 1: baseline tests only)
#   --vllm-cpu-start NUM    Starting CPU for vLLM (for socket separation)
#                           Env: VLLM_CPU_START
#   --vllm-numa-node NUM    NUMA node for vLLM (for socket separation)
#                           Env: VLLM_NUMA_NODE
#   --guidellm-cpus RANGE   CPU range for GuideLLM (e.g., 0-31)
#                           Env: GUIDELLM_CPUS
#   --guidellm-numa-node NUM NUMA node for GuideLLM (for socket separation)
#                           Env: GUIDELLM_NUMA_NODE
#   --skip-models LIST      Comma-separated models to skip
#   --continue-on-error     Continue testing if a model/workload fails
#   --dry-run               Show what would run without executing
#   -h, --help              Show this help
#
# Model Presets:
#   all     - All 5 RHAIIS quantized models
#   llama   - Llama models only (3.1-8B w4a16, w8a8)
#   qwen    - Qwen models only (8B w4a16, W8A8-INT8)
#   tiny    - TinyLlama pruned model only
#
# Examples:
#   # Run all models, all workloads, all core counts (Phase 1 only)
#   ./run-rhaiis-concurrent-load.sh
#
#   # Test specific models with specific workloads
#   ./run-rhaiis-concurrent-load.sh \
#     --models "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16" \
#     --workloads "chat,rag" \
#     --cores "16,32"
#
#   # Quick test on 8 cores
#   ./run-rhaiis-concurrent-load.sh --models tiny --cores 8 --workloads chat
#
#   # Test Llama models only
#   ./run-rhaiis-concurrent-load.sh --models llama --cores 16
#
#   # Use custom RHAIIS container image
#   export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0
#   ./run-rhaiis-concurrent-load.sh
#
#   # Socket separation for 2-socket systems (recommended for performance)
#   ./run-rhaiis-concurrent-load.sh \
#     --vllm-cpu-start 64 \
#     --vllm-numa-node 1 \
#     --guidellm-cpus 0-31 \
#     --guidellm-numa-node 0
#
# ==============================================================================

set -euo pipefail

# Handle Ctrl+C gracefully
trap 'echo -e "\n\nInterrupted by user. Exiting..."; exit 130' SIGINT SIGTERM

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAYBOOK_DIR="${SCRIPT_DIR}/../../ansible"

# Stay in script directory (like embedding script does)
# Use relative paths to playbook files

# Force Ansible to use consistent output formatting
export ANSIBLE_STDOUT_CALLBACK=default
export ANSIBLE_FORCE_COLOR=false

# All supported RHAIIS LLM models
ALL_MODELS=(
    "RedHatAI/Qwen3-8B-quantized.w4a16"
    "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16"
    "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
    "RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4"
    "RedHatAI/Qwen3-8B-W8A8-INT8"
)

# Model presets
PRESET_LLAMA=(
    "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16"
    "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
)

PRESET_QWEN=(
    "RedHatAI/Qwen3-8B-quantized.w4a16"
    "RedHatAI/Qwen3-8B-W8A8-INT8"
)

PRESET_TINY=(
    "RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4"
)

# Default configuration
MODELS_INPUT="all"
CORES_INPUT="8,16,32"
WORKLOADS_INPUT="chat,code,summarization,rag"
PHASE="1"
CONTINUE_ON_ERROR=false
DRY_RUN=false
SKIP_MODELS_INPUT=""

# NUMA/CPU pinning defaults (for socket separation)
# Override with environment variables or command line options
VLLM_CPU_START="${VLLM_CPU_START:-}"
VLLM_NUMA_NODE="${VLLM_NUMA_NODE:-}"
GUIDELLM_CPUS="${GUIDELLM_CPUS:-}"
GUIDELLM_NUMA_NODE="${GUIDELLM_NUMA_NODE:-}"

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
        --vllm-cpu-start)
            VLLM_CPU_START="$2"
            shift 2
            ;;
        --vllm-numa-node)
            VLLM_NUMA_NODE="$2"
            shift 2
            ;;
        --guidellm-cpus)
            GUIDELLM_CPUS="$2"
            shift 2
            ;;
        --guidellm-numa-node)
            GUIDELLM_NUMA_NODE="$2"
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
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Parse models
MODELS=()
case "${MODELS_INPUT}" in
    all)
        MODELS=("${ALL_MODELS[@]}")
        ;;
    llama)
        MODELS=("${PRESET_LLAMA[@]}")
        ;;
    qwen)
        MODELS=("${PRESET_QWEN[@]}")
        ;;
    tiny)
        MODELS=("${PRESET_TINY[@]}")
        ;;
    *)
        IFS=',' read -ra MODELS <<< "${MODELS_INPUT}"
        ;;
esac

# Parse core counts
IFS=',' read -ra CORE_COUNTS <<< "${CORES_INPUT}"

# Parse workloads
IFS=',' read -ra WORKLOADS <<< "${WORKLOADS_INPUT}"

# Parse skip models
SKIP_MODELS=()
if [[ -n "${SKIP_MODELS_INPUT}" ]]; then
    IFS=',' read -ra SKIP_MODELS <<< "${SKIP_MODELS_INPUT}"
fi

# Filter out skipped models
if [[ ${#SKIP_MODELS[@]} -gt 0 ]]; then
    FILTERED_MODELS=()
    for model in "${MODELS[@]}"; do
        skip=false
        for skip_model in "${SKIP_MODELS[@]}"; do
            if [[ "${model}" == "${skip_model}" ]]; then
                skip=true
                break
            fi
        done
        if [[ "${skip}" == false ]]; then
            FILTERED_MODELS+=("${model}")
        fi
    done
    MODELS=("${FILTERED_MODELS[@]}")
fi

# Validate phase
if [[ ! "${PHASE}" =~ ^[123]$|^all$ ]]; then
    log_error "Invalid phase: ${PHASE}"
    log_error "Must be: 1, 2, 3, or all"
    exit 1
fi

# Validate workloads
for workload in "${WORKLOADS[@]}"; do
    if [[ ! "${workload}" =~ ^(chat|code|summarization|rag)$ ]]; then
        log_error "Invalid workload: ${workload}"
        log_error "Supported: chat, code, summarization, rag"
        exit 1
    fi
done

# Check for LD_PRELOAD (CRITICAL for RHAIIS performance)
if [ -z "${LD_PRELOAD:-}" ]; then
    log_error "LD_PRELOAD is not set!"
    log_error ""
    log_error "⚠️  CRITICAL: For optimal RHAIIS performance, you MUST set:"
    log_error "  export LD_PRELOAD=/usr/lib64/libomp.so"
    log_error ""
    log_error "Without this, you will see significantly degraded latency (5-10x slower)."
    log_error ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted. Please set LD_PRELOAD and try again."
        exit 0
    fi
    log_warning "Continuing without LD_PRELOAD - performance will be poor!"
    echo ""
fi

# Check for RHAIIS vLLM container image
if [ -z "${VLLM_CONTAINER_IMAGE:-}" ]; then
    log_warning "VLLM_CONTAINER_IMAGE not set."
    log_warning "Using default image. For RHAIIS testing, set:"
    log_warning "  export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0"
    echo ""
else
    log_info "Using RHAIIS vLLM image: ${VLLM_CONTAINER_IMAGE}"
    log_info "LD_PRELOAD: ${LD_PRELOAD:-NOT SET}"
    echo ""
fi

# Display configuration
echo "=========================================="
echo "RHAIIS LLM Concurrent Load Test Suite"
echo "=========================================="
echo "Models (${#MODELS[@]}):"
for model in "${MODELS[@]}"; do
    echo "  - ${model}"
done
echo ""
echo "Core counts: ${CORE_COUNTS[*]}"
echo "Workloads: ${WORKLOADS[*]}"
echo "Phase: ${PHASE}"
echo ""
echo "NUMA/CPU Configuration:"
if [[ -n "${VLLM_CPU_START}" ]]; then
    echo "  vLLM CPU start: ${VLLM_CPU_START}"
else
    echo "  vLLM CPU start: auto-detect"
fi
if [[ -n "${VLLM_NUMA_NODE}" ]]; then
    echo "  vLLM NUMA node: ${VLLM_NUMA_NODE}"
else
    echo "  vLLM NUMA node: auto-detect"
fi
if [[ -n "${GUIDELLM_CPUS}" ]]; then
    echo "  GuideLLM CPUs: ${GUIDELLM_CPUS}"
else
    echo "  GuideLLM CPUs: auto-detect"
fi
if [[ -n "${GUIDELLM_NUMA_NODE}" ]]; then
    echo "  GuideLLM NUMA node: ${GUIDELLM_NUMA_NODE}"
else
    echo "  GuideLLM NUMA node: auto-detect"
fi
echo ""
echo "Continue on error: ${CONTINUE_ON_ERROR}"
echo "Dry run: ${DRY_RUN}"
echo "=========================================="
echo ""

# Calculate total tests
TOTAL_TESTS=$((${#MODELS[@]} * ${#CORE_COUNTS[@]} * ${#WORKLOADS[@]}))
echo "Total test combinations: ${TOTAL_TESTS}"
echo ""

# Confirm execution
if [[ "${DRY_RUN}" == false ]]; then
    read -p "Proceed with test suite? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
fi

# Track results
CURRENT_TEST=0
PASSED_TESTS=0
FAILED_TESTS=0
FAILED_LIST=()
START_TIME=$(date +%s)

# Results log - save to dedicated logs directory
LOGS_DIR="${SCRIPT_DIR}/../../../../logs"
mkdir -p "${LOGS_DIR}"
RESULTS_LOG="${LOGS_DIR}/rhaiis-concurrent-load-$(date +%Y%m%d-%H%M%S).log"

# Determine phase skip flags
SKIP_PHASE_1=false
SKIP_PHASE_2=false
SKIP_PHASE_3=false

case "${PHASE}" in
    1)
        SKIP_PHASE_2=true
        SKIP_PHASE_3=true
        ;;
    2)
        SKIP_PHASE_1=true
        SKIP_PHASE_3=true
        ;;
    3)
        SKIP_PHASE_1=true
        SKIP_PHASE_2=true
        ;;
    all)
        # Run all phases
        ;;
esac

# Main test loop
for model in "${MODELS[@]}"; do
    for cores in "${CORE_COUNTS[@]}"; do
        for workload in "${WORKLOADS[@]}"; do
            CURRENT_TEST=$((CURRENT_TEST + 1))

            echo ""
            echo -e "${YELLOW}=========================================="
            echo -e "Test ${CURRENT_TEST}/${TOTAL_TESTS}"
            echo -e "==========================================${NC}"
            echo "Model: ${model}"
            echo "Cores: ${cores}"
            echo "Workload: ${workload}"
            echo "Phase: ${PHASE}"
            echo ""

            # Create test name
            MODEL_SHORT=$(basename "${model}")
            TEST_NAME="${MODEL_SHORT}-${cores}C-${workload}"

            # Build ansible command
            cmd=(
                ansible-playbook
                -i "automation/test-execution/ansible/inventory/hosts.yml"
                "automation/test-execution/ansible/llm-benchmark-concurrent-load.yml"
                -e "test_model=${model}"
                -e "base_workload=${workload}"
                -e "requested_cores=${cores}"
            )

            # Add NUMA/CPU pinning parameters if specified
            if [[ -n "${VLLM_CPU_START}" ]]; then
                cmd+=(-e "vllm_cpu_start=${VLLM_CPU_START}")
            fi
            if [[ -n "${VLLM_NUMA_NODE}" ]]; then
                cmd+=(-e "vllm_numa_node=${VLLM_NUMA_NODE}")
            fi
            if [[ -n "${GUIDELLM_CPUS}" ]]; then
                cmd+=(-e "guidellm_cpus=${GUIDELLM_CPUS}")
            fi
            if [[ -n "${GUIDELLM_NUMA_NODE}" ]]; then
                cmd+=(-e "guidellm_numa_node=${GUIDELLM_NUMA_NODE}")
            fi

            # Add phase skip flags
            if [[ "${SKIP_PHASE_1}" == true ]]; then
                cmd+=(-e "skip_phase_1=true")
            fi
            if [[ "${SKIP_PHASE_2}" == true ]]; then
                cmd+=(-e "skip_phase_2=true")
            fi
            if [[ "${SKIP_PHASE_3}" == true ]]; then
                cmd+=(-e "skip_phase_3=true")
            fi

            # For RAG workload, ensure max-model-len >= 8192
            # This is handled in the ansible playbook's test-workloads.yml config
            # but we can add a reminder here
            if [[ "${workload}" == "rag" ]]; then
                log_info "RAG workload selected - vLLM will use max-model-len >= 8192"
            fi

            if [[ "${DRY_RUN}" == true ]]; then
                log_info "DRY RUN: Would execute:"
                echo "  ${cmd[*]}"
                continue
            fi

            # Execute test
            test_start=$(date +%s)
            if "${cmd[@]}" 2>&1 | tee -a "${RESULTS_LOG}"; then
                test_end=$(date +%s)
                test_duration=$((test_end - test_start))
                log_success "✓ Test passed: ${TEST_NAME} (${test_duration}s)"
                PASSED_TESTS=$((PASSED_TESTS + 1))
            else
                test_end=$(date +%s)
                test_duration=$((test_end - test_start))
                log_error "✗ Test failed: ${TEST_NAME} (${test_duration}s)"
                FAILED_TESTS=$((FAILED_TESTS + 1))
                FAILED_LIST+=("${TEST_NAME}")

                if [[ "${CONTINUE_ON_ERROR}" == false ]]; then
                    log_error "Aborting test suite due to failure"
                    break 3
                fi
            fi

            # Pause between tests
            if [ ${CURRENT_TEST} -lt ${TOTAL_TESTS} ]; then
                echo ""
                log_info "Waiting 10 seconds before next test..."
                sleep 10
            fi
        done
    done
done

# Calculate duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(( (DURATION % 3600) / 60 ))
SECONDS=$((DURATION % 60))

# Summary
echo ""
echo "=========================================="
echo "RHAIIS Concurrent Load Test Suite Summary"
echo "=========================================="
echo "Completed at: $(date)"
echo "Total tests: ${TOTAL_TESTS}"
echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"

if [ ${FAILED_TESTS} -gt 0 ]; then
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
    echo ""
    echo "Failed tests:"
    for test in "${FAILED_LIST[@]}"; do
        echo -e "  ${RED}✗${NC} ${test}"
    done
fi

echo ""
echo "Duration: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo "=========================================="
echo ""

if [[ "${DRY_RUN}" == false ]]; then
    log_info "Results saved to: results/llm/"
    log_info "Detailed log: ${RESULTS_LOG}"
    echo ""
    log_info "To view results:"
    echo "  cd automation/test-execution/dashboard-examples/vllm_dashboard"
    echo "  ./launch-dashboard.sh"
    echo ""
fi

# Exit with error if any tests failed
if [ ${FAILED_TESTS} -gt 0 ]; then
    exit 1
fi

exit 0
