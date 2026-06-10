#!/bin/bash
# Build and push the model-downloader container image

set -e

IMAGE="quay.io/vllm-cpu-perf-eval/model-downloader:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔨 Building model-downloader container..."
podman build -t "$IMAGE" "$SCRIPT_DIR"

echo "✅ Build complete: $IMAGE"
echo ""
echo "To push to quay.io:"
echo "  podman login quay.io"
echo "  podman push $IMAGE"
echo ""
echo "To test locally:"
echo "  podman run --rm $IMAGE --help"
echo "  podman run --rm $IMAGE model --help"
echo "  podman run --rm $IMAGE dataset --help"
