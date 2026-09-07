#!/bin/bash
# Unit tests for run-concurrent-load-suite.sh
#
# Tests:
#   - --help exits 0
#   - Untagged dry-run omits test_name
#   - --tag combined with auto-generated name
#   - --vllm-cpu-start deprecation warning

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_SCRIPT="${SCRIPT_DIR}/../../scripts/bash/run-concurrent-load-suite.sh"

# Use the qwen preset (Qwen/Qwen3-0.6B) for deterministic dry-run output.
DRY_RUN_ARGS=(--dry-run --models qwen --cores 8 --phase 1)

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    echo -e "${GREEN}✓${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    if [[ -n "${2:-}" ]]; then
        echo "  ${2}"
    fi
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
}

echo "Running run-concurrent-load-suite.sh tests..."
echo

# Test 1: --help exits 0
if "${SUITE_SCRIPT}" --help >/dev/null 2>&1; then
    pass "--help exits 0"
else
    fail "--help exits 0"
fi

# Test 2: untagged dry-run does not pass test_name
DRY_UNTAGGED=$("${SUITE_SCRIPT}" "${DRY_RUN_ARGS[@]}" 2>&1 || true)
UNTAGGED_COMBO_COUNT=$(echo "${DRY_UNTAGGED}" | grep -c "DRY-RUN:" || true)
if [[ "${UNTAGGED_COMBO_COUNT}" -ne 1 ]]; then
    fail "Untagged dry-run produces 1 test combination" "Got ${UNTAGGED_COMBO_COUNT} combinations"
elif echo "${DRY_UNTAGGED}" | grep -q "test_name="; then
    fail "Untagged dry-run omits test_name" "Found test_name in output"
else
    pass "Untagged dry-run omits test_name"
fi

# Test 3: --tag is combined with auto-generated model/workload/core name
DRY_TAG=$("${SUITE_SCRIPT}" "${DRY_RUN_ARGS[@]}" --tag smoke-test 2>&1 || true)
TAGGED_COMBO_COUNT=$(echo "${DRY_TAG}" | grep -c "DRY-RUN:" || true)
TEST_NAME_VAL=$(echo "${DRY_TAG}" | grep -o 'test_name=[^ ]*' | head -1 | sed 's/test_name=//')
if [[ "${TAGGED_COMBO_COUNT}" -ne 1 ]]; then
    fail "--tag smoke-test combined with model/workload/core name" "Got ${TAGGED_COMBO_COUNT} combinations"
elif [[ "${TEST_NAME_VAL}" == "smoke-test-Qwen3-0-6B-chat-8C" ]]; then
    pass "--tag smoke-test combined with model/workload/core name"
else
    fail "--tag smoke-test combined with model/workload/core name" "Expected test_name=smoke-test-Qwen3-0-6B-chat-8C, got: '${TEST_NAME_VAL:-not found}'"
fi

# Test 4: --vllm-cpu-start prints deprecation warning when --vllm-cpus is not set
DEPRECATION_OUT=$("${SUITE_SCRIPT}" "${DRY_RUN_ARGS[@]}" --vllm-cpu-start 64 2>&1 || true)
if echo "${DEPRECATION_OUT}" | grep -q "deprecated"; then
    pass "--vllm-cpu-start prints deprecation warning"
else
    fail "--vllm-cpu-start prints deprecation warning" "Output: ${DEPRECATION_OUT}"
fi

echo
echo "========================================="
echo "Results: ${TESTS_PASSED}/${TESTS_RUN} passed"
if [[ "${TESTS_FAILED}" -gt 0 ]]; then
    echo -e "${RED}${TESTS_FAILED} test(s) failed${NC}"
    exit 1
fi
echo -e "${GREEN}All tests passed${NC}"
