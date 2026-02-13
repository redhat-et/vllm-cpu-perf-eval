# Deterministic Benchmarking System Configuration

## Eliminating Scheduler, IRQ, and NUMA Noise on Bare-Metal Linux

This document describes a **generalized, repeatable approach** for configuring
a Linux system to run performance-sensitive workloads (benchmarks, inference,
HPC, real-time workloads) with minimal noise and maximum determinism.

It is intentionally **not tied to specific CPU numbers or instance types** so
it can be reused across environments (AWS metal, on-prem, lab systems, CI
performance runners).

Please see: [setup-platform.sh](../../../../../scripts/intel/setup-platform.sh)
for quick system configuration.

---

## 1. Goals

- Eliminate OS scheduler noise
- Eliminate interrupt (IRQ) and softirq noise
- Avoid NUMA cross-traffic
- Avoid SMT (hyperthreading) contention
- Stabilize CPU frequency
- Ensure repeatable, smooth benchmark results
- Make performance attributable only to the workload

---

## 2. High-level Strategy

---

## 2.5 Conceptual layout

### Deterministic dual-host benchmarking (Recommended)

When using multiple hosts, the guidellm system and system under test
**must still be partitioned** to prevent OS and runtime noise from
affecting results.

```text
+====================================================================+
|                    Load Generator Bare-Metal Host                  |
|                                                                    |
|  NUMA node 0 (Housekeeping)                                        |
|  ---------------------------------------------------------------   |
|  CPUs: housekeeping set                                            |
|  Memory: local to node 0                                           |
|                                                                    |
|    - kernel threads                                                |
|    - interrupts / softirqs                                         |
|    - systemd services                                              |
|    - ssh / logging / cron                                          |
|    - storage + networking stack                                    |
|                                                                    |
|  ---------------------------------------------------------------   |
|                                                                    |
|  NUMA node 1 (Load generator)                                      |
|  ---------------------------------------------------------------   |
|  CPUs: isolated set A                                              |
|  Memory: local to node 1                                           |
|                                                                    |
|    +---------------------------+                                   |
|    |   guidellm container      |                                   |
|    |   (load generation)       |                                   |
|    |   --cpuset-cpus=<A>       |                                   |
|    |   --cpuset-mems=1         |                                   |
|    |   --network=host          |                                   |
|    +---------------------------+                                   |
|                                                                    |
+====================================================================+
                                /\
                                ||
                                ||
                                ||
                                \/
+====================================================================+
|                      SUT Bare-Metal Host                           |
|                                                                    |
|  NUMA node 0 (Housekeeping)                                        |
|  ---------------------------------------------------------------   |
|  CPUs: housekeeping set                                            |
|  Memory: local to node 0                                           |
|                                                                    |
|    - kernel threads                                                |
|    - interrupts / softirqs                                         |
|    - systemd services                                              |
|    - ssh / logging / cron                                          |
|    - storage + networking stack                                    |
|                                                                    |
|  ---------------------------------------------------------------   |
|                                                                    |
|  NUMA node 1 (System under test)                                   |
|  ---------------------------------------------------------------   |
|  CPUs: isolated set A                                              |
|  Memory: local to node 1                                           |
|                                                                    |
|    +---------------------------+                                   |
|    |   vLLM container          |                                   |
|    |   (inference server)      |                                   |
|    |   --cpuset-cpus=<B>       |                                   |
|    |   --cpuset-mems=2         |                                   |
|    |   --network=host          |                                   |
|    +---------------------------+                                   |
|                                                                    |
+====================================================================+
```

### Deterministic single-host benchmarking

Even when only **one workload** is under test, the system **must still be**
**partitioned** to prevent OS and runtime noise from affecting results.
When using a local load generator, this partitioning becomes visible and explicit.

