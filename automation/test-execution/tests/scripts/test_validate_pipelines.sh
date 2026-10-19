#!/bin/bash
# Unit tests for validate-pipelines-common.sh (the validation harness library)
#
# Covers the bug classes found during the first validation run:
#   - EMBEDDING_EXTRA_VARS must be valid JSON in default AND override paths
#     (bash ${VAR:-...} eats the first '}' inside the default — regression)
#   - typed extra vars must be passed as one JSON document (k=v stays string)
#   - ansible_cmd must run from the ansible dir (ansible.cfg/roles_path)
#   - stage functions must pass the full -e contract (requested_cores,
#     profile/rate caps, envoy/EPP pins, shape/probe JSON)
#   - stage_enabled / run_stage / summary bookkeeping
#
# ansible-playbook is faked via a PATH shim that records $PWD and "$@"
# (one line per argument, calls separated by '---CALL---').

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${SCRIPT_DIR}/../../scripts/bash/validate-pipelines-common.sh"

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

assert_contains() {  # assert_contains <haystack-file> <needle> <label>
    if grep -qF -- "$2" "$1"; then
        pass "$3"
    else
        fail "$3" "expected '$2' in $1: $(cat "$1" | tr '\n' ' ')"
    fi
}

# --- Isolated environment ---------------------------------------------------
TEST_TMP="$(mktemp -d)"
export CAPTURE_FILE="$TEST_TMP/ansible-calls.txt"
export VALIDATION_LOG_DIR="$TEST_TMP/logs"
cleanup() { rm -rf "$TEST_TMP"; }
trap cleanup EXIT

# Fake ansible-playbook: records cwd + args (append, with call separator)
mkdir -p "$TEST_TMP/bin"
cat > "$TEST_TMP/bin/ansible-playback-shim" <<'SHIM_EOF'
#!/usr/bin/env bash
SHIM_EOF
cat > "$TEST_TMP/bin/ansible-playbook" <<'SHIM_EOF'
#!/usr/bin/env bash
{
    printf -- '---CALL---\n'
    printf 'PWD=%s\n' "$PWD"
    printf 'ARGS=%s\n' "$*"
} >> "$CAPTURE_FILE"
exit 0
SHIM_EOF
chmod +x "$TEST_TMP/bin/ansible-playbook"
export PATH="$TEST_TMP/bin:$PATH"

# Source the harness library (into the main shell; functions are the test unit)
# shellcheck source=validate-pipelines-common.sh
# shellcheck disable=SC1090
source "$COMMON"

# ============================================================================
# Test 1: default EMBEDDING_EXTRA_VARS is valid JSON with the expected shape
# ============================================================================
if printf '%s' "$EMBEDDING_EXTRA_VARS" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["op_probe_levels"] == [8], d
assert d["embedding_workload_shapes"] == [{"name": "chunk", "input_len": 512}], d
' 2>/dev/null; then
    pass "EMBEDDING_EXTRA_VARS default is valid, typed JSON"
else
    fail "EMBEDDING_EXTRA_VARS default is valid, typed JSON" "got: $EMBEDDING_EXTRA_VARS"
fi

# Test 2: brace-eating regression — the shape default must keep its closing '}'
if [[ "$EMBEDDING_SMOKE_SHAPE" == *'}]' && "$EMBEDDING_SMOKE_SHAPE" == '[{'* ]]; then
    pass "EMBEDDING_SMOKE_SHAPE braces intact (bash \${VAR:-} regression)"
else
    fail "EMBEDDING_SMOKE_SHAPE braces intact" "got: $EMBEDDING_SMOKE_SHAPE"
fi

# Test 3: override path flows through and stays valid JSON
OVERRIDE_JSON="$(
    EMBEDDING_PROBE_LEVELS='[1,8]' bash -c '
        source "${1:?}" >/dev/null 2>&1
        printf "%s" "$EMBEDDING_EXTRA_VARS"' _ "$COMMON"
)"
if printf '%s' "$OVERRIDE_JSON" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["op_probe_levels"] == [1, 8], d
' 2>/dev/null; then
    pass "EMBEDDING_PROBE_LEVELS override produces valid JSON"
else
    fail "EMBEDDING_PROBE_LEVELS override produces valid JSON" "got: $OVERRIDE_JSON"
fi

# ============================================================================
# Test 4: stage_enabled selection logic
# ============================================================================
STAGES=all
if stage_enabled 6; then
    fail "stage_enabled: STAGES=all excludes LMCache stage 6 by default" "stage 6 enabled"
else
    pass "stage_enabled: STAGES=all excludes LMCache stage 6 by default"
fi
INCLUDE_LMCACHE=1 STAGES=all stage_enabled 6 && pass "stage_enabled: INCLUDE_LMCACHE enables stage 6" \
    || fail "stage_enabled: INCLUDE_LMCACHE enables stage 6" "stage 6 not enabled"
