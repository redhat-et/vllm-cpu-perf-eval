#!/bin/bash
# Idempotent setup script for Streamlit dashboards
# Safe to run multiple times

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { echo "Error: Cannot change to script directory"; exit 1; }

echo "Setting up Python virtual environment for dashboards..."
echo ""

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate venv
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip (idempotent)
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install/update dependencies (idempotent)
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "✅ Setup complete!"
echo ""
echo "To launch the dashboard:"
echo "  cd vllm_dashboard"
echo "  ./launch-dashboard.sh"
echo ""
echo "Dashboard will open at: http://localhost:8501"
echo ""
echo "Features:"
echo "  📊 Client Metrics - GuideLLM performance analysis"
echo "  🖥️ Server Metrics - vLLM server-side metrics"
echo "  🔄 Unified View   - Combined client + server analysis"
echo "  🏠 Home Page      - Overview and navigation"
echo ""
echo "Navigate between views using the sidebar."
echo ""
