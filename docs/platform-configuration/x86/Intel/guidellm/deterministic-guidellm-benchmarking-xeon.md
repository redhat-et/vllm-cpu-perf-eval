# Deterministic Benchmarking System Configuration
### Eliminating Scheduler, IRQ, and NUMA Noise on Bare-Metal Linux

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

## 2.5 Conceptual layout: deterministic single-host benchmarking

Even when only **one workload** is under test, the system **must still be**
**partitioned** to prevent OS and runtime noise from affecting results.
When using a local load generator, this partitioning becomes visible and explicit.

```sh
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
|    |   guiddllm container      |                                   |
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
- interrupts land on benchmark CPUs
- background services introduce jitter
- latency curves become unstable
- plateaus become noisy or disappear

The load generator container simply makes the partitioning visible —
the same tuning is required for **any deterministic single-container benchmark**.

> **Rule:** tune the system first, then run workloads.

---


The system is partitioned into two CPU classes:

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
```

### Example

```bash
sudo grubby --update-kernel=ALL --args="isolcpus=managed_irq,domain=32-95 nohz_full=32-95 rcu_nocbs=32-95 irqaffinity=0-31,96-127"
```

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

Enable tuned:

```bash
sudo systemctl enable --now tuned
sudo tuned-adm profile throughput-performance
```

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
- uses vLLM’s CPU binding control to **reserve 1 CPU** for the serving
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
  -e VLLM_CPU_OMP_THREADS_BIND=64-94 \
  -e HF_TOKEN=$HF_TOKEN \
  quay.io/mtahhan/vllm:0.14.0 \
  TinyLlama/TinyLlama-1.1B-Chat-v0.6 \
  --dtype=bfloat16 \
  --no_enable_prefix_caching
```

**Notes**
- Runs on its own NUMA node
- Memory is local to CPUs
- Host networking uses loopback for same-host traffic (no NIC interrupts)
- Reserving 1 CPU helps avoid frontend/inference contention

---

### guiddllm (Load generator, separate NUMA node)
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
  -e HF_TOKEN=$HF_TOKEN \
  ghcr.io/vllm-project/guidellm:latest
```

**Notes**
- Runs on a different NUMA node than vLLM
- Does not contend for caches or memory
- Increasing requests/time per sweep point reduces “end-point weirdness” near saturation
- Sweep curves will show a latency “knee” once capacity is exceeded (queueing)
- TO use the latest PR with the saturation patch for guidellm use:

```bash
sudo podman run --rm -it \
  --network=host \
  -v "/tmp/results:/results:z" \
  -e GUIDELLM_TARGET=http://localhost:8000 \
  -e GUIDELLM_PROFILE=sweep \
  -e GUIDELLM_MAX_SECONDS=600 \
  -e GUIDELLM_DATA="prompt_tokens=256,output_tokens=128" \
  -e GUIDELLM_OUTPUTS="html,json,csv" \
  -e GUIDELLM__MAX_CONCURRENCY=8 \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_TARGET=true \
  -e GUIDELLM__EXCLUDE_THROUGHPUT_RESULT=true \
  -e GUIDELLM__SATURATION_THRESHOLD=0.98 \
  quay.io/mtahhan/guidellm:saturation-fix
```

---

## 11. Automation script (apply + check mode)

Please see: [setup-platform.sh](../../../../../scripts/intel/setup-platform.sh) for quick system configuration.


Example usage:

```bash
./setup-platform.sh --apply --numa-balancing-off --thp-defrag-never
sudo reboot
./setup-platform.sh --check
```

---

## 12. Verification

After reboot, validate:

```bash
cat /proc/cmdline | tr ' ' '\n' | egrep 'isolcpus|nohz_full|rcu_nocbs|irqaffinity'
cat /sys/devices/system/cpu/isolated
cat /sys/devices/system/cpu/nohz_full
systemctl show system.slice -p AllowedCPUs
```

Check for unexpected CPU activity on isolated CPUs:

```bash
ps -eLo pid,tid,psr,pcpu,comm --sort=-pcpu | awk '$3>=32 && $3<=95 && $4>0.1 {print}' | head -n 30
```

---

## 13. Outcome

After applying these controls:

- Scheduler noise is eliminated
- IRQ noise is eliminated
- NUMA traffic is local
- Frequency is stable
- Benchmarks are more repeatable
- The system behaves like a dedicated appliance

This configuration is suitable for benchmarking, inference, HPC, and low-latency workloads.