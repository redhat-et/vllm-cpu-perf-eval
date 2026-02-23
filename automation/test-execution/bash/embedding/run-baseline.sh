#!/usr/bin/env bash
# Baseline Performance Test for Embedding Models
# Runs sweep test to find maximum throughput and test at 25%, 50%, 75% load

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../../" && pwd)"

# Default values
VLLM_HOST="${VLLM_HOST:-localhost}"
VLLM_PORT="${VLLM_PORT:-8000}"
MODEL="${1:-ibm-granite/granite-embedding-278m-multilingual}"
RESULTS_DIR="${RESULTS_DIR:-${PROJECT_ROOT}/results/embedding-models}"
NUM_PROMPTS="${NUM_PROMPTS:-1000}"
INPUT_LEN="${INPUT_LEN:-512}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

usage() {
    cat <<EOF
Usage: $0 [MODEL] [OPTIONS]

Run baseline performance tests for embedding models.

Arguments:
    MODEL               Model to test (default: ibm-granite/granite-embedding-278m-multilingual)

Options:
    --vllm-host HOST    vLLM server host (default: localhost)
    --vllm-port PORT    vLLM server port (default: 8000)
    --results-dir DIR   Results directory (default: PROJECT_ROOT/results/embedding-models)
    --num-prompts N     Number of prompts (default: 1000)
    --input-len N       Input sequence length (default: 512)
    -h, --help          Show this help message

Environment Variables:
    VLLM_HOST           Override default vLLM host
    VLLM_PORT           Override default vLLM port
    RESULTS_DIR         Override default results directory

Examples:
    # Test with local vLLM
    $0 ibm-granite/granite-embedding-english-r2

    # Test with remote vLLM
    $0 ibm-granite/granite-embedding-278m-multilingual --vllm-host 192.168.1.10

    # Custom configuration
    VLLM_HOST=10.0.0.5 VLLM_PORT=8080 $0 ibm-granite/granite-embedding-english-r2

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --vllm-host)
            VLLM_HOST="$2"
            shift 2
            ;;
        --vllm-port)
            VLLM_PORT="$2"
            shift 2
            ;;
        --results-dir)
            RESULTS_DIR="$2"
            shift 2
            ;;
        --num-prompts)
            NUM_PROMPTS="$2"
            shift 2
            ;;
        --input-len)
            INPUT_LEN="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            if [[ -z "${MODEL_SET:-}" ]]; then
                MODEL="$1"
                MODEL_SET=1
            fi
            shift
            ;;
    esac
done

# Extract model basename for file naming
MODEL_BASENAME=$(basename "$MODEL")

# Create results directory
RESULT_PATH="${RESULTS_DIR}/${MODEL_BASENAME}/baseline"
mkdir -p "$RESULT_PATH"

log_info "Starting baseline performance test"
log_info "Model: $MODEL"
log_info "vLLM Server: http://${VLLM_HOST}:${VLLM_PORT}"
log_info "Results: $RESULT_PATH"
log_info ""

# Check vLLM connectivity
log_info "Checking vLLM server connectivity..."
if ! curl -sf "http://${VLLM_HOST}:${VLLM_PORT}/health" >/dev/null; then
    log_warn "Cannot connect to vLLM server at http://${VLLM_HOST}:${VLLM_PORT}"
    log_warn "Please ensure vLLM is running and accessible"
    exit 1
fi
log_info "vLLM server is accessible"
log_info ""

# Common vllm bench serve parameters
BENCH_COMMON=(
    --host "$VLLM_HOST"
    --port "$VLLM_PORT"
    --backend openai-embeddings
    --model "$MODEL"
    --dataset-name random
    --random-input-len "$INPUT_LEN"
    --num-prompts "$NUM_PROMPTS"
    --endpoint /v1/embeddings
    --save-result
)

# Test 1: Find maximum throughput
log_info "Test 1/4: Finding maximum throughput (request-rate=inf)..."
vllm bench serve "${BENCH_COMMON[@]}" \
    --request-rate inf \
    --result-filename "${RESULT_PATH}/sweep-inf.json"

# Extract max RPS from output
MAX_RPS=$(jq -r '.request_throughput' "${RESULT_PATH}/sweep-inf.json")
log_info "Maximum RPS: $MAX_RPS"
log_info ""

# Calculate load levels
RATE_25=$(awk "BEGIN {printf \"%.2f\", $MAX_RPS * 0.25}")
RATE_50=$(awk "BEGIN {printf \"%.2f\", $MAX_RPS * 0.50}")
RATE_75=$(awk "BEGIN {printf \"%.2f\", $MAX_RPS * 0.75}")

log_info "Calculated load levels:"
log_info "  25%: ${RATE_25} req/s"
log_info "  50%: ${RATE_50} req/s"
log_info "  75%: ${RATE_75} req/s"
log_info ""

# Test 2: 25% load
log_info "Test 2/4: Running at 25% load (${RATE_25} req/s)..."
vllm bench serve "${BENCH_COMMON[@]}" \
    --request-rate "$RATE_25" \
    --result-filename "${RESULT_PATH}/sweep-25pct.json"
log_info ""

# Test 3: 50% load
log_info "Test 3/4: Running at 50% load (${RATE_50} req/s)..."
vllm bench serve "${BENCH_COMMON[@]}" \
    --request-rate "$RATE_50" \
    --result-filename "${RESULT_PATH}/sweep-50pct.json"
log_info ""

# Test 4: 75% load
log_info "Test 4/4: Running at 75% load (${RATE_75} req/s)..."
vllm bench serve "${BENCH_COMMON[@]}" \
    --request-rate "$RATE_75" \
    --result-filename "${RESULT_PATH}/sweep-75pct.json"
log_info ""

# Summary
log_info "Baseline performance tests completed!"
log_info "Results saved to: $RESULT_PATH"
log_info ""
log_info "Result files:"
ls -lh "$RESULT_PATH"/*.json
log_info ""
log_info "To view results:"
log_info "  cat ${RESULT_PATH}/sweep-inf.json | jq"
