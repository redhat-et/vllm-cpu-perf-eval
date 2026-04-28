"""
Streamlit Dashboard for vLLM Server-Side Metrics Analysis

Visualizes server-side metrics collected during benchmark execution:
- CPU cache utilization over time
- Request queue depth (running/waiting)
- Token generation rates
- Request processing metrics
- Cache hit rates

Complements the GuideLLM client-side analysis dashboard.

Run: streamlit run streamlit_vllm_server_metrics.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add parent directory to path for config_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig

# Page config is set in Home.py for multipage apps

# Dark mode friendly CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🖥️ vLLM Server-Side Metrics Analysis")

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
    key="results_dir_server"
)

# Save button
col1, col2 = st.sidebar.columns([3, 1])
with col2:
    save_btn = st.button(
        "💾",
        help="Save configuration",
        key="save_btn_server"
    )
    if save_btn:
        if results_dir != default_results_dir:
            config.set_results_directory(results_dir)
            st.sidebar.success("✓ Saved!")
        else:
            st.sidebar.info("No changes")

# Load vLLM metrics
@st.cache_data
def load_vllm_metrics(base_dir: str):
    """Load all vLLM server metrics files with metadata"""
    results_path = Path(base_dir)
    metrics_data = []

    if not results_path.exists():
        st.error(f"Directory not found: {results_path.absolute()}")
        return metrics_data

    with st.spinner(f"Scanning {results_path}..."):
        for metrics_file in results_path.rglob("vllm-metrics.json"):
            try:
                # Load vLLM metrics
                with open(metrics_file) as f:
                    data = json.load(f)

                # Load test metadata
                metadata_file = metrics_file.parent / "test-metadata.json"
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        metadata = json.load(f)

                        # Load metadata for both managed and external endpoints
                        data['platform'] = metadata.get('platform', 'unknown')
                        data['model'] = metadata.get('model', 'unknown')
                        data['workload'] = metadata.get('workload', 'unknown')
                        data['test_run_id'] = metadata.get('test_run_id', 'unknown')
                        data['test_name'] = metadata.get('test_name', '')
                        data['cores'] = metadata.get('core_count', 'N/A')
                        data['backend'] = metadata.get('backend', 'unknown')
                        data['vllm_version'] = metadata.get('vllm_version', 'unknown')
                        data['guidellm_version'] = metadata.get('guidellm_version', 'unknown')
                        data['core_config'] = metadata.get('core_config_name', 'unknown')
                        data['vllm_mode'] = metadata.get('vllm_mode', 'managed')
                        data['vllm_endpoint_url'] = metadata.get('vllm_endpoint_url', 'n/a')

                # Add file path
                data['_file_path'] = str(metrics_file.parent)
                data['_file_name'] = metrics_file.name

                metrics_data.append(data)
            except Exception as e:
                st.sidebar.warning(f"Failed to load {metrics_file.name}: {e}")

    return metrics_data

results = load_vllm_metrics(results_dir)

if not results:
    st.error("No vLLM metrics found!")
    st.info(f"Looking in: {Path(results_dir).absolute()}")
    st.info("Make sure vLLM metrics collection is enabled in your benchmark runs.")
    st.stop()

st.sidebar.success(f"Loaded {len(results)} metric files")

# Check if we have both managed and external tests
has_managed = any(r.get('vllm_mode') == 'managed' for r in results)
has_external = any(r.get('vllm_mode') == 'external' for r in results)

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

    # Filter results by mode
    mode_filtered_results = [r for r in results if r.get('vllm_mode') == test_mode]

    if not mode_filtered_results:
        st.warning(f"⚠️ No {test_mode} test results found.")
        st.stop()

    results = mode_filtered_results
elif has_external:
    # Only external tests exist
    st.info("ℹ️ Showing external endpoint test results only")
    test_mode = 'external'
    results = [r for r in results if r.get('vllm_mode') == 'external']
else:
    # Only managed tests exist (default)
    test_mode = 'managed'
    results = [r for r in results if r.get('vllm_mode') == 'managed']

# Extract filter options based on test mode
if test_mode == 'managed':
    platforms = sorted(set(r.get('platform', 'unknown') for r in results))
    cores = sorted(set(r.get('cores', 'N/A') for r in results), key=lambda x: (isinstance(x, str), x))
else:  # external mode
    endpoints = sorted(set(r.get('vllm_endpoint_url', 'n/a') for r in results if r.get('vllm_endpoint_url') != 'n/a'))

models = sorted(set(r.get('model', 'unknown') for r in results))
workloads = sorted(set(r.get('workload', 'unknown') for r in results))
test_runs = sorted(set(r.get('test_run_id', 'unknown') for r in results))
versions = sorted(set(r.get('vllm_version', 'unknown') for r in results))
guidellm_versions = sorted(set(r.get('guidellm_version', 'unknown') for r in results))

# Section navigation
section_list = [
    "📈 Performance Plots",
    "⚖️ Compare Configurations",
]

current_section = st.session_state.get("active_section_server", section_list[0])
if current_section not in section_list:
    current_section = section_list[0]
st.session_state.active_section_server = current_section

# Sidebar navigation
st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")
for section_name in section_list:
    is_active = section_name == current_section
    btn_type = "primary" if is_active else "secondary"
    if st.sidebar.button(
        section_name,
        key=f"nav_{section_name}",
        use_container_width=True,
        type=btn_type,
    ):
        st.session_state.active_section_server = section_name
        st.rerun()

if current_section == "📈 Performance Plots":
    # Single test mode - filters in main area
    st.markdown("### 🔍 Filter Test Data")

    if test_mode == 'managed':
        # Managed mode filters
        col1, col2, col3 = st.columns(3)

        with col1:
            selected_platforms = st.multiselect(
                "Platform",
                platforms,
                default=platforms,
                key="platform_filter_server"
            )

        with col2:
            selected_models = st.multiselect(
                "Model",
                models,
                default=models,
                key="model_filter_server"
            )

        with col3:
            selected_workloads = st.multiselect(
                "Workload",
                workloads,
                default=workloads,
                key="workload_filter_server"
            )

        col4, col5, col6 = st.columns(3)

        with col4:
            selected_cores_list = st.multiselect(
                "Core Count",
                cores,
                default=cores,
                key="cores_filter_server"
            )

        with col5:
            selected_versions = st.multiselect(
                "vLLM Version",
                versions,
                default=versions,
                key="version_filter_server"
            )

        with col6:
            selected_guidellm_versions = st.multiselect(
                "GuideLLM Version",
                guidellm_versions,
                default=guidellm_versions,
                key="guidellm_version_filter_server"
            )

        # Test name filter (separate row if any tests have custom names)
        test_names = sorted(set(r.get('test_name', '') for r in results if r.get('test_name', '').strip()))
        if test_names:
            st.markdown("**Test Name Filter:**")
            selected_test_names = st.multiselect(
                "Custom Test Names",
                test_names,
                default=test_names,
                key="test_name_filter_server_managed",
                help="Filter by custom test names (if provided during test run)"
            )
        else:
            selected_test_names = []

        # Filter results (before test run selection)
        filtered_pre = [
            r for r in results
            if r.get('platform') in selected_platforms
            and r.get('model') in selected_models
            and r.get('workload') in selected_workloads
            and r.get('cores') in selected_cores_list
            and r.get('vllm_version') in selected_versions
            and r.get('guidellm_version') in selected_guidellm_versions
        ]

        # Apply test name filter if user has deselected some names
        if test_names and selected_test_names != test_names:
            filtered_pre = [r for r in filtered_pre if r.get('test_name', '') in selected_test_names]

    else:  # external mode
        # External mode filters
        col1, col2, col3 = st.columns(3)

        with col1:
            selected_endpoints = st.multiselect(
                "Endpoint URL",
                endpoints,
                default=endpoints,
                key="endpoint_filter_server"
            )

        with col2:
            selected_models = st.multiselect(
                "Model",
                models,
                default=models,
                key="model_filter_server_ext"
            )

        with col3:
            selected_workloads = st.multiselect(
                "Workload",
                workloads,
                default=workloads,
                key="workload_filter_server_ext"
            )

        col4, col5, col6 = st.columns(3)

        with col4:
            selected_versions = st.multiselect(
                "vLLM Version",
                versions,
                default=versions,
                key="version_filter_server_ext"
            )

        with col5:
            selected_guidellm_versions = st.multiselect(
                "GuideLLM Version",
                guidellm_versions,
                default=guidellm_versions,
                key="guidellm_version_filter_server_ext"
            )

        with col6:
            # Model source (auto-detected vs specified)
            sources = sorted(set(r.get('model_source', 'specified') for r in results))
            selected_sources = st.multiselect(
                "Model Source",
                sources,
                default=sources,
                key="source_filter_server_ext",
                help="'auto-detected' = model discovered from endpoint, 'specified' = model explicitly provided"
            )

        # Test name filter (separate row if any tests have custom names)
        test_names = sorted(set(r.get('test_name', '') for r in results if r.get('test_name', '').strip()))
        if test_names:
            st.markdown("**Test Name Filter:**")
            selected_test_names = st.multiselect(
                "Custom Test Names",
                test_names,
                default=test_names,
                key="test_name_filter_server_external",
                help="Filter by custom test names (if provided during test run)"
            )
        else:
            selected_test_names = []

        # Filter results (before test run selection)
        filtered_pre = [
            r for r in results
            if r.get('vllm_endpoint_url') in selected_endpoints
            and r.get('model') in selected_models
            and r.get('workload') in selected_workloads
            and r.get('vllm_version') in selected_versions
            and r.get('guidellm_version') in selected_guidellm_versions
            and r.get('model_source', 'specified') in selected_sources
        ]

        # Apply test name filter if user has deselected some names
        if test_names and selected_test_names != test_names:
            filtered_pre = [r for r in filtered_pre if r.get('test_name', '') in selected_test_names]

    if not filtered_pre:
        st.warning("No results match the selected filters")
        st.stop()

    # Show test run selector if multiple runs match
    available_test_runs = sorted(set(r.get('test_run_id', 'unknown') for r in filtered_pre))
    if len(available_test_runs) > 1:
        col7, _, _ = st.columns(3)
        with col7:
            selected_test_run = st.selectbox(
                "Test Run",
                available_test_runs,
                help=f"{len(available_test_runs)} test runs match"
            )
        filtered = [r for r in filtered_pre if r.get('test_run_id') == selected_test_run]
    else:
        filtered = filtered_pre

    st.markdown("---")

    test_data = filtered[0]

    # Show metadata
    st.subheader("Test Configuration")
    if test_mode == 'managed':
        cols = st.columns(7)
        cols[0].metric("Platform", test_data.get('platform', 'N/A'))
        cols[1].metric("Model", test_data.get('model', 'unknown').split('/')[-1])
        cols[2].metric("Workload", test_data.get('workload', 'N/A'))
        cols[3].metric("Cores", test_data.get('cores', 'N/A'))
        cols[4].metric("Backend", test_data.get('backend', 'N/A'))
        cols[5].metric("GuideLLM", test_data.get('guidellm_version', 'N/A'))
        cols[6].metric("Test Run ID", test_data.get('test_run_id', 'N/A')[:8])
    else:  # external mode
        cols = st.columns(6)
        endpoint_url = test_data.get('vllm_endpoint_url', 'N/A')
        # Shorten endpoint for display (preserve host:port)
        endpoint_short = endpoint_url.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
        cols[0].metric("Endpoint", endpoint_short)
        cols[1].metric("Model", test_data.get('model', 'unknown').split('/')[-1])
        cols[2].metric("Workload", test_data.get('workload', 'N/A'))
        cols[3].metric("Backend", test_data.get('backend', 'N/A'))
        cols[4].metric("GuideLLM", test_data.get('guidellm_version', 'N/A'))
        cols[5].metric("Test Run ID", test_data.get('test_run_id', 'N/A')[:8])

    # Collection info
    collection_info = test_data.get('collection_info', {})
    st.caption(f"Collected {collection_info.get('total_samples', 'N/A')} samples over {collection_info.get('duration_seconds', 'N/A')}s")

    # Helper functions to extract metrics
    def get_metric_values(sample: Dict, metric_name: str) -> List[float]:
        """Extract all values for a metric from a sample"""
        metrics = sample.get('metrics', {})
        if metric_name in metrics:
            return [m['value'] for m in metrics[metric_name]]
        return []

    def sum_metric(sample: Dict, metric_name: str) -> float:
        """Sum all values of a metric in a sample"""
        values = get_metric_values(sample, metric_name)
        return sum(values) if values else 0

    def mean_metric(sample: Dict, metric_name: str) -> float:
        """Average all values of a metric in a sample"""
        values = get_metric_values(sample, metric_name)
        return sum(values) / len(values) if values else 0

    # Extract time series data
    samples = test_data.get('samples', [])

    if not samples:
        st.error("No samples found in metrics file")
        st.stop()

    # Build time series
    timestamps = [s['elapsed_seconds'] for s in samples]

    # Queue metrics
    requests_running = [sum_metric(s, 'vllm:num_requests_running') for s in samples]
    requests_waiting = [sum_metric(s, 'vllm:num_requests_waiting') for s in samples]

    # Cache metrics (KV cache usage)
    cpu_cache_usage = [mean_metric(s, 'vllm:kv_cache_usage_perc') for s in samples]

    # Token metrics
    prompt_tokens = [sum_metric(s, 'vllm:prompt_tokens_total') for s in samples]
    generation_tokens = [sum_metric(s, 'vllm:generation_tokens_total') for s in samples]

    # Latency metrics (calculate averages from sum/count if available)
    ttft_latency = []
    itl_latency = []
    e2e_latency = []

    for i, s in enumerate(samples):
        # TTFT (Time to First Token)
        ttft_sum = sum_metric(s, 'vllm:time_to_first_token_seconds_sum')
        ttft_count = sum_metric(s, 'vllm:time_to_first_token_seconds_count')
        if i > 0 and ttft_count > 0:
            prev_sum = sum_metric(samples[i-1], 'vllm:time_to_first_token_seconds_sum')
            prev_count = sum_metric(samples[i-1], 'vllm:time_to_first_token_seconds_count')
            delta_sum = ttft_sum - prev_sum
            delta_count = ttft_count - prev_count
            ttft_latency.append((delta_sum / delta_count * 1000) if delta_count > 0 else 0)  # Convert to ms
        else:
            ttft_latency.append(0)

        # ITL (Inter Token Latency)
        itl_sum = sum_metric(s, 'vllm:request_time_per_output_token_seconds_sum')
        itl_count = sum_metric(s, 'vllm:request_time_per_output_token_seconds_count')
        if i > 0 and itl_count > 0:
            prev_sum = sum_metric(samples[i-1], 'vllm:time_per_output_token_seconds_sum')
            prev_count = sum_metric(samples[i-1], 'vllm:time_per_output_token_seconds_count')
            delta_sum = itl_sum - prev_sum
            delta_count = itl_count - prev_count
            itl_latency.append((delta_sum / delta_count * 1000) if delta_count > 0 else 0)  # Convert to ms
        else:
            itl_latency.append(0)

        # E2E (End-to-End Latency)
        e2e_sum = sum_metric(s, 'vllm:e2e_request_latency_seconds_sum')
        e2e_count = sum_metric(s, 'vllm:e2e_request_latency_seconds_count')
        if i > 0 and e2e_count > 0:
            prev_sum = sum_metric(samples[i-1], 'vllm:e2e_request_latency_seconds_sum')
            prev_count = sum_metric(samples[i-1], 'vllm:e2e_request_latency_seconds_count')
            delta_sum = e2e_sum - prev_sum
            delta_count = e2e_count - prev_count
            e2e_latency.append((delta_sum / delta_count * 1000) if delta_count > 0 else 0)  # Convert to ms
        else:
            e2e_latency.append(0)

    # Request characteristics (calculate average from sum/count)
    prompt_length = []
    generation_length = []

    for i, s in enumerate(samples):
        # Prompt length
        prompt_sum = sum_metric(s, 'vllm:request_prompt_tokens_sum')
        prompt_count = sum_metric(s, 'vllm:request_prompt_tokens_count')
        if i > 0 and prompt_count > 0:
            prev_sum = sum_metric(samples[i-1], 'vllm:request_prompt_tokens_sum')
            prev_count = sum_metric(samples[i-1], 'vllm:request_prompt_tokens_count')
            delta_sum = prompt_sum - prev_sum
            delta_count = prompt_count - prev_count
            prompt_length.append((delta_sum / delta_count) if delta_count > 0 else 0)
        else:
            prompt_length.append(0)

        # Generation length
        gen_sum = sum_metric(s, 'vllm:request_generation_tokens_sum')
        gen_count = sum_metric(s, 'vllm:request_generation_tokens_count')
        if i > 0 and gen_count > 0:
            prev_sum = sum_metric(samples[i-1], 'vllm:request_generation_tokens_sum')
            prev_count = sum_metric(samples[i-1], 'vllm:request_generation_tokens_count')
            delta_sum = gen_sum - prev_sum
            delta_count = gen_count - prev_count
            generation_length.append((delta_sum / delta_count) if delta_count > 0 else 0)
        else:
            generation_length.append(0)

    # Calculate token rates (tokens/sec)
    prompt_token_rate = []
    generation_token_rate = []
    for i in range(len(prompt_tokens)):
        if i == 0:
            prompt_token_rate.append(0)
            generation_token_rate.append(0)
        else:
            time_delta = timestamps[i] - timestamps[i-1]
            if time_delta > 0:
                prompt_token_rate.append((prompt_tokens[i] - prompt_tokens[i-1]) / time_delta)
                generation_token_rate.append((generation_tokens[i] - generation_tokens[i-1]) / time_delta)
            else:
                prompt_token_rate.append(0)
                generation_token_rate.append(0)

    # Check if we have latency data
    has_latency_data = any(ttft_latency) or any(itl_latency) or any(e2e_latency)

    # Create tabs
    if has_latency_data:
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Core Metrics", "⏱️ Latency Metrics", "📊 Summary Stats", "🔍 Raw Data"])
    else:
        tab1, tab3, tab4 = st.tabs(["📈 Core Metrics", "📊 Summary Stats", "🔍 Raw Data"])

    with tab1:
        st.subheader("Core Server Metrics Over Time")

        # Create 3x2 subplot
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                'Request Queue Depth',
                'KV Cache Usage',
                'Token Generation Rate',
                'Cumulative Tokens Processed',
                'Avg Request Prompt Length',
                'Avg Request Generation Length'
            ),
            vertical_spacing=0.10,
            horizontal_spacing=0.1
        )

        # Queue depth
        fig.add_trace(go.Scatter(
            x=timestamps, y=requests_running,
            name='Running',
            mode='lines',
            line=dict(color='#2ecc71', width=2),
            stackgroup='queue'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=timestamps, y=requests_waiting,
            name='Waiting',
            mode='lines',
            line=dict(color='#e74c3c', width=2),
            stackgroup='queue'
        ), row=1, col=1)

        # Cache usage
        fig.add_trace(go.Scatter(
            x=timestamps, y=cpu_cache_usage,
            name='KV Cache %',
            mode='lines',
            line=dict(color='#3498db', width=2),
            showlegend=False
        ), row=1, col=2)

        # Token generation rate
        fig.add_trace(go.Scatter(
            x=timestamps, y=generation_token_rate,
            name='Generation',
            mode='lines',
            line=dict(color='#9b59b6', width=2)
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=timestamps, y=prompt_token_rate,
            name='Prompt',
            mode='lines',
            line=dict(color='#f39c12', width=2)
        ), row=2, col=1)

        # Cumulative tokens
        fig.add_trace(go.Scatter(
            x=timestamps, y=generation_tokens,
            name='Generated',
            mode='lines',
            line=dict(color='#9b59b6', width=2),
            showlegend=False
        ), row=2, col=2)

        fig.add_trace(go.Scatter(
            x=timestamps, y=prompt_tokens,
            name='Prompt',
            mode='lines',
            line=dict(color='#f39c12', width=2),
            showlegend=False
        ), row=2, col=2)

        # Request prompt length
        fig.add_trace(go.Scatter(
            x=timestamps, y=prompt_length,
            name='Prompt Length',
            mode='lines',
            line=dict(color='#1abc9c', width=2),
            showlegend=False
        ), row=3, col=1)

        # Request generation length
        fig.add_trace(go.Scatter(
            x=timestamps, y=generation_length,
            name='Generation Length',
            mode='lines',
            line=dict(color='#e67e22', width=2),
            showlegend=False
        ), row=3, col=2)

        # Update axes
        fig.update_xaxes(title_text="Time (seconds)", row=3, col=1)
        fig.update_xaxes(title_text="Time (seconds)", row=3, col=2)
        fig.update_yaxes(title_text="Requests", row=1, col=1)
        fig.update_yaxes(title_text="Percentage", row=1, col=2)
        fig.update_yaxes(title_text="Tokens/sec", row=2, col=1)
        fig.update_yaxes(title_text="Total Tokens", row=2, col=2)
        fig.update_yaxes(title_text="Tokens", row=3, col=1)
        fig.update_yaxes(title_text="Tokens", row=3, col=2)

        fig.update_layout(height=1000, hovermode='x unified')

        st.plotly_chart(fig, use_container_width=True)

    # Latency Metrics Tab
    if has_latency_data:
        with tab2:
            st.subheader("Latency Metrics Over Time")

            # Create latency subplot
            fig_latency = make_subplots(
                rows=2, cols=2,
                subplot_titles=(
                    'Time to First Token (TTFT)',
                    'Inter-Token Latency (ITL)',
                    'End-to-End Request Latency',
                    'Latency Comparison'
                ),
                vertical_spacing=0.12,
                horizontal_spacing=0.1
            )

            # TTFT
            fig_latency.add_trace(go.Scatter(
                x=timestamps, y=ttft_latency,
                name='TTFT',
                mode='lines',
                line=dict(color='#3498db', width=2),
                showlegend=False
            ), row=1, col=1)

            # ITL
            fig_latency.add_trace(go.Scatter(
                x=timestamps, y=itl_latency,
                name='ITL',
                mode='lines',
                line=dict(color='#9b59b6', width=2),
                showlegend=False
            ), row=1, col=2)

            # E2E
            fig_latency.add_trace(go.Scatter(
                x=timestamps, y=e2e_latency,
                name='E2E',
                mode='lines',
                line=dict(color='#e74c3c', width=2),
                showlegend=False
            ), row=2, col=1)

            # All latencies together for comparison
            if any(ttft_latency):
                fig_latency.add_trace(go.Scatter(
                    x=timestamps, y=ttft_latency,
                    name='TTFT',
                    mode='lines',
                    line=dict(color='#3498db', width=2)
                ), row=2, col=2)

            if any(itl_latency):
                fig_latency.add_trace(go.Scatter(
                    x=timestamps, y=itl_latency,
                    name='ITL',
                    mode='lines',
                    line=dict(color='#9b59b6', width=2)
                ), row=2, col=2)

            if any(e2e_latency):
                fig_latency.add_trace(go.Scatter(
                    x=timestamps, y=e2e_latency,
                    name='E2E',
                    mode='lines',
                    line=dict(color='#e74c3c', width=2)
                ), row=2, col=2)

            # Update axes
            fig_latency.update_xaxes(title_text="Time (seconds)", row=2, col=1)
            fig_latency.update_xaxes(title_text="Time (seconds)", row=2, col=2)
            fig_latency.update_yaxes(title_text="Latency (ms)", row=1, col=1)
            fig_latency.update_yaxes(title_text="Latency (ms)", row=1, col=2)
            fig_latency.update_yaxes(title_text="Latency (ms)", row=2, col=1)
            fig_latency.update_yaxes(title_text="Latency (ms)", row=2, col=2)

            fig_latency.update_layout(height=700, hovermode='x unified')

            st.plotly_chart(fig_latency, use_container_width=True)

            # Latency statistics
            st.markdown("### Latency Statistics")
            cols = st.columns(3)

            if any(ttft_latency):
                valid_ttft = [v for v in ttft_latency if v > 0]
                if valid_ttft:
                    cols[0].metric("TTFT Avg", f"{sum(valid_ttft)/len(valid_ttft):.2f} ms")
                    cols[0].caption(f"Min: {min(valid_ttft):.2f} ms | Max: {max(valid_ttft):.2f} ms")

            if any(itl_latency):
                valid_itl = [v for v in itl_latency if v > 0]
                if valid_itl:
                    cols[1].metric("ITL Avg", f"{sum(valid_itl)/len(valid_itl):.2f} ms")
                    cols[1].caption(f"Min: {min(valid_itl):.2f} ms | Max: {max(valid_itl):.2f} ms")

            if any(e2e_latency):
                valid_e2e = [v for v in e2e_latency if v > 0]
                if valid_e2e:
                    cols[2].metric("E2E Avg", f"{sum(valid_e2e)/len(valid_e2e):.2f} ms")
                    cols[2].caption(f"Min: {min(valid_e2e):.2f} ms | Max: {max(valid_e2e):.2f} ms")

    with tab3:
        st.subheader("Summary Statistics")

        # Queue stats
        st.markdown("### Queue Depth")
        cols = st.columns(4)
        cols[0].metric("Avg Running", f"{sum(requests_running)/len(requests_running):.2f}")
        cols[1].metric("Max Running", f"{max(requests_running):.0f}")
        cols[2].metric("Avg Waiting", f"{sum(requests_waiting)/len(requests_waiting):.2f}")
        cols[3].metric("Max Waiting", f"{max(requests_waiting):.0f}")

        # Cache stats
        st.markdown("### KV Cache")
        cols = st.columns(3)
        cols[0].metric("Avg Usage", f"{sum(cpu_cache_usage)/len(cpu_cache_usage):.1f}%")
        cols[1].metric("Max Usage", f"{max(cpu_cache_usage):.1f}%")
        cols[2].metric("Min Usage", f"{min(cpu_cache_usage):.1f}%")

        # Token stats
        st.markdown("### Token Processing")
        cols = st.columns(4)
        cols[0].metric("Total Prompt Tokens", f"{int(prompt_tokens[-1]):,}")
        cols[1].metric("Total Generated Tokens", f"{int(generation_tokens[-1]):,}")
        cols[2].metric("Avg Gen Rate", f"{sum(generation_token_rate)/len(generation_token_rate):.2f} tok/s")
        cols[3].metric("Peak Gen Rate", f"{max(generation_token_rate):.2f} tok/s")

        # Request characteristics
        if any(prompt_length) or any(generation_length):
            st.markdown("### Request Characteristics")
            cols = st.columns(2)
            if any(prompt_length):
                valid_prompt = [v for v in prompt_length if v > 0]
                if valid_prompt:
                    cols[0].metric("Avg Prompt Length", f"{sum(valid_prompt)/len(valid_prompt):.1f} tokens")
                    cols[0].caption(f"Min: {min(valid_prompt):.0f} | Max: {max(valid_prompt):.0f}")
            if any(generation_length):
                valid_gen = [v for v in generation_length if v > 0]
                if valid_gen:
                    cols[1].metric("Avg Generation Length", f"{sum(valid_gen)/len(valid_gen):.1f} tokens")
                    cols[1].caption(f"Min: {min(valid_gen):.0f} | Max: {max(valid_gen):.0f}")

    with tab4:
        st.subheader("Raw Metrics Data")

        # Show available metrics
        if samples:
            first_sample = samples[0]
            available_metrics = sorted(first_sample.get('metrics', {}).keys())

            st.markdown(f"### Available Metrics ({len(available_metrics)})")

            # Filter to vLLM-specific metrics
            vllm_metrics = [m for m in available_metrics if m.startswith('vllm:')]

            st.caption(f"Found {len(vllm_metrics)} vLLM-specific metrics")

            # Create expandable sections
            for metric_name in vllm_metrics:
                with st.expander(f"📊 {metric_name}"):
                    # Get time series for this metric
                    metric_values = []
                    for sample in samples:
                        values = get_metric_values(sample, metric_name)
                        if values:
                            metric_values.append({
                                'time': sample['elapsed_seconds'],
                                'value': sum(values) / len(values) if len(values) > 1 else values[0],
                                'count': len(values)
                            })

                    if metric_values:
                        df = pd.DataFrame(metric_values)
                        st.dataframe(df, use_container_width=True)

                        # Simple line chart
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=df['time'],
                            y=df['value'],
                            mode='lines',
                            name=metric_name
                        ))
                        fig.update_layout(
                            xaxis_title="Time (seconds)",
                            yaxis_title="Value",
                            height=300
                        )
                        st.plotly_chart(fig, use_container_width=True)

elif current_section == "⚖️ Compare Configurations":
    # Comparison mode
    st.markdown("### ⚖️ Compare Test Configurations")
    st.markdown("Compare server metrics between two test runs")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Baseline Configuration")

        if test_mode == 'managed':
            # Managed mode filters
            baseline_platform = st.selectbox("Platform", platforms, key="baseline_platform_cmp")
            baseline_filtered = [r for r in results if r.get('platform') == baseline_platform]

            baseline_models = sorted(set(r.get('model', 'unknown') for r in baseline_filtered))
            baseline_model = st.selectbox("Model", baseline_models, key="baseline_model_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('model') == baseline_model]

            baseline_workloads = sorted(set(r.get('workload', 'unknown') for r in baseline_filtered))
            baseline_workload = st.selectbox("Workload", baseline_workloads, key="baseline_workload_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('workload') == baseline_workload]

            baseline_cores_list = sorted(set(r.get('cores', 'N/A') for r in baseline_filtered), key=lambda x: (isinstance(x, str), x))
            baseline_cores_sel = st.selectbox("Cores", baseline_cores_list, key="baseline_cores_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('cores') == baseline_cores_sel]

            baseline_versions = sorted(set(r.get('vllm_version', 'unknown') for r in baseline_filtered))
            baseline_version = st.selectbox("vLLM Version", baseline_versions, key="baseline_version_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('vllm_version') == baseline_version]

            baseline_guidellm_versions = sorted(set(r.get('guidellm_version', 'unknown') for r in baseline_filtered))
            baseline_guidellm_version = st.selectbox("GuideLLM Version", baseline_guidellm_versions, key="baseline_guidellm_version_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('guidellm_version') == baseline_guidellm_version]
        else:  # external mode
            # External mode filters
            baseline_endpoint = st.selectbox("Endpoint URL", endpoints, key="baseline_endpoint_cmp")
            baseline_filtered = [r for r in results if r.get('vllm_endpoint_url') == baseline_endpoint]

            baseline_models = sorted(set(r.get('model', 'unknown') for r in baseline_filtered))
            baseline_model = st.selectbox("Model", baseline_models, key="baseline_model_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('model') == baseline_model]

            baseline_workloads = sorted(set(r.get('workload', 'unknown') for r in baseline_filtered))
            baseline_workload = st.selectbox("Workload", baseline_workloads, key="baseline_workload_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('workload') == baseline_workload]

            baseline_versions = sorted(set(r.get('vllm_version', 'unknown') for r in baseline_filtered))
            baseline_version = st.selectbox("vLLM Version", baseline_versions, key="baseline_version_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('vllm_version') == baseline_version]

            baseline_guidellm_versions = sorted(set(r.get('guidellm_version', 'unknown') for r in baseline_filtered))
            baseline_guidellm_version = st.selectbox("GuideLLM Version", baseline_guidellm_versions, key="baseline_guidellm_version_ext_cmp")
            baseline_filtered = [r for r in baseline_filtered if r.get('guidellm_version') == baseline_guidellm_version]

        # Get available test runs for this configuration
        if baseline_filtered:
            baseline_test_run_options = {
                f"{r.get('test_run_id', 'unknown')[:8]} | {r.get('backend', 'unknown')}": r
                for r in baseline_filtered
            }

            baseline_test_run_label = st.selectbox(
                "Test Run",
                list(baseline_test_run_options.keys()),
                key="baseline_test_run"
            )
            baseline_result = baseline_test_run_options[baseline_test_run_label]
        else:
            baseline_result = None
            st.warning("No data for selected filters")

    with col2:
        st.markdown("#### Comparison Configuration")

        if test_mode == 'managed':
            # Managed mode filters
            compare_platform = st.selectbox("Platform", platforms, key="compare_platform_cmp")
            compare_filtered = [r for r in results if r.get('platform') == compare_platform]

            compare_models = sorted(set(r.get('model', 'unknown') for r in compare_filtered))
            compare_model = st.selectbox("Model", compare_models, key="compare_model_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('model') == compare_model]

            compare_workloads = sorted(set(r.get('workload', 'unknown') for r in compare_filtered))
            compare_workload = st.selectbox("Workload", compare_workloads, key="compare_workload_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('workload') == compare_workload]

            compare_cores_list = sorted(set(r.get('cores', 'N/A') for r in compare_filtered), key=lambda x: (isinstance(x, str), x))
            compare_cores_sel = st.selectbox("Cores", compare_cores_list, key="compare_cores_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('cores') == compare_cores_sel]

            compare_versions = sorted(set(r.get('vllm_version', 'unknown') for r in compare_filtered))
            compare_version = st.selectbox("vLLM Version", compare_versions, key="compare_version_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('vllm_version') == compare_version]

            compare_guidellm_versions = sorted(set(r.get('guidellm_version', 'unknown') for r in compare_filtered))
            compare_guidellm_version = st.selectbox("GuideLLM Version", compare_guidellm_versions, key="compare_guidellm_version_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('guidellm_version') == compare_guidellm_version]
        else:  # external mode
            # External mode filters
            compare_endpoint = st.selectbox("Endpoint URL", endpoints, key="compare_endpoint_cmp")
            compare_filtered = [r for r in results if r.get('vllm_endpoint_url') == compare_endpoint]

            compare_models = sorted(set(r.get('model', 'unknown') for r in compare_filtered))
            compare_model = st.selectbox("Model", compare_models, key="compare_model_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('model') == compare_model]

            compare_workloads = sorted(set(r.get('workload', 'unknown') for r in compare_filtered))
            compare_workload = st.selectbox("Workload", compare_workloads, key="compare_workload_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('workload') == compare_workload]

            compare_versions = sorted(set(r.get('vllm_version', 'unknown') for r in compare_filtered))
            compare_version = st.selectbox("vLLM Version", compare_versions, key="compare_version_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('vllm_version') == compare_version]

            compare_guidellm_versions = sorted(set(r.get('guidellm_version', 'unknown') for r in compare_filtered))
            compare_guidellm_version = st.selectbox("GuideLLM Version", compare_guidellm_versions, key="compare_guidellm_version_ext_cmp")
            compare_filtered = [r for r in compare_filtered if r.get('guidellm_version') == compare_guidellm_version]

        # Get available test runs for this configuration
        if compare_filtered:
            compare_test_run_options = {
                f"{r.get('test_run_id', 'unknown')[:8]} | {r.get('backend', 'unknown')}": r
                for r in compare_filtered
            }

            compare_test_run_label = st.selectbox(
                "Test Run",
                list(compare_test_run_options.keys()),
                key="compare_test_run"
            )
            compare_result = compare_test_run_options[compare_test_run_label]
        else:
            compare_result = None
            st.warning("No data for selected filters")

    if not baseline_result or not compare_result:
        st.error("Please select valid configurations for both baseline and comparison")
        st.stop()

    comparison_results = [baseline_result, compare_result]
    st.markdown("---")
    st.subheader("Comparison Results")

    # Helper functions
    def sum_metric(sample: Dict, metric_name: str) -> float:
        metrics = sample.get('metrics', {})
        if metric_name in metrics:
            return sum(m['value'] for m in metrics[metric_name])
        return 0

    def mean_metric(sample: Dict, metric_name: str) -> float:
        metrics = sample.get('metrics', {})
        if metric_name in metrics:
            values = [m['value'] for m in metrics[metric_name]]
            return sum(values) / len(values) if values else 0
        return 0

    # Calculate key metrics for comparison
    baseline_samples = baseline_result.get('samples', [])
    compare_samples = compare_result.get('samples', [])

    if baseline_samples and compare_samples:
        # Calculate metrics
        baseline_cache_avg = sum(mean_metric(s, 'vllm:kv_cache_usage_perc') for s in baseline_samples) / len(baseline_samples)
        compare_cache_avg = sum(mean_metric(s, 'vllm:kv_cache_usage_perc') for s in compare_samples) / len(compare_samples)
        cache_diff = ((compare_cache_avg - baseline_cache_avg) / baseline_cache_avg * 100) if baseline_cache_avg > 0 else 0

        baseline_queue_avg = sum(sum_metric(s, 'vllm:num_requests_running') for s in baseline_samples) / len(baseline_samples)
        compare_queue_avg = sum(sum_metric(s, 'vllm:num_requests_running') for s in compare_samples) / len(compare_samples)
        queue_diff = ((compare_queue_avg - baseline_queue_avg) / baseline_queue_avg * 100) if baseline_queue_avg > 0 else 0

        # Calculate token generation rates
        baseline_gen_tokens = [sum_metric(s, 'vllm:generation_tokens_total') for s in baseline_samples]
        compare_gen_tokens = [sum_metric(s, 'vllm:generation_tokens_total') for s in compare_samples]
        baseline_timestamps = [s['elapsed_seconds'] for s in baseline_samples]
        compare_timestamps = [s['elapsed_seconds'] for s in compare_samples]

        baseline_gen_rates = []
        for i in range(1, len(baseline_gen_tokens)):
            time_delta = baseline_timestamps[i] - baseline_timestamps[i-1]
            if time_delta > 0:
                baseline_gen_rates.append((baseline_gen_tokens[i] - baseline_gen_tokens[i-1]) / time_delta)

        compare_gen_rates = []
        for i in range(1, len(compare_gen_tokens)):
            time_delta = compare_timestamps[i] - compare_timestamps[i-1]
            if time_delta > 0:
                compare_gen_rates.append((compare_gen_tokens[i] - compare_gen_tokens[i-1]) / time_delta)

        baseline_peak_gen = max(baseline_gen_rates) if baseline_gen_rates else 0
        compare_peak_gen = max(compare_gen_rates) if compare_gen_rates else 0
        gen_diff = ((compare_peak_gen - baseline_peak_gen) / baseline_peak_gen * 100) if baseline_peak_gen > 0 else 0

        # Display metrics
        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)

        with metrics_col1:
            st.metric(
                "Peak Token Generation",
                f"{compare_peak_gen:.2f} tok/s",
                f"{gen_diff:+.1f}% vs baseline",
                delta_color="normal"
            )

        with metrics_col2:
            st.metric(
                "Avg Cache Usage",
                f"{compare_cache_avg:.1f}%",
                f"{cache_diff:+.1f}% vs baseline",
                delta_color="inverse"
            )

        with metrics_col3:
            st.metric(
                "Avg Queue Depth",
                f"{compare_queue_avg:.2f}",
                f"{queue_diff:+.1f}% vs baseline",
                delta_color="inverse"
            )

        st.markdown("---")

    # Create comparison charts
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'KV Cache Usage Comparison',
            'Queue Depth Comparison (Running)',
            'Token Generation Rate',
            'Queue Depth Comparison (Waiting)'
        ),
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )

    colors = ['#3b82f6', '#ef4444']

    # Create detailed labels
    if test_mode == 'managed':
        baseline_label = f"Baseline: {baseline_result.get('platform', 'unknown')} | vLLM {baseline_result.get('vllm_version', 'unknown')} | GuideLLM {baseline_result.get('guidellm_version', 'unknown')} | {baseline_result.get('workload', 'unknown')}"
        compare_label = f"Compare: {compare_result.get('platform', 'unknown')} | vLLM {compare_result.get('vllm_version', 'unknown')} | GuideLLM {compare_result.get('guidellm_version', 'unknown')} | {compare_result.get('workload', 'unknown')}"
    else:  # external mode
        baseline_endpoint_short = baseline_result.get('vllm_endpoint_url', 'unknown')
        if '//' in baseline_endpoint_short:
            baseline_endpoint_short = baseline_endpoint_short.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
        compare_endpoint_short = compare_result.get('vllm_endpoint_url', 'unknown')
        if '//' in compare_endpoint_short:
            compare_endpoint_short = compare_endpoint_short.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
        baseline_label = f"Baseline: {baseline_endpoint_short} | vLLM {baseline_result.get('vllm_version', 'unknown')} | GuideLLM {baseline_result.get('guidellm_version', 'unknown')} | {baseline_result.get('workload', 'unknown')}"
        compare_label = f"Compare: {compare_endpoint_short} | vLLM {compare_result.get('vllm_version', 'unknown')} | GuideLLM {compare_result.get('guidellm_version', 'unknown')} | {compare_result.get('workload', 'unknown')}"

    # Add test names if present
    if baseline_result.get('test_name') and baseline_result['test_name'].strip():
        baseline_label = f"[{baseline_result['test_name']}] {baseline_label}"
    if compare_result.get('test_name') and compare_result['test_name'].strip():
        compare_label = f"[{compare_result['test_name']}] {compare_label}"

    labels = [baseline_label, compare_label]

    for idx, result in enumerate(comparison_results):
        samples = result.get('samples', [])
        if not samples:
            continue

        timestamps = [s['elapsed_seconds'] for s in samples]

        # Cache usage
        cache_usage = [mean_metric(s, 'vllm:kv_cache_usage_perc') for s in samples]

        # Queue metrics
        running = [sum_metric(s, 'vllm:num_requests_running') for s in samples]
        waiting = [sum_metric(s, 'vllm:num_requests_waiting') for s in samples]

        # Token generation rate
        gen_tokens = [sum_metric(s, 'vllm:generation_tokens_total') for s in samples]
        gen_rate = []
        for i in range(len(gen_tokens)):
            if i == 0:
                gen_rate.append(0)
            else:
                time_delta = timestamps[i] - timestamps[i-1]
                if time_delta > 0:
                    gen_rate.append((gen_tokens[i] - gen_tokens[i-1]) / time_delta)
                else:
                    gen_rate.append(0)

        label = labels[idx]
        color = colors[idx % len(colors)]

        # Cache usage
        fig.add_trace(go.Scatter(
            x=timestamps, y=cache_usage,
            name=label,
            mode='lines',
            line=dict(color=color, width=2),
            legendgroup=label
        ), row=1, col=1)

        # Running
        fig.add_trace(go.Scatter(
            x=timestamps, y=running,
            name=label,
            mode='lines',
            line=dict(color=color, width=2),
            legendgroup=label,
            showlegend=False
        ), row=1, col=2)

        # Token rate
        fig.add_trace(go.Scatter(
            x=timestamps, y=gen_rate,
            name=label,
            mode='lines',
            line=dict(color=color, width=2),
            legendgroup=label,
            showlegend=False
        ), row=2, col=1)

        # Waiting
        fig.add_trace(go.Scatter(
            x=timestamps, y=waiting,
            name=label,
            mode='lines',
            line=dict(color=color, width=2),
            legendgroup=label,
            showlegend=False
        ), row=2, col=2)

    fig.update_xaxes(title_text="Time (seconds)", row=2, col=1)
    fig.update_xaxes(title_text="Time (seconds)", row=2, col=2)
    fig.update_yaxes(title_text="Percentage", row=1, col=1)
    fig.update_yaxes(title_text="Requests", row=1, col=2)
    fig.update_yaxes(title_text="Tokens/sec", row=2, col=1)
    fig.update_yaxes(title_text="Requests", row=2, col=2)

    fig.update_layout(height=700, hovermode='x unified')

    st.plotly_chart(fig, use_container_width=True)

    # Comparison table
    st.subheader("Summary Comparison")

    comparison_table = []
    for result in comparison_results:
        samples = result.get('samples', [])
        if not samples:
            continue

        # Calculate averages
        cache_avg = sum(mean_metric(s, 'vllm:kv_cache_usage_perc') for s in samples) / len(samples)
        running_avg = sum(sum_metric(s, 'vllm:num_requests_running') for s in samples) / len(samples)
        waiting_avg = sum(sum_metric(s, 'vllm:num_requests_waiting') for s in samples) / len(samples)

        row = {
            'Backend': result.get('backend', 'unknown'),
            'Version': result.get('vllm_version', 'unknown'),
            'Test Run ID': result.get('test_run_id', 'unknown')[:8],
            'Avg Cache %': f"{cache_avg:.1f}",
            'Avg Running': f"{running_avg:.2f}",
            'Avg Waiting': f"{waiting_avg:.2f}"
        }

        if test_mode == 'managed':
            row['Platform'] = result.get('platform', 'unknown')
            row['Cores'] = result.get('cores', 'N/A')
        else:  # external mode
            endpoint_url = result.get('vllm_endpoint_url', 'unknown')
            endpoint_short = endpoint_url.split('//', 1)[-1].rsplit('@', 1)[-1].split('/', 1)[0]
            row['Endpoint'] = endpoint_short

        comparison_table.append(row)

    comparison_df = pd.DataFrame(comparison_table)
    st.dataframe(comparison_df, use_container_width=True)

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("vLLM Server-Side Metrics Dashboard")
st.sidebar.caption(f"Monitoring: {results_dir}")
