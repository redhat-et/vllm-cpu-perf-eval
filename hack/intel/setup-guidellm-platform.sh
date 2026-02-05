#!/usr/bin/env bash
set -euo pipefail

# setup-guidellm-platform.sh
# - Installs tuning tools
# - Detects NUMA topology + SMT siblings via lscpu
# - Chooses:
#     * Housekeeping CPUs = ALL CPUs on NUMA node 0 (both SMT threads)
#     * guidellm CPUs     = primary threads on NUMA node 1
#     * vLLM CPUs         = primary threads on NUMA node 2 (or last node)
#     * Isolated CPUs     = guidellm + vLLM primary threads
# - Uses TUNED to configure kernel parameters (works properly with RHEL/CentOS/Fedora)
# - Configures: isolcpus/nohz_full/rcu_nocbs/irqaffinity/cpufreq
# - Optional: preempt=full
# - Disables irqbalance
# - Pins systemd slices to housekeeping CPUs (persistent)
# - IDEMPOTENT: Safe to run multiple times

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Usage:
  $SCRIPT_NAME [--apply] [--check] [--numa-balancing-off] [--thp-defrag-never] [--preempt-full]

Modes:
  --apply   Apply configuration (default if no mode specified)
  --check   Only check current configuration vs computed plan

Options:
  --numa-balancing-off   Persistently set kernel.numa_balancing=0
  --thp-defrag-never     Set THP defrag to 'never' (runtime + boot)
  --preempt-full         Enable full kernel preemption (preempt=full)
                         WARNING: May cause network instability on some hardware
                         Only use if you have <100μs latency requirements
                         Not recommended for ML inference workloads

EOF
}

MODE="apply"
DO_NUMA_BAL_OFF=0
DO_THP_DEFRAG=0
DO_PREEMPT_FULL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) MODE="apply"; shift ;;
    --check) MODE="check"; shift ;;
    --numa-balancing-off) DO_NUMA_BAL_OFF=1; shift ;;
    --thp-defrag-never) DO_THP_DEFRAG=1; shift ;;
    --preempt-full) DO_PREEMPT_FULL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing required command: $1" >&2; exit 1; }
}

echo "==> Checking required commands..."
require_cmd lscpu
require_cmd awk
require_cmd sort
require_cmd uniq
require_cmd grep
require_cmd sed
require_cmd tr

# -------- Topology discovery --------
echo "==> Reading NUMA/CPU topology from lscpu..."

if lscpu -e=CPU,NODE,CORE -n >/dev/null 2>&1; then
  LSCPU_OUT="$(lscpu -e=CPU,NODE,CORE -n | awk '{$1=$1}1')"
else
  LSCPU_OUT="$(lscpu -e=CPU,NODE,CORE | sed '1d' | awk '{$1=$1}1')"
fi

if [[ -z "${LSCPU_OUT}" ]]; then
  echo "ERROR: unable to read lscpu output." >&2
  exit 1
fi

NODES="$(echo "${LSCPU_OUT}" | awk '{print $2}' | sort -n | uniq)"
NODE_COUNT="$(echo "${NODES}" | wc -l | tr -d ' ')"

if (( NODE_COUNT < 2 )); then
  echo "ERROR: Need at least 2 NUMA nodes to split workloads." >&2
  echo "Detected nodes: ${NODES}" >&2
  exit 1
fi

HOUSE_NODE=0
GUIDE_NODE=1
if echo "${NODES}" | grep -qx "2"; then
  VLLM_NODE=2
else
  VLLM_NODE="$(echo "${NODES}" | tail -n 1)"
fi

if [[ "${GUIDE_NODE}" == "${VLLM_NODE}" ]]; then
  echo "WARNING: Only 2 NUMA nodes detected; cannot place guidellm and vLLM on distinct non-house nodes." >&2
  echo "Falling back to vLLM on node 0 (not recommended for strict isolation)." >&2
  VLLM_NODE=0
fi

node_all_cpus() {
  local node="$1"
  echo "${LSCPU_OUT}" | awk -v n="${node}" '$2==n {print $1}' | sort -n | tr '\n' ',' | sed 's/,$//'
}

node_primary_cpus() {
  local node="$1"
  echo "${LSCPU_OUT}" | awk -v n="${node}" '
    $2==n {
      cpu=$1; core=$3;
      if (!(core in min) || cpu < min[core]) min[core]=cpu;
    }
    END { for (c in min) print min[c]; }' | sort -n | tr '\n' ',' | sed 's/,$//'
}

