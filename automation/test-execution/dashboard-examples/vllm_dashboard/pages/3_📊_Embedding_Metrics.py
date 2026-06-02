"""vLLM Embedding Model Performance Dashboard.

Analyzes embedding model benchmark results from vllm bench serve.
Provides saturation curves, core scaling, and concurrent load analysis.
"""

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots

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

# Custom CSS styling
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_embedding_data(results_dir: str) -> pd.DataFrame:
    """Load embedding benchmark results from directory structure."""
    results_path = Path(results_dir)
    all_results = []

    if not results_path.exists():
        logger.warning(f"Results directory not found: {results_path}")
        return pd.DataFrame()

    # Scan for all test-metadata.json files in embedding results
    for metadata_file in results_path.rglob("test-metadata.json"):
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)

            # Validate required metadata fields
            required_fields = ['test_run_id', 'model', 'platform']
            missing = [f for f in required_fields if f not in metadata or not metadata[f]]
            if missing:
                logger.warning(f"Skipping {metadata_file}: missing required fields {missing}")
                continue

            test_run_dir = metadata_file.parent

            # Process JSON files in baseline/ and latency/ subdirectories
            result_subdirs = ['baseline', 'latency']
            for subdir_name in result_subdirs:
                subdir = test_run_dir / subdir_name
                if not subdir.exists():
                    continue

                # Process all JSON result files in this subdirectory
                for json_file in sorted(subdir.glob("*.json")):
                    with open(json_file) as f:
                        result = json.load(f)

                    # Validate result has key metrics
                    required_metrics = ['request_throughput', 'mean_e2el_ms']
                    missing_metrics = [m for m in required_metrics if m not in result]
                    if missing_metrics:
                        logger.warning(f"Skipping {json_file}: missing metrics {missing_metrics}")
                        continue

                    # Parse test type from filename
                    stem = json_file.stem
                    if stem.startswith('sweep-'):
                        test_type = 'baseline'
                        parameter = stem.replace('sweep-', '')
                    elif stem.startswith('concurrent-'):
                        test_type = 'concurrent'
                        parameter = stem.replace('concurrent-', '')
                    else:
                        test_type = 'unknown'
                        parameter = stem

                    # Extract test_name from test_run_id (format: test_name-YYYYMMDD-HHMMSS or just YYYYMMDD-HHMMSS)
                    test_run_id = metadata.get('test_run_id', 'unknown')
                    test_name = None
                    if test_run_id != 'unknown' and '-' in test_run_id:
                        parts = test_run_id.split('-')
                        # If more than 2 parts (date-time), first part(s) are test_name
                        if len(parts) > 2:
                            test_name = '-'.join(parts[:-2])

                    # Calculate derived metrics
                    rps = result.get('request_throughput', 0)
                    cores = metadata.get('requested_cores')
                    rps_per_core = (rps / cores) if cores and cores > 0 else None

                    row = {
                        # Metadata
                        'test_run_id': test_run_id,
                        'test_name': test_name,
                        'scenario': metadata.get('scenario', ''),
                        'model': metadata.get('model', ''),
                        'platform': metadata.get('platform', 'unknown'),
                        'vllm_version': metadata.get('vllm_version', 'unknown'),
                        'vllm_mode': metadata.get('vllm_mode', 'managed'),
                        'requested_cores': metadata.get('requested_cores'),
                        'input_length': metadata.get('embedding_random_input_len'),
                        'timestamp': metadata.get('timestamp', ''),

                        # Test configuration
                        'test_type': test_type,
                        'parameter': parameter,
                        'request_rate': result.get('request_rate'),
                        'max_concurrency': result.get('max_concurrency'),
                        'num_prompts': result.get('num_prompts'),

                        # Performance metrics
                        'request_throughput_rps': rps,
                        'token_throughput_tps': result.get('total_token_throughput'),
                        'rps_per_core': rps_per_core,
                        'mean_latency_ms': result.get('mean_e2el_ms'),
                        'median_latency_ms': result.get('median_e2el_ms'),
                        'std_latency_ms': result.get('std_e2el_ms'),
                        'p99_latency_ms': result.get('p99_e2el_ms'),
                        'duration_sec': result.get('duration'),
                        'completed_requests': result.get('completed'),
                        'total_input_tokens': result.get('total_input_tokens'),
                    }
                    all_results.append(row)

        except Exception as e:
            logger.warning(f"Failed to load {metadata_file}: {e}")
            continue

    return pd.DataFrame(all_results)