```text
+====================================================================+
|                            Single Bare-Metal Host                  |
|                                                                    |
|  NUMA node 0 (Housekeeping)                                        |
|  ---------------------------------------------------------------   |
|  CPUs: housekeeping set                                            |
|  Memory: local to node 0                                           |
|                                                                    |
|    - kernel threads                                                |
|    - interrupts / softirqs                                         |
|    - systemd services                                              |
|    - ssh / logging / cron                                          |
|    - storage + networking stack                                    |
|                                                                    |
|  ---------------------------------------------------------------   |
|                                                                    |
|  NUMA node 1 (Load generator)                                      |
|  ---------------------------------------------------------------   |
|  CPUs: isolated set A                                              |
|  Memory: local to node 1                                           |
|                                                                    |
|    +---------------------------+                                   |
|    |   guidellm container      |                                   |
|    |   (load generation)       |                                   |
|    |   --cpuset-cpus=<A>       |                                   |
|    |   --cpuset-mems=1         |                                   |
|    |   --network=host          |                                   |
|    +---------------------------+                                   |
|                                                                    |
|  ---------------------------------------------------------------   |
|                                                                    |
|  NUMA node 2 (System under test)                                   |
|  ---------------------------------------------------------------   |
|  CPUs: isolated set B                                              |
|  Memory: local to node 2                                           |
|                                                                    |
|    +---------------------------+                                   |
|    |   vLLM container          |                                   |
|    |   (inference server)      |                                   |
|    |   --cpuset-cpus=<B>       |                                   |
|    |   --cpuset-mems=2         |                                   |
|    |   --network=host          |                                   |
|    +---------------------------+                                   |
|                                                                    |
+====================================================================+
```

### Important: determinism is a system property

This isolation model **must be applied even if only the system under test is**
**running**.

If isolation is skipped:

- kernel work competes with the workload
- interrupts land on benchmark or workload CPUs
- background services introduce jitter
- latency curves become unstable
- plateaus become noisy or disappear

> **Rule:** tune the system first, then run workloads.

### CPU partitioning

The systems are partitioned into two CPU classes:

### Housekeeping CPUs

Used exclusively for:

- Kernel housekeeping
- Interrupts
- Networking and storage
- systemd services
- SSH, logging, monitoring, cron

### Isolated CPUs

Used exclusively for:

- Benchmarks
- Inference workloads
- Performance-critical containers

Workloads are placed on **dedicated NUMA nodes**, with both CPU and memory pinned.

---

## 3. Kernel-level CPU Isolation (Boot-time)

Kernel isolation ensures that the OS cannot interfere with benchmark CPUs.

### Required kernel parameters

```bash
isolcpus=managed_irq,domain,<isolated-cpu-list>
nohz_full=<isolated-cpu-list>
rcu_nocbs=<isolated-cpu-list>
irqaffinity=<housekeeping-cpu-list>
intel_pstate=disable
cpufreq.default_governor=performance
```

### Guidellm preempt=full configuration

```bash
preempt=full
```

**Note on preempt=full:** This parameter is for **Guidellm** only.
For workloads like ML inference, HPC, or batch processing, **omit**
**this parameter** to use the system default (typically `preempt=voluntary`),
which provides better stability without measurable performance impact for
millisecond-scale workloads.

### Parameter Explanations

**Core isolation parameters (required):**

- **isolcpus=managed_irq,domain,\<list\>**: Isolates CPUs from scheduler
  and managed IRQs
- **nohz_full=\<list\>**: Disables scheduling-clock tick on isolated CPUs
  when only one task is runnable
- **rcu_nocbs=\<list\>**: Offloads RCU callbacks from isolated CPUs to
  housekeeping CPUs
- **irqaffinity=\<list\>**: Pins all IRQs to housekeeping CPUs by default

**CPU frequency control parameters (required):**

- **intel_pstate=disable**: Disables Intel P-State driver, allowing use of
  acpi-cpufreq for more direct frequency control
- **cpufreq.default_governor=performance**: Sets CPU frequency governor to
  performance mode at boot

**Preemption parameter (Guidellm only):**

