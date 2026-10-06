"""
Scale-Out Routing Analysis — per-backend metrics for llm-d (EPP + Envoy) deployments.

Expected layout (one directory per benchmark run):
  <results_dir>/
    test-metadata.json               — routing_policy, num_instances, model, …
    vllm-metrics-instance-1.json     — per-backend vLLM Prometheus data
    vllm-metrics-instance-N.json
    epp-metrics.json                 — EPP routing metrics (optional)

Compares per-backend load, prefix-cache hit rates, and supports side-by-side
comparison of intelligent (EPP) vs round_robin routing runs.
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
        try:
            meta = json.loads(meta_file.read_text())
        except Exception:
            pass
        policy = meta.get("routing_policy", "unknown")
        runs.append({
            "path": run_dir,
            "meta": meta,
            "instance_files": instance_files,
            "epp_file": run_dir / "epp-metrics.json",
            "label": f"{run_dir.name} ({policy})",
        })
    return runs


def load_instance_metrics(path: Path) -> Optional[Dict]:
    """Load a single vllm-metrics-instance-N.json file."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


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
    "KV Cache Utilisation (%)": "vllm:gpu_cache_usage_perc",
    "CPU Cache Utilisation (%)": "vllm:cpu_cache_usage_perc",
    "Generation Throughput (tok/s)": "vllm:avg_generation_throughput_toks_per_s",
    "Completed Requests (cumulative)": "vllm:request_success_total",
}

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
col1, col2, col3, col4 = st.columns(4)
col1.metric("Instances", meta.get("num_instances", len(run["instance_files"])))
col2.metric("Routing Policy", meta.get("routing_policy", "—"))
col3.metric("Cores / Instance", meta.get("cores_per_instance", "—"))
col4.metric("Model", (meta.get("model_name", "—") or "—").split("/")[-1])

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
    df = extract_series(instance_data[idx], selected_metric)
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

fig.update_layout(
    xaxis_title="Elapsed (s)",
    yaxis_title=selected_display,
    legend_title="Backend",
    height=380,
    template="plotly_dark",
    margin=dict(t=20, b=40),
)
st.plotly_chart(fig, use_container_width=True)

# ─── Load balance summary ─────────────────────────────────────────────────────

st.subheader("📦 Load distribution — time-averaged")

summary_rows = []
for idx in instance_ids:
    df = extract_series(instance_data[idx], selected_metric)
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
    st.dataframe(
        summary_df.style.format("{:.2f}").background_gradient(
            cmap="RdYlGn_r", axis=0
        ),
        use_container_width=True,
    )
    means = [r["Mean"] for r in summary_rows]
    if means:
        imbalance = (
            (max(means) - min(means)) / (sum(means) / len(means) + 1e-9) * 100
        )
        if imbalance < 15:
            st.success(f"✅ Load well-balanced (imbalance: {imbalance:.1f}%)")
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
    df = extract_series(instance_data[idx], "vllm:cpu_prefix_cache_hit_rate")
    if df.empty:
        df = extract_series(instance_data[idx], "vllm:gpu_prefix_cache_hit_rate")
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

# ─── EPP routing metrics (if available) ──────────────────────────────────────

if run["epp_file"].exists():
    st.subheader("🎯 EPP Routing Metrics")
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
paired_runs = [
    r for r in runs
    if r["path"] != run["path"]
    and r["meta"].get("routing_policy") == paired_policy
    and r["meta"].get("num_instances") == meta.get("num_instances")
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
else:
    st.info(
        f"No paired {paired_policy} run found with the same instance count. "
        f"Run: `-e scaleout_routing_policy={paired_policy}` to enable "
        "the comparison view."
    )
