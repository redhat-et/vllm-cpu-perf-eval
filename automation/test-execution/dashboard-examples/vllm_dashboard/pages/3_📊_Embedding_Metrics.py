"""vLLM Embedding Model Performance Dashboard.

Analyzes embedding model benchmark results from vllm bench serve.
Provides saturation curves, core scaling, and concurrent load analysis.
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
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


def normalize_vllm_version(version_string):
    """Normalize vLLM version for display.

    Maps the current RHAIIS vLLM version to a user-friendly display name.
    Future versions are displayed as-is.

    Args:
        version_string: Raw vLLM version from metadata

    Returns:
        "RHAIIS_3.4" for current version, original string otherwise
    """
    if not version_string or version_string == 'unknown':
        return 'unknown'

    # Current RHAIIS 3.4 version
    if version_string == '0.18.0+rhaiv.7':
        return 'RHAIIS_3.4'

    # All other versions (past or future) display as-is
    return version_string

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


@st.cache_data(ttl=3600)
def load_mteb_data(results_dir: str) -> pd.DataFrame:
    """Load MTEB benchmark results from directory structure.

    MTEB results can be in two formats:

    Format 1 (Expected):
    results/mteb/MODEL/TIMESTAMP/TaskName/test.json

    Format 2 (Actual MTEB output):
    results/mteb/MODEL/TIMESTAMP/no_model_name_available/no_revision_available/TaskName.json

    This function handles both formats.
    """
    results_path = Path(results_dir)
    all_results = []

    if not results_path.exists():
        logger.warning(f"MTEB results directory not found: {results_path}")
        return pd.DataFrame()

    # Scan for all run_summary.json files
    for summary_file in results_path.rglob("run_summary.json"):
        try:
            with open(summary_file) as f:
                summary = json.load(f)

            model = summary.get('model', 'unknown')
            timestamp = summary.get('timestamp', 'unknown')
            task_preset = summary.get('task_preset', 'custom')

            # Get test run directory
            test_run_dir = summary_file.parent

            # Look for task results in multiple possible locations
            task_files = []

            # Format 1: TaskName/test.json subdirectories
            for task_dir in test_run_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                test_file = task_dir / "test.json"
                if test_file.exists():
                    task_files.append((task_dir.name, test_file, 'format1'))

            # Format 2: Look in no_model_name_available/no_revision_available/*.json
            mteb_output_dir = test_run_dir / "no_model_name_available" / "no_revision_available"
            if mteb_output_dir.exists() and mteb_output_dir.is_dir():
                for result_file in mteb_output_dir.glob("*.json"):
                    # Skip model_meta.json
                    if result_file.name == "model_meta.json":
                        continue
                    task_name = result_file.stem  # filename without .json
                    task_files.append((task_name, result_file, 'format2'))

            # Process all found task files
            for task_name, task_file, file_format in task_files:
                try:
                    with open(task_file) as f:
                        task_results = json.load(f)

                    # Extract metrics - handle both formats:
                    # 1. Top-level 'test' key (normalized format)
                    # 2. Nested 'scores.test' (MTEB default format)
                    test_scores = task_results.get('test')
                    if test_scores is None:
                        test_scores = task_results.get('scores', {}).get('test', [])

                    # Normalize to list format
                    if isinstance(test_scores, dict):
                        test_scores = [test_scores]
                    elif not test_scores or len(test_scores) == 0:
                        logger.warning(f"No test scores found in {task_file}")
                        continue

                    # Get experiments array
                    scores_per_experiment = test_scores[0].get('scores_per_experiment', [])

                    if not scores_per_experiment:
                        # Try direct metrics (old format)
                        test_metrics = test_scores[0]
                    else:
                        # Average across experiments (MTEB standard format)
                        test_metrics = {}

                        # List of all possible metrics
                        metric_keys = ['accuracy', 'f1', 'precision', 'recall',
                                     'ndcg_at_10', 'map', 'mrr', 'v_measure',
                                     'cosine_spearman', 'cosine_pearson']

                        for metric_key in metric_keys:
                            values = [exp.get(metric_key) for exp in scores_per_experiment
                                    if exp.get(metric_key) is not None]
                            if values:
                                test_metrics[metric_key] = np.mean(values)

                    # Build row with all available metrics
                    row = {
                        'model': model,
                        'timestamp': timestamp,
                        'task_preset': task_preset,
                        'task_name': task_name,
                        # Common metrics (not all tasks have all of these)
                        'accuracy': test_metrics.get('accuracy'),
                        'f1': test_metrics.get('f1'),
                        'precision': test_metrics.get('precision'),
                        'recall': test_metrics.get('recall'),
                        'ndcg_at_10': test_metrics.get('ndcg_at_10'),
                        'map': test_metrics.get('map'),
                        'mrr': test_metrics.get('mrr'),
                        'v_measure': test_metrics.get('v_measure'),
                        'cosine_spearman': test_metrics.get('cosine_spearman'),
                        'cosine_pearson': test_metrics.get('cosine_pearson'),
                    }
                    all_results.append(row)

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse {task_file}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing {task_file}: {e}")
                    continue

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse {summary_file}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error loading {summary_file}: {e}")
            raise

    logger.info(f"MTEB data loading complete: {len(all_results)} task results loaded")
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


def plot_mteb_radar_chart(df: pd.DataFrame, models: list):
    """Create radar chart showing model performance across task categories (MTEB leaderboard style)."""
    if df.empty:
        return

    # Define task categories (like HuggingFace MTEB leaderboard)
    task_categories = {
        'Classification': ['Banking77Classification', 'EmotionClassification', 'ToxicConversationsClassification',
                          'MTOPDomainClassification', 'MTOPIntentClassification'],
        'Clustering': ['ArxivClusteringP2P', 'TwentyNewsgroupsClustering', 'RedditClustering',
                      'StackExchangeClustering'],
        'Pair Classification': ['TwitterSemEval2015', 'TwitterURLCorpus', 'SprintDuplicateQuestions'],
        'Reranking': ['AskUbuntuDupQuestions', 'MindSmallReranking', 'SciDocsRR'],
        'Retrieval': ['ArguAna', 'NFCorpus', 'SCIDOCS', 'FiQA2018', 'TRECCOVID',
                     'Touche2020', 'DBPedia', 'HotpotQA', 'MSMARCO'],
        'STS': ['STS12', 'STS13', 'STS14', 'STS15', 'STS16', 'STS17', 'STS22',
               'STSBenchmark', 'SICKRelatedness'],
        'Summarization': ['SummEval'],
        'BitextMining': ['Tatoeba', 'BUCC']
    }

    # Primary metric per category
    category_metrics = {
        'Classification': 'accuracy',
        'Clustering': 'v_measure',
        'Pair Classification': 'accuracy',
        'Reranking': 'map',
        'Retrieval': 'ndcg_at_10',
        'STS': 'cosine_spearman',
        'Summarization': 'cosine_spearman',
        'BitextMining': 'f1'
    }

    # Calculate average score per category per model
    # Note: df is already deduplicated by calling code (one row per model+task)
    category_scores = []

    for model in models:
        model_df = df[df['model'] == model]
        scores = {}

        for category, tasks in task_categories.items():
            # Find tasks in this category that we have data for
            category_tasks = [t for t in tasks if t in model_df['task_name'].values]

            if not category_tasks:
                continue

            # Get the appropriate metric for this category
            metric = category_metrics.get(category)
            if not metric:
                continue

            # Get values for this metric across category tasks
            task_values = []
            for task in category_tasks:
                task_df = model_df[model_df['task_name'] == task]
                if not task_df.empty:
                    val = task_df[metric].iloc[0]  # Now deterministic - only one row per task
                    if pd.notna(val):
                        task_values.append(val)

            # Average across tasks in category
            if task_values:
                scores[category] = np.mean(task_values)

        if scores:
            category_scores.append({
                'model': model.split('/')[-1],
                **scores
            })

    if not category_scores:
        st.info("Not enough data across task categories for radar chart. Run more comprehensive MTEB tests.")
        return

    # Convert to dataframe
    radar_df = pd.DataFrame(category_scores)

    # Get categories that have data
    categories = [col for col in radar_df.columns if col != 'model']

    if len(categories) < 3:
        st.info("Need at least 3 task categories for meaningful radar chart. Run more comprehensive MTEB tests.")
        return

    # Create radar chart
    fig = go.Figure()

    # Color palette
    colors = px.colors.qualitative.Set2

    for idx, row in radar_df.iterrows():
        model_name = row['model']
        values = [row.get(cat, 0) * 100 for cat in categories]  # Convert to percentage

        # Close the radar chart by repeating first value
        values.append(values[0])
        cats = categories + [categories[0]]

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=cats,
            fill='toself',
            name=model_name,
            line=dict(color=colors[idx % len(colors)], width=2),
            opacity=0.7
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                ticksuffix='%',
                showline=False,
                gridcolor='lightgray'
            ),
            angularaxis=dict(
                gridcolor='lightgray'
            )
        ),
        showlegend=True,
        title="Model Performance Across Task Categories",
        height=600,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.1
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show category details
    with st.expander("📖 What Do These Categories Mean?", expanded=False):
        st.markdown("""
        ### Task Categories Explained

        **Classification** - Text Categorization
        - *What it does:* Assigns text to predefined categories
        - *Example:* "Is this email spam or not spam?" or "Which of 77 banking intents does this query match?"
        - *Why it matters:* Essential for content filtering, intent detection, and organizing large text collections
        - *Metric:* Accuracy (percentage of correctly classified texts)

        **Retrieval** - Information Retrieval
        - *What it does:* Finds relevant documents from a large collection
        - *Example:* "Given this search query, rank 10,000 documents by relevance"
        - *Why it matters:* Powers search engines, RAG systems, and document discovery
        - *Metric:* NDCG@10 (quality of top 10 results, accounting for ranking order)

        **STS** - Semantic Textual Similarity
        - *What it does:* Measures how similar two sentences are in meaning
        - *Example:* "The cat sat on the mat" vs "A feline rested on the rug" (high similarity)
        - *Why it matters:* Duplicate detection, paraphrase identification, sentence comparison
        - *Metric:* Spearman correlation (how well predicted similarity matches human judgment)

        **Reranking** - Result Reordering
        - *What it does:* Takes an initial list of results and improves the ranking
        - *Example:* Search engine returns 100 results; reranker reorders to put best ones first
        - *Why it matters:* Improves search quality, reduces time to find relevant information
        - *Metric:* MAP (Mean Average Precision - rewards relevant docs appearing early)

        **Pair Classification** - Text Pair Relationships
        - *What it does:* Determines relationship between two text pieces
        - *Example:* "Are these two questions duplicates?" or "Do these tweets discuss the same topic?"
        - *Why it matters:* Deduplication, question answering, content matching
        - *Metric:* Accuracy (percentage of correctly identified relationships)

        **Clustering** - Automatic Grouping
        - *What it does:* Groups similar documents together without predefined categories
        - *Example:* "Group these 10,000 research papers by topic" (unsupervised)
        - *Why it matters:* Topic discovery, data exploration, organizing unlabeled content
        - *Metric:* V-measure (balance of homogeneity and completeness in clusters)

        **Summarization** - Condensing Information
        - *What it does:* Evaluates how well embeddings capture document meaning for summarization
        - *Example:* "Does this summary capture the key points of the original article?"
        - *Why it matters:* Quality assessment for automatic summarization systems
        - *Metric:* Spearman correlation (summary-document similarity alignment)

        **BitextMining** - Parallel Text Extraction
        - *What it does:* Finds equivalent sentences across languages
        - *Example:* "Which Spanish sentence is the translation of this English sentence?"
        - *Why it matters:* Machine translation, building bilingual dictionaries, cross-lingual search
        - *Metric:* F1 score (balance of precision and recall in finding parallel sentences)

        ---

        **Scores shown** are averages across all tasks in each category, normalized to 0-100%.
        Higher is better. 80%+ is generally considered very good performance.
        """)

        # Show the data table
        display_radar = radar_df.copy()
        for cat in categories:
            if cat in display_radar.columns:
                display_radar[cat] = (display_radar[cat] * 100).round(1)

        display_radar.columns = ['Model'] + [f"{cat} (%)" for cat in categories]
        st.dataframe(display_radar, use_container_width=True, hide_index=True)


def plot_mteb_quality_metrics(df: pd.DataFrame):
    """Plot MTEB quality metrics across models and tasks."""
    if df.empty:
        st.warning("No MTEB quality data to display")
        st.info("""
        Run MTEB quality benchmarks first:

        ```bash
        ansible-playbook mteb-benchmark.yml \\
          -e "test_model=RedHatAI/granite-embedding-english-r2" \\
          -e "mteb_task_preset=quick"
        ```
        """)
        return

    # Get unique models and tasks
    models = sorted(df['model'].unique())
    all_tasks = sorted(df['task_name'].unique())

    st.markdown("""
    **MTEB (Massive Text Embedding Benchmark)** evaluates embedding quality across multiple dimensions:
    - **Classification**: Text categorization accuracy
    - **Retrieval**: Information retrieval performance (NDCG, MAP, MRR)
    - **Clustering**: Document clustering quality (V-measure)
    - **STS**: Semantic textual similarity correlation

    Higher scores indicate better quality. All metrics range from 0 to 1 (or 0 to 100%).
    """)

    with st.expander("📖 Metric Definitions", expanded=False):
        st.markdown("""
        ### Classification Metrics

        **Accuracy** (0-1, higher is better)
        - What it is: Percentage of correct guesses
        - Example: 0.85 = got it right 85 times out of 100
        - Used in: Banking77Classification, EmotionClassification, ToxicConversations

        **F1 Score** (0-1, higher is better)
        - What it is: Balanced measure of overall correctness
        - Why it matters: Better than accuracy when some categories are rare (e.g., detecting rare diseases)
        - Example: Spam filter with 0.90 F1 catches most spam without blocking real emails

        **Precision** (0-1, higher is better)
        - What it is: When the model says "yes", how often is it right?
        - Example: Spam filter with 0.95 precision → 95% of flagged emails really are spam
        - High precision = fewer innocent emails in spam folder

        **Recall** (0-1, higher is better)
        - What it is: Of all the real "yes" cases, how many did we find?
        - Example: Spam filter with 0.90 recall → catches 90% of actual spam
        - High recall = fewer spam emails slip through to your inbox

        ---

        ### Retrieval Metrics

        **NDCG@10** (0-1, higher is better)
        - What it is: How good are the top 10 search results?
        - Better ranking = higher score (relevant results at the top count more)
        - Example: 0.80 = search results are 80% as good as a perfect ranking
        - Used in: ArguAna, NFCorpus, SCIDOCS retrieval tasks

        **MAP** (Mean Average Precision) (0-1, higher is better)
        - What it is: Do relevant results appear early in the list?
        - Rewards putting good results near the top
        - Example: 0.75 = relevant docs tend to appear in top positions

        **MRR** (Mean Reciprocal Rank) (0-1, higher is better)
        - What it is: How far down do you scroll to find the first good result?
        - Example: First good result at position 2 → score = 1/2 = 0.50
        - High MRR = answer appears right away (like featured snippets in search)

        ---

        ### Clustering Metrics

        **V-Measure** (0-1, higher is better)
        - What it is: How well did it group similar things together?
        - Checks: Are all sports articles in one group? Did it keep all sports articles together?
        - Example: 0.80 = groups are mostly pure, and related items are mostly together
        - Used in: ArxivClustering, TwentyNewsgroups

        ---

        ### Semantic Similarity Metrics

        **Spearman Correlation** (-1 to 1, closer to 1 is better)
        - What it is: Does it agree with human similarity judgments?
        - If humans say A is more similar to B than to C, does the model agree?
        - Example: 0.85 = model rankings match human rankings 85% of the time
        - Used in: STS12, STS15, STS16 tasks

        **Pearson Correlation** (-1 to 1, closer to 1 is better)
        - What it is: Similar to Spearman, but stricter about exact scores
        - Checks if similarity scores are proportional to human ratings
        - Example: 0.82 = strong agreement with human judgments

        ---

        ### Interpretation Guide

        | Score Range | Classification/V-Measure | Retrieval (NDCG/MAP/MRR) | Correlation (Spearman/Pearson) |
        |-------------|--------------------------|--------------------------|----------------------------------|
        | **0.90-1.00** | Excellent | Excellent | Very Strong |
        | **0.80-0.89** | Very Good | Very Good | Strong |
        | **0.70-0.79** | Good | Good | Moderate-Strong |
        | **0.60-0.69** | Fair | Fair | Moderate |
        | **0.50-0.59** | Weak | Weak | Weak |
        | **<0.50** | Poor | Poor | Very Weak/None |

        ### Real Examples

        **NDCG@10 = 0.72 on ArguAna (document search)**
        - The search results are 72% as good as perfect
        - "Good" score - relevant docs usually appear in top 10
        - Works well for most real-world search applications

        **Accuracy = 0.85 on Banking77 (classifying customer questions)**
        - Gets the right category 85 out of 100 times
        - "Very Good" - only 15% wrong
        - Ready for production use in most cases

        **F1 = 0.90 on spam detection**
        - Catches 90% of spam while rarely blocking real email
        - Great balance - high catch rate, low false alarms
        """)


    # Benchmark type categorization
    human_benchmark_tasks = ['STS12', 'STS13', 'STS14', 'STS15', 'STS16', 'STS17',
                            'STSBenchmark', 'SICKRelatedness']  # Tasks with human-annotated similarity scores

    # Human Benchmark filter (matching MTEB leaderboard UI)
    st.markdown("### 🔍 Filters")
    include_human_benchmark = st.checkbox(
        "Human Benchmark",
        value=True,
        help="Include tasks with human-annotated similarity scores (e.g., STS tasks)"
    )

    # Apply human benchmark filter
    benchmark_filtered_tasks = all_tasks.copy()
    if not include_human_benchmark:
        benchmark_filtered_tasks = [t for t in all_tasks if t not in human_benchmark_tasks]

    # Domain-specific task categorization (matching MTEB leaderboard)
    task_domains = {
        'Code': ['StackOverflowDupQuestions', 'CodeSearchNet'],
        'Legal': ['LegalBenchConsumerContractsQA', 'LegalBenchCorporateLobbying', 'LegalSummarization'],
        'Medical': ['MedicalQARetrieval', 'PubMedQA', 'BioASQ'],
        'Financial': ['Banking77Classification', 'FiQA2018'],
        'Scientific': ['SCIDOCS', 'SciDocsRR', 'ArxivClusteringP2P', 'ArxivClusteringS2S'],
        'Social Media': ['TwitterSemEval2015', 'TwitterURLCorpus', 'TweetSentimentExtraction'],
        'News': ['TwentyNewsgroupsClustering'],
        'General': ['ArguAna', 'NFCorpus', 'EmotionClassification', 'ToxicConversationsClassification',
                   'STS12', 'STS13', 'STS14', 'STS15', 'STS16', 'STS17', 'STS22',
                   'AskUbuntuDupQuestions', 'MindSmallReranking', 'SprintDuplicateQuestions',
                   'STSBenchmark', 'SICKRelatedness']
    }

    # Create domain filter
    st.markdown("### 🏷️ Task Selection")
    col1, col2 = st.columns([1, 2])

    with col1:
        # Get domains that have tasks in our data (filtered by benchmark)
        available_domains = []
        for domain, tasks in task_domains.items():
            if any(task in benchmark_filtered_tasks for task in tasks):
                available_domains.append(domain)

        selected_domains = st.multiselect(
            "Domain",
            options=available_domains,
            default=available_domains,
            help="Filter tasks by domain. Select multiple domains or leave all selected."
        )

    # Filter tasks by domain (use benchmark-filtered tasks)
    if selected_domains:
        domain_filtered_tasks = []
        for domain in selected_domains:
            domain_filtered_tasks.extend([t for t in task_domains[domain] if t in benchmark_filtered_tasks])
        available_task_options = sorted(set(domain_filtered_tasks))
    else:
        available_task_options = benchmark_filtered_tasks

    with col2:
        selected_tasks = st.multiselect(
            "Tasks",
            options=available_task_options,
            default=available_task_options,
            help="Choose which MTEB tasks to show. Filtered by domain selection above."
        )

    if not selected_tasks:
        st.warning("Please select at least one task (or choose a domain)")
        return

    filtered_df = df[df['task_name'].isin(selected_tasks)]

    # Deduplicate: Keep only most recent run for each (model, task_name)
    # This ensures consistent results across all visualizations
    filtered_df = (filtered_df.sort_values('timestamp', ascending=False)
                   .drop_duplicates(subset=['model', 'task_name'], keep='first'))

    # Metric selector
    available_metrics = []
    metric_labels = {
        'accuracy': 'Accuracy',
        'f1': 'F1 Score',
        'precision': 'Precision',
        'recall': 'Recall',
        'ndcg_at_10': 'NDCG@10',
        'map': 'MAP',
        'mrr': 'MRR',
        'v_measure': 'V-Measure',
        'cosine_spearman': 'Spearman Correlation',
        'cosine_pearson': 'Pearson Correlation'
    }

    for metric_col in ['accuracy', 'f1', 'ndcg_at_10', 'map', 'mrr', 'v_measure', 'cosine_spearman']:
        if metric_col in filtered_df.columns and filtered_df[metric_col].notna().any():
            available_metrics.append(metric_col)

    if not available_metrics:
        st.warning("No metrics found in selected tasks")
        return

    # Show active filters
    filter_info = []
    if not include_human_benchmark:
        filter_info.append("Excluding Human Benchmark tasks")
    if selected_domains and len(selected_domains) < len(available_domains):
        filter_info.append(f"Domains: {', '.join(selected_domains)}")

    if filter_info:
        st.info(f"📊 Showing {len(selected_tasks)} tasks | Filters: {' | '.join(filter_info)}")

    # Radar chart by task category (HuggingFace MTEB leaderboard style)
    st.subheader("📊 Model Performance by Task Category")
    plot_mteb_radar_chart(filtered_df, models)

    st.subheader("Model Comparison by Task")

    # For each metric, create a grouped bar chart
    for metric in available_metrics:
        # Filter to rows that have this metric
        metric_df = filtered_df[filtered_df[metric].notna()].copy()

        if metric_df.empty:
            continue

        # Create short model names
        metric_df['model_short'] = metric_df['model'].apply(lambda x: x.split('/')[-1])

        # Create grouped bar chart
        fig = px.bar(
            metric_df,
            x='task_name',
            y=metric,
            color='model_short',
            barmode='group',
            title=f'{metric_labels.get(metric, metric)} by Task',
            text=metric
        )
        fig.update_traces(texttemplate='%{text:.3f}', textposition='outside')
        fig.update_layout(
            xaxis_title="Task",
            yaxis_title=metric_labels.get(metric, metric),
            height=500,
            legend_title="Model",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.35,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            margin=dict(b=150)
        )
        st.plotly_chart(fig, use_container_width=True)

    # Overall quality summary table
    st.subheader("Quality Metrics Summary")
    st.markdown("Average performance across all selected tasks. Ratings based on the interpretation guide below.")

    # Pivot to show average scores per model
    summary_data = []
    for model in models:
        model_df = filtered_df[filtered_df['model'] == model]
        row = {'Model': model.split('/')[-1], 'Tasks': len(model_df)}

        for metric in available_metrics:
            metric_values = model_df[metric].dropna()
            if not metric_values.empty:
                row[metric_labels.get(metric, metric)] = metric_values.mean()

        summary_data.append(row)

    if summary_data:
        # Show numeric scores
        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.round(3)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # Show quality ratings below
        st.markdown("**Quality Ratings** (based on interpretation guide)")

        def classify_score(score):
            """Classify score according to interpretation guide."""
            if pd.isna(score):
                return "N/A"

            if score >= 0.90:
                return "⭐ Excellent"
            elif score >= 0.80:
                return "✅ Very Good"
            elif score >= 0.70:
                return "👍 Good"
            elif score >= 0.60:
                return "👌 Fair"
            elif score >= 0.50:
                return "⚠️ Weak"
            else:
                return "❌ Poor"

        classification_data = []
        for row in summary_data:
            class_row = {'Model': row['Model']}

            # Classify each metric
            for metric in available_metrics:
                label = metric_labels.get(metric, metric)
                if label in row:
                    class_row[label] = classify_score(row[label])

            classification_data.append(class_row)

        if classification_data:
            class_df = pd.DataFrame(classification_data)
            st.dataframe(class_df, use_container_width=True, hide_index=True)

            st.caption("""
            **Rating Scale:**
            ⭐ Excellent (0.90-1.00) | ✅ Very Good (0.80-0.89) | 👍 Good (0.70-0.79) |
            👌 Fair (0.60-0.69) | ⚠️ Weak (0.50-0.59) | ❌ Poor (<0.50)
            """)

    # Detailed results table
    st.subheader("Detailed Task Results")

    # Helper function to get domain for a task
    def get_task_domain(task_name):
        for domain, tasks in task_domains.items():
            if task_name in tasks:
                return domain
        return "Unknown"

    # Build detailed display
    display_df = filtered_df.copy()
    display_df['model_short'] = display_df['model'].apply(lambda x: x.split('/')[-1])
    display_df['domain'] = display_df['task_name'].apply(get_task_domain)

    # Select columns to display (add domain)
    display_cols = ['model_short', 'task_name', 'domain', 'task_preset'] + available_metrics
    display_df = display_df[display_cols]
    display_df.columns = ['Model', 'Task', 'Domain', 'Preset'] + [metric_labels.get(m, m) for m in available_metrics]
    display_df = display_df.round(3)
    st.dataframe(display_df, use_container_width=True)

    # Show quality ratings for detailed results
    st.markdown("**Quality Ratings** (based on interpretation guide)")

    def classify_score_detailed(score):
        """Classify score according to interpretation guide."""
        if pd.isna(score):
            return "N/A"

        if score >= 0.90:
            return "⭐ Excellent"
        elif score >= 0.80:
            return "✅ Very Good"
        elif score >= 0.70:
            return "👍 Good"
        elif score >= 0.60:
            return "👌 Fair"
        elif score >= 0.50:
            return "⚠️ Weak"
        else:
            return "❌ Poor"

    # Create ratings version of detailed results
    ratings_df = filtered_df.copy()
    ratings_df['model_short'] = ratings_df['model'].apply(lambda x: x.split('/')[-1])
    ratings_df['domain'] = ratings_df['task_name'].apply(get_task_domain)

    # Apply classification to metric columns
    for metric in available_metrics:
        if metric in ratings_df.columns:
            ratings_df[metric] = ratings_df[metric].apply(classify_score_detailed)

    # Select columns and rename (add domain)
    ratings_cols = ['model_short', 'task_name', 'domain', 'task_preset'] + available_metrics
    ratings_df = ratings_df[ratings_cols]
    ratings_df.columns = ['Model', 'Task', 'Domain', 'Preset'] + [metric_labels.get(m, m) for m in available_metrics]
    st.dataframe(ratings_df, use_container_width=True)


def main():
    """Main dashboard application."""
    st.title("📊 Embedding Model Performance")
    st.markdown("Analysis of vLLM embedding benchmark results")

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")

        config = DashboardConfig()
        default_results_dir = str(Path(config.get_results_directory()).parent / "embedding")
        default_mteb_dir = str(Path(config.get_results_directory()).parent / "mteb")

        results_dir_input = st.text_input(
            "Performance Results Directory",
            value=default_results_dir,
            help="Path to embedding performance results directory",
            key="results_dir_embedding"
        )

        mteb_dir_input = st.text_input(
            "MTEB Results Directory",
            value=default_mteb_dir,
            help="Path to MTEB quality results directory",
            key="results_dir_mteb"
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()

        st.markdown("---")
        st.markdown("**Performance Metrics:**")
        st.markdown("""
        - Request Throughput (req/s)
        - E2E Latency (P50, P99)
        - Token Processing Speed
        - Concurrent Request Handling
        """)
        st.markdown("**Quality Metrics (MTEB):**")
        st.markdown("""
        - Classification Accuracy
        - Retrieval Performance (NDCG, MAP)
        - Clustering Quality (V-measure)
        - Semantic Similarity Correlation
        """)

    # Load performance data
    df = load_embedding_data(results_dir_input)

    # Load MTEB quality data
    mteb_df = load_mteb_data(mteb_dir_input)

    if df.empty and mteb_df.empty:
        st.error(f"No results found in {results_dir_input} or {mteb_dir_input}")
        st.info("""
        Run embedding benchmarks first:

        ```bash
        # Performance benchmarks
        ansible-playbook embedding-benchmark.yml \\
          -e "test_model=RedHatAI/all-MiniLM-L6-v2" \\
          -e "scenario=all"

        # Quality benchmarks
        ansible-playbook mteb-benchmark.yml \\
          -e "test_model=RedHatAI/all-MiniLM-L6-v2" \\
          -e "mteb_task_preset=quick"
        ```
        """)
        return

    # Show loading status
    status_parts = []
    if not df.empty:
        status_parts.append(f"{len(df)} performance test results")
    if not mteb_df.empty:
        status_parts.append(f"{len(mteb_df)} MTEB quality results")

    if status_parts:
        st.success(f"✓ Loaded {' and '.join(status_parts)}")

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

        # Debug info disabled - uncomment if needed for troubleshooting
        # unique_models = filtered_df['model'].unique()
        # unique_cores = sorted(filtered_df['requested_cores'].unique())
        # unique_test_runs = len(filtered_df['test_run_id'].unique())
        # st.info(f"📊 Displaying: **{len(unique_models)} model(s)** ({', '.join([m.split('/')[-1] for m in unique_models])}) | "
        #         f"**{len(unique_cores)} core config(s)** ({', '.join([f'{c}c' for c in unique_cores])}) | "
        #         f"**{unique_test_runs} test run(s)** | "
        #         f"**{len(filtered_df)} data points**")
    else:
        # No performance data available - skip filters
        filtered_df = pd.DataFrame()

    # Main analysis tabs - show all filtered data together
    st.header("📊 Performance Analysis")

    # Determine which tabs to show
    has_performance = not df.empty
    has_quality = not mteb_df.empty

    if has_performance and has_quality:
        tab1, tab2, tab3, tab4 = st.tabs(["🔀 Concurrent Load", "📊 Saturation Analysis", "⚙️ Core Scaling", "🎯 MTEB Quality"])
    elif has_performance:
        tab1, tab2, tab3 = st.tabs(["🔀 Concurrent Load", "📊 Saturation Analysis", "⚙️ Core Scaling"])
    elif has_quality:
        tab4 = st.container()
        st.markdown("### 🎯 MTEB Quality Metrics")
    else:
        st.warning("No data available")
        return

    if has_performance:
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
            # ==============================================================================
            # Core Scaling Analysis Section
            # ==============================================================================

            st.markdown("*Analyze how performance scales when adding more CPU cores (baseline data at max load)*")

            baseline_inf_data = filtered_df[
                (filtered_df['test_type'] == 'baseline') &
                (filtered_df['parameter'] == 'inf')
            ]

            if not baseline_inf_data.empty and baseline_inf_data['requested_cores'].nunique() > 1:
                st.subheader("📈 Throughput Scaling")
                st.markdown("How well does throughput scale when adding more CPU cores?")

                # Group by model and cores, get max RPS at inf load
                scaling_analysis = baseline_inf_data.groupby(['model', 'requested_cores']).agg({
                    'request_throughput_rps': 'max',
                    'rps_per_core': 'max'
                }).reset_index()

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

                            # Add visual indicator for degraded performance
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

                # Best Configuration Summary
                st.subheader("🎯 Best Configurations")

                best_configs = []
                for model in scaling_analysis['model'].unique():
                    model_data = scaling_analysis[scaling_analysis['model'] == model].copy()

                    # Find best throughput (highest RPS)
                    best_throughput_row = model_data.loc[model_data['request_throughput_rps'].idxmax()]
                    best_throughput_cores = int(best_throughput_row['requested_cores'])
                    best_throughput_rps = best_throughput_row['request_throughput_rps']

                    # Find best efficiency (highest RPS per core)
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

    if has_quality:
        with tab4:
            plot_mteb_quality_metrics(mteb_df)

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
