#!/usr/bin/env bash
# Run all embedding model performance tests

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../../" && pwd)"

# Default values
VLLM_HOST="${VLLM_HOST:-localhost}"
VLLM_PORT="${VLLM_PORT:-8000}"
MODELS="${MODELS:-ibm-granite/granite-embedding-278m-multilingual ibm-granite/granite-embedding-english-r2}"
RUN_BASELINE="${RUN_BASELINE:-true}"
RUN_LATENCY="${RUN_LATENCY:-true}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Early bypass for --help (before blocking guard)
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        usage
        exit 0
    fi
done

# ════════════════════════════════════════════════════════════════════════════════
# ❌ BLOCK UNSUPPORTED TEST SUITE
# ════════════════════════════════════════════════════════════════════════════════
if [[ "${ALLOW_UNSUPPORTED_TESTS:-false}" != "true" ]]; then
    echo -e "" >&2
    echo -e "${RED}❌ EMBEDDING MODELS TEST SUITE NOT YET SUPPORTED${NC}" >&2
    echo -e "" >&2
    echo -e "This script (run-all.sh) is blocked because the Embedding Models test" >&2
    echo -e "suite is still work in progress and not validated for end users." >&2
    echo -e "" >&2
    echo -e "${GREEN}✅ USE SUPPORTED TESTS INSTEAD:${NC}" >&2
    echo -e "" >&2
    echo -e "Concurrent Load Testing (Phase 1 & Phase 2) is fully validated for LLM models." >&2
    echo -e "" >&2
    echo -e "  cd ${PROJECT_ROOT}/automation/test-execution/ansible" >&2
    echo -e "  ansible-playbook -i inventory/hosts.yml llm-benchmark-concurrent-load.yml \\" >&2
    echo -e "    -e \"test_model=TinyLlama/TinyLlama-1.1B-Chat-v1.0\" \\" >&2
    echo -e "    -e \"base_workload=chat\" \\" >&2
    echo -e "    -e \"core_sweep_counts=[16,32,64]\" \\" >&2
    echo -e "    -e \"skip_phase_3=true\"" >&2
    echo -e "" >&2
    echo -e "${BLUE}📚 See: tests/concurrent-load/concurrent-load.md | README.md${NC}" >&2
    echo -e "" >&2
    echo -e "${YELLOW}To bypass (development only): export ALLOW_UNSUPPORTED_TESTS=true${NC}" >&2
    echo -e "" >&2
    exit 1
fi

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
