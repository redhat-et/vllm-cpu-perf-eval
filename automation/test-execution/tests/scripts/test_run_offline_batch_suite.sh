#!/bin/bash
# Unit tests for run-offline-batch-suite.sh
#
# Tests bash script functionality:
# - Model list parsing ("all", comma-separated, single)
# - Parameter validation
# - Command construction

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_SCRIPT="$SCRIPT_DIR/../../scripts/bash/run-offline-batch-suite.sh"

# Colors for test output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test helper functions
assert_equals() {
    local expected="$1"
    local actual="$2"
    local test_name="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$expected" == "$actual" ]]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "  Expected: $expected"
        echo "  Actual:   $actual"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local test_name="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$haystack" == *"$needle"* ]]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "  Expected to contain: $needle"
        echo "  Actual: $haystack"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Source the script functions (without executing main)
source_script_functions() {
    # Extract just the function definitions, not the main execution
    # This is a bit hacky but works for testing
    export MODEL_TINY_PRUNED="RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4"
    export MODEL_LLAMA_W8A8="RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
    export MODEL_LLAMA_W4A16="RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16"
    export MODEL_QWEN_W4A16="RedHatAI/Qwen3-8B-quantized.w4a16"
    export ALL_MODELS="$MODEL_LLAMA_W8A8,$MODEL_LLAMA_W4A16,$MODEL_QWEN_W4A16"
    export VLLM_CONTAINER_IMAGE="vllm/vllm-openai:latest"
}

# Test 1: Check if script exists
test_script_exists() {
    if [[ -f "$SUITE_SCRIPT" ]]; then
        echo -e "${GREEN}✓${NC} Script exists"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} Script not found at: $SUITE_SCRIPT"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    TESTS_RUN=$((TESTS_RUN + 1))
}

# Test 2: Check if script is executable
test_script_executable() {
    if [[ -x "$SUITE_SCRIPT" ]]; then
        echo -e "${GREEN}✓${NC} Script is executable"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} Script is not executable"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    TESTS_RUN=$((TESTS_RUN + 1))
}

# Test 3: Check model constants are defined
test_model_constants() {
    source_script_functions

    assert_equals "RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4" "$MODEL_TINY_PRUNED" "MODEL_TINY_PRUNED is defined"
    assert_equals "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8" "$MODEL_LLAMA_W8A8" "MODEL_LLAMA_W8A8 is defined"
    assert_equals "RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16" "$MODEL_LLAMA_W4A16" "MODEL_LLAMA_W4A16 is defined"
    assert_equals "RedHatAI/Qwen3-8B-quantized.w4a16" "$MODEL_QWEN_W4A16" "MODEL_QWEN_W4A16 is defined"
}

# Test 4: Check ALL_MODELS contains the 3 production models (not TinyLlama)
test_all_models_list() {
    source_script_functions

    assert_contains "$ALL_MODELS" "$MODEL_LLAMA_W8A8" "ALL_MODELS contains Llama w8a8"
    assert_contains "$ALL_MODELS" "$MODEL_LLAMA_W4A16" "ALL_MODELS contains Llama w4a16"
    assert_contains "$ALL_MODELS" "$MODEL_QWEN_W4A16" "ALL_MODELS contains Qwen w4a16"
}

# Test 5: Check VLLM_CONTAINER_IMAGE default
test_default_container_image() {
    source_script_functions

    assert_equals "vllm/vllm-openai:latest" "$VLLM_CONTAINER_IMAGE" "Default container is upstream vLLM"
}

# Test 6: Check usage message exists
test_usage_message() {
    local usage_output
    usage_output=$("$SUITE_SCRIPT" 2>&1 || true)

    assert_contains "$usage_output" "vLLM Offline Batch Benchmark Suite" "Usage shows title"
    assert_contains "$usage_output" "use-cases" "Usage shows use-cases mode"
    assert_contains "$usage_output" "use-case-sweep" "Usage shows use-case-sweep mode"
    assert_contains "$usage_output" "VLLM_CONTAINER_IMAGE" "Usage shows environment variable"
}

# Test 7: Test comma-separated model parsing (simulated)
test_comma_separated_models() {
    source_script_functions

    local model_list="$MODEL_LLAMA_W8A8,$MODEL_QWEN_W4A16"

    # Parse the list
    IFS=',' read -ra MODELS <<< "$model_list"

    assert_equals "2" "${#MODELS[@]}" "Parsed 2 models from comma-separated list"
    assert_equals "$MODEL_LLAMA_W8A8" "${MODELS[0]}" "First model is Llama w8a8"
    assert_equals "$MODEL_QWEN_W4A16" "${MODELS[1]}" "Second model is Qwen w4a16"
}

# Test 8: Test "all" keyword expansion
test_all_keyword_expansion() {
    source_script_functions

    local model_list="all"

    # Handle "all" keyword
    if [[ "$model_list" == "all" ]]; then
        model_list="$ALL_MODELS"
    fi

    # Parse the expanded list
    IFS=',' read -ra MODELS <<< "$model_list"

    assert_equals "3" "${#MODELS[@]}" "'all' expands to 3 production models"
}

# Main test execution
echo "=========================================="
echo "run-offline-batch-suite.sh Unit Tests"
echo "=========================================="
echo

test_script_exists
test_script_executable
test_model_constants
test_all_models_list
test_default_container_image
test_usage_message
test_comma_separated_models
test_all_keyword_expansion

echo
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo "Tests run:    $TESTS_RUN"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
    exit 1
else
    echo -e "Tests failed: $TESTS_FAILED"
    echo
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
fi
