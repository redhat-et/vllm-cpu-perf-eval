#!/usr/bin/env bash
# Latency and Concurrent Load Test for Embedding Models
# Tests latency scaling under increasing concurrent requests

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
CONCURRENCY_LEVELS="${CONCURRENCY_LEVELS:-16 32 64 128 196}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_test() {
    echo -e "${BLUE}[TEST]${NC} $*"
}

usage() {
    cat <<EOF
Usage: $0 [MODEL] [OPTIONS]

Run latency scaling tests for embedding models with varying concurrency.

Arguments:
    MODEL               Model to test (default: ibm-granite/granite-embedding-278m-multilingual)

Options:
    --vllm-host HOST    vLLM server host (default: localhost)
    --vllm-port PORT    vLLM server port (default: 8000)
    --results-dir DIR   Results directory (default: PROJECT_ROOT/results/embedding-models)
    --num-prompts N     Number of prompts (default: 1000)
    --input-len N       Input sequence length (default: 512)
    --concurrency LEVELS Space-separated concurrency levels (default: "16 32 64 128 196")
    -h, --help          Show this help message

Environment Variables:
    VLLM_HOST             Override default vLLM host
    VLLM_PORT             Override default vLLM port
    RESULTS_DIR           Override default results directory
    CONCURRENCY_LEVELS    Override concurrency levels to test

Examples:
    # Test with local vLLM
    $0 ibm-granite/granite-embedding-english-r2

    # Test with remote vLLM and custom concurrency
    $0 ibm-granite/granite-embedding-278m-multilingual \\
        --vllm-host 192.168.1.10 \\
        --concurrency "8 16 32 64"

    # Test with environment variables
    VLLM_HOST=10.0.0.5 CONCURRENCY_LEVELS="16 32 64" $0 \\
        ibm-granite/granite-embedding-english-r2

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
        --concurrency)
            CONCURRENCY_LEVELS="$2"
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
RESULT_PATH="${RESULTS_DIR}/${MODEL_BASENAME}/latency"
mkdir -p "$RESULT_PATH"

log_info "Starting latency scaling test"
log_info "Model: $MODEL"
log_info "vLLM Server: http://${VLLM_HOST}:${VLLM_PORT}"
log_info "Concurrency levels: $CONCURRENCY_LEVELS"
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
    --request-rate inf
    --save-result
)

# Convert concurrency levels to array
IFS=' ' read -r -a CONC_ARRAY <<< "$CONCURRENCY_LEVELS"
TOTAL_TESTS=${#CONC_ARRAY[@]}
CURRENT_TEST=0

# Run tests for each concurrency level
for concurrency in "${CONC_ARRAY[@]}"; do
    ((CURRENT_TEST++))
    log_test "Test $CURRENT_TEST/$TOTAL_TESTS: Concurrency = $concurrency"

    vllm bench serve "${BENCH_COMMON[@]}" \
        --max-concurrency "$concurrency" \
        --result-filename "${RESULT_PATH}/concurrent-${concurrency}.json"

    # Extract and display key metrics
    if [[ -f "${RESULT_PATH}/concurrent-${concurrency}.json" ]]; then
        RPS=$(jq -r '.request_throughput' "${RESULT_PATH}/concurrent-${concurrency}.json" 2>/dev/null || echo "N/A")
        MEAN_LAT=$(jq -r '.mean_e2e_latency_ms' "${RESULT_PATH}/concurrent-${concurrency}.json" 2>/dev/null || echo "N/A")
        P99_LAT=$(jq -r '.p99_e2e_latency_ms' "${RESULT_PATH}/concurrent-${concurrency}.json" 2>/dev/null || echo "N/A")

        log_info "  RPS: $RPS | Mean Latency: ${MEAN_LAT}ms | P99 Latency: ${P99_LAT}ms"
    fi
    log_info ""
done

# Summary
log_info "Latency scaling tests completed!"
log_info "Results saved to: $RESULT_PATH"
log_info ""
log_info "Result files:"
ls -lh "$RESULT_PATH"/*.json
log_info ""

# Quick analysis summary
log_info "Quick Analysis Summary:"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "%-12s %-15s %-20s %-20s\n" "Concurrency" "RPS" "Mean Latency (ms)" "P99 Latency (ms)"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for concurrency in "${CONC_ARRAY[@]}"; do
    if [[ -f "${RESULT_PATH}/concurrent-${concurrency}.json" ]]; then
        RPS=$(jq -r '.request_throughput' "${RESULT_PATH}/concurrent-${concurrency}.json" 2>/dev/null || echo "N/A")
        MEAN_LAT=$(jq -r '.mean_e2e_latency_ms' "${RESULT_PATH}/concurrent-${concurrency}.json" 2>/dev/null || echo "N/A")
        P99_LAT=$(jq -r '.p99_e2e_latency_ms' "${RESULT_PATH}/concurrent-${concurrency}.json" 2>/dev/null || echo "N/A")

        printf "%-12s %-15s %-20s %-20s\n" "$concurrency" "$RPS" "$MEAN_LAT" "$P99_LAT"
    fi
done
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info ""
log_info "Look for:"
log_info "  - Sweet spot: Where throughput plateaus but P99 latency is acceptable"
log_info "  - Degradation point: Where P99 increases significantly with minimal RPS gain"
