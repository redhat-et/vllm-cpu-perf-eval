#!/bin/bash
# Preview the documentation site locally with MkDocs.
#
# Usage: ./preview-site.sh [OPTIONS]
#
# Options:
#   --port PORT    Specify port (default: 8000)
#   --help         Show this help message

set -e

PORT=8000

while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Error: --port requires a valid port number"
                exit 1
            fi
            if ! [[ "$2" =~ ^[0-9]+$ ]] || [ "$2" -lt 1 ] || [ "$2" -gt 65535 ]; then
                echo "Error: Invalid port number '$2'"
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        --help)
            echo "Preview the documentation site locally with MkDocs"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT    Specify port (default: 8000)"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                  # Start on port 8000"
            echo "  $0 --port 4000      # Start on port 4000"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

if [ ! -x "$PROJECT_ROOT/.venv-docs/bin/mkdocs" ]; then
    echo "Creating .venv-docs and installing MkDocs dependencies..."
    python3 -m venv "$PROJECT_ROOT/.venv-docs"
    "$PROJECT_ROOT/.venv-docs/bin/pip" install -q -r requirements-docs.txt
fi
MKDOCS="$PROJECT_ROOT/.venv-docs/bin/mkdocs"

export DISABLE_MKDOCS_2_WARNING=true

echo "Starting MkDocs preview server..."
echo "Project: $PROJECT_ROOT"
echo "Preview: http://localhost:${PORT}"
echo ""
echo "Press Ctrl+C to stop"
echo ""

"$MKDOCS" serve --dev-addr "0.0.0.0:${PORT}"
