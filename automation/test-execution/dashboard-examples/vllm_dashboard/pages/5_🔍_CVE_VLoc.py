#!/usr/bin/env python3
"""CVE Vulnerability Localization Dashboard.

Displays results from the VLoc Bench agent-loop evaluation and
optionally compares them against the upstream leaderboard.
"""

import json
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig, normalize_vllm_version  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEADERBOARD_JSON_URL = (
    "https://raw.githubusercontent.com/cisco-foundation-ai/"
    "vulnerability-localization-benchmark/main/docs/model-performance.json"
)

# Map local model short-names (after the '/') to leaderboard model labels.
# Keys are lowercased for case-insensitive matching.
_LOCAL_TO_LEADERBOARD: Dict[str, str] = {
    "granite-4.0-350m": "Granite-4.0-350M",
    "granite-4.0-1b": "Granite-4.0-1B",
    "granite-4.0-micro": "Granite-4.0-Micro",
    "antares-350m": "Antares-350M-GRPO",
    "antares-1b": "Antares-1B-GRPO",
    "antares-3b": "Antares-3B-GRPO",
    "qwen3.5-9b": "Qwen3.5-9B",
    "qwen3.5-27b": "Qwen3.5-27B",
    "qwen3.5-35b-a3b": "Qwen3.5-35B-A3B",
    "qwen3.5-72b": "Qwen3.5-72B",
    "qwen3.5-122b": "Qwen3.5-122B",
}

