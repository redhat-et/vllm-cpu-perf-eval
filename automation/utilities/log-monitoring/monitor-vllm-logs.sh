#!/usr/bin/env bash
# Monitor vLLM server logs
# Can connect to local container or remote host via SSH

set -euo pipefail

# Default values
MODE="${MODE:-local}"  # local or remote
REMOTE_HOST="${REMOTE_HOST:-}"
CONTAINER_NAME="${CONTAINER_NAME:-vllm-embedding-server}"
CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-podman}"
FOLLOW="${FOLLOW:-true}"
LINES="${LINES:-100}"

# Colors
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Monitor vLLM server container logs.

Options:
    --mode MODE            'local' or 'remote' (default: local)
    --remote-host HOST     SSH host for remote monitoring
    --container NAME       Container name (default: vllm-embedding-server)
    --runtime RUNTIME      Container runtime: podman or docker (default: podman)
    --follow               Follow log output (default: true)
    --no-follow            Don't follow, just show recent logs
    --lines N              Number of lines to show (default: 100)
    -h, --help             Show this help message

Environment Variables:
    MODE                   Override mode (local/remote)
    REMOTE_HOST            Remote host for SSH connection
    CONTAINER_NAME         Override container name
    CONTAINER_RUNTIME      Override container runtime

Examples:
    # Monitor local vLLM container
    $0

    # Monitor local with more history
    $0 --lines 500

    # Monitor remote vLLM server
    $0 --mode remote --remote-host 192.168.1.10

    # Show last 50 lines without following
    $0 --no-follow --lines 50

    # Monitor via SSH with custom container name
    MODE=remote REMOTE_HOST=dut-node-01 $0

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
        --container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --runtime)
            CONTAINER_RUNTIME="$2"
            shift 2
            ;;
        --follow)
            FOLLOW=true
            shift
            ;;
        --no-follow)
            FOLLOW=false
            shift
            ;;
        --lines)
            LINES="$2"
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

# Build log command
LOG_CMD="${CONTAINER_RUNTIME} logs"
if ${FOLLOW}; then
    LOG_CMD="${LOG_CMD} -f"
fi
LOG_CMD="${LOG_CMD} --tail ${LINES} ${CONTAINER_NAME}"

# Display header
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [[ "$MODE" == "remote" ]]; then
    echo -e "${BLUE}vLLM Logs: ${REMOTE_HOST}:${CONTAINER_NAME}${NC}"
else
    echo -e "${BLUE}vLLM Logs: ${CONTAINER_NAME} (local)${NC}"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Execute log command
if [[ "$MODE" == "remote" ]]; then
    if [[ -z "$REMOTE_HOST" ]]; then
        echo "ERROR: Remote host not specified"
        echo "Use --remote-host or set REMOTE_HOST environment variable"
        exit 1
    fi

    echo "Connecting to ${REMOTE_HOST}..."
    ssh "$REMOTE_HOST" "$LOG_CMD"
else
    # Local mode
    if ! command -v "$CONTAINER_RUNTIME" &> /dev/null; then
        echo "ERROR: ${CONTAINER_RUNTIME} not found"
        echo "Please install ${CONTAINER_RUNTIME} or specify correct runtime with --runtime"
        exit 1
    fi

    # Check if container exists
    if ! ${CONTAINER_RUNTIME} ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
        echo "ERROR: Container '${CONTAINER_NAME}' not found"
        echo "Available containers:"
        ${CONTAINER_RUNTIME} ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
        exit 1
    fi

    exec $LOG_CMD
fi
