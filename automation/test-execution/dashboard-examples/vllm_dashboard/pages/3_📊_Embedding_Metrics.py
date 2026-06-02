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
                        'request_throughput_rps': result.get('request_throughput'),
                        'token_throughput_tps': result.get('total_token_throughput'),
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

    # Metrics table for all configurations
    st.subheader("Baseline Metrics (All Configurations)")

    # Prepare display dataframe with config info
    display_df = df.copy()
    display_df['config'] = display_df.apply(
        lambda row: f"{row['model'].split('/')[-1]} | {row['requested_cores']}c | {row['input_length']}tok | run {row['test_run_id'][-8:]}",
        axis=1
    )

    metrics_display = display_df[[
        'config', 'parameter', 'request_throughput_rps', 'p99_latency_ms',
        'mean_latency_ms', 'median_latency_ms'
    ]].copy()
    metrics_display.columns = ['Configuration', 'Load', 'RPS', 'P99 (ms)', 'Mean (ms)', 'Median (ms)']
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

    # Latency metric selector
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
                y=group_df['request_throughput_rps'],
                name=label,
                mode='lines+markers',
                marker=dict(size=8, color=colors[color_idx % len(colors)]),
                line=dict(width=3, color=colors[color_idx % len(colors)])
            ))
            color_idx += 1

        fig1.update_layout(
            title="Throughput vs Concurrency",
            xaxis_title="Concurrent Requests",
            yaxis_title="Request Throughput (req/s)",
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
        'config', 'concurrency', 'request_throughput_rps',
        'mean_latency_ms', 'median_latency_ms', 'p99_latency_ms'
    ]].copy()
    metrics_display.columns = ['Configuration', 'Concurrency', 'RPS', 'Mean (ms)', 'Median (ms)', 'P99 (ms)']
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

    # Debug info
    with st.expander("🔍 Debug: Data Overview"):
        st.write(f"Total rows loaded: {len(df)}")
        st.write(f"Unique models: {df['model'].unique().tolist()}")
        st.write(f"Unique platforms: {df['platform'].unique().tolist()}")
        st.write(f"Unique vllm_modes: {df['vllm_mode'].unique().tolist()}")
        st.write(f"Unique scenarios: {df['scenario'].unique().tolist()}")
        st.write(f"Unique requested_cores: {df['requested_cores'].unique().tolist()}")
        st.write(f"Unique input_length: {df['input_length'].unique().tolist()}")
        st.write(f"Unique vllm_version: {df['vllm_version'].unique().tolist()}")
        st.write(f"Unique test_runs: {df['test_run_id'].unique().tolist()[:5]} (showing first 5)")
        st.write(f"Unique test_types: {df['test_type'].unique().tolist()}")
        st.write(f"Sample data (first 3 rows):")
        st.dataframe(df.head(3)[[
            'test_run_id', 'model', 'scenario', 'test_type', 'parameter',
            'requested_cores', 'input_length', 'vllm_version'
        ]])

    # Apply filters with debug tracking
    step1 = df[df['model'].isin(selected_models)]
    step2 = step1[step1['platform'].isin(selected_platforms)]
    filtered_df = step2[step2['vllm_mode'] == selected_vllm_mode]

    # Apply core count filter (only if data exists)
    if selected_core_counts:
        before_cores = len(filtered_df)
        filtered_df = filtered_df[filtered_df['requested_cores'].isin(selected_core_counts)]
        after_cores = len(filtered_df)
    else:
        before_cores = after_cores = len(filtered_df)

    # Apply input length filter (only if data exists)
    if selected_input_lengths:
        before_input = len(filtered_df)
        filtered_df = filtered_df[filtered_df['input_length'].isin(selected_input_lengths)]
        after_input = len(filtered_df)
    else:
        before_input = after_input = len(filtered_df)

    # Apply scenario filter
    if selected_scenarios:
        before_scenario = len(filtered_df)
        filtered_df = filtered_df[filtered_df['scenario'].isin(selected_scenarios)]
        after_scenario = len(filtered_df)
    else:
        before_scenario = after_scenario = len(filtered_df)

    # Apply vLLM version filter
    if selected_vllm_versions:
        before_version = len(filtered_df)
        filtered_df = filtered_df[filtered_df['vllm_version'].isin(selected_vllm_versions)]
        after_version = len(filtered_df)
    else:
        before_version = after_version = len(filtered_df)

    # Apply test name filter (only if custom names exist)
    if selected_test_names is not None:
        before_name = len(filtered_df)
        filtered_df = filtered_df[filtered_df['test_name'].isin(selected_test_names)]
        after_name = len(filtered_df)
    else:
        before_name = after_name = len(filtered_df)

    with st.expander("🔍 Debug: Filter Steps"):
        st.write(f"After model filter: {len(step1)} rows")
        st.write(f"After platform filter: {len(step2)} rows")
        st.write(f"After vllm_mode filter: {len(filtered_df)} rows")
        st.write(f"After core_count filter: {after_cores} rows (from {before_cores})")
        st.write(f"After input_length filter: {after_input} rows (from {before_input})")
        st.write(f"After scenario filter: {after_scenario} rows (from {before_scenario})")
        st.write(f"After vllm_version filter: {after_version} rows (from {before_version})")
        st.write(f"After test_name filter: {after_name} rows (from {before_name})")

    if filtered_df.empty:
        st.warning("No data matches the selected filters. Check the debug info above to see where data was lost.")
        return

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
