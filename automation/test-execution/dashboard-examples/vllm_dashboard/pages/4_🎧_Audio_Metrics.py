"""vLLM Audio Performance Dashboard.

Audio-specific metrics for speech recognition, translation, and audio chat models.
Focuses on Real-Time Factor (RTF), audio throughput, and audio processing characteristics.
"""

import logging
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Add parent directory to path for config_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig
from audio_enterprise import (
    compute_batch_eta,
    compute_capacity_metrics,
    compute_warmup_metrics,
    discover_run_results,
    format_duration,
    format_enterprise_report,
    load_quality_results,
)

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
    rows = discover_run_results(results_dir)
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    cores = pd.to_numeric(df['cores'], errors='coerce')
    df['efficiency'] = np.where(cores > 0, df['audio_throughput'] / cores, np.nan)
    return df


@st.cache_data(ttl=300)
def load_quality_data(results_dir: str) -> pd.DataFrame:
    """Load quality-results.json files, if any."""
    data = load_quality_results(results_dir)
    return pd.DataFrame(data) if data else pd.DataFrame()


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
    # Test Dataset Overview — use one representative stage per run to avoid
    # double-counting files/audio across sequential + concurrent + max-throughput.
    representative = df.copy()
    if 'sequential' in df['stage'].values:
        representative = df[df['stage'] == 'sequential']
    else:
        representative = df.drop_duplicates(
            subset=['test_run_id', 'model', 'scenario'], keep='first'
        )

    st.markdown("### 📊 Test Dataset Overview")

    # First row: File statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_files = representative['successful_requests'].sum()
        st.metric(
            "Audio Files",
            f"{int(total_files)}",
            help="Total audio files (deduplicated by run, using representative stage)"
        )

    with col2:
        avg_duration = representative['mean_audio_seconds'].mean()
        st.metric(
            "Avg Duration",
            f"{avg_duration:.2f}s per file",
            help="Average audio file duration"
        )

    with col3:
        total_audio = representative['total_audio_seconds'].sum()
        if total_audio >= 3600:
            display_audio = f"{total_audio/3600:.2f}h"
        elif total_audio >= 60:
            display_audio = f"{total_audio/60:.1f}min"
        else:
            display_audio = f"{total_audio:.1f}s"
        st.metric(
            "Total Audio",
            display_audio,
            help="Total audio content (deduplicated by run)"
        )

    with col4:
        total_mb = representative['total_audio_bytes'].sum() / (1024 * 1024)
        st.metric(
            "Total Data",
            f"{total_mb:.1f} MB",
            help="Total audio payload size (deduplicated by run)"
        )

    # Second row: Audio format details
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        unique_formats = df['audio_format'].unique()
        if len(unique_formats) == 1:
            display_format = str(unique_formats[0]).upper()
        else:
            display_format = ", ".join(
                sorted(str(f).upper() for f in unique_formats if f != 'unknown')
            ) or "Mixed"
        st.metric(
            "Audio Format",
            display_format,
            help="Audio file format (MP3, WAV, FLAC, etc.)"
        )

    with col2:
        unique_rates = df['audio_sample_rate'].unique()
        if len(unique_rates) == 1:
            sample_rate = unique_rates[0]
            if sample_rate >= 1000:
                display_rate = f"{int(sample_rate/1000)}kHz"
            else:
                display_rate = f"{int(sample_rate)}Hz"
        else:
            display_rate = "Mixed"
        st.metric(
            "Sample Rate",
            display_rate,
            help="Audio sampling frequency"
        )

    with col3:
        unique_bitrates = df['audio_bitrate'].unique()
        if len(unique_bitrates) == 1:
            bitrate = unique_bitrates[0]
            display_br = bitrate.upper() if isinstance(bitrate, str) else str(bitrate)
        else:
            display_br = "Mixed"
        st.metric(
            "Bitrate",
            display_br,
            help="Audio encoding bitrate"
        )

    with col4:
        # Get dataset
        dataset = df['dataset_name'].iloc[0] if len(df) > 0 else 'unknown'
        dataset_short = dataset.split('/')[-1] if '/' in dataset else dataset
        st.metric(
            "Dataset",
            dataset_short,
            help=f"Source dataset: {dataset}"
        )

    st.markdown("---")

    # Performance Overview — show best-stage metrics explicitly
    st.markdown("### 📈 Performance Overview")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        best_throughput = df['audio_throughput'].max()
        best_throughput_stage = df.loc[df['audio_throughput'].idxmax(), 'stage']
        st.metric(
            "Best Audio Hours/Hour",
            f"{best_throughput:.1f}h/h",
            help=f"Best throughput: {best_throughput:.1f}h/h at {best_throughput_stage} stage"
        )

    with col2:
        max_throughput_row = df.loc[df['requests_per_second'].idxmax()]
        files_per_hour = max_throughput_row['requests_per_second'] * 3600
        st.metric(
            "Max Files/Hour",
            f"{int(files_per_hour):,}",
            help=f"Maximum capacity at {max_throughput_row['stage']} stage"
        )

    with col3:
        best_rtf = df['rtf_mean'].min()
        best_rtf_stage = df.loc[df['rtf_mean'].idxmin(), 'stage']
        st.metric(
            "Best RTF",
            f"{best_rtf:.3f}",
            help=f"Best (lowest) RTF at {best_rtf_stage} stage (< 1.0 = faster than real-time)"
        )

    with col4:
        st.metric(
            "Avg Success Rate",
            f"{df['success_rate'].mean():.1f}%",
            help="Percentage of successful requests across all stages"
        )


