#!/usr/bin/env bash
# ============================================================================
# validate-pipelines.sh — end-to-end pipeline validation (single + multi instance)
# ============================================================================
# Runs a quick validation matrix against a DUT configured via environment
# variables (the same vars the inventory reads):
#
#   export DUT_HOSTNAME=ec2-XX-XX-XX-XX.eu-west-1.compute.amazonaws.com
#   export LOADGEN_HOSTNAME=$DUT_HOSTNAME          # same host = single-host mode
#   export ANSIBLE_SSH_KEY=~/eu-mtahhan.pem
#   export ANSIBLE_SSH_USER=ec2-user
#   export VLLM_ENDPOINT_MODE=dut-only             # normalises to 'managed'
#   export HF_TOKEN=$(cat ~/hf_token)
#
# Stages:
#   0  preflight          — env checks + ansible ping (dut + load_generator)
#   1  single chat        — llm-benchmark-auto.yml, short run, self-cleaning
#   2  single summarization — same, different workload shape
#   3  single embedding   — embedding-benchmark.yml, operating_point smoke
#   4  multi chat         — llm-benchmark-scaleout.yml, NO LMCache
#   5  multi summarization — same topology, different workload
#   6  multi chat + LMCache — scaleout_lmcache_backend=remote (causal-LM only)
#   7  results visibility — view_results.py parses the runs produced above
#   8  teardown           — stop-vllm-scaleout.yml (idempotent final cleanup)
#
# Usage:
#   ./validate-pipelines.sh                      # all stages
#   STAGES=0,4,6 ./validate-pipelines.sh         # subset
#   STAGES=6 LMCACHE_TRANSFER_MODE=vllm_driven ./validate-pipelines.sh
#
# Tunables (env, with defaults):
#   LLM_MODEL, EMBEDDING_MODEL, QUICK_SECONDS, QUICK_REQUESTS,
#   SCALEOUT_NUM_INSTANCES, SCALEOUT_CORES_PER_INSTANCE, SCALEOUT_START_CORE,
#   GUIDELLM_CPUS, GUIDELLM_NUMA_NODE, SCALEOUT_ROUTING_POLICY,
#   LMCACHE_L1_GB, LMCACHE_HUGEPAGES, LMCACHE_UTIL, LMCACHE_TRANSFER_MODE,
#   PRE_CLEAN (true/false), RESULTS_ROOT, VALIDATION_LOG_DIR
#
# Notes:
# - Stage 6 builds the vllm-cpu-lmcache image on first run (multi-GB, slow).
# - Each stage logs to $VALIDATION_LOG_DIR/<stage>.log; failures don't stop
#   the suite — a summary is printed at the end.
# ============================================================================

set -uo pipefail

# --- Locate the repo --------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
ANSIBLE_DIR="$REPO_ROOT/automation/test-execution/ansible"
INVENTORY="$ANSIBLE_DIR/inventory/hosts.yml"
VIEW_RESULTS="$REPO_ROOT/automation/test-execution/scripts/conversion/view_results.py"

# --- Configuration (env-overridable) ----------------------------------------
LLM_MODEL="${LLM_MODEL:-RedHatAI/Meta-Llama-3.1-8B-Instruct-quantized.w8a8}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-RedHatAI/granite-embedding-english-r2}"
QUICK_SECONDS="${QUICK_SECONDS:-180}"      # per-benchmark wall-clock cap (LLM stages)
QUICK_REQUESTS="${QUICK_REQUESTS:-64}"     # per-benchmark request cap (LLM stages)

SCALEOUT_NUM_INSTANCES="${SCALEOUT_NUM_INSTANCES:-2}"
SCALEOUT_CORES_PER_INSTANCE="${SCALEOUT_CORES_PER_INSTANCE:-24}"
SCALEOUT_START_CORE="${SCALEOUT_START_CORE:-0}"
GUIDELLM_CPUS="${GUIDELLM_CPUS:-48-71}"
GUIDELLM_NUMA_NODE="${GUIDELLM_NUMA_NODE:-0}"
SCALEOUT_ROUTING_POLICY="${SCALEOUT_ROUTING_POLICY:-intelligent}"

LMCACHE_L1_GB="${LMCACHE_L1_GB:-10}"
LMCACHE_HUGEPAGES="${LMCACHE_HUGEPAGES:-true}"
LMCACHE_UTIL="${LMCACHE_UTIL:-0.4}"
LMCACHE_TRANSFER_MODE="${LMCACHE_TRANSFER_MODE:-}"   # empty = role default

