"""CPU Performance Analysis Dashboard.

Visualizes CPU-specific performance tradeoffs:
- Throughput vs End-to-End Latency
- Throughput vs Interactivity (throughput per concurrent user)

Similar to GPU performance analysis but adapted for CPU metrics.
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path for config_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Dark mode friendly CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_guidellm_data(results_dir: str) -> pd.DataFrame:
    """Load GuideLLM benchmark results from directory structure."""
    results_path = Path(results_dir)
    all_results = []

    if not results_path.exists():
        logger.warning(f"Results directory not found: {results_path}")
        return pd.DataFrame()

    # Scan for all benchmarks.json files
    for json_file in results_path.rglob("benchmarks.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)

            # Load metadata
            metadata_file = json_file.parent / "test-metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file) as f:
                metadata = json.load(f)

            # Extract each benchmark (load point)
            for bench in data.get('benchmarks', []):
                metrics = bench['metrics']
                config = bench['config']

                # Extract concurrency/rate
                concurrency = config.get('strategy', {}).get('max_concurrency', 0)
                req_rate = metrics.get('requests_per_second', {}).get('successful', {}).get('mean', concurrency)

                row = {
                    # Metadata
                    'test_run_id': metadata.get('test_run_id', 'unknown'),
                    'test_name': metadata.get('test_name', ''),
                    'platform': metadata.get('platform', 'unknown'),
                    'model': metadata.get('model', 'unknown'),
                    'model_short': metadata.get('model', 'unknown').split('/')[-1],
                    'workload': metadata.get('workload', 'unknown'),
                    'cores': metadata.get('core_count', 0),
                    'backend': metadata.get('backend', 'unknown'),
                    'vllm_version': metadata.get('vllm_version', 'unknown'),
                    'guidellm_version': metadata.get('guidellm_version', 'unknown'),
                    'core_config': metadata.get('core_config_name', 'unknown'),
                    'tensor_parallel': metadata.get('tensor_parallel', 1),
                    'vllm_mode': metadata.get('vllm_mode', 'managed'),

                    # Load characteristics
                    'concurrency': concurrency,
                    'request_rate': req_rate,

                    # Throughput metrics
                    'throughput_mean': metrics['tokens_per_second']['successful']['mean'],

                    # E2E latency metrics (s)
                    'e2e_mean': metrics['request_latency']['successful']['mean'],

                    # Request stats
                    'total_requests': metrics['request_totals']['total'],
                    'successful_requests': metrics['request_totals']['successful'],
                }

                all_results.append(row)

        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
            continue

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results)

    # Calculate efficiency (throughput per core)
    cores = pd.to_numeric(df['cores'], errors='coerce')
    df['throughput_per_core'] = np.where(cores > 0, df['throughput_mean'] / cores, np.nan)

    # Calculate interactivity (throughput per concurrent user)
    concurrency = pd.to_numeric(df['concurrency'], errors='coerce')
    df['interactivity'] = np.where(concurrency > 0, df['throughput_mean'] / concurrency, np.nan)

    # Convert latency to ms for consistency
    df['e2e_latency_ms'] = df['e2e_mean'] * 1000

    return df


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter UI and return filtered DataFrame."""
    st.markdown("### 🔍 Filter your data")

    col1, col2, col3 = st.columns(3)

    with col1:
        platforms = sorted(df['platform'].unique())
        selected_platforms = st.multiselect(
            "Platform",
            platforms,
            default=platforms,
            key="platform_filter_cpu"
        )

    with col2:
        models = sorted(df['model_short'].unique())
        selected_models = st.multiselect(
            "Model",
            models,
            default=models,
            key="model_filter_cpu"
        )

    with col3:
        workloads = sorted(df['workload'].unique())
        selected_workloads = st.multiselect(
            "Workload",
            workloads,
            default=workloads,
            key="workload_filter_cpu"
        )

    col4, col5, col6 = st.columns(3)

    with col4:
        cores = sorted(df['cores'].unique())
        selected_cores = st.multiselect(
            "Core Count",
            cores,
            default=cores,
            key="cores_filter_cpu"
        )

    with col5:
        versions = sorted(df['vllm_version'].unique())
        selected_versions = st.multiselect(
            "vLLM Version",
            versions,
            default=versions,
            key="version_filter_cpu"
        )

    with col6:
        guidellm_versions = sorted(df['guidellm_version'].unique())
        selected_guidellm_versions = st.multiselect(
            "GuideLLM Version",
            guidellm_versions,
            default=guidellm_versions,
            key="guidellm_version_filter_cpu"
        )

    # Apply filters
    filtered_df = df[
        df['platform'].isin(selected_platforms) &
        df['model_short'].isin(selected_models) &
        df['workload'].isin(selected_workloads) &
        df['cores'].isin(selected_cores) &
        df['vllm_version'].isin(selected_versions) &
        df['guidellm_version'].isin(selected_guidellm_versions)
    ]

    return filtered_df


