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
from config_manager import DashboardConfig, normalize_vllm_version

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


@st.cache_data(ttl=3600)  # Increased from 5min to 1 hour - results rarely change
def load_embedding_data(results_dir: str) -> pd.DataFrame:
    """Load embedding benchmark results from directory structure."""
    results_path = Path(results_dir)
    all_results = []

    # Track skipped/failed files for user feedback
    stats = {
        'total_metadata_files': 0,
        'skipped_missing_fields': 0,
        'skipped_missing_metrics': 0,
        'skipped_json_errors': 0,
        'failed_unexpected': 0
    }

    if not results_path.exists():
        logger.warning(f"Results directory not found: {results_path}")
        return pd.DataFrame()

    # Scan for all test-metadata.json files in embedding results
    for metadata_file in results_path.rglob("test-metadata.json"):
        stats['total_metadata_files'] += 1
        try:
            with open(metadata_file) as f:
                metadata = json.load(f)

            # Validate required metadata fields
            required_fields = ['test_run_id', 'model', 'platform']
            missing = [f for f in required_fields if f not in metadata or not metadata[f]]
            if missing:
                logger.warning(f"Skipping {metadata_file}: missing required fields {missing}")
                stats['skipped_missing_fields'] += 1
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
                    try:
                        with open(json_file) as f:
                            result = json.load(f)

                        # Validate result has key metrics
                        required_metrics = ['request_throughput', 'mean_e2el_ms']
                        missing_metrics = [m for m in required_metrics if m not in result]
                        if missing_metrics:
                            logger.warning(f"Skipping {json_file}: missing metrics {missing_metrics}")
                            stats['skipped_missing_metrics'] += 1
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
                        test_name = ''
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
                            'vllm_version': normalize_vllm_version(metadata.get('vllm_version', 'unknown')),
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

                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON in {json_file}: {e}")
                        stats['skipped_json_errors'] += 1
                        continue

        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            logger.warning(f"Failed to load {metadata_file}: {e}")
            stats['skipped_json_errors'] += 1
            continue
        except Exception as e:
            logger.error(f"Unexpected error loading {metadata_file}: {e}")
            stats['failed_unexpected'] += 1
            # Re-raise unexpected errors - don't hide bugs
            raise

    # Log statistics about data loading
    logger.info(f"Data loading complete: {len(all_results)} result files loaded from {stats['total_metadata_files']} test runs")
    if stats['skipped_missing_fields'] > 0 or stats['skipped_missing_metrics'] > 0 or stats['skipped_json_errors'] > 0:
        logger.warning(
            f"Skipped files: {stats['skipped_missing_fields']} missing fields, "
            f"{stats['skipped_missing_metrics']} missing metrics, "
            f"{stats['skipped_json_errors']} JSON errors"
        )

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

    # Create subplots: 2 rows, 1 column
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Throughput vs Load', 'E2E Latency vs Load'),
        vertical_spacing=0.25
    )

    colors = px.colors.qualitative.Set2
    color_idx = 0

    # Order for load levels (for sorting display)
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

        # Graph 1: Load (x-axis) vs Throughput (y-axis)
        fig.add_trace(
            go.Scatter(
                x=group_df['parameter'],
                y=group_df['request_throughput_rps'],
                name=base_label,
                mode='lines+markers',
                marker=dict(size=8, color=colors[color_idx % len(colors)]),
                line=dict(width=3, color=colors[color_idx % len(colors)]),
                legendgroup=base_label
            ),
            row=1, col=1
        )

        # Graph 2: Load (x-axis) vs Latency (y-axis)
        fig.add_trace(
            go.Scatter(
                x=group_df['parameter'],
                y=group_df['p99_latency_ms'],
                name=base_label,
                mode='lines+markers',
                marker=dict(size=8, color=colors[color_idx % len(colors)]),
                line=dict(width=3, color=colors[color_idx % len(colors)]),
                showlegend=False,
                legendgroup=base_label
            ),
            row=2, col=1
        )

        color_idx += 1

    # X-axes for both graphs (categorical load levels)
    fig.update_xaxes(
        title_text="Load Level",
        categoryorder='array',
        categoryarray=['25pct', '50pct', '75pct', 'inf'],
        row=1, col=1
    )
    fig.update_xaxes(
        title_text="Load Level",
        categoryorder='array',
        categoryarray=['25pct', '50pct', '75pct', 'inf'],
        row=2, col=1
    )

    # Y-axes for metrics
    fig.update_yaxes(title_text="Request Throughput (req/s)", row=1, col=1)
    fig.update_yaxes(title_text="P99 E2E Latency (ms)", row=2, col=1)

    fig.update_layout(
        title="Saturation Analysis: Throughput & E2E Latency vs Load",
        hovermode='closest',
        height=1200,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(b=400)  # Add bottom margin for legend
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
        height=650,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.45,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(b=200)
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

    # Throughput metric selector
    throughput_metric = st.radio(
        "Throughput Metric",
        options=["RPS", "Token/s"],
        horizontal=True,
        help="Select throughput metric: Requests per second or Tokens per second"
    )
    throughput_col = 'request_throughput_rps' if throughput_metric == "RPS" else 'token_throughput_tps'
    throughput_label = "Request Throughput (req/s)" if throughput_metric == "RPS" else "Token Throughput (tokens/s)"

    # Group by test configuration
    grouped = df.groupby([
        'platform', 'model', 'vllm_version', 'requested_cores',
        'input_length', 'test_name', 'test_run_id'
    ])

    colors = px.colors.qualitative.Set2
    color_idx = 0

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
        height=650,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.45,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(b=200)
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Latency metric selector (after throughput graph)
    latency_metric = st.radio(
        "E2E Latency Metric",
        options=["Mean", "P99"],
        horizontal=True,
        help="Select which E2E latency metric to display"
    )
    latency_col = 'mean_latency_ms' if latency_metric == "Mean" else 'p99_latency_ms'

    # E2E Latency vs concurrency
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
        title=f"{latency_metric} E2E Latency vs Concurrency",
        xaxis_title="Concurrent Requests",
        yaxis_title=f"{latency_metric} E2E Latency (ms)",
        height=650,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.45,
            xanchor="center",
            x=0.5,
            font=dict(size=10)
        ),
        margin=dict(b=200)
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
            title='P99 E2E Latency Comparison',
            text='p99_latency_ms'
        )
        fig2.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig2.update_layout(xaxis_title="Model", yaxis_title="P99 E2E Latency (ms)", height=400)
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
            "Performance Results Directory",
            value=default_results_dir,
            help="Path to embedding performance results directory",
            key="results_dir_embedding"
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()

        st.markdown("---")
        st.subheader("📥 Import CSV")

        uploaded_file = st.file_uploader(
            "Upload embedding results CSV",
            type=['csv'],
            help="Upload CSV with embedding benchmark results",
            key="csv_uploader_embedding"
        )

        if uploaded_file is not None:
            try:
                imported_df = pd.read_csv(uploaded_file)

                # Show what we're importing
                st.write(f"📄 **Importing:** {uploaded_file.name}")
                st.write(f"📊 **Rows:** {len(imported_df)}")
                st.write(f"📋 **Columns:** {len(imported_df.columns)}")

                # Check for required columns
                required_cols = ['test_type', 'model', 'platform']
                missing_cols = [col for col in required_cols if col not in imported_df.columns]

                if missing_cols:
                    st.error(f"❌ Missing required columns: {missing_cols}")
                    st.write("**Available columns:**", list(imported_df.columns))
                else:
                    st.session_state['imported_embedding_performance'] = imported_df
                    st.success(f"✓ Loaded {len(imported_df)} rows")

                    # Show a sample
                    with st.expander("Preview imported data"):
                        st.dataframe(imported_df.head(3))

                    st.cache_data.clear()
                    st.info("⚠️ **Data loaded!** Scroll down to see charts or click '🔄 Reload Data' to refresh.")

            except Exception as e:
                st.error(f"Failed to load CSV: {e}")
                import traceback
                st.code(traceback.format_exc())

        if 'imported_embedding_performance' in st.session_state:
            if st.button("❌ Clear imported CSV"):
                del st.session_state['imported_embedding_performance']
                st.rerun()

        st.markdown("---")
        st.markdown("**Performance Metrics:**")
        st.markdown("""
        - Request Throughput (req/s)
        - E2E Latency (P50, P99)
        - Token Processing Speed
        - Concurrent Request Handling
        """)

    # Load performance data
    df = load_embedding_data(results_dir_input)

    # Check for imported CSV data in session state
    if 'imported_embedding_performance' in st.session_state:
        imported_df = st.session_state['imported_embedding_performance'].copy()
        if not imported_df.empty:
            # Ensure data types match expected format
            # Convert numeric columns that might be strings
            numeric_cols = [
                'requested_cores', 'input_length', 'request_rate', 'max_concurrency',
                'num_prompts', 'request_throughput_rps', 'token_throughput_tps',
                'rps_per_core', 'mean_latency_ms', 'median_latency_ms',
                'std_latency_ms', 'p99_latency_ms', 'duration_sec',
                'completed_requests', 'total_input_tokens'
            ]

            for col in numeric_cols:
                if col in imported_df.columns:
                    # Handle 'inf' string values
                    imported_df[col] = pd.to_numeric(imported_df[col], errors='coerce')

            # Merge imported CSV with loaded data
            original_count = len(df)
            df = pd.concat([df, imported_df], ignore_index=True)
            st.success(f"✓ Imported {len(imported_df)} CSV records (merged with {original_count} from directory)")

    if df.empty:
        st.error(f"No results found in `{results_dir_input}`")
        st.info("""
        Run embedding benchmarks first:

        ```bash
        ansible-playbook embedding-benchmark.yml \\
          -e "test_model=RedHatAI/all-MiniLM-L6-v2" \\
          -e "scenario=all"
        ```

        For MTEB embedding quality metrics, use the **🎯 MTEB Metrics** page.
        """)
        return

    st.success(f"✓ Loaded {len(df)} performance test results")

    # Only show filters if we have performance data
    if not df.empty:
        # Filters Header
        st.markdown("### 🔍 Performance Data Filters")

        # Filters - Row 1: Primary filters
        col1, col2, col3 = st.columns(3)

        with col1:
            models = sorted(df['model'].unique())
            selected_models = st.multiselect(
                "Models",
                options=models,
                default=models,  # Select all models by default
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
            # Preserve deselections while auto-selecting newly available scenarios:
            # intersect prev_selection with current scenarios (drops gone options and
            # respects user deselections), then union only the net-new scenarios so
            # they are selected by default when they first appear.
            _scenario_key = '_embedding_scenario_filter'
            _scenario_opts_key = '_embedding_scenario_opts'
            if st.session_state.get(_scenario_opts_key) != scenarios:
                prev_opts = set(st.session_state.get(_scenario_opts_key, []))
                prev_selection = set(st.session_state.get(_scenario_key, scenarios))
                new_scenarios = set(scenarios) - prev_opts
                st.session_state[_scenario_key] = sorted(
                    (prev_selection & set(scenarios)) | new_scenarios
                )
                st.session_state[_scenario_opts_key] = scenarios
            selected_scenarios = st.multiselect(
                "Scenario",
                options=scenarios,
                default=scenarios,
                key=_scenario_key,
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

    # Main analysis tabs
    st.header("📊 Performance Analysis")

    tab1, tab2, tab3 = st.tabs(["🔀 Concurrent Load", "📊 Saturation Analysis", "⚙️ Core Scaling"])

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

    with tab3:
        st.markdown("*Analyze how performance scales when adding more CPU cores (baseline data at max load)*")

        baseline_inf_data = filtered_df[
            (filtered_df['test_type'] == 'baseline') &
            (filtered_df['parameter'] == 'inf')
        ]

        if not baseline_inf_data.empty and baseline_inf_data['requested_cores'].nunique() > 1:
            st.subheader("📈 Throughput Scaling")
            st.markdown("How well does throughput scale when adding more CPU cores?")

            scaling_analysis = baseline_inf_data.groupby(['model', 'requested_cores']).agg({
                'request_throughput_rps': 'max',
                'rps_per_core': 'max'
            }).reset_index()

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

                        if actual_speedup < 1.0:
                            speedup_display = f"❌ {actual_speedup:.2f}x (SLOWER)"
                            verdict = "❌ Degraded"
                        elif efficiency_pct < 50:
                            speedup_display = f"⚠️ {actual_speedup:.2f}x"
                            verdict = "⚠️ Poor"
                        elif efficiency_pct < 80:
                            speedup_display = f"{actual_speedup:.2f}x"
                            verdict = "⚠️ Fair"
                        else:
                            speedup_display = f"✅ {actual_speedup:.2f}x"
                            verdict = "✅ Good"

                        efficiency_data.append({
                            'Model': model.split('/')[-1],
                            'Baseline': f"{base_cores}c",
                            'Comparison': f"{cores}c",
                            'Theoretical Speedup': f"{theoretical_speedup:.1f}x",
                            'Actual Speedup': speedup_display,
                            'Efficiency %': f"{efficiency_pct:.1f}%",
                            'Verdict': verdict
                        })

            if efficiency_data:
                efficiency_df = pd.DataFrame(efficiency_data)
                st.dataframe(efficiency_df, use_container_width=True)

                st.info("""
                **Scaling Efficiency** shows how close actual performance gains are to theoretical (linear) scaling.

                **Verdict Guide:**
                - ✅ **Good** (≥80%): Excellent scaling - worth adding cores
                - ⚠️ **Fair** (50-80%): Moderate scaling - some benefit but diminishing returns
                - ⚠️ **Poor** (<50%): Minimal benefit - cores are underutilized
                - ❌ **Degraded** (<1.0x speedup): **Performance got WORSE** - overhead exceeds benefit

                **Actual Speedup:**
                - **<1.0x** means adding cores made it **SLOWER** (avoid this configuration)
                - **1.0x-2.0x** for doubling cores = partial scaling (check if worth the resources)
                - **2.0x** for doubling cores = perfect linear scaling (ideal)
                """)

            st.subheader("🎯 Best Configurations")

            best_configs = []
            for model in scaling_analysis['model'].unique():
                model_data = scaling_analysis[scaling_analysis['model'] == model].copy()

                best_throughput_row = model_data.loc[model_data['request_throughput_rps'].idxmax()]
                best_throughput_cores = int(best_throughput_row['requested_cores'])
                best_throughput_rps = best_throughput_row['request_throughput_rps']

                best_efficiency_row = model_data.loc[model_data['rps_per_core'].idxmax()]
                best_efficiency_cores = int(best_efficiency_row['requested_cores'])
                best_efficiency_rps_per_core = best_efficiency_row['rps_per_core']
                best_efficiency_rps = best_efficiency_row['request_throughput_rps']

                model_short = model.split('/')[-1]

                best_configs.append({
                    'Model': model_short,
                    'Best Throughput': f"{best_throughput_cores}c @ {best_throughput_rps:.1f} RPS",
                    'Best Efficiency': f"{best_efficiency_cores}c @ {best_efficiency_rps_per_core:.2f} RPS/core ({best_efficiency_rps:.1f} RPS)"
                })

            if best_configs:
                config_df = pd.DataFrame(best_configs)
                st.dataframe(config_df, use_container_width=True, hide_index=True)

                st.markdown("""
                **How to choose:**
                - **Best Throughput**: Maximum RPS - use when you need highest absolute performance
                - **Best Efficiency**: Lowest resource usage per request - use for cost optimization or when running multiple instances
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