to_ranges() {
  awk -v list="$1" '
    BEGIN {
      n=split(list,a,",");
      if(n==0){exit}
      start=a[1]; prev=a[1];
      out="";
      for(i=2;i<=n;i++){
        cur=a[i];
        if(cur==prev+1){ prev=cur; continue }
        if(start==prev) out = out (out? ",":"") start;
        else out = out (out? ",":"") start "-" prev;
        start=cur; prev=cur;
      }
      if(start==prev) out = out (out? ",":"") start;
      else out = out (out? ",":"") start "-" prev;
      print out;
    }'
}

HOUSE_ALL_LIST="$(node_all_cpus "${HOUSE_NODE}")"
GUIDE_PRIMARY_LIST="$(node_primary_cpus "${GUIDE_NODE}")"
VLLM_PRIMARY_LIST="$(node_primary_cpus "${VLLM_NODE}")"

HOUSE_CPUS="$(to_ranges "${HOUSE_ALL_LIST}")"
GUIDE_CPUS="$(to_ranges "${GUIDE_PRIMARY_LIST}")"
VLLM_CPUS="$(to_ranges "${VLLM_PRIMARY_LIST}")"

ISOL_LIST="$(printf "%s,%s\n" "${GUIDE_PRIMARY_LIST}" "${VLLM_PRIMARY_LIST}" \
  | tr ',' '\n' | grep -E '^[0-9]+$' | sort -n | uniq | tr '\n' ',' | sed 's/,$//')"
ISOL_CPUS="$(to_ranges "${ISOL_LIST}")"

echo "==> Detected NUMA nodes:"
echo "${NODES}" | sed 's/^/    /'
echo "==> Selected:"
echo "    Housekeeping node: ${HOUSE_NODE}  CPUs(all threads): ${HOUSE_CPUS}"
echo "    guidellm node:     ${GUIDE_NODE}  CPUs(primary):     ${GUIDE_CPUS}"
echo "    vLLM node:         ${VLLM_NODE}  CPUs(primary):     ${VLLM_CPUS}"
echo "    Isolated CPUs:     ${ISOL_CPUS}"
echo

# Build kernel cmdline
CMDLINE_ISOLATION="isolcpus=managed_irq,domain,${ISOL_CPUS} nohz_full=${ISOL_CPUS} rcu_nocbs=${ISOL_CPUS} irqaffinity=${HOUSE_CPUS} intel_pstate=disable cpufreq.default_governor=performance"

if (( DO_PREEMPT_FULL )); then
  CMDLINE_PREEMPT="preempt=full"
else
  CMDLINE_PREEMPT=""
fi

# -------- Check mode --------
if [[ "$MODE" == "check" ]]; then
  echo "==> CHECK MODE: verifying current system matches expected configuration"
  echo

  echo "[Kernel cmdline]"
  CMDLINE="$(cat /proc/cmdline)"
  echo "  /proc/cmdline: ${CMDLINE}"
  echo

  echo "[Isolated CPUs]"
  echo "  expected: ${ISOL_CPUS}"
  echo "  actual  : $(cat /sys/devices/system/cpu/isolated 2>/dev/null || echo '<none>')"
  echo

  echo "[nohz_full]"
  echo "  expected: ${ISOL_CPUS}"
  echo "  actual  : $(cat /sys/devices/system/cpu/nohz_full 2>/dev/null || echo '<none>')"
  echo

  echo "[IRQ balance]"
  systemctl is-enabled irqbalance >/dev/null 2>&1 && echo "  irqbalance: enabled (BAD)" || echo "  irqbalance: disabled (OK)"
  echo

  echo "[Preemption mode]"
  if (( DO_PREEMPT_FULL )); then
    echo "  expected: preempt=full"
  else
    echo "  expected: default (voluntary or none, not full)"
  fi
  PREEMPT="$(cat /proc/cmdline | tr ' ' '\n' | grep '^preempt=' || echo '<none>')"
  echo "  actual  : ${PREEMPT}"
  echo

  echo "[CPU Frequency Governor]"
  echo "  expected: performance"
  if command -v cpupower >/dev/null 2>&1; then
    echo "  current governors:"
    cpupower frequency-info -o 2>/dev/null | grep 'current policy' | head -3 | sed 's/^/    /' || echo "    (unable to query)"
  else
    echo "  cpupower not available"
  fi
  echo

  echo "[Tuned profile]"
  TUNED_PROFILE="$(tuned-adm active 2>/dev/null | awk '{print $NF}' || echo '<none>')"
  echo "  current: ${TUNED_PROFILE}"
  echo "  expected: vllm-benchmark (custom) or throughput-performance (fallback)"
  echo

  echo "[systemd AllowedCPUs]"
  systemctl show system.slice -p AllowedCPUs 2>/dev/null | sed 's/^/  /' || echo "  <unable to query>"
  systemctl show user.slice   -p AllowedCPUs 2>/dev/null | sed 's/^/  /' || echo "  <unable to query>"
  systemctl show init.scope   -p AllowedCPUs 2>/dev/null | sed 's/^/  /' || echo "  <unable to query>"
  echo

  echo "[NUMA balancing]"
  if [[ -f /proc/sys/kernel/numa_balancing ]]; then
    NUMA_BAL="$(cat /proc/sys/kernel/numa_balancing)"
    echo "  current: ${NUMA_BAL} (0=off is best for benchmarks)"
  fi
  echo

  echo "[THP defrag]"
  if [[ -f /sys/kernel/mm/transparent_hugepage/defrag ]]; then
    THP_DEFRAG="$(cat /sys/kernel/mm/transparent_hugepage/defrag)"
    echo "  current: ${THP_DEFRAG}"
    echo "  recommended: [never] for benchmark stability"
  fi
  echo

  echo "[Hot CPU activity on isolated CPUs]"
  echo "  Showing threads with >0.1% CPU on isolated CPUs:"
  ps -eLo pid,tid,psr,pcpu,comm --sort=-pcpu 2>/dev/null | awk -v cpus="${ISOL_LIST}" '
    BEGIN { split(cpus, arr, ","); for (i in arr) iso[arr[i]]=1 }
    NR>1 && ($3 in iso) && $4>0.1 {print}
  ' | head -n 30 || echo "  (unable to query)"
  echo
  echo "==> CHECK complete."
  exit 0
