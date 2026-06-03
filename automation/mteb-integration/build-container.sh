#!/bin/bash
#
# Build MTEB benchmark container for vLLM CPU testing
#
# Usage:
#   ./build-container.sh [image-name]
#
# Example:
#   ./build-container.sh vllm-mteb:latest
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

IMAGE_NAME="${1:-vllm-mteb:latest}"

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

echo ""
echo "========================================="
echo "✓ Build Complete"
echo "========================================="
echo "Image: $IMAGE_NAME"
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
echo ""