def plot_speedup_vs_sequential(df: pd.DataFrame):
    """Plot speedup relative to sequential baseline."""
    st.markdown("### 📈 Speedup vs Sequential Baseline")
    st.markdown("""
    **How much faster is concurrent processing vs sequential?**

    Shows the speedup factor for each stage compared to sequential processing.
    - 1.0x = Same speed as sequential (baseline)
    - 2.6x = 2.6 times faster than sequential
    - Higher = better

    Example: If sequential takes 10 seconds and concurrent-8 takes 3.8 seconds, speedup = 2.6x
    """)

    # Calculate speedup for each model+run combination
    speedup_data = []
    for (model, run_id), group_df in df.groupby(['model_short', 'test_run_id']):
        sequential_rows = group_df[group_df['stage'] == 'sequential']
        if sequential_rows.empty:
            continue

        sequential_duration = sequential_rows['duration'].iloc[0]

        for _, row in group_df.iterrows():
            speedup = sequential_duration / row['duration'] if row['duration'] > 0 else 0
            speedup_data.append({
                'model': model,
                'stage': row['stage'],
                'speedup': speedup,
                'concurrency': row['concurrency']
            })

    if not speedup_data:
        st.warning("No sequential baseline found for speedup calculation")
        return

    speedup_df = pd.DataFrame(speedup_data)

    fig = px.bar(
        speedup_df.sort_values('concurrency'),
        x='stage',
        y='speedup',
        color='model',
        barmode='group',
        labels={
            'speedup': 'Speedup (vs Sequential)',
            'stage': 'Test Stage',
            'model': 'Model'
        },
        title="Speedup Relative to Sequential Processing"
    )

    # Add reference line at 1.0x (sequential baseline)
    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="gray",
        annotation_text="Sequential Baseline (1.0x)",
        annotation_position="right"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    # Show speedup summary
    st.markdown("#### Speedup Summary")
    summary = speedup_df.groupby(['model', 'stage']).agg({'speedup': 'first', 'concurrency': 'first'}).reset_index()
    summary = summary.rename(columns={
        'model': 'Model',
        'stage': 'Stage',
        'speedup': 'Speedup (x)',
        'concurrency': 'Concurrency'
    })
    summary['Speedup (x)'] = summary['Speedup (x)'].round(2)
    st.dataframe(summary, use_container_width=True, hide_index=True)


def plot_audio_throughput(df: pd.DataFrame):
    """Plot audio throughput vs concurrency/stage."""
    st.markdown("### 🎵 Audio Hours/Hour")
    st.markdown("""
    **Hours of audio processed per hour** (higher = faster)

    This shows how many hours of audio content are processed every wall-clock hour.
    - **1.0 h/h** = Real-time processing (1 hour to process 1 hour of audio)
    - **10.0 h/h** = 10x real-time (process 10 hours of audio in 1 hour)
    - Higher = faster processing
    """)

    fig = px.bar(
        df.sort_values('concurrency'),
        x='stage',
        y='audio_throughput',
        color='model_short',
        barmode='group',
        labels={
            'audio_throughput': 'Audio Hours/Hour',
            'stage': 'Test Stage',
            'model_short': 'Model'
        },
        title="Audio Processing Throughput (Hours of Audio per Hour)"
    )

    # Add reference line at 1.0 (real-time)
    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="red",
        annotation_text="Real-time (1.0 h/h)",
        annotation_position="right"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)


