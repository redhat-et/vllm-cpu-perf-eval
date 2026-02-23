#!/usr/bin/env bash
# Run all embedding model performance tests

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
VLLM_HOST="${VLLM_HOST:-localhost}"
VLLM_PORT="${VLLM_PORT:-8000}"
MODELS="${MODELS:-ibm-granite/granite-embedding-278m-multilingual ibm-granite/granite-embedding-english-r2}"
RUN_BASELINE="${RUN_BASELINE:-true}"
RUN_LATENCY="${RUN_LATENCY:-true}"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$*${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Run complete embedding model performance test suite.

Options:
    --vllm-host HOST       vLLM server host (default: localhost)
    --vllm-port PORT       vLLM server port (default: 8000)
    --models "MODEL..."    Space-separated list of models to test
    --baseline-only        Run only baseline tests
    --latency-only         Run only latency tests
    -h, --help             Show this help message

Environment Variables:
    VLLM_HOST              Override vLLM host
    VLLM_PORT              Override vLLM port
    MODELS                 Override models to test
    RUN_BASELINE           Set to false to skip baseline tests
    RUN_LATENCY            Set to false to skip latency tests

Examples:
    # Run all tests with local vLLM
    $0

    # Run all tests with remote vLLM
    $0 --vllm-host 192.168.1.10

    # Test specific models
    $0 --models "ibm-granite/granite-embedding-english-r2 ibm-granite/granite-embedding-278m-multilingual"

    # Run only baseline tests
    $0 --baseline-only

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
        --models)
            MODELS="$2"
            shift 2
            ;;
        --baseline-only)
            RUN_BASELINE=true
            RUN_LATENCY=false
            shift
            ;;
        --latency-only)
            RUN_BASELINE=false
            RUN_LATENCY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Export for child scripts
export VLLM_HOST
export VLLM_PORT

log_section "Embedding Model Performance Test Suite"
log_info "vLLM Server: http://${VLLM_HOST}:${VLLM_PORT}"
log_info "Models to test: $MODELS"
log_info "Tests to run: $(${RUN_BASELINE} && echo -n "Baseline " ; ${RUN_LATENCY} && echo "Latency")"

# Check vLLM connectivity
log_info ""
log_info "Checking vLLM server connectivity..."
if ! curl -sf "http://${VLLM_HOST}:${VLLM_PORT}/health" >/dev/null; then
    echo "ERROR: Cannot connect to vLLM server at http://${VLLM_HOST}:${VLLM_PORT}"
    echo "Please ensure vLLM is running and accessible"
    exit 1
fi
log_info "vLLM server is accessible"

# Convert models to array
IFS=' ' read -r -a MODEL_ARRAY <<< "$MODELS"

# Run tests for each model
for model in "${MODEL_ARRAY[@]}"; do
    log_section "Testing model: $model"

    if ${RUN_BASELINE}; then
        log_info "Running baseline performance tests..."
        "${SCRIPT_DIR}/run-baseline.sh" "$model"
        log_info ""
    fi

    if ${RUN_LATENCY}; then
        log_info "Running latency scaling tests..."
        "${SCRIPT_DIR}/run-latency.sh" "$model"
        log_info ""
    fi

    log_info "Completed tests for $model"
    log_info ""
done

log_section "All Embedding Tests Completed!"
log_info "Results are available in: \$PROJECT_ROOT/results/embedding-models/"
log_info ""
log_info "Next steps:"
log_info "  1. Review results: ls -lh results/embedding-models/"
log_info "  2. Generate reports: cd automation/analysis && python generate-embedding-report.py"
log_info "  3. Compare models: scripts/compare-results.sh"
