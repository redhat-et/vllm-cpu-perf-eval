"""
Scale-Out Routing Analysis — per-backend metrics for llm-d (EPP + Envoy) deployments.

Expected layout (one directory per benchmark run):
  <results_dir>/
    test-metadata.json               — routing_policy, num_instances, model, …
    vllm-metrics-instance-1.json     — per-backend vLLM Prometheus data
    vllm-metrics-instance-N.json
    epp-metrics.json                 — EPP routing metrics (optional)
    benchmarks.json                  — guidellm client-side results (optional)

Compares per-backend load, prefix-cache hit rates, supports side-by-side
comparison of intelligent (EPP) vs round_robin routing runs with quantitative
deltas, and charts throughput/latency scaling across instance counts.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig  # noqa: E402

st.title("🔀 Scale-Out Routing Analysis")
st.caption(
    "Per-backend load distribution and routing policy comparison "
    "for llm-d (EPP + Envoy) deployments."
)

# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.header("Configuration")

config = DashboardConfig()
default_results_dir = config.get_results_directory()

results_dir = st.sidebar.text_input(
    "Results Directory",
    value=default_results_dir,
    help="Directory containing per-run result subdirectories",
    key="results_dir_scaleout",
)

if st.sidebar.button("💾 Save", key="save_scaleout"):
    config.set_results_directory(results_dir)
    st.sidebar.success("✓ Saved")

if st.sidebar.button("🔄 Reload Data", key="reload_scaleout"):
    st.cache_data.clear()
    st.rerun()

with st.sidebar.expander("ℹ️ Data Collection", expanded=False):
    st.markdown("""
**Enable per-instance metrics collection:**
```bash
-e "scaleout_collect_per_instance_metrics=true"
```
**SSH tunnel for live EPP metrics** (port 9091 avoids clash with Prometheus):
```bash
ssh -L 9091:localhost:9090 user@DUT
```
    """)

# ─── Data loading ────────────────────────────────────────────────────────────


@st.cache_data(ttl=30)
def find_scaleout_runs(base_dir: str) -> List[Dict]:
    """Find all scale-out run directories containing per-instance metrics."""
    runs = []
    base = Path(base_dir)
    if not base.exists():
        return runs

    for meta_file in base.rglob("test-metadata.json"):
        run_dir = meta_file.parent
        instance_files = sorted(run_dir.glob("vllm-metrics-instance-*.json"))
        if not instance_files:
            continue
        meta = {}
        meta_ok = True
        try:
            meta = json.loads(meta_file.read_text())
        except Exception:
            meta_ok = False
        policy = meta.get("routing_policy", "unknown")
        runs.append({
            "path": run_dir,
            "meta": meta,
            "meta_ok": meta_ok,
            "instance_files": instance_files,
            "epp_file": run_dir / "epp-metrics.json",
            "benchmarks_file": run_dir / "benchmarks.json",
            "label": f"{run_dir.name} ({policy})",
        })
    return runs


def load_instance_metrics(path: Path) -> Optional[Dict]:
    """Load a single vllm-metrics-instance-N.json file."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def extract_histogram_mean(data: Dict, metric: str) -> pd.DataFrame:
    """Compute per-sample mean for a Prometheus histogram (sum / count)."""
    rows = []
    for sample in data.get("samples", []):
        ts = sample.get("elapsed_seconds", 0)
        metrics = sample.get("metrics", {})
        s = sum(e["value"] for e in metrics.get(f"{metric}_sum", []))
        c = sum(e["value"] for e in metrics.get(f"{metric}_count", []))
        if c > 0:
            rows.append({"elapsed_s": ts, "value": s / c})
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=["elapsed_s", "value"])


def extract_series(data: Dict, metric: str) -> pd.DataFrame:
    """Extract a time-series for a Prometheus metric from vllm-metrics JSON."""
    rows = []
    for sample in data.get("samples", []):
        ts = sample.get("elapsed_seconds", 0)
        for entry in sample.get("metrics", {}).get(metric, []):
            rows.append({"elapsed_s": ts, "value": entry["value"]})
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=["elapsed_s", "value"])


