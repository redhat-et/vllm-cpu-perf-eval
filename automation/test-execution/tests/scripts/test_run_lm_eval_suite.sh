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

# Test 9: --tag is combined with auto-generated model/core name (not replaces it)
# quick preset = Qwen/Qwen3-0.6B → Qwen3-0-6B-8C → smoke-test-Qwen3-0-6B-8C
DRY_TAG=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 8 --tag smoke-test 2>&1 || true)
if echo "${DRY_TAG}" | grep -q "test_name=smoke-test-Qwen3-0-6B-8C"; then
    pass "--tag smoke-test combined with model name in dry-run (smoke-test-Qwen3-0-6B-8C)"
else
    fail "--tag smoke-test combined with model name in dry-run" "Expected test_name=smoke-test-Qwen3-0-6B-8C, got: $(echo "${DRY_TAG}" | grep test_name || echo 'not found')"
fi

# Test 10: dotted model name is sanitized (dots → hyphens, no dots in test_name value)
DRY_DOT=$("${SUITE_SCRIPT}" --dry-run --models "meta-llama/Llama-3.2-1B-Instruct" --cores 16 2>&1 || true)
TEST_NAME_VAL=$(echo "${DRY_DOT}" | grep -o 'test_name=[^ ]*' | head -1 | sed 's/test_name=//')
if [[ -n "${TEST_NAME_VAL}" ]] && echo "${TEST_NAME_VAL}" | grep -qv '\.'; then
    pass "Dotted model name produces sanitized test_name (no dots): ${TEST_NAME_VAL}"
else
    fail "Dotted model name produces sanitized test_name (no dots)" "test_name value: '${TEST_NAME_VAL}'"
fi

# Test 11: combined tag+name exceeding 100 chars exits with error
# 90-char tag + "-Qwen3-0-6B-8C" (14 chars) = 105 chars → error
LONG_TAG=$(printf 'a%.0s' {1..90})
LONG_TAG_OUT=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 8 --tag "${LONG_TAG}" 2>&1 || true)
if echo "${LONG_TAG_OUT}" | grep -q "exceeds 100 chars"; then
    pass "Combined tag+name > 100 chars exits with clear error"
else
    fail "Combined tag+name > 100 chars exits with clear error" "Output: ${LONG_TAG_OUT}"
fi

# Test 12: --vllm-cpus and --guidellm-cpus are passed through to ansible-playbook
DRY_CPUS=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 32 --vllm-cpus 0-31 --guidellm-cpus 32-47 2>&1 || true)
if echo "${DRY_CPUS}" | grep -q "vllm_cpus=0-31" && echo "${DRY_CPUS}" | grep -q "guidellm_cpus=32-47"; then
    pass "--vllm-cpus and --guidellm-cpus passed through in dry-run"
else
    fail "--vllm-cpus and --guidellm-cpus passed through in dry-run" "Output: ${DRY_CPUS}"
fi

# Test 13: --tasks truthful resolves to TruthfulQA tasks in dry-run
DRY_TRUTHFUL=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 8 --tasks truthful 2>&1 || true)
if echo "${DRY_TRUTHFUL}" | grep -q "lm_eval_tasks=truthfulqa_mc1,truthfulqa_mc2"; then
    pass "--tasks truthful resolves to truthfulqa_mc1,truthfulqa_mc2"
else
    fail "--tasks truthful resolves to truthfulqa_mc1,truthfulqa_mc2" "Output: ${DRY_TRUTHFUL}"
fi

# Test 14: mixing gsm8k with MC tasks fails before ansible
MIXED_OUT=$("${SUITE_SCRIPT}" --dry-run --models quick --cores 8 --tasks gsm8k,truthfulqa_mc1 2>&1 || true)
if echo "${MIXED_OUT}" | grep -qi "Cannot mix generation tasks"; then
    pass "gsm8k + truthfulqa rejected with clear error"
else
    fail "gsm8k + truthfulqa rejected with clear error" "Output: ${MIXED_OUT}"
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
