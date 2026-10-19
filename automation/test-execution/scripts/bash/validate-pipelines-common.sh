# shellcheck shell=bash
# Shared config and stage functions for validate-pipelines.sh (source only).

# --- Locate the repo --------------------------------------------------------
_SCRIPT_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$_SCRIPT_COMMON_DIR/../../../.." && pwd)"
ANSIBLE_DIR="$REPO_ROOT/automation/test-execution/ansible"
INVENTORY="$ANSIBLE_DIR/inventory/hosts.yml"
VIEW_RESULTS="$REPO_ROOT/automation/test-execution/scripts/conversion/view_results.py"

# --- Configuration (env-overridable) ----------------------------------------
LLM_MODEL="${LLM_MODEL:-RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-RedHatAI/granite-embedding-english-r2}"
QUICK_SECONDS="${QUICK_SECONDS:-180}"      # per-benchmark wall-clock cap (LLM stages)
QUICK_REQUESTS="${QUICK_REQUESTS:-64}"     # per-benchmark request cap (LLM stages)

# Single-instance vLLM / embedding managed mode (embedding-benchmark.yml reads
# REQUESTED_CORES from the environment and -e requested_cores).
REQUESTED_CORES="${REQUESTED_CORES:-24}"
export REQUESTED_CORES

SCALEOUT_NUM_INSTANCES="${SCALEOUT_NUM_INSTANCES:-2}"
SCALEOUT_CORES_PER_INSTANCE="${SCALEOUT_CORES_PER_INSTANCE:-24}"
SCALEOUT_START_CORE="${SCALEOUT_START_CORE:-0}"
GUIDELLM_CPUS="${GUIDELLM_CPUS:-48-71}"
GUIDELLM_NUMA_NODE="${GUIDELLM_NUMA_NODE:-0}"
SCALEOUT_ROUTING_POLICY="${SCALEOUT_ROUTING_POLICY:-intelligent}"

# Envoy/EPP pins.  Role defaults (1-7 / 8-15) overlap instance 1 when
# scaleout_start_core=0 — pin them to SMT siblings instead so vLLM keeps its
# physical cores.  SCALEOUT_ENVOY_CONCURRENCY must match the core count in
# SCALEOUT_ENVOY_CORES.
SCALEOUT_ENVOY_CORES="${SCALEOUT_ENVOY_CORES:-72-75}"
SCALEOUT_EPP_CORES="${SCALEOUT_EPP_CORES:-76-83}"
SCALEOUT_ENVOY_CONCURRENCY="${SCALEOUT_ENVOY_CONCURRENCY:-4}"

# Lighter topology for stage 9 (embedding scale-out smoke).  Defaults match
# docs/vllm-scaleout.md § Embedding functional smoke (2 × 4 cores from 16).
EMBEDDING_SCALEOUT_NUM_INSTANCES="${EMBEDDING_SCALEOUT_NUM_INSTANCES:-2}"
EMBEDDING_SCALEOUT_CORES_PER_INSTANCE="${EMBEDDING_SCALEOUT_CORES_PER_INSTANCE:-4}"
EMBEDDING_SCALEOUT_START_CORE="${EMBEDDING_SCALEOUT_START_CORE:-16}"
VLLM_BENCH_CPUS="${VLLM_BENCH_CPUS:-$GUIDELLM_CPUS}"
VLLM_BENCH_NUMA_NODE="${VLLM_BENCH_NUMA_NODE:-$GUIDELLM_NUMA_NODE}"

LMCACHE_L1_GB="${LMCACHE_L1_GB:-10}"
LMCACHE_HUGEPAGES="${LMCACHE_HUGEPAGES:-true}"
LMCACHE_UTIL="${LMCACHE_UTIL:-0.4}"
LMCACHE_TRANSFER_MODE="${LMCACHE_TRANSFER_MODE:-}"   # empty = role default

