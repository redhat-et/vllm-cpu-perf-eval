#!/bin/bash
# Run full embedding test suite across all RedHatAI models and core counts
# Usage: ./run-embedding-suite.sh

set -e  # Exit on error

# Ensure we're in the repo root
if [ ! -f "automation/test-execution/ansible/embedding-benchmark.yml" ]; then
    echo "ERROR: Must run from repository root directory"
    echo "Expected file: automation/test-execution/ansible/embedding-benchmark.yml"
    exit 1
fi

# Check for required environment variables
if [ -z "$VLLM_CONTAINER_IMAGE" ]; then
    echo "WARNING: VLLM_CONTAINER_IMAGE not set. Using default image."
    echo "To use a custom image:"
    echo "  export VLLM_CONTAINER_IMAGE=registry.redhat.io/rhaii/vllm-cpu-rhel9:3.4.0"
    echo ""
else
    echo "Using custom vLLM image: $VLLM_CONTAINER_IMAGE"
    echo ""
fi

# Models from https://huggingface.co/collections/RedHatAI/intel-xeon-compatible-models
# Priority models (today - 1.5 hour target)
MODELS=(
    "RedHatAI/granite-embedding-english-r2"
    "RedHatAI/embeddinggemma-300m"
)

# Remaining models (tomorrow)
# "RedHatAI/all-MiniLM-L6-v2"
# "RedHatAI/nomic-embed-text-v1.5"
# "RedHatAI/Qwen3-Embedding-8B"

# Core counts to test
CORE_COUNTS=(8 16 32)

# Test configuration
SCENARIO="all"  # Run both baseline and latency tests
NUM_PROMPTS=250  # Default: 250 (use 10 for quick testing)

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Embedding Model Test Suite"
echo "=========================================="
echo "Models: ${#MODELS[@]}"
echo "Core counts: ${CORE_COUNTS[@]}"
echo "Scenario: ${SCENARIO}"
echo "Prompts per test: ${NUM_PROMPTS}"
echo "=========================================="
echo ""

# Calculate total tests
TOTAL_TESTS=$((${#MODELS[@]} * ${#CORE_COUNTS[@]}))
CURRENT_TEST=0

# Track results
PASSED_TESTS=0
FAILED_TESTS=0
FAILED_LIST=()

# Start timestamp
START_TIME=$(date +%s)

# Loop through models and core counts
for model in "${MODELS[@]}"; do
    for cores in "${CORE_COUNTS[@]}"; do
        CURRENT_TEST=$((CURRENT_TEST + 1))

        echo ""
        echo -e "${YELLOW}=========================================="
        echo -e "Test ${CURRENT_TEST}/${TOTAL_TESTS}"
        echo -e "==========================================${NC}"
        echo "Model: ${model}"
        echo "Cores: ${cores}"
        echo "Scenario: ${SCENARIO}"
        echo ""

        # Create test name
        MODEL_SHORT=$(echo "${model}" | cut -d'/' -f2)
        TEST_NAME="${MODEL_SHORT}-${cores}C"

        # Run test
        if ansible-playbook -i automation/test-execution/ansible/inventory/hosts.yml \
            automation/test-execution/ansible/embedding-benchmark.yml \
            -e "test_model=${model}" \
            -e "scenario=${SCENARIO}" \
            -e "requested_cores=${cores}" \
            -e "num_prompts=${NUM_PROMPTS}" \
            -e "test_name=${TEST_NAME}"; then

            echo -e "${GREEN}✓ Test passed: ${TEST_NAME}${NC}"
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            echo -e "${RED}✗ Test failed: ${TEST_NAME}${NC}"
            FAILED_TESTS=$((FAILED_TESTS + 1))
            FAILED_LIST+=("${TEST_NAME}")
        fi

        # Brief pause between tests to ensure clean shutdown
        if [ ${CURRENT_TEST} -lt ${TOTAL_TESTS} ]; then
            echo ""
            echo "Waiting 10 seconds before next test..."
            sleep 10
        fi
    done
done

# End timestamp and duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
HOURS=$((DURATION / 3600))
MINUTES=$(( (DURATION % 3600) / 60 ))
SECONDS=$((DURATION % 60))

# Summary
echo ""
echo "=========================================="
echo "Test Suite Complete"
echo "=========================================="
echo "Total tests: ${TOTAL_TESTS}"
echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"
if [ ${FAILED_TESTS} -gt 0 ]; then
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
    echo ""
    echo "Failed tests:"
    for test in "${FAILED_LIST[@]}"; do
        echo -e "  ${RED}✗${NC} ${test}"
    done
fi
echo ""
echo "Duration: ${HOURS}h ${MINUTES}m ${SECONDS}s"
echo "=========================================="

# Results location
echo ""
echo "Results saved to: results/embedding/"
echo ""
echo "To view results:"
echo "  cd automation/test-execution/dashboard-examples/vllm_dashboard"
echo "  ./launch-dashboard.sh"
echo ""

# Exit with error if any tests failed
if [ ${FAILED_TESTS} -gt 0 ]; then
    exit 1
fi
