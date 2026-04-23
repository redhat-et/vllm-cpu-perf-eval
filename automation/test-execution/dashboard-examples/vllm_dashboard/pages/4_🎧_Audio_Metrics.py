"""vLLM Audio Performance Dashboard.

Audio-specific metrics for speech recognition, translation, and audio chat models.
Focuses on Real-Time Factor (RTF), audio throughput, and audio processing characteristics.
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


# Custom CSS styling
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_audio_data(results_dir: str) -> pd.DataFrame:
    """Load audio benchmark results with audio-specific metrics."""
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
            metadata_file = json_file.parent.parent / "test-metadata.json"
            if not metadata_file.exists():
                # Try in same directory for flat structure
                metadata_file = json_file.parent / "test-metadata.json"
            if not metadata_file.exists():
                continue

            with open(metadata_file) as f:
                metadata = json.load(f)

            # Extract each benchmark (load point)
            for bench in data.get('benchmarks', []):
                metrics = bench['metrics']
                config = bench['config']
                requests = bench['requests']

                # Extract concurrency/rate
                concurrency = config.get('strategy', {}).get('max_concurrency', 0)
                req_rate = metrics.get('requests_per_second', {}).get('successful', {}).get('mean', concurrency)

                # Calculate audio-specific aggregates from successful requests
                successful_requests = requests.get('successful', [])
                audio_metrics = calculate_audio_aggregates(successful_requests)

                # Skip if no audio metrics found (filters out LLM results)
                if audio_metrics['total_audio_seconds'] == 0:
                    continue

                # Extract stage name from path (e.g., "sequential", "concurrent-2")
                stage = json_file.parent.name

                row = {
                    # Metadata
                    'test_run_id': metadata.get('test_run_id', 'unknown'),
                    'platform': metadata.get('platform', 'unknown'),
                    'model': metadata.get('model', 'unknown'),
                    'model_short': metadata.get('model', 'unknown').split('/')[-1],
                    'scenario': metadata.get('scenario_name', metadata.get('scenario', 'unknown')),
                    'stage': stage,
                    'cores': metadata.get('core_count', 0),
                    'backend': metadata.get('backend', 'unknown'),
                    'vllm_version': metadata.get('vllm_version', 'unknown'),
                    'guidellm_version': metadata.get('guidellm_version', 'unknown'),
                    'tensor_parallel': metadata.get('tensor_parallel', 1),

                    # Load characteristics
                    'concurrency': concurrency,
                    'request_rate': req_rate,

                    # General performance metrics
                    'duration': bench['duration'],
                    'requests_per_second': metrics['requests_per_second']['successful']['mean'],

                    # Request latency (seconds)
                    'e2e_mean': metrics['request_latency']['successful']['mean'],
                    'e2e_p50': metrics['request_latency']['successful']['percentiles']['p50'],
                    'e2e_p95': metrics['request_latency']['successful']['percentiles']['p95'],
                    'e2e_p99': metrics['request_latency']['successful']['percentiles']['p99'],

                    # Request stats
                    'total_requests': metrics['request_totals']['total'],
                    'successful_requests': metrics['request_totals']['successful'],
                    'errored_requests': metrics['request_totals']['errored'],
                    'success_rate': (metrics['request_totals']['successful'] /
                                   metrics['request_totals']['total'] * 100)
                                   if metrics['request_totals']['total'] > 0 else 0,

                    # Audio-specific metrics (aggregated from requests)
                    'total_audio_seconds': audio_metrics['total_audio_seconds'],
                    'mean_audio_seconds': audio_metrics['mean_audio_seconds'],
                    'total_audio_samples': audio_metrics['total_audio_samples'],
                    'total_audio_bytes': audio_metrics['total_audio_bytes'],
                    'audio_tokens': audio_metrics['audio_tokens'],

                    # Calculated audio metrics
                    'audio_throughput': audio_metrics['audio_throughput'],  # audio_seconds/wall_clock_second
                    'rtf_mean': audio_metrics['rtf_mean'],  # Real-time factor
                    'rtf_p50': audio_metrics['rtf_p50'],
                    'rtf_p95': audio_metrics['rtf_p95'],
                    'rtf_p99': audio_metrics['rtf_p99'],
                }

                all_results.append(row)

        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
            continue

    if not all_results:
        return pd.DataFrame()

    df = pd.DataFrame(all_results)

    # Calculate efficiency (audio throughput per core)
    cores = pd.to_numeric(df['cores'], errors='coerce')
    df['efficiency'] = np.where(cores > 0, df['audio_throughput'] / cores, np.nan)

    return df


def calculate_audio_aggregates(successful_requests: list) -> dict:
    """Calculate audio-specific aggregate metrics from request list."""
    if not successful_requests:
        return {
            'total_audio_seconds': 0,
            'mean_audio_seconds': 0,
            'total_audio_samples': 0,
            'total_audio_bytes': 0,
            'audio_tokens': 0,
            'audio_throughput': 0,
            'rtf_mean': 0,
            'rtf_p50': 0,
            'rtf_p95': 0,
            'rtf_p99': 0,
        }

    audio_seconds_list = []
    audio_samples_list = []
    audio_bytes_list = []
    audio_tokens_list = []
    rtf_list = []
    total_duration = 0

    for req in successful_requests:
        input_metrics = req.get('input_metrics', {})
        audio_seconds = input_metrics.get('audio_seconds', 0)
        audio_samples = input_metrics.get('audio_samples', 0)
        audio_bytes = input_metrics.get('audio_bytes', 0)
        audio_tokens = input_metrics.get('audio_tokens', 0)
        request_latency = req.get('request_latency', 0)

        if audio_seconds and audio_seconds > 0:
            audio_seconds_list.append(audio_seconds)
            # RTF = processing_time / audio_duration
            # RTF < 1.0 = faster than real-time
            rtf = request_latency / audio_seconds if audio_seconds > 0 else 0
            rtf_list.append(rtf)

        if audio_samples:
            audio_samples_list.append(audio_samples)
        if audio_bytes:
            audio_bytes_list.append(audio_bytes)
        if audio_tokens:
            audio_tokens_list.append(audio_tokens)

        # Use max end time for throughput calculation
        end_time = req.get('request_end_time', 0)
        total_duration = max(total_duration, end_time)

    total_audio_seconds = sum(audio_seconds_list)
    mean_audio_seconds = np.mean(audio_seconds_list) if audio_seconds_list else 0

    # Audio throughput: total audio seconds processed per wall-clock second
    # E.g., if we process 100 seconds of audio in 10 wall-clock seconds, throughput = 10
    audio_throughput = total_audio_seconds / total_duration if total_duration > 0 else 0

    return {
        'total_audio_seconds': total_audio_seconds,
        'mean_audio_seconds': mean_audio_seconds,
        'total_audio_samples': sum(audio_samples_list),
        'total_audio_bytes': sum(audio_bytes_list),
        'audio_tokens': sum(audio_tokens_list),
        'audio_throughput': audio_throughput,
        'rtf_mean': np.mean(rtf_list) if rtf_list else 0,
        'rtf_p50': np.percentile(rtf_list, 50) if rtf_list else 0,
        'rtf_p95': np.percentile(rtf_list, 95) if rtf_list else 0,
        'rtf_p99': np.percentile(rtf_list, 99) if rtf_list else 0,
    }


def render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render filter UI and return filtered DataFrame."""
    st.markdown("### 🔍 Filter your data")

    col1, col2, col3 = st.columns(3)

    with col1:
        models = sorted(df['model_short'].unique())
        selected_models = st.multiselect(
            "Model",
            models,
            default=models,
            key="model_filter_audio"
        )

    with col2:
        scenarios = sorted(df['scenario'].unique())
        selected_scenarios = st.multiselect(
            "Scenario",
            scenarios,
            default=scenarios,
            key="scenario_filter_audio"
        )

    with col3:
        cores_list = sorted(df['cores'].unique())
        selected_cores = st.multiselect(
            "Core Count",
            cores_list,
            default=cores_list,
            key="cores_filter_audio"
        )

    # Apply filters
    filtered = df[
        (df['model_short'].isin(selected_models)) &
        (df['scenario'].isin(selected_scenarios)) &
        (df['cores'].isin(selected_cores))
    ]

    return filtered


