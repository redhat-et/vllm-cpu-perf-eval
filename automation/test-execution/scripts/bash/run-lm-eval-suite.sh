#!/bin/bash
# ==============================================================================
# LM Evaluation Harness Accuracy Test Suite
# ==============================================================================
# Run lm-eval accuracy benchmarks across LLM models and core counts.
# Starts a vLLM CPU container per test then runs lm-eval against it.
#
# Usage:
#   ./run-lm-eval-suite.sh [options]
#
# Options:
#   --models LIST           Comma-separated models or preset (all|quick|small|medium)
#                           Default: all
#   --cores LIST            Comma-separated core counts
#                           Default: 8,16,32
#   --tasks LIST            Comma-separated lm-eval task names
#                           Default: hellaswag,winogrande,arc_easy,arc_challenge
#   --batch-size NUM        lm-eval batch size
#                           Default: 16
#   --dtype DTYPE           Model dtype (bfloat16|float16|float32)
#                           Default: bfloat16
#   --max-model-len NUM     Override vLLM max context length (optional)
#   --kv-cache-space NUM    KV cache in GiB (VLLM_CPU_KVCACHE_SPACE)
#                           Default: 40
#   --lm-eval-image IMAGE   lm-eval container image
#                           Default: quay.io/vllm-cpu-perf-eval/lm-eval:latest
#   --limit NUM             Limit examples per task (useful for quick runs)
#   --continue-on-error     Continue suite after a test failure
#   --dry-run               Show what would run without executing
#   -h, --help              Show this help
#
# Model Presets:
#   all     - All models (0.6B to 3B)
#   quick   - Single small open model: Qwen/Qwen3-0.6B
#   small   - Fast models: Qwen3-0.6B, TinyLlama, Granite-3.2-2B
#   medium  - Larger: Llama-3.2-1B, Qwen2.5-3B, Llama-3.2-3B
#
# Environment Variables:
#   VLLM_CONTAINER_IMAGE    Override vLLM container image
#   VLLM_CONTAINER_NAME     Container name for parallel runs
#   VLLM_PORT               vLLM server port for parallel runs
#   VLLM_NUMA_NODES         NUMA nodes for parallel runs
#   HF_TOKEN                HuggingFace token for gated models
#
# Examples:
#   # Quick smoke test
#   ./run-lm-eval-suite.sh --models quick --cores 8 --limit 50
#
#   # Small models on default core counts
#   ./run-lm-eval-suite.sh --models small --tasks hellaswag,arc_easy
#
#   # Full accuracy sweep
#   ./run-lm-eval-suite.sh --models all --cores 16,32
#
#   # Custom model
#   ./run-lm-eval-suite.sh --models ibm-granite/granite-3.2-2b-instruct --cores 16
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

if [ ! -f "automation/test-execution/ansible/lm-eval-benchmark.yml" ]; then
    echo "ERROR: Not in repository root or structure has changed"
    echo "Expected file: automation/test-execution/ansible/lm-eval-benchmark.yml"
    exit 1
fi

# Model presets
PRESET_QUICK=(
    "Qwen/Qwen3-0.6B"
)

PRESET_SMALL=(
    "Qwen/Qwen3-0.6B"
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    "ibm-granite/granite-3.2-2b-instruct"
)

PRESET_MEDIUM=(
    "meta-llama/Llama-3.2-1B-Instruct"
    "Qwen/Qwen2.5-3B-Instruct"
    "meta-llama/Llama-3.2-3B-Instruct"
)

PRESET_ALL=(
    "Qwen/Qwen3-0.6B"
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
    "ibm-granite/granite-3.2-2b-instruct"
    "meta-llama/Llama-3.2-1B-Instruct"
    "Qwen/Qwen2.5-3B-Instruct"
    "meta-llama/Llama-3.2-3B-Instruct"
)

# Defaults
MODELS_INPUT="all"
CORES_INPUT="8,16,32"
TASKS="hellaswag,winogrande,arc_easy,arc_challenge"
BATCH_SIZE="16"
DTYPE="bfloat16"
MAX_MODEL_LEN=""
KV_CACHE_SPACE="40"
LM_EVAL_IMAGE="quay.io/vllm-cpu-perf-eval/lm-eval:latest"
LIMIT=""
CONTINUE_ON_ERROR=false
DRY_RUN=false

# Colors
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
        --models)      MODELS_INPUT="$2";  shift 2 ;;
        --cores)       CORES_INPUT="$2";   shift 2 ;;
        --tasks)       TASKS="$2";         shift 2 ;;
        --batch-size)  BATCH_SIZE="$2";    shift 2 ;;
        --dtype)       DTYPE="$2";         shift 2 ;;
        --max-model-len)  MAX_MODEL_LEN="$2"; shift 2 ;;
        --kv-cache-space) KV_CACHE_SPACE="$2"; shift 2 ;;
        --lm-eval-image)  LM_EVAL_IMAGE="$2"; shift 2 ;;
        --limit)       LIMIT="$2";         shift 2 ;;
        --continue-on-error) CONTINUE_ON_ERROR=true; shift ;;
        --dry-run)     DRY_RUN=true;       shift ;;
        -h|--help)     show_help; exit 0 ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Resolve model preset
