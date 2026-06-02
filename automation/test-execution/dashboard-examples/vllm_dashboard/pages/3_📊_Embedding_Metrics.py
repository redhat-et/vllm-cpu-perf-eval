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

                    row = {
                        # Metadata
                        'test_run_id': metadata.get('test_run_id', 'unknown'),
                        'scenario': metadata.get('scenario', ''),
                        'model': metadata.get('model', ''),
                        'platform': metadata.get('platform', 'unknown'),
                        'vllm_version': metadata.get('vllm_version', 'unknown'),
                        'vllm_mode': metadata.get('vllm_mode', 'managed'),
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
    """Plot throughput and P99 latency vs load level (saturation analysis)."""
    if df.empty:
        st.warning("No baseline data to display")
        return

    # Order load levels
    load_order = {'inf': 4, '75pct': 3, '50pct': 2, '25pct': 1}
    df = df.copy()
    df['load_order'] = df['parameter'].map(load_order)
    df = df.sort_values('load_order')

    # Create dual-axis figure
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Throughput line
    fig.add_trace(
        go.Scatter(
            x=df['parameter'],
            y=df['request_throughput_rps'],
            name='Throughput (req/s)',
            mode='lines+markers',
            marker=dict(size=10, color='blue'),
            line=dict(width=3, color='blue')
        ),
        secondary_y=False
    )

    # P99 Latency line
    fig.add_trace(
        go.Scatter(
            x=df['parameter'],
            y=df['p99_latency_ms'],
            name='P99 Latency (ms)',
            mode='lines+markers',
            marker=dict(size=10, color='red'),
            line=dict(width=3, dash='dash', color='red')
        ),
        secondary_y=True
    )

    fig.update_xaxes(
        title_text="Load Level",
        categoryorder='array',
        categoryarray=['25pct', '50pct', '75pct', 'inf']
    )
    fig.update_yaxes(title_text="Request Throughput (req/s)", secondary_y=False, title_font_color='blue')
    fig.update_yaxes(title_text="P99 Latency (ms)", secondary_y=True, title_font_color='red')

    fig.update_layout(
        title="Saturation Analysis: Throughput & Latency vs Load",
        hovermode='x unified',
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Metrics table
    st.subheader("Baseline Metrics")
    metrics_display = df[[
        'parameter', 'request_throughput_rps', 'p99_latency_ms',
        'mean_latency_ms', 'median_latency_ms'
    ]].copy()
    metrics_display.columns = ['Load', 'RPS', 'P99 (ms)', 'Mean (ms)', 'Median (ms)']
    metrics_display = metrics_display.round(2)
    st.dataframe(metrics_display, use_container_width=True)


def plot_concurrent_load(df: pd.DataFrame):
    """Plot throughput and latency vs concurrency level."""
    if df.empty:
        st.warning("No concurrent load data to display")
        return

    df = df.copy()
    df['concurrency'] = df['parameter'].astype(int)
    df = df.sort_values('concurrency')

    col1, col2 = st.columns(2)

    with col1:
        # Throughput vs concurrency
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=df['concurrency'],
            y=df['request_throughput_rps'],
            mode='lines+markers',
            marker=dict(size=10),
            line=dict(width=3)
        ))
        fig1.update_layout(
            title="Throughput vs Concurrency",
            xaxis_title="Concurrent Requests",
            yaxis_title="Request Throughput (req/s)",
            height=400
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        # Latencies vs concurrency
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df['concurrency'],
            y=df['mean_latency_ms'],
            name='Mean Latency',
            mode='lines+markers',
            marker=dict(size=8)
        ))
        fig2.add_trace(go.Scatter(
            x=df['concurrency'],
            y=df['p99_latency_ms'],
            name='P99 Latency',
            mode='lines+markers',
            marker=dict(size=8)
        ))
        fig2.update_layout(
            title="Latency vs Concurrency",
            xaxis_title="Concurrent Requests",
            yaxis_title="Latency (ms)",
            height=400
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Metrics table
    st.subheader("Concurrent Load Metrics")
    concurrent_display = df[[
        'concurrency', 'request_throughput_rps',
        'mean_latency_ms', 'median_latency_ms', 'p99_latency_ms'
    ]].copy()
    concurrent_display.columns = ['Concurrency', 'RPS', 'Mean (ms)', 'Median (ms)', 'P99 (ms)']
    concurrent_display = concurrent_display.round(2)
    st.dataframe(concurrent_display, use_container_width=True)


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

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        models = sorted(df['model'].unique())
        selected_models = st.multiselect(
            "Select Models",
            options=models,
            default=[models[0]] if models else []
        )

    with col2:
        platforms = sorted(df['platform'].unique())
        selected_platforms = st.multiselect(
            "Select Platforms",
            options=platforms,
            default=platforms
        )

    with col3:
        test_runs = sorted(df['test_run_id'].unique(), reverse=True)
        selected_test_run = st.selectbox(
            "Test Run",
            options=test_runs,
            help="Select specific test run to analyze"
        )

    if not selected_models:
        st.warning("Please select at least one model")
        return

    # Filter data
    filtered_df = df[
        (df['model'].isin(selected_models)) &
        (df['platform'].isin(selected_platforms)) &
        (df['test_run_id'] == selected_test_run)
    ]

    if filtered_df.empty:
        st.warning("No data matches the selected filters")
        return

    # Model comparison (if multiple models)
    if len(selected_models) > 1:
        st.header("🔍 Model Comparison")
        plot_model_comparison(df, selected_models, 'baseline')
        st.markdown("---")

    # Detailed analysis for each model
    for model in selected_models:
        st.header(f"📈 {model}")

        model_data = filtered_df[filtered_df['model'] == model]

        if model_data.empty:
            st.warning(f"No data for {model} in selected test run")
            continue

        # Tabs for different views
        tab1, tab2 = st.tabs(["📊 Saturation Analysis", "🔀 Concurrent Load"])

        with tab1:
            baseline_data = model_data[model_data['test_type'] == 'baseline']
            plot_saturation_curve(baseline_data)

        with tab2:
            concurrent_data = model_data[model_data['test_type'] == 'concurrent']
            plot_concurrent_load(concurrent_data)

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
