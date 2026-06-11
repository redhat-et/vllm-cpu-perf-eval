#!/usr/bin/env python3
"""
Offline Batch Benchmark Dashboard

Displays results from vLLM offline batch benchmarking (vllm bench throughput).
"""

import json
import sys
from pathlib import Path
from typing import Dict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path for config_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig  # noqa: E402


def get_use_case_units(use_case: str) -> Dict[str, str]:
    """
    Map use case to appropriate units for display.

    Returns dict with 'singular' and 'plural' forms.
    """
    use_case_lower = use_case.lower()

    if 'translation' in use_case_lower or '🌐' in use_case:
        return {'singular': 'doc', 'plural': 'docs'}
    elif 'classification' in use_case_lower or 'tagging' in use_case_lower or '🏷️' in use_case:
        return {'singular': 'item', 'plural': 'items'}
    elif 'summarization' in use_case_lower or '📝' in use_case:
        return {'singular': 'doc', 'plural': 'docs'}
    elif 'code' in use_case_lower or '💻' in use_case:
        return {'singular': 'function', 'plural': 'functions'}
    elif 'generation' in use_case_lower or 'dataset' in use_case_lower or '🎲' in use_case:
        return {'singular': 'example', 'plural': 'examples'}
    elif 'extraction' in use_case_lower or '🧬' in use_case:
        return {'singular': 'doc', 'plural': 'docs'}
    elif 'etl' in use_case_lower or 'pipeline' in use_case_lower or '🔄' in use_case:
        return {'singular': 'record', 'plural': 'records'}
    else:
        return {'singular': 'request', 'plural': 'requests'}


def infer_use_case(test_metadata: dict) -> str:
    """
    Infer the use case from test metadata parameters.

    Maps to the 7 use cases from run-offline-batch-suite.sh:
    1. Summarization (cnn_dailymail, 1000 prompts)
    2. Classification/Tagging (sharegpt, 1000 prompts, output=64)
    3. Translation (sharegpt, 500 prompts, output=1024)
    4. Entity Extraction (cnn_dailymail, 1000 prompts, output=128)
    5. Dataset Generation (random, 256→256 tokens, 5000 prompts)
    6. Code Generation (random, 512→512 tokens, 500 prompts)
    7. ETL Pipelines (sonnet, 500 prompts, variable cores)

    Args:
        test_metadata: Dictionary containing test configuration

    Returns:
        String describing the use case with emoji
    """
    config = test_metadata.get('configuration', {})
    dataset = config.get('dataset', '')
    num_prompts = config.get('num_prompts', 0)
    cores = config.get('cores', 0)
    dataset_config = config.get('dataset_config', {})
    output_len = dataset_config.get('output_len', 0)

    # CNN/DailyMail dataset cases
    if dataset == 'cnn_dailymail':
        # Summarization: cnn_dailymail, 1000 prompts
        if num_prompts == 1000 and (output_len == 0 or output_len >= 100):
            return "📝 Summarization"
        # Entity Extraction: cnn_dailymail, 1000 prompts, output=128
        elif num_prompts == 1000 and output_len > 0 and output_len <= 150:
            return "🧬 Entity Extraction"
        else:
            return "📝 Summarization"  # Default for cnn_dailymail

    # ShareGPT dataset cases
    if dataset == 'sharegpt':
        # Translation: sharegpt, 500 prompts, output=1024
        if num_prompts == 500 and output_len >= 900:
            return "🌐 Translation"
        # Classification/Tagging: sharegpt, 1000 prompts, output=64
        elif num_prompts == 1000 and output_len > 0 and output_len <= 100:
            return "🏷️ Classification/Tagging"
        # Fallback: short output = classification, long output = translation
        elif output_len > 0 and output_len <= 100:
            return "🏷️ Classification/Tagging"
        elif output_len > 900:
            return "🌐 Translation"
        else:
            return "🏷️ Classification/Tagging"  # Default for sharegpt

    # Sonnet dataset cases
    if dataset == 'sonnet':
        # ETL Pipelines: sonnet, 500 prompts, variable cores (8/16/32)
        if num_prompts == 500 and cores in [8, 16, 32]:
            return "🔄 ETL Pipelines"
        else:
            return "🔄 ETL Pipelines"  # Default for sonnet

    # Random dataset - infer from token lengths
    if dataset == 'random':
        input_len = dataset_config.get('input_len', 0)
        output_len = dataset_config.get('output_len', 0)

        # Dataset Generation: 256→256 tokens, 5000 prompts
        if input_len == 256 and output_len == 256 and num_prompts == 5000:
            return "🎲 Dataset Generation"

        # Code Generation: 512→512 tokens, 500 prompts
        elif input_len == 512 and output_len == 512 and num_prompts == 500:
            return "💻 Code Generation"

        # Fallback for random with pattern matching
        # Code Generation: moderate balanced
        elif 400 <= input_len <= 600 and 400 <= output_len <= 600 and num_prompts <= 1000:
            return "💻 Code Generation"

        # Dataset Generation: high volume
        elif num_prompts >= 5000:
            return "🎲 Dataset Generation"

    # Default fallback
    return "⚙️ General"