def plot_files_per_hour(df: pd.DataFrame):
    """Plot files processed per hour."""
    st.markdown("### 📁 Files per Hour")
    st.markdown("""
    **Audio files processed per hour** (higher = better)

    This shows capacity for batch processing audio files.
    Example: 15,840 files/hour means you can process almost 16K audio files per hour.
    """)

    # Calculate files/hour from requests/second
    df_plot = df.copy()
    df_plot['files_per_hour'] = df_plot['requests_per_second'] * 3600

    fig = px.bar(
        df_plot.sort_values('concurrency'),
        x='stage',
        y='files_per_hour',
        color='model_short',
        barmode='group',
        labels={
            'files_per_hour': 'Files/Hour',
            'stage': 'Test Stage',
            'model_short': 'Model'
        },
        title="Files Processed per Hour"
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

    # Percentile selector (checkboxes like LLM dashboard)
    percentile_labels = {"mean": "Mean", "p50": "P50", "p95": "P95", "p99": "P99"}
    available_percentiles = ["mean", "p50", "p95", "p99"]

    st.markdown("**Show percentiles:**")
    cols = st.columns(len(available_percentiles))
    selected_percentiles = []
    for idx, percentile in enumerate(available_percentiles):
        with cols[idx]:
            # Default to P95 and P99 like LLM dashboard
            default_checked = percentile in ["p95", "p99"]
            if st.checkbox(percentile_labels[percentile], value=default_checked, key=f"rtf_percentile_{percentile}"):
                selected_percentiles.append(percentile)

    if not selected_percentiles:
        st.warning("⚠️ Select at least one percentile to display")
        return

    # Prepare data for plotting selected percentiles only
    plot_data = []
    for _, row in df.iterrows():
        for percentile in selected_percentiles:
            plot_data.append({
                'stage': row['stage'],
                'model': row['model_short'],
                'percentile': percentile_labels[percentile],
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
        title="Real-Time Factor - {} (Lower = Better)".format(
            ", ".join(percentile_labels[p] for p in selected_percentiles)
        )
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


def render_quality_tab(quality_df: pd.DataFrame, perf_df: pd.DataFrame):
    """Render the Quality (WER/CER) tab."""
    if quality_df.empty:
        st.info(
            "No quality data found.  Run `evaluate_audio_quality.py` against your "
            "vLLM endpoint to generate WER/CER metrics, then reload this page."
        )
        return

    st.markdown("### Transcription Quality (WER / CER)")

    col1, col2, col3 = st.columns(3)
    with col1:
        avg_wer = quality_df['wer'].mean()
        st.metric("Avg WER", f"{avg_wer * 100:.1f}%" if pd.notna(avg_wer) else "n/a")
    with col2:
        if 'cer' in quality_df.columns and quality_df['cer'].notna().any():
            avg_cer = quality_df['cer'].mean()
            st.metric("Avg CER", f"{avg_cer * 100:.1f}%")
        else:
            st.metric("Avg CER", "n/a")
    with col3:
        total_clips = quality_df['num_clips'].sum()
        st.metric("Total Clips Evaluated", f"{int(total_clips)}")

    st.markdown("---")

    if len(quality_df) > 1:
        fig = px.bar(
            quality_df,
            x='model_short',
            y=quality_df['wer'] * 100,
            color='model_short',
            labels={'y': 'WER (%)', 'model_short': 'Model'},
            title="Word Error Rate by Model",
        )
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    if not perf_df.empty and 'model_short' in perf_df.columns:
        merged = quality_df.merge(
            perf_df.groupby('model_short')['rtf_mean'].min().reset_index(),
            on='model_short', how='inner',
        )
        if not merged.empty:
            st.markdown("#### WER vs Best RTF")
            if len(merged) > 1:
                fig2 = px.scatter(
                    merged,
                    x=merged['wer'] * 100,
                    y='rtf_mean',
                    text='model_short',
                    labels={'x': 'WER (%)', 'rtf_mean': 'Best RTF (lower=faster)'},
                    title="Accuracy vs Speed Trade-off",
                )
                fig2.update_traces(textposition='top center')
                fig2.update_layout(height=400)
                st.plotly_chart(fig2, use_container_width=True)
            else:
                row = merged.iloc[0]
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Model", row['model_short'])
                with col2:
                    st.metric("WER", f"{row['wer'] * 100:.1f}%")
                with col3:
                    st.metric("Best RTF", f"{row['rtf_mean']:.3f}")

    st.markdown("#### Quality Details")
    display = quality_df[['model_short', 'wer', 'cer', 'num_clips',
                          'dataset', 'audio_format']].copy()
    display['wer'] = display['wer'].apply(
        lambda v: f"{v * 100:.1f}%" if pd.notna(v) else "n/a",
    )
    display['cer'] = display['cer'].apply(
        lambda v: f"{v * 100:.1f}%" if pd.notna(v) else "n/a",
    )
    st.dataframe(display, use_container_width=True, hide_index=True)


def render_capacity_tab(df: pd.DataFrame, p95_target: float):
    """Render the Capacity / Sizing tab."""
    from collections import defaultdict

    st.markdown("### Capacity Planning & Sizing")

    runs: dict[str, list[dict]] = defaultdict(list)
    for row in df.to_dict('records'):
        runs[row['test_run_id']].append(row)

    if not runs:
        st.warning("No performance data available for capacity analysis.")
        return

    for run_id, stages in sorted(runs.items()):
        model = stages[0].get('model', 'unknown')
        cores = stages[0].get('cores', 0)
        cap = compute_capacity_metrics(stages, cores, p95_target)
        warmup = compute_warmup_metrics(stages)

        st.markdown(f"#### {model} — {cores} cores (run: {run_id})")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            v = cap.get('audio_hours_per_hour')
            st.metric("Audio Hours/Hour",
                       f"{v:.1f}" if v is not None else "n/a")
        with col2:
            v = cap.get('files_per_hour')
            st.metric("Files/Hour",
                       f"{int(v):,}" if v is not None else "n/a")
        with col3:
            mc = cap.get('max_concurrency_at_p95')
            st.metric(f"Max Concurrency (P95 ≤ {p95_target}s)",
                       f"{mc}" if mc is not None else "n/a")
        with col4:
            v = cap.get('core_hours_per_audio_hour')
            st.metric("Core-Hours/Audio-Hour",
                       f"{v:.2f}" if v is not None else "n/a")

        col1, col2, col3 = st.columns(3)
        with col1:
            v = cap.get('throughput_per_core')
            st.metric("Throughput/Core",
                       f"{v:.3f}" if v is not None else "n/a")
        with col2:
            v = warmup.get('warmup_duration')
            st.metric("Warmup (ready)",
                       f"{v:.1f}s" if v is not None else "n/a")
        with col3:
            v = warmup.get('first_rtf')
            st.metric("First RTF",
                       f"{v:.2f}" if v is not None else "n/a")

        # Concurrency vs P95 chart
        conc_data = [s for s in stages if s.get('concurrency') and s.get('e2e_p95')]
        if len(conc_data) > 1:
            conc_df = pd.DataFrame(conc_data).sort_values('concurrency')
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=conc_df['concurrency'], y=conc_df['e2e_p95'],
                mode='lines+markers', name='P95 Latency',
            ))
            fig.add_hline(
                y=p95_target, line_dash='dash', line_color='red',
                annotation_text=f"Target ({p95_target}s)",
            )
            fig.update_layout(
                title="Concurrency vs P95 Latency",
                xaxis_title="Concurrency",
                yaxis_title="P95 Latency (s)",
                height=350,
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

    # Batch ETA calculator
    st.markdown("### Batch ETA Calculator")
    col1, col2 = st.columns(2)
    with col1:
        eta_files = st.number_input(
            "Number of files to process", min_value=0, value=0, step=1000,
            key="eta_files",
        )
    with col2:
        eta_hours = st.number_input(
            "Audio hours to process", min_value=0.0, value=0.0, step=10.0,
            key="eta_hours",
        )

    if eta_files or eta_hours:
        for run_id, stages in sorted(runs.items()):
            model = stages[0].get('model', 'unknown')
            cores = stages[0].get('cores', 0)
            cap = compute_capacity_metrics(stages, cores, p95_target)
            eta = compute_batch_eta(
                files_per_second=cap.get('best_requests_per_second'),
                total_files=int(eta_files) if eta_files else None,
                audio_hours_per_hour=cap.get('audio_hours_per_hour'),
                target_audio_hours=float(eta_hours) if eta_hours else None,
            )
            parts = [f"**{model} ({cores} cores):** "]
            if eta.get('eta_files_seconds'):
                parts.append(f"  {int(eta_files):,} files → {format_duration(eta['eta_files_seconds'])}")
            if eta.get('eta_audio_hours_seconds'):
                parts.append(f"  {eta_hours:.1f} audio hours → {format_duration(eta['eta_audio_hours_seconds'])}")
            st.markdown("\n".join(parts))

    # Terminal report button
    st.markdown("---")
    if st.button("Show Terminal Report"):
        for run_id, stages in sorted(runs.items()):
            model = stages[0].get('model', 'unknown')
            scenario = stages[0].get('scenario', 'unknown')
            cores = stages[0].get('cores', 0)
            report = format_enterprise_report(
                stages, cores, p95_target=p95_target,
                model=model, scenario=scenario, run_id=run_id,
            )
            st.code(report, language='text')


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

        #### 🎵 Audio Hours/Hour
        - **What it measures:** How many hours of audio are processed per wall-clock hour
        - **Example:** 10.0 h/h means 10 hours of audio processed every wall-clock hour (10x real-time)
        - **1.0 h/h** = Real-time processing
        - **> 1.0 h/h** = Faster than real-time ✅
        - **< 1.0 h/h** = Slower than real-time ⚠️
        - **Use case:** "How long to transcribe 1000 hours of audio?"

        #### 📁 Files/Hour
        - **What it measures:** Number of audio files processed per hour
        - **Example:** 15,840 files/hour = can process almost 16K files per hour
        - **Interpretation:** Higher = more files processed per unit time
        - **Use case:** "How many call recordings can we process overnight?"

        #### 📈 Speedup vs Sequential
        - **What it measures:** How much faster concurrent processing is vs sequential baseline
        - **Example:** 2.6x means concurrent-8 is 2.6 times faster than sequential
        - **Interpretation:** Higher = better benefit from concurrency
        - **Use case:** "Is it worth running with 8 concurrent requests instead of sequential?"

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

    # Get default path from audio-specific config (does not touch LLM path)
    default_results_dir = config.get_audio_results_directory()

    # Sidebar: Results directory
    st.sidebar.markdown("## 📁 Data Source")
    results_dir = st.sidebar.text_input(
        "Results Directory",
        value=default_results_dir,
        help="Path to audio-models results directory"
    )

    # Persist audio path separately (does not overwrite LLM results dir)
    if results_dir != default_results_dir:
        config.set_audio_results_directory(results_dir)

    # Sidebar: enterprise settings
    p95_target = st.sidebar.number_input(
        "P95 Latency Target (s)", min_value=0.1, value=2.0, step=0.5,
        help="Max acceptable P95 latency for online serving",
    )

    # Load data
    with st.spinner("Loading audio benchmark data..."):
        df = load_audio_data(results_dir)
        quality_df = load_quality_data(results_dir)

    if df.empty and quality_df.empty:
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

    has_perf = not df.empty

    if has_perf:
        st.success(f"✅ Loaded {len(df)} test results from {len(df['test_run_id'].unique())} test runs")
    else:
        st.info("No performance data found. Quality data is available.")

    # Filters (only when perf data exists)
    filtered_df = pd.DataFrame()
    if has_perf:
        filtered_df = render_filters(df)
        if filtered_df.empty:
            st.warning("No data matches the selected filters.")
            has_perf = False

    # Tabbed layout
    tab_perf, tab_quality, tab_capacity, tab_data = st.tabs(
        ["Performance", "Quality", "Capacity / Sizing", "Data"],
    )

    with tab_perf:
        if has_perf:
            render_overview_metrics(filtered_df)
            st.markdown("---")
            plot_total_time_comparison(filtered_df)
            st.markdown("---")
            plot_speedup_vs_sequential(filtered_df)
            st.markdown("---")
            plot_files_per_hour(filtered_df)
            st.markdown("---")
            plot_audio_throughput(filtered_df)
            st.markdown("---")
            plot_rtf(filtered_df)
            st.markdown("---")
            plot_latency_vs_audio_duration(filtered_df)
            st.markdown("---")
            plot_efficiency(filtered_df)
        else:
            st.info("No performance benchmark data available. "
                    "Run a throughput or latency scenario to populate this tab.")

    with tab_quality:
        render_quality_tab(quality_df, filtered_df)

    with tab_capacity:
        if has_perf:
            render_capacity_tab(filtered_df, p95_target)
        else:
            st.info("No performance data available for capacity analysis. "
                    "Run a throughput scenario to populate this tab.")

    with tab_data:
        if has_perf:
            render_data_table(filtered_df)
        else:
            st.info("No performance data available.")


if __name__ == "__main__":
    main()