BACKEND_COLORS = [
    "#4C9BE8", "#F5A623", "#7ED321", "#D0021B", "#9B59B6",
    "#1ABC9C", "#E67E22", "#2ECC71", "#E74C3C", "#3498DB",
]

KEY_METRICS = {
    "Running Requests": "vllm:num_requests_running",
    "Queued Requests": "vllm:num_requests_waiting",
    "KV Cache Utilisation (%)": "vllm:kv_cache_usage_perc",
    "CPU Cache Utilisation (%)": "vllm:cpu_cache_usage_perc",
    "Generation Throughput (tok/s)": "vllm:avg_generation_throughput_toks_per_s",
    "Completed Requests (cumulative)": "vllm:request_success_total",
}

# Primary metric name with optional fallbacks (GPU vs CPU vLLM builds differ)
METRIC_ALIASES = {
    "vllm:kv_cache_usage_perc": [
        "vllm:kv_cache_usage_perc",
        "vllm:gpu_cache_usage_perc",
    ],
}


def extract_series_with_aliases(data: dict, metric: str) -> pd.DataFrame:
    """Extract a time series, trying alias names when the primary is absent."""
    for name in METRIC_ALIASES.get(metric, [metric]):
        df = extract_series(data, name)
        if not df.empty:
            return df
    return pd.DataFrame(columns=["elapsed_s", "value"])


def load_client_results(run: Dict) -> Optional[pd.DataFrame]:
    """Parse a run's benchmarks.json into a client-side results DataFrame.

    Returns None when the file is absent, unreadable, or has no valid entries.
    """
    benchmarks_file = run.get("benchmarks_file")
    if not benchmarks_file or not benchmarks_file.exists():
        return None
    try:
        bench_data = json.loads(benchmarks_file.read_text())
    except Exception:
        return None

    client_rows = []
    for b in bench_data.get("benchmarks", []):
        cfg = b.get("config", {})
        m = b.get("metrics", {})
        strategy = cfg.get("strategy", {})
        conc = (
            strategy.get("streams")
            or strategy.get("max_concurrency")
            or strategy.get("worker_count")
        )
        ttft = m.get("time_to_first_token_ms", {}).get("successful", {})
        itl = m.get("inter_token_latency_ms", {}).get("successful", {})
        tps = m.get("tokens_per_second", {}).get("successful", {})
        if not tps.get("mean"):
            tps = m.get("output_tokens_per_second", {}).get("successful", {})
        rps = m.get("requests_per_second", {}).get("successful", {})
        if not ttft.get("mean"):
            continue
        client_rows.append({
            "Concurrency": conc,
            "TTFT mean (ms)": ttft.get("mean", 0),
            "TTFT P95 (ms)": (
                ttft.get("percentiles", {}).get("p95", 0)
            ),
            "ITL mean (ms)": itl.get("mean", 0),
            "ITL P95 (ms)": (
                itl.get("percentiles", {}).get("p95", 0)
            ),
            "Output TPS": tps.get("mean", 0),
            "RPS": rps.get("mean", 0),
        })

    if not client_rows:
        return None
    return pd.DataFrame(client_rows).sort_values("Concurrency")


def run_model_name(run: Dict) -> str:
    """Model identifier for a run (falls back across metadata key spellings)."""
    meta = run.get("meta", {})
    return str(meta.get("model_name") or meta.get("model") or "")


def extract_prefix_cache_hit_rate(data: dict) -> pd.DataFrame:
    """Prefix cache hit rate from gauges or hits/queries counters."""
    for gauge in (
        "vllm:cpu_prefix_cache_hit_rate",
        "vllm:gpu_prefix_cache_hit_rate",
    ):
        df = extract_series(data, gauge)
        if not df.empty:
            return df

    rows = []
    for sample in data.get("samples", []):
        ts = sample.get("elapsed_seconds", 0)
        metrics = sample.get("metrics", {})
        hits_list = metrics.get("vllm:prefix_cache_hits_total") or []
        queries_list = metrics.get("vllm:prefix_cache_queries_total") or []
        hits = hits_list[0].get("value", 0) if hits_list else 0
        queries = queries_list[0].get("value", 0) if queries_list else 0
        if queries and queries > 0:
            rows.append({"elapsed_s": ts, "value": hits / queries})
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=["elapsed_s", "value"])

