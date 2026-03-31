"""vLLM CPU Performance Dashboard.

A comprehensive performance analysis dashboard for vLLM CPU benchmark results.
Provides interactive visualizations and analysis of CPU inference performance
across different platforms, models, and configurations.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
from plotly.subplots import make_subplots

# Add parent directory to path for config_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig

# Set global Plotly template
if "plotly_white_light" not in pio.templates:
    _light_hover = go.layout.Template(
        layout=go.Layout(
            hoverlabel={
                "bgcolor": "white",
                "font_color": "#262730",
                "bordercolor": "#d1d5db",
            },
        ),
    )
    pio.templates["plotly_white_light"] = pio.templates["plotly_white"]
    pio.templates["plotly_white_light"].layout.update(_light_hover.layout)
    pio.templates.default = "plotly_white_light"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# Page config is set in Home.py for multipage apps


# Custom CSS styling (dark mode friendly)
st.markdown("""
<style>
    /* Sidebar - use theme default for dark mode compatibility */
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
                    'platform': metadata.get('platform', 'unknown'),
                    'model': metadata.get('model', 'unknown'),
                    'model_short': metadata.get('model', 'unknown').split('/')[-1],
                    'workload': metadata.get('workload', 'unknown'),
                    'cores': metadata.get('core_count', 0),
                    'backend': metadata.get('backend', 'unknown'),
                    'vllm_version': metadata.get('vllm_version', 'unknown'),
                    'core_config': metadata.get('core_config_name', 'unknown'),
                    'tensor_parallel': metadata.get('tensor_parallel', 1),

                    # Load characteristics
                    'concurrency': concurrency,
                    'request_rate': req_rate,

                    # Throughput metrics
                    'throughput_mean': metrics['tokens_per_second']['successful']['mean'],
                    'throughput_p50': metrics['tokens_per_second']['successful']['percentiles']['p50'],
                    'throughput_p95': metrics['tokens_per_second']['successful']['percentiles']['p95'],
                    'throughput_p99': metrics['tokens_per_second']['successful']['percentiles']['p99'],

                    # TTFT metrics (ms)
                    'ttft_mean': metrics['time_to_first_token_ms']['successful']['mean'],
                    'ttft_p50': metrics['time_to_first_token_ms']['successful']['percentiles']['p50'],
                    'ttft_p95': metrics['time_to_first_token_ms']['successful']['percentiles']['p95'],
                    'ttft_p99': metrics['time_to_first_token_ms']['successful']['percentiles']['p99'],

                    # ITL metrics (ms)
                    'itl_mean': metrics['inter_token_latency_ms']['successful']['mean'],
                    'itl_p50': metrics['inter_token_latency_ms']['successful']['percentiles']['p50'],
                    'itl_p95': metrics['inter_token_latency_ms']['successful']['percentiles']['p95'],
                    'itl_p99': metrics['inter_token_latency_ms']['successful']['percentiles']['p99'],

                    # E2E latency metrics (s)
                    'e2e_mean': metrics['request_latency']['successful']['mean'],
                    'e2e_p50': metrics['request_latency']['successful']['percentiles']['p50'],
                    'e2e_p95': metrics['request_latency']['successful']['percentiles']['p95'],
                    'e2e_p99': metrics['request_latency']['successful']['percentiles']['p99'],

                    # Request stats
                    'total_requests': metrics['request_totals']['total'],
                    'successful_requests': metrics['request_totals']['successful'],
                    'success_rate': (metrics['request_totals']['successful'] /
                                   metrics['request_totals']['total'] * 100)
                                   if metrics['request_totals']['total'] > 0 else 0,
                }

                all_results.append(row)

        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
            continue

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results)

    # Calculate efficiency (throughput per core)
    df['efficiency'] = df['throughput_mean'] / df['cores']

    return df


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter UI and return filtered DataFrame."""
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### 🔍 Filter your data")

    col1, col2, col3 = st.columns(3)

    with col1:
        platforms = sorted(df['platform'].unique())
        selected_platforms = st.multiselect(
            "Platform",
            platforms,
            default=platforms,
            key="platform_filter"
        )

    with col2:
        models = sorted(df['model_short'].unique())
        selected_models = st.multiselect(
            "Model",
            models,
            default=models,
            key="model_filter"
        )

    with col3:
        workloads = sorted(df['workload'].unique())
        selected_workloads = st.multiselect(
            "Workload",
            workloads,
            default=workloads,
            key="workload_filter"
        )

    col4, col5 = st.columns(2)

    with col4:
        cores = sorted(df['cores'].unique())
        selected_cores = st.multiselect(
            "Core Count",
            cores,
            default=cores,
            key="cores_filter"
        )

    with col5:
        versions = sorted(df['vllm_version'].unique())
        selected_versions = st.multiselect(
            "vLLM Version",
            versions,
            default=versions,
            key="version_filter"
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # Apply filters
    filtered_df = df[
        df['platform'].isin(selected_platforms) &
        df['model_short'].isin(selected_models) &
        df['workload'].isin(selected_workloads) &
        df['cores'].isin(selected_cores) &
        df['vllm_version'].isin(selected_versions)
    ]

    return filtered_df


def render_performance_plots(df: pd.DataFrame):
    """Render performance vs load plots section."""
    st.markdown('<p class="section-header">📈 Performance Plots</p>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No data available for selected filters.")
        return

    # Axis selectors
    metric_options = {
        "Throughput (tokens/sec)": "throughput_mean",
        "TTFT (ms)": "ttft_p95",
        "ITL (ms)": "itl_p95",
        "E2E Latency (s)": "e2e_p95",
        "Efficiency (tokens/sec/core)": "efficiency",
        "Success Rate (%)": "success_rate"
    }

    x_axis_options = {
        "Request Rate (req/s)": "request_rate",
        "Concurrency": "concurrency"
    }

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        selected_x_axis = st.selectbox(
            "X-axis",
            list(x_axis_options.keys()),
            key="x_axis"
        )

    with col2:
        selected_metric = st.selectbox(
            "Y-axis Metric",
            list(metric_options.keys()),
            key="y_metric"
        )

    x_col = x_axis_options[selected_x_axis]
    metric_col = metric_options[selected_metric]

    # Group by test configuration
    grouped = df.groupby([
        'platform', 'model_short', 'workload', 'vllm_version',
        'cores', 'tensor_parallel', 'test_run_id'
    ])

    # Create plot
    fig = go.Figure()

    colors = px.colors.qualitative.Set2
    color_idx = 0

    for (platform, model, workload, vllm_version, cores, tp, test_id), group_df in grouped:
        # Sort by selected x-axis
        group_df = group_df.sort_values(x_col)

        # Get full model name from the first row
        full_model = group_df['model'].iloc[0]

        # Format label: platform | model | release | core_count | TP | workload
        label = f"{platform} | {full_model} | {vllm_version} | {cores}c | TP={tp} | {workload}"

        fig.add_trace(go.Scatter(
            x=group_df[x_col],
            y=group_df[metric_col],
            name=label,
            mode='lines+markers',
            line=dict(color=colors[color_idx % len(colors)], width=3),
            marker=dict(size=10),
            hovertemplate=(
                f"<b>{label}</b><br>" +
                f"{selected_x_axis}: %{{x:.2f}}<br>" +
                f"{selected_metric}: %{{y:.2f}}<br>" +
                "<extra></extra>"
            )
        ))

        color_idx += 1

    fig.update_layout(
        title=f"{selected_metric} vs {selected_x_axis}",
        xaxis_title=selected_x_axis,
        yaxis_title=selected_metric,
        height=600,
        hovermode='closest',
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,  # Position outside the plot area
            bgcolor="white",
            bordercolor="rgba(0, 0, 0, 0.3)",
            borderwidth=1,
            font=dict(size=10, color="rgb(0, 0, 0)")
        ),
        margin=dict(r=350)  # Add right margin for legend panel
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show load sweep details
    with st.expander("📊 View Detailed Load Sweep Data"):
        # Summary table
        summary = []
        for (platform, model, workload, vllm_version, cores, tp, test_id), group_df in grouped:
            max_throughput = group_df['throughput_mean'].max()
            best_ttft = group_df['ttft_p95'].min()
            max_concurrency = group_df['concurrency'].max()
            backend = group_df['backend'].iloc[0]

            summary.append({
                'Platform': platform,
                'Model': model,
                'Workload': workload,
                'Release': vllm_version,
                'Cores': cores,
                'TP': tp,
                'Backend': backend,
                'Peak Throughput (tok/s)': f"{max_throughput:.2f}",
                'Best TTFT P95 (ms)': f"{best_ttft:.2f}",
                'Max Concurrency': max_concurrency,
                'Load Points': len(group_df)
            })

        summary_df = pd.DataFrame(summary)
        st.dataframe(summary_df, use_container_width=True)


def render_compare_versions(df: pd.DataFrame):
    """Render version/platform comparison section."""
    st.markdown('<p class="section-header">⚖️ Compare Configurations</p>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No data available for selected filters.")
        return

    # Comparison selector
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Baseline Configuration")
        baseline_platforms = df['platform'].unique()
        baseline_platform = st.selectbox("Platform", baseline_platforms, key="baseline_platform")

        baseline_df = df[df['platform'] == baseline_platform]
        baseline_models = baseline_df['model_short'].unique()
        baseline_model = st.selectbox("Model", baseline_models, key="baseline_model")

        baseline_df = baseline_df[baseline_df['model_short'] == baseline_model]
        baseline_cores_list = sorted(baseline_df['cores'].unique())
        baseline_cores = st.selectbox("Cores", baseline_cores_list, key="baseline_cores")

        baseline_df = baseline_df[baseline_df['cores'] == baseline_cores]

        # Get available test runs for this configuration
        baseline_test_runs = baseline_df[['test_run_id', 'vllm_version', 'workload', 'tensor_parallel']].drop_duplicates()
        baseline_test_run_options = {
            f"{row['test_run_id'][:8]} | {row['vllm_version']} | {row['workload']} | TP={row['tensor_parallel']}": row['test_run_id']
            for _, row in baseline_test_runs.iterrows()
        }

        if baseline_test_run_options:
            baseline_test_run_label = st.selectbox(
                "Test Run",
                list(baseline_test_run_options.keys()),
                key="baseline_test_run"
            )
            baseline_test_run_id = baseline_test_run_options[baseline_test_run_label]
            baseline_data = baseline_df[baseline_df['test_run_id'] == baseline_test_run_id]
        else:
            baseline_data = pd.DataFrame()

    with col2:
        st.markdown("#### Comparison Configuration")
        compare_platforms = df['platform'].unique()
        compare_platform = st.selectbox("Platform", compare_platforms, key="compare_platform")

        compare_df = df[df['platform'] == compare_platform]
        compare_models = compare_df['model_short'].unique()
        compare_model = st.selectbox("Model", compare_models, key="compare_model")

        compare_df = compare_df[compare_df['model_short'] == compare_model]
        compare_cores_list = sorted(compare_df['cores'].unique())
        compare_cores = st.selectbox("Cores", compare_cores_list, key="compare_cores")

        compare_df = compare_df[compare_df['cores'] == compare_cores]

        # Get available test runs for this configuration
        compare_test_runs = compare_df[['test_run_id', 'vllm_version', 'workload', 'tensor_parallel']].drop_duplicates()
        compare_test_run_options = {
            f"{row['test_run_id'][:8]} | {row['vllm_version']} | {row['workload']} | TP={row['tensor_parallel']}": row['test_run_id']
            for _, row in compare_test_runs.iterrows()
        }

        if compare_test_run_options:
            compare_test_run_label = st.selectbox(
                "Test Run",
                list(compare_test_run_options.keys()),
                key="compare_test_run"
            )
            compare_test_run_id = compare_test_run_options[compare_test_run_label]
            compare_data = compare_df[compare_df['test_run_id'] == compare_test_run_id]
        else:
            compare_data = pd.DataFrame()

    if baseline_data.empty or compare_data.empty:
        st.warning("Insufficient data for comparison.")
        return

    # Side-by-side comparison
    st.markdown("---")
    st.markdown("### Comparison Results")

    # X-axis selector for comparison plots
    st.markdown("#### Chart Options")
    x_axis_options = {
        "Request Rate (req/s)": "request_rate",
        "Concurrency": "concurrency"
    }

    selected_x_axis_compare = st.selectbox(
        "X-axis for comparison charts",
        list(x_axis_options.keys()),
        key="x_axis_compare"
    )

    x_col_compare = x_axis_options[selected_x_axis_compare]

    # Peak performance metrics
    st.markdown("---")
    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)

    baseline_peak_tput = baseline_data['throughput_mean'].max()
    compare_peak_tput = compare_data['throughput_mean'].max()
    tput_diff = ((compare_peak_tput - baseline_peak_tput) / baseline_peak_tput) * 100

    baseline_best_ttft = baseline_data['ttft_p95'].min()
    compare_best_ttft = compare_data['ttft_p95'].min()
    ttft_diff = ((compare_best_ttft - baseline_best_ttft) / baseline_best_ttft) * 100

    baseline_efficiency = baseline_data['efficiency'].max()
    compare_efficiency = compare_data['efficiency'].max()
    eff_diff = ((compare_efficiency - baseline_efficiency) / baseline_efficiency) * 100

    with metrics_col1:
        st.metric(
            "Peak Throughput",
            f"{compare_peak_tput:.2f} tok/s",
            f"{tput_diff:+.1f}% vs baseline",
            delta_color="normal"
        )

    with metrics_col2:
        st.metric(
            "Best TTFT P95",
            f"{compare_best_ttft:.2f} ms",
            f"{ttft_diff:+.1f}% vs baseline",
            delta_color="inverse"
        )

    with metrics_col3:
        st.metric(
            "Efficiency",
            f"{compare_efficiency:.2f} tok/s/core",
            f"{eff_diff:+.1f}% vs baseline",
            delta_color="normal"
        )

    # Comparison plot
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Throughput Comparison', 'TTFT P95 Comparison')
    )

    # Create detailed labels with test run info
    baseline_run_info = baseline_data.iloc[0]
    compare_run_info = compare_data.iloc[0]

    baseline_label = f"Baseline: {baseline_platform} | {baseline_run_info['vllm_version']} | {baseline_run_info['workload']}"
    compare_label = f"Compare: {compare_platform} | {compare_run_info['vllm_version']} | {compare_run_info['workload']}"

    # Throughput
    for data, name, color in [
        (baseline_data.sort_values(x_col_compare),
         baseline_label, '#3b82f6'),
        (compare_data.sort_values(x_col_compare),
         compare_label, '#ef4444')
    ]:
        fig.add_trace(
            go.Scatter(
                x=data[x_col_compare],
                y=data['throughput_mean'],
                name=name,
                mode='lines+markers',
                line=dict(color=color, width=3),
                marker=dict(size=10),
                legendgroup=name
            ),
            row=1, col=1
        )

    # TTFT
    for data, name, color in [
        (baseline_data.sort_values(x_col_compare),
         baseline_label, '#3b82f6'),
        (compare_data.sort_values(x_col_compare),
         compare_label, '#ef4444')
    ]:
        fig.add_trace(
            go.Scatter(
                x=data[x_col_compare],
                y=data['ttft_p95'],
                name=name,
                mode='lines+markers',
                line=dict(color=color, width=3),
                marker=dict(size=10),
                showlegend=False,
                legendgroup=name
            ),
            row=1, col=2
        )

    fig.update_xaxes(title_text=selected_x_axis_compare, row=1, col=1)
    fig.update_xaxes(title_text=selected_x_axis_compare, row=1, col=2)
    fig.update_yaxes(title_text="Throughput (tokens/sec)", row=1, col=1)
    fig.update_yaxes(title_text="TTFT P95 (ms)", row=1, col=2)

    fig.update_layout(height=500, hovermode='closest')

    st.plotly_chart(fig, use_container_width=True)


def render_filtered_data(df: pd.DataFrame):
    """Render filtered data table section."""
    st.markdown('<p class="section-header">📄 Data Table</p>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No data available for selected filters.")
        return

    # Column selector
    all_columns = df.columns.tolist()
    default_columns = [
        'platform', 'model_short', 'cores', 'backend', 'request_rate',
        'throughput_mean', 'ttft_p95', 'itl_p95', 'success_rate'
    ]

    selected_columns = st.multiselect(
        "Select columns to display",
        all_columns,
        default=[col for col in default_columns if col in all_columns],
        key="data_columns"
    )

    if selected_columns:
        display_df = df[selected_columns].copy()

        # Sort options
        sort_col = st.selectbox("Sort by", selected_columns, key="sort_col")
        sort_order = st.radio("Order", ["Descending", "Ascending"], key="sort_order")

        display_df = display_df.sort_values(
            sort_col,
            ascending=(sort_order == "Ascending")
        )

        st.dataframe(display_df, use_container_width=True)

        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name="vllm_cpu_benchmark_results.csv",
            mime="text/csv"
        )


def render_dashboard():
    """Main dashboard rendering function."""
    # Header
    st.title("🚀 vLLM CPU Performance Dashboard")
    st.markdown("Comprehensive analysis of vLLM CPU inference performance")

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
        key="results_dir_client"
    )

    # Save button
    col1, col2 = st.sidebar.columns([3, 1])
    with col2:
        save_btn = st.button(
            "💾",
            help="Save configuration",
            key="save_btn_client"
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

    # Section navigation
    section_list = [
        "📈 Performance Plots",
        "⚖️ Compare Configurations",
        "📄 Data Table",
    ]

    SECTION_GROUPS = [
        ("Performance Analysis", ["📈 Performance Plots", "⚖️ Compare Configurations"]),
        ("Data", ["📄 Data Table"]),
    ]

    current_section = st.session_state.get("active_section", section_list[0])
    if current_section not in section_list:
        current_section = section_list[0]
    st.session_state.active_section = current_section

    # Global filters (shown for all sections)
    filtered_df = render_filters(df)

    if filtered_df.empty:
        st.warning("⚠️ No runs match the selected filters.")
        return

    st.markdown("---")

    # Sidebar navigation
    with st.sidebar:
        st.markdown("### Navigation")
        for group_name, group_sections in SECTION_GROUPS:
            visible = [s for s in group_sections if s in section_list]
            if not visible:
                continue

            st.markdown(
                f'<p class="nav-group-header">{group_name}</p>',
                unsafe_allow_html=True,
            )

            for section_name in visible:
                is_active = section_name == current_section
                btn_type: Literal["primary", "secondary"] = (
                    "primary" if is_active else "secondary"
                )
                if st.button(
                    section_name,
                    key=f"nav_{section_name}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    st.session_state.active_section = section_name
                    st.rerun()

    # Render selected section
    if current_section == "📈 Performance Plots":
        render_performance_plots(filtered_df)
    elif current_section == "⚖️ Compare Configurations":
        render_compare_versions(filtered_df)
    elif current_section == "📄 Data Table":
        render_filtered_data(filtered_df)


if __name__ == "__main__":
    render_dashboard()
