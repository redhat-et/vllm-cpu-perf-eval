#!/usr/bin/env bash
# Health check script for vLLM server
# Can be used to verify vLLM is ready before running tests

set -euo pipefail

# Default values
VLLM_HOST="${VLLM_HOST:-localhost}"
VLLM_PORT="${VLLM_PORT:-8000}"
TIMEOUT="${TIMEOUT:-300}"  # 5 minutes
INTERVAL="${INTERVAL:-5}"   # 5 seconds
VERBOSE="${VERBOSE:-false}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}✓${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}!${NC} $*"
}

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Check if vLLM server is healthy and ready to serve requests.

Options:
    --host HOST        vLLM server host (default: localhost)
    --port PORT        vLLM server port (default: 8000)
    --timeout SECONDS  Maximum wait time (default: 300)
    --interval SECONDS Check interval (default: 5)
    --verbose          Show detailed output
    -h, --help         Show this help message

Environment Variables:
    VLLM_HOST          Override default host
    VLLM_PORT          Override default port
    TIMEOUT            Override default timeout
    INTERVAL           Override default interval

Exit Codes:
    0 - vLLM server is healthy
    1 - vLLM server is not accessible
    2 - Health check timeout

Examples:
    # Check local vLLM
    $0

    # Check remote vLLM with 10 minute timeout
    $0 --host 192.168.1.10 --timeout 600

    # Quick check
    $0 --timeout 30 --interval 2

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            VLLM_HOST="$2"
            shift 2
            ;;
        --port)
            VLLM_PORT="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
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

VLLM_URL="http://${VLLM_HOST}:${VLLM_PORT}"

echo "Checking vLLM server at ${VLLM_URL}..."
echo "Timeout: ${TIMEOUT}s | Interval: ${INTERVAL}s"
echo ""

# Calculate number of retries
MAX_RETRIES=$((TIMEOUT / INTERVAL))
RETRY_COUNT=0

# Check loop
while (( RETRY_COUNT < MAX_RETRIES )); do
    ((RETRY_COUNT++))

    if ${VERBOSE}; then
        echo "Attempt $RETRY_COUNT/$MAX_RETRIES..."
    fi

    # Check /health endpoint
    if HEALTH_RESPONSE=$(curl -sf "${VLLM_URL}/health" 2>&1); then
        log_info "vLLM server is healthy!"

        # Additional checks
        if ${VERBOSE}; then
            echo ""
            echo "Health response:"
            echo "$HEALTH_RESPONSE" | jq '.' 2>/dev/null || echo "$HEALTH_RESPONSE"
            echo ""

            # Check /v1/models
            if MODELS_RESPONSE=$(curl -sf "${VLLM_URL}/v1/models" 2>&1); then
                echo "Available models:"
                echo "$MODELS_RESPONSE" | jq '.data[] | .id' 2>/dev/null || echo "$MODELS_RESPONSE"
                echo ""
            fi

            # Get version info (if available)
            if VERSION_RESPONSE=$(curl -sf "${VLLM_URL}/version" 2>&1); then
                echo "vLLM version:"
                echo "$VERSION_RESPONSE"
                echo ""
            fi
        fi

        exit 0
    fi

    # Failed - wait before retry
    if ${VERBOSE}; then
        log_warn "Server not ready, retrying in ${INTERVAL}s..."
    else
        echo -n "."
    fi

    sleep "$INTERVAL"
done

# Timeout reached
echo ""
log_error "Health check timeout after ${TIMEOUT}s"
log_error "vLLM server at ${VLLM_URL} is not responding"
echo ""
echo "Troubleshooting:"
echo "  1. Check if vLLM is running: podman ps | grep vllm"
echo "  2. Check vLLM logs: podman logs vllm-embedding-server"
echo "  3. Check network connectivity: ping ${VLLM_HOST}"
echo "  4. Check port is open: nc -zv ${VLLM_HOST} ${VLLM_PORT}"

exit 2