def render_overview_metrics(df: pd.DataFrame):
    """Render overview metric cards."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Avg Audio Throughput",
            f"{df['audio_throughput'].mean():.2f}x",
            help="Average audio seconds processed per wall-clock second (higher = faster)"
        )

    with col2:
        avg_rtf = df['rtf_mean'].mean()
        st.metric(
            "Avg Real-Time Factor",
            f"{avg_rtf:.3f}",
            help="Processing time / audio duration (< 1.0 = faster than real-time)"
        )

    with col3:
        st.metric(
            "Avg Success Rate",
            f"{df['success_rate'].mean():.1f}%",
            help="Percentage of successful requests"
        )

    with col4:
        st.metric(
            "Total Audio Processed",
            f"{df['total_audio_seconds'].sum():.1f}s",
            help="Total seconds of audio processed across all tests"
        )


def plot_audio_throughput(df: pd.DataFrame):
    """Plot audio throughput vs concurrency/stage."""
    st.markdown("### 🎵 Audio Throughput")
    st.markdown("""
    **Audio seconds processed per wall-clock second** (higher = faster)

    This shows how many seconds of audio content are processed every wall-clock second.
    Example: 10.0x means 10 seconds of audio are transcribed in 1 wall-clock second.
    """)

    fig = px.bar(
        df.sort_values('concurrency'),
        x='stage',
        y='audio_throughput',
        color='model_short',
        barmode='group',
        labels={
            'audio_throughput': 'Audio Throughput (audio_sec/wall_sec)',
            'stage': 'Test Stage',
            'model_short': 'Model'
        },
        title="Audio Throughput by Stage and Model"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)


def plot_rtf(df: pd.DataFrame):
    """Plot Real-Time Factor (RTF) across stages."""
    st.markdown("### ⏱️ Real-Time Factor (RTF)")
    st.markdown("""
    **Processing time / audio duration** (lower = better)

    - **RTF < 1.0** = ✅ Faster than real-time (e.g., RTF=0.1 is 10x faster)
    - **RTF = 1.0** = Real-time processing (shown as red dashed line)
    - **RTF > 1.0** = ⚠️ Slower than real-time

    Example: RTF=0.2 means a 10-second audio clip takes 2 seconds to process.
    """)

    # Prepare data for plotting percentiles
    plot_data = []
    for _, row in df.iterrows():
        for percentile in ['mean', 'p50', 'p95', 'p99']:
            plot_data.append({
                'stage': row['stage'],
                'model': row['model_short'],
                'percentile': percentile.upper(),
                'rtf': row[f'rtf_{percentile}']
            })

    plot_df = pd.DataFrame(plot_data)

    fig = px.line(
        plot_df,
        x='stage',
        y='rtf',
        color='model',
        line_dash='percentile',
        markers=True,
        labels={
            'rtf': 'Real-Time Factor',
            'stage': 'Test Stage',
            'model': 'Model',
            'percentile': 'Percentile'
        },
        title="Real-Time Factor by Stage (Lower = Better)"
    )

    # Add reference line at RTF=1.0 (real-time processing)
    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="red",
        annotation_text="Real-time (RTF=1.0)",
        annotation_position="right"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)


def plot_latency_vs_audio_duration(df: pd.DataFrame):
    """Plot request latency vs audio duration."""
    st.markdown("### 📊 Latency vs Audio Duration")
    st.markdown("""
    **How processing time scales with audio length**

    Points above the red dashed line (RTF=1.0) are slower than real-time.
    Points below the line are faster than real-time.
    Linear scaling means processing time grows proportionally with audio duration.
    """)

    fig = px.scatter(
        df,
        x='mean_audio_seconds',
        y='e2e_mean',
        color='model_short',
        size='concurrency',
        labels={
            'mean_audio_seconds': 'Audio Duration (seconds)',
            'e2e_mean': 'Mean Request Latency (seconds)',
            'model_short': 'Model',
            'concurrency': 'Concurrency'
        },
        title="Request Latency vs Audio Duration"
    )

    # Add diagonal line for RTF=1.0
    max_duration = df['mean_audio_seconds'].max()
    fig.add_scatter(
        x=[0, max_duration],
        y=[0, max_duration],
        mode='lines',
        line=dict(dash='dash', color='red'),
        name='RTF=1.0 (real-time)',
        showlegend=True
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)


def plot_total_time_comparison(df: pd.DataFrame):
    """Plot total time to process N files by stage."""
    st.markdown("### ⏰ Total Time to Process N Files")
    st.markdown("""
    **Wall-clock time to transcribe all audio files** (lower = faster)

    This answers: "How long does it take to transcribe N audio files?"
    - Sequential: Files processed one-by-one (baseline)
    - Concurrent-N: Files processed with N concurrent requests
    - Max-throughput: Maximum concurrency for fastest total time

    Lower bars = faster total processing time.
    """)

    # Show total duration (lower is better)
    fig = px.bar(
        df.sort_values('concurrency'),
        x='stage',
        y='duration',
        color='model_short',
        barmode='group',
        labels={
            'duration': 'Total Time (seconds)',
            'stage': 'Test Stage',
            'model_short': 'Model'
        },
        title="Total Time to Process All Files (Lower = Faster)"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    # Also show the summary table
    st.markdown("#### Summary: Files Processed and Total Time")
    summary = df.groupby(['model_short', 'stage']).agg({
        'successful_requests': 'first',
        'duration': 'first',
        'requests_per_second': 'first'
    }).reset_index()
    summary['files_per_hour'] = summary['requests_per_second'] * 3600
    summary = summary.rename(columns={
        'model_short': 'Model',
        'stage': 'Stage',
        'successful_requests': 'Files Processed',
        'duration': 'Total Time (s)',
        'requests_per_second': 'Files/Second',
        'files_per_hour': 'Files/Hour'
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)


def plot_efficiency(df: pd.DataFrame):
    """Plot efficiency (audio throughput per core)."""
    st.markdown("### ⚡ Efficiency (Audio Throughput per Core)")

    fig = px.bar(
        df.sort_values('concurrency'),
        x='stage',
        y='efficiency',
        color='model_short',
        barmode='group',
        labels={
            'efficiency': 'Efficiency (audio_sec/wall_sec/core)',
            'stage': 'Test Stage',
            'model_short': 'Model'
        },
        title="Audio Processing Efficiency"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)


def render_data_table(df: pd.DataFrame):
    """Render detailed data table."""
    st.markdown("### 📋 Detailed Results")

    # Select relevant columns
    display_cols = [
        'model_short', 'scenario', 'stage', 'cores', 'concurrency',
        'audio_throughput', 'rtf_mean', 'rtf_p95', 'rtf_p99',
        'requests_per_second', 'e2e_mean', 'e2e_p95',
        'total_audio_seconds', 'mean_audio_seconds',
        'successful_requests', 'success_rate'
    ]

    # Filter to available columns
    display_cols = [col for col in display_cols if col in df.columns]

    st.dataframe(
        df[display_cols].sort_values(['model_short', 'scenario', 'concurrency']),
        use_container_width=True,
        hide_index=True
    )

    # Download button
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="audio_benchmark_results.csv",
        mime="text/csv"
    )


def main():
    """Main dashboard rendering."""
    st.title("🎧 Audio Performance Metrics")
    st.markdown("""
    Audio-specific performance analysis for speech recognition, translation, and audio chat models.
    """)

    # Metrics explanation in expandable section
    with st.expander("📖 Understanding Audio Metrics", expanded=False):
        st.markdown("""
        ### Key Metrics Explained

        #### 🎵 Audio Throughput (audio_seconds/wall_second)
        - **What it measures:** How many seconds of audio are processed per wall-clock second
        - **Example:** 10.0x means 10 seconds of audio processed every wall-clock second
        - **Interpretation:** Higher = faster processing, better for batch jobs
        - **Use case:** "How long to transcribe 1000 hours of audio?"

        #### ⏱️ Real-Time Factor (RTF)
        - **Formula:** RTF = processing_time / audio_duration
        - **RTF < 1.0** = ✅ Faster than real-time (e.g., RTF=0.1 means 10x faster)
        - **RTF = 1.0** = Real-time processing (processing keeps pace with audio playback)
        - **RTF > 1.0** = ⚠️ Slower than real-time (processing can't keep up)
        - **Example:** RTF=0.2 means a 10-second audio clip is processed in 2 seconds
        - **Use case:** "Can we transcribe live phone calls in real-time?"

        #### 📈 Request Throughput (files/second)
        - **What it measures:** Number of audio files processed per second
        - **Interpretation:** Higher = more files processed per unit time
        - **Use case:** "How many audio files can we process per hour?"

        #### ⚡ Efficiency (per core)
        - **Formula:** Audio throughput / CPU cores
        - **What it measures:** Audio processing throughput per CPU core
        - **Interpretation:** Higher = better CPU utilization
        - **Use case:** "Should we allocate 32 or 64 cores for best efficiency?"

        #### 📊 Percentiles (P50, P95, P99)
        - **P50 (Median):** 50% of requests were this fast or faster
        - **P95:** 95% of requests were this fast or faster (tail latency)
        - **P99:** 99% of requests were this fast or faster (worst-case tail)
        - **For RTF:** Lower percentiles = better (more consistent performance)
        - **Use case:** "What's our worst-case RTF for 99% of requests?"

        ### Test Stages Explained

        - **Sequential:** Process files one-by-one (offline batch baseline)
        - **Concurrent-N:** Simulate N concurrent users (online serving)
        - **Max-throughput:** Find maximum capacity with high concurrency
        """)

    st.markdown("---")

    # Load config
    config = DashboardConfig()

    # Get default path - use audio-models instead of llm
    default_results_dir = config.get_results_directory().replace('/llm', '/audio-models')

    # Sidebar: Results directory
    st.sidebar.markdown("## 📁 Data Source")
    results_dir = st.sidebar.text_input(
        "Results Directory",
        value=default_results_dir,
        help="Path to audio-models results directory"
    )

    # Update config if changed (save the audio path)
    if results_dir != default_results_dir:
        config.set_results_directory(results_dir)

    # Load data
    with st.spinner("Loading audio benchmark data..."):
        df = load_audio_data(results_dir)

    if df.empty:
        st.warning(f"""
        No audio benchmark data found in: `{results_dir}`

        **Note:** This dashboard only shows audio model results (ASR, translation, chat).
        LLM text generation results are filtered out automatically.

        **Expected structure:**
        ```
        {results_dir}/
        └── openai__whisper-small/
            └── transcription-throughput-20260423-103307/
                ├── sequential/
                │   └── benchmarks.json
                ├── concurrent-2/
                │   └── benchmarks.json
                └── test-metadata.json
        ```

        **Run audio benchmarks first:**
        ```bash
        ansible-playbook -i inventory/hosts.yml audio-benchmark.yml \\
          -e "test_model=openai/whisper-small" \\
          -e "test_scenario=transcription-throughput" \\
          -e "requested_cores=32"
        ```

        **Default path:** Results should be in `results/audio-models/`
        """)
        return

    st.success(f"✅ Loaded {len(df)} test results from {len(df['test_run_id'].unique())} test runs")

    # Filters
    filtered_df = render_filters(df)

    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
        return

    # Overview metrics
    render_overview_metrics(filtered_df)

    st.markdown("---")

    # Charts
    plot_total_time_comparison(filtered_df)
    st.markdown("---")

    plot_audio_throughput(filtered_df)
    st.markdown("---")

    plot_rtf(filtered_df)
    st.markdown("---")

    plot_latency_vs_audio_duration(filtered_df)
    st.markdown("---")

    plot_efficiency(filtered_df)
    st.markdown("---")

    # Data table
    render_data_table(filtered_df)


if __name__ == "__main__":
    main()
