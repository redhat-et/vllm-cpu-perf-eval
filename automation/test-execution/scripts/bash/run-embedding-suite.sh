#!/bin/bash
# ==============================================================================
# Embedding Model Performance Test Suite
# ==============================================================================
# Run performance benchmarks across RedHatAI embedding models and core counts.
#
# Usage:
#   ./run-embedding-suite.sh [options]
#
# Options:
#   --models LIST           Comma-separated models or preset (all|small|large|quick)
#                           Default: all
#   --cores LIST            Comma-separated core counts
#                           Default: 4,8,16,32
#   --scenario TYPE         Test scenario (baseline|latency|all)
#                           Default: all
#   --num-prompts NUM       Number of prompts per test
#                           Default: 250
#   --max-seconds SEC       Per-test time limit in seconds; sets guidellm_max_seconds
#                           Default: Ansible default (300s); env var GUIDELLM_MAX_SECONDS also accepted
#   --vllm-bench-cpus RANGE CPU range for vllm-bench loadgen container (e.g., 8-15)
#   --vllm-bench-numa-node NUM NUMA node for vllm-bench loadgen container
#   --skip-models LIST      Comma-separated models to skip
#   --continue-on-error     Continue testing if a model fails
#   --dry-run               Show what would run without executing
#   -h, --help              Show this help
#
# Model Presets:
#   all     - All 5 models (22M to 8B)
#   small   - Fast models: all-MiniLM (22M), granite-english (109M)
#   medium  - Mid-size: nomic-embed (137M), embeddinggemma (300M)
#   large   - Large model: Qwen3-Embedding-8B
#   quick   - Single fast model for testing: all-MiniLM-L6-v2
#
# Examples:
#   # Run all models on all core counts
#   ./run-embedding-suite.sh
#
#   # Quick test with single small model
#   ./run-embedding-suite.sh --models quick --cores 4 --num-prompts 10
#
#   # Test small models only
#   ./run-embedding-suite.sh --models small --cores 8,16,32
#
#   # Test specific models
#   ./run-embedding-suite.sh \
#     --models "RedHatAI/all-MiniLM-L6-v2,RedHatAI/granite-embedding-english-r2"
#
#   # Skip large model
#   ./run-embedding-suite.sh --skip-models "RedHatAI/Qwen3-Embedding-8B"
#
#   # Baseline tests only on 16 cores
#   ./run-embedding-suite.sh --scenario baseline --cores 16
#
#   # Increase per-test time limit for slow models (e.g. Qwen3-Embedding-8B)
#   ./run-embedding-suite.sh --models large --max-seconds 600
#   GUIDELLM_MAX_SECONDS=600 ./run-embedding-suite.sh --models large
#
# ==============================================================================

set -euo pipefail

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

if [ ! -f "automation/test-execution/ansible/embedding-benchmark.yml" ]; then
    echo "ERROR: Not in repository root or structure has changed"
    echo "Expected file: automation/test-execution/ansible/embedding-benchmark.yml"
    exit 1
fi

# All available models from RedHatAI Intel Xeon-compatible collection
declare -A ALL_MODELS
ALL_MODELS=(
    ["RedHatAI/all-MiniLM-L6-v2"]="22.7M"
    ["RedHatAI/granite-embedding-english-r2"]="109M"
    ["RedHatAI/nomic-embed-text-v1.5"]="137M"
    ["RedHatAI/embeddinggemma-300m"]="300M"
    ["RedHatAI/Qwen3-Embedding-8B"]="8B"
)

# Model presets
PRESET_ALL=(
    "RedHatAI/all-MiniLM-L6-v2"
    "RedHatAI/granite-embedding-english-r2"
    "RedHatAI/nomic-embed-text-v1.5"
    "RedHatAI/embeddinggemma-300m"
    "RedHatAI/Qwen3-Embedding-8B"
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

PRESET_QUICK=(
    "RedHatAI/all-MiniLM-L6-v2"
)

# Default configuration
MODELS_INPUT="all"
CORES_INPUT="4,8,16,32"
SCENARIO="all"
NUM_PROMPTS=250
MAX_SECONDS="${GUIDELLM_MAX_SECONDS:-}"
VLLM_BENCH_CPUS=""
VLLM_BENCH_NUMA_NODE=""
CONTINUE_ON_ERROR=false
DRY_RUN=false
SKIP_MODELS_INPUT=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

show_help() {
    sed -n '/^# ===/,/^# ===/p' "$0" | sed 's/^# //; s/^#//'
}

# Parse arguments
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
        --scenario)
            SCENARIO="$2"
            shift 2
            ;;
        --num-prompts)
            NUM_PROMPTS="$2"
            shift 2
            ;;
        --max-seconds)
            MAX_SECONDS="$2"
            shift 2
            ;;
        --vllm-bench-cpus)
            VLLM_BENCH_CPUS="$2"
            shift 2
            ;;
        --vllm-bench-numa-node)
            VLLM_BENCH_NUMA_NODE="$2"
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
        MODELS=("${PRESET_ALL[@]}")
        ;;
    small)
        MODELS=("${PRESET_SMALL[@]}")
        ;;
    medium)
        MODELS=("${PRESET_MEDIUM[@]}")
        ;;
    large)
        MODELS=("${PRESET_LARGE[@]}")
        ;;
    quick)
        MODELS=("${PRESET_QUICK[@]}")
        ;;
    *)
        IFS=',' read -ra MODELS <<< "${MODELS_INPUT}"
        ;;