- **preempt=full**: Enables full kernel preemption for accurate
  timing measurements.

### Why CPU Frequency Governor Matters

The CPU frequency governor controls how the kernel adjusts CPU frequency:

- **powersave/schedutil** (common defaults): Dynamically adjust frequency
  based on load, causing performance variability
- **performance**: Locks CPUs at maximum frequency for consistent,
  repeatable benchmark results

Without setting the governor to performance:

- Benchmark results will vary between runs
- CPU frequency throttling introduces unpredictable latency
- Throughput measurements become unreliable
- Performance attribution becomes impossible

### Example Configuration

**Using the automation script (recommended):**

For ML inference, HPC, and general deterministic workloads:

```bash
./setup-platform.sh --apply --numa-balancing-off --thp-defrag-never
sudo reboot
```

Only if you have hard real-time requirements (<100μs latency):

```bash
./setup-platform.sh --apply --numa-balancing-off --thp-defrag-never --preempt-full
sudo reboot
```

**Manual configuration (if not using the script):**

The script uses tuned to manage kernel parameters, which is the recommended
approach for RHEL/CentOS/Fedora systems. If you need to configure manually:

For ML inference, HPC, and general deterministic workloads:

```bash
sudo grubby --update-kernel=ALL \
  --args="isolcpus=managed_irq,domain,32-95 nohz_full=32-95 \
  rcu_nocbs=32-95 irqaffinity=0-31,96-127 \
  intel_pstate=disable cpufreq.default_governor=performance"
```

Only if you have hard real-time requirements (<100μs latency):

```bash
sudo grubby --update-kernel=ALL \
  --args="isolcpus=managed_irq,domain,32-95 nohz_full=32-95 \
  rcu_nocbs=32-95 irqaffinity=0-31,96-127 \
  intel_pstate=disable cpufreq.default_governor=performance"

sudo grubby --update-kernel=ALL \
  --remove-args="preempt=none preempt=voluntary preempt=full" \
  --args="preempt=full"
```

**Note:** The automation script creates a custom tuned profile
(`vllm-benchmark`) that properly integrates with the system's tuning framework.
This is preferred over direct grubby commands as it ensures proper interaction
with other system tuning mechanisms. The CPU isolation parameters (`isolcpus`,
`nohz_full`, `rcu_nocbs`) provide the primary performance benefits, while
omitting `preempt=full` avoids potential network instability on bare-metal
hardware.

---

## 4. NUMA-aware CPU Partitioning

Discover topology:

```bash
lscpu -e=CPU,NODE,CORE
numactl -H
```

Rules:

- One workload per NUMA node
- No cross-node memory
- One SMT thread per physical core (recommended for stable benchmarking)
- Pin memory with CPUs

---

## 5. systemd Userland Isolation

Pin system slices to housekeeping CPUs:

```bash
sudo mkdir -p /etc/systemd/system/system.slice.d
sudo tee /etc/systemd/system/system.slice.d/allowedcpus.conf <<EOF
[Slice]
AllowedCPUs=<housekeeping-cpu-list>
EOF
```

Repeat for `user.slice` and `init.scope`, then:

```bash
sudo systemctl daemon-reload
```

---

## 6. Interrupt Noise Elimination

Disable irqbalance:

```bash
sudo systemctl disable --now irqbalance
```

Verify IRQ affinity:

```bash
grep . /proc/irq/*/smp_affinity_list | head
```

---

## 7. Frequency Stability

### Enable tuned for system-wide performance profile

```bash
sudo systemctl enable --now tuned
sudo tuned-adm profile throughput-performance
```

### Set CPU frequency governor (runtime)

The kernel parameters set the default governor at boot, but you can also
apply it immediately at runtime:

```bash
sudo dnf install -y kernel-tools  # Provides cpupower
sudo cpupower frequency-set -g performance
```

### Verify CPU frequency governor

```bash
cpupower frequency-info | grep governor
```