# Colors shared across charts
_COLORS = {
    "file_f1": "#1f77b4",
    "abstain": "#d62728",
    "tnr": "#2ca02c",
    "throughput": "#ff7f0e",
    "leaderboard": "#9467bd",
    "local": "#1f77b4",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _model_short(model: str) -> str:
    return model.split("/")[-1]


def _leaderboard_name(model: str) -> Optional[str]:
    key = _model_short(model).lower()
    return _LOCAL_TO_LEADERBOARD.get(key)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_cve_results(results_base_dir: str) -> pd.DataFrame:
    """Scan results/llm/ for cve-vloc-* directories and load all runs."""
    rows: List[dict] = []
    base = Path(results_base_dir)

    if not base.exists():
        return pd.DataFrame()

    for model_dir in base.iterdir():
        if not model_dir.is_dir() or model_dir.name.startswith("."):
            continue

        for ts_dir in model_dir.iterdir():
            if not ts_dir.is_dir() or not ts_dir.name.startswith("cve-vloc-"):
                continue

            for config_dir in ts_dir.iterdir():
                if not config_dir.is_dir():
                    continue

                results_file = config_dir / "results.json"
                meta_file = config_dir / "test-metadata.json"

                if not (results_file.exists() and meta_file.exists()):
                    continue

                try:
                    with open(results_file) as f:
                        res = json.load(f)
                    with open(meta_file) as f:
                        meta = json.load(f)
                except Exception as exc:
                    st.warning(f"Could not load {config_dir}: {exc}")
                    continue

                cfg = meta.get("configuration", {})
                env = meta.get("environment", {})
                metrics = res.get("metrics", {})

                row = {
                    "model": meta.get("model", "unknown"),
                    "model_short": _model_short(meta.get("model", "unknown")),
                    "vloc_runner": meta.get("vloc_runner", "vllm"),
                    "vloc_phases": meta.get("vloc_phases", "a"),
                    "test_run_id": meta.get("test_run_id", ""),
                    "timestamp": meta.get("timestamp", ""),
                    "cores": cfg.get("cores", 0),
                    "workers": cfg.get("workers", 1),
                    "n_limit": cfg.get("n_limit", 0),
                    "max_model_len": cfg.get("max_model_len", 0),
                    "vllm_version": normalize_vllm_version(
                        env.get("vllm_version", "unknown")
                    ),
                    "container_image": env.get("container_image", "unknown"),
                    "vloc_bench_commit": env.get("vloc_bench_commit", ""),
                    # Quality metrics
                    "mean_file_f1": metrics.get("mean_file_f1"),
                    "abstain_rate": metrics.get("abstain_rate"),
                    "true_negative_rate": metrics.get("true_negative_rate"),
                    "false_positive_rate": metrics.get("false_positive_rate"),
                    # Throughput
                    "tasks_per_hour": metrics.get("tasks_per_hour"),
                    "wall_time_seconds": metrics.get("wall_time_seconds"),
                    "tasks_completed": metrics.get("tasks_completed", 0),
                    "phase_a_tasks": metrics.get("phase_a_tasks", 0),
                    "phase_b_tasks": metrics.get("phase_b_tasks", 0),
                    # Derived
                    "leaderboard_name": _leaderboard_name(
                        meta.get("model", "")
                    ),
                    "config_label": config_dir.name,
                }
                rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


# Embedded snapshot of the upstream leaderboard (fetched 2026-08-11).
# Used as a fallback when the network is unavailable.
_FALLBACK_LEADERBOARD = [
    {"model": "GPT-5.5 (xhigh)", "size": "—", "type": "frontier",
     "file_f1": 0.229, "precision": 0.310, "recall": 0.221,
     "true_negative_rate": 0.279, "false_positive_rate": 0.721,
     "submitted_nothing_rate": 0.158},
    {"model": "GPT-5.5", "size": "—", "type": "frontier",
     "file_f1": 0.221, "precision": 0.305, "recall": 0.211,
     "true_negative_rate": 0.192, "false_positive_rate": 0.808,
     "submitted_nothing_rate": 0.158},
    {"model": "Antares-3B-GRPO", "size": "3B", "type": "open-weights",
     "file_f1": 0.223, "precision": 0.298, "recall": 0.219,
     "true_negative_rate": None, "false_positive_rate": None,
     "submitted_nothing_rate": None},
    {"model": "Antares-1B-GRPO", "size": "1B", "type": "open-weights",
     "file_f1": 0.209, "precision": 0.268, "recall": 0.221,
     "true_negative_rate": None, "false_positive_rate": None,
     "submitted_nothing_rate": None},
    {"model": "GLM-5.2", "size": "753B", "type": "open-weights",
     "file_f1": 0.186, "precision": 0.226, "recall": 0.186,
     "true_negative_rate": None, "false_positive_rate": None,
     "submitted_nothing_rate": None},
    {"model": "Gemini-3-Pro", "size": "—", "type": "frontier",
     "file_f1": 0.152, "precision": 0.190, "recall": 0.153,
     "true_negative_rate": 0.329, "false_positive_rate": 0.671,
     "submitted_nothing_rate": 27.1},
    {"model": "Antares-350M-GRPO", "size": "350M", "type": "open-weights",
     "file_f1": 0.135, "precision": 0.144, "recall": 0.176,
     "true_negative_rate": None, "false_positive_rate": None,
     "submitted_nothing_rate": None},
    {"model": "Gemma-4-31B", "size": "31B", "type": "open-weights",
     "file_f1": 0.101, "precision": 0.131, "recall": 0.097,
     "true_negative_rate": 0.682, "false_positive_rate": 0.318,
     "submitted_nothing_rate": None},
    {"model": "Gemini-2.5-Flash", "size": "—", "type": "frontier",
     "file_f1": 0.102, "precision": 0.132, "recall": 0.098,
     "true_negative_rate": 0.392, "false_positive_rate": 0.608,
     "submitted_nothing_rate": 37.8},
    {"model": "GPT-5-Mini", "size": "—", "type": "frontier",
     "file_f1": 0.098, "precision": 0.115, "recall": 0.096,
     "true_negative_rate": 0.702, "false_positive_rate": 0.298,
     "submitted_nothing_rate": 67.7},
    {"model": "Gemini-3.1-Flash-Lite", "size": "—", "type": "frontier",
     "file_f1": 0.095, "precision": 0.131, "recall": 0.090,
     "true_negative_rate": 0.632, "false_positive_rate": 0.368,
     "submitted_nothing_rate": 62.3},
    {"model": "Qwen3.5-27B", "size": "27B", "type": "open-weights",
     "file_f1": 0.091, "precision": 0.116, "recall": 0.088,
     "true_negative_rate": 0.748, "false_positive_rate": 0.252,
     "submitted_nothing_rate": None},
    {"model": "Qwen3.5-122B", "size": "122B", "type": "open-weights",
     "file_f1": 0.091, "precision": 0.124, "recall": 0.083,
     "true_negative_rate": 0.750, "false_positive_rate": 0.250,
     "submitted_nothing_rate": None},
    {"model": "Qwen3.5-35B-A3B", "size": "35B", "type": "open-weights",
     "file_f1": 0.085, "precision": 0.115, "recall": 0.081,
     "true_negative_rate": 0.740, "false_positive_rate": 0.260,
     "submitted_nothing_rate": None},
    {"model": "GPT-OSS-20B", "size": "20B", "type": "open-weights",
     "file_f1": 0.070, "precision": 0.095, "recall": 0.065,
     "true_negative_rate": 0.719, "false_positive_rate": 0.281,
     "submitted_nothing_rate": None},
    {"model": "GPT-OSS-120B", "size": "120B", "type": "open-weights",
     "file_f1": 0.069, "precision": 0.095, "recall": 0.062,
     "true_negative_rate": 0.720, "false_positive_rate": 0.280,
     "submitted_nothing_rate": None},
    {"model": "MiniMax-M2.7", "size": "229B", "type": "open-weights",
     "file_f1": 0.054, "precision": 0.078, "recall": 0.050,
     "true_negative_rate": 0.321, "false_positive_rate": 0.679,
     "submitted_nothing_rate": 28.4},
    {"model": "GPT-5", "size": "—", "type": "frontier",
     "file_f1": 0.048, "precision": 0.062, "recall": 0.048,
     "true_negative_rate": 0.743, "false_positive_rate": 0.257,
     "submitted_nothing_rate": 69.9},
    {"model": "CodeScout-14B", "size": "14B", "type": "open-weights",
     "file_f1": 0.044, "precision": 0.065, "recall": 0.039,
     "true_negative_rate": 0.563, "false_positive_rate": 0.437,
     "submitted_nothing_rate": None},
    {"model": "Qwen3.5-9B", "size": "9B", "type": "open-weights",
     "file_f1": 0.043, "precision": 0.058, "recall": 0.039,
     "true_negative_rate": 0.814, "false_positive_rate": 0.186,
     "submitted_nothing_rate": None},
    {"model": "Gemma-4-E2B", "size": "2B", "type": "open-weights",
     "file_f1": 0.039, "precision": 0.045, "recall": 0.042,
     "true_negative_rate": 0.755, "false_positive_rate": 0.245,
     "submitted_nothing_rate": None},
    {"model": "Gemma-4-E4B", "size": "4B", "type": "open-weights",
     "file_f1": 0.034, "precision": 0.039, "recall": 0.034,
     "true_negative_rate": 0.845, "false_positive_rate": 0.155,
     "submitted_nothing_rate": None},
    {"model": "Llama-3.3-70B", "size": "70B", "type": "open-weights",
     "file_f1": 0.012, "precision": 0.016, "recall": 0.014,
     "true_negative_rate": 0.745, "false_positive_rate": 0.255,
     "submitted_nothing_rate": None},
    {"model": "GPT-5-Nano", "size": "—", "type": "frontier",
     "file_f1": 0.024, "precision": 0.038, "recall": 0.021,
     "true_negative_rate": 0.868, "false_positive_rate": 0.132,
     "submitted_nothing_rate": 86.0},
    {"model": "Granite-4.0-350M", "size": "350M", "type": "open-weights",
     "file_f1": 0.001, "precision": 0.001, "recall": 0.001,
     "true_negative_rate": None, "false_positive_rate": None,
     "submitted_nothing_rate": None},
    {"model": "Granite-4.0-Micro", "size": "3B", "type": "open-weights",
     "file_f1": 0.000, "precision": 0.000, "recall": 0.000,
     "true_negative_rate": None, "false_positive_rate": None,
     "submitted_nothing_rate": None},
    {"model": "Granite-4.0-1B", "size": "1B", "type": "open-weights",
     "file_f1": 0.000, "precision": 0.000, "recall": 0.000,
     "true_negative_rate": None, "false_positive_rate": None,
     "submitted_nothing_rate": None},
]


def _parse_leaderboard_entries(entries: list) -> pd.DataFrame:
    rows = []
    for entry in entries:
        rows.append({
            "lb_model": entry.get("model", ""),
            "lb_size": entry.get("size", ""),
            "lb_type": entry.get("type", ""),
            "lb_file_f1": entry.get("file_f1"),
            "lb_precision": entry.get("precision"),
            "lb_recall": entry.get("recall"),
            "lb_true_negative_rate": entry.get("true_negative_rate"),
            "lb_false_positive_rate": entry.get("false_positive_rate"),
            "lb_submitted_nothing_rate": entry.get(
                "submitted_nothing_rate"
            ),
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=3600)
def load_leaderboard() -> tuple:
    """Fetch the upstream VLoc leaderboard JSON.

    Returns (DataFrame, source_label) where source_label is either
    "live" or "cached" so the caller can inform the user.
    The JSON envelope is {"note": "...", "models": [...]}.
    Falls back to an embedded snapshot when the network is unavailable.
    """
    try:
        with urllib.request.urlopen(
            LEADERBOARD_JSON_URL, timeout=8
        ) as resp:
            raw = json.loads(resp.read())
        # Unwrap envelope: top-level may be a dict with a "models" key
        if isinstance(raw, dict):
            entries = raw.get("models", [])
        elif isinstance(raw, list):
            entries = raw
        else:
            entries = []
        if entries:
            return _parse_leaderboard_entries(entries), "live"
    except Exception:
        pass

    return _parse_leaderboard_entries(_FALLBACK_LEADERBOARD), "cached"


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _bar_chart(
    labels: list,
    values: list,
    title: str,
    yaxis_title: str,
    color: str,
    hover_fmt: str = "%{y:.3f}",
    height: int = 400,
) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        text=[f"{v:.3f}" if v is not None else "—" for v in values],
        textposition="auto",
        marker_color=color,
        hovertemplate=f"<b>%{{x}}</b><br>{yaxis_title}: {hover_fmt}<extra></extra>",
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Model",
        yaxis_title=yaxis_title,
        yaxis=dict(range=[0, 1]),
        height=height,
        showlegend=False,
    )
    return fig


# File F1 bands for the leaderboard. Each chart gets its own y-axis so a
# 0.002 Granite score is not flattened against a 0.22 GPT-class score.
_F1_BANDS = [
    {
        "title": "High File F1 (≥ 0.15) — models that actually find the files",
        "lo": 0.15,
        "hi": None,
        "y_floor": 0.30,
    },
    {
        "title": "Mid File F1 (0.05–0.15) — partial localization",
        "lo": 0.05,
        "hi": 0.15,
        "y_floor": 0.16,
    },
    {
        "title": "Low File F1 (< 0.05) — near-zero / untrained baseline",
        "lo": None,
        "hi": 0.05,
        "y_floor": 0.06,
    },
]


def _in_f1_band(score, lo, hi) -> bool:
    if score is None or pd.isna(score):
        return False
    if lo is not None and score < lo:
        return False
    if hi is not None and score >= hi:
        return False
    return True


def _leaderboard_band_figure(
    band_df: pd.DataFrame,
    title: str,
    y_floor: float,
) -> go.Figure:
    """Grouped GPU-vs-CPU File F1 bars for one score band."""
    plot_df = band_df.sort_values("lb_file_f1", ascending=False).copy()
    plot_df["xlabel"] = plot_df.apply(
        lambda r: f"★ {r['lb_model']}" if r["has_local"] else r["lb_model"],
        axis=1,
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Leaderboard (GPU)",
        x=plot_df["xlabel"],
        y=plot_df["lb_file_f1"].fillna(0),
        marker_color=_COLORS["leaderboard"],
        opacity=0.75,
        hovertemplate="<b>%{x}</b><br>GPU File F1: %{y:.3f}<extra></extra>",
    ))

    local = plot_df[plot_df["has_local"]]
    if not local.empty:
        fig.add_trace(go.Bar(
            name="Our results (CPU)",
            x=local["xlabel"],
            y=local["local_file_f1"],
            text=[f"{v:.3f}" for v in local["local_file_f1"]],
            textposition="auto",
            marker_color=_COLORS["local"],
            marker_line=dict(width=1.5, color="#08306b"),
            hovertemplate="<b>%{x}</b><br>CPU File F1: %{y:.3f}<extra></extra>",
        ))

    y_vals = plot_df["lb_file_f1"].dropna().tolist()
    if not local.empty:
        y_vals.extend(local["local_file_f1"].dropna().tolist())
    y_max = max(max(y_vals) * 1.2, y_floor) if y_vals else y_floor

    fig.update_layout(
        barmode="group",
        title=title,
        xaxis_title="Model  (★ = we tested this model on CPU)",
        yaxis_title="File F1",
        yaxis=dict(range=[0, y_max]),
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_tickangle=-30,
    )
    return fig