def render_cpu_performance_plots(df: pd.DataFrame):
    """Render CPU performance tradeoff plots."""
    st.markdown("## ⚡ CPU Performance Analysis")
    st.markdown("Analyze CPU performance tradeoffs similar to GPU benchmarks")

    if df.empty:
        st.warning("No data available for selected filters.")
        return

    # Interactive toggles
    st.markdown("### Chart Options")
    col_opt1, col_opt2, col_opt3 = st.columns(3)

    with col_opt1:
        log_scale = st.checkbox("Log Scale", value=False, key="cpu_perf_log_scale")

    with col_opt2:
        optimal_only = st.checkbox("Optimal Only", value=False, key="cpu_perf_optimal_only",
                                   help="Show only Pareto-optimal points (best throughput for each latency level)")

    with col_opt3:
        show_concurrency = st.checkbox("Show Concurrency Labels", value=False, key="cpu_perf_show_conc",
                                      help="Display concurrency values on each point")

    st.markdown("---")

    # Group by test configuration
    grouped = df.groupby([
        'platform', 'model_short', 'workload', 'vllm_version',
        'cores', 'tensor_parallel', 'test_name', 'test_run_id'
    ])

    # Color palette
    colors = px.colors.qualitative.Set2

    # Tab selection
    tab1, tab2 = st.tabs([
        "📈 Throughput vs. End-to-End Latency",
        "📊 Throughput vs. Interactivity"
    ])

    with tab1:
        st.markdown("### Token Throughput per Core vs. End-to-end Latency")
        st.caption("Note: Throughput is Total Tokens per second per core (prompt + output tokens combined)")

        # Create plot
        fig = go.Figure()
        color_idx = 0

        for (platform, model, workload, vllm_version, cores, tp, test_name, test_id), group_df in grouped:
            # Sort by latency
            group_df = group_df.sort_values('e2e_latency_ms')

            # Filter to optimal points only if requested
            if optimal_only:
                # Keep only pareto-optimal points (best throughput for each latency level or better)
                optimal_points = []
                max_throughput_seen = 0
                for idx, row in group_df.iterrows():
                    if row['throughput_per_core'] >= max_throughput_seen:
                        optimal_points.append(idx)
                        max_throughput_seen = row['throughput_per_core']
                group_df = group_df.loc[optimal_points]

            # Get full model name
            full_model = group_df['model'].iloc[0]

            # Simplified legend label - just platform and cores
            simple_label = f"{platform} | {cores}c"
            if tp > 1:
                simple_label += f" (TP={tp})"

            # Detailed label for hover
            detail_label = f"{platform} | {full_model} | {vllm_version} | {cores}c | TP={tp} | {workload}"
            if test_name and test_name.strip():
                run_id_short = test_id[-12:] if len(test_id) >= 12 else test_id
                detail_label = f"[{test_name}] {detail_label} (run {run_id_short})"

            # Prepare text labels if requested
            text_labels = None
            if show_concurrency:
                text_labels = [f"{int(c)}" for c in group_df['concurrency']]

            fig.add_trace(go.Scatter(
                x=group_df['e2e_latency_ms'],
                y=group_df['throughput_per_core'],
                name=simple_label,
                mode='lines+markers+text' if show_concurrency else 'lines+markers',
                text=text_labels,
                textposition='top center',
                textfont=dict(size=9),
                line=dict(
                    color=colors[color_idx % len(colors)],
                    width=3
                ),
                marker=dict(size=10),
                hovertemplate=(
                    f"<b>{detail_label}</b><br>" +
                    "Concurrency: %{customdata}<br>" +
                    "E2E Latency: %{x:.2f} ms<br>" +
                    "Throughput/Core: %{y:.2f} tok/s.core<br>" +
                    "<extra></extra>"
                ),
                customdata=group_df['concurrency']
            ))

            color_idx += 1

        # Apply log scale if requested
        yaxis_config = dict(title="Total Token Throughput per Core (tok/s.core)")
        if log_scale:
            yaxis_config['type'] = 'log'

        fig.update_layout(
            title="Token Throughput per Core vs. End-to-end Latency",
            xaxis_title="End-to-end Latency (ms)",
            yaxis=yaxis_config,
            height=600,
            hovermode='closest',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                bgcolor="white",
                bordercolor="rgba(0, 0, 0, 0.3)",
                borderwidth=1,
                font=dict(size=10, color="rgb(0, 0, 0)"),
                title=dict(text="Platform | Cores", font=dict(size=11))
            ),
            margin=dict(r=250)
        )

        st.plotly_chart(fig, use_container_width=True)

        # Summary table
        with st.expander("📊 View Detailed Performance Data"):
            summary = []
            for (platform, model, workload, vllm_version, cores, tp, test_name, test_id), group_df in grouped:
                backend = group_df['backend'].iloc[0]

                row = {
                    'Platform': platform,
                    'Model': model,
                    'Workload': workload,
                    'Release': vllm_version,
                    'Cores': cores,
                    'TP': tp,
                    'Backend': backend,
                }

                # Add test name if exists
                if test_name and test_name.strip():
                    run_id_short = test_id[-12:] if len(test_id) >= 12 else test_id
                    row['Test Name'] = f"{test_name} (run {run_id_short})"

                # Peak throughput per core and corresponding latency
                peak_idx = group_df['throughput_per_core'].idxmax()
                peak_throughput = group_df.loc[peak_idx, 'throughput_per_core']
                peak_latency = group_df.loc[peak_idx, 'e2e_latency_ms']
                row['Peak Throughput/Core'] = f"{peak_throughput:.2f} @ {peak_latency:.1f}ms"

                # Lowest latency and corresponding throughput
                best_latency_idx = group_df['e2e_latency_ms'].idxmin()
                best_latency = group_df.loc[best_latency_idx, 'e2e_latency_ms']
                best_latency_throughput = group_df.loc[best_latency_idx, 'throughput_per_core']
                row['Best Latency'] = f"{best_latency:.2f}ms @ {best_latency_throughput:.1f} tok/s.core"

                row['Load Points'] = len(group_df)
                summary.append(row)

            summary_df = pd.DataFrame(summary)
            st.dataframe(summary_df, use_container_width=True)

    with tab2:
        st.markdown("### Token Throughput per Core vs. Interactivity")
        st.caption("Note: Throughput is Total Tokens per second per core (prompt + output tokens combined)")
        st.caption("Interactivity = tok/s/user (total throughput divided by concurrent users)")

        # Create plot
        fig = go.Figure()
        color_idx = 0

        for (platform, model, workload, vllm_version, cores, tp, test_name, test_id), group_df in grouped:
            # Sort by interactivity
            group_df = group_df.sort_values('interactivity')

            # Filter to optimal points only if requested
            if optimal_only:
                # Keep only pareto-optimal points (best throughput for each interactivity level or better)
                optimal_points = []
                max_throughput_seen = 0
                for idx, row in group_df.iterrows():
                    if row['throughput_per_core'] >= max_throughput_seen:
                        optimal_points.append(idx)
                        max_throughput_seen = row['throughput_per_core']
                group_df = group_df.loc[optimal_points]

            # Get full model name
            full_model = group_df['model'].iloc[0]

            # Simplified legend label - just platform and cores
            simple_label = f"{platform} | {cores}c"
            if tp > 1:
                simple_label += f" (TP={tp})"

            # Detailed label for hover
            detail_label = f"{platform} | {full_model} | {vllm_version} | {cores}c | TP={tp} | {workload}"
            if test_name and test_name.strip():
                run_id_short = test_id[-12:] if len(test_id) >= 12 else test_id
                detail_label = f"[{test_name}] {detail_label} (run {run_id_short})"

            # Prepare text labels if requested
            text_labels = None
            if show_concurrency:
                text_labels = [f"{int(c)}" for c in group_df['concurrency']]

            fig.add_trace(go.Scatter(
                x=group_df['interactivity'],
                y=group_df['throughput_per_core'],
                name=simple_label,
                mode='lines+markers+text' if show_concurrency else 'lines+markers',
                text=text_labels,
                textposition='top center',
                textfont=dict(size=9),
                line=dict(
                    color=colors[color_idx % len(colors)],
                    width=3
                ),
                marker=dict(size=10),
                hovertemplate=(
                    f"<b>{detail_label}</b><br>" +
                    "Concurrency: %{customdata}<br>" +
                    "Interactivity: %{x:.2f} tok/s/user<br>" +
                    "Throughput/Core: %{y:.2f} tok/s.core<br>" +
                    "<extra></extra>"
                ),
                customdata=group_df['concurrency']
            ))

            color_idx += 1

        # Apply log scale if requested
        yaxis_config = dict(title="Total Token Throughput per Core (tok/s.core)")
        if log_scale:
            yaxis_config['type'] = 'log'

        fig.update_layout(
            title="Token Throughput per Core vs. Interactivity",
            xaxis_title="Interactivity (tok/s/user)",
            yaxis=yaxis_config,
            height=600,
            hovermode='closest',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                bgcolor="white",
                bordercolor="rgba(0, 0, 0, 0.3)",
                borderwidth=1,
                font=dict(size=10, color="rgb(0, 0, 0)"),
                title=dict(text="Platform | Cores", font=dict(size=11))
            ),
            margin=dict(r=250)
        )

        st.plotly_chart(fig, use_container_width=True)

        # Summary table
        with st.expander("📊 View Detailed Performance Data"):
            summary = []
            for (platform, model, workload, vllm_version, cores, tp, test_name, test_id), group_df in grouped:
                backend = group_df['backend'].iloc[0]

                row = {
                    'Platform': platform,
                    'Model': model,
                    'Workload': workload,
                    'Release': vllm_version,
                    'Cores': cores,
                    'TP': tp,
                    'Backend': backend,
                }

                # Add test name if exists
                if test_name and test_name.strip():
                    run_id_short = test_id[-12:] if len(test_id) >= 12 else test_id
                    row['Test Name'] = f"{test_name} (run {run_id_short})"

                # Peak throughput per core and corresponding interactivity
                peak_idx = group_df['throughput_per_core'].idxmax()
                peak_throughput = group_df.loc[peak_idx, 'throughput_per_core']
                peak_interactivity = group_df.loc[peak_idx, 'interactivity']
                row['Peak Throughput/Core'] = f"{peak_throughput:.2f} @ {peak_interactivity:.1f} tok/s/user"

                # Best interactivity and corresponding throughput
                best_interactivity_idx = group_df['interactivity'].idxmax()
                best_interactivity = group_df.loc[best_interactivity_idx, 'interactivity']
                best_interactivity_throughput = group_df.loc[best_interactivity_idx, 'throughput_per_core']
                row['Best Interactivity'] = f"{best_interactivity:.2f} tok/s/user @ {best_interactivity_throughput:.1f} tok/s.core"

                row['Load Points'] = len(group_df)
                summary.append(row)

            summary_df = pd.DataFrame(summary)
            st.dataframe(summary_df, use_container_width=True)


