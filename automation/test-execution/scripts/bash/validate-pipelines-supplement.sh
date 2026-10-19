#!/usr/bin/env bash
# ============================================================================
# validate-pipelines-supplement.sh — run added/fixed stages after a full harness
# ============================================================================
# Use when validate-pipelines.sh is already in flight (older revision) or you
# only need to backfill gaps from a prior run:
#
#   Default STAGES=3,9,7
#     3 — single embedding with correct requested_cores / REQUESTED_CORES
#     9 — multi-instance embedding scale-out smoke
#     7 — refresh view_results.py output
#
# Examples:
#   ./validate-pipelines-supplement.sh
#   STAGES=9 ./validate-pipelines-supplement.sh
#   VALIDATION_LOG_DIR=$RESULTS_ROOT/validation-20251019-120000 \
#     STAGES=3,9 ./validate-pipelines-supplement.sh
#
# Same env tunables as validate-pipelines.sh (see validate-pipelines-common.sh).
#
# Stage 0 (preflight) is omitted by default — use this after a full harness run
# or when inventory/SSH is already known good. Add preflight with STAGES=0,3,9,7.
# ============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT_SUPP="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
# shellcheck disable=SC2034  # read by validate-pipelines-common.sh (LMCache retry hint)
VALIDATION_MAIN_SCRIPT="$0"

# Default stages for supplement runs (override with STAGES=…).
export STAGES="${STAGES:-3,9,7}"

# Separate log dir unless the caller reuses an existing validation folder.
if [[ -z "${VALIDATION_LOG_DIR:-}" ]]; then
    VALIDATION_LOG_DIR="${RESULTS_ROOT:-$REPO_ROOT_SUPP/results}/validation-supplement-$(date +%Y%m%d-%H%M%S)"
    export VALIDATION_LOG_DIR
fi

# shellcheck source=validate-pipelines-common.sh
source "$SCRIPT_DIR/validate-pipelines-common.sh"

info "Supplement run — stages ${STAGES} (default 3,9,7: single embed + multi embed + results)"
validation_print_banner
validation_run_stages
validation_print_summary || exit 1
