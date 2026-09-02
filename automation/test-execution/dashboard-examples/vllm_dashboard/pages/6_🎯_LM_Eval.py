"""LM Evaluation Harness Accuracy Dashboard.

Displays accuracy results from lm-eval benchmarks run against vLLM CPU.
Metrics: acc (accuracy) and acc_norm (length-normalised accuracy) per task.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TASK_LABELS = {
    "hellaswag": "HellaSwag",
    "winogrande": "WinoGrande",
    "arc_easy": "ARC-Easy",
    "arc_challenge": "ARC-Challenge",
    "mmlu": "MMLU",
    "truthfulqa_mc1": "TruthfulQA (MC1)",
    "truthfulqa_mc2": "TruthfulQA (MC2)",
    "gsm8k": "GSM8K",
    "piqa": "PIQA",
    "boolq": "BoolQ",
}

METRIC_OPTIONS = {
    "acc,none": "Accuracy (acc)",
    "acc_norm,none": "Normalised Accuracy (acc_norm)",
}

PLOTLY_COLORS = px.colors.qualitative.Safe


# ---------------------------------------------------------------------------
# Data loading helpers (no Streamlit dependency — unit-testable)
# ---------------------------------------------------------------------------

def _find_lm_eval_results(run_dir: Path) -> Optional[dict]:
    """Return the first lm-eval results JSON found in *run_dir*, or None."""
    # lm-eval writes results_<timestamp>.json or results/<timestamp>.json
    for candidate in sorted(run_dir.glob("results*.json")):
        try:
            with open(candidate) as f:
                data = json.load(f)
            if "results" in data and isinstance(data["results"], dict):
                return data
        except (json.JSONDecodeError, OSError):
            continue
    # Some versions write a nested structure
    for candidate in sorted(run_dir.rglob("*.json")):
        if candidate.name == "test-metadata.json":
            continue
        try:
            with open(candidate) as f:
                data = json.load(f)
            if "results" in data and isinstance(data["results"], dict):
                return data
        except (json.JSONDecodeError, OSError):
            continue
    return None


def load_lm_eval_data(results_dir: str) -> pd.DataFrame:
    """Load all lm-eval benchmark results from *results_dir*.

    Directory layout expected:
      <results_dir>/<model_slug>/<test_run_id>/
        test-metadata.json
        results_<timestamp>.json   (from lm-evaluation-harness)
    """
    records: List[dict] = []
    root = Path(results_dir)

    if not root.exists():
        return pd.DataFrame()

    for model_dir in root.iterdir():
        if not model_dir.is_dir():
            continue
        model_id = model_dir.name.replace("__", "/")

        for run_dir in model_dir.iterdir():
            if not run_dir.is_dir():
                continue

            metadata_file = run_dir / "test-metadata.json"
            if not metadata_file.exists():
                continue

            try:
                with open(metadata_file) as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            lm_results = _find_lm_eval_results(run_dir)
            if lm_results is None:
                continue

            cores = int(meta.get("requested_cores", 0))
            platform = meta.get("platform", "unknown")
            timestamp = meta.get("timestamp", "")
            test_run_id = meta.get("test_run_id", run_dir.name)
            limit = meta.get("limit", "none")
            dtype = meta.get("dtype", "bfloat16")

            for task, task_metrics in lm_results["results"].items():
                row = {
                    "model": model_id,
                    "model_short": model_id.split("/")[-1],
                    "cores": cores,
                    "platform": platform,
                    "timestamp": timestamp,
                    "test_run_id": test_run_id,
                    "task": task,
                    "task_label": TASK_LABELS.get(task, task),
                    "limit": limit,
                    "dtype": dtype,
                }
                for metric_key, metric_val in task_metrics.items():
                    if isinstance(metric_val, (int, float)):
                        row[metric_key] = metric_val
                records.append(row)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def _accuracy_bar(
    df: pd.DataFrame,
    metric: str,
    title: str,
    color_by: str = "model_short",
) -> go.Figure:
    """Grouped bar chart of accuracy by task, coloured by *color_by*."""
    groups = df[color_by].unique().tolist()
    color_map = {g: PLOTLY_COLORS[i % len(PLOTLY_COLORS)] for i, g in enumerate(groups)}

    fig = go.Figure()
    for group in groups:
        sub = df[df[color_by] == group].sort_values("task_label")
        if metric not in sub.columns:
            continue
        stderr_col = metric.replace(",none", "_stderr,none")
        error_y = sub[stderr_col].tolist() if stderr_col in sub.columns else None
        fig.add_trace(go.Bar(
            name=group,
            x=sub["task_label"],
            y=sub[metric],
            error_y=dict(type="data", array=error_y) if error_y else None,
            text=[_pct(v) for v in sub[metric]],
            textposition="auto",
            marker_color=color_map[group],
            hovertemplate=(
                f"<b>{group}</b><br>"
                "Task: %{x}<br>"
                "Score: %{text}<br>"
                "<extra></extra>"
            ),
        ))
    fig.update_layout(
        title=title,
        barmode="group",
        xaxis_title="Task",
        yaxis_title="Score",
        yaxis=dict(range=[0, 1.05], tickformat=".0%"),
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="LM Eval Accuracy",
        page_icon="🎯",
        layout="wide",
    )

    st.title("🎯 LM Evaluation Harness — Accuracy")
    st.markdown(
        "Accuracy benchmarks (hellaswag, winogrande, arc, mmlu, …) "
        "run against vLLM CPU via "
        "[lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness)."
    )

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("Configuration")

        config = DashboardConfig()
        default_dir = config.get_lm_eval_results_directory()

        results_dir = st.text_input(
            "Results Directory",
            value=default_dir,
            help="Path to lm-eval results (results/lm-eval/)",
            key="lm_eval_results_dir",
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()
            st.rerun()

    @st.cache_data(ttl=3600)
    def _load(path: str) -> pd.DataFrame:
        return load_lm_eval_data(path)

    df = _load(results_dir)

    if df.empty:
        st.warning(
            "No lm-eval results found. "
            f"Expected directory: `{results_dir}`"
        )
        st.code(
            "# Quick smoke test (single model, 50 examples per task)\n"
            "./cpueval --suite lm-eval --models quick --cores 8 --limit 50\n"
            "\n"
            "# Full accuracy sweep\n"
            "./cpueval --suite lm-eval\n"
            "\n"
            "# Or via bash script:\n"
            "automation/test-execution/scripts/bash/run-lm-eval-suite.sh "
            "--models small --cores 8 --limit 100",
        )
        return

    # ------------------------------------------------------------------
    # Sidebar filters (populated after data loads)
    # ------------------------------------------------------------------
    with st.sidebar:
        st.markdown("---")
        st.header("Filters")

        all_models = sorted(df["model_short"].unique())
        sel_models = st.multiselect(
            "Model", options=all_models, default=all_models
        )
        if not sel_models:
            sel_models = all_models

        all_tasks = sorted(df["task_label"].unique())
        sel_tasks = st.multiselect(
            "Task", options=all_tasks, default=all_tasks
        )
        if not sel_tasks:
            sel_tasks = all_tasks

        all_cores = sorted(df["cores"].unique())
        sel_cores = st.multiselect(
            "Cores", options=all_cores, default=all_cores
        )
        if not sel_cores:
            sel_cores = all_cores

        metric_key = st.selectbox(
            "Metric",
            options=list(METRIC_OPTIONS.keys()),
            format_func=lambda k: METRIC_OPTIONS[k],
        )

        # Warn if results include limited (--limit) runs
        limits = df["limit"].unique()
        if any(str(lim) not in ("none", "") for lim in limits):
            st.warning(
                "⚠️ Some runs used `--limit`. "
                "Scores may not represent full dataset accuracy."
            )

    df_f = df[
        df["model_short"].isin(sel_models)
        & df["task_label"].isin(sel_tasks)
        & df["cores"].isin(sel_cores)
    ].copy()

    if df_f.empty:
        st.warning("No results match the current filters.")
        return

    n_runs = df_f["test_run_id"].nunique()
    n_models = df_f["model_short"].nunique()
    n_tasks = df_f["task_label"].nunique()
    st.success(
        f"Loaded **{n_runs}** run(s) · "
        f"**{n_models}** model(s) · "
        f"**{n_tasks}** task(s)"
    )

    # ------------------------------------------------------------------
    # Section 1: Task accuracy by model
    # ------------------------------------------------------------------
    st.header("1️⃣ Accuracy by Task")

    # Use the latest run per model+task+cores to avoid double-counting
    df_latest = (
        df_f.sort_values("timestamp")
        .groupby(["model_short", "task_label", "cores"], dropna=False)
        .last()
        .reset_index()
    )

    if metric_key in df_latest.columns:
        # Average across core counts when multiple are present
        df_avg = (
            df_latest.groupby(["model_short", "task_label"])[metric_key]
            .mean()
            .reset_index()
        )
        df_avg["task_label"] = df_avg["task_label"]

        fig1 = _accuracy_bar(
            df_avg,
            metric_key,
            title=f"{METRIC_OPTIONS[metric_key]} by Task",
            color_by="model_short",
        )
        st.plotly_chart(fig1, use_container_width=True)

        if len(sel_cores) > 1:
            st.caption(
                "Scores are averaged across selected core counts "
                "(accuracy should not vary with core count — "
                "any variation indicates non-determinism or "
                "different random seeds)."
            )
    else:
        st.info(
            f"Metric `{metric_key}` not found in results. "
            "Some tasks only report `acc,none`."
        )

    # ------------------------------------------------------------------
    # Section 2: Model comparison on a single task
    # ------------------------------------------------------------------
    st.divider()
    st.header("2️⃣ Model Comparison")
    st.markdown("Compare models on a single task across core counts.")

    col1, col2 = st.columns(2)
    with col1:
        cmp_task = st.selectbox(
            "Task", options=all_tasks, key="cmp_task"
        )
    with col2:
        cmp_metric = st.selectbox(
            "Metric",
            options=list(METRIC_OPTIONS.keys()),
            format_func=lambda k: METRIC_OPTIONS[k],
            key="cmp_metric",
        )

    df_cmp = df_latest[df_latest["task_label"] == cmp_task].copy()

    if not df_cmp.empty and cmp_metric in df_cmp.columns:
        df_cmp_g = (
            df_cmp.groupby(["model_short", "cores"])[cmp_metric]
            .mean()
            .reset_index()
        )
        df_cmp_g["cores_label"] = df_cmp_g["cores"].astype(str) + " cores"

        models_in_task = sorted(df_cmp_g["model_short"].unique())
        color_map = {
            m: PLOTLY_COLORS[i % len(PLOTLY_COLORS)]
            for i, m in enumerate(models_in_task)
        }

        if df_cmp_g["cores"].nunique() > 1:
            fig2 = go.Figure()
            for model in models_in_task:
                sub = df_cmp_g[df_cmp_g["model_short"] == model].sort_values("cores")
                fig2.add_trace(go.Scatter(
                    x=sub["cores"],
                    y=sub[cmp_metric],
                    mode="lines+markers",
                    name=model,
                    line=dict(width=2, color=color_map[model]),
                    marker=dict(size=9),
                    hovertemplate=(
                        f"<b>{model}</b><br>"
                        "Cores: %{x}<br>"
                        f"Score: %{{y:.3f}}<br>"
                        "<extra></extra>"
                    ),
                ))
            fig2.update_layout(
                xaxis_title="CPU Cores",
                yaxis_title=METRIC_OPTIONS[cmp_metric],
                yaxis=dict(range=[0, 1.05], tickformat=".0%"),
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig2, use_container_width=True)
            st.caption(
                "Accuracy should be stable across core counts for a "
                "given model — a consistent spread indicates genuine "
                "model differences, not measurement noise."
            )
        else:
            # Single core count — horizontal bar chart
            df_cmp_g = df_cmp_g.sort_values(cmp_metric, ascending=True)
            fig2b = go.Figure(go.Bar(
                x=df_cmp_g[cmp_metric],
                y=df_cmp_g["model_short"],
                orientation="h",
                text=[_pct(v) for v in df_cmp_g[cmp_metric]],
                textposition="auto",
                marker_color=[
                    color_map[m] for m in df_cmp_g["model_short"]
                ],
            ))
            fig2b.update_layout(
                xaxis_title=METRIC_OPTIONS[cmp_metric],
                xaxis=dict(range=[0, 1.05], tickformat=".0%"),
                yaxis_title="Model",
                height=max(300, len(models_in_task) * 50),
                showlegend=False,
            )
            st.plotly_chart(fig2b, use_container_width=True)
    else:
        st.info("No data for the selected task/metric combination.")

    # ------------------------------------------------------------------
    # Section 3: Heatmap — model × task
    # ------------------------------------------------------------------
    if metric_key in df_latest.columns and n_models > 1 and n_tasks > 1:
        st.divider()
        st.header("3️⃣ Accuracy Heatmap")

        pivot = (
            df_latest.groupby(["model_short", "task_label"])[metric_key]
            .mean()
            .unstack(level="task_label")
            .fillna(float("nan"))
        )

        fig3 = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            text=[
                [_pct(v) if not pd.isna(v) else "—" for v in row]
                for row in pivot.values
            ],
            texttemplate="%{text}",
            colorscale="RdYlGn",
            zmin=0,
            zmax=1,
            colorbar=dict(title="Score", tickformat=".0%"),
            hovertemplate=(
                "Model: %{y}<br>Task: %{x}<br>Score: %{text}<extra></extra>"
            ),
        ))
        fig3.update_layout(
            xaxis_title="Task",
            yaxis_title="Model",
            height=max(300, n_models * 60 + 100),
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ------------------------------------------------------------------
    # Detailed results table
    # ------------------------------------------------------------------
    st.divider()
    with st.expander("📋 All Results", expanded=False):
        display_cols: Dict[str, str] = {
            "model_short": "Model",
            "task_label": "Task",
            "cores": "Cores",
        }
        for mk, mlabel in METRIC_OPTIONS.items():
            if mk in df_latest.columns:
                display_cols[mk] = mlabel
        stderr_cols = {
            k.replace(",none", "_stderr,none"): f"±{v}"
            for k, v in METRIC_OPTIONS.items()
        }
        for sc, slabel in stderr_cols.items():
            if sc in df_latest.columns:
                display_cols[sc] = slabel

        display_cols["platform"] = "Platform"
        display_cols["test_run_id"] = "Run ID"

        avail = {k: v for k, v in display_cols.items() if k in df_latest.columns}
        tbl = df_latest[list(avail.keys())].copy()
        tbl.columns = list(avail.values())

        for col in tbl.columns:
            if tbl[col].dtype in ["float64", "float32"]:
                tbl[col] = tbl[col].map(
                    lambda x: f"{x:.4f}" if pd.notna(x) else "—"
                )

        st.dataframe(
            tbl.sort_values(["Model", "Task", "Cores"]),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