@st.cache_data
def load_benchmark_results(results_base_dir: str) -> pd.DataFrame:
    """
    Load all offline batch benchmark results from the results directory.

    Args:
        results_base_dir: Base directory containing benchmark results

    Returns:
        DataFrame with all benchmark results
    """
    results = []
    results_path = Path(results_base_dir)

    if not results_path.exists():
        st.error(f"Results directory not found: {results_base_dir}")
        return pd.DataFrame()

    # Walk through results directory looking for offline-batch results
    for model_dir in results_path.iterdir():
        if not model_dir.is_dir():
            continue

        for timestamp_dir in model_dir.iterdir():
            if not timestamp_dir.is_dir() or not timestamp_dir.name.startswith('offline-batch-'):
                continue

            for config_dir in timestamp_dir.iterdir():
                if not config_dir.is_dir():
                    continue

                # Look for results.json and test-metadata.json
                results_file = config_dir / 'results.json'
                metadata_file = config_dir / 'test-metadata.json'

                if results_file.exists() and metadata_file.exists():
                    try:
                        with open(results_file, 'r') as f:
                            result_data = json.load(f)
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)

                        # Merge results and metadata
                        combined = {
                            'model': metadata['model'],
                            'timestamp': metadata['timestamp'],
                            'test_run_id': metadata['test_run_id'],
                            'cores': metadata['configuration']['cores'],
                            'dataset': metadata['configuration']['dataset'],
                            'num_prompts': metadata['configuration']['num_prompts'],
                            'container_image': metadata['environment'].get('container_image', 'unknown'),
                            'vllm_version': metadata['environment'].get('vllm_version', 'unknown'),
                        }

                        # Add dataset-specific config
                        dataset_config = metadata['configuration'].get('dataset_config', {})
                        if 'input_len' in dataset_config:
                            combined['config_input_len'] = dataset_config['input_len']
                            combined['config_output_len'] = dataset_config['output_len']

                        # Add all metrics with 'metric_' prefix
                        metrics = result_data.get('metrics', {})
                        for metric_name, metric_value in metrics.items():
                            combined[f'metric_{metric_name}'] = metric_value

                        # Infer use case
                        combined['use_case'] = infer_use_case(metadata)

                        results.append(combined)

                    except Exception as e:
                        st.warning(f"Error loading {config_dir}: {e}")
                        continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    return df