All CPUs should show "performance" as the current policy governor.

---

## 8. Optional runtime determinism knobs

These are not strictly required for CPU isolation, but often improve run-to-run
stability.

### Disable automatic NUMA page balancing (persistent)

```bash
echo 'kernel.numa_balancing=0' | sudo tee /etc/sysctl.d/99-numa-benchmark.conf
sudo sysctl --system
```

### Disable THP defrag (persistent)

```bash
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
```

To make this persistent across reboots, create a systemd service:

```bash
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

sudo systemctl daemon-reload
sudo systemctl enable thp-defrag-never.service
```

(Optionally disable THP entirely for maximum determinism, depending on workload.)

---

## 9. Host networking between containers (recommended for same-host benchmarks)

When the load generator and server run on the **same host**, run **both**
**containers with host networking** and target the server via `localhost`.

Why:

- Avoids veth/bridge/NAT overhead
- Minimizes jitter from container networking layers
- Uses Linux loopback for intra-host traffic (no NIC interrupts)

Notes:

- When using `--network=host`, **do not** use `-p` port mappings.
- `GUIDELLM_TARGET` should be `http://localhost:<port>`.

---

## 10. Container CPU + Memory Pinning (FULL EXAMPLES)

### vLLM (Inference workload, dedicated NUMA node)

This example:

- pins vLLM to a dedicated CPU set and NUMA memory node
- uses vLLM's CPU binding control to **reserve 1 CPU** for the serving
  framework (reduces oversubscription)

```bash
# If using a model that requires a hugging face token make sure to export it
export HF_TOKEN=<hf_token>
sudo podman run --rm \
  --security-opt seccomp=unconfined \
  --cap-add SYS_NICE \
  --network=host \
  --shm-size=4g \
  --cpuset-cpus=64-95 \
  --cpuset-mems=2 \
  -e VLLM_CPU_KVCACHE_SPACE=40 \
  -e VLLM_CPU_NUM_OF_RESERVED_CPU=1 \
  -e VLLM_CPU_OMP_THREADS_BIND=64-94 \
  -e HF_TOKEN=$HF_TOKEN \
  <vllm-cpu-container-image> \
  TinyLlama/TinyLlama-1.1B-Chat-v0.6 \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

#### vLLM Notes

- Runs on its own NUMA node
- Memory is local to CPUs
- Host networking uses loopback for same-host traffic (no NIC interrupts)
- Reserving 1 CPU helps avoid frontend/inference contention

---

### guidellm (Load generator, separate NUMA node)

```bash
mkdir -p /tmp/results
chmod 777 /tmp/results
# If using a model that requires a hugging face token make sure to export it
export HF_TOKEN=<hf_token>
sudo podman run --rm -it \
  --network=host \
  --cpuset-cpus=32-63 \
  --cpuset-mems=1 \
  -v "/tmp/results:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_MAX_REQUESTS=2000 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  -e HF_TOKEN=$HF_TOKEN \
  <vllm-cpu-container-image>
