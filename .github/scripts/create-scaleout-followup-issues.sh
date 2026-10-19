#!/usr/bin/env bash
# Create GitHub follow-up issues for multi-instance / scale-out work.
# Prereq: gh auth login (or GH_TOKEN with issues:write on this repo).
#
# Usage:
#   ./.github/scripts/create-scaleout-followup-issues.sh
#   DRY_RUN=1 ./.github/scripts/create-scaleout-followup-issues.sh   # print only

set -euo pipefail

REPO="${GITHUB_REPOSITORY:-redhat-et/vllm-cpu-perf-eval}"
DRY_RUN="${DRY_RUN:-0}"

create_issue() {
    local title="$1"
    local body="$2"
    local labels="${3:-enhancement}"

    if [[ "$DRY_RUN" == "1" ]]; then
        printf '\n=== %s ===\nLabels: %s\n%s\n' "$title" "$labels" "$body"
        return 0
    fi
    gh issue create --repo "$REPO" --title "$title" --label "$labels" --body "$body"
}

if [[ "$DRY_RUN" != "1" ]]; then
    gh auth status >/dev/null 2>&1 || {
        echo "Run: gh auth login  (or set GH_TOKEN)" >&2
        exit 1
    }
fi

create_issue \
    "scaleout: benchmark playbooks hard-code Envoy/EPP cores for large hosts (72-83)" \
    "$(cat <<'EOF'
## Problem
Integrated `*-benchmark-scaleout.yml` playbooks default Envoy/EPP to `72-75` / `76-83` (SMT siblings). That matches c8i.24xlarge-style layouts but **fails CPU verification** on smaller DUTs (cores 72+ do not exist).

The validation harness uses the same defaults via `SCALEOUT_ENVOY_CORES` / `SCALEOUT_EPP_CORES`.

## Proposed direction
- Derive router pins from `scaleout_start_core`, instance count, and cores/instance (place Envoy/EPP after the last vLLM cpuset, or on the opposite socket).
- Or: ship **topology profiles** in inventory (`scaleout_smoke`, `scaleout_production`) instead of magic core numbers.
- Pre-flight check in playbooks: fail with a clear message when `max(requested_cores) >= online_cpu_count`.

## References
- `llm-benchmark-scaleout.yml` import vars
- `validate-pipelines-common.sh`
- `vllm_scaleout` CPU verify task in `roles/vllm_scaleout/tasks/main.yml`
EOF
)" \
    "enhancement"

create_issue \
    "docs: document validate-pipelines harness and scaleout_strict_cpu_isolation" \
    "$(cat <<'EOF'
## Problem
`validate-pipelines.sh` is the primary DUT smoke path for scale-out but is **not linked** from `docs/scripts-reference.md` or `docs/vllm-scaleout.md`.

`scaleout_strict_cpu_isolation` (role default `true`) is only mentioned in inventory comments, not in the scale-out guide.

## Acceptance criteria
- [ ] Add a **Pipeline validation** section to `docs/vllm-scaleout.md` covering:
  - Full run vs `--supplement`
  - `STAGES=all` excluding LMCache unless `INCLUDE_LMCACHE=1`
  - `STOP_ON_FAIL`, interrupt → teardown
  - Key env tunables (`SCALEOUT_*`, `REQUESTED_CORES`, embedding smoke JSON vars)
- [ ] Entry in `docs/scripts-reference.md` pointing to the script
- [ ] Document `scaleout_strict_cpu_isolation` and overlap failure modes + overrides
EOF
)" \
    "documentation"

create_issue \
    "validation: stage 7 should prefer scale-out embedding results when present" \
    "$(cat <<'EOF'
## Problem
`results_visibility` (stage 7) only prefers `deployment_type: scaleout` embedding runs when **stage 9 is in the current `STAGES` list**.

`./validate-pipelines.sh --supplement` with default `STAGES=3,9,7` is fine. If someone runs `STAGES=3,7` after a prior scale-out run, stage 7 validates the **newest single-instance** embedding run and can false-fail even though scale-out artifacts exist.

## Proposed fix
In `_find_latest_embedding_run_dir` / stage 7:
- If any scale-out embedding run exists under `results/embedding`, use the newest scale-out by mtime (unless `PREFER_SINGLE_EMBEDDING=1`).
- Log which directory was chosen and why.

## Files
- `automation/test-execution/scripts/bash/validate-pipelines-common.sh`
- `automation/test-execution/tests/scripts/test_validate_pipelines.sh` (add case)
EOF
)" \
    "bug"

create_issue \
    "ansible: stop-vllm-scaleout.yml should reuse scaleout_config_dir from role defaults" \
    "$(cat <<'EOF'
## Problem
`stop-vllm-scaleout.yml` hard-codes `scaleout_config_dir: /tmp/vllm-scaleout` in playbook `vars`, duplicating `roles/vllm_scaleout/defaults/main.yml` and `group_vars/all/vllm-scaleout.yml`.

If a deploy uses a custom `scaleout_config_dir`, teardown may miss compose state.

## Proposed fix
- Remove playbook-local override; rely on group_vars / `-e scaleout_config_dir=...`
- Or `include_vars` from role defaults before tasks
- Add a one-line note in playbook header that `-e scaleout_config_dir` must match deploy

## Files
- `automation/test-execution/ansible/stop-vllm-scaleout.yml`
EOF
)" \
    "enhancement"

create_issue \
    "test: unit-test vllm_scaleout CPU overlap verifier (strict vs warn-only)" \
    "$(cat <<'EOF'
## Problem
CPU overlap detection lives in an inline Python heredoc in `roles/vllm_scaleout/tasks/main.yml`. Behaviour changed with `scaleout_strict_cpu_isolation` (fail vs warn). There is no automated test outside full Ansible deploy.

## Proposed fix
- Extract verifier to `roles/vllm_scaleout/files/verify_scaleout_cpusets.py` (or `ansible/tests/unit/`)
- Table-driven tests: overlap + strict=true → exit 1; overlap + strict=false → exit 0 with warnings; missing cores → exit 1

## Related
Harness tests in `automation/test-execution/tests/scripts/test_validate_pipelines.sh` do not cover this path.
EOF
)" \
    "testing"

create_issue \
    "ci: optional scheduled DUT job for validate-pipelines.sh" \
    "$(cat <<'EOF'
## Problem
Scale-out Ansible paths are covered by bash contract tests (`test_validate_pipelines.sh`) but not by an automated deploy on real hardware. Regressions in compose, EPP, or LMCache only show up in manual runs.

## Proposal (non-blocking)
- Self-hosted or lab runner with inventory secrets
- Weekly / on-demand workflow: `STAGES=0,4,9,7,8` (skip LMCache unless `INCLUDE_LMCACHE=1`)
- Upload `VALIDATION_LOG_DIR` as artifact on failure

## Notes
Stage 6 (LMCache) should remain opt-in due to image build time.
EOF
)" \
    "enhancement"

echo "Done."