STAGES=all
# shellcheck disable=SC2034  # read by stage_enabled() in the sourced library
STAGES=4,6
stage_enabled 6 && pass "stage_enabled: subset membership" \
    || fail "stage_enabled: subset membership" "6 not in 4,6"
if stage_enabled 5; then
    fail "stage_enabled: non-member excluded" "5 matched STAGES=4,6"
else
    pass "stage_enabled: non-member excluded"
fi

# ============================================================================
# Test 5: HF_ARGS built from HF_TOKEN
# ============================================================================
HF_WITH_TOKEN="$(HF_TOKEN=hf_test123 bash -c '
    source "${1:?}" >/dev/null 2>&1
    printf "%s" "${HF_ARGS[*]}"' _ "$COMMON")"
[[ "$HF_WITH_TOKEN" == "-e hf_token=hf_test123" ]] \
    && pass "HF_ARGS includes token when HF_TOKEN set" \
    || fail "HF_ARGS includes token when HF_TOKEN set" "got: $HF_WITH_TOKEN"
HF_NO_TOKEN="$(env -u HF_TOKEN bash -c '
    source "${1:?}" >/dev/null 2>&1
    printf "%s" "${HF_ARGS[*]}"' _ "$COMMON")"
[[ -z "$HF_NO_TOKEN" ]] \
    && pass "HF_ARGS empty when HF_TOKEN unset" \
    || fail "HF_ARGS empty when HF_TOKEN unset" "got: $HF_NO_TOKEN"

# ============================================================================
# Test 6: run_stage bookkeeping (PASS + FAIL + log file)
# ============================================================================
: > "$CAPTURE_FILE"
run_stage 97 "always passes" true
# tee runs async via process substitution — wait briefly for the log file
for _ in $(seq 1 20); do
    [[ -f "$LOG_DIR/stage97-always_passes.log" ]] && break
    sleep 0.1
done
[[ "${STAGE_RCS[0]}" == "0" && -f "$LOG_DIR/stage97-always_passes.log" ]] \
    && pass "run_stage records PASS with log file" \
    || fail "run_stage records PASS with log file" "rc=${STAGE_RCS[0]}"
run_stage 96 "always fails" false || true
[[ "${STAGE_RCS[1]}" != "0" ]] \
    && pass "run_stage records FAIL rc" \
    || fail "run_stage records FAIL rc" "rc=${STAGE_RCS[1]}"

# Test 7: summary fails when no stage was selected
if (STAGE_NAMES=(); STAGE_RCS=(); STAGE_SECS=(); validation_print_summary) >/dev/null 2>&1; then
    fail "summary returns 1 on empty stage selection" "exited 0"
else
    pass "summary returns 1 on empty stage selection"
fi

# ============================================================================
# Test 8: ansible_cmd runs from the ansible dir (ansible.cfg must load)
# ============================================================================
: > "$CAPTURE_FILE"
ansible_cmd stop-vllm-scaleout.yml
if [[ "$(grep '^PWD=' "$CAPTURE_FILE" | cut -d= -f2-)" == "$ANSIBLE_DIR" ]]; then
    pass "ansible_cmd runs from the ansible dir"
else
    fail "ansible_cmd runs from the ansible dir" "$(grep '^PWD=' "$CAPTURE_FILE")"
fi

# ============================================================================
# Test 9: single_llm -e contract
# ============================================================================
: > "$CAPTURE_FILE"
single_llm chat
assert_contains "$CAPTURE_FILE" "-e test_model=${LLM_MODEL}" "single_llm passes test_model"
assert_contains "$CAPTURE_FILE" "-e workload_type=chat" "single_llm passes workload_type"
assert_contains "$CAPTURE_FILE" "-e requested_cores=${REQUESTED_CORES}" "single_llm passes requested_cores"
assert_contains "$CAPTURE_FILE" "-e guidellm_profile=${GUIDELLM_PROFILE}" "single_llm passes guidellm_profile"
assert_contains "$CAPTURE_FILE" "-e guidellm_rate=${GUIDELLM_RATE}" "single_llm passes guidellm_rate"
assert_contains "$CAPTURE_FILE" "-e guidellm_max_seconds=${QUICK_SECONDS}" "single_llm passes run-time cap"
assert_contains "$CAPTURE_FILE" "-e guidellm_max_requests=${QUICK_REQUESTS}" "single_llm passes request cap"

# Test 10: single_embedding passes the typed JSON doc as ONE argument
: > "$CAPTURE_FILE"
single_embedding
if grep -qF -- "$EMBEDDING_EXTRA_VARS" "$CAPTURE_FILE"; then
    pass "single_embedding passes typed JSON extra-vars document"
