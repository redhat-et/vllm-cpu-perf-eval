"""
Scale-Out Routing Analysis — per-backend metrics for llm-d (EPP + Envoy) deployments.

Expected layout (one directory per benchmark run):
  <results_dir>/
    test-metadata.json               — routing_policy, num_instances, model, …
    vllm-metrics-instance-1.json     — per-backend vLLM Prometheus data
    vllm-metrics-instance-N.json
    epp-metrics.json                 — EPP routing metrics (optional)
    benchmarks.json                  — guidellm client-side results (optional)
    container-stats-scaleout.jsonl   — podman CPU/memory per container (optional)
    latency/ / operating_point/      — embedding bench JSON (optional)

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
from scaleout_data import (  # noqa: E402
    find_scaleout_runs,
    load_client_results_for_run,
    load_scaleout_container_stats,
    aggregate_container_stats_for_run,
)

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
def _cached_find_scaleout_runs(base_dir: str) -> List[Dict]:
    return find_scaleout_runs(base_dir)


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


def extract_generation_throughput(data: dict) -> pd.DataFrame:
    """tok/s from gauge if present, else derived from generation_tokens_total."""
    df = extract_series(data, "vllm:avg_generation_throughput_toks_per_s")
    if not df.empty:
        return df
    rows = []
    prev_ts = prev_tokens = None
    for sample in data.get("samples", []):
        ts = sample.get("elapsed_seconds", 0)
        metrics = sample.get("metrics", {})
        entry = (metrics.get("vllm:generation_tokens_total") or [{}])[0]
        tokens = entry.get("value")
        if tokens is None:
            continue
        if prev_ts is not None and ts > prev_ts:
            rows.append({
                "elapsed_s": ts,
                "value": (tokens - prev_tokens) / (ts - prev_ts),
            })
        prev_ts, prev_tokens = ts, tokens
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["elapsed_s", "value"]
    )


BACKEND_COLORS = [
    "#4C9BE8", "#F5A623", "#7ED321", "#D0021B", "#9B59B6",
    "#1ABC9C", "#E67E22", "#2ECC71", "#E74C3C", "#3498DB",
]

LATENCY_HISTOGRAM_METRICS = {
    "vllm:time_to_first_token_seconds",
    "vllm:time_per_output_token_seconds",
}

KEY_METRICS = {
    "Running Requests": "vllm:num_requests_running",
    "Queued Requests": "vllm:num_requests_waiting",
    "KV Cache Utilisation (%)": "vllm:kv_cache_usage_perc",
    "CPU Cache Utilisation (%)": "vllm:cpu_cache_usage_perc",
    "Generation Throughput (tok/s)": "vllm:avg_generation_throughput_toks_per_s",
    "Server TTFT (histogram mean, s)": "vllm:time_to_first_token_seconds",
    "Server TPOT (histogram mean, s)": "vllm:time_per_output_token_seconds",
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
    df, _source = load_client_results_for_run(run)
    return df


def run_model_name(run: Dict) -> str:
    """Model identifier for a run (falls back across metadata key spellings)."""
    meta = run.get("meta", {})
    return str(meta.get("model_name") or meta.get("model") or "")


def extract_prefix_cache_hit_rate(data: dict) -> pd.DataFrame:
    """Prefix cache hit rate: gauges → local counters (delta) → external counters (delta)."""
    for gauge in (
        "vllm:cpu_prefix_cache_hit_rate",
        "vllm:gpu_prefix_cache_hit_rate",
    ):
        df = extract_series(data, gauge)
        if not df.empty:
            return df

    def _delta_hit_rate(samples, hits_key, queries_key):
        rows = []
        prev_hits = prev_queries = None
        for sample in samples:
            ts = sample.get("elapsed_seconds", 0)
            metrics = sample.get("metrics", {})
            hits_list = metrics.get(hits_key) or []
            queries_list = metrics.get(queries_key) or []
            hits = hits_list[0].get("value", 0) if hits_list else 0
            queries = queries_list[0].get("value", 0) if queries_list else 0
            if prev_hits is not None and prev_queries is not None:
                dq = queries - prev_queries
                dh = hits - prev_hits
                if dq > 0:
                    rows.append({"elapsed_s": ts, "value": dh / dq})
            prev_hits, prev_queries = hits, queries
        return rows

    samples = data.get("samples", [])
    rows = _delta_hit_rate(
        samples,
        "vllm:prefix_cache_hits_total",
        "vllm:prefix_cache_queries_total",
    )
    if rows:
        return pd.DataFrame(rows)

    rows = _delta_hit_rate(
        samples,
        "vllm:external_prefix_cache_hits_total",
        "vllm:external_prefix_cache_queries_total",
    )
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

runs = _cached_find_scaleout_runs(results_dir)

if not runs:
    st.info(
        "No scale-out run data found. "
        "Point the results directory at folders containing `test-metadata.json` "
        "with `deployment_type: scaleout` (or `vllm-metrics-instance-*.json`, "
        "`benchmarks.json`, or `container-stats-scaleout.jsonl`)."
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
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Instances", meta.get("num_instances", len(run["instance_files"])))
col2.metric("Routing Policy", meta.get("routing_policy", "—"))
col3.metric("Cores / Instance", meta.get("cores_per_instance", "—"))
model_display = meta.get("model_name") or meta.get("model") or "—"
col4.metric("Model", str(model_display).split("/")[-1])
lmcache_backend = meta.get("lmcache_backend", "none")
lmcache_active = lmcache_backend not in ("none", "", None)
col5.metric("LMCache", lmcache_backend if lmcache_active else "Disabled")

st.divider()

# ─── Client-side performance (GuideLLM or embedding bench) ───────────────────

st.subheader("📈 Client performance (through Envoy)")

client_df, client_source = load_client_results_for_run(run)

if client_df is not None:
    st.caption(
        f"Data source: **{client_source}** "
        + (
            "(TTFT / TPOT / ITL from GuideLLM)"
            if client_source == "guidellm"
            else "(request throughput & E2E latency from vllm-bench)"
        )
    )
    display_cols = [c for c in client_df.columns if client_df[c].notna().any()]
    st.dataframe(
        client_df[display_cols].set_index("Concurrency").style.format("{:.2f}"),
        use_container_width=True,
    )

    if client_source == "guidellm":
        cl1, cl2, cl3 = st.columns(3)
        for col, mean_c, p95_c, p99_c, title, ylab in [
            (cl1, "TTFT mean (ms)", "TTFT P95 (ms)", "TTFT P99 (ms)", "TTFT", "ms"),
            (cl2, "TPOT mean (ms)", "TPOT P95 (ms)", "TPOT P99 (ms)", "TPOT / ITL", "ms"),
            (cl3, None, None, None, "Throughput", ""),
        ]:
            fig = go.Figure()
            if mean_c and mean_c in client_df.columns:
                fig.add_trace(go.Scatter(
                    x=client_df["Concurrency"],
                    y=client_df[mean_c],
                    name="mean",
                    mode="lines+markers",
                ))
            if p95_c and p95_c in client_df.columns:
                fig.add_trace(go.Scatter(
                    x=client_df["Concurrency"],
                    y=client_df[p95_c],
                    name="P95",
                    mode="lines+markers",
                    line=dict(dash="dash"),
                ))
            if p99_c and p99_c in client_df.columns:
                fig.add_trace(go.Scatter(
                    x=client_df["Concurrency"],
                    y=client_df[p99_c],
                    name="P99",
                    mode="lines+markers",
                    line=dict(dash="dot"),
                ))
            if title == "Throughput":
                if "Output TPS" in client_df.columns:
                    fig.add_trace(go.Scatter(
                        x=client_df["Concurrency"],
                        y=client_df["Output TPS"],
                        name="Output TPS",
                        mode="lines+markers",
                    ))
                if "RPS" in client_df.columns:
                    fig.add_trace(go.Scatter(
                        x=client_df["Concurrency"],
                        y=client_df["RPS"],
                        name="RPS",
                        mode="lines+markers",
                        line=dict(dash="dash"),
                    ))
                ylab = "tok/s or req/s"
            fig.update_layout(
                title=title,
                xaxis_title="Concurrency",
                yaxis_title=ylab,
                height=300,
                template="plotly_dark",
                margin=dict(t=40, b=40),
            )
            col.plotly_chart(fig, use_container_width=True)
    else:
        ec1, ec2 = st.columns(2)
        thr_fig = go.Figure()
        thr_fig.add_trace(go.Scatter(
            x=client_df["Concurrency"],
            y=client_df["RPS"],
            name="Request throughput (RPS)",
            mode="lines+markers",
        ))
        thr_fig.update_layout(
            xaxis_title="Concurrency",
            yaxis_title="req/s",
            height=300,
            template="plotly_dark",
        )
        ec1.plotly_chart(thr_fig, use_container_width=True)
        lat_fig = go.Figure()
        if "E2E mean (ms)" in client_df.columns:
            lat_fig.add_trace(go.Scatter(
                x=client_df["Concurrency"],
                y=client_df["E2E mean (ms)"],
                name="E2E mean",
                mode="lines+markers",
            ))
        if "E2E P99 (ms)" in client_df.columns:
            lat_fig.add_trace(go.Scatter(
                x=client_df["Concurrency"],
                y=client_df["E2E P99 (ms)"],
                name="E2E P99",
                mode="lines+markers",
                line=dict(dash="dash"),
            ))
        lat_fig.update_layout(
            xaxis_title="Concurrency",
            yaxis_title="ms",
            height=300,
            template="plotly_dark",
        )
        ec2.plotly_chart(lat_fig, use_container_width=True)
else:
    st.info(
        "No client results in this directory. "
        "For LLM scale-out, ensure `benchmarks.json` (GuideLLM) is copied next to "
        "`test-metadata.json`. For embedding scale-out, run results should be under "
        "`latency/` or `operating_point/`."
    )

# ─── Container CPU / memory (podman stats) ───────────────────────────────────

st.subheader("🖥️ Container CPU & memory")

container_dfs = load_scaleout_container_stats(Path(run["path"]))
if container_dfs:
    vllm_only = {
        k: v for k, v in container_dfs.items() if "vllm-instance" in k
    }
    agg_vllm = aggregate_container_stats_for_run(vllm_only or container_dfs)
    cc1, cc2 = st.columns(2)
    cpu_fig = go.Figure()
    mem_fig = go.Figure()
    for name, cdf in sorted(container_dfs.items()):
        cpu_fig.add_trace(go.Scatter(
            x=cdf["elapsed_min"],
            y=cdf["cpu_pct"],
            name=name,
            mode="lines",
        ))
        mem_fig.add_trace(go.Scatter(
            x=cdf["elapsed_min"],
            y=cdf["mem_usage_gb"],
            name=name,
            mode="lines",
        ))
    if not agg_vllm.empty:
        cpu_fig.add_trace(go.Scatter(
            x=agg_vllm["elapsed_min"],
            y=agg_vllm["cpu_pct"],
            name="Σ vLLM instances",
            mode="lines",
            line=dict(width=3, dash="dot"),
        ))
    cpu_fig.update_layout(
        xaxis_title="Elapsed (min)",
        yaxis_title="CPU %",
        height=320,
        template="plotly_dark",
        legend_title="Container",
    )
    mem_fig.update_layout(
        xaxis_title="Elapsed (min)",
        yaxis_title="Memory (GB)",
        height=320,
        template="plotly_dark",
        legend_title="Container",
    )
    cc1.plotly_chart(cpu_fig, use_container_width=True)
    cc2.plotly_chart(mem_fig, use_container_width=True)
    st.caption("Source: `container-stats-scaleout.jsonl` (podman stats, ~10s interval).")
else:
    st.info(
        "`container-stats-scaleout.jsonl` not found. Enable scale-out metrics collection "
        "in the benchmark playbook (default: on)."
    )

st.divider()

# ─── Load per-instance Prometheus scrapes ─────────────────────────────────────

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
    st.warning(
        "No per-instance `vllm-metrics-instance-*.json` files — "
        "server-side KV / routing charts are unavailable for this run."
    )
    instance_ids: List = []
else:
    instance_ids = sorted(instance_data.keys())

    # Cluster aggregate generation throughput vs client output TPS
    st.subheader("🚀 Cluster vs client throughput")
    cluster_rows = []
    all_ts = set()
    per_backend_tps: Dict = {}
    for idx in instance_ids:
        df = extract_generation_throughput(instance_data[idx])
        if df.empty:
            continue
        per_backend_tps[idx] = df.set_index("elapsed_s")["value"]
        all_ts.update(df["elapsed_s"].tolist())
    if all_ts and per_backend_tps:
        cluster_df = pd.DataFrame(index=sorted(all_ts))
        for idx, series in per_backend_tps.items():
            cluster_df[f"b{idx}"] = series
        cluster_df["cluster_tok_s"] = cluster_df.sum(axis=1, min_count=1)
        cluster_df = cluster_df.reset_index(names="elapsed_s")
        cl_fig = go.Figure()
        cl_fig.add_trace(go.Scatter(
            x=cluster_df["elapsed_s"],
            y=cluster_df["cluster_tok_s"],
            name="Σ server generation tok/s",
            mode="lines",
            line=dict(width=2, color="#9B59B6"),
        ))
        if client_df is not None and "Output TPS" in client_df.columns:
            peak_tps = client_df["Output TPS"].max()
            cl_fig.add_hline(
                y=peak_tps,
                line_dash="dash",
                line_color="#F5A623",
                annotation_text=f"Client peak output TPS ({peak_tps:.1f})",
            )
        cl_fig.update_layout(
            xaxis_title="Elapsed (s)",
            yaxis_title="tok/s",
            height=300,
            template="plotly_dark",
        )
        st.plotly_chart(cl_fig, use_container_width=True)

    st.divider()

# ─── Metric selector ─────────────────────────────────────────────────────────

if not instance_ids:
    st.stop()

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
    if selected_metric in LATENCY_HISTOGRAM_METRICS:
        df = extract_histogram_mean(instance_data[idx], selected_metric)
    elif selected_metric == "vllm:avg_generation_throughput_toks_per_s":
        df = extract_generation_throughput(instance_data[idx])
    else:
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

is_latency = selected_metric in LATENCY_HISTOGRAM_METRICS

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
    all_zero = all(
        (t.y is None or max(t.y, default=0) == 0)
        for t in hit_fig.data
    )
    _yaxis_cfg = dict(rangemode="tozero")
    if not all_zero:
        _yaxis_cfg["range"] = [0, 100]
    hit_fig.update_layout(
        xaxis_title="Elapsed (s)",
        yaxis_title="Cache Hit Rate (%)",
        yaxis=_yaxis_cfg,
        legend_title="Backend",
        height=300,
        template="plotly_dark",
        margin=dict(t=20, b=40),
    )
    st.plotly_chart(hit_fig, use_container_width=True)
    if all_zero:
        st.caption(
            "Cache hit rate is 0% for all backends — the KV cache has not "
            "served any hits yet (cold cache or cache misses throughout the run)."
        )
    else:
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
    df = extract_generation_throughput(instance_data[idx])
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

# ─── EPP routing metrics (if available) ──────────────────────────────────────

st.subheader("🎯 EPP routing metrics")

if run["epp_file"].exists():
    try:
        epp_data = json.loads(run["epp_file"].read_text())
        epp_chart_metrics = [
            ("llm_d_epp_prefix_indexer_hit_ratio", "Prefix hit ratio"),
            ("llm_d_epp_average_kv_cache_utilization", "Avg KV cache util"),
            ("llm_d_epp_average_queue_size", "Avg queue size"),
            ("llm_d_epp_std_dev_queue_size", "Queue size std dev"),
            ("llm_d_epp_average_running_requests", "Avg running requests"),
        ]
        epp_fig = make_subplots(
            rows=len(epp_chart_metrics),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            subplot_titles=[t[1] for t in epp_chart_metrics],
        )
        any_epp = False
        for row_i, (metric, _label) in enumerate(epp_chart_metrics, start=1):
            rows = []
            for sample in epp_data.get("samples", []):
                ts = sample.get("elapsed_seconds", 0)
                for entry in sample.get("metrics", {}).get(metric, []):
                    rows.append({"elapsed_s": ts, "value": entry["value"]})
            if not rows:
                continue
            any_epp = True
            edf = pd.DataFrame(rows)
            epp_fig.add_trace(
                go.Scatter(
                    x=edf["elapsed_s"],
                    y=edf["value"],
                    mode="lines",
                    name=_label,
                    showlegend=False,
                ),
                row=row_i,
                col=1,
            )
        if any_epp:
            epp_fig.update_layout(
                height=180 * len(epp_chart_metrics),
                template="plotly_dark",
                margin=dict(t=40, b=40),
            )
            epp_fig.update_xaxes(title_text="Elapsed (s)", row=len(epp_chart_metrics), col=1)
            st.plotly_chart(epp_fig, use_container_width=True)
        else:
            st.info("EPP metrics file present but no known `llm_d_epp_*` series found.")
        with st.expander("Collection metadata", expanded=False):
            st.json(epp_data.get("collection_info", {}))
    except Exception as e:
        st.warning(f"Could not parse epp-metrics.json: {e}")
else:
    st.info(
        "EPP metrics not collected (`epp-metrics.json` missing). "
        "Intelligent routing runs scrape EPP :9090 during benchmarks."
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
                ("TPOT mean (ms)", False),
                ("TPOT P95 (ms)", False),
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


# ─── LMCache comparison ──────────────────────────────────────────────────────

st.subheader("💾 LMCache On/Off Comparison")

current_lmcache = meta.get("lmcache_backend", "none")
current_has_lmcache = current_lmcache not in ("none", "", None)
lmcache_pair_runs = [
    r for r in runs
    if r["path"] != run["path"]
    and r["meta"].get("routing_policy") == meta.get("routing_policy")
    and r["meta"].get("num_instances") == meta.get("num_instances")
    and run_model_name(r) == run_model_name(run)
    and (r["meta"].get("lmcache_backend", "none") in ("none", "", None)) != current_has_lmcache
]

if lmcache_pair_runs:
    lmcache_pair_label = st.selectbox(
        "Compare with run (LMCache toggled)",
        [r["label"] for r in lmcache_pair_runs],
        key="lmcache_pair_select",
    )
    lmcache_paired = next(
        r for r in lmcache_pair_runs if r["label"] == lmcache_pair_label
    )
    lmcache_paired_data = {}
    for f in lmcache_paired["instance_files"]:
        try:
            idx = int(f.stem.rsplit("-", 1)[-1])
        except ValueError:
            idx = f.stem
        d = load_instance_metrics(f)
        if d:
            lmcache_paired_data[idx] = d

    lmc_label_cur = f"LMCache={current_lmcache}"
    lmc_label_pair = (
        f"LMCache={lmcache_paired['meta'].get('lmcache_backend', 'none')}"
    )

    lmc_fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            f"{lmc_label_cur} — Running Requests",
            f"{lmc_label_pair} — Running Requests",
        ],
    )
    for col_idx, data_dict in enumerate(
        [instance_data, lmcache_paired_data], start=1
    ):
        for i, idx in enumerate(sorted(data_dict.keys())):
            df = extract_series(data_dict[idx], "vllm:num_requests_running")
            if df.empty:
                continue
            lmc_fig.add_trace(
                go.Scatter(
                    x=df["elapsed_s"],
                    y=df["value"].rolling(3, min_periods=1).mean(),
                    name=f"Backend {idx}",
                    line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
                    showlegend=(col_idx == 1),
                ),
                row=1, col=col_idx,
            )
    lmc_fig.update_layout(
        height=380,
        template="plotly_dark",
        legend_title="Backend",
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(lmc_fig, use_container_width=True)

    lmc_hit_fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            f"{lmc_label_cur} — Cache Hit Rate (%)",
            f"{lmc_label_pair} — Cache Hit Rate (%)",
        ],
    )
    any_hit_data = False
    for col_idx, data_dict in enumerate(
        [instance_data, lmcache_paired_data], start=1
    ):
        for i, idx in enumerate(sorted(data_dict.keys())):
            df = extract_prefix_cache_hit_rate(data_dict[idx])
            if df.empty:
                continue
            any_hit_data = True
            lmc_hit_fig.add_trace(
                go.Scatter(
                    x=df["elapsed_s"],
                    y=df["value"] * 100,
                    name=f"Backend {idx}",
                    line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
                    showlegend=(col_idx == 1),
                ),
                row=1, col=col_idx,
            )
    if any_hit_data:
        lmc_hit_fig.update_layout(
            height=380,
            template="plotly_dark",
            legend_title="Backend",
            margin=dict(t=40, b=40),
        )
        st.plotly_chart(lmc_hit_fig, use_container_width=True)
    else:
        st.info("Cache hit rate metric not available in either run.")

    lmc_client_df = load_client_results(lmcache_paired)
    if client_df is not None and lmc_client_df is not None:
        _guidellm_charts = [
            ("TTFT mean (ms)", "TTFT P95 (ms)", "⏱ Time to First Token (ms)", False),
            ("TPOT mean (ms)", "TPOT P95 (ms)", "⚡ TPOT (ms)", False),
            ("ITL mean (ms)", "ITL P95 (ms)", "Inter-token latency (ms)", False),
            ("Output TPS", None, "🚀 Output Throughput (tok/s)", True),
            ("RPS", None, "📨 Requests per Second", True),
        ]
        for mean_col, p95_col, chart_title, higher_is_better in _guidellm_charts:
            if mean_col not in client_df.columns:
                continue
            gc_fig = go.Figure()
            for df_data, label, dash in [
                (client_df, lmc_label_cur, "solid"),
                (lmc_client_df, lmc_label_pair, "dash"),
            ]:
                if mean_col in df_data.columns:
                    gc_fig.add_trace(go.Scatter(
                        x=df_data["Concurrency"],
                        y=df_data[mean_col],
                        name=f"{label} (mean)",
                        mode="lines+markers",
                        line=dict(dash=dash),
                    ))
                if p95_col and p95_col in df_data.columns:
                    gc_fig.add_trace(go.Scatter(
                        x=df_data["Concurrency"],
                        y=df_data[p95_col],
                        name=f"{label} (P95)",
                        mode="lines+markers",
                        line=dict(dash=dash, width=1),
                        opacity=0.6,
                    ))
            gc_fig.update_layout(
                title=chart_title,
                xaxis_title="Concurrency",
                yaxis_title=mean_col,
                height=320,
                template="plotly_dark",
                margin=dict(t=40, b=40),
            )
            st.plotly_chart(gc_fig, use_container_width=True)
        st.caption(
            "Data source: guidellm benchmarks.json — "
            "solid lines = current run, dashed = paired run."
        )

        merged = client_df.merge(
            lmc_client_df, on="Concurrency",
            suffixes=("_cur", "_pair"),
        )
        delta_rows = []
        for _, row in merged.iterrows():
            for metric, higher_is_better in (
                ("TTFT mean (ms)", False),
                ("TTFT P95 (ms)", False),
                ("TPOT mean (ms)", False),
                ("TPOT P95 (ms)", False),
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
                    lmc_label_cur: cur_v,
                    lmc_label_pair: pair_v,
                    "Delta (%)": delta_pct,
                    "Better?": (
                        "✓" if (delta_pct > 0) == higher_is_better else "✗"
                    ),
                })
        if delta_rows:
            st.markdown(
                "**Client-side deltas** "
                f"(positive Delta = {lmc_label_cur} is higher)"
            )
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
                "benchmarks.json files — cannot compute LMCache deltas."
            )
    else:
        st.info(
            "Client-side results (benchmarks.json) are required in both "
            "runs for quantitative LMCache deltas."
        )
else:
    opposite = "without" if current_has_lmcache else "with"
    st.info(
        f"No paired run found {opposite} LMCache (same model, policy, "
        "and instance count). Run the benchmark with "
        f"`-e scaleout_lmcache_backend={'remote' if not current_has_lmcache else 'none'}` "
        "to enable the comparison view."
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
