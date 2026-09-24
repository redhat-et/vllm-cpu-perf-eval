# Proposal: CPU Power & Energy Metrics Collection (PCP + JouleIT)

Status: **Draft / Proposal** — not implemented

---

## 1. Motivation

Performance results today capture throughput and latency but not energy. For CPU
inference the interesting efficiency questions are:

| Metric | Unit | Definition |
| --- | --- | --- |
| Mean Power Consumption | W | Average socket power over the measurement window |
| Energy per token | J/token | Energy consumed divided by tokens processed |
| Tokens per Watt | token/J | Sustained throughput per unit power |
| Million-token cost | $/1M tokens | Marginal energy cost of one million tokens |

These are derived from two quantities: **energy over the run window** (to be collected)
and **token counts + timings** (already collected via `vllm-metrics.json` and
`benchmarks.json`).

**Policy:** We emit power and energy figures only when **real counters** (RAPL/`denki`,
optional BMC/RFchassis, or JouleIT on a wrapped run) are available and verified live.
We do **not** infer or model power on AWS, Graviton, virtualized guests, or any host where
probes fail — those runs record `power_mode: off` and omit derived efficiency metrics.

---

## 2. Why PCP and JouleIT (vs. a hand-rolled sampler)

Both are built on the same powerapi-ng / RAPL substrate, so their numbers agree, and both
cover the measurement paths we need. Choosing them removes a custom collector from our
maintenance surface and leans on Red Hat-supported tooling.

**PCP (Performance Co-Pilot)** — Red Hat's own framework, shipped in RHEL. Relevant
pieces already present in the source tree (v7.2.2 in this checkout):

- `pmdadenki` — electricity PMDA. Metrics:
  - `denki.rapl.sysfs` — cumulative Joules per RAPL domain (package / core / uncore /
    dram), read from `/sys/class/powercap`, **per-socket instances** (multi-NUMA aware).
  - `denki.rapl.msr` — cumulative Joules via MSR, domains incl. **`psys`** (platform power).
  - Rate-converted, these become **Watts** directly (`pmrep`, `pmval`).
- `pmdaperfevent` — optional Intel RAPL events (`RAPL:PACKAGE_ENERGY`,
  `RAPL:DRAM_ENERGY`, `THERMAL_SPEC`, `MINIMUM/MAXIMUM_POWER`).
- `pmdaopenmetrics` — scrape Prometheus-format endpoints into PCP (same archive as power).
- `pmlogger` — records a time-series archive per run; `pmrep` / `pmlogextract` render it.
  `pmdalinux` supplies CPU utilization + frequency (context for reports, not a power
  substitute); `tuned` integration for reproducible state.

**JouleIT (powerapi-ng)** — `sudo jouleit.sh <cmd>` wraps a command, samples RAPL for its
whole lifetime, and reports energy for CPU + DRAM (+ iGPU). Flags we use: `-g` (aggregate
sockets), `-s s0,s1` (select sockets), `-b` (KEY:VALUE energy out), `-n/-j` (repeat +
CSV). It is **process/run-scoped** — the natural tool for a bounded job and for
cross-checking PCP window integration on bare metal.

Summary of roles:

| Tool | Role |
| --- | --- |
| PCP `pmdadenki` + `pmlogger` | Continuous, time-aligned power source of record (server + load runs) |
| PCP `pmdaopenmetrics` | Co-log vLLM `/metrics` in the **same** archive as `denki` (time alignment) |
| PCP `pmdalinux` / `tuned` | Utilization + frequency context; reproducible state |
| PCP `process` PMDA | Per-process CPU time (attribution context, §5.8) — not a power source |
| JouleIT | Per-run energy for bounded workloads; optional validation of PCP windows |
| Redfish / BMC (via openmetrics or direct poll) | Whole-chassis PSU watts (system scope) |

**On Redfish / RFchassis:** PCP has **no native Redfish PMDA in this tree** (v7.2.2).
Chassis power is brought in via a Redfish→openmetrics bridge (e.g. `openmetrics.RFchassis`)
or direct Redfish poll. That is **whole-system input watts** — vendor-agnostic and the
closest thing to at-wall power without a meter — but **chassis-granularity** (no per-socket
/ per-process), often **slow to update**, and must be **sanity-checked** against RAPL (prior
lab archives have shown implausible RFchassis values). Not available in AWS (no BMC exposed).
Optional complement to `denki`, not a replacement.

**Post-test visualization:** Extend the existing **Streamlit** dashboard
(`dashboard-examples/vllm_dashboard/`) with a Power & Energy page that reads
`power-metrics.json` and optional `power-samples.json` from the result directory. Power
collection does **not** depend on Grafana/Prometheus; those remain optional for live vLLM
server metrics only (`docs/metrics-collection.md`).

### 2.1 Prior art: co-logging vLLM metrics and RAPL in one PCP archive

Red Hat experimented with recording **vLLM Prometheus metrics** and **RAPL energy** in a
single `pmlogger` archive (*vLLM, llama.cpp and PCP*, July 2025). The lesson for
this repo is:

**Problem:** Server throughput (`/metrics`) and socket energy (`denki`) live in different
tools today — our Ansible play already scrapes vLLM into `vllm-metrics.json` on the
controller, while RAPL must be read on the **same physical machine** that runs inference
(not from inside the vLLM container, and not from the load-generator host).

