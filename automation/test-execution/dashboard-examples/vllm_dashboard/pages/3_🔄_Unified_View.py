"""vLLM CPU Performance - Unified Dashboard.

Combined client-side (GuideLLM) and server-side (vLLM) metrics in one dashboard.

Run: streamlit run unified_dashboard.py
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

# Page config is set in Home.py for multipage apps

# Dark mode friendly CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# Import rendering functions from existing dashboards
# We'll define simplified versions here to avoid import issues

@st.cache_data(ttl=300)
def load_guidellm_data(results_dir: str) -> pd.DataFrame:
    """Load GuideLLM benchmark results."""
    results_path = Path(results_dir)
    all_results = []

    if not results_path.exists():
        return pd.DataFrame()

    for json_file in results_path.rglob("benchmarks.json"):
        try:
            with open(json_file) as f:
                data = json.load(f)

            metadata_file = json_file.parent / "test-metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file) as f:
                metadata = json.load(f)

            for bench in data.get('benchmarks', []):
                metrics = bench['metrics']
                config = bench['config']

                concurrency = config.get('strategy', {}).get('max_concurrency', 0)
                req_rate = metrics.get('requests_per_second', {}).get('successful', {}).get('mean', concurrency)

                row = {
                    'test_run_id': metadata.get('test_run_id', 'unknown'),
                    'platform': metadata.get('platform', 'unknown'),
                    'model': metadata.get('model', 'unknown'),
                    'model_short': metadata.get('model', 'unknown').split('/')[-1],
                    'workload': metadata.get('workload', 'unknown'),
                    'cores': metadata.get('core_count', 0),
                    'backend': metadata.get('backend', 'unknown'),
                    'vllm_version': metadata.get('vllm_version', 'unknown'),
                    'tensor_parallel': metadata.get('tensor_parallel', 1),
                    'concurrency': concurrency,
                    'request_rate': req_rate,
                    'throughput_mean': metrics['tokens_per_second']['successful']['mean'],
                    'ttft_p95': metrics['time_to_first_token_ms']['successful']['percentiles']['p95'],
                    'itl_p95': metrics['inter_token_latency_ms']['successful']['percentiles']['p95'],
                    'e2e_p95': metrics['request_latency']['successful']['percentiles']['p95'],
                    'success_rate': (metrics['request_totals']['successful'] / metrics['request_totals']['total'] * 100)
                                   if metrics['request_totals']['total'] > 0 else 0,
                }
                row['efficiency'] = row['throughput_mean'] / row['cores']
                all_results.append(row)

        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
            continue

    return pd.DataFrame(all_results) if all_results else pd.DataFrame()


@st.cache_data(ttl=300)
def load_vllm_metrics(results_dir: str) -> pd.DataFrame:
    """Load vLLM server metrics."""
    results_path = Path(results_dir)
    metrics_data = []

    if not results_path.exists():
        return pd.DataFrame()

    for metrics_file in results_path.rglob("vllm-metrics.json"):
        try:
            with open(metrics_file) as f:
                data = json.load(f)

            metadata_file = metrics_file.parent / "test-metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file) as f:
                metadata = json.load(f)

            for sample in data.get('samples', []):
                row = {
                    'test_run_id': metadata.get('test_run_id', 'unknown'),
                    'platform': metadata.get('platform', 'unknown'),
                    'model': metadata.get('model', 'unknown'),
                    'model_short': metadata.get('model', 'unknown').split('/')[-1],
                    'workload': metadata.get('workload', 'unknown'),
                    'cores': metadata.get('core_count', 0),
                    'backend': metadata.get('backend', 'unknown'),
                    'vllm_version': metadata.get('vllm_version', 'unknown'),
                    'tensor_parallel': metadata.get('tensor_parallel', 1),
                    'timestamp': sample['timestamp'],
                    'elapsed_seconds': sample['elapsed_seconds'],
                }

                # Extract key metrics
                metrics = sample.get('metrics', {})

                def sum_metric(name):
                    if name in metrics:
                        return sum(m['value'] for m in metrics[name])
                    return 0

                def mean_metric(name):
                    if name in metrics:
                        values = [m['value'] for m in metrics[name]]
                        return sum(values) / len(values) if values else 0
                    return 0

                row['requests_running'] = sum_metric('vllm:num_requests_running')
                row['requests_waiting'] = sum_metric('vllm:num_requests_waiting')
                row['cache_usage'] = mean_metric('vllm:kv_cache_usage_perc')
                row['prompt_tokens'] = sum_metric('vllm:prompt_tokens_total')
                row['gen_tokens'] = sum_metric('vllm:generation_tokens_total')

                metrics_data.append(row)

        except Exception as e:
            logger.warning(f"Failed to load {metrics_file}: {e}")
            continue

    return pd.DataFrame(metrics_data) if metrics_data else pd.DataFrame()


# Main app
st.title("🚀 vLLM CPU Performance Dashboard")
st.markdown("**Unified Client-Side & Server-Side Metrics Analysis**")

# Sidebar configuration
st.sidebar.header("Configuration")

# Initialize config manager
config = DashboardConfig()
default_results_dir = config.get_results_directory()

results_dir = st.sidebar.text_input(
    "Results Directory",
    value=default_results_dir,
    help="Path to results directory (saved across sessions)"
)

# Save if changed
if results_dir != default_results_dir:
    config.set_results_directory(results_dir)

# Load both datasets
with st.spinner("Loading benchmark data..."):
    client_df = load_guidellm_data(results_dir)
    server_df = load_vllm_metrics(results_dir)

if client_df.empty and server_df.empty:
    st.error("No benchmark data found!")
    st.info(f"Looking in: {Path(results_dir).absolute()}")
    st.stop()

# Unified filters (use client_df for filter options, apply to both)
st.markdown("### 🔍 Filter Data")

if not client_df.empty:
    col1, col2, col3 = st.columns(3)

    with col1:
        platforms = sorted(client_df['platform'].unique())
        selected_platforms = st.multiselect(
            "Platform",
            platforms,
            default=platforms,
            key="platform_filter"
        )

    with col2:
        models = sorted(client_df['model_short'].unique())
        selected_models = st.multiselect(
            "Model",
            models,
            default=models,
            key="model_filter"
        )

    with col3:
        workloads = sorted(client_df['workload'].unique())
        selected_workloads = st.multiselect(
            "Workload",
            workloads,
            default=workloads,
            key="workload_filter"
        )

    col4, col5 = st.columns(2)

    with col4:
        cores = sorted(client_df['cores'].unique())
        selected_cores = st.multiselect(
            "Core Count",
            cores,
            default=cores,
            key="cores_filter"
        )

    with col5:
        versions = sorted(client_df['vllm_version'].unique())
        selected_versions = st.multiselect(
            "vLLM Version",
            versions,
            default=versions,
            key="version_filter"
        )

    # Apply filters
    filtered_client = client_df[
        client_df['platform'].isin(selected_platforms) &
        client_df['model_short'].isin(selected_models) &
        client_df['workload'].isin(selected_workloads) &
        client_df['cores'].isin(selected_cores) &
        client_df['vllm_version'].isin(selected_versions)
    ]

    filtered_server = server_df[
        server_df['platform'].isin(selected_platforms) &
        server_df['model_short'].isin(selected_models) &
        server_df['workload'].isin(selected_workloads) &
        server_df['cores'].isin(selected_cores) &
        server_df['vllm_version'].isin(selected_versions)
    ] if not server_df.empty else pd.DataFrame()

else:
    filtered_client = pd.DataFrame()
    filtered_server = server_df

if filtered_client.empty and filtered_server.empty:
    st.warning("⚠️ No data matches the selected filters.")
    st.stop()

st.markdown("---")

# Create tabs for Client vs Server views
tab1, tab2, tab3 = st.tabs(["📊 Client-Side Metrics (GuideLLM)", "🖥️ Server-Side Metrics (vLLM)", "🔄 Correlation View"])

# ============================================================================
# TAB 1: Client-Side Metrics (GuideLLM)
# ============================================================================
with tab1:
    if filtered_client.empty:
        st.warning("No client-side data available.")
    else:
        st.markdown("### Performance Analysis")

        # Metric selectors
        col1, col2, col3 = st.columns([1, 1, 2])

        with col1:
            x_axis_options = {
                "Request Rate (req/s)": "request_rate",
                "Concurrency": "concurrency"
            }
            selected_x = st.selectbox("X-axis", list(x_axis_options.keys()), key="client_x")
            x_col = x_axis_options[selected_x]

        with col2:
            metric_options = {
                "Throughput (tokens/sec)": "throughput_mean",
                "TTFT P95 (ms)": "ttft_p95",
                "ITL P95 (ms)": "itl_p95",
                "E2E Latency P95 (s)": "e2e_p95",
                "Efficiency (tok/s/core)": "efficiency",
                "Success Rate (%)": "success_rate"
            }
            selected_metric = st.selectbox("Y-axis", list(metric_options.keys()), key="client_y")
            metric_col = metric_options[selected_metric]

        # Plot
        fig = go.Figure()
        colors = px.colors.qualitative.Set2
        color_idx = 0

        grouped = filtered_client.groupby([
            'platform', 'model_short', 'workload', 'vllm_version',
            'cores', 'tensor_parallel', 'test_run_id'
        ])

        for (platform, model, workload, vllm_version, cores, tp, test_id), group_df in grouped:
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
                marker=dict(size=10)
            ))
            color_idx += 1

        fig.update_layout(
            title=f"{selected_metric} vs {selected_x}",
            xaxis_title=selected_x,
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

        # Peak performance summary
        st.markdown("### Peak Performance")
        cols = st.columns(4)
        cols[0].metric("Peak Throughput", f"{filtered_client['throughput_mean'].max():.2f} tok/s")
        cols[1].metric("Best TTFT P95", f"{filtered_client['ttft_p95'].min():.2f} ms")
        cols[2].metric("Best Efficiency", f"{filtered_client['efficiency'].max():.2f} tok/s/core")
        cols[3].metric("Avg Success Rate", f"{filtered_client['success_rate'].mean():.1f}%")

# ============================================================================
# TAB 2: Server-Side Metrics (vLLM)
# ============================================================================
with tab2:
    if filtered_server.empty:
        st.warning("No server-side data available. Ensure vLLM metrics were collected during tests.")
        st.info("Server metrics require Prometheus to be running during the test. See documentation for setup.")
    else:
        st.markdown("### Server Metrics Overview")
        st.info("💡 **Tip:** For detailed server-side metrics including latency histograms (TTFT, ITL, E2E), use the **🖥️ Server Metrics** dashboard.")

        # Create time-series plot
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Queue Depth', 'KV Cache Usage', 'Token Counts', 'Requests Over Time'),
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )

        # Group by test configuration
        grouped = filtered_server.groupby([
            'platform', 'model_short', 'workload', 'vllm_version',
            'cores', 'tensor_parallel', 'test_run_id'
        ])
        colors = px.colors.qualitative.Set2
        color_idx = 0

        for (platform, model, workload, vllm_version, cores, tp, test_id), group_df in grouped:
            group_df = group_df.sort_values('elapsed_seconds')

            # Get full model name
            full_model = group_df['model'].iloc[0]

            # Format label: platform | model | release | core_count | TP | workload
            label = f"{platform} | {full_model} | {vllm_version} | {cores}c | TP={tp} | {workload}"
            color = colors[color_idx % len(colors)]

            # Queue depth (stacked)
            fig.add_trace(go.Scatter(
                x=group_df['elapsed_seconds'],
                y=group_df['requests_running'],
                name=f"{label} - Running",
                mode='lines',
                line=dict(color=color, width=2),
                stackgroup='queue',
                legendgroup=label
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=group_df['elapsed_seconds'],
                y=group_df['requests_waiting'],
                name=f"{label} - Waiting",
                mode='lines',
                line=dict(color=color, width=2, dash='dash'),
                stackgroup='queue',
                legendgroup=label
            ), row=1, col=1)

            # Cache usage
            fig.add_trace(go.Scatter(
                x=group_df['elapsed_seconds'],
                y=group_df['cache_usage'],
                name=label,
                mode='lines',
                line=dict(color=color, width=2),
                showlegend=False,
                legendgroup=label
            ), row=1, col=2)

            # Token counts
            fig.add_trace(go.Scatter(
                x=group_df['elapsed_seconds'],
                y=group_df['gen_tokens'],
                name=label,
                mode='lines',
                line=dict(color=color, width=2),
                showlegend=False,
                legendgroup=label
            ), row=2, col=1)

            # Total queue
            fig.add_trace(go.Scatter(
                x=group_df['elapsed_seconds'],
                y=group_df['requests_running'] + group_df['requests_waiting'],
                name=label,
                mode='lines',
                line=dict(color=color, width=2),
                showlegend=False,
                legendgroup=label
            ), row=2, col=2)

            color_idx += 1

        fig.update_xaxes(title_text="Time (seconds)", row=2, col=1)
        fig.update_xaxes(title_text="Time (seconds)", row=2, col=2)
        fig.update_yaxes(title_text="Requests", row=1, col=1)
        fig.update_yaxes(title_text="Percentage", row=1, col=2)
        fig.update_yaxes(title_text="Tokens", row=2, col=1)
        fig.update_yaxes(title_text="Total Queue", row=2, col=2)

        fig.update_layout(height=700, hovermode='x unified')

        st.plotly_chart(fig, use_container_width=True)

        # Summary stats
        st.markdown("### Summary Statistics")
        cols = st.columns(4)
        cols[0].metric("Avg Queue Depth", f"{(filtered_server['requests_running'] + filtered_server['requests_waiting']).mean():.2f}")
        cols[1].metric("Max Queue Depth", f"{(filtered_server['requests_running'] + filtered_server['requests_waiting']).max():.0f}")
        cols[2].metric("Avg Cache Usage", f"{filtered_server['cache_usage'].mean():.1f}%")
        cols[3].metric("Total Gen Tokens", f"{filtered_server['gen_tokens'].max():,.0f}")

# ============================================================================
# TAB 3: Correlation View
# ============================================================================
with tab3:
    st.markdown("### Client-Server Correlation Analysis")

    if filtered_client.empty or filtered_server.empty:
        st.warning("Both client and server data needed for correlation analysis.")
        st.info("Client data: " + ("Available" if not filtered_client.empty else "Missing"))
        st.info("Server data: " + ("Available" if not filtered_server.empty else "Missing"))
    else:
        st.markdown("""
        **Correlation View** helps identify how server-side behavior affects client-side performance.

        **Examples:**
        - Client latency spike + Server queue buildup = Insufficient capacity
        - Good client throughput + High cache usage = Optimal utilization
        - Client timeouts + Empty server queue = Network/routing issue
        """)

        # Show side-by-side comparison
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Client-Side Peak Performance")
            st.metric("Peak Throughput", f"{filtered_client['throughput_mean'].max():.2f} tok/s")
            st.metric("Best TTFT P95", f"{filtered_client['ttft_p95'].min():.2f} ms")

        with col2:
            st.markdown("#### Server-Side Behavior")
            st.metric("Avg Queue Depth", f"{(filtered_server['requests_running'] + filtered_server['requests_waiting']).mean():.2f}")
            st.metric("Peak Cache Usage", f"{filtered_server['cache_usage'].max():.1f}%")

        st.markdown("---")
        st.info("💡 Tip: Use the Client and Server tabs above to drill down into specific metrics and identify bottlenecks.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**vLLM CPU Performance Dashboard**")
st.sidebar.caption(f"Client: {len(filtered_client)} points | Server: {len(filtered_server)} points")
