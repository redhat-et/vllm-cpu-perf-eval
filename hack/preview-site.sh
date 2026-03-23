#!/bin/bash
# Preview GitHub Pages site locally using Docker or Podman
#
# Usage: ./preview-site.sh [OPTIONS]
#
# Environment Variables:
#   CONTAINER_RUNTIME    Force specific runtime: 'docker' or 'podman'
#                        If not set, auto-detects available runtime
#
# Options:
#   --port PORT    Specify port (default: 4000)
#   --stop         Stop the Jekyll preview server
#   --help         Show this help message

set -e

PORT=4000
DOCKER_CMD=""
STOP_SERVER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "❌ Error: --port requires a valid port number"
                echo "Usage: $0 --port PORT"
                exit 1
            fi
            if ! [[ "$2" =~ ^[0-9]+$ ]] || [ "$2" -lt 1 ] || [ "$2" -gt 65535 ]; then
                echo "❌ Error: Invalid port number '$2'"
                echo "Port must be a number between 1 and 65535"
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        --stop)
            STOP_SERVER=true
            shift
            ;;
        --help)
            echo "Preview GitHub Pages site locally using Docker or Podman"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Environment Variables:"
            echo "  CONTAINER_RUNTIME    Force specific runtime: 'docker' or 'podman'"
            echo "                       If not set, auto-detects available runtime"
            echo ""
            echo "Options:"
            echo "  --port PORT    Specify port (default: 4000)"
            echo "  --stop         Stop the Jekyll preview server"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Auto-detect and start on port 4000"
            echo "  $0 --port 8080                  # Auto-detect and start on port 8080"
            echo "  CONTAINER_RUNTIME=podman $0     # Force Podman on port 4000"
            echo "  CONTAINER_RUNTIME=docker $0     # Force Docker on port 4000"
            echo "  $0 --stop                       # Stop the preview server"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Determine project root (parent of hack/ directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Determine container runtime
if [ -n "$CONTAINER_RUNTIME" ]; then
    # User explicitly set CONTAINER_RUNTIME
    CONTAINER_RUNTIME=$(echo "$CONTAINER_RUNTIME" | tr '[:upper:]' '[:lower:]')
    if [[ "$CONTAINER_RUNTIME" != "docker" && "$CONTAINER_RUNTIME" != "podman" ]]; then
        echo "❌ Error: Invalid CONTAINER_RUNTIME='$CONTAINER_RUNTIME'"
        echo "Must be 'docker' or 'podman'"
        exit 1
    fi
    if ! command -v "$CONTAINER_RUNTIME" &> /dev/null; then
        echo "❌ Error: $CONTAINER_RUNTIME not found"
        echo "Please install $CONTAINER_RUNTIME or unset CONTAINER_RUNTIME to auto-detect"
        exit 1
    fi
    DOCKER_CMD="$CONTAINER_RUNTIME"
    echo "✓ Using $CONTAINER_RUNTIME (forced via CONTAINER_RUNTIME)"
else
    # Auto-detect
    if command -v docker &> /dev/null; then
        DOCKER_CMD="docker"
        echo "✓ Using Docker (auto-detected)"
    elif command -v podman &> /dev/null; then
        DOCKER_CMD="podman"
        echo "✓ Using Podman (auto-detected)"
    else
        echo "❌ Error: Neither Docker nor Podman found"
        echo "Please install Docker or Podman to preview the site"
        exit 1
    fi
fi

# Handle stop command
if [ "$STOP_SERVER" = true ]; then
    echo "🛑 Stopping Jekyll preview server..."
    if $DOCKER_CMD stop jekyll-preview &> /dev/null; then
        $DOCKER_CMD rm jekyll-preview &> /dev/null
        echo "✓ Jekyll preview server stopped"
    else
        echo "ℹ️  No running Jekyll preview server found"
    fi
    exit 0
fi

echo "📦 Starting Jekyll server in container..."
echo "📍 Project: $PROJECT_ROOT"
echo "📁 Config: .github-pages/_config.yml"
echo "🌐 Preview will be available at: http://localhost:${PORT}"
echo ""
echo "⚠️  First run will install GitHub Pages gems (takes 2-3 minutes)"
echo "⚠️  Automation files are excluded to prevent Jinja2/Liquid conflicts"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run Jekyll in container with GitHub Pages support
# Mount project root and use config from .github-pages/
if [ -t 0 ]; then
  # Interactive mode
  $DOCKER_CMD run --rm -it \
    --name jekyll-preview \
    -v "$PROJECT_ROOT:/srv/jekyll:Z" \
    -p "${PORT}:4000" \
    -e JEKYLL_ENV=development \
    -w /srv/jekyll/.github-pages \
    jekyll/jekyll:latest \
    sh -c "git config --global --add safe.directory /srv/jekyll && bundle install && bundle exec jekyll serve --config _config.yml --watch --force_polling --livereload --host 0.0.0.0"
else
  # Non-interactive mode (background)
  $DOCKER_CMD run --rm \
    --name jekyll-preview \
    -v "$PROJECT_ROOT:/srv/jekyll:Z" \
    -p "${PORT}:4000" \
    -e JEKYLL_ENV=development \
    -w /srv/jekyll/.github-pages \
    jekyll/jekyll:latest \
    sh -c "git config --global --add safe.directory /srv/jekyll && bundle install && bundle exec jekyll serve --config _config.yml --watch --force_polling --livereload --host 0.0.0.0"
fi

echo ""
echo "✓ Jekyll server stopped"