else
    fail "single_embedding passes typed JSON extra-vars document" \
        "JSON doc not found as a single -e argument"
fi
assert_contains "$CAPTURE_FILE" "-e scenario=operating_point" "single_embedding passes scenario"

# Test 11: multi_llm topology + pinning contract
: > "$CAPTURE_FILE"
PRE_CLEAN=false multi_llm chat
assert_contains "$CAPTURE_FILE" "-e scaleout_num_instances=${SCALEOUT_NUM_INSTANCES}" "multi_llm passes instance count"
assert_contains "$CAPTURE_FILE" "-e scaleout_cores_per_instance=${SCALEOUT_CORES_PER_INSTANCE}" "multi_llm passes cores per instance"
assert_contains "$CAPTURE_FILE" "-e scaleout_start_core=${SCALEOUT_START_CORE}" "multi_llm passes start core"
assert_contains "$CAPTURE_FILE" "-e scaleout_envoy_cores=${SCALEOUT_ENVOY_CORES}" "multi_llm pins envoy cores"
assert_contains "$CAPTURE_FILE" "-e scaleout_epp_cores=${SCALEOUT_EPP_CORES}" "multi_llm pins epp cores"
assert_contains "$CAPTURE_FILE" "-e scaleout_envoy_concurrency=${SCALEOUT_ENVOY_CONCURRENCY}" "multi_llm passes envoy concurrency"

# Test 12: multi_embedding_scaleout passes scaleout topology + typed JSON doc
: > "$CAPTURE_FILE"
PRE_CLEAN=false multi_embedding_scaleout
assert_contains "$CAPTURE_FILE" "-e scaleout_num_instances=${EMBEDDING_SCALEOUT_NUM_INSTANCES}" "multi_embedding passes instance count"
if grep -qF -- "$EMBEDDING_EXTRA_VARS" "$CAPTURE_FILE"; then
    pass "multi_embedding passes typed JSON extra-vars document"
else
    fail "multi_embedding passes typed JSON extra-vars document" "JSON doc not found"
fi

# Test 12b: audio scaleout smoke contract
: > "$CAPTURE_FILE"
PRE_CLEAN=false audio_scaleout
assert_contains "$CAPTURE_FILE" "audio-benchmark-scaleout.yml" "audio stage invokes the audio scale-out playbook"
assert_contains "$CAPTURE_FILE" "-e test_model=${AUDIO_MODEL}" "audio stage passes the smoke model"
assert_contains "$CAPTURE_FILE" "-e test_scenario=transcription-throughput" "audio stage passes the smoke scenario"
assert_contains "$CAPTURE_FILE" "-e audio_num_files=2" "audio stage caps the file count"
assert_contains "$CAPTURE_FILE" "-e scaleout_start_core=${EMBEDDING_SCALEOUT_START_CORE}" "audio stage uses the light topology"
if grep -q "scaleout_lmcache" "$CAPTURE_FILE"; then
    fail "audio stage must not enable LMCache" "LMCache vars present"
else
    pass "audio stage must not enable LMCache"
fi

# Test 13: PRE_CLEAN invokes the teardown playbook first
: > "$CAPTURE_FILE"
PRE_CLEAN=true multi_llm chat
CALLS="$(grep -c -- '---CALL---' "$CAPTURE_FILE")"
FIRST_CALL_ARGS="$(awk '/---CALL---/{found=1; next} found && /^ARGS=/{print; exit}' "$CAPTURE_FILE")"
if [[ "$CALLS" -eq 2 ]] && [[ "$FIRST_CALL_ARGS" == *"stop-vllm-scaleout.yml"* ]]; then
    pass "PRE_CLEAN runs stop-vllm-scaleout before the benchmark"
else
    fail "PRE_CLEAN runs stop-vllm-scaleout before the benchmark" "$CALLS calls captured; first args: $FIRST_CALL_ARGS"
fi

# Test 14: multi_llm_lmcache forwards the LMCache backend settings
: > "$CAPTURE_FILE"
PRE_CLEAN=false multi_llm_lmcache >/dev/null 2>&1
assert_contains "$CAPTURE_FILE" "-e scaleout_lmcache_backend=remote" "lmcache stage enables remote backend"
assert_contains "$CAPTURE_FILE" "-e scaleout_lmcache_server_l1_size_gb=${LMCACHE_L1_GB}" "lmcache stage passes L1 pool size"
assert_contains "$CAPTURE_FILE" "-e scaleout_vllm_gpu_memory_utilization=${LMCACHE_UTIL}" "lmcache stage passes memory utilization"

# ============================================================================
echo ""
echo "============================================================"
echo "Results: $TESTS_PASSED passed, $TESTS_FAILED failed ($TESTS_RUN total)"
echo "============================================================"
if [[ "$TESTS_FAILED" -gt 0 ]]; then
    exit 1
fi
exit 0