MODELS=()
case "${MODELS_INPUT}" in
    all)    MODELS=("${PRESET_ALL[@]}") ;;
    quick)  MODELS=("${PRESET_QUICK[@]}") ;;
    small)  MODELS=("${PRESET_SMALL[@]}") ;;
    medium) MODELS=("${PRESET_MEDIUM[@]}") ;;
    *)      IFS=',' read -ra MODELS <<< "${MODELS_INPUT}" ;;
esac

IFS=',' read -ra CORE_COUNTS <<< "${CORES_INPUT}"

# Validate dtype
if [[ ! "${DTYPE}" =~ ^(bfloat16|float16|float32)$ ]]; then
    log_error "Invalid dtype: ${DTYPE}. Must be bfloat16, float16, or float32"
    exit 1
fi

# Check custom vLLM image
if [ -z "${VLLM_CONTAINER_IMAGE:-}" ]; then
    log_warning "VLLM_CONTAINER_IMAGE not set. Using default image."
    log_info "To use a custom image: export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:latest"
    echo ""
else
    log_info "Using custom vLLM image: ${VLLM_CONTAINER_IMAGE}"
    echo ""
fi

# Display configuration
echo "=========================================="
echo "LM Evaluation Harness Accuracy Test Suite"
echo "=========================================="
echo "Models (${#MODELS[@]}):"
for model in "${MODELS[@]}"; do
    echo "  - ${model}"
done
echo ""
echo "Core counts: ${CORE_COUNTS[*]}"
echo "Tasks: ${TASKS}"
echo "Batch size: ${BATCH_SIZE}"
echo "Dtype: ${DTYPE}"
echo "KV cache space: ${KV_CACHE_SPACE}GiB"
echo "Max model len: ${MAX_MODEL_LEN:-model default}"
echo "Limit per task: ${LIMIT:-none}"
echo "lm-eval image: ${LM_EVAL_IMAGE}"
echo "Continue on error: ${CONTINUE_ON_ERROR}"
echo "Dry run: ${DRY_RUN}"
echo "=========================================="
echo ""

TOTAL_TESTS=$((${#MODELS[@]} * ${#CORE_COUNTS[@]}))
echo "Total test combinations: ${TOTAL_TESTS}"
echo ""

if [[ "${DRY_RUN}" == false ]]; then
    read -p "Proceed with test suite? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
fi

CURRENT_TEST=0
PASSED_TESTS=0
FAILED_TESTS=0
FAILED_LIST=()
START_TIME=$(date +%s)

RESULTS_LOG="${SCRIPT_DIR}/lm-eval-suite-results-$(date +%Y%m%d-%H%M%S).log"

for model in "${MODELS[@]}"; do
    for cores in "${CORE_COUNTS[@]}"; do
        CURRENT_TEST=$((CURRENT_TEST + 1))

        echo ""
        echo -e "${YELLOW}=========================================="
        echo -e "Test ${CURRENT_TEST}/${TOTAL_TESTS}"
        echo -e "==========================================${NC}"
        echo "Model: ${model}"
        echo "Cores: ${cores}"
        echo "Tasks: ${TASKS}"
        echo ""

        MODEL_SHORT=$(basename "${model}")
        TEST_NAME="${MODEL_SHORT}-${cores}C"

        cmd=(
            ansible-playbook
            -i "automation/test-execution/ansible/inventory/hosts.yml"
            "automation/test-execution/ansible/lm-eval-benchmark.yml"
            -e "test_model=${model}"
            -e "requested_cores=${cores}"
            -e "lm_eval_tasks=${TASKS}"
            -e "lm_eval_batch_size=${BATCH_SIZE}"
            -e "lm_eval_dtype=${DTYPE}"
            -e "lm_eval_kv_cache_space=${KV_CACHE_SPACE}"
            -e "lm_eval_image=${LM_EVAL_IMAGE}"
            -e "test_name=${TEST_NAME}"
        )

        [[ -n "${MAX_MODEL_LEN}" ]]  && cmd+=(-e "lm_eval_max_model_len=${MAX_MODEL_LEN}")
        [[ -n "${LIMIT}" ]]          && cmd+=(-e "lm_eval_limit=${LIMIT}")

        # Parallel instance overrides
        [[ -n "${VLLM_CONTAINER_NAME:-}" ]] && cmd+=(-e "vllm_container_name=${VLLM_CONTAINER_NAME}")
        [[ -n "${VLLM_PORT:-}" ]]           && cmd+=(-e "vllm_port=${VLLM_PORT}")
        [[ -n "${VLLM_NUMA_NODES:-}" ]]     && cmd+=(-e "vllm_numa_nodes=${VLLM_NUMA_NODES}")

        if [[ "${DRY_RUN}" == true ]]; then
            log_info "DRY RUN: Would execute:"
            echo "  ${cmd[*]}"
            continue
        fi

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

        if [ ${CURRENT_TEST} -lt ${TOTAL_TESTS} ]; then
            echo ""
            log_info "Waiting 10 seconds before next test..."
            sleep 10
        fi
    done
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(( (DURATION % 3600) / 60 ))
SECONDS=$((DURATION % 60))

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
    log_info "Results saved to: results/lm-eval/"
    log_info "Detailed log: ${RESULTS_LOG}"
    echo ""
fi

[ ${FAILED_TESTS} -gt 0 ] && exit 1
exit 0
