#!/bin/bash
# Test script for vllm-cpu-perf-eval container

set -e

IMAGE_NAME="vllm-cpu-perf-eval"
IMAGE_TAG="test"

echo "=== Building Container ==="
podman build -t ${IMAGE_NAME}:${IMAGE_TAG} -f Containerfile .

echo ""
echo "=== Testing Python Version ==="
podman run --rm ${IMAGE_NAME}:${IMAGE_TAG} python --version

echo ""
echo "=== Testing vLLM Installation ==="
podman run --rm ${IMAGE_NAME}:${IMAGE_TAG} python -c "import vllm; print(f'vLLM version: {vllm.__version__}')"

echo ""
echo "=== Testing GuideLLM Installation ==="
podman run --rm ${IMAGE_NAME}:${IMAGE_TAG} python -c "import guidellm; print('GuideLLM installed successfully')"

echo ""
echo "=== Testing System Info ==="
podman run --rm ${IMAGE_NAME}:${IMAGE_TAG} bash -c "
echo 'OS Release:'
cat /etc/redhat-release
echo ''
echo 'CPU Info:'
lscpu | grep 'Model name'
echo ''
echo 'Memory:'
free -h
"

echo ""
echo "=== Testing vLLM CLI ==="
podman run --rm ${IMAGE_NAME}:${IMAGE_TAG} vllm --help | head -20

echo ""
echo "=== Testing GuideLLM CLI ==="
podman run --rm ${IMAGE_NAME}:${IMAGE_TAG} guidellm --help | head -20

echo ""
echo "=== Container Size ==="
podman images ${IMAGE_NAME}:${IMAGE_TAG}

echo ""
echo "✅ All tests passed!"
echo ""
echo "To run interactively:"
echo "  podman run -it --rm ${IMAGE_NAME}:${IMAGE_TAG} /bin/bash"
