#!/bin/bash
#
# Build MTEB benchmark container for vLLM CPU testing
#
# Usage:
#   ./build.sh [image-name] [--push]
#
# Examples:
#   ./build.sh vllm-mteb:latest
#   ./build.sh quay.io/vllm-cpu-perf-eval/vllm-mteb:latest --push
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

IMAGE_NAME="${1:-vllm-mteb:latest}"
PUSH_IMAGE=false

# Check for --push flag
if [[ "$2" == "--push" ]] || [[ "$1" == "--push" ]]; then
    PUSH_IMAGE=true
fi

echo "========================================="
echo "Building MTEB Container"
echo "========================================="
echo "Image: $IMAGE_NAME"
echo "Build context: $SCRIPT_DIR"
echo ""

# Build the container
podman build \
    -t "$IMAGE_NAME" \
    -f Dockerfile \
    .

# Also tag with Quay.io if building local image
if [[ "$IMAGE_NAME" == "vllm-mteb:latest" ]]; then
    echo ""
    echo "Tagging for Quay.io..."
    podman tag "$IMAGE_NAME" quay.io/vllm-cpu-perf-eval/vllm-mteb:latest
fi

echo ""
echo "========================================="
echo "✓ Build Complete"
echo "========================================="
echo "Image: $IMAGE_NAME"

# Push if requested
if [ "$PUSH_IMAGE" = true ]; then
    echo ""
    echo "Pushing to registry..."

    # Determine which image to push
    if [[ "$IMAGE_NAME" == "vllm-mteb:latest" ]]; then
        PUSH_TARGET="quay.io/vllm-cpu-perf-eval/vllm-mteb:latest"
    else
        PUSH_TARGET="$IMAGE_NAME"
    fi

    podman push "$PUSH_TARGET"
    echo "✓ Pushed: $PUSH_TARGET"
fi

echo ""
echo "Test the container:"
echo "  podman run --rm $IMAGE_NAME python -c 'import mteb; print(mteb.__version__)'"
echo ""
echo "Run MTEB benchmark:"
echo "  podman run --rm --network host \\"
echo "    -v \$PWD/results:/results:z \\"
echo "    $IMAGE_NAME \\"
echo "    python /opt/mteb/scripts/run_mteb_benchmark.py \\"
echo "      --endpoint-url http://localhost:8000 \\"
echo "      --model-name RedHatAI/granite-embedding-english-r2 \\"
echo "      --task-preset quick"

if [ "$PUSH_IMAGE" = false ]; then
    echo ""
    echo "To push to Quay.io:"
    echo "  podman login quay.io"
    echo "  ./build.sh --push"
fi
echo ""