# EPP metric names — collected from EPP :9090/metrics (llm_d_epp_* prefix)
EPP_POOL_METRICS = {
    "llm_d_epp_ready_endpoints": "Ready Endpoints",
    "llm_d_epp_average_kv_cache_utilization": "Avg KV Cache Utilisation",
    "llm_d_epp_average_queue_size": "Avg Queue Size",
    "llm_d_epp_average_running_requests": "Avg Running Requests",
    "llm_d_epp_std_dev_kv_cache_utilization": "KV Cache Std Dev",
    "llm_d_epp_std_dev_queue_size": "Queue Size Std Dev",
    "llm_d_epp_per_endpoint_queue_size": "Queue Size per Endpoint",
    "llm_d_epp_prefix_indexer_hit_ratio": "Prefix Cache Hit Ratio (EPP)",
    "llm_d_epp_request_total": "Requests Routed (total)",
    "llm_d_epp_scheduler_e2e_duration_seconds": "Scheduler E2E Latency",
}

# ─── Main ────────────────────────────────────────────────────────────────────

runs = find_scaleout_runs(results_dir)

if not runs:
    st.info(
        "No scale-out run data found. "
        "Run `start-vllm-scaleout.yml` with per-instance metrics collection, "
        "or point the results directory at a folder containing "
        "`vllm-metrics-instance-*.json` files alongside `test-metadata.json`."
    )
    st.stop()

# ─── Run selector ────────────────────────────────────────────────────────────

run_labels = [r["label"] for r in runs]
selected_label = st.selectbox("Select benchmark run", run_labels)
run = next(r for r in runs if r["label"] == selected_label)

meta = run["meta"]
if not run.get("meta_ok", True):
    st.warning(
        "Could not parse test-metadata.json for this run — "
        "metadata-derived fields (instances, policy, model) may be missing."
    )
col1, col2, col3, col4 = st.columns(4)
col1.metric("Instances", meta.get("num_instances", len(run["instance_files"])))
col2.metric("Routing Policy", meta.get("routing_policy", "—"))
col3.metric("Cores / Instance", meta.get("cores_per_instance", "—"))
model_display = meta.get("model_name") or meta.get("model") or "—"
col4.metric("Model", str(model_display).split("/")[-1])

st.divider()

# ─── Load per-instance data ───────────────────────────────────────────────────

instance_data = {}
for f in run["instance_files"]:
    try:
        idx = int(f.stem.rsplit("-", 1)[-1])
    except ValueError:
        idx = f.stem
    data = load_instance_metrics(f)
    if data:
        instance_data[idx] = data

if not instance_data:
    st.error("Could not load any per-instance metrics files.")
    st.stop()

instance_ids = sorted(instance_data.keys())

# ─── Metric selector ─────────────────────────────────────────────────────────

selected_display = st.selectbox(
    "Metric to compare across backends",
    list(KEY_METRICS.keys()),
    index=0,
)
selected_metric = KEY_METRICS[selected_display]

# ─── Per-backend time-series chart ───────────────────────────────────────────

st.subheader(f"📊 {selected_display} — all backends over time")

fig = go.Figure()
for i, idx in enumerate(instance_ids):
    df = extract_series_with_aliases(instance_data[idx], selected_metric)
    if df.empty:
        continue
    df["value"] = df["value"].rolling(3, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=df["elapsed_s"],
        y=df["value"],
        name=f"Backend {idx}",
        line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
        mode="lines",
    ))

