"""vLLM CPU Performance - Repeatability Analysis Dashboard.

Analyze benchmark repeatability using Coefficient of Variation (CV) metrics.
Shows which configurations provide stable, repeatable results.

Run: streamlit run Home.py
"""

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig
from repeatability_utils import (
    calculate_cv,
    get_repeatability_grade,
    get_grade_color,
    calculate_repeatability_metrics,
    format_metric_with_cv,
    get_repeatability_summary,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Dark mode friendly CSS
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_benchmark_runs(results_dir: str) -> tuple[pd.DataFrame, dict]:
    """Load benchmark results and calculate repeatability metrics.

    Returns:
        Tuple of (raw_data_df, repeatability_metrics_dict)
    """
    results_path = Path(results_dir)
    all_runs = []
    runs_by_config = defaultdict(list)

    if not results_path.exists():
        return pd.DataFrame(), {}

    # Load all benchmark runs
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

                # Extract key metrics
                row = {
                    'test_run_id': metadata.get('test_run_id', 'unknown'),
                    'platform': metadata.get('platform', 'unknown'),
                    'model': metadata.get('model', 'unknown'),
                    'model_short': metadata.get('model', 'unknown').split('/')[-1],
                    'workload': metadata.get('workload', 'unknown'),
                    'cores': metadata.get('core_count', 0),
                    'tensor_parallel': metadata.get('tensor_parallel', 1),
                    'vllm_version': metadata.get('vllm_version', 'unknown'),
                    'concurrency': concurrency,
                    'throughput_mean': metrics['tokens_per_second']['successful']['mean'],
                    'ttft_mean': metrics['time_to_first_token_ms']['successful']['mean'],
                    'ttft_p90': metrics['time_to_first_token_ms']['successful']['percentiles']['p90'],
                    'ttft_p95': metrics['time_to_first_token_ms']['successful']['percentiles']['p95'],
                    'tpot_mean': metrics['inter_token_latency_ms']['successful']['mean'],
                    'tpot_p90': metrics['inter_token_latency_ms']['successful']['percentiles']['p90'],
                    'tpot_p95': metrics['inter_token_latency_ms']['successful']['percentiles']['p95'],
                    'request_latency_mean': metrics['request_latency']['successful']['mean'],
                    'request_latency_p90': metrics['request_latency']['successful']['percentiles']['p90'],
                    'request_latency_p95': metrics['request_latency']['successful']['percentiles']['p95'],
                }

                all_runs.append(row)

                # Group by configuration for repeatability analysis
                config_key = (
                    row['platform'],
                    row['model'],
                    row['workload'],
                    row['cores'],
                    row['tensor_parallel'],
                    row['vllm_version'],
                    row['concurrency']
                )
                runs_by_config[config_key].append(row)

        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
            continue

    df = pd.DataFrame(all_runs)

    # Calculate repeatability metrics
    repeatability_data = []

    for config_key, runs in runs_by_config.items():
        if len(runs) < 2:
            continue

        platform, model, workload, cores, tp, vllm_ver, conc = config_key

        config_df = pd.DataFrame(runs)

        # Calculate CV for each metric
        metrics_to_analyze = [
            'throughput_mean',
            'ttft_mean', 'ttft_p90', 'ttft_p95',
            'tpot_mean', 'tpot_p90', 'tpot_p95',
            'request_latency_mean', 'request_latency_p90', 'request_latency_p95'
        ]

        result = {
            'platform': platform,
            'model_short': model.split('/')[-1],
            'model': model,
            'workload': workload,
            'cores': cores,
            'tensor_parallel': tp,
            'vllm_version': vllm_ver,
            'concurrency': conc,
            'n_runs': len(runs)
        }

        cvs = []
        for metric in metrics_to_analyze:
            if metric in config_df.columns:
                values = config_df[metric].dropna()
                if len(values) >= 2:
                    cv = calculate_cv(values)
                    grade = get_repeatability_grade(cv)
                    result[f'{metric}_cv'] = cv
                    result[f'{metric}_grade'] = grade
                    result[f'{metric}_value'] = values.mean()
                    if not np.isnan(cv):
                        cvs.append(cv)

        # Calculate overall average CV
        if cvs:
            result['avg_cv'] = np.mean(cvs)
            result['median_cv'] = np.median(cvs)
            result['max_cv'] = np.max(cvs)
            result['overall_grade'] = get_repeatability_grade(result['avg_cv'])
            repeatability_data.append(result)

    repeatability_df = pd.DataFrame(repeatability_data)

    return df, repeatability_df


def render_repeatability_overview(df: pd.DataFrame):
    """Render overview metrics."""
    st.markdown("## 📊 Repeatability Overview")

    if df.empty:
        st.warning("No repeatability data available (need at least 2 runs per configuration)")
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        n_configs = len(df)
        st.metric("Configurations Analyzed", n_configs)

    with col2:
        avg_cv = df['avg_cv'].mean()
        overall_grade = get_repeatability_grade(avg_cv)
        st.metric("Average CV", f"{avg_cv:.2f}%", help=f"Grade: {overall_grade}")

    with col3:
        excellent_count = (df['overall_grade'] == 'Excellent').sum()
        pct = (excellent_count / len(df) * 100) if len(df) > 0 else 0
        st.metric("Excellent Configs", f"{excellent_count} ({pct:.0f}%)")

    with col4:
        poor_count = (df['overall_grade'] == 'Poor').sum()
        pct = (poor_count / len(df) * 100) if len(df) > 0 else 0
        st.metric("Poor Configs", f"{poor_count} ({pct:.0f}%)",
                 delta_color="inverse" if poor_count > 0 else "off")


def render_grade_distribution(df: pd.DataFrame):
    """Render grade distribution pie chart."""
    st.markdown("### Grade Distribution")

    grade_counts = df['overall_grade'].value_counts()

    colors = {
        'Excellent': '#28a745',  # green
        'Good': '#17a2b8',       # blue
        'Acceptable': '#ffc107', # orange
        'Poor': '#dc3545'        # red
    }

    fig = go.Figure(data=[go.Pie(
        labels=grade_counts.index,
        values=grade_counts.values,
        marker=dict(colors=[colors.get(grade, '#gray') for grade in grade_counts.index]),
        textinfo='label+percent+value',
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>'
    )])

    fig.update_layout(
        title="Overall Repeatability Grade Distribution",
        showlegend=True,
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)


def render_cv_by_metric(df: pd.DataFrame):
    """Render CV comparison across metrics."""
    st.markdown("### CV by Metric Type")

    # Prepare data for plotting
    metric_groups = {
        'Throughput': ['throughput_mean'],
        'TTFT': ['ttft_mean', 'ttft_p90', 'ttft_p95'],
        'TPoT': ['tpot_mean', 'tpot_p90', 'tpot_p95'],
        'Request Latency': ['request_latency_mean', 'request_latency_p90', 'request_latency_p95']
    }

    cv_data = []
    for group_name, metrics in metric_groups.items():
        for metric in metrics:
            cv_col = f'{metric}_cv'
            if cv_col in df.columns:
                for _, row in df.iterrows():
                    if not np.isnan(row[cv_col]):
                        cv_data.append({
                            'Metric Group': group_name,
                            'Metric': metric.replace('_', ' ').title(),
                            'CV (%)': row[cv_col],
                            'Configuration': f"{row['cores']}c-{row['concurrency']}conc"
                        })

    if not cv_data:
        st.info("No CV data available")
        return

    cv_df = pd.DataFrame(cv_data)

    fig = px.box(
        cv_df,
        x='Metric Group',
        y='CV (%)',
        color='Metric Group',
        points='all',
        hover_data=['Metric', 'Configuration'],
        title='Coefficient of Variation Distribution by Metric Type'
    )

    # Add grade threshold lines
    fig.add_hline(y=1.0, line_dash="dash", line_color="green",
                  annotation_text="Excellent (<1%)")
    fig.add_hline(y=3.0, line_dash="dash", line_color="orange",
                  annotation_text="Good (<3%)")
    fig.add_hline(y=5.0, line_dash="dash", line_color="red",
                  annotation_text="Acceptable (<5%)")

    fig.update_layout(height=500, showlegend=False)

    st.plotly_chart(fig, use_container_width=True)


def render_configuration_table(df: pd.DataFrame, min_grade: str = None):
    """Render detailed configuration table."""
    st.markdown("### Configuration Details")

    # Filter by grade if specified
    if min_grade and min_grade != 'All':
        grade_order = ['Excellent', 'Good', 'Acceptable', 'Poor']
        min_idx = grade_order.index(min_grade)
        df = df[df['overall_grade'].apply(
            lambda g: grade_order.index(g) <= min_idx if g in grade_order else False
        )]

    if df.empty:
        st.info(f"No configurations match the filter: {min_grade}")
        return

    # Sort by average CV (best first)
    df = df.sort_values('avg_cv')

    # Create display dataframe
    display_cols = {
        'Platform': 'platform',
        'Model': 'model_short',
        'Cores': 'cores',
        'TP': 'tensor_parallel',
        'Conc': 'concurrency',
        'Runs': 'n_runs',
        'Avg CV (%)': 'avg_cv',
        'Grade': 'overall_grade',
        'Throughput CV': 'throughput_mean_cv',
        'TTFT CV': 'ttft_mean_cv',
        'TPoT CV': 'tpot_mean_cv',
    }

    display_df = pd.DataFrame()
    for display_name, col_name in display_cols.items():
        if col_name in df.columns:
            if 'cv' in col_name.lower() and col_name != 'overall_grade':
                # Format CV values
                display_df[display_name] = df[col_name].apply(
                    lambda x: f"{x:.2f}%" if not np.isnan(x) else 'N/A'
                )
            elif col_name == 'avg_cv':
                display_df[display_name] = df[col_name].apply(lambda x: f"{x:.2f}%")
            else:
                display_df[display_name] = df[col_name]

    # Color-code grades
    def highlight_grades(row):
        colors = []
        for col in row.index:
            if col == 'Grade':
                grade = row[col]
                if grade == 'Excellent':
                    colors.append('background-color: #d4edda')
                elif grade == 'Good':
                    colors.append('background-color: #d1ecf1')
                elif grade == 'Acceptable':
                    colors.append('background-color: #fff3cd')
                elif grade == 'Poor':
                    colors.append('background-color: #f8d7da')
                else:
                    colors.append('')
            else:
                colors.append('')
        return colors

    styled_df = display_df.style.apply(highlight_grades, axis=1)

    st.dataframe(styled_df, use_container_width=True, height=400)

    # Download button
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Repeatability Data (CSV)",
        data=csv,
        file_name="repeatability_analysis.csv",
        mime="text/csv"
    )


