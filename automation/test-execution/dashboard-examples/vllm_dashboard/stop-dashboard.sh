#!/bin/bash
#
# Stop vLLM CPU Performance Dashboard
#
# Usage:
#   ./stop-dashboard.sh
#

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Stopping vLLM CPU Performance Dashboard ===${NC}"
echo ""

# Kill by PID file if it exists
if [ -f /tmp/streamlit-vllm-dashboard.pid ]; then
    DASHBOARD_PID=$(cat /tmp/streamlit-vllm-dashboard.pid)
    if ps -p $DASHBOARD_PID > /dev/null 2>&1; then
        echo "Stopping Dashboard (PID: $DASHBOARD_PID)..."
        kill $DASHBOARD_PID
        rm /tmp/streamlit-vllm-dashboard.pid
    fi
fi

# Fallback: Kill all streamlit processes on port 8501
pkill -f "streamlit.*8501" 2>/dev/null || true

echo -e "${GREEN}✓ Dashboard stopped${NC}"
echo ""
echo "Logs preserved at:"
echo "  /tmp/streamlit-vllm-dashboard.log"