if fig.data:
    fig.update_layout(
        xaxis_title="Elapsed (s)",
        yaxis_title=selected_display,
        legend_title="Backend",
        height=380,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(
        f"No data found for **{selected_display}** "
        f"(`{selected_metric}`) in this run."
    )

LATENCY_METRICS = {
    "vllm:time_to_first_token_seconds",
    "vllm:time_per_output_token_seconds",
}
is_latency = selected_metric in LATENCY_METRICS

# ─── Summary table ────────────────────────────────────────────────────────────

section_title = (
    "📦 Latency distribution — time-averaged"
    if is_latency
    else "📦 Load distribution — time-averaged"
)
st.subheader(section_title)

summary_rows = []
for idx in instance_ids:
    df = extract_series_with_aliases(instance_data[idx], selected_metric)
    if df.empty and is_latency:
        df = extract_histogram_mean(instance_data[idx], selected_metric)
    if df.empty:
        continue
    summary_rows.append({
        "Backend": f"Backend {idx}",
        "Mean": df["value"].mean(),
        "P50": df["value"].quantile(0.50),
        "P95": df["value"].quantile(0.95),
        "Max": df["value"].max(),
    })

if summary_rows:
    summary_df = pd.DataFrame(summary_rows).set_index("Backend")
    fmt = "{:.4f}" if is_latency else "{:.2f}"
    st.dataframe(
        summary_df.style.format(fmt),
        use_container_width=True,
    )
    means = [r["Mean"] for r in summary_rows]
    if means and not is_latency:
        imbalance = (
            (max(means) - min(means)) / (sum(means) / len(means) + 1e-9) * 100
        )
        if imbalance < 15:
            st.success(
                f"✅ Load well-balanced (imbalance: {imbalance:.1f}%)"
            )
        elif imbalance < 40:
            st.warning(f"⚠️ Moderate imbalance ({imbalance:.1f}%)")
        else:
            st.error(
                f"❌ High imbalance ({imbalance:.1f}%) — "
                "consider tuning EPP scorer weights"
            )

# ─── Prefix cache hit rates ───────────────────────────────────────────────────

st.subheader("💾 Prefix Cache Hit Rate per Backend")

hit_fig = go.Figure()
for i, idx in enumerate(instance_ids):
    df = extract_prefix_cache_hit_rate(instance_data[idx])
    if df.empty:
        continue
    hit_fig.add_trace(go.Scatter(
        x=df["elapsed_s"],
        y=df["value"] * 100,
        name=f"Backend {idx}",
        line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
        mode="lines",
    ))

if hit_fig.data:
    hit_fig.update_layout(
        xaxis_title="Elapsed (s)",
        yaxis_title="Cache Hit Rate (%)",
        yaxis_range=[0, 100],
        legend_title="Backend",
        height=300,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(hit_fig, use_container_width=True)
    st.caption(
        "Higher hit rates on specific backends indicates EPP is steering "
        "requests with matching KV-cache prefixes to the same backend."
    )
else:
    st.info("Prefix cache hit rate metric not available in this dataset.")

# ─── Generation throughput per backend ───────────────────────────────────────

st.subheader("🚀 Generation Throughput per Backend (tok/s)")

tps_fig = go.Figure()
for i, idx in enumerate(instance_ids):
    df = extract_series(
        instance_data[idx], "vllm:avg_generation_throughput_toks_per_s"
    )
    if df.empty:
        continue
    df["value"] = df["value"].rolling(3, min_periods=1).mean()
    tps_fig.add_trace(go.Scatter(
        x=df["elapsed_s"],
        y=df["value"],
        name=f"Backend {idx}",
        line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
        mode="lines",
    ))
if tps_fig.data:
    tps_fig.update_layout(
        xaxis_title="Elapsed (s)",
        yaxis_title="Generation Throughput (tok/s)",
        legend_title="Backend",
        height=300,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(tps_fig, use_container_width=True)
else:
    st.info("Generation throughput metric not available in this dataset.")

# ─── Client-side benchmark results (guidellm) ────────────────────────────────

st.subheader("📈 Client-Side Benchmark Results (guidellm)")

client_df = load_client_results(run)

if client_df is not None:
    st.dataframe(
        client_df.set_index("Concurrency").style.format("{:.2f}"),
        use_container_width=True,
    )

    cl1, cl2 = st.columns(2)

    ttft_fig = go.Figure()
    ttft_fig.add_trace(go.Scatter(
        x=client_df["Concurrency"],
        y=client_df["TTFT mean (ms)"],
        name="TTFT mean",
        mode="lines+markers",
        line=dict(color="#4C9BE8"),
    ))
    ttft_fig.add_trace(go.Scatter(
        x=client_df["Concurrency"],
        y=client_df["TTFT P95 (ms)"],
        name="TTFT P95",
        mode="lines+markers",
        line=dict(color="#F5A623", dash="dash"),
    ))
    ttft_fig.update_layout(
        xaxis_title="Concurrency",
        yaxis_title="TTFT (ms)",
        height=300,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    cl1.plotly_chart(ttft_fig, use_container_width=True)

    itl_fig = go.Figure()
    itl_fig.add_trace(go.Scatter(
        x=client_df["Concurrency"],
        y=client_df["ITL mean (ms)"],
        name="ITL mean",
        mode="lines+markers",
        line=dict(color="#7ED321"),
    ))
    itl_fig.add_trace(go.Scatter(
        x=client_df["Concurrency"],
        y=client_df["ITL P95 (ms)"],
        name="ITL P95",
        mode="lines+markers",
        line=dict(color="#D0021B", dash="dash"),
    ))
    itl_fig.update_layout(
        xaxis_title="Concurrency",
        yaxis_title="ITL (ms)",
        height=300,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    cl2.plotly_chart(itl_fig, use_container_width=True)

    tps_client_fig = go.Figure()
    tps_client_fig.add_trace(go.Scatter(
        x=client_df["Concurrency"],
        y=client_df["Output TPS"],
        name="Output TPS",
        mode="lines+markers",
        line=dict(color="#9B59B6"),
    ))
    tps_client_fig.update_layout(
        xaxis_title="Concurrency",
        yaxis_title="Output Tokens/s",
        height=280,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(tps_client_fig, use_container_width=True)
elif run.get("benchmarks_file") and run["benchmarks_file"].exists():
    st.info(
        "No valid benchmark entries found in benchmarks.json "
        "(or the file is unreadable)."
    )
else:
    st.info(
        "No `benchmarks.json` found for this run. "
        "Client-side TTFT, ITL, and TPS metrics require a guidellm result file."
    )

# ─── EPP routing metrics (if available) ──────────────────────────────────────

with st.expander("🎯 EPP Routing Metrics", expanded=False):
    if run["epp_file"].exists():
        try:
            epp_data = json.loads(run["epp_file"].read_text())
            st.json(epp_data.get("collection_info", {}))
            first_sample = (epp_data.get("samples") or [{}])[0]
            epp_metric_names = list(first_sample.get("metrics", {}).keys())
            epp_llmd = [m for m in epp_metric_names if m.startswith("llm_d_epp")]
            if epp_llmd:
                st.caption(f"llm_d_epp_* metrics present: {len(epp_llmd)}")
                st.markdown(", ".join(f"`{m}`" for m in epp_llmd[:12]))
        except Exception as e:
            st.warning(f"Could not parse epp-metrics.json: {e}")
    else:
        st.info(
            "EPP routing metrics not found (`epp-metrics.json`). "
            "Add the EPP endpoint (DUT port 9090) to your metrics collector "
            "configuration to enable EPP-level routing analysis."
        )

# ─── Policy comparison ───────────────────────────────────────────────────────

st.subheader("⚖️ Routing Policy Comparison")

paired_policy = (
    "round_robin" if meta.get("routing_policy") == "intelligent"
    else "intelligent"
)
# Pair only with runs of the same model and instance count — comparing across
# models or topologies would attribute workload differences to the policy.
paired_runs = [
    r for r in runs
    if r["path"] != run["path"]
    and r["meta"].get("routing_policy") == paired_policy
    and r["meta"].get("num_instances") == meta.get("num_instances")
    and run_model_name(r) == run_model_name(run)
]

if paired_runs:
    paired_label = st.selectbox(
        f"Compare with {paired_policy} run",
        [r["label"] for r in paired_runs],
    )
    paired = next(r for r in paired_runs if r["label"] == paired_label)
    paired_data = {}
    for f in paired["instance_files"]:
        try:
            idx = int(f.stem.rsplit("-", 1)[-1])
        except ValueError:
            idx = f.stem
        d = load_instance_metrics(f)
        if d:
            paired_data[idx] = d

    comp_metric = "vllm:num_requests_running"
    comp_label = "Running Requests"

    comp_fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            f"{meta.get('routing_policy', 'current')} — {comp_label}",
            f"{paired_policy} — {comp_label}",
        ],
    )
    for col_idx, (_, data_dict) in enumerate([
        (meta.get("routing_policy"), instance_data),
        (paired_policy, paired_data),
    ], start=1):
        for i, idx in enumerate(sorted(data_dict.keys())):
            df = extract_series(data_dict[idx], comp_metric)
            if df.empty:
                continue
            comp_fig.add_trace(
                go.Scatter(
                    x=df["elapsed_s"],
                    y=df["value"].rolling(3, min_periods=1).mean(),
                    name=f"Backend {idx}",
                    line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
                    showlegend=(col_idx == 1),
                ),
                row=1, col=col_idx,
            )

    comp_fig.update_layout(
        height=380,
        template="plotly_dark",
        legend_title="Backend",
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(comp_fig, use_container_width=True)
    st.caption(
        "EPP intelligent routing should show more balanced load and higher "
        "prefix-cache hit rates than round-robin. Narrow spread in the left "
        "chart vs. wider spread in the right confirms EPP is working."
    )

    # Quantitative client-side deltas between the two policies.
    paired_client_df = load_client_results(paired)
    if client_df is not None and paired_client_df is not None:
        merged = client_df.merge(
            paired_client_df, on="Concurrency", suffixes=("_cur", "_pair")
        )
        delta_rows = []
        for _, row in merged.iterrows():
            for metric, higher_is_better in (
                ("TTFT mean (ms)", False),
                ("TTFT P95 (ms)", False),
                ("ITL mean (ms)", False),
                ("ITL P95 (ms)", False),
                ("Output TPS", True),
                ("RPS", True),
            ):
                cur_v = row.get(f"{metric}_cur")
                pair_v = row.get(f"{metric}_pair")
                if not cur_v or not pair_v:
                    continue
                delta_pct = (cur_v - pair_v) / pair_v * 100
                delta_rows.append({
                    "Concurrency": row["Concurrency"],
                    "Metric": metric,
                    f"{meta.get('routing_policy', 'current')}": cur_v,
                    paired_policy: pair_v,
                    "Delta (%)": delta_pct,
                    "Better?": (
                        "✓" if (delta_pct > 0) == higher_is_better else "✗"
                    ),
                })
        if delta_rows:
            st.markdown("**Client-side deltas** (positive Delta = current run is higher)")
            st.dataframe(
                pd.DataFrame(delta_rows).style.format(
                    {"Delta (%)": "{:+.1f}"}, precision=2
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No matching concurrency levels between the two runs' "
                "benchmarks.json files — cannot compute policy deltas."
            )
    else:
        st.info(
            "Client-side results (benchmarks.json) are required in both runs "
            "for quantitative policy deltas."
        )
else:
    st.info(
        f"No paired {paired_policy} run found with the same model and instance count. "
        f"Run: `-e scaleout_routing_policy={paired_policy}` to enable "
        "the comparison view."
    )


# ─── Instance-count scaling analysis ─────────────────────────────────────────

st.subheader("📏 Instance-Count Scaling Analysis")

# Compare runs with the same model, routing policy, and cores per instance,
# but different instance counts — the headline question for scale-out.
scaling_candidates = [
    r for r in runs
    if run_model_name(r) == run_model_name(run)
    and str(r["meta"].get("routing_policy") or "") == str(meta.get("routing_policy") or "")
    and str(r["meta"].get("cores_per_instance") or "") == str(meta.get("cores_per_instance") or "")
]

scaling_rows = []
for r in scaling_candidates:
    n_instances = r["meta"].get("num_instances") or len(r["instance_files"])
    df = load_client_results(r)
    if df is None or df.empty:
        continue
    # Peak client throughput for the run (best concurrency level by RPS,
    # falling back to output TPS when RPS is not reported).
    throughput_col = "RPS" if df["RPS"].max() > 0 else "Output TPS"
    peak = df.loc[df[throughput_col].idxmax()]
    scaling_rows.append({
        "run": r,
        "label": r["label"],
        "instances": int(n_instances),
        "peak_rps": peak.get("RPS", 0) or 0,
        "peak_tps": peak.get("Output TPS", 0) or 0,
        "ttft_p95_at_peak": peak.get("TTFT P95 (ms)", 0) or 0,
        "throughput_col": throughput_col,
    })

scaling_rows.sort(key=lambda row: row["instances"])
instance_counts = sorted({row["instances"] for row in scaling_rows})

if len(instance_counts) >= 2:
    st.caption(
        f"Runs grouped by model `{run_model_name(run) or '—'}`, policy "
        f"`{meta.get('routing_policy', '—')}`, "
        f"{meta.get('cores_per_instance', '?')} cores/instance."
    )

    sc1, sc2 = st.columns(2)

    scale_fig = go.Figure()
    scale_fig.add_trace(go.Scatter(
        x=[row["instances"] for row in scaling_rows],
        y=[row["peak_rps"] or row["peak_tps"] for row in scaling_rows],
        name="Peak throughput",
        mode="lines+markers",
        line=dict(color="#4C9BE8"),
    ))
    scale_fig.update_layout(
        xaxis_title="vLLM instances",
        yaxis_title="Peak RPS (or Output TPS)",
        height=320,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    sc1.plotly_chart(scale_fig, use_container_width=True)

    ttft_scale_fig = go.Figure()
    ttft_scale_fig.add_trace(go.Scatter(
        x=[row["instances"] for row in scaling_rows],
        y=[row["ttft_p95_at_peak"] for row in scaling_rows],
        name="TTFT P95 at peak load",
        mode="lines+markers",
        line=dict(color="#F5A623"),
    ))
    ttft_scale_fig.update_layout(
        xaxis_title="vLLM instances",
        yaxis_title="TTFT P95 (ms)",
        height=320,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    sc2.plotly_chart(ttft_scale_fig, use_container_width=True)

    # Scaling efficiency vs the smallest instance count in the group.
    base = scaling_rows[0]
    base_throughput = base["peak_rps"] or base["peak_tps"]
    eff_rows = []
    for row in scaling_rows:
        throughput = row["peak_rps"] or row["peak_tps"]
        speedup = throughput / base_throughput if base_throughput else 0
        instances_ratio = row["instances"] / base["instances"]
        efficiency = (speedup / instances_ratio * 100) if instances_ratio else 0
        eff_rows.append({
            "Instances": row["instances"],
            "Run": row["label"],
            "Peak RPS": row["peak_rps"],
            "Peak Output TPS": row["peak_tps"],
            "TTFT P95 (ms)": row["ttft_p95_at_peak"],
            "Speedup vs base": round(speedup, 2),
            "Scaling efficiency (%)": round(efficiency, 1),
        })
    st.dataframe(pd.DataFrame(eff_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Scaling efficiency = throughput speedup ÷ instance-count ratio. "
        "100% is perfect linear scaling; values well below that indicate a "
        "bottleneck elsewhere (Envoy, EPP, load generator, or shared memory bandwidth)."
    )
elif len(scaling_rows) >= 2:
    st.info(
        "Multiple runs found for this combination, but all use the same "
        "instance count — run with different `scaleout_num_instances` values "
        "to populate the scaling analysis."
    )
else:
    st.info(
        "Not enough comparable runs for this model / policy / cores-per-instance "
        "combination. Run the same configuration with different "
        "`scaleout_num_instances` values (with per-instance metrics and guidellm "
        "client results) to populate the scaling analysis."
    )