def main():
    """Main dashboard function."""
    st.title("📈 Benchmark Repeatability Analysis")
    st.markdown("**Analyze test consistency using Coefficient of Variation (CV)**")

    # Configuration
    config = DashboardConfig()
    results_dir = config.get_results_directory()

    st.sidebar.markdown("### Data Source")
    st.sidebar.text_input("Results Directory", value=str(results_dir), disabled=True)

    # Load data
    with st.spinner("Loading benchmark data..."):
        raw_df, repeatability_df = load_benchmark_runs(str(results_dir))

    if repeatability_df.empty:
        st.warning("""
        ⚠️ No repeatability data available.

        **Requirements:**
        - At least 2 runs of the same configuration
        - Matching: platform, model, workload, cores, tensor_parallel, vllm_version, concurrency

        Run the same benchmark multiple times to generate repeatability metrics.
        """)
        return

    # Show CV interpretation guide
    with st.expander("ℹ️ Understanding Coefficient of Variation (CV)", expanded=False):
        st.markdown("""
        **CV = (Standard Deviation / Mean) × 100%**

        CV measures the relative variability of repeated measurements:

        | CV Range | Grade | Meaning |
        |----------|-------|---------|
        | CV < 1% | **Excellent** 🟢 | Highly repeatable, ideal for regression testing |
        | CV 1-3% | **Good** 🔵 | Repeatable, suitable for performance comparisons |
        | CV 3-5% | **Acceptable** 🟡 | Moderate variance, acceptable for most use cases |
        | CV > 5% | **Poor** 🔴 | High variance, results may not be reliable |

        Lower CV values indicate better repeatability and more trustworthy benchmark results.
        """)

    # Overview
    render_repeatability_overview(repeatability_df)

    st.markdown("---")

    # Filters
    col1, col2 = st.columns([2, 1])

    with col1:
        render_grade_distribution(repeatability_df)

    with col2:
        st.markdown("### Filters")

        min_grade_filter = st.selectbox(
            "Minimum Grade",
            ['All', 'Excellent', 'Good', 'Acceptable', 'Poor'],
            help="Show only configurations with this grade or better"
        )

        min_runs = st.slider(
            "Minimum Runs",
            min_value=2,
            max_value=int(repeatability_df['n_runs'].max()),
            value=2,
            help="Minimum number of runs required"
        )

        # Apply filters
        filtered_df = repeatability_df[repeatability_df['n_runs'] >= min_runs]

        st.metric("Filtered Configs", len(filtered_df))

    st.markdown("---")

    # CV distribution
    render_cv_by_metric(filtered_df)

    st.markdown("---")

    # Configuration table
    render_configuration_table(
        filtered_df,
        min_grade=min_grade_filter if min_grade_filter != 'All' else None
    )


if __name__ == "__main__":
    main()