fi

# -------- Apply mode --------
echo "==> Installing tuning tools (tuned, kernel-tools, numactl)..."
sudo dnf -y install tuned kernel-tools numactl >/dev/null 2>&1 || true

echo "==> Disabling irqbalance (persistent)..."
if systemctl is-enabled irqbalance >/dev/null 2>&1; then
  sudo systemctl disable --now irqbalance >/dev/null 2>&1 || true
  echo "    Disabled irqbalance"
else
  echo "    irqbalance already disabled"
fi

echo "==> Creating persistent systemd CPU pinning drop-ins..."
sudo mkdir -p /etc/systemd/system/system.slice.d /etc/systemd/system/user.slice.d /etc/systemd/system/init.scope.d

NEEDS_RELOAD=0

if [[ ! -f /etc/systemd/system/system.slice.d/allowedcpus.conf ]] || \
   ! grep -q "AllowedCPUs=${HOUSE_CPUS}" /etc/systemd/system/system.slice.d/allowedcpus.conf 2>/dev/null; then
  sudo tee /etc/systemd/system/system.slice.d/allowedcpus.conf >/dev/null <<EOF
[Slice]
AllowedCPUs=${HOUSE_CPUS}
EOF
  echo "    Created/updated system.slice CPU pinning"
  NEEDS_RELOAD=1
else
  echo "    system.slice CPU pinning already configured"
fi

if [[ ! -f /etc/systemd/system/user.slice.d/allowedcpus.conf ]] || \
   ! grep -q "AllowedCPUs=${HOUSE_CPUS}" /etc/systemd/system/user.slice.d/allowedcpus.conf 2>/dev/null; then
  sudo tee /etc/systemd/system/user.slice.d/allowedcpus.conf >/dev/null <<EOF
[Slice]
AllowedCPUs=${HOUSE_CPUS}
EOF
  echo "    Created/updated user.slice CPU pinning"
  NEEDS_RELOAD=1
else
  echo "    user.slice CPU pinning already configured"
fi

if [[ ! -f /etc/systemd/system/init.scope.d/allowedcpus.conf ]] || \
   ! grep -q "AllowedCPUs=${HOUSE_CPUS}" /etc/systemd/system/init.scope.d/allowedcpus.conf 2>/dev/null; then
  sudo tee /etc/systemd/system/init.scope.d/allowedcpus.conf >/dev/null <<EOF
[Scope]
AllowedCPUs=${HOUSE_CPUS}
EOF
  echo "    Created/updated init.scope CPU pinning"
  NEEDS_RELOAD=1
else
  echo "    init.scope CPU pinning already configured"
fi

if (( NEEDS_RELOAD )); then
  sudo systemctl daemon-reload >/dev/null
fi

