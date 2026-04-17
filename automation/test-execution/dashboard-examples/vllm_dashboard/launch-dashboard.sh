#!/bin/bash
#
# Launch vLLM CPU Performance Dashboard (Multipage App)
#
# Usage:
#   ./launch-dashboard.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Launching vLLM CPU Performance Dashboard ===${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/../venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running setup...${NC}"
    cd "$SCRIPT_DIR/.."
    ./setup.sh
fi

# Activate virtual environment
source "$SCRIPT_DIR/../venv/bin/activate"

echo -e "${GREEN}Starting dashboard...${NC}"
echo ""

# Launch multipage app
echo "Starting vLLM Performance Dashboard..."
streamlit run "$SCRIPT_DIR/Home.py" \
    --server.port 8501 \
    --server.headless true \
    > /tmp/streamlit-vllm-dashboard.log 2>&1 &
APP_PID=$!
echo "  PID: $APP_PID"
echo "  URL: http://localhost:8501"
echo "  Log: /tmp/streamlit-vllm-dashboard.log"
echo ""

# Wait for dashboard to start
echo "Waiting for dashboard to initialize..."
sleep 5

# Check if running
if ps -p $APP_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Dashboard started successfully!${NC}"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  vLLM CPU Performance Dashboard: http://localhost:8501"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Navigation:"
    echo "  • Home - Overview and quick start"
    echo "  • Client Metrics - GuideLLM performance analysis (multi-percentile overlay)"
    echo "  • Server Metrics - vLLM server-side metrics (time-series analysis)"
    echo ""
    echo "Switch dashboards to correlate client and server behavior."
    echo ""
    echo "To stop dashboard:"
    echo "  kill $APP_PID"
    echo ""
    echo "Or use:"
    echo "  ./stop-dashboard.sh"
    echo ""

    # Save PID for stop script
    echo "$APP_PID" > /tmp/streamlit-vllm-dashboard.pid

    # Open browser (optional - comment out if you don't want auto-open)
    if command -v open > /dev/null 2>&1; then
        sleep 2
        open http://localhost:8501
    fi
else
    echo -e "${YELLOW}⚠ Dashboard failed to start${NC}"
    echo "Check logs:"
    echo "  tail -f /tmp/streamlit-vllm-dashboard.log"
    exit 1
fi
