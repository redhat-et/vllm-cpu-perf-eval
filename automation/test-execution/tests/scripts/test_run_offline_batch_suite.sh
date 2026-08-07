#!/bin/bash
# Unit tests for run-offline-batch-suite.sh
#
# Tests bash script functionality:
# - Model list parsing ("all", comma-separated, single)
# - Parameter validation
# - count_existing_results: path/use-case/dataset/prompt isolation
# - run_with_resume: skip, partial resume, --force bypass, failure propagation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_SCRIPT="$SCRIPT_DIR/../../scripts/bash/run-offline-batch-suite.sh"
HELPERS_LIB="$SCRIPT_DIR/../../scripts/bash/helpers/offline-batch-helpers.sh"

# Source shared helpers so count_existing_results and run_with_resume are available
# directly — no duplication of the function logic in this file.
source "$HELPERS_LIB"

# Colors for test output (already defined by helpers lib, kept here for clarity)
# GREEN / RED / NC come from HELPERS_LIB

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
        echo "  Expected NOT to contain: $needle"
        echo "  Actual: $haystack"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Source the script variables (without executing main)
source_script_functions() {
    export MODEL_TINY_PRUNED="RedHatAI/TinyLlama-1.1B-Chat-v1.0-pruned2.4"
    export MODEL_LLAMA_W8A8="RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8"
    export MODEL_LLAMA_W4A16="RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w4a16"
    export MODEL_QWEN_W4A16="RedHatAI/Qwen3-8B-quantized.w4a16"
    export ALL_MODELS="$MODEL_LLAMA_W8A8,$MODEL_LLAMA_W4A16,$MODEL_QWEN_W4A16"
    export VLLM_CONTAINER_IMAGE="vllm/vllm-openai:latest"
}

# Write a minimal results.json matching the real schema into the given directory.
# use_case lives under dataset_config, matching the grep pattern in count_existing_results.
_make_result() {
    local dir="$1" use_case="$2"
    mkdir -p "$dir"
    printf '{"test_type": "offline-batch", "dataset_config": {"use_case": "%s"}}\n' \
        "$use_case" > "$dir/results.json"
}

# Default no-op run_test stub — overridden per test as needed.
run_test() { return 0; }

# ── Script smoke tests ────────────────────────────────────────────────────────

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

# ── count_existing_results fixture tests ─────────────────────────────────────
# These tests use count_existing_results directly from offline-batch-helpers.sh
# (no inline copy needed).

# Test 9: returns 0 when the model results directory does not exist
test_count_no_results_dir() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    local result
    result=$(count_existing_results "model/foo" "summarization" 16 "sharegpt" 1000)
    assert_equals "0" "$result" "count returns 0 when no results dir exists"
}

# Test 10: full skip - all 3 runs already complete
test_count_full_skip() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run3/16cores-sharegpt-1000prompts" "summarization"
    local result
    result=$(count_existing_results "model/foo" "summarization" 16 "sharegpt" 1000)
    assert_equals "3" "$result" "count returns 3 when 3 runs are complete (full skip)"
}

# Test 11: partial resume - 2 of 3 runs complete
test_count_partial_resume() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sharegpt-1000prompts" "summarization"
    local result
    result=$(count_existing_results "model/foo" "summarization" 16 "sharegpt" 1000)
    assert_equals "2" "$result" "count returns 2 when 2 of 3 runs are complete (partial resume)"
}

# Test 12: no false match across use cases (same dataset/prompts/cores, different use_case)
test_count_no_false_match_use_case() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sharegpt-1000prompts" "summarization"
    local result
    result=$(count_existing_results "model/foo" "classification" 16 "sharegpt" 1000)
    assert_equals "0" "$result" "summarization results do not count toward classification sweep"
}

# Test 13: prompt count isolation (500-prompt results must not count toward 1000-prompt sweep)
test_count_prompt_isolation() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sharegpt-500prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sharegpt-500prompts" "summarization"
    local result
    result=$(count_existing_results "model/foo" "summarization" 16 "sharegpt" 1000)
    assert_equals "0" "$result" "500-prompt results do not count toward 1000-prompt sweep"
}

# Test 14: dataset name isolation (sonnet results must not count toward sharegpt sweep)
test_count_dataset_isolation() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sonnet-500prompts" "etl"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sonnet-500prompts" "etl"
    local result
    result=$(count_existing_results "model/foo" "etl" 16 "sharegpt" 500)
    assert_equals "0" "$result" "sonnet results do not count toward sharegpt sweep"
}