if (( DO_NUMA_BAL_OFF )); then
  echo "==> Disabling automatic NUMA balancing (persistent)..."
  if [[ ! -f /etc/sysctl.d/99-numa-benchmark.conf ]] || \
     ! grep -q "kernel.numa_balancing=0" /etc/sysctl.d/99-numa-benchmark.conf 2>/dev/null; then
    echo 'kernel.numa_balancing=0' | sudo tee /etc/sysctl.d/99-numa-benchmark.conf >/dev/null
    sudo sysctl -w kernel.numa_balancing=0 >/dev/null 2>&1 || true
    echo "    NUMA balancing disabled"
  else
    echo "    NUMA balancing already disabled in config"
  fi
fi

if (( DO_THP_DEFRAG )); then
  echo "==> Setting THP defrag to 'never' and installing a boot-time reapply unit..."

  CURRENT_THP="$(cat /sys/kernel/mm/transparent_hugepage/defrag 2>/dev/null | grep -o '\[.*\]' | tr -d '[]' || echo '')"
  if [[ "${CURRENT_THP}" != "never" ]]; then
    echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag >/dev/null
    echo "    Set THP defrag to 'never' (runtime)"
  else
    echo "    THP defrag already set to 'never'"
  fi

  if [[ ! -f /etc/systemd/system/thp-defrag-never.service ]]; then
    sudo tee /etc/systemd/system/thp-defrag-never.service >/dev/null <<'EOFSERVICE'
[Unit]
Description=Set THP defrag to never (benchmark determinism)
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/defrag'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOFSERVICE
    sudo systemctl daemon-reload >/dev/null
    sudo systemctl enable thp-defrag-never.service >/dev/null
    echo "    Created and enabled THP defrag service"
  else
    if ! systemctl is-enabled thp-defrag-never.service >/dev/null 2>&1; then
      sudo systemctl enable thp-defrag-never.service >/dev/null
      echo "    Enabled THP defrag service"
    else
      echo "    THP defrag service already configured"
    fi
  fi
fi

# -------- Configure via TUNED (proper way for RHEL-based systems) --------
echo "==> Creating custom tuned profile: vllm-benchmark..."

TUNED_PROFILE_DIR="/usr/lib/tuned/profiles/vllm-benchmark"
sudo mkdir -p "${TUNED_PROFILE_DIR}"

# Build the cmdline for tuned
TUNED_CMDLINE="${CMDLINE_ISOLATION}"
if [[ -n "${CMDLINE_PREEMPT}" ]]; then
  TUNED_CMDLINE="${TUNED_CMDLINE} ${CMDLINE_PREEMPT}"
  echo "    Including preempt=full (WARNING: may cause network instability)"
fi

# Create tuned profile
sudo tee "${TUNED_PROFILE_DIR}/tuned.conf" >/dev/null <<EOFTUNED
[main]
summary=vLLM benchmarking with CPU isolation
include=throughput-performance

[bootloader]
cmdline_vllm=${TUNED_CMDLINE}

[cpu]
governor=performance
EOFTUNED

echo "    Created tuned profile at ${TUNED_PROFILE_DIR}/tuned.conf"

# Restart tuned to pick up the new profile
echo "==> Restarting tuned to reload profiles..."
sudo systemctl restart tuned
sleep 1

# Check if profile needs to be applied
CURRENT_TUNED="$(tuned-adm active 2>/dev/null | awk '{print $NF}' || echo '')"
if [[ "${CURRENT_TUNED}" != "vllm-benchmark" ]]; then
  echo "==> Enabling tuned and applying vllm-benchmark profile..."
  sudo systemctl enable --now tuned >/dev/null 2>&1 || true
  sudo tuned-adm profile vllm-benchmark
  echo "    Applied tuned profile: vllm-benchmark"
  NEEDS_GRUB_UPDATE=1
else
  echo "==> Tuned profile vllm-benchmark already active"
  # Check if the profile content changed
  if ! grep -q "cmdline_vllm=${TUNED_CMDLINE}" "${TUNED_PROFILE_DIR}/tuned.conf" 2>/dev/null; then
    echo "    Profile content changed, reapplying..."
    sudo tuned-adm profile vllm-benchmark
    NEEDS_GRUB_UPDATE=1
  else
    NEEDS_GRUB_UPDATE=0
  fi
fi

# Regenerate grub config if needed
if (( NEEDS_GRUB_UPDATE )); then
  echo "==> Regenerating GRUB configuration..."
  if [[ -f /boot/grub2/grub.cfg ]]; then
    sudo grub2-mkconfig -o /boot/grub2/grub.cfg >/dev/null 2>&1 || echo "    WARNING: grub2-mkconfig failed"
  elif [[ -f /boot/efi/EFI/redhat/grub.cfg ]]; then
    sudo grub2-mkconfig -o /boot/efi/EFI/redhat/grub.cfg >/dev/null 2>&1 || echo "    WARNING: grub2-mkconfig failed"
  fi
  echo "    GRUB configuration updated"
