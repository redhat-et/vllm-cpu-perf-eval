#!/bin/bash
# Unit tests for run-lm-eval-suite.sh
#
# Tests:
#   - --help exits 0
#   - --dry-run from repo root does not error on REPO_ROOT check
#   - Unknown flag exits non-zero
#   - Model preset resolution (--models quick)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_SCRIPT="${SCRIPT_DIR}/../../scripts/bash/run-lm-eval-suite.sh"

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
    echo "  $2"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_RUN=$((TESTS_RUN + 1))
}

# Test 1: Script exists
if [[ -f "${SUITE_SCRIPT}" ]]; then
    pass "Script exists at expected path"
else
    fail "Script exists at expected path" "Not found: ${SUITE_SCRIPT}"
fi

# Test 2: Script is executable
if [[ -x "${SUITE_SCRIPT}" ]]; then
    pass "Script is executable"
else
    fail "Script is executable" "Script is not executable"
fi

# Test 3: --help exits 0
if "${SUITE_SCRIPT}" --help > /dev/null 2>&1; then
    pass "--help exits 0"
else
    fail "--help exits 0" "Exit code was non-zero"
fi

# Test 4: --help output contains expected content
HELP_OUT=$("${SUITE_SCRIPT}" --help 2>&1 || true)
if echo "${HELP_OUT}" | grep -q "LM Evaluation"; then
    pass "--help output contains 'LM Evaluation'"
else
    fail "--help output contains 'LM Evaluation'" "Output: ${HELP_OUT}"
fi

# Test 5: Unknown flag exits non-zero
if "${SUITE_SCRIPT}" --unknown-flag-xyz 2>/dev/null; then
    fail "Unknown flag exits non-zero" "Expected non-zero exit, got 0"
else
    pass "Unknown flag exits non-zero"
fi

# Test 6: --dry-run from repo root does not fail on REPO_ROOT discovery
# We cd to the repo root before running (REPO_ROOT discovery walks up to .git)
REPO_ROOT="${SCRIPT_DIR}"
while [[ ! -d "${REPO_ROOT}/.git" ]] && [[ "${REPO_ROOT}" != "/" ]]; do
    REPO_ROOT="$(dirname "${REPO_ROOT}")"
done

if [[ -d "${REPO_ROOT}/.git" ]]; then
    DRY_OUT=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 8 2>&1 || true)
    if echo "${DRY_OUT}" | grep -q "ERROR: Could not find repository root"; then
        fail "--dry-run REPO_ROOT discovery succeeds" "Got REPO_ROOT error: ${DRY_OUT}"
    else
        pass "--dry-run REPO_ROOT discovery succeeds"
    fi
else
    echo "  SKIP: cannot locate .git root from ${SCRIPT_DIR}"
    TESTS_RUN=$((TESTS_RUN + 1))
fi

# Test 7: --models quick resolves to a single model in dry-run output
DRY_QUICK=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 8 2>&1 || true)
if echo "${DRY_QUICK}" | grep -q "Qwen3-0.6B\|Qwen/Qwen3"; then
    pass "--models quick resolves to Qwen3-0.6B"
else
    fail "--models quick resolves to Qwen3-0.6B" "Output: ${DRY_QUICK}"
fi

# Test 8: --models quick --cores 8 dry-run shows exactly 1 test combination
MODEL_COUNT=$(echo "${DRY_QUICK}" | grep -c "DRY RUN: Would execute" || true)
if [[ "${MODEL_COUNT}" -eq 1 ]]; then
    pass "--models quick --cores 8 produces 1 test combination"
else
    fail "--models quick --cores 8 produces 1 test combination" "Got ${MODEL_COUNT} combinations"
fi

# Test 9: --tag is passed through in dry-run output
DRY_TAG=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 8 --tag smoke-test 2>&1 || true)
if echo "${DRY_TAG}" | grep -q "test_name=smoke-test"; then
    pass "--tag smoke-test appears in dry-run ansible command"
else
    fail "--tag smoke-test appears in dry-run ansible command" "Output: ${DRY_TAG}"
fi

echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo "Tests run:    ${TESTS_RUN}"
echo -e "Tests passed: ${GREEN}${TESTS_PASSED}${NC}"

if [[ ${TESTS_FAILED} -gt 0 ]]; then
    echo -e "Tests failed: ${RED}${TESTS_FAILED}${NC}"
    exit 1
else
    echo -e "Tests failed: ${TESTS_FAILED}"
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
fi