PRE_CLEAN="${PRE_CLEAN:-true}"
RESULTS_ROOT="${RESULTS_ROOT:-$REPO_ROOT/results}"
LOG_DIR="${VALIDATION_LOG_DIR:-$RESULTS_ROOT/validation-$(date +%Y%m%d-%H%M%S)}"

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

# run_stage <num> <name> <cmd...> — runs cmd, captures rc + duration, logs
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

ansible_cmd() {  # common playbook invocation prefix
    ansible-playbook -i "$INVENTORY" "$@"
}

scaleout_teardown() {
    ansible_cmd "$ANSIBLE_DIR/stop-vllm-scaleout.yml"
}

# HF token as an array (guarded expansion keeps bash 3.2 + set -u happy)
HF_ARGS=()
if [[ -n "${HF_TOKEN:-}" ]]; then
    HF_ARGS=(-e "hf_token=${HF_TOKEN}")
fi

# --- Banner -----------------------------------------------------------------
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
info "LMCache     : l1=${LMCACHE_L1_GB}GB hugepages=${LMCACHE_HUGEPAGES} util=${LMCACHE_UTIL}"
info "Quick caps  : ${QUICK_SECONDS}s / ${QUICK_REQUESTS} requests per LLM benchmark"
info "Logs        : $LOG_DIR"
log ""

# ============================================================================
# Stage 0 — preflight
# ============================================================================
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
    ansible dut:load_generator -i "$INVENTORY" -m ping
}

# ============================================================================
# Stages 1-2 — single-instance LLM (auto playbook deploys + self-cleans)
# ============================================================================
single_llm() {
    local workload="$1"
    ansible_cmd "$ANSIBLE_DIR/llm-benchmark-auto.yml" \
        -e "test_model=${LLM_MODEL}" \
        -e "workload_type=${workload}" \
        -e "guidellm_max_seconds=${QUICK_SECONDS}" \
        -e "guidellm_max_requests=${QUICK_REQUESTS}" \
        ${HF_ARGS[@]+"${HF_ARGS[@]}"}
}

# ============================================================================
# Stage 3 — single-instance embedding (operating-point smoke)
# ============================================================================
single_embedding() {
    ansible_cmd "$ANSIBLE_DIR/embedding-benchmark.yml" \
        -e "test_model=${EMBEDDING_MODEL}" \
        -e "scenario=operating_point" \
        -e "num_prompts=64" \
        -e "op_peak_concurrency=8" \
        ${HF_ARGS[@]+"${HF_ARGS[@]}"}
}

# ============================================================================
# Stages 4-6 — multi-instance scale-out (full lifecycle incl. teardown)
# ============================================================================
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
        -e "guidellm_max_seconds=${QUICK_SECONDS}" \
        -e "guidellm_max_requests=${QUICK_REQUESTS}" \
        ${HF_ARGS[@]+"${HF_ARGS[@]}"} "${extra[@]+"${extra[@]}"}"
}

multi_llm_lmcache() {
    info "LMCache stage: first run builds the vllm-cpu-lmcache image (slow)."
    info "If the connector fails at startup, retry with:"
    info "  STAGES=6 LMCACHE_TRANSFER_MODE=vllm_driven $0"
    multi_llm chat \
        -e "scaleout_lmcache_backend=remote" \
        -e "scaleout_lmcache_server_l1_size_gb=${LMCACHE_L1_GB}" \
        -e "scaleout_lmcache_hugepages_enabled=${LMCACHE_HUGEPAGES}" \
        -e "scaleout_vllm_gpu_memory_utilization=${LMCACHE_UTIL}"
}

# ============================================================================
# Stage 7 — results visibility (viewers must parse what the stages produced)
# ============================================================================
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

# ============================================================================
# Run the selected stages
# ============================================================================
want() { stage_enabled "$1"; }

want 0 && run_stage 0 "preflight"            stage0
want 1 && run_stage 1 "single chat"          single_llm chat
want 2 && run_stage 2 "single summarization" single_llm summarization
want 3 && run_stage 3 "single embedding"     single_embedding
want 4 && run_stage 4 "multi chat"           multi_llm chat
want 5 && run_stage 5 "multi summarization"  multi_llm summarization
want 6 && run_stage 6 "multi chat lmcache"   multi_llm_lmcache
want 7 && run_stage 7 "results visibility"   results_visibility
want 8 && run_stage 8 "final teardown"       scaleout_teardown

# --- Summary ----------------------------------------------------------------
log ""
log "${C_B}╔══════════════ Validation Summary ════════════════════════════════╗${C_0}"
fails=0
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
    exit 1
fi
log "${C_G}All stages passed${C_0}"