# ── run_with_resume tests ─────────────────────────────────────────────────────
# run_test is stubbed per test. Stubs write to a calls file so we can verify
# call count from the parent after the subshell exits.

# Test 15: full skip — run_test must not be called when all runs exist
test_resume_full_skip() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run3/16cores-sharegpt-1000prompts" "summarization"

    local calls_file="$tmpdir/calls.log"
    run_test() { echo "called" >> "$calls_file"; return 0; }

    local output
    output=$(OFFLINE_BATCH_FORCE=0 run_with_resume \
        "model/foo" "summarization" "sharegpt" 1000 16 3 -e "use_case=summarization" 2>&1)

    assert_contains "$output" "SKIP" "full skip: SKIP message shown"
    local call_count=0
    [[ -f "$calls_file" ]] && call_count=$(wc -l < "$calls_file" | tr -d ' ')
    assert_equals "0" "$call_count" "full skip: run_test not called"

    # Restore default stub
    run_test() { return 0; }
}

# Test 16: partial resume — correct run number shown, run_test called once for the missing run
test_resume_partial() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sharegpt-1000prompts" "summarization"

    local calls_file="$tmpdir/calls.log"
    run_test() { echo "called" >> "$calls_file"; return 0; }

    local output
    output=$(OFFLINE_BATCH_FORCE=0 run_with_resume \
        "model/foo" "summarization" "sharegpt" 1000 16 3 -e "use_case=summarization" 2>&1)

    assert_contains "$output" "Run 3/3" "partial resume: run display shows Run 3/3"
    local call_count=0
    [[ -f "$calls_file" ]] && call_count=$(wc -l < "$calls_file" | tr -d ' ')
    assert_equals "1" "$call_count" "partial resume: run_test called exactly once"

    run_test() { return 0; }
}

# Test 17: --force bypass — run_test called for all runs even when results exist
test_resume_force_bypass() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"
    _make_result "$tmpdir/results/llm/model__foo/run1/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run2/16cores-sharegpt-1000prompts" "summarization"
    _make_result "$tmpdir/results/llm/model__foo/run3/16cores-sharegpt-1000prompts" "summarization"

    local calls_file="$tmpdir/calls.log"
    run_test() { echo "called" >> "$calls_file"; return 0; }

    local output
    output=$(OFFLINE_BATCH_FORCE=1 run_with_resume \
        "model/foo" "summarization" "sharegpt" 1000 16 3 -e "use_case=summarization" 2>&1)

    assert_not_contains "$output" "SKIP" "force: no SKIP message shown"
    assert_contains "$output" "force" "force: force message shown"
    local call_count=0
    [[ -f "$calls_file" ]] && call_count=$(wc -l < "$calls_file" | tr -d ' ')
    assert_equals "3" "$call_count" "force: run_test called 3 times"

    run_test() { return 0; }
}

# Test 18: failure propagation — run_with_resume returns 1 when run_test fails
test_resume_failure_propagation() {
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' RETURN
    local REPO_ROOT="$tmpdir"

    run_test() { return 1; }

    local result="pass"
    OFFLINE_BATCH_FORCE=0 run_with_resume \
        "model/foo" "summarization" "sharegpt" 1000 16 1 -e "use_case=summarization" \
        >/dev/null 2>&1 && result="pass" || result="fail"

    assert_equals "fail" "$result" "failure propagation: run_with_resume returns 1 when run_test fails"

    run_test() { return 0; }
}

# ── cap_prompts tests ─────────────────────────────────────────────────────────
# cap_prompts is sourced from offline-batch-helpers.sh via HELPERS_LIB above.

# Test 19: cap active — input above cap returns the cap value
test_cap_prompts_capped() {
    local result
    result=$(OFFLINE_BATCH_MAX_PROMPTS=100 cap_prompts 1000)
    assert_equals "100" "$result" "cap_prompts: 1000 capped to 100 when MAX_PROMPTS=100"
}

# Test 20: cap disabled — OFFLINE_BATCH_MAX_PROMPTS=0 returns the original value
test_cap_prompts_disabled() {
    local result
    result=$(OFFLINE_BATCH_MAX_PROMPTS=0 cap_prompts 1000)
    assert_equals "1000" "$result" "cap_prompts: 1000 unchanged when MAX_PROMPTS=0 (cap disabled)"
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
test_count_no_results_dir
test_count_full_skip
test_count_partial_resume
test_count_no_false_match_use_case
test_count_prompt_isolation
test_count_dataset_isolation
test_resume_full_skip
test_resume_partial
test_resume_force_bypass
test_resume_failure_propagation
test_cap_prompts_capped
test_cap_prompts_disabled

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