```

#### guidellm Notes

- Runs on a different NUMA node than vLLM
- Does not contend for caches or memory
- Increasing requests/time per sweep point reduces "end-point weirdness"
  near saturation
- Sweep curves will show a latency "knee" once capacity is exceeded (queueing)

**Note**: The main example above already uses the recommended guidellm
saturation-fix image with proper saturation detection settings.

---

## 11. Automation script (apply + check mode)

Please see:
[setup-guidellm-platform.sh](../../../../../hack/intel/setup-guidellm-platform.sh)
for quick system configuration.

### How the script works

The script uses **tuned** (the system tuning framework) to manage kernel
parameters. This is the recommended approach for RHEL/CentOS/Fedora systems
because:

1. **Proper integration**: tuned coordinates with other system services
2. **Persistent across updates**: Kernel updates won't lose your configuration
3. **Profile management**: Easy to switch between configurations
4. **Governor management**: Handles CPU frequency scaling properly

The script creates a custom profile at
`/usr/lib/tuned/profiles/vllm-benchmark/` that includes:

- Base profile: `throughput-performance`
- Custom kernel cmdline parameters (CPU isolation, NUMA, frequency)
- CPU governor: `performance`
- Optional: `preempt=full` (only with `--preempt-full` flag)

### Example usage

**Recommended for ML inference and general workloads:**

```bash
./setup-platform.sh --apply --numa-balancing-off --thp-defrag-never
sudo reboot
./setup-platform.sh --check
```

**Only for real-time workloads requiring <100μs latency:**

```bash
./setup-platform.sh --apply --numa-balancing-off --thp-defrag-never --preempt-full
sudo reboot
./setup-platform.sh --check
```

### What the script does

- Package installation (tuned, kernel-tools, numactl)
- NUMA topology detection and automatic CPU set calculation
- Custom tuned profile creation (`vllm-benchmark`)
- Kernel parameter configuration via tuned bootloader integration
- CPU frequency governor configuration
- systemd slice pinning (housekeeping CPUs)
- IRQ balancing configuration (disable irqbalance)
- Runtime governor application (immediate effect)
- GRUB configuration regeneration
- Idempotent execution (safe to run multiple times)
- Optional preempt=full via `--preempt-full` flag
  (recommended for Guidellm host)

---

## 12. Verification

After reboot, validate:

### Check kernel parameters

```bash
cat /proc/cmdline | tr ' ' '\n' | grep -E 'isolcpus|nohz|rcu|irq|pstate'
```

Note: `preempt` parameter should only appear if you explicitly enabled
`--preempt-full` (not recommended for most workloads).

### Check tuned profile

```bash
tuned-adm active
```

Expected output: `Current active profile: vllm-benchmark`

To view the profile configuration:

```bash
cat /usr/lib/tuned/profiles/vllm-benchmark/tuned.conf
```

### Check isolated CPU configuration

```bash
cat /sys/devices/system/cpu/isolated
cat /sys/devices/system/cpu/nohz_full
```

### Check systemd CPU pinning

```bash
systemctl show system.slice -p AllowedCPUs
systemctl show user.slice -p AllowedCPUs
systemctl show init.scope -p AllowedCPUs
```

### Check CPU frequency governor (CRITICAL)

```bash
cpupower frequency-info | grep governor
```

Expected output: All CPUs should show "performance" as the current governor.

### Check for unexpected CPU activity on isolated CPUs

```bash
ps -eLo pid,tid,psr,pcpu,comm --sort=-pcpu | \
  awk '$3>=32 && $3<=95 && $4>0.1 {print}' | head -n 30
```

### Check IRQ affinity

```bash
grep . /proc/irq/*/smp_affinity_list | grep -v "0-31,96-127" | head
```

Any IRQs not pinned to housekeeping CPUs should be investigated.

---

## 13. Outcome

After applying these controls:

- Scheduler noise is eliminated
- IRQ noise is eliminated
- NUMA traffic is local
- CPU frequency is stable and maximized
- Benchmarks are more repeatable
- The system behaves like a dedicated appliance
- Performance variability is minimized
- Results are attributable only to the workload

This configuration is suitable for benchmarking, inference, HPC, and
low-latency workloads.

---

## 15. References

- [Linux kernel CPU isolation documentation](https://www.kernel.org/doc/html/latest/admin-guide/kernel-per-CPU-kthreads.html)
- [RHEL Performance Tuning Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/monitoring_and_managing_system_status_and_performance/)
- [Tuned documentation](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/monitoring_and_managing_system_status_and_performance/getting-started-with-tuned_monitoring-and-managing-system-status-and-performance)
- [CPU frequency scaling governors](https://www.kernel.org/doc/Documentation/cpu-freq/governors.txt)
- [NUMA memory policy](https://www.kernel.org/doc/html/latest/admin-guide/mm/numa_memory_policy.html)
- [Real-time kernel preemption](https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html)