def render_dashboard():
    """Main dashboard rendering function."""
    # Header
    st.title("⚡ CPU Performance Analysis")
    st.markdown("Performance tradeoff analysis for CPU inference (similar to GPU benchmarks)")

    # Sidebar configuration
    st.sidebar.header("Configuration")

    # Initialize config manager
    config = DashboardConfig()
    default_results_dir = config.get_results_directory()

    # Results directory input
    results_dir = st.sidebar.text_input(
        "Results Directory",
        value=default_results_dir,
        help="Path to results directory",
        key="results_dir_cpu_perf"
    )

    # Save button
    col1, col2 = st.sidebar.columns([3, 1])
    with col2:
        save_btn = st.button(
            "💾",
            help="Save configuration",
            key="save_btn_cpu_perf"
        )
        if save_btn:
            if results_dir != default_results_dir:
                config.set_results_directory(results_dir)
                st.sidebar.success("✓ Saved!")
            else:
                st.sidebar.info("No changes")

    with st.spinner("Loading benchmark data..."):
        df = load_guidellm_data(results_dir)

    if df.empty:
        st.error("No benchmark data found!")
        st.info(f"Looking in: {Path(results_dir).absolute()}")
        st.info("Make sure benchmark results exist in the specified directory.")
        return

    # Filter to managed mode only (CPU tests)
    if 'vllm_mode' in df.columns:
        df = df[df['vllm_mode'] == 'managed']

    if df.empty:
        st.warning("No managed (CPU) test results found. This dashboard is for CPU-based tests only.")
        return

    # Global filters
    filtered_df = render_filters(df)

    if filtered_df.empty:
        st.warning("⚠️ No runs match the selected filters.")
        return

    st.markdown("---")

    # Render plots
    render_cpu_performance_plots(filtered_df)


if __name__ == "__main__":
    render_dashboard()