def plot_saturation_curve(df: pd.DataFrame):
    """Plot throughput and P99 latency vs load level, grouped by test configuration."""
    if df.empty:
        st.warning("No baseline data to display")
        return

    # Group by test configuration
    grouped = df.groupby([
        'platform', 'model', 'vllm_version', 'requested_cores',
        'input_length', 'test_name', 'test_run_id'
    ])

    # Create dual-axis figure
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    colors = px.colors.qualitative.Set2
    color_idx = 0

    # Order for load levels
    load_order = {'inf': 4, '75pct': 3, '50pct': 2, '25pct': 1}

    for (platform, model, version, cores, input_len, test_name, test_id), group_df in grouped:
        # Sort by load order
        group_df = group_df.copy()
        group_df['load_order'] = group_df['parameter'].map(load_order).fillna(0)
        group_df = group_df.sort_values('load_order')

        # Build concise trace label
        model_short = model.split('/')[-1]
        run_id_short = test_id[-6:] if len(test_id) >= 6 else test_id

        # If test_name exists (e.g., "embeddinggemma-300m-8C"), use it since it's already compact
        if test_name and test_name.strip():
            base_label = f"{test_name} ({run_id_short})"
        else:
            # Otherwise: model | cores | input_len
            base_label = f"{model_short} | {cores}c | {input_len}tok ({run_id_short})"

        # Throughput trace
        fig.add_trace(
            go.Scatter(
                x=group_df['parameter'],
                y=group_df['request_throughput_rps'],
                name=f"{base_label} - Throughput",
                mode='lines+markers',
                marker=dict(size=8, color=colors[color_idx % len(colors)]),
                line=dict(width=3, color=colors[color_idx % len(colors)])
            ),
            secondary_y=False
        )

        # P99 Latency trace
        fig.add_trace(
            go.Scatter(
                x=group_df['parameter'],
                y=group_df['p99_latency_ms'],
                name=f"{base_label} - P99 Latency",
                mode='lines+markers',
                marker=dict(size=8, color=colors[color_idx % len(colors)]),
                line=dict(width=2, dash='dash', color=colors[color_idx % len(colors)])
            ),
            secondary_y=True
        )

        color_idx += 1

    fig.update_xaxes(
        title_text="Load Level",
        categoryorder='array',
        categoryarray=['25pct', '50pct', '75pct', 'inf']
    )
    fig.update_yaxes(title_text="Request Throughput (req/s)", secondary_y=False)
    fig.update_yaxes(title_text="P99 Latency (ms)", secondary_y=True)

    fig.update_layout(
        title="Saturation Analysis: Throughput & Latency vs Load",
        hovermode='x unified',
        height=600,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Token throughput graph
    st.subheader("Token Processing Speed vs Load")
    fig_tokens = go.Figure()
    color_idx = 0

    for (_, model, _, cores, input_len, test_name, test_id), group_df in grouped:
        group_df = group_df.copy()
        group_df['load_order'] = group_df['parameter'].map(load_order).fillna(0)
        group_df = group_df.sort_values('load_order')

        model_short = model.split('/')[-1]
        run_id_short = test_id[-6:] if len(test_id) >= 6 else test_id

        if test_name and test_name.strip():
            label = f"{test_name} ({run_id_short})"
        else:
            label = f"{model_short} | {cores}c | {input_len}tok ({run_id_short})"

        fig_tokens.add_trace(go.Scatter(
            x=group_df['parameter'],
            y=group_df['token_throughput_tps'],
            name=label,
            mode='lines+markers',
            marker=dict(size=8, color=colors[color_idx % len(colors)]),
            line=dict(width=3, color=colors[color_idx % len(colors)])
        ))
        color_idx += 1

    fig_tokens.update_xaxes(
        title_text="Load Level",
        categoryorder='array',
        categoryarray=['25pct', '50pct', '75pct', 'inf']
    )
    fig_tokens.update_yaxes(title_text="Token Throughput (tokens/s)")
    fig_tokens.update_layout(
        title="Token Processing Speed vs Load",
        hovermode='x unified',
        height=500,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
    )
    st.plotly_chart(fig_tokens, use_container_width=True)

    # Metrics table for all configurations
    st.subheader("Baseline Metrics (All Configurations)")

    # Prepare display dataframe with config info
    display_df = df.copy()
    display_df['config'] = display_df.apply(
        lambda row: f"{row['model'].split('/')[-1]} | {row['requested_cores']}c | {row['input_length']}tok | run {row['test_run_id'][-8:]}",
        axis=1
    )

    metrics_display = display_df[[
        'config', 'parameter', 'request_throughput_rps', 'rps_per_core', 'token_throughput_tps',
        'p99_latency_ms', 'mean_latency_ms', 'median_latency_ms'
    ]].copy()
    metrics_display.columns = ['Configuration', 'Load', 'RPS', 'RPS/Core', 'Token/s', 'P99 (ms)', 'Mean (ms)', 'Median (ms)']
    metrics_display = metrics_display.round(2)
    st.dataframe(metrics_display, use_container_width=True)


def plot_concurrent_load(df: pd.DataFrame):
    """Plot throughput and latency vs concurrency level, grouped by test configuration."""
    if df.empty:
        st.warning("No concurrent load data to display")
        return

    # Parse concurrency from parameter column
    df = df.copy()
    df['concurrency'] = pd.to_numeric(df['parameter'], errors='coerce')
    df = df.dropna(subset=['concurrency'])
    df['concurrency'] = df['concurrency'].astype(int)

    # Metric selectors
    col_selector1, col_selector2 = st.columns(2)

    with col_selector1:
        throughput_metric = st.radio(
            "Throughput Metric",
            options=["RPS", "Token/s"],
            horizontal=True,
            help="Select throughput metric: Requests per second or Tokens per second"
        )
        throughput_col = 'request_throughput_rps' if throughput_metric == "RPS" else 'token_throughput_tps'
        throughput_label = "Request Throughput (req/s)" if throughput_metric == "RPS" else "Token Throughput (tokens/s)"

    with col_selector2:
        latency_metric = st.radio(
            "Latency Metric",
            options=["Mean", "P99"],
            horizontal=True,
            help="Select which latency metric to display"
        )
        latency_col = 'mean_latency_ms' if latency_metric == "Mean" else 'p99_latency_ms'

    # Group by test configuration
    grouped = df.groupby([
        'platform', 'model', 'vllm_version', 'requested_cores',
        'input_length', 'test_name', 'test_run_id'
    ])

    colors = px.colors.qualitative.Set2
    color_idx = 0

    col1, col2 = st.columns(2)

    with col1:
        # Throughput vs concurrency
        fig1 = go.Figure()

        for (_, model, _, cores, input_len, test_name, test_id), group_df in grouped:
            group_df = group_df.sort_values('concurrency')

            # Build concise trace label
            model_short = model.split('/')[-1]
            run_id_short = test_id[-6:] if len(test_id) >= 6 else test_id

            if test_name and test_name.strip():
                label = f"{test_name} ({run_id_short})"
            else:
                label = f"{model_short} | {cores}c | {input_len}tok ({run_id_short})"

            fig1.add_trace(go.Scatter(
                x=group_df['concurrency'],
                y=group_df[throughput_col],
                name=label,
                mode='lines+markers',
                marker=dict(size=8, color=colors[color_idx % len(colors)]),
                line=dict(width=3, color=colors[color_idx % len(colors)])
            ))
            color_idx += 1

        fig1.update_layout(
            title=f"{throughput_metric} vs Concurrency",
            xaxis_title="Concurrent Requests",
            yaxis_title=throughput_label,
            height=500,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        # Latency vs concurrency
        fig2 = go.Figure()
        color_idx = 0

        for (_, model, _, cores, input_len, test_name, test_id), group_df in grouped:
            group_df = group_df.sort_values('concurrency')

            # Build concise trace label
            model_short = model.split('/')[-1]
            run_id_short = test_id[-6:] if len(test_id) >= 6 else test_id

            if test_name and test_name.strip():
                label = f"{test_name} ({run_id_short})"
            else:
                label = f"{model_short} | {cores}c | {input_len}tok ({run_id_short})"

            fig2.add_trace(go.Scatter(
                x=group_df['concurrency'],
                y=group_df[latency_col],
                name=label,
                mode='lines+markers',
                marker=dict(size=8, color=colors[color_idx % len(colors)]),
                line=dict(width=3, color=colors[color_idx % len(colors)])
            ))
            color_idx += 1

        fig2.update_layout(
            title=f"{latency_metric} Latency vs Concurrency",
            xaxis_title="Concurrent Requests",
            yaxis_title=f"{latency_metric} Latency (ms)",
            height=500,
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Metrics table for all configurations
    st.subheader("Concurrent Load Metrics (All Configurations)")

    # Prepare display dataframe with config info
    display_df = df.copy()
    display_df['config'] = display_df.apply(
        lambda row: f"{row['model'].split('/')[-1]} | {row['requested_cores']}c | {row['input_length']}tok | run {row['test_run_id'][-8:]}",
        axis=1
    )

    metrics_display = display_df[[
        'config', 'concurrency', 'request_throughput_rps', 'rps_per_core', 'token_throughput_tps',
        'mean_latency_ms', 'median_latency_ms', 'p99_latency_ms'
    ]].copy()
    metrics_display.columns = ['Configuration', 'Concurrency', 'RPS', 'RPS/Core', 'Token/s', 'Mean (ms)', 'Median (ms)', 'P99 (ms)']
    metrics_display = metrics_display.round(2)
    st.dataframe(metrics_display, use_container_width=True)


def plot_model_comparison(df: pd.DataFrame, models: list, test_type: str):
    """Compare performance across multiple models."""
    if len(models) < 2:
        st.info("Select multiple models to see comparison")
        return

    # Get latest inf baseline for each model
    comparison_data = []
    for model in models:
        model_data = df[
            (df['model'] == model) &
            (df['test_type'] == test_type) &
            (df['parameter'] == 'inf')
        ]
        if not model_data.empty:
            latest = model_data.sort_values('test_run_id', ascending=False).iloc[0]
            comparison_data.append(latest)

    if not comparison_data:
        st.warning(f"No {test_type} data found for selected models")
        return

    comparison_df = pd.DataFrame(comparison_data)

    col1, col2 = st.columns(2)

    with col1:
        fig1 = px.bar(
            comparison_df,
            x='model',
            y='request_throughput_rps',
            title='Max Throughput Comparison',
            text='request_throughput_rps'
        )
        fig1.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig1.update_layout(xaxis_title="Model", yaxis_title="Request Throughput (req/s)", height=400)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = px.bar(
            comparison_df,
            x='model',
            y='p99_latency_ms',
            title='P99 Latency Comparison',
            text='p99_latency_ms'
        )
        fig2.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig2.update_layout(xaxis_title="Model", yaxis_title="P99 Latency (ms)", height=400)
        st.plotly_chart(fig2, use_container_width=True)

    # Comparison table
    st.subheader("Model Comparison Table")
    comparison_display = comparison_df[[
        'model', 'request_throughput_rps', 'p99_latency_ms',
        'mean_latency_ms', 'vllm_version'
    ]].copy()
    comparison_display.columns = ['Model', 'Max RPS', 'P99 (ms)', 'Mean (ms)', 'vLLM Version']
    comparison_display = comparison_display.round(2)
    st.dataframe(comparison_display, use_container_width=True)


def main():
    """Main dashboard application."""
    st.title("📊 Embedding Model Performance")
    st.markdown("Analysis of vLLM embedding benchmark results")

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")

        config = DashboardConfig()
        default_results_dir = str(Path(config.get_results_directory()).parent / "embedding")

        results_dir_input = st.text_input(
            "Results Directory",
            value=default_results_dir,
            help="Path to embedding results directory",
            key="results_dir_embedding"
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()

        st.markdown("---")
        st.markdown("**Embedding Metrics:**")
        st.markdown("""
        - Request Throughput (req/s)
        - End-to-End Latency (P50, P99)
        - Token Processing Speed
        - Concurrent Request Handling
        """)

    # Load data
    df = load_embedding_data(results_dir_input)

    if df.empty:
        st.error(f"No embedding results found in {results_dir_input}")
        st.info("""
        Run embedding benchmarks first:

        ```bash
        ansible-playbook embedding-benchmark.yml \\
          -e "test_model=RedHatAI/all-MiniLM-L6-v2" \\
          -e "scenario=all"
        ```
        """)
        return

    st.success(f"✓ Loaded {len(df)} test results from {results_dir_input}")

    # Filters Header
    st.markdown("### 🔍 Filters")

    # Filters - Row 1: Primary filters
    col1, col2, col3 = st.columns(3)

    with col1:
        models = sorted(df['model'].unique())
        selected_models = st.multiselect(
            "Models",
            options=models,
            default=[models[0]] if models else [],
            help="Select one or more models to compare"
        )

    with col2:
        platforms = sorted(df['platform'].unique())
        selected_platforms = st.multiselect(
            "Platforms",
            options=platforms,
            default=platforms,
            help="Filter by CPU platform"
        )

    with col3:
        # vLLM Mode filter - radio buttons for mutually exclusive choice
        vllm_modes = sorted(df['vllm_mode'].unique())
        # Default to first mode (usually 'dut-only' or 'managed')
        selected_vllm_mode = st.radio(
            "vLLM Mode",
            options=vllm_modes,
            index=0,
            horizontal=True,
            help="Execution architecture: managed (2-node), dut-only (single-node), or external (existing endpoint)"
        )

    # Filters - Row 2: Configuration filters
    col4, col5, col6 = st.columns(3)

    with col4:
        # Get unique core counts, filtering out None/NaN
        core_counts = sorted([int(c) for c in df['requested_cores'].unique() if pd.notna(c)])
        if core_counts:
            selected_core_counts = st.multiselect(
                "Core Count",
                options=core_counts,
                default=core_counts,
                help="CPU cores allocated to vLLM"
            )
        else:
            st.multiselect(
                "Core Count",
                options=[],
                default=[],
                disabled=True,
                help="No core count data available"
            )
            selected_core_counts = None

    with col5:
        # Input length filter
        input_lengths = sorted([int(i) for i in df['input_length'].unique() if pd.notna(i)])
        if input_lengths:
            selected_input_lengths = st.multiselect(
                "Input Length",
                options=input_lengths,
                default=input_lengths,
                help="Random input token length"
            )
        else:
            st.multiselect(
                "Input Length",
                options=[],
                default=[],
                disabled=True,
                help="No input length data available"
            )
            selected_input_lengths = None

    with col6:
        # Scenario filter - remove empty strings and deduplicate
        scenarios = sorted(set([s for s in df['scenario'].unique() if s and s.strip()]))
        selected_scenarios = st.multiselect(
            "Scenario",
            options=scenarios,
            default=scenarios,
            help="Test scenario: baseline, latency, or all"
        )

    # Filters - Row 3: Version and test identification
    col7, col8 = st.columns(2)

    with col7:
        # Filter out "unknown" and keep only real versions
        vllm_versions = sorted([v for v in df['vllm_version'].unique() if v and v != 'unknown'])
        selected_vllm_versions = st.multiselect(
            "vLLM Version",
            options=vllm_versions,
            default=vllm_versions,
            help="vLLM software version (detected automatically)"
        )

    with col8:
        # Test name filter - only show if there are custom names
        test_names = sorted([n for n in df['test_name'].unique() if n is not None and n.strip()])
        if test_names:
            selected_test_names = st.multiselect(
                "Test Name",
                options=test_names,
                default=test_names,
                help="Custom test configuration name"
            )
        else:
            selected_test_names = None

    if not selected_models:
        st.warning("Please select at least one model")
        return

    # Apply filters
    filtered_df = df[
        (df['model'].isin(selected_models)) &
        (df['platform'].isin(selected_platforms)) &
        (df['vllm_mode'] == selected_vllm_mode)
    ]

    # Apply core count filter (only if data exists)
    if selected_core_counts:
        filtered_df = filtered_df[filtered_df['requested_cores'].isin(selected_core_counts)]

    # Apply input length filter (only if data exists)
    if selected_input_lengths:
        filtered_df = filtered_df[filtered_df['input_length'].isin(selected_input_lengths)]

    # Apply scenario filter
    if selected_scenarios:
        filtered_df = filtered_df[filtered_df['scenario'].isin(selected_scenarios)]

    # Apply vLLM version filter
    if selected_vllm_versions:
        filtered_df = filtered_df[filtered_df['vllm_version'].isin(selected_vllm_versions)]

    # Apply test name filter (only if custom names exist)
    if selected_test_names is not None:
        filtered_df = filtered_df[filtered_df['test_name'].isin(selected_test_names)]

    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
        return

    # Show what's being displayed
    unique_models = filtered_df['model'].unique()
    unique_cores = sorted(filtered_df['requested_cores'].unique())
    unique_test_runs = len(filtered_df['test_run_id'].unique())

    st.info(f"📊 Displaying: **{len(unique_models)} model(s)** ({', '.join([m.split('/')[-1] for m in unique_models])}) | "
            f"**{len(unique_cores)} core config(s)** ({', '.join([f'{c}c' for c in unique_cores])}) | "
            f"**{unique_test_runs} test run(s)** | "
            f"**{len(filtered_df)} data points**")

    # Main analysis tabs - show all filtered data together
    st.header("📊 Performance Analysis")

    tab1, tab2 = st.tabs(["🔀 Concurrent Load", "📊 Saturation Analysis"])

    with tab1:
        concurrent_data = filtered_df[filtered_df['test_type'] == 'concurrent']
        if not concurrent_data.empty:
            plot_concurrent_load(concurrent_data)
        else:
            st.info("No concurrent load data available for selected filters. Run latency tests to generate this data.")

    with tab2:
        baseline_data = filtered_df[filtered_df['test_type'] == 'baseline']
        if not baseline_data.empty:
            plot_saturation_curve(baseline_data)
        else:
            st.info("No baseline saturation data available for selected filters. Run baseline tests to generate this data.")

    st.markdown("---")

    # Scaling Efficiency Analysis
    baseline_inf_data = filtered_df[
        (filtered_df['test_type'] == 'baseline') &
        (filtered_df['parameter'] == 'inf')
    ]

    if not baseline_inf_data.empty and baseline_inf_data['requested_cores'].nunique() > 1:
        st.header("📈 Core Scaling Efficiency")
        st.markdown("How well does throughput scale when adding more CPU cores?")

        # Group by model and cores, get max RPS at inf load
        scaling_analysis = baseline_inf_data.groupby(['model', 'requested_cores']).agg({
            'request_throughput_rps': 'max',
            'rps_per_core': 'max'
        }).reset_index()

        col1, col2 = st.columns(2)

        with col1:
            # Throughput vs Core Count
            fig_scaling = px.bar(
                scaling_analysis,
                x='requested_cores',
                y='request_throughput_rps',
                color='model',
                barmode='group',
                title='Max Throughput vs Core Count',
                labels={
                    'requested_cores': 'CPU Cores',
                    'request_throughput_rps': 'Max RPS (at inf load)',
                    'model': 'Model'
                },
                text='request_throughput_rps'
            )
            fig_scaling.update_traces(texttemplate='%{text:.1f}', textposition='outside')
            fig_scaling.update_layout(height=400)
            st.plotly_chart(fig_scaling, use_container_width=True)

        with col2:
            # RPS per Core (efficiency)
            fig_efficiency = px.bar(
                scaling_analysis,
                x='requested_cores',
                y='rps_per_core',
                color='model',
                barmode='group',
                title='Efficiency: RPS per Core',
                labels={
                    'requested_cores': 'CPU Cores',
                    'rps_per_core': 'RPS per Core',
                    'model': 'Model'
                },
                text='rps_per_core'
            )
            fig_efficiency.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_efficiency.update_layout(height=400)
            st.plotly_chart(fig_efficiency, use_container_width=True)

        # Calculate scaling efficiency
        st.subheader("Scaling Efficiency Metrics")

        efficiency_data = []
        for model in scaling_analysis['model'].unique():
            model_data = scaling_analysis[scaling_analysis['model'] == model].sort_values('requested_cores')

            if len(model_data) > 1:
                base_row = model_data.iloc[0]
                base_cores = base_row['requested_cores']
                base_rps = base_row['request_throughput_rps']

                for _, row in model_data.iloc[1:].iterrows():
                    cores = row['requested_cores']
                    rps = row['request_throughput_rps']

                    theoretical_speedup = cores / base_cores
                    actual_speedup = rps / base_rps
                    efficiency_pct = (actual_speedup / theoretical_speedup) * 100

                    efficiency_data.append({
                        'Model': model.split('/')[-1],
                        'Baseline': f"{base_cores}c",
                        'Comparison': f"{cores}c",
                        'Theoretical Speedup': f"{theoretical_speedup:.1f}x",
                        'Actual Speedup': f"{actual_speedup:.2f}x",
                        'Efficiency %': f"{efficiency_pct:.1f}%"
                    })

        if efficiency_data:
            efficiency_df = pd.DataFrame(efficiency_data)
            st.dataframe(efficiency_df, use_container_width=True)

            st.info("""
            **Scaling Efficiency** shows how close actual performance gains are to theoretical (linear) scaling.
            - **100%** = Perfect linear scaling (doubling cores doubles throughput)
            - **>80%** = Good scaling efficiency
            - **<80%** = Diminishing returns, bottlenecks present
            """)

    st.markdown("---")

    # Raw data export
    with st.expander("📥 Export Data"):
        st.subheader("Download Results")
        csv = filtered_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="embedding-results.csv",
            mime="text/csv"
        )
        st.dataframe(filtered_df, use_container_width=True)


if __name__ == "__main__":
    main()