# Smoke sizing: ONE short benchmark per configuration.  LLM stages run a
# single GuideLLM concurrency level instead of the group-vars default sweep
# ([1,2,4,8,16,32]); embedding stages run a single shape and a single
# operating-point probe.  Full sweeps live in the benchmark suites.
GUIDELLM_PROFILE="${GUIDELLM_PROFILE:-concurrent}"
GUIDELLM_RATE="${GUIDELLM_RATE:-8}"
# NOTE: -e "k=v" values stay STRINGS in ansible (no YAML parsing), which broke
# embedding_workload_shapes / op_probe_levels in earlier runs.  List/dict
# values must be passed as one JSON extra-vars document so they arrive typed.
# (The JSON defaults use if-unset assignments because ${VAR:-...} expansion
# terminates at the first '}' — a brace inside the default would be eaten.)
if [[ -z "${EMBEDDING_SMOKE_SHAPE:-}" ]]; then
    EMBEDDING_SMOKE_SHAPE='[{"name":"chunk","input_len":512}]'
fi
if [[ -z "${EMBEDDING_PROBE_LEVELS:-}" ]]; then
    EMBEDDING_PROBE_LEVELS='[8]'
fi
EMBEDDING_EXTRA_VARS="{\"embedding_workload_shapes\":${EMBEDDING_SMOKE_SHAPE},\"op_probe_levels\":${EMBEDDING_PROBE_LEVELS}}"

PRE_CLEAN="${PRE_CLEAN:-true}"
RESULTS_ROOT="${RESULTS_ROOT:-$REPO_ROOT/results}"

# Caller may set VALIDATION_LOG_DIR before sourcing; otherwise pick a timestamped dir.
if [[ -z "${VALIDATION_LOG_DIR:-}" ]]; then
    VALIDATION_LOG_DIR="$RESULTS_ROOT/validation-$(date +%Y%m%d-%H%M%S)"
fi
LOG_DIR="$VALIDATION_LOG_DIR"

STAGES="${STAGES:-all}"

# --- Helpers ----------------------------------------------------------------
if [[ -t 1 ]]; then
    C_G=$'\033[32m'; C_R=$'\033[31m'; C_Y=$'\033[33m'; C_B=$'\033[1m'; C_0=$'\033[0m'
else
    C_G=""; C_R=""; C_Y=""; C_B=""; C_0=""
fi

mkdir -p "$LOG_DIR"
declare -a STAGE_NAMES=()
declare -a STAGE_RCS=()
declare -a STAGE_SECS=()

log()  { printf '%s\n' "$*"; }
info() { printf '%s[INFO]%s %s\n' "$C_B" "$C_0" "$*"; }
warn() { printf '%s[WARN]%s %s\n' "$C_Y" "$C_0" "$*"; }

stage_enabled() {
    [[ "$STAGES" == "all" ]] && return 0
    [[ ",$STAGES," == *",$1,"* ]]
}

