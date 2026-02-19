#!/usr/bin/env bash
# Monitor test progress and display real-time metrics
# Shows summary of test execution and results

set -euo pipefail

# Default values
MODE="${MODE:-local}"
REMOTE_HOST="${REMOTE_HOST:-}"
RESULTS_DIR="${RESULTS_DIR:-/var/tmp/embedding-results}"
REFRESH="${REFRESH:-5}"  # seconds

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Monitor test progress and view real-time metrics from the load generator.

Options:
    --mode MODE            'local' or 'remote' (default: local)
    --remote-host HOST     SSH host for remote monitoring
    --results-dir DIR      Results directory (default: /var/tmp/embedding-results)
    --refresh SECONDS      Refresh interval (default: 5)
    -h, --help             Show this help message

Environment Variables:
    MODE                   Override mode (local/remote)
    REMOTE_HOST            Remote host for SSH connection
    RESULTS_DIR            Override results directory
    REFRESH                Override refresh interval

Examples:
    # Monitor local test progress
    $0

    # Monitor remote load generator
    $0 --mode remote --remote-host 192.168.1.20

    # Fast refresh for active monitoring
    $0 --refresh 2

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --remote-host)
            REMOTE_HOST="$2"
            MODE=remote
            shift 2
            ;;
        --results-dir)
            RESULTS_DIR="$2"
            shift 2
            ;;
        --refresh)
            REFRESH="$2"
            shift 2
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

# Function to display test status
display_status() {
    local host_prefix=""
    if [[ "$MODE" == "remote" ]]; then
        host_prefix="ssh $REMOTE_HOST "
    fi

    clear
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Embedding Test Progress Monitor${NC}"
    if [[ "$MODE" == "remote" ]]; then
        echo -e "${BLUE}Load Generator: ${REMOTE_HOST}${NC}"
    else
        echo -e "${BLUE}Load Generator: localhost${NC}"
    fi
    echo -e "${BLUE}Results Directory: ${RESULTS_DIR}${NC}"
    echo -e "${BLUE}Refresh: ${REFRESH}s | Press Ctrl+C to exit${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Check if results directory exists
    if ! ${host_prefix}test -d "$RESULTS_DIR" 2>/dev/null; then
        echo -e "${YELLOW}Results directory not found: ${RESULTS_DIR}${NC}"
        echo "Waiting for tests to start..."
        return
    fi

    # List test results
    echo -e "${GREEN}Completed Test Results:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Find all JSON result files
    ${host_prefix}find "$RESULTS_DIR" -name "*.json" -type f 2>/dev/null | while read -r result_file; do
        # Extract relative path
        rel_path="${result_file#$RESULTS_DIR/}"

        # Get file size and modified time
        if [[ "$MODE" == "remote" ]]; then
            file_info=$(ssh "$REMOTE_HOST" "ls -lh '$result_file' 2>/dev/null" || echo "")
        else
            file_info=$(ls -lh "$result_file" 2>/dev/null || echo "")
        fi

        if [[ -n "$file_info" ]]; then
            size=$(echo "$file_info" | awk '{print $5}')
            time=$(echo "$file_info" | awk '{print $6, $7, $8}')

            echo -e "  ${GREEN}✓${NC} ${rel_path} (${size}, ${time})"

            # Try to extract key metrics if jq is available
            if command -v jq &> /dev/null; then
                if [[ "$MODE" == "remote" ]]; then
                    metrics=$(ssh "$REMOTE_HOST" "cat '$result_file' | jq -r '\"    RPS: \" + (.request_throughput // \"N/A\" | tostring) + \" | P99: \" + (.p99_e2e_latency_ms // \"N/A\" | tostring) + \"ms\"' 2>/dev/null" || echo "")
                else
                    metrics=$(jq -r '"    RPS: " + (.request_throughput // "N/A" | tostring) + " | P99: " + (.p99_e2e_latency_ms // "N/A" | tostring) + "ms"' "$result_file" 2>/dev/null || echo "")
                fi

                if [[ -n "$metrics" ]]; then
                    echo "$metrics"
                fi
            fi
        fi
    done || echo "  No results yet..."

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Show vllm bench process status
    echo ""
    echo -e "${GREEN}Active Test Processes:${NC}"
    if [[ "$MODE" == "remote" ]]; then
        ssh "$REMOTE_HOST" "ps aux | grep -E 'vllm.*bench.*serve' | grep -v grep" || echo "  No active tests"
    else
        ps aux | grep -E 'vllm.*bench.*serve' | grep -v grep || echo "  No active tests"
    fi

    echo ""
    echo "Last updated: $(date '+%Y-%m-%d %H:%M:%S')"
}

# Check remote connectivity if needed
if [[ "$MODE" == "remote" && -z "$REMOTE_HOST" ]]; then
    echo "ERROR: Remote host not specified"
    echo "Use --remote-host or set REMOTE_HOST environment variable"
    exit 1
fi

# Main monitoring loop
while true; do
    display_status
    sleep "$REFRESH"
done