**What that work validated:** Point PCP's `pmdaopenmetrics` at vLLM's `/metrics` endpoint
and log `openmetrics.vllm` in the **same archive** as `denki.rapl`, so `pmrep` can correlate
watts and server counters on a shared timeline. vLLM exposes metrics at
`http://<dut>:8000/metrics` (same URL we use for the existing collector).

**What we adopt**

| Prior-art idea | Our use |
| --- | --- |
| One archive, two signal types | `power_collector` starts run-scoped `pmlogger` with `denki.rapl` + optional `openmetrics.vllm` (§5.3). |
| Run-bounded recording | Start archive after vLLM is up, stop after the benchmark — same window as §5.2, not 24/7 host logging. |
| Archive sanity check | `pmrep` on the saved archive in CI/smoke tests (§8). |

**What we do differently**

| Prior-art idea | Our choice |
| --- | --- |
| [PCPrecord-systemd](https://github.com/jharriga/PCPrecord_systemd) (always-on host recorder) | **Ansible `power_collector`** tied to benchmark plays — results land next to `benchmarks.json`. |
| Grafana for power + vLLM | **Streamlit** post-test only; no new Grafana datasources for energy. |
| Large default `pmlogger` recipe (RFchassis, `nvidia`, full htop set) | **Minimal default:** `denki.rapl` + `openmetrics.vllm` when enabled; optional extras (`hinv` once, RFchassis, GPU) behind flags — RFchassis is easy to misread and is not required for CPU J/token. |
| Modeled power on hosts without RAPL | **Not adopted** — `power_mode: off` only (§1). |

The concrete `pmlogger` config file is an implementation detail of the `power_collector`
role (not duplicated here); metric names must be validated on the target PCP version during
bring-up (§8).

---

## 3. Scope and non-goals

**In scope**

- Measure CPU + DRAM energy on **bare-metal x86** (Intel Xeon 6, AMD EPYC) via PCP
  (`pmdadenki`, optionally `pmdaperfevent`) and JouleIT. No external hardware required for
  silicon energy.
- Optional chassis power via Redfish/openmetrics when BMC is reachable and readings pass
  validation.
- Run PCP/`pmlogger` in a **dedicated collector container** on the inference machine
  (managed mode only) — **no `pcp` RPM install on the host OS** (see §5.10).
- Make collection a **first-class toggle** (on/off/auto) across Ansible, `cpueval`, and env.
- Emit power time-series + the four derived metrics into the existing results layout and
  the Streamlit dashboard when `power_mode: measured`.

**Out of scope (this proposal)**

- **Inferred or modeled power** when RAPL/BMC/JouleIT cannot provide real data (AWS
  virtualized, Graviton, static counters, etc.) — `power_mode: off`, no fabricated
  J/token or $/1M tokens.
- True at-wall energy at a hyperscaler (no rack/PDU access).
- GPU/accelerator power (may be logged if `nvidia` PMDA exists; not part of CPU efficiency
  metrics in phase 1).
- In-line meter / PDU / PowerSentry at-wall energy, or site-wide PCPrecord-systemd policies.
- Grafana dashboards or `pmproxy` for power (Streamlit only for this feature).

---

## 4. Key constraint: cloud vs bare metal (and AWS `.metal`)

Energy counters come from RAPL/`powercap`. Availability:

| Platform | Driver | Coverage |
| --- | --- | --- |
| Intel Xeon 6 | `intel_rapl_common` (sysfs) + MSR | package, core, uncore, dram, psys |
| AMD EPYC (Genoa/Turin) | `amd_rapl` (sysfs) | package, dram (package-only on older kernels) |
| AWS Graviton (incl. `.metal`) | none | none (ARM, no powercap) |
| AWS EC2 virtualized (Intel/AMD) | masked | none in-guest |
| AWS x86 `.metal` (i4i / m7i / hpc6a) | physical CPU, but AWS does not document/guarantee the energy MSRs | typically hidden/zeroed — **probe, do not assume** |

PCP makes the probe trivial and uniform: with the PMDA installed, `pminfo denki.rapl.sysfs`
either returns incrementing instances or it does not. JouleIT likewise aborts when no RAPL
domain is present. **Measured power is reported only when counters exist and tick**, regardless
of on-prem vs AWS `.metal`. Otherwise collection is **off** — not estimated.

| Target | `host_virt` (see §5.1) | `denki.rapl.sysfs` ticks? | Resulting mode |
| --- | --- | --- | --- |
| On-prem Xeon 6 / EPYC | `none` | yes | `measured` |
| AWS `.metal` x86 (counters tick) | `none` | yes | `measured` |
| AWS `.metal` x86 (static) | `none` | no | `off` |
| AWS Graviton (any) | `amazon` / `kvm` | no | `off` |
| AWS EC2 virtualized x86 | `amazon` / `kvm` | no | `off` |

---

## 5. Design

### 5.1 Capability probe + mode resolution

Run once per benchmark play (before starting collectors), **inside the collector container**
on the inference machine; sets `power_mode` and records it in `test-metadata.json`.
Skipped when `vllm_mode == external` (§5.10):

```text
1. collect_power == false                         -> off
2. pmdadenki available in collector image (not on host OS)
3. host_virt = systemd-detect-virt on inference host (Ansible fact, outside sidecar)
   container_virt = optional systemd-detect-virt inside collector (record only; not used for mode)
4. enumerate configured sysfs metrics (default: denki.rapl.sysfs):
     pminfo -f denki.rapl.sysfs  # instances present
     live = package instance J increases over ~200 ms busy spin in collector
5. if host_virt allows RAPL path and instances and live -> measured
   else                                               -> off (+ warning)
```

**Metric source (Phase 1 default):** `power_pcp_metrics` defaults to **`denki.rapl.sysfs` only**.
`denki.rapl.msr` / `psys` is opt-in (extra caps/devices); probe and `compute.yml` use only
metrics listed in `power_pcp_metrics`. Measured mode requires every configured sysfs domain
needed for reporting to pass the live check.

`power_force_measured=true` is **not** supported for emitting numbers when counters are
static — it may still run the collector for debugging, but derived metrics stay absent and
`power_mode` remains `off`.

### 5.2 Integration with a test run (Ansible / `cpueval`)

Power collection follows the same **start → benchmark → stop → post-process** pattern as
`vllm_metrics_collector`. RAPL is **not** visible inside the vLLM container; a separate
**power collector container** on the `vllm` inventory host reads host `powercap` via mounts
(§5.10). We do **not** install or configure PCP on the host operating system.

**Not supported:** `vllm_mode: external` — the playbook does not manage the inference
machine, so power collection is always `off` (latency/throughput metrics unchanged).

**Timeline (managed mode, concurrent load — e.g. `llm-benchmark-auto.yml`):**

```text
  localhost                    inference host (vllm group)              load_generator
       |                                |                                    |
       |-- start vLLM container -------->|                                    |
       |-- start power collector ctr --->|  pmlogger (denki + openmetrics)    |
       |-- start vllm_metrics (local) ---|-- scrape /metrics (HTTP)          |
       |                                |<----------- GuideLLM benchmark -----|
       |-- stop power collector ctr ---->|  archive -> volume bind           |
       |-- stop vllm_metrics ------------|                                    |
       |<-- fetch results dir -------------------------------------------------|
       |-- extract_benchmark_timings ----- (benchmarks.json)                  |
       |-- compute power metrics --------- power-samples.json, power-metrics.json
```

| Step | When | Actor | Output |
| --- | --- | --- | --- |
| Probe | Pre-benchmark; managed mode only | `power_collector` exec in collector container | `power_mode` fact |
| Start collector | After vLLM healthy, before GuideLLM | Podman on `vllm` host | Archive under mounted results path |
| Benchmark | Existing playbooks | load_generator + inference host | `benchmarks.json`, timings |
| Stop collector | `post_tasks` after benchmark | Podman on `vllm` host | Closed archive on results volume |
| Extract timings | Collect-results play | localhost | `benchmark_timings` in `test-metadata.json` |
| Extract + derive | After timings step | localhost or one-shot container exec | `power-samples.json`, `power-metrics.json` |
| Metadata merge | Collect-results / packaging | existing tasks | `test-metadata.json` `power` block |

**Hooks (proposed files):**

- `automation/test-execution/ansible/tasks/start-power-collection.yml`
- `automation/test-execution/ansible/tasks/stop-power-collection.yml`

Included from `llm-benchmark-auto.yml`, offline-batch suite plays, and other benchmarks when
`vllm_mode == managed` and `collect_power` is `auto` or `true`. Skipped when external mode,
when probe yields `off`, or when `collect_power=false` (no archive, no placeholder metrics).

**Offline / bounded workloads:** The benchmark command runs on the DUT (or wraps the whole
suite). Option A — PCP window only (same as server case). Option B — wrap the command with
JouleIT for a direct energy total; PCP archive still recommended for time alignment with
`openmetrics.vllm` if the server exposes `/metrics`.

**Result directory layout** (under existing `results/llm/<model>/<test-id>/<config>/`):

| File / dir | Description |
| --- | --- |
| `power-metrics.json` | Derived four metrics + windows + `power_mode: measured` |
| `power-samples.json` | Downsampled W and J series per socket/domain (and optional RFchassis) |
| `pcp/<archive>/` | Raw `pmlogger` archive (optional retention policy; needed for `pmrep` audits) |
| `test-metadata.json` | `power` block: mode, backend, sockets, scope, PUE, domains |

**Streamlit:** New page (e.g. `pages/7_⚡_Power_Energy.py`) loads `power-metrics.json` when
present; charts mean power and energy/token vs config; shows a clear banner when
`power_mode` is `off` or files are missing (cloud runs).

### 5.3 Continuous collection with PCP (source of record)

- Inside the collector container, configure `pmdaopenmetrics` with `vllm.url` pointing at
  the vLLM metrics URL reachable on the container network (e.g. host-published port or
  shared pod network — same reachability rules as §5.10).
- Start a **`pmlogger` archive scoped to the run** capturing metrics in `power_pcp_metrics`
  (default `denki.rapl.sysfs`), optional `openmetrics.vllm`, and `pmdalinux` util/frequency, at
  **1 s** for `openmetrics.vllm` where the role's `pmlogger` profile enables it.
- After the run, `pmlogextract`/`pmrep` over the archive produce `power-samples.json`
  (timestamped consistently with `vllm-metrics.json`), one series per domain per socket.
- Power = rate-converted energy (PCP reports cumulative J; deltas / Δt = W).
- No parallel Prometheus power exporter; no Grafana power panels.

### 5.4 Per-run energy with JouleIT (bounded workloads + validation)

- For workloads whose **process lifetime equals the measurement window**, optional JouleIT
  wrap inside the collector container (same image or tooling volume) —
  `jouleit.sh -b -s <sockets> <cmd>` → energy (J) for CPU/DRAM over that run.
- For the **server + external-client** case, use the PCP time-window method (§5.5). Optionally
  compare JouleIT session totals to PCP-integrated energy on calibration hosts.
- JouleIT is **not** used to synthesize power on hosts without RAPL.

### 5.5 Measurement window & attribution

Energy is integrated over **load windows** that match GuideLLM, not the full wall-clock span
of the Ansible play (server start, model load, idle gaps between rate steps).

**Window definition (per benchmark index `i`):**

```text
window_start = benchmark.start_time + benchmark.warmup_duration
window_end   = benchmark.end_time   - benchmark.cooldown_duration
```

**Window validation (before integrating E or Δt):** require `warmup_duration >= 0`,
`cooldown_duration >= 0`, and `window_start < window_end`. If not, skip that
`benchmark_index`, set `per_benchmark[].window_valid: false` with `window_skip_reason`, and
do not include it in roll-up efficiency metrics.

Use the same fields as `extract_benchmark_timings.py` reads from `benchmarks.json`
(`warmup_duration`, `cooldown_duration`, `start_time`, `end_time`). Do **not** assume a
fixed 30 s warmup — durations are per benchmark and come from GuideLLM config.

**Pipeline order (required):**

1. GuideLLM finishes → `benchmarks.json` exists.
2. `extract_benchmark_timings.py` updates `test-metadata.json` with `benchmark_timings`
   (see `llm-benchmark-auto.yml` collect-results play).
3. `power_collector` `compute.yml` runs — integrates PCP samples over each window above.
4. Merge summary fields into `test-metadata.json` `power` block.

`compute.yml` may read windows directly from `benchmarks.json` (same math as the extractor)
but must not run before `benchmarks.json` is written. Running after `extract_benchmark_timings.py`
keeps per-rate metadata and power breakdowns aligned.

**Multi-socket / NUMA:** PCP's per-socket instances plus our `cpuset_cpus` map let us sum
only the packages whose cores host the vLLM workers (power under test), while also
recording the all-socket total, so a tp1 run is not charged an idle socket's energy.

### 5.6 Deriving the four metrics

**Eligibility:** Top-level `power_mode: measured` only when the probe passed **and** every
requested benchmark window is `window_valid` with complete PCP samples for its interval
(§5.11). Otherwise `power_mode: off` or omit summary derived fields; per-window rows may
still carry `energy_joules` with `data_complete: false`.

**Domain energy (no double counting):** For each socket, integrate **one** primary silicon
total for headline metrics:

| Vendor | Include in socket total E | Do not sum together |
| --- | --- | --- |
| Intel (sysfs) | `package` energy per socket | `package` + `core` / `uncore` (children overlap package) |
| Intel (optional) | Report `dram` separately; add to E only when `sut_boundary` includes DRAM | `package` + `dram` both in E only when boundary says package+dram |
| AMD (sysfs) | `package` + `dram` when both instances exist | `package` + `core` |

Store per-domain J in `domains` for audit; roll-up E uses the non-overlapping rule above.

Join E, mean power (P̄), window Δt, and tokens (§5.9) for each complete window:

```text
Mean Power (W)   = E / Δt
Energy/token     = E / tokens                       # J/token
Tokens/W         = 1 / (energy_per_token)           # token/J
$/1M tokens      = (energy_per_token * 1e6 / 3.6e6) * PUE * price_per_kwh
```

**Optional hardware amortization (separate from energy cost):**

```text
hw_cost_per_million_tokens_usd = (hw_cost_per_hr / tokens_per_hr) * 1e6
```

Do not add this term inside the energy-based `$/1M tokens` formula unless explicitly
combined in a downstream cost report.

**Config validation (before cost metrics):** `power_pue` must be finite and `>= 1.0`.
When `power_price_per_kwh` is set, it must be finite and `>= 0`; otherwise skip
`cost_per_million_tokens_usd`. When unset, omit cost fields (JSON `null`).

**Cost metric:** Emit `cost_per_million_tokens_usd` only when price validation passes.
Default `power_pue: 1.0` is at-silicon energy; values `> 1` apply facility PUE on the
energy term only.

Output: `power-metrics.json` per run, plus a `power` block in `test-metadata.json`
recording `power_mode` (`measured` / `off`), backend used (`pcp-denki` / `pcp-perfevent` /
`jouleit` / `redfish`), the sockets/cores attributed, vendor, domains, PUE, price, and
`sut_boundary` — so every figure is auditable.

### 5.7 New Ansible role: `power_collector`

Mirrors `vllm_metrics_collector` lifecycle:

```text
automation/test-execution/ansible/roles/power_collector/
  defaults/main.yml   # collect_power, image, mounts, sockets, pue, price_per_kwh
  tasks/detect.yml    # start probe container / exec -> power_mode
  tasks/start.yml     # start collector container; pmlogger archive on results volume
  tasks/stop.yml      # stop container; pmlogextract -> power-samples.json
  tasks/compute.yml   # derive four metrics -> power-metrics.json + metadata block
```

Ansible on the **`vllm` group host** starts/stops the collector container (Podman, same as
vLLM). PCP runs **only inside that container**, not on the host OS and not in the vLLM
server container. Hooks slot in beside `tasks/start-vllm-metrics-collection.yml` / `stop-...`.

### 5.8 Attribution & topology (per-core power is not available)

RAPL/`powercap` granularity on Xeon 6 and EPYC is **per socket** (one package zone per
socket) plus in-socket aggregate domains (`core` = *all* cores summed, `uncore`, `dram`).
There is **no per-logical-core and no per-PID / per-cgroup energy**. JouleIT's `-s` selects
sockets, not cores, and PCP `denki.rapl.sysfs` instances are per socket/domain. So we cannot
carve out exactly "the cores vLLM is pinned to" unless that set equals a whole socket.

Consequence for running the load generator (guidellm) and vLLM on **one host**:

| Topology | Separable? | How |
| --- | --- | --- |
| Loadgen on a **separate host** (current `load_generator` group) | Yes | DUT package energy = power under test (clean) |
| Same host, **different sockets** (vLLM numa0 / guidellm numa1), vLLM socket otherwise idle | Yes | Report `socket-under-test` package energy |
| Same host, **same socket** shared | No | Not measurable — only a CPU-time-share estimate |
| Single-socket host (e.g. Graviton) | N/A | No RAPL in-guest anyway |

**Limitation (documented, not enforced):** measured energy is per-socket only, so it cannot
be attributed to a single process. "vLLM power" is only defensible when the load generator
does **not** share the measured socket — i.e. a separate loadgen host, or a disjoint-socket
split with the vLLM socket otherwise idle (recorded on the result as `power_scope`). When the
load generator shares the measured socket, the only honest outputs are the per-socket or
all-socket totals; a per-process split would just apportion by CPU-time share (a rough
estimate, not a measurement) and is out of scope here. Redfish is no help — it is
whole-chassis. This is recorded on every result rather than blocked.

Net: for a clean measured figure the load generator should be on a **separate DUT**, or on a
disjoint socket with the vLLM socket otherwise idle. Pinning cores and using `resctrl` /
`isolcpus` keeps housekeeping off the measured socket. These are preconditions we surface to
the user, not gates the tool enforces.

### 5.9 Token accounting (energy per token denominator)

| Rule | Detail |
| --- | --- |
| Primary token count | Tokens counted over the **same** `[window_start, window_end)` as energy (§5.5). Use GuideLLM fields that are scoped to the load phase only; if `benchmarks.json` only provides whole-step totals that include warmup/cooldown, do **not** compute `energy_per_token_j` for that index — set `token_window_mismatch: true` and emit energy-only for that slice. |
| Cross-check | When `vllm-metrics.json` is present, log server-side token counters for the overlapping interval; if client vs server totals diverge by more than a configured tolerance (e.g. 2%), set `power_metrics.token_source: client` and add `token_count_warning` in metadata — do **not** silently switch denominators. |
| Output-only variants | Optional derived field `energy_per_output_token` (J / generated tokens only) for reporting; default headline metric remains **all tokens processed** in the load window. |
| Zero tokens | If `tokens == 0` in a window, skip efficiency metrics for that window and record `energy_only: true` for that slice. |

### 5.10 Deployment: managed vs external, collector sidecar

| `vllm_mode` | Power collection | `power_mode` |
| --- | --- | --- |
| **Managed** | Power collector **sidecar** when `collect_power` auto/true | `measured` if RAPL probe passes |
| **External** | None — role not invoked | **`off`** always |

External runs still collect GuideLLM + optional `vllm-metrics.json` from `/metrics` when
exposed; they never claim energy or J/token.

**Power collector sidecar (managed mode only)**

| Concern | Approach |
| --- | --- |
| Image | Dedicated `power-collector` image (PCP + `pmdadenki` + `pmdaopenmetrics` + `pmlogger`/`pmrep` preconfigured). Version-pinned like `VLLM_CONTAINER_IMAGE`. |
| Runtime | Podman on `vllm` host (`containers.podman.podman_container`), lifecycle parallel to vLLM container. |
| RAPL access | Read-only bind-mount `/sys/class/powercap`. Optional MSR metrics: add `/dev/cpu` only when `power_pcp_metrics` includes `denki.rapl.msr`. |
| Security default | **Restricted:** read-only mounts, no host PID namespace, network only to vLLM `/metrics` (+ optional BMC). `CAP_SYS_ADMIN` not required for sysfs-only. `power_collector_privileged: false` by default. |
| Privileged exception | Set `power_collector_privileged: true` only when MSR or driver quirks require it; document in run metadata. |
| Results | Bind-mount the same host path used for benchmark `results_path` so archives and JSON land in the run directory. |
| vLLM `/metrics` | `pmdaopenmetrics` `vllm.url` uses a URL reachable **from inside the collector container** — e.g. `http://host.containers.internal:{{ vllm_port }}/metrics` or host network mode if required (match however vLLM publishes port today). |
| Host OS | **No** `dnf install pcp`, no `pmdadenki` Install on `$PCP_PMDAS_DIR` on the host. |

```text
  inference host (podman)
  ┌─────────────────────┐     ┌───────────────────────────┐
  │ vLLM container      │     │ power-collector container │
  │ (inference only)    │     │ pmcd + pmlogger + denki   │
  └──────────┬──────────┘     │ mounts: powercap, results │
             │ published      └─────────────┬─────────────┘
             │         /metrics scrape ─────┘ (openmetrics)
             └──────────────────────────────────────────────► host powercap (RAPL)
```

### 5.11 Prerequisites, privileges, and failure behavior

**Prerequisites on the `vllm` host (managed mode)**

- Podman (already required for managed vLLM).
- Collector image pulled or built once (`power_collector_image`).
- Bare-metal (or metal with live RAPL) — same probe rules as §4.

**Inside the collector container**

- `pmcd` + `pmlogger` started by container entrypoint for the run window.
- `pmdadenki` / `pmdaopenmetrics` baked into the image (not installed at playbook time on the host).

**Privileges**

- Collector uses the **restricted profile** in the sidecar table (§5.10); vLLM stays
  unprivileged. BMC/Redfish via env/vault — never in result JSON.

**Probe / toggle behavior**

| `collect_power` | Probe result | Playbook behavior |
| --- | --- | --- |
| `false` | — | Skip power role entirely |
| `auto` | fail | Warn; `power_mode: off`; benchmark continues |
| `true` | fail | Warn (or `power_collection_requested_but_unavailable: true` in metadata); benchmark **continues** — latency/throughput are not blocked |

**Collector failures mid-run**

- If `pmlogger` stops unexpectedly or any window lacks reconstructable samples: log error,
  set `power_collection_error` in metadata, save partial archive if possible, and set
  **`power_mode: off`** (or omit all summary derived metrics). Per-window entries may include
  partial `energy_joules` with `data_complete: false`. **Never** publish top-level
  `power_mode: measured` with incomplete roll-ups. **Do not** fail the benchmark play.
- Benchmark failure: still stop `pmlogger` in `always` block to avoid orphaned archives.

### 5.12 Playbook and workload coverage (Phase 1)

| Playbook / suite | Phase 1 hooks | Notes |
| --- | --- | --- |
| `llm-benchmark-auto.yml` | Yes | Primary concurrent-load path |
| `llm-benchmark.yml` | Yes | Manual config; same collect-results ordering |
| Offline batch suite (`run-offline-batch-suite.sh` / ansible) | Yes | JouleIT wrap optional |
| `audio-benchmark.yml` | Later | Phase 1 if trivial hook reuse; else Phase 2 |
| Embedding / MTEB sweeps | Later | Token semantics differ; Phase 2 |
| Core sweep (`is_core_sweep`) | Yes per config dir | One archive per `core_configuration.name` |

### 5.13 Dual server metrics paths (vLLM)

| Path | Collector | Interval | Role for power |
| --- | --- | --- | --- |
| `vllm-metrics.json` | `vllm_metrics_collector` on localhost → HTTP scrape | ~10 s | Existing Streamlit/server analysis; token cross-check |
| `openmetrics.vllm` in PCP archive | `pmdaopenmetrics` in collector container | 1 s | **Time-aligned** with `denki.rapl` in one archive for `pmrep` / audits |

Headline throughput/latency remain from GuideLLM + `vllm-metrics.json`. PCP openmetrics is
the source of record for **correlating watts with server counters** in post-mortem archive
review, not a replacement for the JSON scrape.

### 5.14 Time alignment and clocks

- GuideLLM `start_time` / `end_time` are ISO-8601 (load generator clock); PCP uses epoch
  seconds on the inference host. All conversions explicit (UTC).
- **Before integrating energy for a window:** `compute.yml` estimates clock offset between
  load_generator and `vllm` host (e.g. compare first benchmark `start_time` to archive
  start, bounded by `power_clock_max_skew_s`, default 2). Apply offset when mapping windows
  to PCP samples.
- If skew exceeds the bound: mark affected `per_benchmark` rows `clock_aligned: false`, skip
  derived metrics for those indices, and set `power_clock_error` in metadata. A warning alone
  is **not** sufficient to compute J/token on misaligned windows.
- `pmlogger` brackets the full multi-rate sweep (first `window_start` through last
  `window_end`).

### 5.15 MLflow (Phase 1 scope)

Phase 1: extend `log_to_mlflow.py` (optional post-run step, same as today) to log when
`power_mode == measured`:

- Params: `power_mode`, `power_scope`, `power_backend`, `energy_domains`
- Metrics: `mean_power_watts`, `energy_per_token_j`, `tokens_per_watt`, and
  `cost_per_million_tokens_usd` only if present in `power-metrics.json`

Skip MLflow power metrics entirely when `power_mode: off` (do not log zeros). Phase 2:
per-rate metrics keyed by `benchmark_index` / concurrency.

### 5.16 Streamlit scope (Phase 1 vs later)

- **Phase 1:** Single result directory — time series from `power-samples.json`, summary cards
  from `power-metrics.json`, banner when `off` or missing files; per-rate table when
  `benchmarks` array is present in `power-metrics.json`.
- **Phase 2:** Cross-run comparison (core sweep, TP sweep) — energy/token vs `core_count` /
  `tensor_parallel` from sibling dirs under a test run id (same pattern as other dashboard pages).

### 5.17 Result schemas (examples)

**`power-metrics.json` (illustrative):**

```json
{
  "power_mode": "measured",
  "token_source": "client",
  "sut_boundary": "socket-package-dram",
  "summary": {
    "mean_power_watts": 142.5,
    "total_energy_joules": 85420,
    "total_tokens": 1250000,
    "energy_per_token_j": 0.0683,
    "tokens_per_watt": 7.02,
    "cost_per_million_tokens_usd": null
  },
  "domains": {
    "socket0": { "package_j": 71200, "dram_j": 4200 }
  },
  "per_benchmark": [
    {
      "benchmark_index": 0,
      "rate": 16,
      "window_start": "2025-08-07T00:15:30.123Z",
      "window_end": "2025-08-07T00:18:45.456Z",
      "energy_joules": 22100,
      "tokens": 320000,
      "energy_per_token_j": 0.0691,
      "mean_power_watts": 138.2
    }
  ]
}
```

**`test-metadata.json` `power` block (illustrative):**

```json
{
  "power": {
    "power_mode": "measured",
    "power_backend": "pcp-denki",
    "power_scope": "socket-under-test",
    "sockets_attributed": ["0"],
    "domains": ["denki.rapl.sysfs"],
    "pue": 1.0,
    "price_per_kwh": null,
    "probe": { "host_virt": "none", "container_virt": "kvm", "denki_live": true }
  }
}
```

When `power_mode` is `off`, include a minimal block:

```json
{ "power": { "power_mode": "off", "reason": "denki counters not live" } }
```

---

## 6. Toggling collection on/off

| Surface | Example |
| --- | --- |
| Ansible extra-var | `-e collect_power=true` (values: auto / true / false) |
| `cpueval` CLI / suite yaml | `--collect-power` / a `collect_power:` field |
| Environment | `CPUEVAL_COLLECT_POWER` = auto / true / false |
| Image tag | `POWER_COLLECTOR_IMAGE` / `power_collector_image` Ansible var |

`auto` (default) runs the probe in §5.1. On AWS and other non-RAPL targets, `auto` yields
`off` with no derived power fields.

---

## 7. Packaging / availability

| Component | Where it lives | Notes |
| --- | --- | --- |
| **Power collector container image** | Built in-repo (Containerfile) or pulled from registry | Bundles PCP ≥ version with `pmdadenki` + `pmdaopenmetrics`; pin in CI |
| PCP (`pmcd`, `pmlogger`, `pmrep`) | Inside collector image only | Not installed on host OS |
| `pmdadenki` (RAPL energy) | Inside collector image | Validate on target CPU during image bring-up (§8) |
| `pmdaperfevent` RAPL (Intel) | Optional in image | Intel only |
| JouleIT (powerapi-ng) | Optional layer in collector image | Offline-batch cross-check only |
| Redfish/BMC power | Optional in collector image | whole-chassis; validate vs RAPL |

Host needs Podman only; no `pcp` RPM on the inference machine.

---

## 8. Verification items (to close before Phase 1 merge)

1. **AMD EPYC enumeration** — confirm `pmdadenki` sysfs picks up `amd_rapl` package + dram
   instances (its MSR path and `pmdaperfevent` RAPL are Intel-only). If it only matches
   `intel-rapl*`, EPYC needs a newer PCP or a small PMDA tweak.
2. **RHEL PCP version** — confirm the distro `pcp` includes `pmdadenki` and `pmdaopenmetrics`;
   otherwise pin a build.
3. **Sampling resolution & RAPL deltas (Phase 1 requirement for `compute.yml`):** 1 s
   `pmlogger` interval; integrate energy with **modular 32-bit wrap** on counter deltas;
   treat unexpected decreases (reset, rebind, gap) as invalid intervals — skip or mark
   `data_complete: false` so mean power never goes negative; do not emit measured roll-ups
   built from invalid intervals.
4. `psys` availability on the target Xeon 6 (MSR path).
5. **Redfish / RFchassis** — confirm BMC exposes usable power metrics; compare archive
   `openmetrics.RFchassis` to `denki.rapl` (reject or flag outliers).
6. **Archive cross-check** — `pmrep --ignore-incompat -a` on a smoke archive; `openmetrics.vllm`
   present and overlapping benchmark window.

---

## 9. Accuracy caveats to record on every result

- At-silicon (CPU+DRAM) vs at-wall (× PUE, or RFchassis) — state which is reported; Intel
  `psys` (MSR) is the closest on-die wall proxy.
- AMD package-only on older kernels (DRAM energy missing).
- JouleIT reports energy over the **whole selected socket(s)** for the wrapped command's
  lifetime, not a single PID's threads — attribute accordingly.
- 1 s sampling averages power; per-token energy over short windows is a window average.
- **No per-core / per-PID energy** — only per-socket (+ aggregate core/uncore/dram). If the
  load gen shares vLLM's socket, report per-socket/all-socket totals only (§5.8).
- **No inferred power** — missing counters ⇒ `power_mode: off`, not modeled values.

---

## 10. Deliverables / phases

- **Phase 1 (this proposal):** `power-collector` container image + `power_collector` role
  (Podman sidecar, no host PCP) with `pmdadenki` + run-scoped `pmlogger` (with
  `openmetrics.vllm` when metrics are enabled), managed mode only;
  JouleIT wrapper for offline-batch optional validation, the four metrics when measured,
  toggle across Ansible/CLI/env, Streamlit Power & Energy page (§5.16), MLflow fields when
  measured (§5.15), collect-results pipeline ordering (§5.5), attribution limitation
  documented on results (§5.8).
- **Phase 2:** multi-socket/NUMA attribution polish; reproducibility pinning (`tuned`,
  governor); optional RFchassis with automated sanity checks vs RAPL.

---

## 11. Configuration reference (proposed defaults)

```yaml
collect_power: auto                 # auto | true | false
power_backend: pcp                  # pcp | jouleit | pcp+jouleit
power_pcp_metrics: [denki.rapl.sysfs]   # append denki.rapl.msr only with MSR caps/mounts
power_pcp_interval_s: 1
power_log_openmetrics_vllm: true    # pmdaopenmetrics vllm.url when /metrics available
power_sockets: auto                 # auto (socket-under-test) | all | comma list for jouleit -s
power_scope: socket-under-test      # socket-under-test | all-sockets
power_pue: 1.0                      # 1.0 == at-silicon; >1 for at-wall
power_price_per_kwh: null           # required to emit $/1M tokens
power_redfish: false                # also collect BMC system power via openmetrics/Redfish
power_redfish_endpoint: null        # validated against denki when enabled
power_retain_pcp_archive: true      # keep pmlogger archive under results for pmrep audits
power_collector_image: null         # default: built tag from automation/test-execution/containers/power-collector
power_collector_privileged: false   # true only for MSR / platform-specific quirks
power_clock_max_skew_s: 2.0
power_token_mismatch_tolerance_pct: 2.0
```

---

## 12. Test plan

- Unit: window integration + metric math against synthetic energy/token samples; warmup/cooldown
  trimming matches `extract_benchmark_timings.py` fixtures.
- Integration: playbook order — `compute.yml` only after `benchmarks.json` and
  `extract_benchmark_timings.py` (§5.5).
- Bare-metal smoke: `pminfo -fT denki` shows incrementing domains; `power_mode=measured`;
  JouleIT energy on an offline-batch run is sane vs a known TDP ballpark; archive contains
  `openmetrics.vllm` when vLLM metrics are enabled; host-reachable `vllm.url` in container mode.
- EPYC probe: verify AMD package (and dram) instances per §8.1.
- Cloud smoke: probe reports `off`; metadata `power.power_mode: off` — never fake `measured`.
- External mode: `power_collector` skipped; `power_mode: off` in metadata.
- Failure: killed `pmlogger` mid-run → benchmark still succeeds; `power_mode: off`, no measured roll-up.
- RAPL wrap/reset fixtures: invalid intervals never produce negative W; clock skew beyond
  `power_clock_max_skew_s` skips J/token for affected windows.
- `collect_power=true` on host without RAPL → warning, benchmark continues.
- Attribution: separate-host run yields `measured`; same-host same-socket co-location is
  recorded with the documented per-socket/all-socket limitation (§5.8).
- Streamlit: power page renders measured run; off-state banner for cloud (§5.16).
- MLflow: optional log run includes power metrics when measured; absent when `off`.
- Regression: with `collect_power=false`, result layout and runtime unchanged.

---

## 13. Open questions

1. Default `power_backend` for online runs — PCP-only, or PCP continuous + JouleIT-on-batch?
2. Default `power_pue` / `price_per_kwh` source (per-datacenter config vs per-run override)?
3. `denki.rapl.msr` (psys) vs `denki.rapl.sysfs` (package+dram) as the reported default.
4. Collector image base (UBI + pinned `pcp` RPM) vs multi-stage copy from host — image must
   ship `pmdadenki` + EPYC validation (§8).
5. Minimum container caps: is `privileged` required on all platforms or sysfs-only mount enough?
6. Retain full PCP archives in every result tarball vs extract-only (`power_retain_pcp_archive`).
7. Same-host same-socket co-location — **resolved: documented as a limitation (§5.8), not
   enforced**; results record the per-socket/all-socket scope rather than being blocked.
8. Shared Python module for window extraction — import from `extract_benchmark_timings.py`
   vs duplicate logic inside `compute.yml` helper script.

---

Related: `docs/metrics-collection.md`, `automation/test-execution/ansible/roles/vllm_metrics_collector`,
`automation/test-execution/scripts/ansible/extract_benchmark_timings.py`,
`automation/test-execution/scripts/ansible/log_to_mlflow.py`,
`automation/test-execution/dashboard-examples/vllm_dashboard/`