def _render_phase_explainer() -> None:
    """Plain-language Phase A vs Phase B primer for a non-specialist reader."""
    with st.expander("How Phase A and Phase B work", expanded=True):
        st.markdown(
            "We ask the model to act like a security reviewer with a terminal. "
            "Each CVE is tested **twice**, with the same bug description, on two "
            "versions of the same project:"
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                """
**Phase A — Find the bug**

We hand the model a project that **still contains** a known security hole
and ask: *which files is it in?*

- **Right answer:** name the vulnerable files.
- **Wrong answers:** stay silent, or point at the wrong files.
- **Score:** File F1 (1.0 = found every vulnerable file and named no extras).
"""
            )
        with col_b:
            st.markdown(
                """
**Phase B — Don't cry wolf**

We hand the model the **same project after the hole has been patched**
and ask: *is anything still wrong?*

- **Right answer:** say *no vulnerability found*.
- **Wrong answer:** still flag the patched files (a false alarm).
- **Score:** True Negative Rate (1.0 = correctly cleared every patched repo).
"""
            )
        st.markdown(
            """
**A useful model needs both skills.** Finding real bugs (Phase A) and staying
quiet once they are fixed (Phase B) are different tests. A high score on only
one phase is not a passing grade.

**Why a quiet model can look great on Phase B:** if a model almost never
reports a vulnerability, Phase A collapses (it never finds the bug) but
Phase B looks strong (saying "nothing found" is the correct answer on
patched code). That pattern is expected for untrained baselines such as
Granite-4.0. The opposite pattern — hunting aggressively — raises Phase A
and then over-flags patched code on Phase B.
"""
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="CVE Vulnerability Localization",
        page_icon="🔍",
        layout="wide",
    )

    st.title("🔍 CVE Vulnerability Localization (VLoc Bench)")
    st.markdown(
        "Quality and throughput results from the Cisco VLoc Bench "
        "agent-loop evaluation. Each CVE is scored twice: **Phase A** (find "
        "the still-vulnerable files) and **Phase B** (recognize that the "
        "patch already fixed it). Higher File F1 and True Negative Rate "
        "are better — but they measure different skills, so they are not "
        "interchangeable."
    )
    _render_phase_explainer()

    # ------------------------------------------------------------------
    # Sidebar — configuration
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("Configuration")

        config = DashboardConfig()
        default_results_dir = str(Path(config.get_results_directory()))

        results_dir_input = st.text_input(
            "Results Directory",
            value=default_results_dir,
            help="Path to the results/llm directory",
            key="results_dir_cve",
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()
            st.rerun()

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    df = load_cve_results(results_dir_input)

    if df.empty:
        st.warning("No CVE-VLoc results found.")
        st.code(
            "# Run a CVE-VLoc benchmark (from repository root):\n"
            "./cpueval --suite cve-vloc --model ibm-granite/granite-4.0-350m\n"
            "\n"
            "# Or via Ansible:\n"
            "ansible-playbook automation/test-execution/ansible/"
            "llm-benchmark-cve-vloc.yml \\\n"
            '  -e "test_model=ibm-granite/granite-4.0-350m"\n'
            '  -e "requested_cores=16"'
        )
        return

    st.success(f"Loaded {len(df)} CVE-VLoc test run(s)")

    # ------------------------------------------------------------------
    # Sidebar — filters (after data loaded)
    # ------------------------------------------------------------------
    with st.sidebar:
        st.markdown("---")
        st.header("Filters")

        all_models = sorted(df["model_short"].unique().tolist())
        sel_models = st.multiselect(
            "Model", options=all_models, default=all_models, key="cve_models"
        )
        if not sel_models:
            sel_models = all_models

        all_phases = sorted(df["vloc_phases"].unique().tolist())
        sel_phases = st.multiselect(
            "Phases run", options=all_phases, default=all_phases, key="cve_phases"
        )
        if not sel_phases:
            sel_phases = all_phases

        all_cores = sorted(df["cores"].unique().tolist())
        sel_cores = st.multiselect(
            "Cores", options=all_cores, default=all_cores, key="cve_cores"
        )
        if not sel_cores:
            sel_cores = all_cores

        if df["vllm_version"].nunique() > 1:
            all_versions = sorted(df["vllm_version"].unique().tolist())
            sel_versions = st.multiselect(
                "vLLM Version",
                options=all_versions,
                default=all_versions,
                key="cve_versions",
            )
            if not sel_versions:
                sel_versions = all_versions
        else:
            sel_versions = df["vllm_version"].unique().tolist()

        st.markdown("---")
        show_leaderboard = st.checkbox(
            "Compare to upstream leaderboard",
            value=True,
            help="Fetch reference scores from the VLoc Bench leaderboard",
        )

    # Apply filters
    dff = df[
        df["model_short"].isin(sel_models)
        & df["vloc_phases"].isin(sel_phases)
        & df["cores"].isin(sel_cores)
        & df["vllm_version"].isin(sel_versions)
    ].copy()

    if dff.empty:
        st.warning("No results match the current filters.")
        return

    # Environment banner
    unique_versions = dff["vllm_version"].unique()
    unique_containers = dff["container_image"].unique()
    if len(unique_versions) > 1 or len(unique_containers) > 1:
        st.warning(
            f"**Mixed environments** — {len(unique_containers)} container "
            f"image(s), {len(unique_versions)} vLLM version(s). "
            "Compare with care."
        )
    else:
        container_short = (
            unique_containers[0].split("/")[-1]
            if len(unique_containers) > 0
            else "unknown"
        )
        ver = unique_versions[0] if len(unique_versions) > 0 else "unknown"
        st.info(f"🐳 **Environment**: {container_short} (vLLM {ver})")

    # Best run per model (highest mean_file_f1 among all runs for that model)
    best_per_model = (
        dff.sort_values("mean_file_f1", ascending=False)
        .groupby("model_short", sort=False)
        .first()
        .reset_index()
    )

    # ==================================================================
    # KPI SUMMARY
    # ==================================================================
    st.header("📊 Summary")

    n_models = dff["model_short"].nunique()
    n_runs = len(dff)
    best_f1 = dff["mean_file_f1"].max()
    best_model = dff.loc[dff["mean_file_f1"].idxmax(), "model_short"] if best_f1 is not None else "—"

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Models Tested", n_models)
    kpi2.metric("Total Runs", n_runs)
    kpi3.metric("Best File F1", f"{best_f1:.3f}" if best_f1 is not None else "—")
    kpi4.metric("Best Model", best_model)
    st.caption(
        "Best File F1 and Best Model are **Phase A** scores (did the model "
        "find the vulnerable files?). They do not include Phase B "
        "(did it stay quiet on already-patched code?)."
    )

    # ==================================================================
    # SECTION 1: Quality — File F1
    # ==================================================================
    st.divider()
    st.subheader("1️⃣ Localization Quality — File F1 (Phase A)")
    st.markdown(
        "Phase A is the **find-the-bug** test: the vulnerability is still "
        "in the code, and the model must name the right files. "
        "File F1 is the harmonic mean of precision (were the files it named "
        "actually vulnerable?) and recall (did it find all of them?). "
        "A score of 1.0 means it identified every vulnerable file and "
        "submitted no extras. Silence counts as a miss (File F1 = 0)."
    )

    # Latest run per model (use best F1 for comparison)
    f1_data = (
        best_per_model[["model_short", "mean_file_f1", "abstain_rate"]]
        .sort_values("mean_file_f1", ascending=False)
    )

    fig_f1 = go.Figure()
    fig_f1.add_trace(go.Bar(
        name="File F1",
        x=f1_data["model_short"],
        y=f1_data["mean_file_f1"].fillna(0),
        text=[f"{v:.3f}" for v in f1_data["mean_file_f1"].fillna(0)],
        textposition="auto",
        marker_color=_COLORS["file_f1"],
        hovertemplate="<b>%{x}</b><br>File F1: %{y:.3f}<extra></extra>",
    ))
    fig_f1.add_trace(go.Bar(
        name="Abstain Rate",
        x=f1_data["model_short"],
        y=f1_data["abstain_rate"].fillna(0),
        text=[f"{v:.2%}" for v in f1_data["abstain_rate"].fillna(0)],
        textposition="auto",
        marker_color=_COLORS["abstain"],
        opacity=0.6,
        hovertemplate="<b>%{x}</b><br>Abstain Rate: %{y:.2%}<extra></extra>",
    ))
    fig_f1.update_layout(
        barmode="group",
        xaxis_title="Model",
        yaxis_title="Score (0–1)",
        yaxis=dict(range=[0, 1]),
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_f1, use_container_width=True)
    st.caption(
        "**Abstain Rate** (red) = fraction of tasks where the model submitted "
        "nothing. File F1 is 0 on those tasks. A high abstain rate usually "
        "means the model has not been trained to use the terminal tools this "
        "benchmark requires — it never starts the search, so it cannot find "
        "the bug."
    )

    # ==================================================================
    # SECTION 2: Phase B — True Negative Rate
    # ==================================================================
    phase_b_data = best_per_model[
        best_per_model["true_negative_rate"].notna()
        & (best_per_model["phase_b_tasks"] > 0)
    ]

    if not phase_b_data.empty:
        st.divider()
        st.subheader("2️⃣ False Positive Resistance — True Negative Rate (Phase B)")
        st.markdown(
            "Phase B is the **don't-cry-wolf** test: the same project, after "
            "the bug has already been patched. A True Negative means the "
            "model correctly declared *no vulnerability found*. "
            "A False Positive means it still flagged the fixed code as "
            "vulnerable. High TNR is good — but only if Phase A is also good. "
            "A model that never reports a bug will ace Phase B and fail Phase A."
        )

        tnr_data = phase_b_data.sort_values("true_negative_rate", ascending=False)

        fig_tnr = go.Figure()
        fig_tnr.add_trace(go.Bar(
            name="True Negative Rate",
            x=tnr_data["model_short"],
            y=tnr_data["true_negative_rate"].fillna(0),
            text=[f"{v:.3f}" for v in tnr_data["true_negative_rate"].fillna(0)],
            textposition="auto",
            marker_color=_COLORS["tnr"],
            hovertemplate="<b>%{x}</b><br>TNR: %{y:.3f}<extra></extra>",
        ))
        if "false_positive_rate" in tnr_data.columns:
            fig_tnr.add_trace(go.Bar(
                name="False Positive Rate",
                x=tnr_data["model_short"],
                y=tnr_data["false_positive_rate"].fillna(0),
                text=[f"{v:.3f}" for v in tnr_data["false_positive_rate"].fillna(0)],
                textposition="auto",
                marker_color=_COLORS["abstain"],
                opacity=0.6,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "False Positive Rate: %{y:.3f}<extra></extra>"
                ),
            ))
        fig_tnr.update_layout(
            barmode="group",
            xaxis_title="Model",
            yaxis_title="Rate (0–1)",
            yaxis=dict(range=[0, 1]),
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_tnr, use_container_width=True)

    # ==================================================================
    # SECTION 3: Leaderboard Comparison
    # ==================================================================
    if show_leaderboard:
        st.divider()
        st.subheader("3️⃣ Upstream Leaderboard Context")
        st.caption(
            "This section is Phase A File F1 only — the same skill as chart 1, "
            "compared with the published GPU leaderboard. It is not a Phase B "
            "ranking."
        )

        lb_df, lb_source = load_leaderboard()

        if lb_source == "cached":
            st.info(
                "ℹ️ Network unavailable — using embedded leaderboard "
                "snapshot (fetched 2026-08-11). "
                "Restart the dashboard with network access to refresh."
            )

        if not lb_df.empty:
            # Build a combined view: all leaderboard models + our local results
            # annotated with whether we ran them
            local_scores: Dict[str, float] = {}
            for _, row in best_per_model.iterrows():
                lb_name = row["leaderboard_name"]
                f1 = row["mean_file_f1"]
                if lb_name and f1 is not None:
                    # Keep the best local score if model appears multiple times
                    if lb_name not in local_scores or f1 > local_scores[lb_name]:
                        local_scores[lb_name] = f1

            # Merge leaderboard with local scores
            lb_df["local_file_f1"] = lb_df["lb_model"].map(local_scores)
            lb_df["has_local"] = lb_df["local_file_f1"].notna()

            st.markdown(
                "The published leaderboard is a **Phase A File F1** ranking "
                "(GPU). One chart cannot show both a 0.22 GPT-class score and "
                "a 0.002 Granite score without flattening the models we "
                "actually ran. The three charts below group models by score "
                "band; each band has its own vertical scale. ★ marks models "
                "we tested on CPU. Placement follows File F1, not Phase B "
                "TNR — Granite belongs in the low band here even when its "
                "Phase B score is high."
            )

            tested = lb_df[lb_df["has_local"]].copy()
            if not tested.empty:
                def _band_label(score) -> str:
                    if _in_f1_band(score, 0.15, None):
                        return "High (≥ 0.15)"
                    if _in_f1_band(score, 0.05, 0.15):
                        return "Mid (0.05–0.15)"
                    return "Low (< 0.05)"

                tested["band"] = tested["lb_file_f1"].apply(_band_label)
                locations = ", ".join(
                    f"**{row['lb_model']}** → {row['band']}"
                    for _, row in tested.sort_values(
                        "lb_file_f1", ascending=False
                    ).iterrows()
                )
                st.markdown(f"Where our tested models sit: {locations}.")

            for band in _F1_BANDS:
                band_df = lb_df[
                    lb_df["lb_file_f1"].apply(
                        lambda s, lo=band["lo"], hi=band["hi"]: _in_f1_band(
                            s, lo, hi
                        )
                    )
                ]
                if band_df.empty:
                    continue
                fig_lb = _leaderboard_band_figure(
                    band_df, band["title"], band["y_floor"]
                )
                st.plotly_chart(fig_lb, use_container_width=True)

            st.caption(
                "Purple bars = leaderboard reference scores (GPU). "
                "Blue bars = our CPU results on the same model (★). "
                "CPU scores may differ from GPU reference due to "
                "different n_limit, temperature sensitivity, and inference speed. "
                "These charts are Phase A File F1 only — they do not rank "
                "Phase B (don't-cry-wolf) performance."
            )

            # Leaderboard table with local score column
            with st.expander("📋 Full leaderboard table", expanded=False):
                display_lb = lb_df[
                    ["lb_model", "lb_size", "lb_type", "lb_file_f1",
                     "lb_true_negative_rate", "lb_submitted_nothing_rate",
                     "local_file_f1"]
                ].copy()
                display_lb.columns = [
                    "Model", "Size", "Type", "File F1 (LB)",
                    "TNR (LB)", "Abstain Rate (LB)", "File F1 (Our CPU)"
                ]
                display_lb = display_lb.sort_values("File F1 (LB)", ascending=False)
                for col in ["File F1 (LB)", "TNR (LB)", "Abstain Rate (LB)", "File F1 (Our CPU)"]:
                    display_lb[col] = display_lb[col].apply(
                        lambda v: f"{v:.3f}" if pd.notna(v) else "—"
                    )
                st.dataframe(display_lb, hide_index=True, use_container_width=True)

            # Delta table — only models we tested
            matched = lb_df[lb_df["has_local"]].copy()
            if not matched.empty:
                st.markdown("**Score delta for tested models:**")
                matched["delta"] = matched["local_file_f1"] - matched["lb_file_f1"]
                delta_cols = ["lb_model", "lb_file_f1", "local_file_f1", "delta"]
                delta_df = matched[delta_cols].copy()
                delta_df.columns = ["Model", "LB File F1 (GPU)", "Our File F1 (CPU)", "Delta"]
                delta_df = delta_df.sort_values("Our File F1 (CPU)", ascending=False)
                st.dataframe(
                    delta_df.style.format({
                        "LB File F1 (GPU)": "{:.3f}",
                        "Our File F1 (CPU)": "{:.3f}",
                        "Delta": "{:+.3f}",
                    }).applymap(
                        lambda v: "color: green" if isinstance(v, float) and v >= 0
                        else ("color: red" if isinstance(v, float) and v < 0 else ""),
                        subset=["Delta"],
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
                st.caption(
                    "Positive delta = our CPU result exceeds the GPU "
                    "leaderboard for that model. "
                    "Negative delta is expected for n_limit smoke tests "
                    "(fewer tasks = noisier score)."
                )

    # ==================================================================
    # SECTION 4: Throughput
    # ==================================================================
    st.divider()
    st.subheader("4️⃣ Throughput — Tasks per Hour")
    st.markdown(
        "Higher tasks/hr means the model completes the agent loop faster "
        "per CVE task (driven by inference speed on CPU)."
    )

    tput_data = (
        dff[dff["tasks_per_hour"].notna()]
        .groupby(["model_short", "cores"])["tasks_per_hour"]
        .mean()
        .reset_index()
    )
    tput_data["label"] = (
        tput_data["model_short"] + "\n" + tput_data["cores"].astype(str) + " cores"
    )
    tput_data = tput_data.sort_values("tasks_per_hour", ascending=False)

    if not tput_data.empty:
        fig_tput = go.Figure(go.Bar(
            x=tput_data["label"],
            y=tput_data["tasks_per_hour"],
            text=tput_data["tasks_per_hour"].round(1),
            textposition="auto",
            marker_color=_COLORS["throughput"],
            hovertemplate="<b>%{x}</b><br>Tasks/hr: %{y:.1f}<extra></extra>",
        ))
        fig_tput.update_layout(
            xaxis_title="Configuration",
            yaxis_title="Tasks per Hour",
            height=380,
            showlegend=False,
        )
        st.plotly_chart(fig_tput, use_container_width=True)
        st.caption(
            "Smaller models complete tasks faster but may trade quality for speed. "
            "Tasks/hr is a function of model size, CPU cores, and n_limit."
        )
    else:
        st.info("No throughput data available in current results.")

    # ==================================================================
    # SECTION 5: All Runs Table
    # ==================================================================
    st.divider()
    with st.expander("📋 All Runs — Raw Results", expanded=False):
        display_cols = {
            "model_short": "Model",
            "vloc_phases": "Phases",
            "cores": "Cores",
            "workers": "Workers",
            "n_limit": "N Limit",
            "mean_file_f1": "File F1",
            "abstain_rate": "Abstain Rate",
            "true_negative_rate": "TNR",
            "false_positive_rate": "FP Rate",
            "tasks_completed": "Tasks Done",
            "phase_a_tasks": "Phase A",
            "phase_b_tasks": "Phase B",
            "tasks_per_hour": "Tasks/hr",
            "vllm_version": "vLLM Ver.",
            "test_run_id": "Run ID",
        }
        avail = {k: v for k, v in display_cols.items() if k in dff.columns}
        show_df = dff[list(avail.keys())].copy()
        show_df.columns = list(avail.values())

        for col in ["File F1", "Abstain Rate", "TNR", "FP Rate"]:
            if col in show_df.columns:
                show_df[col] = show_df[col].apply(
                    lambda v: round(v, 4) if pd.notna(v) else None
                )
        if "Tasks/hr" in show_df.columns:
            show_df["Tasks/hr"] = show_df["Tasks/hr"].apply(
                lambda v: round(v, 1) if pd.notna(v) else None
            )

        st.dataframe(
            show_df.sort_values(["Model", "Run ID"]),
            hide_index=True,
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
