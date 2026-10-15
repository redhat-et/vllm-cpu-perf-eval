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
    resolve_rps_column,
    resolve_throughput_column,
    throughput_sweep_summary,
    client_workload_from_source,
    run_has_client_workload,
)

st.title("🔀 Scale-Out Routing Analysis")
st.caption(
    "Scale-out benchmarks only. **Client** tab = aggregate SLOs through Envoy; "
    "**Per-instance** tab = backends, KV cache, CPU, and EPP. "
    "Single-instance runs stay on **Client Metrics** (page 1)."
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


def _prefix_hit_rate_to_percent(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize vLLM hit-rate gauges (0–1 or 0–100) to percent."""
    if df.empty:
        return df
    out = df.copy()
    vmax = float(out["value"].max()) if out["value"].notna().any() else 0.0
    out["value"] = out["value"] * (100.0 if vmax <= 1.0 else 1.0)
    return out


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

def instance_data_for_run(run_entry: Dict) -> Dict:
    """Load per-backend Prometheus JSON for a scale-out run."""
    out: Dict = {}
    for f in run_entry["instance_files"]:
        try:
            idx = int(f.stem.rsplit("-", 1)[-1])
        except ValueError:
            idx = f.stem
        data = load_instance_metrics(f)
        if data:
            out[idx] = data
    return out


def caching_config_summary(meta: Dict) -> str:
    """Human-readable caching / LMCache settings from test-metadata.json."""
    parts: List[str] = []
    mode = meta.get("vllm_caching_mode")
    if mode:
        parts.append(f"vllm_caching_mode={mode}")
    lcm = meta.get("lmcache_backend", "none")
    if lcm not in ("none", "", None):
        parts.append(f"LMCache={lcm}")
    elif meta.get("scaleout_enable_prefix_caching") is not None:
        on = meta.get("scaleout_enable_prefix_caching")
        parts.append(f"prefix_caching={'on' if on else 'off'}")
    policy = meta.get("routing_policy")
    if policy:
        parts.append(f"routing={policy}")
    return " · ".join(parts) if parts else "caching settings not recorded"


def resolve_scaleout_run(runs: List[Dict], label: str) -> Dict:
    return next(r for r in runs if r["label"] == label)


def server_cluster_throughput_ref(
    cluster_tok_s: pd.Series,
    stat: str,
) -> Tuple[float, str]:
    """Robust server-side cluster tok/s from scrape time series (not max)."""
    s = cluster_tok_s.dropna()
    if s.empty:
        return 0.0, "server sum (no data)"
    key = stat.lower()
    if key == "mean":
        return float(s.median()), "median server sum (scrapes)"
    if key == "p99":
        return float(s.quantile(0.99)), "P99 server sum (scrapes)"
    return float(s.quantile(0.95)), "P95 server sum (scrapes)"


def scaleout_run_caption(meta: Dict, run: Dict) -> str:
    """One-line run context (replaces top-of-page metric cards)."""
    model_short = str(
        meta.get("model_name") or meta.get("model") or "—"
    ).split("/")[-1]
    n_inst = meta.get("num_instances", len(run.get("instance_files", [])))
    cores = meta.get("cores_per_instance", "—")
    return (
        f"`{model_short}` · **{n_inst}** instances · **{cores}** cores/instance · "
        f"{caching_config_summary(meta)}"
    )


def client_latency_column(prefix: str, stat: str) -> Optional[str]:
    """Map TTFT/TPOT/ITL/E2E + mean|p95|p99 to a benchmarks.json column name."""
    stat = stat.lower()
    if prefix == "E2E":
        if stat == "mean":
            return "E2E mean (ms)"
        if stat in ("p95", "p99"):
            return "E2E P99 (ms)"
        return None
    suffix = {"mean": " mean (ms)", "p95": " P95 (ms)", "p99": " P99 (ms)"}
    if stat not in suffix:
        return None
    return f"{prefix}{suffix[stat]}"


def _metric_has_data(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and df[col].notna().any()


def delta_metrics_for_stat(
    latency_stat: str,
    throughput_stat: str,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    workload: str = "llm",
) -> List[tuple]:
    metrics: List[tuple] = []
    if workload == "llm":
        for prefix, higher in (("TTFT", False), ("TPOT", False), ("ITL", False)):
            col = client_latency_column(prefix, latency_stat)
            if col and (
                _metric_has_data(df_a, col) or _metric_has_data(df_b, col)
            ):
                metrics.append((col, higher))
    else:
        e2e = client_latency_column("E2E", latency_stat)
        if e2e and (
            _metric_has_data(df_a, e2e) or _metric_has_data(df_b, e2e)
        ):
            metrics.append((e2e, False))
    tps_col = resolve_throughput_column(df_a, throughput_stat)
    if _metric_has_data(df_a, tps_col) or _metric_has_data(df_b, tps_col):
        metrics.append((tps_col, True))
    rps_col = resolve_rps_column(df_a, throughput_stat)
    if _metric_has_data(df_a, rps_col) or _metric_has_data(df_b, rps_col):
        metrics.append((rps_col, True))
    return metrics


def _client_delta_table(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str,
    label_b: str,
    latency_stat: str = "mean",
    throughput_stat: str = "p95",
    workload: str = "llm",
) -> None:
    merged = df_a.merge(df_b, on="Concurrency", suffixes=("_a", "_b"))
    delta_rows = []
    for _, row in merged.iterrows():
        for metric, higher_is_better in delta_metrics_for_stat(
            latency_stat, throughput_stat, df_a, df_b, workload=workload
        ):
            va = row.get(f"{metric}_a")
            vb = row.get(f"{metric}_b")
            if va is None or vb is None or (pd.isna(va) or pd.isna(vb)):
                continue
            if va == 0 and vb == 0:
                continue
            delta_pct = (va - vb) / vb * 100 if vb else 0
            delta_rows.append({
                "Concurrency": row["Concurrency"],
                "Metric": metric,
                label_a: va,
                label_b: vb,
                "Δ% (A vs B)": delta_pct,
                "Better for A?": (
                    "✓" if (delta_pct > 0) == higher_is_better else "✗"
                ),
            })
    if delta_rows:
        st.markdown(
            "**Client metrics delta** (Δ% = how much higher run A is than run B)"
        )
        st.dataframe(
            pd.DataFrame(delta_rows).style.format({"Δ% (A vs B)": "{:+.1f}"}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No overlapping concurrency levels with comparable metrics "
            "between run A and run B."
        )


def _client_overlay_charts(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    label_a: str,
    label_b: str,
    latency_stat: str = "mean",
    throughput_stat: str = "p95",
    workload: str = "llm",
) -> None:
    stat_label = (
        latency_stat.upper() if latency_stat != "mean" else "Mean"
    )
    tp_label = (
        throughput_stat.upper()
        if throughput_stat != "mean"
        else "Mean"
    )
    if workload == "llm":
        latency_charts = (
            ("TTFT", "⏱ Time to First Token (ms)"),
            ("TPOT", "⚡ TPOT (ms)"),
            ("ITL", "Inter-token latency (ms)"),
        )
    else:
        latency_charts = (("E2E", "End-to-end latency (ms)"),)

    for prefix, chart_title in latency_charts:
        col = client_latency_column(prefix, latency_stat)
        if not col or not (
            _metric_has_data(df_a, col) or _metric_has_data(df_b, col)
        ):
            continue
        gc_fig = go.Figure()
        for df_data, label, dash in [
            (df_a, label_a, "solid"),
            (df_b, label_b, "dash"),
        ]:
            if _metric_has_data(df_data, col):
                gc_fig.add_trace(go.Scatter(
                    x=df_data["Concurrency"],
                    y=df_data[col],
                    name=f"{label} ({stat_label})",
                    mode="lines+markers",
                    line=dict(dash=dash),
                ))
        if not gc_fig.data:
            continue
        gc_fig.update_layout(
            title=f"{chart_title} — {stat_label}",
            xaxis_title="Concurrency",
            yaxis_title=col,
            height=300,
            template="plotly_dark",
            margin=dict(t=40, b=40),
        )
        st.plotly_chart(gc_fig, use_container_width=True)

    thr_fig = go.Figure()
    for df_data, label, dash in [
        (df_a, label_a, "solid"),
        (df_b, label_b, "dash"),
    ]:
        tps_c = resolve_throughput_column(df_data, throughput_stat)
        if tps_c in df_data.columns and df_data[tps_c].notna().any():
            thr_fig.add_trace(go.Scatter(
                x=df_data["Concurrency"],
                y=df_data[tps_c],
                name=f"{label} — {tps_c}",
                mode="lines+markers",
                line=dict(dash=dash),
            ))
        rps_c = resolve_rps_column(df_data, throughput_stat)
        if rps_c in df_data.columns and df_data[rps_c].notna().any():
            thr_fig.add_trace(go.Scatter(
                x=df_data["Concurrency"],
                y=df_data[rps_c],
                name=f"{label} — {rps_c}",
                mode="lines+markers",
                line=dict(dash="dot" if dash == "solid" else "dashdot"),
            ))
    if thr_fig.data:
        thr_fig.update_layout(
            title=f"🚀 Throughput — {tp_label} (per load point)",
            xaxis_title="Concurrency",
            yaxis_title="tok/s or req/s",
            height=300,
            template="plotly_dark",
            margin=dict(t=40, b=40),
        )
        st.plotly_chart(thr_fig, use_container_width=True)


def _render_single_run_client_charts(
    client_df: pd.DataFrame,
    client_source: str,
    stat: str,
) -> None:
    stat_label = stat.upper() if stat != "mean" else "Mean"
    if client_source == "guidellm":
        cl1, cl2, cl3 = st.columns(3)
        chart_specs = [
            (cl1, "TTFT", "TTFT", "ms"),
            (cl2, "TPOT", "TPOT / ITL", "ms"),
            (cl3, None, "Throughput", ""),
        ]
        for col, prefix, title, ylab in chart_specs:
            fig = go.Figure()
            if prefix:
                lat_col = client_latency_column(prefix, stat)
                if lat_col and lat_col in client_df.columns:
                    fig.add_trace(go.Scatter(
                        x=client_df["Concurrency"],
                        y=client_df[lat_col],
                        name=stat_label,
                        mode="lines+markers",
                    ))
                    ylab = "ms"
                itl_col = client_latency_column("ITL", stat) if prefix == "TPOT" else None
                if itl_col and itl_col in client_df.columns:
                    fig.add_trace(go.Scatter(
                        x=client_df["Concurrency"],
                        y=client_df[itl_col],
                        name=f"ITL {stat_label}",
                        mode="lines+markers",
                        line=dict(dash="dash"),
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
            if not fig.data:
                continue
            fig.update_layout(
                title=f"{title} ({stat_label})" if prefix else title,
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
        e2e_col = client_latency_column("E2E", stat)
        if e2e_col and e2e_col in client_df.columns:
            lat_fig.add_trace(go.Scatter(
                x=client_df["Concurrency"],
                y=client_df[e2e_col],
                name=e2e_col,
                mode="lines+markers",
            ))
        lat_fig.update_layout(
            title=f"E2E latency ({stat_label})",
            xaxis_title="Concurrency",
            yaxis_title="ms",
            height=300,
            template="plotly_dark",
        )
        ec2.plotly_chart(lat_fig, use_container_width=True)


def _server_side_by_side(
    data_a: Dict,
    data_b: Dict,
    title_a: str,
    title_b: str,
    series_kind: str,
    y_title: str,
) -> None:
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[title_a, title_b],
    )

    def _series(data_dict: Dict, idx) -> pd.DataFrame:
        if series_kind == "prefix_cache_hit_rate":
            return _prefix_hit_rate_to_percent(
                extract_prefix_cache_hit_rate(data_dict[idx])
            )
        if series_kind == "generation_tps":
            return extract_generation_throughput(data_dict[idx])
        return extract_series(data_dict[idx], series_kind)

    for col_idx, data_dict in enumerate([data_a, data_b], start=1):
        for i, idx in enumerate(sorted(data_dict.keys())):
            df = _series(data_dict, idx)
            if df.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=df["elapsed_s"],
                    y=df["value"].rolling(3, min_periods=1).mean(),
                    name=f"Backend {idx}",
                    line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
                    showlegend=(col_idx == 1),
                ),
                row=1, col=col_idx,
            )
    if fig.data:
        fig.update_layout(
            height=360,
            template="plotly_dark",
            legend_title="Backend",
            margin=dict(t=40, b=40),
        )
        fig.update_yaxes(title_text=y_title)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No server data for {y_title} in one or both runs.")


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

run_labels = [r["label"] for r in runs]
if "scaleout_run_label" not in st.session_state:
    st.session_state.scaleout_run_label = run_labels[0]

tab_client, tab_instances, tab_comparisons = st.tabs([
    "📈 Client (through Envoy)",
    "🖥️ Per-instance performance",
    "⚖️ Compare & scaling",
])

with tab_client:
    st.subheader("📈 Client performance (through Envoy)")
    st.caption("End-to-end metrics through Envoy (load generator view).")

    run_idx = (
        run_labels.index(st.session_state.scaleout_run_label)
        if st.session_state.scaleout_run_label in run_labels
        else 0
    )
    selected_label = st.selectbox(
        "Benchmark run",
        run_labels,
        index=run_idx,
        key="scaleout_run_client",
    )
    st.session_state.scaleout_run_label = selected_label
    run = resolve_scaleout_run(runs, selected_label)
    meta = run["meta"]
    if not run.get("meta_ok", True):
        st.warning(
            "Could not parse test-metadata.json for this run — "
            "metadata-derived fields may be missing."
        )
    st.markdown(scaleout_run_caption(meta, run))
    with st.expander("Run metadata", expanded=False):
        st.json(meta)

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

        client_stat = st.radio(
            "Chart statistic",
            options=["Mean", "P95", "P99"],
            horizontal=True,
            key="client_tab_stat",
        )
        _render_single_run_client_charts(
            client_df, client_source, client_stat.lower()
        )
    else:
        st.info(
            "No client results in this directory. "
            "For LLM scale-out, ensure `benchmarks.json` (GuideLLM) is copied next to "
            "`test-metadata.json`. For embedding scale-out, run results should be under "
            "`latency/` or `operating_point/`."
        )


with tab_instances:
    st.subheader("🖥️ Per-instance performance")
    st.caption(
        "Per-backend vLLM Prometheus scrapes, podman CPU/memory, EPP routing, "
        "and KV-cache balance — not visible to the client load generator."
    )

    inst_idx = (
        run_labels.index(st.session_state.scaleout_run_label)
        if st.session_state.scaleout_run_label in run_labels
        else 0
    )
    inst_label = st.selectbox(
        "Benchmark run",
        run_labels,
        index=inst_idx,
        key="scaleout_run_instances",
    )
    st.session_state.scaleout_run_label = inst_label
    run = resolve_scaleout_run(runs, inst_label)
    meta = run["meta"]
    st.markdown(scaleout_run_caption(meta, run))
    client_df, _client_src = load_client_results_for_run(run)

    # ─── Container CPU / memory (podman stats) ───────────────────────────────────

    st.subheader("Container CPU & memory")

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

        st.subheader("🚀 Server decode rate vs client throughput")
        with st.expander("How to interpret this chart", expanded=True):
            st.markdown(
                """
**What each line means**

| Series | Meaning |
|---|---|
| **Colored thin lines** | Each **backend**’s generation tok/s (`vllm:avg_generation_throughput_toks_per_s`) |
| **Thick purple** | **Σ backends** at each scrape (instant cluster decode rate) |
| **Orange dashed** | GuideLLM client throughput **reference** (Compare → Throughput stat) |
| **Purple dotted** | Same statistic applied to the **Σ** scrape series (not peak) |

Client reference is from `benchmarks.json` during the load sweep; server lines
are whatever the Prometheus scraper saw every ~10s (often includes idle time).

**Purple below orange — does that make sense?**

**Yes, often.** Typical reasons:

1. **Summary vs moment** — Orange is a **stable client summary**; purple is
   instantaneous server sum during scrapes (ramps, idle gaps, timing).

2. **Metric definition** — vLLM’s “avg generation throughput” gauge is a
   **backend-local rolling average**, not a Prometheus-perfect “cluster output
   tokens/sec.” Summing replicas is a good sanity check but can **under-report**
   vs GuideLLM’s end-to-end token accounting.

3. **Not all replicas in the sum** — If a backend failed to scrape, its tok/s
   is missing for that interval and the sum is low.

**Purple above orange** can happen when the client is not saturating the cluster
(routing, concurrency below peak) or when server gauges spike briefly above what
GuideLLM averaged for that sweep step.

**How to use it** — Compare the **dotted purple** (P95/P99/median server sum over
scrapes, same statistic as Compare → Throughput) to **orange** during steady load.
                """
            )
        per_backend_tps: Dict = {}
        for idx in instance_ids:
            df = extract_generation_throughput(instance_data[idx])
            if df.empty:
                continue
            # Snap each backend's timestamps to the nearest 10 s grid so that
            # backends scraped slightly out of phase align and their tok/s values
            # are summed rather than interleaved (NaN + 100 = 100 not 200).
            s = df.set_index("elapsed_s")["value"]
            s.index = (s.index / 10).round() * 10
            s = s.groupby(level=0).mean()
            per_backend_tps[idx] = s
        if per_backend_tps:
            cluster_df = pd.DataFrame(
                {f"b{idx}": s for idx, s in per_backend_tps.items()}
            )
            cluster_df["cluster_tok_s"] = cluster_df.sum(axis=1, min_count=1)
            cluster_df = cluster_df.reset_index(names="elapsed_s")
            cluster_series = cluster_df["cluster_tok_s"].rolling(
                3, min_periods=1
            ).mean()
            tp_key = st.session_state.get(
                "compare_throughput_stat", "P95"
            ).lower()
            server_ref, server_ref_label = server_cluster_throughput_ref(
                cluster_df["cluster_tok_s"], tp_key
            )
            cl_fig = go.Figure()
            for i, idx in enumerate(sorted(per_backend_tps.keys())):
                col = f"b{idx}"
                if col not in cluster_df.columns:
                    continue
                backend_y = (
                    cluster_df[col].rolling(3, min_periods=1).mean()
                )
                cl_fig.add_trace(
                    go.Scatter(
                        x=cluster_df["elapsed_s"],
                        y=backend_y,
                        name=f"Backend {idx}",
                        mode="lines",
                        line=dict(
                            color=BACKEND_COLORS[i % len(BACKEND_COLORS)],
                            width=1,
                        ),
                        opacity=0.85,
                    ),
                )
            cl_fig.add_trace(
                go.Scatter(
                    x=cluster_df["elapsed_s"],
                    y=cluster_series,
                    name="Σ all backends (tok/s)",
                    mode="lines",
                    line=dict(width=3, color="#9B59B6"),
                ),
            )
            cl_fig.add_hline(
                y=server_ref,
                line_dash="dot",
                line_color="#9B59B6",
                annotation_text=f"{server_ref_label} ({server_ref:.1f})",
            )
            client_ref_note = (
                f"**{server_ref_label}:** {server_ref:.1f} tok/s "
                f"(matches Compare → Throughput statistic)."
            )
            if client_df is not None and "Output TPS" in client_df.columns:
                ref_tps, tps_col, anchor_conc, tps_desc = (
                    throughput_sweep_summary(client_df, tp_key)
                )
                cl_fig.add_hline(
                    y=ref_tps,
                    line_dash="dash",
                    line_color="#F5A623",
                    annotation_text=f"Client {tps_col} ({ref_tps:.1f})",
                )
                ratio = (
                    server_ref / ref_tps * 100 if ref_tps > 0 else 0
                )
                conc_note = (
                    f" @ concurrency **{anchor_conc}**"
                    if anchor_conc is not None
                    else ""
                )
                client_ref_note = (
                    f"**Client ({tps_desc}):** {ref_tps:.1f} tok/s "
                    f"({tps_col}{conc_note}) · **{server_ref_label}:** "
                    f"{server_ref:.1f} tok/s ({ratio:.0f}% of client ref). "
                    "Statistic: Compare tab → Throughput (default P95)."
                )
            elif client_df is not None and "RPS" in client_df.columns:
                st.caption(
                    "No GuideLLM Output TPS in this run — use the Client tab "
                    "for embedding throughput (RPS / E2E)."
                )
            cl_fig.update_layout(
                xaxis_title="Elapsed since server metrics scrape (s)",
                yaxis_title="Generation tok/s (per backend & Σ)",
                yaxis=dict(rangemode="tozero"),
                height=400,
                template="plotly_dark",
                margin=dict(t=40, b=40),
                legend_title="Server metrics",
            )
            st.plotly_chart(cl_fig, use_container_width=True)
            if client_ref_note:
                st.caption(client_ref_note)
        else:
            st.info(
                "Per-backend generation throughput not found in "
                "`vllm-metrics-instance-*.json`."
            )

        st.divider()

    # ─── Metric selector ─────────────────────────────────────────────────────────

    if not instance_ids:
        st.info(
            "No per-instance metrics — deploy with "
            "`scaleout_collect_per_instance_metrics=true`."
        )
    else:
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
        hit_y_max = 0.0
        for i, idx in enumerate(instance_ids):
            df = _prefix_hit_rate_to_percent(
                extract_prefix_cache_hit_rate(instance_data[idx])
            )
            if df.empty:
                continue
            hit_y_max = max(hit_y_max, float(df["value"].max()))
            hit_fig.add_trace(go.Scatter(
                x=df["elapsed_s"],
                y=df["value"],
                name=f"Backend {idx}",
                line=dict(color=BACKEND_COLORS[i % len(BACKEND_COLORS)]),
                mode="lines",
            ))

        if hit_fig.data:
            all_zero = hit_y_max <= 0.0
            _yaxis_cfg = dict(rangemode="tozero")
            if all_zero:
                _yaxis_cfg["range"] = [0, 5]
            elif hit_y_max < 100:
                _yaxis_cfg["range"] = [0, max(1.0, hit_y_max * 1.2)]
            else:
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
            policy = meta.get("routing_policy", "—")
            if policy == "round_robin":
                st.info(
                    "No EPP metrics for this run — **round_robin** routing does not "
                    "start the EPP sidecar, so `epp-metrics.json` is not produced. "
                    "Use **intelligent** routing (`-e scaleout_routing_policy=intelligent`) "
                    "to collect `llm_d_epp_*` series from EPP :9090/metrics."
                )
            elif policy == "intelligent":
                st.warning(
                    "`epp-metrics.json` is missing but this run is tagged **intelligent**. "
                    "Expected when using the scale-out Ansible playbooks with "
                    "`scaleout_collect_per_instance_metrics=true` (default): a background "
                    "scraper on the control node writes "
                    "`/tmp/scaleout-metrics-<test_run_id>/epp-metrics.json` and copies it "
                    "into the results folder at the end of the benchmark. "
                    "Check that `test-metadata.json` `test_run_id` matches the run, "
                    "firewall allows control-node → DUT:**9090**, and "
                    "`collector-epp.log` in the temp metrics dir for scrape errors."
                )
            else:
                st.info(
                    "`epp-metrics.json` not found in this results directory. "
                    "EPP scraping runs only for **intelligent** routing during "
                    "scale-out benchmark playbooks."
                )
            with st.expander("What EPP metrics would show", expanded=False):
                st.markdown(
                    "Prefix indexer hit ratio, per-endpoint KV cache and queue "
                    "stats, and scheduler latency — complementary to per-vLLM "
                    "`vllm-metrics-instance-*.json` (backend view vs EPP routing view)."
                )


with tab_comparisons:

    def _suggest_compare_run_b(run_a: Dict) -> Optional[str]:
        """Prefer LMCache on/off pair with same model, policy, and instance count."""
        meta_a = run_a["meta"]
        has_lcm = meta_a.get("lmcache_backend", "none") not in ("none", "", None)
        toggled = [
            r for r in runs
            if r["path"] != run_a["path"]
            and (
                r["meta"].get("lmcache_backend", "none") in ("none", "", None)
            )
            != has_lcm
            and r["meta"].get("routing_policy") == meta_a.get("routing_policy")
            and r["meta"].get("num_instances") == meta_a.get("num_instances")
            and run_model_name(r) == run_model_name(run_a)
        ]
        if toggled:
            return toggled[0]["label"]
        other = [r for r in runs if r["path"] != run_a["path"]]
        return other[0]["label"] if other else None

    def _suggest_in_pool(run_a: Dict, pool: List[Dict]) -> Optional[str]:
        toggled = _suggest_compare_run_b(run_a)
        pool_labels = {r["label"] for r in pool}
        if toggled and toggled in pool_labels:
            return toggled
        other = [r for r in pool if r["path"] != run_a["path"]]
        return other[0]["label"] if other else None

    def _render_workload_compare(workload: str, key_prefix: str) -> None:
        pool = [r for r in runs if run_has_client_workload(r, workload)]
        pool_labels = [r["label"] for r in pool]
        if len(pool_labels) < 2:
            need = (
                "GuideLLM `benchmarks.json`"
                if workload == "llm"
                else "`latency/` or `operating_point/` JSON from vllm-bench"
            )
            st.info(
                f"Need at least two scale-out runs with {need} to compare."
            )
            return

        ref_label = st.session_state.get("scaleout_run_label", run_labels[0])
        idx_a = (
            pool_labels.index(ref_label)
            if ref_label in pool_labels
            else 0
        )
        label_a = st.selectbox(
            "Run A",
            pool_labels,
            index=idx_a,
            key=f"compare_run_a_{key_prefix}",
        )
        run_a = next(r for r in pool if r["label"] == label_a)
        other_labels = [lbl for lbl in pool_labels if lbl != label_a]
        suggested_b = _suggest_in_pool(run_a, pool)
        idx_b = (
            other_labels.index(suggested_b)
            if suggested_b in other_labels
            else 0
        )
        label_b = st.selectbox(
            "Run B",
            other_labels,
            index=idx_b,
            key=f"compare_run_b_{key_prefix}",
        )
        run_b = next(r for r in pool if r["label"] == label_b)

        short_a = label_a if len(label_a) <= 48 else label_a[:45] + "…"
        short_b = label_b if len(label_b) <= 48 else label_b[:45] + "…"
        cfg_a, cfg_b = st.columns(2)
        with cfg_a:
            st.markdown(f"**Run A** — `{short_a}`")
            st.caption(caching_config_summary(run_a["meta"]))
        with cfg_b:
            st.markdown(f"**Run B** — `{short_b}`")
            st.caption(caching_config_summary(run_b["meta"]))

        st.markdown("### Client (through Envoy)")
        lat_col, tp_col = st.columns(2)
        tp_help = (
            "GuideLLM per-load-point tok/s percentiles when available."
            if workload == "llm"
            else "Embedding runs use mean RPS / throughput from vllm-bench."
        )
        with lat_col:
            compare_lat = st.radio(
                "Latency statistic",
                options=["Mean", "P95", "P99"],
                horizontal=True,
                key=f"compare_client_stat_{key_prefix}",
            )
        with tp_col:
            compare_tp = st.radio(
                "Throughput statistic",
                options=["P95", "P99", "Mean"],
                horizontal=True,
                key=f"compare_throughput_stat_{key_prefix}",
                help=tp_help,
            )
        if workload == "llm":
            st.session_state["compare_throughput_stat"] = compare_tp
        lat_key = compare_lat.lower()
        tp_key = compare_tp.lower()
        df_a, src_a = load_client_results_for_run(run_a)
        df_b, src_b = load_client_results_for_run(run_b)
        if df_a is None or df_b is None:
            missing = []
            if df_a is None:
                missing.append("A")
            if df_b is None:
                missing.append("B")
            st.info(f"Client results missing for run(s) {', '.join(missing)}.")
            return
        st.caption(
            f"Sources: A={src_a}, B={src_b} — solid = run A, dashed = run B. "
            f"Latency: **{compare_lat}** · Throughput: **{compare_tp}**."
        )
        _client_overlay_charts(
            df_a, df_b, short_a, short_b,
            latency_stat=lat_key,
            throughput_stat=tp_key,
            workload=workload,
        )
        _client_delta_table(
            df_a, df_b, short_a, short_b,
            latency_stat=lat_key,
            throughput_stat=tp_key,
            workload=workload,
        )

        st.markdown("### Per-instance server metrics")
        data_a = instance_data_for_run(run_a)
        data_b = instance_data_for_run(run_b)
        _server_side_by_side(
            data_a,
            data_b,
            f"{short_a} — running requests",
            f"{short_b} — running requests",
            "vllm:num_requests_running",
            "Running requests",
        )
        _server_side_by_side(
            data_a,
            data_b,
            f"{short_a} — prefix cache hit %",
            f"{short_b} — prefix cache hit %",
            "prefix_cache_hit_rate",
            "Cache hit rate (%)",
        )

    st.subheader("⚖️ Compare & scaling")
    tab_cmp_llm, tab_cmp_embed, tab_scale = st.tabs([
        "💬 Compare LLM runs",
        "📐 Compare embedding runs",
        "📏 Instance scaling",
    ])
    with tab_cmp_llm:
        st.caption(
            "Generative workloads (GuideLLM): TTFT, TPOT, ITL, Output TPS. "
            "Embedding metrics are on the **Compare embedding runs** tab."
        )
        _render_workload_compare("llm", "llm")
    with tab_cmp_embed:
        st.caption(
            "Embedding workloads (vllm-bench): RPS, throughput, E2E latency. "
            "For full embedding dashboards see **Embedding Metrics** (page 3)."
        )
        _render_workload_compare("embedding", "emb")

    with tab_scale:
        st.subheader("📏 Instance-Count Scaling Analysis")

        scaling_ref = resolve_scaleout_run(
            runs,
            st.session_state.get("scaleout_run_label", run_labels[0]),
        )
        scaling_meta = scaling_ref["meta"]
        _ref_df, ref_src = load_client_results_for_run(scaling_ref)
        scale_wl = (
            client_workload_from_source(ref_src)
            if ref_src
            else "llm"
        )
        lat_prefix = "E2E" if scale_wl == "embedding" else "TTFT"
        sc_lat_col, sc_tp_col = st.columns(2)
        with sc_lat_col:
            scaling_stat = st.radio(
                f"{lat_prefix} statistic",
                options=["Mean", "P95", "P99"],
                horizontal=True,
                key="scaling_ttft_stat",
            )
        with sc_tp_col:
            scaling_tp_stat = st.radio(
                "Throughput summary (not peak)",
                options=["P95", "P99", "Mean"],
                horizontal=True,
                key="scaling_tp_stat",
            )
        scaling_ttft_col = client_latency_column(
            lat_prefix, scaling_stat.lower()
        )
        scaling_ttft_label = (
            scaling_ttft_col or f"{lat_prefix} {scaling_stat}"
        )
        scaling_tp_key = scaling_tp_stat.lower()

        # Compare runs with the same model, routing policy, and cores per instance,
        # but different instance counts — the headline question for scale-out.
        scaling_candidates = [
            r for r in runs
            if run_has_client_workload(r, scale_wl)
            and run_model_name(r) == run_model_name(scaling_ref)
            and str(r["meta"].get("routing_policy") or "") == str(
                scaling_meta.get("routing_policy") or ""
            )
            and str(r["meta"].get("cores_per_instance") or "") == str(
                scaling_meta.get("cores_per_instance") or ""
            )
        ]

        scaling_rows = []
        for r in scaling_candidates:
            n_instances = r["meta"].get("num_instances") or len(r["instance_files"])
            df = load_client_results(r)
            if df is None or df.empty:
                continue
            thr_ref, thr_col, anchor_conc, _thr_desc = throughput_sweep_summary(
                df, scaling_tp_key
            )
            ttft_at_anchor = 0.0
            if scaling_ttft_col and anchor_conc is not None:
                match = df[df["Concurrency"] == anchor_conc]
                if not match.empty and scaling_ttft_col in match.columns:
                    ttft_at_anchor = match.iloc[0].get(scaling_ttft_col, 0) or 0
            scaling_rows.append({
                "run": r,
                "label": r["label"],
                "instances": int(n_instances),
                "throughput_ref": thr_ref,
                "throughput_col": thr_col,
                "anchor_concurrency": anchor_conc,
                "ttft_at_anchor": ttft_at_anchor,
            })

        scaling_rows.sort(key=lambda row: row["instances"])
        instance_counts = sorted({row["instances"] for row in scaling_rows})

        if len(instance_counts) >= 2:
            st.caption(
                f"Runs grouped by model `{run_model_name(scaling_ref) or '—'}`, policy "
                f"`{scaling_meta.get('routing_policy', '—')}`, "
                f"{scaling_meta.get('cores_per_instance', '?')} cores/instance "
                f"({scale_wl} client workload; reference: Client tab selection)."
            )

            sc1, sc2 = st.columns(2)

            scale_fig = go.Figure()
            scale_fig.add_trace(go.Scatter(
                x=[row["instances"] for row in scaling_rows],
                y=[row["throughput_ref"] for row in scaling_rows],
                name=f"Throughput ({scaling_tp_stat})",
                mode="lines+markers",
                line=dict(color="#4C9BE8"),
            ))
            scale_fig.update_layout(
                xaxis_title="vLLM instances",
                yaxis_title=f"Client {scaling_rows[0]['throughput_col']} summary",
                height=320,
                template="plotly_dark",
                margin=dict(t=20, b=40),
            )
            sc1.plotly_chart(scale_fig, use_container_width=True)

            ttft_scale_fig = go.Figure()
            ttft_scale_fig.add_trace(go.Scatter(
                x=[row["instances"] for row in scaling_rows],
                y=[row["ttft_at_anchor"] for row in scaling_rows],
                name=f"{scaling_ttft_label} @ throughput anchor",
                mode="lines+markers",
                line=dict(color="#F5A623"),
            ))
            ttft_scale_fig.update_layout(
                xaxis_title="vLLM instances",
                yaxis_title=f"{scaling_ttft_label} (ms)",
                height=320,
                template="plotly_dark",
                margin=dict(t=20, b=40),
            )
            sc2.plotly_chart(ttft_scale_fig, use_container_width=True)

            # Scaling efficiency vs the smallest instance count in the group.
            base = scaling_rows[0]
            base_throughput = base["throughput_ref"]
            eff_rows = []
            for row in scaling_rows:
                throughput = row["throughput_ref"]
                speedup = throughput / base_throughput if base_throughput else 0
                instances_ratio = row["instances"] / base["instances"]
                efficiency = (
                    (speedup / instances_ratio * 100) if instances_ratio else 0
                )
                eff_rows.append({
                    "Instances": row["instances"],
                    "Run": row["label"],
                    "Throughput summary": round(throughput, 2),
                    "Column": row["throughput_col"],
                    "Anchor concurrency": row["anchor_concurrency"],
                    scaling_ttft_label: row["ttft_at_anchor"],
                    "Speedup vs base": round(speedup, 2),
                    "Scaling efficiency (%)": round(efficiency, 1),
                })
            st.dataframe(
                pd.DataFrame(eff_rows), use_container_width=True, hide_index=True
            )
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
            client_hint = (
                "vllm-bench embedding client results"
                if scale_wl == "embedding"
                else "GuideLLM client results"
            )
            st.info(
                "Not enough comparable runs for this model / policy / cores-per-instance "
                f"combination. Run the same configuration with different "
                f"`scaleout_num_instances` values (with per-instance metrics and "
                f"{client_hint}) to populate the scaling analysis."
            )