def main():
    st.set_page_config(
        page_title="Offline Batch Benchmarks",
        page_icon="📦",
        layout="wide"
    )

    st.title("📦 Offline Batch Benchmarking")
    st.markdown("""
    Results from vLLM offline batch benchmarking using `vllm bench throughput`.
    This tests batch processing performance (like processing thousands of documents at once).
    """)

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")

        config = DashboardConfig()
        default_results_dir = str(Path(config.get_results_directory()) / "llm")

        results_dir_input = st.text_input(
            "Results Directory",
            value=default_results_dir,
            help="Path to offline batch results directory",
            key="results_dir_offline"
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("**Use Case Reference:**")

        # Use case configurations
        with st.expander("📋 Task Configurations", expanded=False):
            st.markdown("**Use Case Characteristics**")
            use_case_data = {
                "Use Case": ["📝 Summarization", "🏷️ Classification", "🌐 Translation",
                            "🧬 Entity Extraction", "🎲 Dataset Gen", "💻 Code Gen", "🔄 ETL"],
                "Dataset": ["cnn_dailymail", "sharegpt", "sharegpt", "cnn_dailymail", "random", "random", "sonnet"],
                "Output Tokens": ["~150", "64", "1024", "128", "256", "512", "~150"],
                "Unit": ["docs", "items", "docs", "docs", "examples", "functions", "records"]
            }
            use_case_df = pd.DataFrame(use_case_data)
            st.dataframe(
                use_case_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Use Case": st.column_config.TextColumn("Use Case", width="medium"),
                    "Dataset": st.column_config.TextColumn("Dataset", width="medium"),
                    "Output Tokens": st.column_config.TextColumn("Output", width="small"),
                    "Unit": st.column_config.TextColumn("Unit", width="small"),
                }
            )
            st.caption("Real datasets: cnn_dailymail (news), sharegpt (conversations), sonnet (baseline)")

    # Load all results
    df = load_benchmark_results(results_dir_input)

    if df.empty:
        st.warning("No benchmark results found. Run some benchmarks first!")
        st.code("""
# Run a benchmark:
cd automation/test-execution
ansible-playbook -i inventory/hosts.yml ansible/llm-benchmark-offline-batch.yml \\
  -e "test_model=RedHatAI/TinyLlama-1.1B-Chat-v1.0-16k-pruned2.4" \\
  -e "dataset_name=random" \\
  -e "num_prompts=100" \\
  -e "requested_cores=16" \\
  -e "input_len=512" \\
  -e "output_len=256"
        """)
        return

    st.success(f"Loaded {len(df)} benchmark results")

    # Show what container images and vLLM versions are in the results
    if 'container_image' in df.columns:
        unique_containers = df['container_image'].unique()
        unique_versions = df['vllm_version'].unique() if 'vllm_version' in df.columns else []

        if len(unique_containers) > 1 or len(unique_versions) > 1:
            st.warning(f"⚠️ **Mixed environments detected!** Results include {len(unique_containers)} container image(s) and {len(unique_versions)} vLLM version(s). Be careful when comparing.")
            with st.expander("View environment details"):
                for container in unique_containers:
                    count = len(df[df['container_image'] == container])
                    st.write(f"- **{container}**: {count} test(s)")
        else:
            container_short = unique_containers[0].split('/')[-1] if len(unique_containers) > 0 else 'unknown'
            version = unique_versions[0] if len(unique_versions) > 0 else 'unknown'
            st.info(f"🐳 **Environment**: {container_short} (vLLM {version})")

    # Visual Analysis Sections
    st.header("📊 Performance Analysis")

    # Add model short name
    df['model_short'] = df['model'].apply(lambda x: x.split('/')[-1])

    st.divider()

    # Section 1: Processing Capacity - MOST USEFUL FIRST
    st.subheader("1️⃣ Processing Capacity")
    st.markdown("**How many items can you process per hour?**")

    # Group all configs by use case, then show capacity
    use_cases_available = sorted(df['use_case'].unique().tolist())

    # If multiple use cases, let user select
    if len(use_cases_available) > 1:
        capacity_use_case = st.selectbox(
            "Select use case:",
            options=use_cases_available,
            key="capacity_use_case"
        )
    else:
        capacity_use_case = use_cases_available[0]
        st.info(f"Showing results for: **{capacity_use_case}**")

    df_capacity = df[df['use_case'] == capacity_use_case].copy()

    # Group by model and cores (average multiple runs)
    df_capacity_grouped = df_capacity.groupby(['model_short', 'cores']).agg({
        'metric_throughput_requests_per_sec': 'mean'
    }).reset_index()
    df_capacity_grouped['items_per_hour'] = df_capacity_grouped['metric_throughput_requests_per_sec'] * 3600
    df_capacity_grouped['config_label'] = (
        df_capacity_grouped['model_short'] + '\n' +
        df_capacity_grouped['cores'].astype(str) + ' cores'
    )
    df_capacity_grouped = df_capacity_grouped.sort_values('items_per_hour', ascending=False)

    units = get_use_case_units(capacity_use_case)

    fig_capacity = go.Figure()

    fig_capacity.add_trace(go.Bar(
        x=df_capacity_grouped['config_label'],
        y=df_capacity_grouped['items_per_hour'],
        text=df_capacity_grouped['items_per_hour'].round(0).astype(int),
        textposition='auto',
        marker_color='#2ca02c',
        hovertemplate='<b>%{x}</b><br>' +
                     f'{units["plural"].capitalize()}/hour: ' + '%{y:,.0f}<br>' +
                     '<extra></extra>'
    ))

    fig_capacity.update_layout(
        xaxis_title="Configuration",
        yaxis_title=f"{units['plural'].capitalize()} per Hour",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_capacity, use_container_width=True)

    st.info(f"💡 **Example**: To process 10,000 {units['plural']}/day, you need at least {int(10000/24):,} {units['plural']}/hour")

    st.divider()

    # Section 2: Processing Time Estimates
    st.subheader("2️⃣ Processing Time Estimates")
    st.markdown("**How long to process a batch?**")

    col1, col2 = st.columns(2)
    with col1:
        # If multiple use cases, let user select
        if len(use_cases_available) > 1:
            time_use_case = st.selectbox(
                "Use case:",
                options=use_cases_available,
                key="time_use_case"
            )
        else:
            time_use_case = use_cases_available[0]
            st.write(f"**Use case:** {time_use_case}")

    with col2:
        batch_size = st.selectbox(
            "Batch size:",
            options=[1000, 5000, 10000, 50000, 100000],
            index=2,
            key="time_batch_size"
        )

    df_time = df[df['use_case'] == time_use_case].copy()

    # Group by model and cores (average multiple runs)
    df_time_grouped = df_time.groupby(['model_short', 'cores']).agg({
        'metric_throughput_requests_per_sec': 'mean'
    }).reset_index()
    df_time_grouped['config_label'] = (
        df_time_grouped['model_short'] + '\n' +
        df_time_grouped['cores'].astype(str) + ' cores'
    )
    df_time_grouped['time_minutes'] = (batch_size / df_time_grouped['metric_throughput_requests_per_sec']) / 60
    df_time_grouped = df_time_grouped.sort_values('time_minutes')

    units = get_use_case_units(time_use_case)

    # Determine time unit
    max_time = df_time_grouped['time_minutes'].max()
    if max_time >= 60:
        df_time_grouped['time_display'] = df_time_grouped['time_minutes'] / 60
        time_unit = "hours"
        time_labels = [f"{t:.1f}h" for t in df_time_grouped['time_display']]
    else:
        df_time_grouped['time_display'] = df_time_grouped['time_minutes']
        time_unit = "minutes"
        time_labels = [f"{t:.1f}min" for t in df_time_grouped['time_display']]

    fig_time = go.Figure()

    fig_time.add_trace(go.Bar(
        y=df_time_grouped['config_label'],
        x=df_time_grouped['time_display'],
        orientation='h',
        text=time_labels,
        textposition='auto',
        marker_color='#ff7f0e',
        hovertemplate='<b>%{y}</b><br>' +
                     f'Time for {batch_size:,} {units["plural"]}: ' + '%{text}<br>' +
                     '<extra></extra>'
    ))

    fig_time.update_layout(
        xaxis_title=f"Processing Time ({time_unit})",
        yaxis_title="Configuration",
        height=max(300, len(df_time_grouped) * 40),
        showlegend=False
    )
    st.plotly_chart(fig_time, use_container_width=True)

    fastest = time_labels[0]
    slowest = time_labels[-1]
    st.success(f"💡 **Quick answer**: To process {batch_size:,} {units['plural']}, fastest takes **{fastest}**, slowest takes **{slowest}**")

    st.divider()

    # Section 3: Model Comparison (if multiple models)
    if df['model'].nunique() > 1:
        st.subheader("3️⃣ Model Comparison")
        st.markdown("**Compare different models on the same task**")

        # Let user select which config to compare models on
        col1, col2, col3 = st.columns(3)
        with col1:
            if len(use_cases_available) > 1:
                model_comp_use_case = st.selectbox(
                    "Use case:",
                    options=use_cases_available,
                    key="model_comp_use_case"
                )
            else:
                model_comp_use_case = use_cases_available[0]
                st.write(f"**Use case:** {model_comp_use_case}")

        with col2:
            available_cores = sorted(df[df['use_case'] == model_comp_use_case]['cores'].unique().tolist())
            if len(available_cores) > 1:
                model_comp_cores = st.selectbox("Core count:", options=available_cores, key="model_comp_cores")
            else:
                model_comp_cores = available_cores[0]
                st.write(f"**Cores:** {model_comp_cores}")

        with col3:
            available_prompts = sorted(df[(df['use_case'] == model_comp_use_case) & (df['cores'] == model_comp_cores)]['num_prompts'].unique().tolist())
            if len(available_prompts) > 1:
                model_comp_prompts = st.selectbox("Batch size:", options=available_prompts, key="model_comp_prompts")
            else:
                model_comp_prompts = available_prompts[0]
                st.write(f"**Batch size:** {model_comp_prompts}")

        df_model_comp = df[
            (df['use_case'] == model_comp_use_case) &
            (df['cores'] == model_comp_cores) &
            (df['num_prompts'] == model_comp_prompts)
        ].copy()

        # Group by model (average multiple runs)
        df_model_comp_grouped = df_model_comp.groupby('model_short').agg({
            'metric_throughput_total_tokens_per_sec': 'mean',
            'metric_throughput_requests_per_sec': 'mean'
        }).reset_index()
        df_model_comp_grouped = df_model_comp_grouped.sort_values('metric_throughput_total_tokens_per_sec', ascending=False)

        fig_model = go.Figure()

        fig_model.add_trace(go.Bar(
            x=df_model_comp_grouped['model_short'],
            y=df_model_comp_grouped['metric_throughput_total_tokens_per_sec'],
            text=df_model_comp_grouped['metric_throughput_total_tokens_per_sec'].round(0).astype(int),
            textposition='auto',
            marker_color='#1f77b4',
            hovertemplate='<b>%{x}</b><br>' +
                         'Throughput: %{y:,.0f} tokens/sec<br>' +
                         '<extra></extra>'
        ))

        fig_model.update_layout(
            xaxis_title="Model",
            yaxis_title="Throughput (tokens/sec)",
            height=400,
            showlegend=False
        )
        st.plotly_chart(fig_model, use_container_width=True)

        st.divider()

    # Section 4: CPU Core Scaling
    st.subheader("4️⃣ CPU Core Scaling")
    st.markdown("**How performance scales with CPU cores**")

    # Check if we have core variation in the data
    if df['cores'].nunique() > 1:
        col1, col2 = st.columns(2)
        with col1:
            if len(use_cases_available) > 1:
                core_scaling_use_case = st.selectbox(
                    "Use case:",
                    options=use_cases_available,
                    key="core_scaling_use_case"
                )
            else:
                core_scaling_use_case = use_cases_available[0]
                st.write(f"**Use case:** {core_scaling_use_case}")

        with col2:
            available_models = sorted(df[df['use_case'] == core_scaling_use_case]['model_short'].unique().tolist())
            if len(available_models) > 1:
                core_scaling_model = st.selectbox("Model:", options=available_models, key="core_scaling_model")
            else:
                core_scaling_model = available_models[0]
                st.write(f"**Model:** {core_scaling_model}")

        df_core_scaling = df[
            (df['use_case'] == core_scaling_use_case) &
            (df['model_short'] == core_scaling_model)
        ].copy()

        # Group by cores (average multiple runs)
        df_core_scaling_grouped = df_core_scaling.groupby('cores').agg({
            'metric_throughput_total_tokens_per_sec': 'mean',
            'metric_throughput_requests_per_sec': 'mean'
        }).reset_index().sort_values('cores')

        if len(df_core_scaling_grouped) > 1:
            fig_cores = go.Figure()

            fig_cores.add_trace(go.Scatter(
                x=df_core_scaling_grouped['cores'],
                y=df_core_scaling_grouped['metric_throughput_total_tokens_per_sec'],
                mode='lines+markers',
                line=dict(width=3, color='#d62728'),
                marker=dict(size=10),
                hovertemplate='<b>%{x} cores</b><br>' +
                             'Throughput: %{y:,.0f} tokens/sec<br>' +
                             '<extra></extra>'
            ))

            fig_cores.update_layout(
                xaxis_title="CPU Cores",
                yaxis_title="Throughput (tokens/sec)",
                height=400
            )
            st.plotly_chart(fig_cores, use_container_width=True)

            # Show efficiency metric
            df_core_scaling_grouped['efficiency'] = df_core_scaling_grouped['metric_throughput_total_tokens_per_sec'] / df_core_scaling_grouped['cores']
            best_efficiency_cores = df_core_scaling_grouped.loc[df_core_scaling_grouped['efficiency'].idxmax(), 'cores']
            best_efficiency_value = df_core_scaling_grouped['efficiency'].max()
            st.info(f"💡 **Best efficiency**: {best_efficiency_cores} cores gives {best_efficiency_value:.1f} tokens/sec per core")
        else:
            st.info("Need results with multiple core counts to show scaling. Try running the ETL Pipelines use case which tests 8, 16, and 32 cores.")
    else:
        st.info("Need results with multiple core counts to show scaling. Try running the ETL Pipelines use case which tests 8, 16, and 32 cores.")

    st.divider()

    # Section 5: Batch Size Scaling
    st.subheader("5️⃣ Batch Size Scaling")
    st.markdown("**How batch size affects throughput**")

    # Check if we have batch size variation
    if df['num_prompts'].nunique() > 1:
        col1, col2, col3 = st.columns(3)
        with col1:
            if len(use_cases_available) > 1:
                batch_scaling_use_case = st.selectbox(
                    "Use case:",
                    options=use_cases_available,
                    key="batch_scaling_use_case"
                )
            else:
                batch_scaling_use_case = use_cases_available[0]
                st.write(f"**Use case:** {batch_scaling_use_case}")

        with col2:
            available_models_batch = sorted(df[df['use_case'] == batch_scaling_use_case]['model_short'].unique().tolist())
            if len(available_models_batch) > 1:
                batch_scaling_model = st.selectbox("Model:", options=available_models_batch, key="batch_scaling_model")
            else:
                batch_scaling_model = available_models_batch[0]
                st.write(f"**Model:** {batch_scaling_model}")

        with col3:
            available_cores_batch = sorted(df[(df['use_case'] == batch_scaling_use_case) & (df['model_short'] == batch_scaling_model)]['cores'].unique().tolist())
            if len(available_cores_batch) > 1:
                batch_scaling_cores = st.selectbox("Core count:", options=available_cores_batch, key="batch_scaling_cores")
            else:
                batch_scaling_cores = available_cores_batch[0]
                st.write(f"**Cores:** {batch_scaling_cores}")

        df_batch_scaling = df[
            (df['use_case'] == batch_scaling_use_case) &
            (df['model_short'] == batch_scaling_model) &
            (df['cores'] == batch_scaling_cores)
        ].copy()

        # Group by batch size (average multiple runs)
        df_batch_scaling_grouped = df_batch_scaling.groupby('num_prompts').agg({
            'metric_throughput_total_tokens_per_sec': 'mean',
            'metric_throughput_requests_per_sec': 'mean'
        }).reset_index().sort_values('num_prompts')

        if len(df_batch_scaling_grouped) > 1:
            fig_batch = go.Figure()

            fig_batch.add_trace(go.Scatter(
                x=df_batch_scaling_grouped['num_prompts'],
                y=df_batch_scaling_grouped['metric_throughput_total_tokens_per_sec'],
                mode='lines+markers',
                line=dict(width=3, color='#9467bd'),
                marker=dict(size=10),
                hovertemplate='<b>Batch size: %{x}</b><br>' +
                             'Throughput: %{y:,.0f} tokens/sec<br>' +
                             '<extra></extra>'
            ))

            fig_batch.update_layout(
                xaxis_title="Batch Size (number of prompts)",
                yaxis_title="Throughput (tokens/sec)",
                height=400
            )
            st.plotly_chart(fig_batch, use_container_width=True)

            st.info("💡 Larger batch sizes typically improve throughput up to a point, then plateau or decrease due to memory/scheduling overhead")
        else:
            st.info("Need results with multiple batch sizes to show scaling")
    else:
        st.info("Need results with multiple batch sizes to show scaling")

    st.divider()

    # Section 6: Detailed Results Table
    with st.expander("📋 View All Results", expanded=False):
        # Build comprehensive results table
        results_table = df.copy()

        # Select columns for display
        display_cols = {
            'use_case': 'Use Case',
            'model_short': 'Model',
            'cores': 'Cores',
            'num_prompts': 'Batch Size',
            'metric_throughput_requests_per_sec': 'Req/sec',
            'metric_throughput_total_tokens_per_sec': 'Tokens/sec',
        }

        # Add optional columns if they exist
        if 'config_input_len' in results_table.columns:
            display_cols['config_input_len'] = 'Input Len'
            display_cols['config_output_len'] = 'Output Len'

        if 'metric_prefill_throughput_tokens_per_sec' in results_table.columns:
            display_cols['metric_prefill_throughput_tokens_per_sec'] = 'Prefill (tok/sec)'
            display_cols['metric_decode_throughput_tokens_per_sec'] = 'Decode (tok/sec)'

        # Add environment info
        if 'vllm_version' in results_table.columns:
            display_cols['vllm_version'] = 'vLLM Version'
        if 'container_image' in results_table.columns:
            # Show short version of container image
            results_table['container_short'] = results_table['container_image'].apply(
                lambda x: x.split('/')[-1] if isinstance(x, str) else x
            )
            display_cols['container_short'] = 'Container'

        # Filter to available columns
        available_display_cols = {k: v for k, v in display_cols.items() if k in results_table.columns}

        display_df = results_table[list(available_display_cols.keys())].copy()
        display_df.columns = list(available_display_cols.values())

        # Round numeric columns
        for col in display_df.columns:
            if display_df[col].dtype in ['float64', 'float32']:
                display_df[col] = display_df[col].round(2)

        st.dataframe(
            display_df.sort_values(['Use Case', 'Model', 'Cores', 'Batch Size']),
            use_container_width=True,
            hide_index=True
        )


if __name__ == "__main__":
    main()
