#!/bin/bash
#
# Launch MLflow Tracking Server and Setup Environment
#
# Usage:
#   ./launch-mlflow.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}      MLflow Experiment Tracking Setup & Launch        ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Step 1: Check Docker/Podman and Compose
echo -e "${BLUE}[1/4] Checking container runtime...${NC}"

# Detect compose command (prefer podman-compose)
if command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
    RUNTIME="podman"
    echo -e "${GREEN}✓ Using Podman Compose${NC}"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    RUNTIME="docker"
    echo -e "${GREEN}✓ Using Docker Compose${NC}"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    RUNTIME="docker"
    echo -e "${GREEN}✓ Using docker-compose (legacy)${NC}"
else
    echo -e "${RED}✗ No compose command found${NC}"
    echo "Please install one of:"
    echo "  - podman-compose: brew install podman-compose"
    echo "  - Docker Desktop (includes docker compose)"
    exit 1
fi

# Check if runtime is available
if [ "$RUNTIME" = "podman" ]; then
    if ! command -v podman &> /dev/null; then
        echo -e "${RED}✗ Podman is not installed${NC}"
        exit 1
    fi
    if ! podman info &> /dev/null; then
        echo -e "${RED}✗ Podman is not running${NC}"
        echo "Start Podman machine: podman machine start"
        exit 1
    fi
else
    if ! docker info &> /dev/null; then
        echo -e "${RED}✗ Docker is not running${NC}"
        echo "Please start Docker Desktop"
        exit 1
    fi
fi
echo ""

# Step 2: Setup Python Virtual Environment
echo -e "${BLUE}[2/4] Setting up Python environment...${NC}"

# Create venv if it doesn't exist
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/venv"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    else
        echo -e "${RED}✗ Failed to create virtual environment${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate venv
echo "Activating virtual environment..."
source "$SCRIPT_DIR/venv/bin/activate"

# Upgrade pip in venv (suppress noise)
pip install --upgrade pip --quiet --no-cache-dir 2>&1 | grep -v "already satisfied" | grep -v "Cache entry" || true

# Install/update mlflow in venv
if python3 -c "import mlflow" &> /dev/null; then
    MLFLOW_VERSION=$(python3 -c "import mlflow; print(mlflow.__version__)")
    echo -e "${GREEN}✓ MLflow ${MLFLOW_VERSION} is installed${NC}"
else
    echo "Installing MLflow in virtual environment..."
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet --no-cache-dir 2>&1 | grep -v "Cache entry" || true
    if python3 -c "import mlflow" &> /dev/null; then
        MLFLOW_VERSION=$(python3 -c "import mlflow; print(mlflow.__version__)")
        echo -e "${GREEN}✓ MLflow ${MLFLOW_VERSION} installed${NC}"
    else
        echo -e "${RED}✗ Failed to install MLflow${NC}"
        exit 1
    fi
fi
echo ""

# Step 3: Start MLflow Tracking Server (Docker)
echo -e "${BLUE}[3/4] Starting MLflow Tracking Server...${NC}"

cd "$SCRIPT_DIR"

# Check if already running
CONTAINER_CHECK_CMD="${RUNTIME} ps"
if $CONTAINER_CHECK_CMD | grep -q mlflow-tracking-server; then
    echo -e "${YELLOW}⚠ MLflow server is already running${NC}"
    CONTAINER_ID=$($CONTAINER_CHECK_CMD -qf "name=mlflow-tracking-server")
    echo "Container ID: $CONTAINER_ID"
else
    # Start with compose
    if [ -f docker-compose.yml ]; then
        $COMPOSE_CMD up -d
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ MLflow server started${NC}"
            CONTAINER_ID=$($CONTAINER_CHECK_CMD -qf "name=mlflow-tracking-server")
        else
            echo -e "${RED}✗ Failed to start MLflow server${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ docker-compose.yml not found in $SCRIPT_DIR${NC}"
        exit 1
    fi
fi

# Save container ID for stop script
echo "$CONTAINER_ID" > /tmp/mlflow-tracking-server.pid

echo ""

# Step 4: Wait for server to be ready
echo -e "${BLUE}[4/4] Waiting for MLflow server to initialize...${NC}"
MAX_WAIT=30
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ MLflow server is ready!${NC}"
        break
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    echo -n "."
done
echo ""

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ MLflow server failed to start within ${MAX_WAIT}s${NC}"
    echo "Check logs with: docker logs mlflow-tracking-server"
    exit 1
fi

echo ""

# Set environment variable for current session
export MLFLOW_TRACKING_URI=http://localhost:5000

# Persist to shell rc files
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "MLFLOW_TRACKING_URI" "$SHELL_RC"; then
        echo "" >> "$SHELL_RC"
        echo "# MLflow Tracking URI" >> "$SHELL_RC"
        echo "export MLFLOW_TRACKING_URI=http://localhost:5000" >> "$SHELL_RC"
        echo -e "${GREEN}✓ Added MLFLOW_TRACKING_URI to $SHELL_RC${NC}"
    fi
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}      MLflow Setup Complete!                           ${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📊 MLflow UI:${NC}       http://localhost:5000"
echo -e "${BLUE}🐳 Container:${NC}       mlflow-tracking-server (${CONTAINER_ID:0:12})"
echo -e "${BLUE}🚀 Runtime:${NC}         ${RUNTIME} (${COMPOSE_CMD})"
echo -e "${BLUE}🐍 Python:${NC}          Virtual environment at $SCRIPT_DIR/venv"
echo -e "${BLUE}📁 Data:${NC}            Docker volume 'mlflow-data'"
echo -e "${BLUE}📦 Artifacts:${NC}       $SCRIPT_DIR/artifacts/"
echo ""
echo -e "${YELLOW}Environment Variable:${NC}"
echo "  export MLFLOW_TRACKING_URI=http://localhost:5000"
echo ""
echo -e "${YELLOW}To use the MLflow Python client:${NC}"
echo "  source $SCRIPT_DIR/venv/bin/activate"
echo ""
echo -e "${YELLOW}Quick Start:${NC}"
echo "  # Import all benchmark results"
echo "  cd ../ansible/scripts"
echo "  ./mlflow-quick-log.sh --all"
echo ""
echo "  # Or import latest test only"
echo "  ./mlflow-quick-log.sh --latest"
echo ""
echo -e "${YELLOW}Stop MLflow:${NC}"
echo "  $SCRIPT_DIR/stop-mlflow.sh"
echo ""
echo -e "${YELLOW}View Logs:${NC}"
echo "  ${RUNTIME} logs mlflow-tracking-server"
echo "  ${RUNTIME} logs -f mlflow-tracking-server  # Follow logs"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Open browser (optional - comment out if you don't want auto-open)
if command -v open > /dev/null 2>&1; then
    echo ""
    echo "Opening MLflow UI in browser..."
    sleep 2
    open http://localhost:5000
fi

echo ""
echo -e "${GREEN}✓ Ready to track experiments!${NC}"
echo ""
