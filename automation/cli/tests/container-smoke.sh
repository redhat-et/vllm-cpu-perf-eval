#!/usr/bin/env bash
# Smoke-test the repo-root ./cpueval launcher and common commands.
# Intended to run inside a RHEL/Fedora container (UBI 9, Fedora, …).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

if [[ ! -x ./cpueval ]]; then
    echo "error: ./cpueval is missing or not executable" >&2
    exit 1
fi

echo "==> ./cpueval list"
./cpueval list

echo "==> ./cpueval show rhaiis-sweep"
./cpueval show rhaiis-sweep

echo "==> ./cpueval install --help"
./cpueval install --help

echo "==> ./cpueval install --dry-run"
./cpueval install --dry-run

echo "==> ./cpueval install --skip-completion"
./cpueval install --skip-completion

echo "==> ./cpueval --suite rhaiis-sweep --dry-run"
./cpueval --suite rhaiis-sweep --dry-run

echo "==> ./cpueval doctor --no-ping (env vars unset is expected)"
set +e
doctor_out="$(./cpueval doctor --no-ping 2>&1)"
doctor_rc=$?
set -e
printf '%s\n' "$doctor_out"
if ! printf '%s\n' "$doctor_out" | grep -q "ansible-playbook"; then
    echo "error: doctor output did not mention ansible-playbook" >&2
    exit 1
fi
if [[ "$doctor_rc" -eq 0 ]]; then
    echo "warning: doctor succeeded without DUT_HOSTNAME (unexpected in CI)" >&2
fi

echo "==> container smoke passed"