run_stage() {
    local num="$1" name="$2"; shift 2
    local start rc
    STAGE_NAMES+=("$name"); STAGE_RCS+=("pending")
    local idx=$(( ${#STAGE_NAMES[@]} - 1 ))
    printf '\n%s════════ Stage %s: %s ════════%s\n' "$C_B" "$num" "$name" "$C_0"
    start=$SECONDS
    "$@" > >(tee "$LOG_DIR/stage${num}-${name// /_}.log") 2>&1
    rc=$?
    STAGE_RCS[$idx]=$rc
    STAGE_SECS[$idx]=$(( SECONDS - start ))
    if [[ $rc -eq 0 ]]; then
        printf '%s✓ PASS%s stage %s (%s) in %ss — log: %s\n' \
            "$C_G" "$C_0" "$num" "$name" "${STAGE_SECS[$idx]}" "$LOG_DIR/stage${num}-${name// /_}.log"
    else
        printf '%s✗ FAIL%s stage %s (%s) rc=%s in %ss — log: %s\n' \
            "$C_R" "$C_0" "$num" "$name" "$rc" "${STAGE_SECS[$idx]}" "$LOG_DIR/stage${num}-${name// /_}.log"
    fi
    return $rc
}

ansible_cmd() {
    # Run from the ansible directory so ansible.cfg loads (roles_path,
    # filter_plugins, host_key_checking).  Without it, include_role inside
    # common/*.yml cannot resolve roles/vllm_server — embedding stages fail
    # with "The role 'vllm_server' was not found".
    (cd "$ANSIBLE_DIR" && ansible-playbook -i "$INVENTORY" "$@")
}

scaleout_teardown() {
    ansible_cmd "$ANSIBLE_DIR/stop-vllm-scaleout.yml"
}

HF_ARGS=()
if [[ -n "${HF_TOKEN:-}" ]]; then
    HF_ARGS=(-e "hf_token=${HF_TOKEN}")
fi

validation_print_banner() {
    log ""
    log "${C_B}╔══════════════════════════════════════════════════════════════════╗${C_0}"
    log "${C_B}║  vLLM CPU Pipeline Validation                                     ║${C_0}"
    log "${C_B}╚══════════════════════════════════════════════════════════════════╝${C_0}"
    info "Repo        : $REPO_ROOT"
    info "Inventory   : $INVENTORY"
    info "DUT         : ${DUT_HOSTNAME:-<unset>}"
    info "LoadGen     : ${LOADGEN_HOSTNAME:-<unset>}"
    info "Models      : LLM=$LLM_MODEL  Embedding=$EMBEDDING_MODEL"
    info "Scale-out   : ${SCALEOUT_NUM_INSTANCES}x${SCALEOUT_CORES_PER_INSTANCE} cores from core $SCALEOUT_START_CORE, $SCALEOUT_ROUTING_POLICY"
    info "Embed scale : ${EMBEDDING_SCALEOUT_NUM_INSTANCES}x${EMBEDDING_SCALEOUT_CORES_PER_INSTANCE} from core $EMBEDDING_SCALEOUT_START_CORE (stage 9)"
    info "CPU pins    : single=${REQUESTED_CORES}c  envoy=${SCALEOUT_ENVOY_CORES}  epp=${SCALEOUT_EPP_CORES}  guidellm=${GUIDELLM_CPUS}  vllm-bench=${VLLM_BENCH_CPUS}"
    info "LMCache     : l1=${LMCACHE_L1_GB}GB hugepages=${LMCACHE_HUGEPAGES} util=${LMCACHE_UTIL}"
    info "Quick caps  : ${QUICK_SECONDS}s / ${QUICK_REQUESTS} reqs; LLM ${GUIDELLM_PROFILE}@rate ${GUIDELLM_RATE}; embedding probes ${EMBEDDING_PROBE_LEVELS} (${EMBEDDING_SMOKE_SHAPE})"
    info "Stages      : $STAGES"
    info "Logs        : $LOG_DIR"
    log ""
}

stage0() {
    local failed=0
    for v in DUT_HOSTNAME LOADGEN_HOSTNAME; do
        if [[ -z "${!v:-}" ]]; then
            warn "$v is not set — the inventory needs it"; failed=1
        fi
    done
    if [[ -n "${ANSIBLE_SSH_KEY:-}" && ! -f "${ANSIBLE_SSH_KEY/#\~/$HOME}" ]]; then
        warn "ANSIBLE_SSH_KEY not found: $ANSIBLE_SSH_KEY"; failed=1
    fi
    if [[ -z "${HF_TOKEN:-}" ]]; then
        warn "HF_TOKEN not set — gated models (Llama) will fail"
    fi
    [[ $failed -eq 1 ]] && return 1
    info "Ansible connectivity check (dut + load_generator)…"
    (cd "$ANSIBLE_DIR" && ansible dut:load_generator -i "$INVENTORY" -m ping)
}

single_llm() {
    local workload="$1"
    ansible_cmd "$ANSIBLE_DIR/llm-benchmark-auto.yml" \
        -e "test_model=${LLM_MODEL}" \
        -e "workload_type=${workload}" \
        -e "requested_cores=${REQUESTED_CORES}" \
        -e "guidellm_profile=${GUIDELLM_PROFILE}" \
        -e "guidellm_rate=${GUIDELLM_RATE}" \
        -e "guidellm_max_seconds=${QUICK_SECONDS}" \
        -e "guidellm_max_requests=${QUICK_REQUESTS}" \
        ${HF_ARGS[@]+"${HF_ARGS[@]}"}
}

single_embedding() {
    ansible_cmd "$ANSIBLE_DIR/embedding-benchmark.yml" \
        -e "test_model=${EMBEDDING_MODEL}" \
        -e "requested_cores=${REQUESTED_CORES}" \
        -e "scenario=operating_point" \
        -e "$EMBEDDING_EXTRA_VARS" \
        -e "num_prompts=64" \
        -e "op_peak_concurrency=8" \
        ${HF_ARGS[@]+"${HF_ARGS[@]}"}
}

multi_llm() {
    local workload="$1"; shift
    if [[ "$PRE_CLEAN" == "true" ]]; then
        info "Pre-clean: removing any leftover scale-out containers/SHM"
        scaleout_teardown || warn "pre-clean teardown had errors (continuing)"
    fi
    local -a extra=("$@")
    if [[ -n "$LMCACHE_TRANSFER_MODE" ]]; then
        extra+=(-e "scaleout_lmcache_mp_transfer_mode=${LMCACHE_TRANSFER_MODE}")
    fi
    ansible_cmd "$ANSIBLE_DIR/llm-benchmark-scaleout.yml" \
        -e "test_model=${LLM_MODEL}" \
        -e "workload_type=${workload}" \
        -e "scaleout_num_instances=${SCALEOUT_NUM_INSTANCES}" \
        -e "scaleout_cores_per_instance=${SCALEOUT_CORES_PER_INSTANCE}" \
        -e "scaleout_start_core=${SCALEOUT_START_CORE}" \
        -e "guidellm_cpus=${GUIDELLM_CPUS}" \
        -e "guidellm_numa_node=${GUIDELLM_NUMA_NODE}" \
        -e "scaleout_routing_policy=${SCALEOUT_ROUTING_POLICY}" \
        -e "scaleout_envoy_cores=${SCALEOUT_ENVOY_CORES}" \
        -e "scaleout_epp_cores=${SCALEOUT_EPP_CORES}" \
        -e "scaleout_envoy_concurrency=${SCALEOUT_ENVOY_CONCURRENCY}" \
        -e "guidellm_profile=${GUIDELLM_PROFILE}" \
        -e "guidellm_rate=${GUIDELLM_RATE}" \
        -e "guidellm_max_seconds=${QUICK_SECONDS}" \
        -e "guidellm_max_requests=${QUICK_REQUESTS}" \
        ${HF_ARGS[@]+"${HF_ARGS[@]}"} "${extra[@]+"${extra[@]}"}"
}

multi_llm_lmcache() {
    info "LMCache stage: first run builds the vllm-cpu-lmcache image (slow)."
    info "If the connector fails at startup, retry with:"
    info "  STAGES=6 LMCACHE_TRANSFER_MODE=vllm_driven ${VALIDATION_MAIN_SCRIPT:-validate-pipelines.sh}"
    multi_llm chat \
        -e "scaleout_lmcache_backend=remote" \
        -e "scaleout_lmcache_server_l1_size_gb=${LMCACHE_L1_GB}" \
        -e "scaleout_lmcache_hugepages_enabled=${LMCACHE_HUGEPAGES}" \
        -e "scaleout_vllm_gpu_memory_utilization=${LMCACHE_UTIL}"
}

multi_embedding_scaleout() {
    if [[ "$PRE_CLEAN" == "true" ]]; then
        info "Pre-clean: removing any leftover scale-out containers/SHM"
        scaleout_teardown || warn "pre-clean teardown had errors (continuing)"
    fi
    ansible_cmd "$ANSIBLE_DIR/embedding-benchmark-scaleout.yml" \
        -e "test_model=${EMBEDDING_MODEL}" \
        -e "scenario=operating_point" \
        -e "$EMBEDDING_EXTRA_VARS" \
        -e "num_prompts=64" \
        -e "op_peak_concurrency=8" \
        -e "scaleout_num_instances=${EMBEDDING_SCALEOUT_NUM_INSTANCES}" \
        -e "scaleout_cores_per_instance=${EMBEDDING_SCALEOUT_CORES_PER_INSTANCE}" \
        -e "scaleout_start_core=${EMBEDDING_SCALEOUT_START_CORE}" \
        -e "scaleout_routing_policy=${SCALEOUT_ROUTING_POLICY}" \
        -e "scaleout_envoy_cores=${SCALEOUT_ENVOY_CORES}" \
        -e "scaleout_epp_cores=${SCALEOUT_EPP_CORES}" \
        -e "scaleout_envoy_concurrency=${SCALEOUT_ENVOY_CONCURRENCY}" \
        -e "vllm_bench_cpus=${VLLM_BENCH_CPUS}" \
        -e "vllm_bench_numa_node=${VLLM_BENCH_NUMA_NODE}" \
        ${HF_ARGS[@]+"${HF_ARGS[@]}"}
}

results_visibility() {
    local rc=0 out latest_emb
    info "LLM results via view_results.py…"
    out="$(python3 "$VIEW_RESULTS" "$RESULTS_ROOT/llm" 2>&1)" || true
    printf '%s\n' "$out" | tail -5
    if [[ -z "$out" || "$out" == *"No results"* || "$out" == *"No benchmarks"* ]]; then
        warn "view_results.py found no LLM results under $RESULTS_ROOT/llm"; rc=1
    fi

    info "Embedding results via view_results.py (latest run)…"
    latest_emb="$(ls -td "$RESULTS_ROOT"/embedding/*/*/ 2>/dev/null | head -1 || true)"
    if [[ -z "$latest_emb" ]]; then
        warn "no embedding run directories under $RESULTS_ROOT/embedding"; rc=1
    else
        info "latest embedding run: $latest_emb"
        out="$(python3 "$VIEW_RESULTS" "${latest_emb%/}" 2>&1)" || true
        printf '%s\n' "$out" | tail -8
        if [[ -z "$out" || "$out" == *"No results"* || "$out" == *"No embedding"* ]]; then
            warn "view_results.py found no embedding results in $latest_emb"; rc=1
        fi
    fi
    return $rc
}

validation_run_stages() {
    want() { stage_enabled "$1"; }

    want 0 && run_stage 0 "preflight"            stage0
    want 1 && run_stage 1 "single chat"          single_llm chat
    want 2 && run_stage 2 "single summarization" single_llm summarization
    want 3 && run_stage 3 "single embedding"     single_embedding
    want 4 && run_stage 4 "multi chat"           multi_llm chat
    want 5 && run_stage 5 "multi summarization"  multi_llm summarization
    want 6 && run_stage 6 "multi chat lmcache"   multi_llm_lmcache
    want 9 && run_stage 9 "multi embedding"      multi_embedding_scaleout
    want 7 && run_stage 7 "results visibility"   results_visibility
    want 8 && run_stage 8 "final teardown"       scaleout_teardown
}

validation_print_summary() {
    if [[ ${#STAGE_NAMES[@]} -eq 0 ]]; then
        warn "No stages selected (STAGES=${STAGES}). Valid stage numbers: 0-6, 7, 8, 9"
        return 1
    fi

    log ""
    log "${C_B}╔══════════════ Validation Summary ════════════════════════════════╗${C_0}"
    local fails=0
    local i
    for i in "${!STAGE_NAMES[@]}"; do
        if [[ "${STAGE_RCS[$i]}" == "pending" ]]; then continue; fi
        if [[ "${STAGE_RCS[$i]}" -eq 0 ]]; then
            printf '  %s✓ PASS%s %-22s %ss\n' "$C_G" "$C_0" "${STAGE_NAMES[$i]}" "${STAGE_SECS[$i]:-?}"
        else
            printf '  %s✗ FAIL%s %-22s %ss (rc=%s)\n' "$C_R" "$C_0" "${STAGE_NAMES[$i]}" "${STAGE_SECS[$i]:-?}" "${STAGE_RCS[$i]}"
            fails=$((fails + 1))
        fi
    done
    log "${C_B}╚══════════════════════════════════════════════════════════════════╝${C_0}"
    info "Full logs: $LOG_DIR"

    if [[ $fails -gt 0 ]]; then
        log "${C_R}$fails stage(s) FAILED${C_0}"
        return 1
    fi
    log "${C_G}All stages passed${C_0}"
    return 0
}