esac

# Parse core counts
IFS=',' read -ra CORE_COUNTS <<< "${CORES_INPUT}"

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

# Validate max-seconds
if [[ -n "${MAX_SECONDS}" && ! "${MAX_SECONDS}" =~ ^[0-9]+$ ]]; then
    log_error "Invalid --max-seconds value: ${MAX_SECONDS}"
    log_error "Must be a positive integer (seconds)"
    exit 1
fi

# Validate scenario
if [[ ! "${SCENARIO}" =~ ^(baseline|latency|all)$ ]]; then
    log_error "Invalid scenario: ${SCENARIO}"
    log_error "Must be: baseline, latency, or all"
    exit 1
fi

# Check for custom vLLM image
if [ -z "${VLLM_CONTAINER_IMAGE:-}" ]; then
    log_warning "VLLM_CONTAINER_IMAGE not set. Using default image."
    log_info "To use a custom image:"
    log_info "  export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0"
    echo ""
else
    log_info "Using custom vLLM image: ${VLLM_CONTAINER_IMAGE}"
    echo ""
fi

# Display configuration
echo "=========================================="
echo "Embedding Model Performance Test Suite"
echo "=========================================="
echo "Models (${#MODELS[@]}):"
for model in "${MODELS[@]}"; do
    size="${ALL_MODELS[$model]:-unknown}"
    echo "  - ${model} (${size})"
done
echo ""
echo "Core counts: ${CORE_COUNTS[*]}"
echo "Scenario: ${SCENARIO}"
echo "Prompts per test: ${NUM_PROMPTS}"
echo "Time limit: ${MAX_SECONDS:-300 (Ansible default)}s"
echo "Continue on error: ${CONTINUE_ON_ERROR}"
echo "Dry run: ${DRY_RUN}"
echo "=========================================="
echo ""

# Calculate total tests
TOTAL_TESTS=$((${#MODELS[@]} * ${#CORE_COUNTS[@]}))
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

# Results log
RESULTS_LOG="${SCRIPT_DIR}/embedding-suite-results-$(date +%Y%m%d-%H%M%S).log"

# Main test loop
for model in "${MODELS[@]}"; do
    for cores in "${CORE_COUNTS[@]}"; do
        CURRENT_TEST=$((CURRENT_TEST + 1))

        echo ""
        echo -e "${YELLOW}=========================================="
        echo -e "Test ${CURRENT_TEST}/${TOTAL_TESTS}"
        echo -e "==========================================${NC}"
        echo "Model: ${model}"
        echo "Cores: ${cores}"
        echo "Scenario: ${SCENARIO}"
        echo ""

        # Create test name
        MODEL_SHORT=$(basename "${model}")
        TEST_NAME="${MODEL_SHORT}-${cores}C"

        # Build ansible command
        cmd=(
            ansible-playbook
            -i "automation/test-execution/ansible/inventory/hosts.yml"
            "automation/test-execution/ansible/embedding-benchmark.yml"
            -e "test_model=${model}"
            -e "scenario=${SCENARIO}"
            -e "requested_cores=${cores}"
            -e "num_prompts=${NUM_PROMPTS}"
            -e "test_name=${TEST_NAME}"
        )

        [[ -n "${MAX_SECONDS}" ]] && cmd+=(-e "guidellm_max_seconds=${MAX_SECONDS}")
        [[ -n "${VLLM_BENCH_CPUS}" ]] && cmd+=(-e "vllm_bench_cpus=${VLLM_BENCH_CPUS}")
        [[ -n "${VLLM_BENCH_NUMA_NODE}" ]] && cmd+=(-e "vllm_bench_numa_node=${VLLM_BENCH_NUMA_NODE}")

        # Parallel instance overrides — set env vars to run multiple instances
        # simultaneously on the same host (each with its own container, port, NUMA nodes):
        #   VLLM_CONTAINER_NAME=vllm-0 VLLM_PORT=8000 VLLM_NUMA_NODES="0,1" ./run-embedding-suite.sh
        if [[ -n "${VLLM_CONTAINER_NAME:-}" ]]; then
            cmd+=(-e "vllm_container_name=${VLLM_CONTAINER_NAME}")
        fi
        if [[ -n "${VLLM_PORT:-}" ]]; then
            cmd+=(-e "vllm_port=${VLLM_PORT}")
        fi
        if [[ -n "${VLLM_NUMA_NODES:-}" ]]; then
            cmd+=(-e "vllm_numa_nodes=${VLLM_NUMA_NODES}")
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
                break 2
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

# Calculate duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(( (DURATION % 3600) / 60 ))
SECONDS=$((DURATION % 60))

# Summary
echo ""
echo "=========================================="
echo "Test Suite Summary"
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
    log_info "Results saved to: results/embedding/"
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
