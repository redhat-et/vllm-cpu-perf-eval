"""vLLM Audio Performance Dashboard.

Audio-specific metrics for speech recognition (ASR) models.
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


def _model_label(df: pd.DataFrame) -> pd.Series:
    """Return a model label that includes core count when multiple core counts are present."""
    if df['cores'].nunique() > 1:
        return df['model_short'] + ' (' + df['cores'].astype(str) + 'c)'
    return df['model_short']


def _stage_sort_key(stages: pd.Series) -> pd.Series:
    """Map stage names to a tuple key for logical x-axis ordering.

    sequential → (0, 0), concurrent-N → (1, N), max-throughput → (2, 0).
    Avoids relying on the concurrency field, which may not order max-throughput
    correctly relative to the highest concurrent-N stage.
    """
    def _key(s: str) -> tuple:
        if s == 'sequential':
            return (0, 0)
        if s == 'max-throughput':
            return (2, 0)
        try:
            return (1, int(s.split('-')[-1]))
        except (ValueError, IndexError):
            return (1, 999)
    return stages.map(_key)


def _agg_for_bar(df: pd.DataFrame, y_col: str,
                 extra_mean: list | None = None) -> pd.DataFrame:
    """Reduce df to one row per (stage, model_label) before passing to px.bar.

    px.bar stacks every row that shares the same (x, color), so if multiple
    scenarios or test runs exist for the same model+cores the bars stack even
    with barmode='group'.  Averaging across them gives one clean bar per slot.
    """
    agg: dict = {
        y_col: 'mean',
        'concurrency': 'first',
        'cores': 'first',
    }
    for col in (extra_mean or []):
        if col in df.columns and col not in agg:
            agg[col] = 'mean'
    result = df.groupby(['stage', 'model_label'], as_index=False).agg(agg)
    return result.sort_values('stage', key=_stage_sort_key)


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
    """Render per-model × per-cores performance summary table."""
    if df.empty:
        return

    # One representative row per run (sequential stage preferred) to get
    # dataset metadata and file counts without double-counting stages.
    groups = []
    for _, grp in df.groupby(['test_run_id', 'model', 'scenario']):
        seq = grp[grp['stage'] == 'sequential']
        groups.append(seq if not seq.empty else grp.head(1))
    representative = pd.concat(groups)

    # Warn when runs used different file counts.
    run_file_counts = representative.groupby(
        ['model_short', 'cores', 'test_run_id']
    )['successful_requests'].first()
    unique_file_counts = run_file_counts.unique()
    if len(unique_file_counts) > 1:
        detail_lines = "  \n".join(
            f"- {'/'.join(str(v) for v in idx)}: **{n} files**"
            for idx, n in run_file_counts.items()
        )
        st.warning(
            "⚠️ **Runs used different numbers of input files** — normalized "
            "metrics (Files/Hour, RTF, Time per File) are still comparable, "
            "but raw totals are not.  \n" + detail_lines
        )

    # One-line dataset/format context.
    unique_datasets = df['dataset_name'].dropna().unique()
    dataset_str = (
        unique_datasets[0] if len(unique_datasets) == 1
        else "Mixed: " + ", ".join(str(d) for d in unique_datasets)
    )
    unique_formats = [
        str(f).upper() for f in df['audio_format'].dropna().unique()
        if str(f).lower() != 'unknown'
    ]
    unique_rates = df['audio_sample_rate'].dropna().unique()
    rate_str = (
        f"{int(unique_rates[0]/1000)}kHz" if len(unique_rates) == 1
        else "mixed sample rates"
    )
    format_str = "/".join(sorted(set(unique_formats))) or "unknown"
    st.caption(
        f"Dataset: **{dataset_str}** · Format: **{format_str}** "
        f"· Sample rate: **{rate_str}**"
    )

    st.markdown("### 📊 Performance Summary by Model & Core Count")

    # Build one row per (model_short, cores) with best-stage metrics.
    rows = []
    for (model, cores), grp in df.groupby(['model_short', 'cores']):
        # File count from the representative (sequential) stage.
        rep_rows = representative[
            (representative['model_short'] == model)
            & (representative['cores'] == cores)
        ]
        files_per_run = (
            int(rep_rows['successful_requests'].mean())
            if not rep_rows.empty else None
        )
        best_fph_idx = grp['requests_per_second'].idxmax()
        best_hh_idx = grp['audio_throughput'].idxmax()
        best_rtf_idx = grp['rtf_p95'].idxmin()
        rows.append({
            'Model': model,
            'Cores': int(cores),
            'Files / Run': files_per_run,
            'Best Files/Hour': int(grp.loc[best_fph_idx, 'requests_per_second'] * 3600),
            'Best Files/Hour Stage': grp.loc[best_fph_idx, 'stage'],
            'Best Audio h/h': round(grp.loc[best_hh_idx, 'audio_throughput'], 1),
            'Best Audio h/h Stage': grp.loc[best_hh_idx, 'stage'],
            'Best RTF P95': round(grp.loc[best_rtf_idx, 'rtf_p95'], 3),
            'Best RTF P95 Stage': grp.loc[best_rtf_idx, 'stage'],
            'Avg Success %': round(grp['success_rate'].mean(), 1),
        })

    summary = (
        pd.DataFrame(rows)
        .sort_values(['Model', 'Cores'])
        .reset_index(drop=True)
    )
    st.dataframe(summary, use_container_width=True, hide_index=True)


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

    # Calculate speedup for each model+cores+run combination.
    # Use _model_label so the label format stays consistent with all other charts.
    df_labeled = df.copy()
    df_labeled['model_label'] = _model_label(df_labeled)
    speedup_data = []
    for (model, cores, run_id), group_df in df_labeled.groupby(
        ['model_short', 'cores', 'test_run_id']
    ):
        sequential_rows = group_df[group_df['stage'] == 'sequential']
        if sequential_rows.empty:
            continue

        sequential_duration = sequential_rows['duration'].iloc[0]
        label = group_df['model_label'].iloc[0]

        for _, row in group_df.iterrows():
            speedup = (
                sequential_duration / row['duration']
                if row['duration'] > 0 else 0
            )
            speedup_data.append({
                'model_label': label,
                'cores': cores,
                'stage': row['stage'],
                'speedup': speedup,
                'concurrency': row['concurrency'],
            })

    if not speedup_data:
        st.warning("No sequential baseline found for speedup calculation")
        return

    # Aggregate to one row per (stage, model_label) — multiple scenarios or
    # test_run_ids with the same model+cores would otherwise stack in px.bar.
    speedup_df = (
        pd.DataFrame(speedup_data)
        .groupby(['stage', 'model_label', 'cores'], as_index=False)
        .agg({'speedup': 'mean', 'concurrency': 'first'})
        .sort_values('stage', key=_stage_sort_key)
    )

    fig = px.bar(
        speedup_df,
        x='stage',
        y='speedup',
        color='model_label',
        barmode='group',
        hover_data={'cores': True},
        labels={
            'speedup': 'Speedup (vs Sequential)',
            'stage': 'Test Stage',
            'model_label': 'Model',
            'cores': 'Cores',
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
    summary = speedup_df[
        ['model_label', 'cores', 'stage', 'speedup', 'concurrency']
    ].copy()
    summary = summary.rename(columns={
        'model_label': 'Model',
        'cores': 'Cores',
        'stage': 'Stage',
        'speedup': 'Speedup (x)',
        'concurrency': 'Concurrency',
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

    df_plot = df.copy()
    df_plot['model_label'] = _model_label(df_plot)
    df_agg = _agg_for_bar(df_plot, 'audio_throughput')

    fig = px.bar(
        df_agg,
        x='stage',
        y='audio_throughput',
        color='model_label',
        barmode='group',
        hover_data={'cores': True},
        labels={
            'audio_throughput': 'Audio Hours/Hour',
            'stage': 'Test Stage',
            'model_label': 'Model',
            'cores': 'Cores',
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

    df_plot = df.copy()
    df_plot['files_per_hour'] = df_plot['requests_per_second'] * 3600
    df_plot['model_label'] = _model_label(df_plot)
    df_agg = _agg_for_bar(df_plot, 'files_per_hour')

    fig = px.bar(
        df_agg,
        x='stage',
        y='files_per_hour',
        color='model_label',
        barmode='group',
        hover_data={'cores': True},
        labels={
            'files_per_hour': 'Files/Hour',
            'stage': 'Test Stage',
            'model_label': 'Model',
            'cores': 'Cores',
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

    # Aggregate to one row per (model_label, stage) before building plot_data.
    # Multiple scenarios/runs with the same model+cores would otherwise produce
    # duplicate (x, color) points that appear as a zigzag in the line chart.
    rtf_cols = {f'rtf_{p}': 'mean' for p in ['mean', 'p50', 'p95', 'p99']
                if f'rtf_{p}' in df.columns}
    df_agg = df.copy()
    df_agg['model_label'] = _model_label(df_agg)
    df_agg = (
        df_agg.groupby(['stage', 'model_label', 'cores'], as_index=False)
        .agg({'concurrency': 'first', **rtf_cols})
        .sort_values('stage', key=_stage_sort_key)
    )

    plot_data = []
    for _, row in df_agg.iterrows():
        for percentile in selected_percentiles:
            col = f'rtf_{percentile}'
            if col not in row:
                continue
            plot_data.append({
                'stage': row['stage'],
                'model_label': row['model_label'],
                'cores': row['cores'],
                'percentile': percentile_labels[percentile],
                'rtf': row[col],
            })

    plot_df = pd.DataFrame(plot_data)

    fig = px.line(
        plot_df,
        x='stage',
        y='rtf',
        color='model_label',
        line_dash='percentile',
        markers=True,
        hover_data={'cores': True},
        labels={
            'rtf': 'Real-Time Factor',
            'stage': 'Test Stage',
            'model_label': 'Model',
            'percentile': 'Percentile',
            'cores': 'Cores',
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

    df_plot = df.copy()
    df_plot['model_label'] = _model_label(df_plot)
    # Aggregate to one point per (model_label, cores, stage) so multiple
    # scenarios or runs don't produce overlapping points at the same coordinates.
    # Key on stage (not concurrency) — two stages can share the same concurrency
    # value (e.g. concurrent-8 and max-throughput at 8 workers).
    df_agg = (
        df_plot.groupby(['model_label', 'cores', 'stage'], as_index=False)
        .agg({'mean_audio_seconds': 'mean', 'e2e_mean': 'mean',
              'concurrency': 'first'})
    )

    fig = px.scatter(
        df_agg,
        x='mean_audio_seconds',
        y='e2e_mean',
        color='model_label',
        size='concurrency',
        hover_data={'cores': True},
        labels={
            'mean_audio_seconds': 'Audio Duration (seconds)',
            'e2e_mean': 'Mean Request Latency (seconds)',
            'model_label': 'Model',
            'concurrency': 'Concurrency',
            'cores': 'Cores',
        },
        title="Request Latency vs Audio Duration"
    )

    # Add diagonal line for RTF=1.0
    max_duration = df_agg['mean_audio_seconds'].max()
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
    """Plot time-per-file by stage, normalized for fair cross-run comparison."""
    st.markdown("### ⏰ Time per File by Stage")
    st.markdown("""
    **Seconds to process a single audio file** (lower = faster)

    This is normalized by the number of files processed so runs with different
    dataset sizes are directly comparable. Hover to see the total file count (N)
    for each bar.
    - Sequential: Files processed one-by-one (baseline)
    - Concurrent-N: Files processed with N concurrent requests
    - Max-throughput: Maximum concurrency for fastest total time
    """)

    df_plot = df.copy()
    df_plot['model_label'] = _model_label(df_plot)
    # Aggregate duration and N first, then derive seconds_per_file as
    # ratio-of-means rather than mean-of-ratios so the bar height is consistent
    # with the hover values when multiple runs are averaged into one slot.
    df_agg = _agg_for_bar(
        df_plot, 'duration',
        extra_mean=['successful_requests', 'requests_per_second'],
    )
    df_agg['seconds_per_file'] = (
        df_agg['duration'] / df_agg['successful_requests'].replace(0, float('nan'))
    )

    fig = px.bar(
        df_agg,
        x='stage',
        y='seconds_per_file',
        color='model_label',
        barmode='group',
        hover_data={
            'successful_requests': ':.0f',
            'duration': ':.1f',
            'cores': True,
        },
        labels={
            'seconds_per_file': 'Time per File (s)',
            'stage': 'Test Stage',
            'model_label': 'Model',
            'successful_requests': 'Files (N)',
            'duration': 'Total Time (s)',
            'cores': 'Cores',
        },
        title="Time per File by Stage (Lower = Faster)"
    )

    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)

    # Summary table — reuse df_agg so table and chart always show the same values.
    st.markdown("#### Summary: Files Processed and Total Time")
    summary = df_agg[
        ['model_label', 'cores', 'stage',
         'successful_requests', 'duration', 'seconds_per_file',
         'requests_per_second']
    ].copy()
    summary['files_per_hour'] = summary['requests_per_second'] * 3600
    summary = summary.rename(columns={
        'model_label': 'Model',
        'cores': 'Cores',
        'stage': 'Stage',
        'successful_requests': 'Files (N)',
        'duration': 'Total Time (s)',
        'seconds_per_file': 'Time/File (s)',
        'requests_per_second': 'Files/Second',
        'files_per_hour': 'Files/Hour',
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)


def plot_efficiency(df: pd.DataFrame):
    """Plot efficiency (audio throughput per core)."""
    st.markdown("### ⚡ Efficiency (Audio Throughput per Core)")

    df_plot = df.copy()
    df_plot['model_label'] = _model_label(df_plot)
    df_agg = _agg_for_bar(df_plot, 'efficiency')

    fig = px.bar(
        df_agg,
        x='stage',
        y='efficiency',
        color='model_label',
        barmode='group',
        hover_data={'cores': True},
        labels={
            'efficiency': 'Efficiency (audio_sec/wall_sec/core)',
            'stage': 'Test Stage',
            'model_label': 'Model',
            'cores': 'Cores',
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
            # Show which core counts are currently in view so charts are unambiguous.
            cores_in_view = sorted(filtered_df['cores'].unique())
            cores_str = ', '.join(str(c) for c in cores_in_view)
            if len(cores_in_view) == 1:
                st.info(
                    f"📌 All charts show results for **{cores_in_view[0]} cores**. "
                    f"Use the Core Count filter above to compare different core counts."
                )
            else:
                st.warning(
                    f"⚠️ **Multiple core counts in view: {cores_str} cores.** "
                    f"Legends include the core count (e.g. *model (32c)*) to "
                    f"distinguish runs. Use the Core Count filter to isolate one."
                )
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
