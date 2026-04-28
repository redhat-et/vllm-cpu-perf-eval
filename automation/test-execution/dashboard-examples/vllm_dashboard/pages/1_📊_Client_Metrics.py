"""vLLM CPU Performance Dashboard.

A comprehensive performance analysis dashboard for vLLM CPU benchmark results.
Provides interactive visualizations and analysis of CPU inference performance
across different platforms, models, and configurations.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Literal

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
                    'vllm_endpoint_url': metadata.get('vllm_endpoint_url', 'n/a'),
                    'model_source': metadata.get('model_source', 'specified'),

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
    # Guard against missing/zero cores to avoid inf/NaN
    cores = pd.to_numeric(df['cores'], errors='coerce')
    df['efficiency'] = np.where(cores > 0, df['throughput_mean'] / cores, np.nan)

    return df


def render_filters(df: pd.DataFrame, test_mode: str) -> pd.DataFrame:
    """Render filter UI and return filtered DataFrame.

    Args:
        df: DataFrame to filter
        test_mode: Either 'managed' or 'external'
    """
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### 🔍 Filter your data")

    if test_mode == 'managed':
        # Managed mode filters - traditional platform/cores filtering
        col1, col2, col3 = st.columns(3)

        with col1:
            platforms = sorted(df['platform'].unique())
            selected_platforms = st.multiselect(
                "Platform",
                platforms,
                default=platforms,
                key="platform_filter_managed"
            )

        with col2:
            models = sorted(df['model_short'].unique())
            selected_models = st.multiselect(
                "Model",
                models,
                default=models,
                key="model_filter_managed"
            )

        with col3:
            workloads = sorted(df['workload'].unique())
            selected_workloads = st.multiselect(
                "Workload",
                workloads,
                default=workloads,
                key="workload_filter_managed"
            )

        col4, col5, col6 = st.columns(3)

        with col4:
            cores = sorted(df['cores'].unique())
            selected_cores = st.multiselect(
                "Core Count",
                cores,
                default=cores,
                key="cores_filter_managed"
            )

        with col5:
            versions = sorted(df['vllm_version'].unique())
            selected_versions = st.multiselect(
                "vLLM Version",
                versions,
                default=versions,
                key="version_filter_managed"
            )

        with col6:
            guidellm_versions = sorted(df['guidellm_version'].unique())
            selected_guidellm_versions = st.multiselect(
                "GuideLLM Version",
                guidellm_versions,
                default=guidellm_versions,
                key="guidellm_version_filter_managed"
            )

        # Test name filter (separate row if any tests have custom names)
        if df['test_name'].astype(str).ne('').any():
            test_names = sorted([n for n in df['test_name'].unique() if n])
            if test_names:
                st.markdown("**Test Name Filter:**")
                selected_test_names = st.multiselect(
                    "Custom Test Names",
                    test_names,
                    default=test_names,
                    key="test_name_filter_managed",
                    help="Filter by custom test names (if provided during test run)"
                )
            else:
                selected_test_names = []
            all_test_names = test_names
        else:
            selected_test_names = []
            all_test_names = []

        st.markdown('</div>', unsafe_allow_html=True)

        # Apply filters
        filtered_df = df[
            df['platform'].isin(selected_platforms) &
            df['model_short'].isin(selected_models) &
            df['workload'].isin(selected_workloads) &
            df['cores'].isin(selected_cores) &
            df['vllm_version'].isin(selected_versions) &
            df['guidellm_version'].isin(selected_guidellm_versions)
        ]

        # Apply test name filter only if user has deselected some names
        if selected_test_names and selected_test_names != all_test_names:
            filtered_df = filtered_df[filtered_df['test_name'].isin(selected_test_names)]

    else:  # external mode
        # External mode filters - endpoint-based filtering
        col1, col2, col3 = st.columns(3)

        with col1:
            endpoints = sorted([e for e in df['vllm_endpoint_url'].unique() if e != 'n/a'])
            selected_endpoints = st.multiselect(
                "Endpoint URL",
                endpoints,
                default=endpoints,
                key="endpoint_filter_external"
            )

        with col2:
            models = sorted(df['model_short'].unique())
            selected_models = st.multiselect(
                "Model",
                models,
                default=models,
                key="model_filter_external"
            )

        with col3:
            workloads = sorted(df['workload'].unique())
            selected_workloads = st.multiselect(
                "Workload",
                workloads,
                default=workloads,
                key="workload_filter_external"
            )

        col4, col5, col6 = st.columns(3)

        with col4:
            versions = sorted(df['vllm_version'].unique())
            selected_versions = st.multiselect(
                "vLLM Version",
                versions,
                default=versions,
                key="version_filter_external"
            )

        with col5:
            guidellm_versions = sorted(df['guidellm_version'].unique())
            selected_guidellm_versions = st.multiselect(
                "GuideLLM Version",
                guidellm_versions,
                default=guidellm_versions,
                key="guidellm_version_filter_external"
            )

        with col6:
            # Model source (auto-detected vs specified)
            sources = sorted(df['model_source'].unique())
            selected_sources = st.multiselect(
                "Model Source",
                sources,
                default=sources,
                key="source_filter_external",
                help="'auto-detected' = model discovered from endpoint, 'specified' = model explicitly provided"
            )

        # Test name filter (separate row if any tests have custom names)
        if df['test_name'].astype(str).ne('').any():
            test_names = sorted([n for n in df['test_name'].unique() if n])
            if test_names:
                st.markdown("**Test Name Filter:**")
                selected_test_names = st.multiselect(
                    "Custom Test Names",
                    test_names,
                    default=test_names,
                    key="test_name_filter_external",
                    help="Filter by custom test names (if provided during test run)"
                )
            else:
                selected_test_names = []
            all_test_names = test_names
        else:
            selected_test_names = []
            all_test_names = []

        st.markdown('</div>', unsafe_allow_html=True)

        # Apply filters
        filtered_df = df[
            df['vllm_endpoint_url'].isin(selected_endpoints) &
            df['model_short'].isin(selected_models) &
            df['workload'].isin(selected_workloads) &
            df['vllm_version'].isin(selected_versions) &
            df['guidellm_version'].isin(selected_guidellm_versions) &
            df['model_source'].isin(selected_sources)
        ]

        # Apply test name filter only if user has deselected some names
        if selected_test_names and selected_test_names != all_test_names:
            filtered_df = filtered_df[filtered_df['test_name'].isin(selected_test_names)]

    return filtered_df


def geometric_mean(values):
    """Geometric mean of positive values. Accepts a list or pandas Series."""
    if hasattr(values, "values"):
        positive = values[values > 0].values
    else:
        positive = [v for v in values if v > 0]
    if len(positive) == 0:
        return None
    return float(np.exp(np.mean(np.log(positive))))


def compare_two_datasets(
    data_a,
    data_b,
    metric_column,
    aggregation,
    higher_is_better,
    x_axis_column='request_rate'
):
    """Compare two DataFrames on a metric.

    Args:
        data_a: Baseline DataFrame
        data_b: Comparison DataFrame
        metric_column: Column name to compare
        aggregation: 'peak' or 'geom_mean'
        higher_is_better: True if higher values are better
        x_axis_column: 'request_rate' or 'concurrency'

    Returns:
        (pct_diff, a_is_better, a_peak_load, b_peak_load, is_similar, a_val, b_val)
    """
    # Get common load points
    # For request_rate, round to avoid floating-point comparison issues
    if x_axis_column == "request_rate":
        a_keys = np.round(pd.to_numeric(data_a[x_axis_column], errors='coerce'), 2)
        b_keys = np.round(pd.to_numeric(data_b[x_axis_column], errors='coerce'), 2)
    else:
        a_keys = pd.to_numeric(data_a[x_axis_column], errors='coerce')
        b_keys = pd.to_numeric(data_b[x_axis_column], errors='coerce')

    a_loads = set(a_keys.dropna().unique())
    b_loads = set(b_keys.dropna().unique())
    common = a_loads.intersection(b_loads)

    if not common:
        return None, None, None, None, None, None, None

    # Filter to common load points
    if x_axis_column == "request_rate":
        a_common = data_a[a_keys.isin(common)]
        b_common = data_b[b_keys.isin(common)]
    else:
        a_common = data_a[data_a[x_axis_column].isin(common)]
        b_common = data_b[data_b[x_axis_column].isin(common)]

    a_vals = a_common[metric_column].dropna().tolist()
    b_vals = b_common[metric_column].dropna().tolist()

    if not a_vals or not b_vals:
        return None, None, None, None, None, None, None

    # Calculate aggregate value based on method
    if aggregation == "peak":
        if higher_is_better:
            a_val, b_val = max(a_vals), max(b_vals)
            # Track at which load point the peak occurs
            a_peak_load = float(
                a_common.loc[a_common[metric_column].idxmax(), x_axis_column]
            )
            b_peak_load = float(
                b_common.loc[b_common[metric_column].idxmax(), x_axis_column]
            )
        else:
            a_val, b_val = min(a_vals), min(b_vals)
            a_peak_load = float(
                a_common.loc[a_common[metric_column].idxmin(), x_axis_column]
            )
            b_peak_load = float(
                b_common.loc[b_common[metric_column].idxmin(), x_axis_column]
            )
    else:  # geom_mean
        a_val = geometric_mean(a_vals)
        b_val = geometric_mean(b_vals)
        a_peak_load = None
        b_peak_load = None

    if a_val is None or b_val is None or b_val == 0:
        return None, None, None, None, None, None, None

    # Calculate percentage difference
    pct_diff = ((a_val - b_val) / b_val) * 100
    a_better = pct_diff > 0 if higher_is_better else pct_diff < 0

    # Consider similar if within 5%
    is_similar = abs(pct_diff) < 5

    return pct_diff, a_better, a_peak_load, b_peak_load, is_similar, a_val, b_val


def render_performance_plots(df: pd.DataFrame):
    """Render performance vs load plots section."""
    st.markdown('<p class="section-header">📈 Performance Plots</p>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No data available for selected filters.")
        return

    # Detect test mode from dataframe
    test_mode = df['vllm_mode'].iloc[0] if not df.empty else 'managed'

    # Metric families
    metric_families = {
        "Throughput (tokens/sec)": {
            "prefix": "throughput",
            "unit": "tokens/sec",
            "percentiles": ["mean", "p50", "p95", "p99"]
        },
        "TTFT (ms)": {
            "prefix": "ttft",
            "unit": "ms",
            "percentiles": ["mean", "p50", "p95", "p99"]
        },
        "ITL (ms)": {
            "prefix": "itl",
            "unit": "ms",
            "percentiles": ["mean", "p50", "p95", "p99"]
        },
        "E2E Latency (s)": {
            "prefix": "e2e",
            "unit": "s",
            "percentiles": ["mean", "p50", "p95", "p99"]
        },
        "Success Rate (%)": {
            "prefix": "success_rate",
            "unit": "%",
            "percentiles": None  # No percentiles for success rate
        }
    }

    # Only add efficiency metric for managed mode (requires core count)
    if test_mode == 'managed':
        metric_families["Efficiency (tokens/sec/core)"] = {
            "prefix": "efficiency",
            "unit": "tokens/sec/core",
            "percentiles": None
        }

    x_axis_options = {
        "Request Rate (req/s)": "request_rate",
        "Concurrency": "concurrency"
    }

    col1, col2 = st.columns([1, 1])
    with col1:
        selected_x_axis = st.selectbox(
            "X-axis",
            list(x_axis_options.keys()),
            key="x_axis"
        )

    with col2:
        selected_metric_family = st.selectbox(
            "Metric Family",
            list(metric_families.keys()),
            key="metric_family"
        )

    x_col = x_axis_options[selected_x_axis]
    metric_config = metric_families[selected_metric_family]

    # Percentile labels for display
    percentile_labels = {"mean": "Mean", "p50": "P50", "p95": "P95", "p99": "P99"}

    # Percentile selector (only show for metrics with percentiles)
    selected_percentiles = []
    if metric_config["percentiles"]:
        st.markdown("**Show percentiles:**")
        cols = st.columns(len(metric_config["percentiles"]))
        for idx, percentile in enumerate(metric_config["percentiles"]):
            with cols[idx]:
                if st.checkbox(percentile_labels[percentile], value=(percentile in ["p95", "p99"]), key=f"percentile_{percentile}"):
                    selected_percentiles.append(percentile)

        if not selected_percentiles:
            st.warning("⚠️ Select at least one percentile to display")
            return
    else:
        # For metrics without percentiles, use the base column
        selected_percentiles = [None]

    # Group by test configuration (include test_name to separate named tests)
    grouped = df.groupby([
        'platform', 'model_short', 'workload', 'vllm_version',
        'cores', 'tensor_parallel', 'test_name', 'test_run_id'
    ])

    # Create plot
    fig = go.Figure()

    colors = px.colors.qualitative.Set2
    # Line styles for different percentiles
    line_styles = {
        "mean": "solid",
        "p50": "dash",
        "p95": "dot",
        "p99": "dashdot"
    }

    color_idx = 0

    for (platform, model, workload, vllm_version, cores, tp, test_name, test_id), group_df in grouped:
        # Sort by selected x-axis
        group_df = group_df.sort_values(x_col)

        # Get full model name from the first row
        full_model = group_df['model'].iloc[0]

        # Format base label based on mode
        if test_mode == 'managed':
            # Format label: platform | model | release | core_count | TP | workload
            base_label = f"{platform} | {full_model} | {vllm_version} | {cores}c | TP={tp} | {workload}"
        else:
            # External mode: endpoint | model | release | TP | workload
            endpoint_url = group_df['vllm_endpoint_url'].iloc[0]
            endpoint_short = endpoint_url.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
            base_label = f"{endpoint_short} | {full_model} | {vllm_version} | TP={tp} | {workload}"

        # Add test_name to label if it exists
        if test_name and test_name.strip():
            base_label = f"[{test_name}] {base_label}"

        # Plot each selected percentile
        for percentile in selected_percentiles:
            if percentile is None:
                # No percentiles (e.g., success_rate, efficiency)
                metric_col = metric_config["prefix"]
                trace_label = base_label
                line_style = "solid"
            else:
                # Build column name: prefix_percentile (e.g., ttft_p95)
                metric_col = f"{metric_config['prefix']}_{percentile}"
                trace_label = f"{base_label} ({percentile_labels[percentile]})"
                line_style = line_styles.get(percentile, "solid")

            fig.add_trace(go.Scatter(
                x=group_df[x_col],
                y=group_df[metric_col],
                name=trace_label,
                mode='lines+markers',
                line=dict(
                    color=colors[color_idx % len(colors)],
                    width=3 if percentile in ["p95", "p99", None] else 2,
                    dash=line_style
                ),
                marker=dict(size=8 if percentile in ["p95", "p99", None] else 6),
                hovertemplate=(
                    f"<b>{trace_label}</b><br>" +
                    f"{selected_x_axis}: %{{x:.2f}}<br>" +
                    f"{selected_metric_family}: %{{y:.2f}} {metric_config['unit']}<br>" +
                    "<extra></extra>"
                )
            ))

        color_idx += 1

    fig.update_layout(
        title=f"{selected_metric_family} vs {selected_x_axis}",
        xaxis_title=selected_x_axis,
        yaxis_title=selected_metric_family,
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
            font=dict(size=9, color="rgb(0, 0, 0)")
        ),
        margin=dict(r=400)  # Add right margin for legend panel
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show load sweep details
    with st.expander("📊 View Detailed Load Sweep Data"):
        # Summary table with peak load tracking
        summary = []
        x_label = (
            "@ Request Rate"
            if x_col == "request_rate"
            else "@ Concurrency"
        )

        for (
            platform, model, workload,
            vllm_version, cores, tp, test_name, test_id
        ), group_df in grouped:
            backend = group_df['backend'].iloc[0]
            vllm_mode = group_df['vllm_mode'].iloc[0]

            row = {
                'Model': model,
                'Workload': workload,
                'Release': vllm_version,
                'TP': tp,
                'Backend': backend,
            }

            # Add test name if it exists
            if test_name and test_name.strip():
                row['Test Name'] = test_name

            # Add platform/cores for managed, endpoint for external
            if vllm_mode == 'managed':
                row['Platform'] = platform
                row['Cores'] = cores
            else:
                endpoint_url = group_df['vllm_endpoint_url'].iloc[0]
                # Preserve host:port in endpoint display
                endpoint_short = endpoint_url.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
                row['Endpoint'] = endpoint_short[:50]  # Allow more space for host:port

            # Add peak/best values for selected metric family and percentiles
            if selected_percentiles[0] is None:
                # Single metric without percentiles (e.g., success_rate, efficiency)
                metric_col = metric_config["prefix"]
                if metric_config["prefix"] in ["throughput", "efficiency"]:
                    # Higher is better
                    peak_idx = group_df[metric_col].idxmax()
                    peak_val = group_df.loc[peak_idx, metric_col]
                    peak_load = group_df.loc[peak_idx, x_col]
                    row[f'Peak {selected_metric_family} {x_label}'] = f"{peak_val:.2f} @ {peak_load:.1f}"
                else:
                    # Lower is better
                    best_idx = group_df[metric_col].idxmin()
                    best_val = group_df.loc[best_idx, metric_col]
                    best_load = group_df.loc[best_idx, x_col]
                    row[f'Best {selected_metric_family} {x_label}'] = f"{best_val:.2f} @ {best_load:.1f}"
            else:
                # Metrics with percentiles
                for percentile in selected_percentiles:
                    metric_col = f"{metric_config['prefix']}_{percentile}"
                    percentile_label = percentile_labels[percentile]

                    if metric_config["prefix"] == "throughput":
                        # Higher is better
                        peak_idx = group_df[metric_col].idxmax()
                        peak_val = group_df.loc[peak_idx, metric_col]
                        peak_load = group_df.loc[peak_idx, x_col]
                        row[f'Peak {percentile_label} {x_label}'] = f"{peak_val:.2f} @ {peak_load:.1f}"
                    else:
                        # Lower is better (latencies)
                        best_idx = group_df[metric_col].idxmin()
                        best_val = group_df.loc[best_idx, metric_col]
                        best_load = group_df.loc[best_idx, x_col]
                        row[f'Best {percentile_label} {x_label}'] = f"{best_val:.2f} @ {best_load:.1f}"

            row['Load Points'] = len(group_df)
            summary.append(row)

        summary_df = pd.DataFrame(summary)
        st.dataframe(summary_df, use_container_width=True)


def render_compare_versions(df: pd.DataFrame):
    """Render version/platform comparison section."""
    st.markdown('<p class="section-header">⚖️ Compare Configurations</p>', unsafe_allow_html=True)

    if df.empty:
        st.warning("No data available for selected filters.")
        return

    # Detect test mode from dataframe
    test_mode = df['vllm_mode'].iloc[0] if not df.empty else 'managed'

    # Comparison selector
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Baseline Configuration")

        if test_mode == 'managed':
            # Managed mode: filter by platform
            baseline_platforms = df['platform'].unique()
            baseline_platform = st.selectbox("Platform", baseline_platforms, key="baseline_platform")
            baseline_df = df[df['platform'] == baseline_platform]
        else:
            # External mode: filter by endpoint
            baseline_endpoints = [e for e in df['vllm_endpoint_url'].unique() if e != 'n/a']
            if not baseline_endpoints:
                st.warning("No valid endpoint URLs found for external runs.")
                return
            baseline_endpoint = st.selectbox("Endpoint URL", baseline_endpoints, key="baseline_endpoint")
            baseline_df = df[df['vllm_endpoint_url'] == baseline_endpoint]

        baseline_models = baseline_df['model_short'].unique()
        baseline_model = st.selectbox("Model", baseline_models, key="baseline_model")

        baseline_df = baseline_df[baseline_df['model_short'] == baseline_model]

        if test_mode == 'managed':
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

        if test_mode == 'managed':
            # Managed mode: filter by platform
            compare_platforms = df['platform'].unique()
            compare_platform = st.selectbox("Platform", compare_platforms, key="compare_platform")
            compare_df = df[df['platform'] == compare_platform]
        else:
            # External mode: filter by endpoint
            compare_endpoints = [e for e in df['vllm_endpoint_url'].unique() if e != 'n/a']
            if not compare_endpoints:
                st.warning("No valid endpoint URLs found for external runs.")
                return
            compare_endpoint = st.selectbox("Endpoint URL", compare_endpoints, key="compare_endpoint")
            compare_df = df[df['vllm_endpoint_url'] == compare_endpoint]

        compare_models = compare_df['model_short'].unique()
        compare_model = st.selectbox("Model", compare_models, key="compare_model")

        compare_df = compare_df[compare_df['model_short'] == compare_model]

        if test_mode == 'managed':
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

    # Chart options
    st.markdown("#### Chart Options")
    col_opt1, col_opt2 = st.columns(2)

    with col_opt1:
        x_axis_options = {
            "Request Rate (req/s)": "request_rate",
            "Concurrency": "concurrency"
        }
        selected_x_axis_compare = st.selectbox(
            "X-axis",
            list(x_axis_options.keys()),
            key="x_axis_compare"
        )
        x_col_compare = x_axis_options[selected_x_axis_compare]

    with col_opt2:
        aggregation_options = {
            "Peak": "peak",
            "Geometric Mean": "geom_mean"
        }
        selected_aggregation = st.selectbox(
            "Aggregation Method",
            list(aggregation_options.keys()),
            key="aggregation_compare",
            help="Peak: Compare best single value | "
                 "Geom Mean: Compare average across all load points"
        )
        aggregation = aggregation_options[selected_aggregation]

    # Performance metrics comparison
    st.markdown("---")

    # Define metrics to compare
    metrics_config = {
        "Throughput": {
            "column": "throughput_mean",
            "higher_is_better": True,
            "format": "{:.2f} tok/s",
            "show": True
        },
        "TTFT P95": {
            "column": "ttft_p95",
            "higher_is_better": False,
            "format": "{:.2f} ms",
            "show": True
        },
        "TTFT P99": {
            "column": "ttft_p99",
            "higher_is_better": False,
            "format": "{:.2f} ms",
            "show": True
        },
        "ITL P95": {
            "column": "itl_p95",
            "higher_is_better": False,
            "format": "{:.2f} ms",
            "show": True
        },
        "ITL P99": {
            "column": "itl_p99",
            "higher_is_better": False,
            "format": "{:.2f} ms",
            "show": True
        }
    }

    # Add efficiency only for managed mode
    if test_mode == 'managed':
        metrics_config["Efficiency"] = {
            "column": "efficiency",
            "higher_is_better": True,
            "format": "{:.2f} tok/s/core",
            "show": True
        }

    # Calculate comparisons
    comparison_results = {}
    for metric_name, config in metrics_config.items():
        result = compare_two_datasets(
            baseline_data,
            compare_data,
            config["column"],
            aggregation,
            config["higher_is_better"],
            x_col_compare
        )
        comparison_results[metric_name] = result

    # Display metrics
    num_metrics = len([m for m in metrics_config.values() if m["show"]])
    cols = st.columns(num_metrics)
    col_idx = 0

    for metric_name, config in metrics_config.items():
        if not config["show"]:
            continue

        pct_diff, _better, _a_load, b_load, _similar, _a_val, compare_val = (
            comparison_results[metric_name]
        )

        if pct_diff is not None:
            # compare_val comes from the same subset used for pct_diff

            load_label = "@ rate" if x_col_compare == "request_rate" else "@ conc"

            with cols[col_idx]:
                st.metric(
                    metric_name,
                    config["format"].format(compare_val),
                    f"{pct_diff:+.1f}% vs baseline",
                    delta_color=(
                        "normal" if config["higher_is_better"] else "inverse"
                    )
                )
                if aggregation == "peak" and b_load is not None:
                    st.caption(f"{load_label} {b_load:.1f}")

        col_idx += 1

    # Comparison plot
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Throughput Comparison', 'TTFT P95 Comparison')
    )

    # Create detailed labels with test run info
    baseline_run_info = baseline_data.iloc[0]
    compare_run_info = compare_data.iloc[0]

    if test_mode == 'managed':
        baseline_label = f"Baseline: {baseline_platform} | {baseline_run_info['vllm_version']} | {baseline_run_info['workload']}"
        compare_label = f"Compare: {compare_platform} | {compare_run_info['vllm_version']} | {compare_run_info['workload']}"
    else:
        # For external mode, show endpoint URL (shortened for display, preserving host:port)
        baseline_endpoint_short = baseline_endpoint.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
        compare_endpoint_short = compare_endpoint.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
        baseline_label = f"Baseline: {baseline_endpoint_short} | {baseline_run_info['vllm_version']} | {baseline_run_info['workload']}"
        compare_label = f"Compare: {compare_endpoint_short} | {compare_run_info['vllm_version']} | {compare_run_info['workload']}"

    # Add test names to labels if they exist
    if baseline_run_info.get('test_name') and baseline_run_info['test_name'].strip():
        baseline_label = f"[{baseline_run_info['test_name']}] {baseline_label}"
    if compare_run_info.get('test_name') and compare_run_info['test_name'].strip():
        compare_label = f"[{compare_run_info['test_name']}] {compare_label}"

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

    # Check if we have both managed and external tests
    has_managed = 'managed' in df['vllm_mode'].unique()
    has_external = 'external' in df['vllm_mode'].unique()

    # Deployment mode selection (only show if both types exist)
    if has_managed and has_external:
        st.markdown("---")
        deployment_mode = st.radio(
            "📍 Test Deployment Mode",
            ["Managed (DUT Container)", "External Endpoints"],
            horizontal=True,
            help="Managed: vLLM runs on DUT in container | External: vLLM runs on external endpoint (cloud/K8s)"
        )
        test_mode = 'managed' if deployment_mode == "Managed (DUT Container)" else 'external'

        # Info message about different filters
        if test_mode == 'external':
            st.info("ℹ️ External endpoint view: Filter by endpoint URL instead of platform/cores")

        # Filter dataframe by mode
        mode_filtered_df = df[df['vllm_mode'] == test_mode]

        if mode_filtered_df.empty:
            st.warning(f"⚠️ No {test_mode} test results found.")
            return
    elif has_external:
        # Only external tests exist
        st.info("ℹ️ Showing external endpoint test results only")
        test_mode = 'external'
        mode_filtered_df = df[df['vllm_mode'] == 'external']
    else:
        # Only managed tests exist (default)
        test_mode = 'managed'
        mode_filtered_df = df[df['vllm_mode'] == 'managed']

    # Global filters (shown for all sections)
    filtered_df = render_filters(mode_filtered_df, test_mode)

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
