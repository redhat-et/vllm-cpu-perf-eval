#!/usr/bin/env bash
set -euo pipefail

# setup-aws-metal.sh
# - Installs tuning tools
# - Detects NUMA topology + SMT siblings via lscpu
# - Chooses:
#     * Housekeeping CPUs = ALL CPUs on NUMA node 0 (both SMT threads)
#     * guidellm CPUs     = primary threads on NUMA node 1
#     * vLLM CPUs         = primary threads on NUMA node 2 (or last node)
#     * Isolated CPUs     = guidellm + vLLM primary threads
# - Configures kernel cmdline: isolcpus/nohz_full/rcu_nocbs/irqaffinity
# - Disables irqbalance
# - Pins systemd slices to housekeeping CPUs (persistent)
# - Enables tuned and sets throughput-performance
# - Optionally applies sysctls (numa_balancing=0)
# - Provides a --check mode to validate current config
# - Prints suggested podman commands (REMIND: reboot before running containers)

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<EOF
Usage:
  $SCRIPT_NAME [--apply] [--check] [--numa-balancing-off] [--thp-defrag-never]

Modes:
  --apply   Apply configuration (default if no mode specified)
  --check   Only check current configuration vs computed plan; do not change anything

Options:
  --numa-balancing-off   Persistently set kernel.numa_balancing=0
  --thp-defrag-never     Set THP defrag to 'never' (runtime) and install a systemd unit to reapply at boot

EOF
}

MODE="apply"
DO_NUMA_BAL_OFF=0
DO_THP_DEFRAG=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) MODE="apply"; shift ;;
    --check) MODE="check"; shift ;;
    --numa-balancing-off) DO_NUMA_BAL_OFF=1; shift ;;
    --thp-defrag-never) DO_THP_DEFRAG=1; shift ;;
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

if [[ "$MODE" == "apply" ]]; then
  if ! command -v grubby >/dev/null 2>&1; then
    echo "==> grubby not found; installing grubby..."
    sudo dnf -y install grubby >/dev/null
  fi
  require_cmd grubby
fi

# -------- Topology discovery --------
echo "==> Reading NUMA/CPU topology from lscpu..."

# Prefer numeric/no-header output if available, else strip header line.
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

KARGS_EXPECTED="isolcpus=managed_irq,domain,${ISOL_CPUS} nohz_full=${ISOL_CPUS} rcu_nocbs=${ISOL_CPUS} irqaffinity=${HOUSE_CPUS}"

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

  echo "[systemd AllowedCPUs]"
  systemctl show system.slice -p AllowedCPUs | sed 's/^/  /'
  systemctl show user.slice   -p AllowedCPUs | sed 's/^/  /'
  systemctl show init.scope   -p AllowedCPUs | sed 's/^/  /'
  echo

  echo "[Hot CPU activity on isolated CPUs]"
  echo "  Showing threads with >0.1% CPU on isolated CPUs:"
  ps -eLo pid,tid,psr,pcpu,comm --sort=-pcpu | awk '$3>=32 && $3<=95 && $4>0.1 {print}' | head -n 30 || true
  echo
  echo "==> CHECK complete."
  exit 0
fi

# -------- Apply mode --------
echo "==> Installing tuning tools (tuned, kernel-tools, numactl)..."
sudo dnf -y install tuned kernel-tools numactl >/dev/null

echo "==> Enabling tuned and setting profile..."
sudo systemctl enable --now tuned >/dev/null
sudo tuned-adm profile throughput-performance >/dev/null || true

echo "==> Disabling irqbalance (persistent)..."
sudo systemctl disable --now irqbalance >/dev/null 2>&1 || true

echo "==> Creating persistent systemd CPU pinning drop-ins..."
sudo mkdir -p /etc/systemd/system/system.slice.d /etc/systemd/system/user.slice.d /etc/systemd/system/init.scope.d

sudo tee /etc/systemd/system/system.slice.d/allowedcpus.conf >/dev/null <<EOF
[Slice]
AllowedCPUs=${HOUSE_CPUS}
EOF

sudo tee /etc/systemd/system/user.slice.d/allowedcpus.conf >/dev/null <<EOF
[Slice]
AllowedCPUs=${HOUSE_CPUS}
EOF

sudo tee /etc/systemd/system/init.scope.d/allowedcpus.conf >/dev/null <<EOF
[Scope]
AllowedCPUs=${HOUSE_CPUS}
EOF

sudo systemctl daemon-reload >/dev/null

if (( DO_NUMA_BAL_OFF )); then
  echo "==> Disabling automatic NUMA balancing (persistent)..."
  echo 'kernel.numa_balancing=0' | sudo tee /etc/sysctl.d/99-numa-benchmark.conf >/dev/null
  sudo sysctl --system >/dev/null
fi

if (( DO_THP_DEFRAG )); then
  echo "==> Setting THP defrag to 'never' and installing a boot-time reapply unit..."
  echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag >/dev/null

  sudo tee /etc/systemd/system/thp-defrag-never.service >/dev/null <<'EOF'
[Unit]
Description=Set THP defrag to never (benchmark determinism)
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/defrag'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload >/dev/null
  sudo systemctl enable thp-defrag-never.service >/dev/null
fi

echo "==> Updating kernel command line (ALL kernels) with CPU isolation + IRQ affinity..."
sudo grubby --update-kernel=ALL --args="${KARGS_EXPECTED}"

echo
echo "============================================================"
echo "Kernel args added:"
echo "  ${KARGS_EXPECTED}"
echo "============================================================"
echo
echo "IMPORTANT: You MUST reboot for kernel args + slice pinning to fully apply."
echo

# vLLM CPU: reserve 1 core by binding OMP threads to all-but-last CPU in the vLLM range
# This is done with vLLM's own env var (better than generic OMP_* guessing).
VLLM_BIND="${VLLM_CPUS}"
# If vLLM_CPUS is a single range like 64-95, bind 64-94 to reserve one CPU.
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

2) guiddllm (host networking; local NUMA memory; separate NUMA node)
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

After reboot, validate:
  cat /proc/cmdline | tr ' ' '\\n' | egrep 'isolcpus|nohz_full|rcu_nocbs|irqaffinity'
  cat /sys/devices/system/cpu/isolated
  cat /sys/devices/system/cpu/nohz_full
  systemctl show system.slice -p AllowedCPUs
  ps -eLo pid,tid,psr,pcpu,comm --sort=-pcpu | awk '\\$3>=32 && \\$3<=95 && \\$4>0.1 {print}' | head -n 30

To just check a new host without making changes:
  $SCRIPT_NAME --check
EOF
