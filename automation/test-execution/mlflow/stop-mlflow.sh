#!/bin/bash
#
# Stop MLflow Tracking Server
#
# Usage:
#   ./stop-mlflow.sh
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}      Stopping MLflow Tracking Server                  ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Detect compose command (prefer podman-compose)
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
    RUNTIME="podman"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    RUNTIME="docker"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    RUNTIME="docker"
else
    COMPOSE_CMD=""
    RUNTIME="docker"  # fallback
fi

# Stop by container name (compose)
cd "$SCRIPT_DIR"

if [ -f docker-compose.yml ] && [ -n "$COMPOSE_CMD" ]; then
    echo "Stopping MLflow server (${COMPOSE_CMD})..."
    $COMPOSE_CMD down
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ MLflow server stopped${NC}"
    else
        echo -e "${YELLOW}⚠ Compose down failed, trying manual stop...${NC}"
    fi
fi

# Fallback: Stop by container name
CONTAINER_CHECK_CMD="${RUNTIME} ps"
if $CONTAINER_CHECK_CMD 2>/dev/null | grep -q mlflow-tracking-server; then
    echo "Stopping container mlflow-tracking-server..."
    ${RUNTIME} stop mlflow-tracking-server
    echo -e "${GREEN}✓ Container stopped${NC}"
fi

# Cleanup PID file
if [ -f /tmp/mlflow-tracking-server.pid ]; then
    rm /tmp/mlflow-tracking-server.pid
fi

echo ""
echo -e "${BLUE}📁 Data Preserved:${NC}"
echo "  • Docker volume: mlflow-data"
echo "  • Artifacts: $SCRIPT_DIR/artifacts/"
echo ""
echo -e "${YELLOW}To completely remove MLflow data:${NC}"
echo "  cd $SCRIPT_DIR"
if [ -n "$COMPOSE_CMD" ]; then
    echo "  ${COMPOSE_CMD} down -v  # Remove volumes"
fi
echo "  rm -rf artifacts/           # Remove artifact files"
echo ""
echo -e "${YELLOW}View server logs (if needed):${NC}"
echo "  ${RUNTIME} logs mlflow-tracking-server"
echo ""
echo -e "${YELLOW}To restart MLflow:${NC}"
echo "  $SCRIPT_DIR/launch-mlflow.sh"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ MLflow stopped successfully${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
