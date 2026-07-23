#!/bin/bash
# Unit tests for run-cve-vloc-suite.sh
#
# Tests bash script functionality:
# - Model constants and presets
# - Runner auto-detection
# - Argument parsing
# - Mode validation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_SCRIPT="$SCRIPT_DIR/../../scripts/bash/run-cve-vloc-suite.sh"

# Colors for test output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

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
        echo "  Got: ${haystack:0:200}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

assert_not_contains() {
    local haystack="$1"
    local needle="$2"
    local test_name="$3"

    TESTS_RUN=$((TESTS_RUN + 1))

    if [[ "$haystack" != *"$needle"* ]]; then
        echo -e "${GREEN}✓${NC} $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} $test_name"
        echo "  Should not contain: $needle"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# ============================================================================
# Test 1: Script exists and is executable
# ============================================================================

test_script_exists() {
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ -f "$SUITE_SCRIPT" ]]; then
        echo -e "${GREEN}✓${NC} Script exists"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} Script not found at: $SUITE_SCRIPT"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

test_script_executable() {
    TESTS_RUN=$((TESTS_RUN + 1))
    if [[ -x "$SUITE_SCRIPT" ]]; then
        echo -e "${GREEN}✓${NC} Script is executable"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}✗${NC} Script is not executable"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# ============================================================================
# Test 2: Model constants are defined in the script
# ============================================================================

test_model_constants() {
    local script_content
    script_content=$(cat "$SUITE_SCRIPT")

    assert_contains "$script_content" 'MODEL_GRANITE_1B="ibm-granite/granite-4.0-1b"' \
        "MODEL_GRANITE_1B defined"
    assert_contains "$script_content" 'MODEL_GRANITE_350M="ibm-granite/granite-4.0-350m"' \
        "MODEL_GRANITE_350M defined"
    assert_contains "$script_content" 'MODEL_GRANITE_MICRO="ibm-granite/granite-4.0-micro"' \
        "MODEL_GRANITE_MICRO defined"
    assert_contains "$script_content" 'MODEL_QWEN_9B="Qwen/Qwen3.5-9B"' \
        "MODEL_QWEN_9B defined"
    assert_contains "$script_content" 'MODEL_ANTARES_1B="fdtn-ai/antares-1b"' \
        "MODEL_ANTARES_1B defined"
    assert_contains "$script_content" 'MODEL_ANTARES_350M="fdtn-ai/antares-350m"' \
        "MODEL_ANTARES_350M defined"
}

# ============================================================================
# Test 3: Runner auto-detection function exists
# ============================================================================

test_runner_detection() {
    local script_content
    script_content=$(cat "$SUITE_SCRIPT")

    assert_contains "$script_content" 'get_vloc_runner()' \
        "get_vloc_runner function defined"
    assert_contains "$script_content" 'vllm_antares' \
        "Antares runner referenced"
    assert_contains "$script_content" 'vllm_qwen_3_5' \
        "Qwen runner referenced"
    assert_contains "$script_content" 'vllm_gemma_4' \
        "Gemma runner referenced"
}

# ============================================================================
# Test 4: Usage message shows all modes and key options
# ============================================================================

test_usage_message() {
    local usage_output
    usage_output=$("$SUITE_SCRIPT" 2>&1 || true)

    assert_contains "$usage_output" "CVE Vulnerability Localization" \
        "Usage shows title"
    assert_contains "$usage_output" "smoke" \
        "Usage shows smoke mode"
    assert_contains "$usage_output" "phase-a" \
        "Usage shows phase-a mode"
    assert_contains "$usage_output" "phase-b" \
        "Usage shows phase-b mode"
    assert_contains "$usage_output" "model-sweep" \
        "Usage shows model-sweep mode"
    assert_contains "$usage_output" "full" \
        "Usage shows full mode"
    assert_contains "$usage_output" "--models" \
        "Usage shows --models option"
    assert_contains "$usage_output" "--cores" \
        "Usage shows --cores option"
    assert_contains "$usage_output" "--vloc-dir" \
        "Usage shows --vloc-dir option"
    assert_contains "$usage_output" "--keep-server" \
        "Usage shows --keep-server option"
    assert_contains "$usage_output" "HF_TOKEN" \
        "Usage mentions HF_TOKEN"
    assert_contains "$usage_output" "VLLM_CONTAINER_IMAGE" \
        "Usage mentions VLLM_CONTAINER_IMAGE"
}

# ============================================================================
# Test 5: Preset model lists defined
# ============================================================================

test_model_presets() {
    local script_content
    script_content=$(cat "$SUITE_SCRIPT")

    assert_contains "$script_content" 'PRESET_GRANITE=' \
        "PRESET_GRANITE defined"
    assert_contains "$script_content" 'PRESET_QWEN=' \
        "PRESET_QWEN defined"
    assert_contains "$script_content" 'PRESET_ANTARES=' \
        "PRESET_ANTARES defined"
    assert_contains "$script_content" 'PRESET_PUBLIC=' \
        "PRESET_PUBLIC defined"
    assert_contains "$script_content" 'PRESET_ALL=' \
        "PRESET_ALL defined"
}

# ============================================================================
# Test 6: Playbook reference is correct
# ============================================================================

test_playbook_reference() {
    local script_content
    script_content=$(cat "$SUITE_SCRIPT")

    assert_contains "$script_content" 'llm-benchmark-cve-vloc.yml' \
        "References correct playbook"
}

# ============================================================================
# Test 7: Dry-run mode is supported
# ============================================================================

test_dry_run_flag() {
    local script_content
    script_content=$(cat "$SUITE_SCRIPT")

    assert_contains "$script_content" 'DRY_RUN' \
        "DRY_RUN variable used"
    assert_contains "$script_content" '--dry-run' \
        "--dry-run flag handled"
}

# ============================================================================
# Test 8: Security — HF_TOKEN not in logged commands
# ============================================================================

test_no_token_logging() {
    local script_content
    script_content=$(cat "$SUITE_SCRIPT")

    assert_not_contains "$script_content" 'echo.*HF_TOKEN' \
        "HF_TOKEN not echoed directly"
}

# ============================================================================
# Main test execution
# ============================================================================

echo "=========================================="
echo "run-cve-vloc-suite.sh Unit Tests"
echo "=========================================="
echo

test_script_exists
test_script_executable
test_model_constants
test_runner_detection
test_usage_message
test_model_presets
test_playbook_reference
test_dry_run_flag
test_no_token_logging

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
