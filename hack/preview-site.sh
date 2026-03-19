#!/bin/bash
# Preview GitHub Pages site locally using Docker
#
# Usage: ./preview-site.sh [OPTIONS]
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
            PORT="$2"
            shift 2
            ;;
        --stop)
            STOP_SERVER=true
            shift
            ;;
        --help)
            echo "Preview GitHub Pages site locally using Docker"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT    Specify port (default: 4000)"
            echo "  --stop         Stop the Jekyll preview server"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                  # Start preview on port 4000"
            echo "  $0 --port 8080      # Start preview on port 8080"
            echo "  $0 --stop           # Stop the preview server"
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

# Check for Docker or Podman
if command -v docker &> /dev/null; then
    DOCKER_CMD="docker"
elif command -v podman &> /dev/null; then
    DOCKER_CMD="podman"
else
    echo "❌ Error: Neither Docker nor Podman found"
    echo "Please install Docker or Podman to preview the site"
    exit 1
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

echo "✓ Using $([ "$DOCKER_CMD" = "docker" ] && echo "Docker" || echo "Podman")"

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
    sh -c "bundle install && bundle exec jekyll serve --config _config.yml --watch --force_polling --livereload --host 0.0.0.0"
else
  # Non-interactive mode (background)
  $DOCKER_CMD run --rm \
    --name jekyll-preview \
    -v "$PROJECT_ROOT:/srv/jekyll:Z" \
    -p "${PORT}:4000" \
    -e JEKYLL_ENV=development \
    -w /srv/jekyll/.github-pages \
    jekyll/jekyll:latest \
    sh -c "bundle install && bundle exec jekyll serve --config _config.yml --watch --force_polling --livereload --host 0.0.0.0"
fi

echo ""
echo "✓ Jekyll server stopped"
