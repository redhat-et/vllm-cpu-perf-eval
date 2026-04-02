#!/usr/bin/env bash
#
# SSH Tunnel Setup for vLLM Metrics Collection
#
# Creates reverse SSH tunnel for Pushgateway (LOADGEN → local)
# Creates forward tunnel for live vLLM metrics (local → DUT)
#
# Usage:
#   ./setup-tunnels.sh
#
# Environment variables (or set in script):
#   DUT_HOSTNAME        - DUT EC2 hostname (required)
#   LOADGEN_HOSTNAME    - LOADGEN EC2 hostname (required)
#   ANSIBLE_SSH_USER    - SSH username (default: ec2-user)
#   ANSIBLE_SSH_KEY     - SSH key path (required)
#   PROMETHEUS_PORT     - Prometheus port (default: 9091, or use 9090)

set -e

# Configuration
: "${DUT_HOSTNAME:=}"
: "${LOADGEN_HOSTNAME:=}"
: "${ANSIBLE_SSH_USER:=ec2-user}"
: "${ANSIBLE_SSH_KEY:=}"

PUSHGATEWAY_PORT="${PROMETHEUS_PORT:-9091}"
VLLM_METRICS_PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== vLLM Metrics SSH Tunnel Setup ===${NC}"
echo ""
echo "Configuration:"
echo "  DUT: ${DUT_HOSTNAME}"
echo "  LOADGEN: ${LOADGEN_HOSTNAME}"
echo "  SSH User: ${ANSIBLE_SSH_USER}"
echo "  SSH Key: ${ANSIBLE_SSH_KEY}"
echo ""

# Check if SSH key exists
if [ ! -f "${ANSIBLE_SSH_KEY}" ]; then
    echo -e "${RED}ERROR: SSH key not found: ${ANSIBLE_SSH_KEY}${NC}"
    exit 1
fi

# Check if local Pushgateway is running
if ! curl -s http://localhost:${PUSHGATEWAY_PORT}/-/healthy > /dev/null 2>&1; then
    echo -e "${YELLOW}WARNING: Local Pushgateway not running on port ${PUSHGATEWAY_PORT}${NC}"
    echo "Start it with: cd automation/test-execution/grafana && docker-compose up -d pushgateway"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to create reverse tunnel for Pushgateway
setup_pushgateway_tunnel() {
    echo -e "${GREEN}Setting up reverse tunnel for Pushgateway (LOADGEN → local)...${NC}"
    echo "  LOADGEN localhost:${PUSHGATEWAY_PORT} → Your machine localhost:${PUSHGATEWAY_PORT}"

    # Kill existing tunnel if any
    pkill -f "ssh.*${LOADGEN_HOSTNAME}.*${PUSHGATEWAY_PORT}:localhost:${PUSHGATEWAY_PORT}" 2>/dev/null || true

    # Create reverse tunnel in background
    ssh -i "${ANSIBLE_SSH_KEY}" \
        -R ${PUSHGATEWAY_PORT}:localhost:${PUSHGATEWAY_PORT} \
        -N -f \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        "${ANSIBLE_SSH_USER}@${LOADGEN_HOSTNAME}"

    sleep 2

    # Verify tunnel
    if pgrep -f "ssh.*${LOADGEN_HOSTNAME}.*${PUSHGATEWAY_PORT}:localhost:${PUSHGATEWAY_PORT}" > /dev/null; then
        echo -e "${GREEN}✓ Pushgateway reverse tunnel established${NC}"
        echo "  Ansible on LOADGEN can now push to: http://localhost:${PUSHGATEWAY_PORT}"
    else
        echo -e "${RED}✗ Failed to establish reverse tunnel${NC}"
        return 1
    fi
}