fi

echo "==> Setting CPU frequency governor to performance (runtime)..."
if command -v cpupower >/dev/null 2>&1; then
  sudo cpupower frequency-set -g performance >/dev/null 2>&1 && \
    echo "    CPU governor set to performance" || \
    echo "    WARNING: Could not set governor (will be set on next boot)"
else
  echo "    cpupower not available; governor will be set on boot via tuned"
fi

echo
echo "============================================================"
echo "Configuration Summary:"
echo "------------------------------------------------------------"
echo "Kernel args configured (via tuned):"
echo "  isolcpus=managed_irq,domain,${ISOL_CPUS}"
echo "  nohz_full=${ISOL_CPUS}"
echo "  rcu_nocbs=${ISOL_CPUS}"
echo "  irqaffinity=${HOUSE_CPUS}"
echo "  intel_pstate=disable"
if (( DO_PREEMPT_FULL )); then
  echo "  preempt=full (WARNING: may cause network instability)"
else
  echo "  preempt=<not set> (using system default: voluntary)"
fi
echo
echo "Tuned profile: vllm-benchmark (includes governor=performance)"
echo "Systemd slices pinned to: ${HOUSE_CPUS}"
echo "irqbalance: disabled"
if (( DO_NUMA_BAL_OFF )); then
  echo "NUMA balancing: disabled"
fi
if (( DO_THP_DEFRAG )); then
  echo "THP defrag: never"
fi
echo "============================================================"
echo

if (( NEEDS_GRUB_UPDATE )); then
  echo "⚠️  REBOOT REQUIRED for kernel parameters to take effect!"
  echo
fi

# vLLM CPU: reserve 1 core by binding OMP threads to all-but-last CPU
VLLM_BIND="${VLLM_CPUS}"
if [[ "${VLLM_CPUS}" =~ ^([0-9]+)-([0-9]+)$ ]]; then
  start="${BASH_REMATCH[1]}"; end="${BASH_REMATCH[2]}"
  if (( end > start )); then
    VLLM_BIND="${start}-$((end-1))"
  fi
fi

cat <<EOF
Suggested container commands (RUN AFTER REBOOT):

1) vLLM (host networking; local NUMA memory; vLLM CPU thread binding; reserve 1 CPU)
sudo podman run --rm \\
  --security-opt seccomp=unconfined --cap-add SYS_NICE \\
  --network=host \\
  --shm-size=4g \\
  --cpuset-cpus=${VLLM_CPUS} \\
  --cpuset-mems=${VLLM_NODE} \\
  -e VLLM_CPU_KVCACHE_SPACE=40 \\
  -e VLLM_CPU_OMP_THREADS_BIND=${VLLM_BIND} \\
  -e HF_TOKEN=\$HF_TOKEN \\
  quay.io/mtahhan/vllm:0.14.0 \\
  TinyLlama/TinyLlama-1.1B-Chat-v0.6 \\
  --dtype=bfloat16 --no_enable_prefix_caching

2) guidellm (host networking; local NUMA memory; separate NUMA node)
sudo podman run --rm -it \\
  --network=host \\
  --cpuset-cpus=${GUIDE_CPUS} \\
  --cpuset-mems=${GUIDE_NODE} \\
  -v "/tmp/results:/results:z" \\
  -e GUIDELLM_TARGET=http://localhost:8000 \\
  -e GUIDELLM_PROFILE=sweep \\
  -e GUIDELLM_MAX_SECONDS=180 \\
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \\
  -e GUIDELLM_OUTPUTS="html,json,csv" \\
  -e HF_TOKEN=\$HF_TOKEN \\
  -e GUIDELLM_MAX_CONCURRENCY=196 \\
  ghcr.io/vllm-project/guidellm:latest

After reboot, validate configuration:
  cat /proc/cmdline | tr ' ' '\\n' | grep -E 'isolcpus|nohz|rcu|irq|pstate'
  cat /sys/devices/system/cpu/isolated
  cat /sys/devices/system/cpu/nohz_full
  systemctl show system.slice -p AllowedCPUs
  cpupower frequency-info | grep governor
  tuned-adm active
  $SCRIPT_NAME --check

To check configuration without making changes:
  $SCRIPT_NAME --check

Recommended usage for ML inference workloads:
  $SCRIPT_NAME --apply --numa-balancing-off --thp-defrag-never
  (omit --preempt-full for better stability)

Only use --preempt-full if you have hard real-time requirements (<100μs):
  $SCRIPT_NAME --apply --numa-balancing-off --thp-defrag-never --preempt-full
EOF
