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
#   0  preflight            — env checks + ansible ping (dut + load_generator)
#   1  single chat           — llm-benchmark-auto.yml, short run, self-cleaning
#   2  single summarization  — same, different workload shape
#   3  single embedding      — embedding-benchmark.yml (uses REQUESTED_CORES)
#   4  multi chat            — llm-benchmark-scaleout.yml, NO LMCache
#   5  multi summarization   — same topology, different workload
#   6  multi chat + LMCache   — scaleout_lmcache_backend=remote (causal-LM only)
#   9  multi embedding       — embedding-benchmark-scaleout.yml smoke
#   7  results visibility    — view_results.py parses the runs produced above
#   8  teardown              — stop-vllm-scaleout.yml (idempotent final cleanup)
#
# Usage:
#   ./validate-pipelines.sh                      # all stages (0-6, 9, 7, 8)
#   STAGES=0,4,6 ./validate-pipelines.sh         # subset
#   STAGES=6 LMCACHE_TRANSFER_MODE=vllm_driven ./validate-pipelines.sh
#
# Supplement mode (backfill after a full run; default STAGES=3,9,7, skips preflight):
#   ./validate-pipelines.sh --supplement
#   ./validate-pipelines.sh -s
#   SUPPLEMENT=1 ./validate-pipelines.sh
#   STAGES=9 ./validate-pipelines.sh --supplement
#   VALIDATION_LOG_DIR=$RESULTS_ROOT/validation-YYYYMMDD-HHMMSS \
#     STAGES=3,9,7 ./validate-pipelines.sh --supplement
#
# Tunables (env, with defaults):
#   LLM_MODEL, EMBEDDING_MODEL, QUICK_SECONDS, QUICK_REQUESTS, REQUESTED_CORES,
#   SCALEOUT_* , GUIDELLM_*, EMBEDDING_SCALEOUT_* , VLLM_BENCH_* ,
#   LMCACHE_*, PRE_CLEAN, RESULTS_ROOT, VALIDATION_LOG_DIR, STAGES, SUPPLEMENT
#
# Notes:
# - Smoke sizing: ONE short benchmark per configuration — LLM stages run a
#   single GuideLLM concurrency level (GUIDELLM_PROFILE / GUIDELLM_RATE) and
#   embedding stages a single shape + probe (EMBEDDING_SMOKE_SHAPE /
#   EMBEDDING_PROBE_LEVELS).  Full sweeps live in the benchmark suites.
# - Stage 6 builds the vllm-cpu-lmcache image on first run (multi-GB, slow).
# - Each stage logs to $VALIDATION_LOG_DIR/stage<N>-<name>.log
# ============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT_EARLY="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

usage() {
    # Extract the Usage block from the header (marker-based, robust to edits)
    sed -n '/^# Usage:/,/^# Tunables/p' "$0" \
        | sed 's/^# \{0,1\}//' \
        | sed -e '/^Tunables (env, with defaults):/d' -e '${/^$/d}'
}

VALIDATION_SUPPLEMENT_MODE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --supplement|-s)
            VALIDATION_SUPPLEMENT_MODE=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf 'Unknown option: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "${SUPPLEMENT:-}" in true|1|yes|TRUE|YES) VALIDATION_SUPPLEMENT_MODE=true ;; esac

if [[ "$VALIDATION_SUPPLEMENT_MODE" == true ]]; then
    if [[ -z "${STAGES:-}" ]]; then
        STAGES=3,9,7
    fi
    if [[ -z "${VALIDATION_LOG_DIR:-}" ]]; then
        VALIDATION_LOG_DIR="${RESULTS_ROOT:-$_REPO_ROOT_EARLY/results}/validation-supplement-$(date +%Y%m%d-%H%M%S)"
    fi
    export STAGES VALIDATION_LOG_DIR
fi

# shellcheck disable=SC2034  # read by validate-pipelines-common.sh (LMCache retry hint)
VALIDATION_MAIN_SCRIPT="$0"
# shellcheck disable=SC2034
VALIDATION_SUPPLEMENT_MODE="$VALIDATION_SUPPLEMENT_MODE"
# shellcheck source=validate-pipelines-common.sh
source "$SCRIPT_DIR/validate-pipelines-common.sh"

if [[ "$VALIDATION_SUPPLEMENT_MODE" == true ]]; then
    info "Supplement mode — stages ${STAGES} (default 3,9,7: single embed + multi embed + results; no preflight unless STAGES includes 0)"
fi

validation_print_banner
validation_run_stages
validation_print_summary || exit 1