# Function to create forward tunnel for vLLM live metrics
setup_vllm_tunnel() {
    echo -e "${GREEN}Setting up forward tunnel for vLLM metrics (local → DUT)...${NC}"
    echo "  Your machine localhost:${VLLM_METRICS_PORT} → DUT localhost:${VLLM_METRICS_PORT}"

    # Kill existing tunnel if any
    pkill -f "ssh.*${DUT_HOSTNAME}.*${VLLM_METRICS_PORT}:localhost:${VLLM_METRICS_PORT}" 2>/dev/null || true

    # Create forward tunnel in background
    ssh -i "${ANSIBLE_SSH_KEY}" \
        -L ${VLLM_METRICS_PORT}:localhost:${VLLM_METRICS_PORT} \
        -N -f \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        "${ANSIBLE_SSH_USER}@${DUT_HOSTNAME}"

    sleep 2

    # Verify tunnel
    if pgrep -f "ssh.*${DUT_HOSTNAME}.*${VLLM_METRICS_PORT}:localhost:${VLLM_METRICS_PORT}" > /dev/null; then
        echo -e "${GREEN}✓ vLLM metrics forward tunnel established${NC}"
        echo "  Prometheus can now scrape: http://localhost:${VLLM_METRICS_PORT}/metrics"
    else
        echo -e "${YELLOW}⚠ Forward tunnel may not be active (vLLM must be running on DUT)${NC}"
    fi
}

# Function to check tunnel status
check_tunnels() {
    echo ""
    echo -e "${GREEN}=== Tunnel Status ===${NC}"

    # Check reverse tunnel
    if pgrep -f "ssh.*${LOADGEN_HOSTNAME}.*${PUSHGATEWAY_PORT}" > /dev/null; then
        echo -e "${GREEN}✓ Pushgateway reverse tunnel: ACTIVE${NC}"
    else
        echo -e "${RED}✗ Pushgateway reverse tunnel: DOWN${NC}"
    fi

    # Check forward tunnel
    if pgrep -f "ssh.*${DUT_HOSTNAME}.*${VLLM_METRICS_PORT}" > /dev/null; then
        echo -e "${GREEN}✓ vLLM metrics forward tunnel: ACTIVE${NC}"

        # Try to access vLLM metrics
        if curl -s http://localhost:${VLLM_METRICS_PORT}/metrics > /dev/null 2>&1; then
            echo -e "${GREEN}  └─ vLLM /metrics endpoint: ACCESSIBLE${NC}"
        else
            echo -e "${YELLOW}  └─ vLLM /metrics endpoint: NOT ACCESSIBLE (is vLLM running?)${NC}"
        fi
    else
        echo -e "${RED}✗ vLLM metrics forward tunnel: DOWN${NC}"
    fi
}

# Function to stop tunnels
stop_tunnels() {
    echo ""
    echo -e "${YELLOW}Stopping all tunnels...${NC}"
    pkill -f "ssh.*${LOADGEN_HOSTNAME}.*${PUSHGATEWAY_PORT}" 2>/dev/null || true
    pkill -f "ssh.*${DUT_HOSTNAME}.*${VLLM_METRICS_PORT}" 2>/dev/null || true
    echo -e "${GREEN}✓ Tunnels stopped${NC}"
}

# Main execution
case "${1:-setup}" in
    setup)
        setup_pushgateway_tunnel
        setup_vllm_tunnel
        check_tunnels
        echo ""
        echo -e "${GREEN}=== Setup Complete ===${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Verify Prometheus is scraping:"
        echo "     open http://localhost:9090/targets"
        echo ""
        echo "  2. Run benchmarks with publishing enabled:"
        echo "     ansible-playbook llm-benchmark-auto.yml -e publish_to_prometheus=true"
        echo ""
        echo "  3. View results in Grafana:"
        echo "     open http://localhost:3000"
        echo ""
        echo "To check tunnel status: $0 status"
        echo "To stop tunnels: $0 stop"
        ;;

    status)
        check_tunnels
        ;;

    stop)
        stop_tunnels
        ;;

    *)
        echo "Usage: $0 {setup|status|stop}"
        exit 1
        ;;
esac
