#!/bin/bash
#
# Build lm-eval benchmark container for vLLM CPU accuracy testing
#
# Usage:
#   ./build.sh [image-name] [--push]
#
# Examples:
#   ./build.sh lm-eval:latest
#   ./build.sh quay.io/vllm-cpu-perf-eval/lm-eval:latest --push
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

IMAGE_NAME="lm-eval:latest"
PUSH_IMAGE=false

for arg in "$@"; do
    case "$arg" in
        --push)
            PUSH_IMAGE=true
            ;;
        -*)
            echo "Unknown option: $arg"
            exit 1
            ;;
        *)
            IMAGE_NAME="$arg"
            ;;
    esac
done

echo "========================================="
echo "Building lm-eval Container"
echo "========================================="
echo "Image: $IMAGE_NAME"
echo "Build context: $SCRIPT_DIR"
echo ""

podman build \
    -t "$IMAGE_NAME" \
    -f Dockerfile \
    .

if [[ "$IMAGE_NAME" == "lm-eval:latest" ]]; then
    echo ""
    echo "Tagging for Quay.io..."
    podman tag "$IMAGE_NAME" quay.io/vllm-cpu-perf-eval/lm-eval:latest
fi

echo ""
echo "========================================="
echo "✓ Build Complete"
echo "========================================="
echo "Image: $IMAGE_NAME"

if [ "$PUSH_IMAGE" = true ]; then
    echo ""
    echo "Pushing to registry..."
    if [[ "$IMAGE_NAME" == "lm-eval:latest" ]]; then
        PUSH_TARGET="quay.io/vllm-cpu-perf-eval/lm-eval:latest"
    else
        PUSH_TARGET="$IMAGE_NAME"
    fi
    podman push "$PUSH_TARGET"
    echo "✓ Pushed: $PUSH_TARGET"
fi

echo ""
echo "Test the container:"
echo "  podman run --rm $IMAGE_NAME --help"
echo ""
echo "Run lm-eval benchmark against a running vLLM server:"
echo "  podman run --rm --network host \\"
echo "    -v \$PWD/results:/results:z \\"
echo "    $IMAGE_NAME \\"
echo "    --model local-completions \\"
echo "    --model_args model=meta-llama/Llama-3.2-1B-Instruct,base_url=http://localhost:8000/v1/completions,tokenizer=meta-llama/Llama-3.2-1B-Instruct \\"
echo "    --tasks hellaswag \\"
echo "    --batch_size 16 \\"
echo "    --output_path /results"

if [ "$PUSH_IMAGE" = false ]; then
    echo ""
    echo "To push to Quay.io:"
    echo "  podman login quay.io"
    echo "  ./build.sh --push"
fi
echo ""
