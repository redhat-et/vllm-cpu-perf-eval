#!/usr/bin/env python3
"""
Offline Batch Benchmark Dashboard

Displays results from vLLM offline batch benchmarking
(vllm bench throughput). Capacity-planning focus: items/hr,
time estimates, core scaling, prefill/decode.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path for config_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable, no Streamlit dependency)
# ---------------------------------------------------------------------------

TECHNICAL_USE_CASES = frozenset({
    "kv_capacity",
    "context_scaling",
    "batch_scaling",
    "baseline",
    "input_scaling",
    "output_scaling",
    "quantization_comparison",
    "core_scaling",
})

USE_CASE_MAP = {
    'summarization': '📝 Summarization',
    'classification': '🏷️ Classification/Tagging',
    'translation': '🌐 Translation',
    'entity_extraction': '🧬 Entity Extraction',
    'dataset_generation': '🎲 Dataset Generation',
    'code_generation': '💻 Code Generation',
    'etl': '🔄 ETL Pipelines',
    'long_summarization': '📜 Long-Document Summarization',
    'rag_batch': '🔍 Batch RAG / Grounded Q&A',
    'shared_prefix': '📋 Shared-Prefix / Template Batch',
    'short_labeling': '⚡ Ultra-Short Labeling',
    'kv_capacity': '📊 KV-Cache Capacity',
    'context_scaling': '📏 Context Scaling',
    'baseline': '📐 Baseline Throughput',
    'batch_scaling': '📈 Batch Size Scaling',
    'input_scaling': '📥 Input Length Scaling',
    'output_scaling': '📤 Output Length Scaling',
    'core_scaling': '🔧 Core Scaling',
    'quantization_comparison': '⚖️ Quantization Comparison',
}

USE_CASE_REFERENCE = [
    {
        "Use Case": "📝 Summarization",
        "Dataset": "sharegpt",
        "Input": "variable",
        "Output": "variable",
        "Unit": "docs",
    },
    {
        "Use Case": "🏷️ Classification",
        "Dataset": "sharegpt",
        "Input": "variable",
        "Output": "64",
        "Unit": "items",
    },
    {
        "Use Case": "🌐 Translation",
        "Dataset": "sharegpt",
        "Input": "variable",
        "Output": "1024",
        "Unit": "docs",
    },
    {
        "Use Case": "🧬 Entity Extraction",
        "Dataset": "sharegpt",
        "Input": "variable",
        "Output": "128",
        "Unit": "docs",
    },
    {
        "Use Case": "🎲 Dataset Gen",
        "Dataset": "random",
        "Input": "256",
        "Output": "256",
        "Unit": "examples",
    },
    {
        "Use Case": "💻 Code Gen",
        "Dataset": "random",
        "Input": "512",
        "Output": "512",
        "Unit": "functions",
    },
    {
        "Use Case": "🔄 ETL",
        "Dataset": "sonnet",
        "Input": "~50",
        "Output": "~150",
        "Unit": "records",
    },
    {
        "Use Case": "📜 Long-Doc Summary",
        "Dataset": "random",
        "Input": "4096",
        "Output": "256",
        "Unit": "docs",
    },
    {
        "Use Case": "🔍 RAG Batch",
        "Dataset": "random",
        "Input": "2048",
        "Output": "128",
        "Unit": "queries",
    },
    {
        "Use Case": "📋 Shared-Prefix*",
        "Dataset": "random",
        "Input": "1024",
        "Output": "64",
        "Unit": "items",
    },
    {
        "Use Case": "⚡ Short Labeling",
        "Dataset": "sharegpt",
        "Input": "variable",
        "Output": "16",
        "Unit": "items",
    },
]


def compute_items_per_hour(requests_per_sec: float) -> float:
    """Convert req/s to items/hour."""
    return requests_per_sec * 3600.0


def compute_time_for_batch(requests_per_sec: float, batch_size: int) -> float:
    """Return seconds to process *batch_size* items at *requests_per_sec*.

    Returns float('inf') when rate is zero or negative.
    """
    if requests_per_sec <= 0:
        return float('inf')
    return batch_size / requests_per_sec


def is_technical_use_case(use_case_key: str) -> bool:
    """Return True if *use_case_key* (the raw slug, not the display name)
    belongs to a technical benchmark rather than a product-oriented use case.
    """
    return use_case_key in TECHNICAL_USE_CASES


def normalize_version(version: str) -> str:
    """Strip a single leading 'v'/'V' for consistent version comparison."""
    if not version:
        return 'unknown'
    if version[:1] in ('v', 'V') and len(version) > 1:
        return version[1:]
    return version


def format_duration(seconds: float) -> str:
    """Human-friendly duration string from seconds."""
    if seconds == float('inf') or seconds != seconds:  # inf or NaN
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} hr"


def get_use_case_units(use_case: str) -> Dict[str, str]:
    """
    Map use case to appropriate units for display.

    Returns dict with 'singular' and 'plural' forms.
    """
    use_case_lower = use_case.lower()

    if (
        ('long' in use_case_lower and 'summarization' in use_case_lower)
        or '📜' in use_case
    ):
        return {'singular': 'doc', 'plural': 'docs'}
    elif 'translation' in use_case_lower or '🌐' in use_case:
        return {'singular': 'doc', 'plural': 'docs'}
    elif (
        'labeling' in use_case_lower
        or ('short' in use_case_lower and 'label' in use_case_lower)
        or '⚡' in use_case
    ):
        return {'singular': 'item', 'plural': 'items'}
    elif (
        'classification' in use_case_lower
        or 'tagging' in use_case_lower
        or '🏷️' in use_case
    ):
        return {'singular': 'item', 'plural': 'items'}
    elif 'summarization' in use_case_lower or '📝' in use_case:
        return {'singular': 'doc', 'plural': 'docs'}
    elif (
        'rag' in use_case_lower
        or 'grounded' in use_case_lower
        or '🔍' in use_case
    ):
        return {'singular': 'query', 'plural': 'queries'}
    elif (
        'prefix' in use_case_lower
        or 'template' in use_case_lower
        or '📋' in use_case
    ):
        return {'singular': 'item', 'plural': 'items'}
    elif 'code' in use_case_lower or '💻' in use_case:
        return {'singular': 'function', 'plural': 'functions'}
    elif (
        'generation' in use_case_lower
        or 'dataset' in use_case_lower
        or '🎲' in use_case
    ):
        return {'singular': 'example', 'plural': 'examples'}
    elif 'extraction' in use_case_lower or '🧬' in use_case:
        return {'singular': 'doc', 'plural': 'docs'}
    elif (
        'etl' in use_case_lower
        or 'pipeline' in use_case_lower
        or '🔄' in use_case
    ):
        return {'singular': 'record', 'plural': 'records'}
    elif 'kv' in use_case_lower or 'capacity' in use_case_lower:
        return {'singular': 'request', 'plural': 'requests'}
    elif 'context' in use_case_lower and 'scaling' in use_case_lower:
        return {'singular': 'request', 'plural': 'requests'}
    else:
        return {'singular': 'request', 'plural': 'requests'}


def infer_use_case(test_metadata: dict) -> str:
    """
    Infer the use case from test metadata parameters.

    Maps to the 11 use cases from run-offline-batch-suite.sh:
    1. Summarization (sharegpt, 1000 prompts, no output_len set)
    2. Classification/Tagging (sharegpt, 1000 prompts, output=64)
    3. Translation (sharegpt, 500 prompts, output=1024)
    4. Entity Extraction (sharegpt, 1000 prompts, output=128)
    5. Dataset Generation (random, 256->256 tokens, 5000 prompts)
    6. Code Generation (random, 512->512 tokens, 500 prompts)
    7. ETL Pipelines (sonnet, 500 prompts, variable cores)
    8. Long-Document Summarization (random, 4096->256 tokens, 500 prompts)
    9. Batch RAG / Grounded Q&A (random, 2048->128 tokens, 500 prompts)
    10. Shared-Prefix / Template Batch (random, 1024->64 tokens, 1000 prompts)
    11. Ultra-Short Labeling (sharegpt, 2000 prompts, output=16)
    """
    config = test_metadata.get('configuration', {})
    dataset_config = config.get('dataset_config', {})

    # Check for explicit use_case field first
    use_case = dataset_config.get('use_case', '')
    if use_case:
        if use_case in USE_CASE_MAP:
            return USE_CASE_MAP[use_case]

    dataset = config.get('dataset', '')
    num_prompts = config.get('num_prompts', 0)
    cores = config.get('cores', 0)
    output_len = dataset_config.get('output_len', 0)

    # ShareGPT dataset cases
    if dataset == 'sharegpt':
        if output_len > 0 and output_len <= 20:
            return "⚡ Ultra-Short Labeling"
        elif num_prompts == 1000 and output_len > 0 and output_len <= 100:
            return "🏷️ Classification/Tagging"
        elif num_prompts == 1000 and output_len > 100 and output_len <= 150:
            return "🧬 Entity Extraction"
        elif num_prompts == 500 and output_len >= 900:
            return "🌐 Translation"
        elif num_prompts == 1000 and output_len == 0:
            return "📝 Summarization"
        elif output_len > 0 and output_len <= 100:
            return "🏷️ Classification/Tagging"
        elif output_len > 900:
            return "🌐 Translation"
        elif output_len > 100 and output_len <= 200:
            return "🧬 Entity Extraction"
        else:
            return "📝 Summarization"

    # Sonnet dataset cases
    if dataset == 'sonnet':
        if num_prompts == 500 and cores in [8, 16, 24, 32]:
            return "🔄 ETL Pipelines"
        else:
            return "🔄 ETL Pipelines"

    # Random dataset - infer from token lengths
    if dataset == 'random':
        input_len = dataset_config.get('input_len', 0)
        output_len = dataset_config.get('output_len', 0)

        if input_len == 256 and output_len == 256 and num_prompts == 5000:
            return "🎲 Dataset Generation"
        elif input_len == 512 and output_len == 512 and num_prompts == 500:
            return "💻 Code Generation"
        elif (
            input_len >= 512
            and output_len <= 64
            and output_len > 0
            and num_prompts >= 1000
        ):
            return "📋 Shared-Prefix / Template Batch"
        elif (
            input_len >= 1024
            and output_len <= 128
            and output_len > 0
            and num_prompts <= 500
        ):
            return "🔍 Batch RAG / Grounded Q&A"
        elif input_len >= 2048 and output_len <= 256 and output_len > 128:
            return "📜 Long-Document Summarization"
        elif (
            400 <= input_len <= 600
            and 400 <= output_len <= 600
            and num_prompts <= 1000
        ):
            return "💻 Code Generation"
        elif num_prompts >= 5000:
            return "🎲 Dataset Generation"

    return "⚙️ General"


def _get_use_case_slug(display_name: str) -> str:
    """Reverse-map display name to slug, or empty string."""
    _reverse = {v: k for k, v in USE_CASE_MAP.items()}
    return _reverse.get(display_name, '')


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_benchmark_results(results_base_dir: str) -> pd.DataFrame:
    """Load all offline batch benchmark results from the results directory."""
    results: List[dict] = []
    results_path = Path(results_base_dir)

    if not results_path.exists():
        st.error(f"Results directory not found: {results_base_dir}")
        return pd.DataFrame()

    for model_dir in results_path.iterdir():
        if not model_dir.is_dir():
            continue

        for timestamp_dir in model_dir.iterdir():
            if (
                not timestamp_dir.is_dir()
                or not timestamp_dir.name.startswith('offline-batch-')
            ):
                continue

            for config_dir in timestamp_dir.iterdir():
                if not config_dir.is_dir():
                    continue

                results_file = config_dir / 'results.json'
                metadata_file = config_dir / 'test-metadata.json'

                if results_file.exists() and metadata_file.exists():
                    try:
                        with open(results_file, 'r') as f:
                            result_data = json.load(f)
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)

                        combined = {
                            'model': metadata['model'],
                            'timestamp': metadata['timestamp'],
                            'test_run_id': metadata['test_run_id'],
                            'cores': metadata['configuration']['cores'],
                            'dataset': metadata['configuration']['dataset'],
                            'num_prompts': metadata['configuration'][
                                'num_prompts'
                            ],
                            'container_image': metadata['environment'].get(
                                'container_image', 'unknown'
                            ),
                            'vllm_version': normalize_version(
                                metadata['environment'].get(
                                    'vllm_version', 'unknown'
                                )
                            ),
                        }

                        dataset_config = metadata['configuration'].get(
                            'dataset_config', {}
                        )
                        if 'input_len' in dataset_config:
                            combined['config_input_len'] = dataset_config[
                                'input_len'
                            ]
                        if 'output_len' in dataset_config:
                            combined['config_output_len'] = dataset_config[
                                'output_len'
                            ]

                        # Store raw use_case slug for technical detection
                        combined['use_case_slug'] = dataset_config.get(
                            'use_case', ''
                        )

                        metrics = result_data.get('metrics', {})
                        for metric_name, metric_value in metrics.items():
                            combined[f'metric_{metric_name}'] = metric_value

                        combined['use_case'] = infer_use_case(metadata)

                        results.append(combined)

                    except Exception as e:
                        st.warning(f"Error loading {config_dir}: {e}")
                        continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _safe_metric(df: pd.DataFrame, col: str, default: float = 0.0):
    """Return column values with fallback to *default* when missing."""
    if col in df.columns:
        return df[col].fillna(default)
    return pd.Series([default] * len(df), index=df.index)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Offline Batch Benchmarks",
        page_icon="📦",
        layout="wide",
    )

    st.title("📦 Offline Batch Benchmarking")
    st.markdown(
        "Results from `vllm bench throughput` — capacity planning for "
        "batch processing workloads."
    )

    # ------------------------------------------------------------------
    # Sidebar — configuration + global filters
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("Configuration")

        config = DashboardConfig()
        default_results_dir = str(Path(config.get_results_directory()))

        results_dir_input = st.text_input(
            "Results Directory",
            value=default_results_dir,
            help="Path to offline batch results directory",
            key="results_dir_offline",
        )

        if st.button("🔄 Reload Data"):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("**Use Case Reference:**")

        with st.expander("📋 Task Configurations", expanded=False):
            ref_df = pd.DataFrame(USE_CASE_REFERENCE)
            st.dataframe(
                ref_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Use Case": st.column_config.TextColumn(
                        "Use Case", width="medium"
                    ),
                    "Dataset": st.column_config.TextColumn(
                        "Dataset", width="small"
                    ),
                    "Input": st.column_config.TextColumn(
                        "Input", width="small"
                    ),
                    "Output": st.column_config.TextColumn(
                        "Output", width="small"
                    ),
                    "Unit": st.column_config.TextColumn(
                        "Unit", width="small"
                    ),
                },
            )
            st.caption(
                "Datasets: sharegpt (conversations), random (synthetic), "
                "sonnet (baseline)"
            )
            st.caption(
                "*Shared-Prefix does **not** enable prefix caching "
                "(random prompts have no shared prefix)."
            )

    # Load data
    df = load_benchmark_results(results_dir_input)

    if df.empty:
        st.warning("No benchmark results found. Run some benchmarks first!")
        st.code(
            "# Run a benchmark:\n"
            "cd automation/test-execution\n"
            "ansible-playbook -i inventory/hosts.yml "
            "ansible/llm-benchmark-offline-batch.yml \\\n"
            '  -e "test_model=RedHatAI/'
            'TinyLlama-1.1B-Chat-v1.0-pruned2.4" \\\n'
            '  -e "dataset_name=random" \\\n'
            '  -e "num_prompts=100" \\\n'
            '  -e "requested_cores=16" \\\n'
            '  -e "input_len=512" \\\n'
            '  -e "output_len=256"',
        )
        return

    st.success(f"Loaded {len(df)} benchmark results")

    # Short model names
    df['model_short'] = df['model'].apply(lambda x: x.split('/')[-1])

    # ------------------------------------------------------------------
    # Global sidebar filters (after data is loaded so we know the options)
    # ------------------------------------------------------------------
    with st.sidebar:
        st.markdown("---")
        st.header("Filters")

        all_use_cases = sorted(df['use_case'].unique().tolist())
        selected_use_cases = st.multiselect(
            "Use Case",
            options=all_use_cases,
            default=all_use_cases,
            key="global_use_case",
        )
        if not selected_use_cases:
            selected_use_cases = all_use_cases

        all_models = sorted(df['model_short'].unique().tolist())
        selected_models = st.multiselect(
            "Model",
            options=all_models,
            default=all_models,
            key="global_model",
        )
        if not selected_models:
            selected_models = all_models

        all_cores = sorted(df['cores'].unique().tolist())
        selected_cores = st.multiselect(
            "Cores",
            options=all_cores,
            default=all_cores,
            key="global_cores",
        )
        if not selected_cores:
            selected_cores = all_cores

        # Optional container / version filter when mixed
        if df['vllm_version'].nunique() > 1:
            all_versions = sorted(df['vllm_version'].unique().tolist())
            selected_versions = st.multiselect(
                "vLLM Version",
                options=all_versions,
                default=all_versions,
                key="global_version",
            )
            if not selected_versions:
                selected_versions = all_versions
        else:
            selected_versions = df['vllm_version'].unique().tolist()

    # Apply global filters
    df_filtered = df[
        (df['use_case'].isin(selected_use_cases))
        & (df['model_short'].isin(selected_models))
        & (df['cores'].isin(selected_cores))
        & (df['vllm_version'].isin(selected_versions))
    ].copy()

    if df_filtered.empty:
        st.warning(
            "No results match the current filters. "
            "Adjust filters in the sidebar."
        )
        return

    # Environment banner
    if 'container_image' in df_filtered.columns:
        unique_containers = df_filtered['container_image'].unique()
        unique_versions = (
            df_filtered['vllm_version'].unique()
            if 'vllm_version' in df_filtered.columns
            else []
        )

        if len(unique_containers) > 1 or len(unique_versions) > 1:
            st.warning(
                f"**Mixed environments** — "
                f"{len(unique_containers)} container image(s), "
                f"{len(unique_versions)} vLLM version(s). "
                "Compare with care."
            )
            with st.expander("View environment details"):
                for container in unique_containers:
                    count = len(
                        df_filtered[
                            df_filtered['container_image'] == container
                        ]
                    )
                    st.write(f"- **{container}**: {count} test(s)")
        else:
            container_short = (
                unique_containers[0].split('/')[-1]
                if len(unique_containers) > 0
                else 'unknown'
            )
            version = (
                unique_versions[0] if len(unique_versions) > 0 else 'unknown'
            )
            st.info(f"🐳 **Environment**: {container_short} (vLLM {version})")

    # Separate product vs technical use cases in the filtered data
    df_filtered['_is_technical'] = df_filtered['use_case_slug'].apply(
        is_technical_use_case
    )
    df_product = df_filtered[~df_filtered['_is_technical']].copy()
    df_technical = df_filtered[df_filtered['_is_technical']].copy()

    # ==================================================================
    # PRODUCT USE-CASE SECTIONS
    # ==================================================================
    st.header("📊 Performance Analysis")

    use_cases_available = sorted(
        df_product['use_case'].unique().tolist()
    ) if not df_product.empty else []

    # ---- Section 1: Processing Capacity ----
    st.divider()
    st.subheader("1️⃣ Processing Capacity")
    st.markdown("**How many items can you process per hour?**")

    if use_cases_available:
        capacity_use_case = st.selectbox(
            "Select use case:",
            options=use_cases_available,
            key="capacity_use_case",
        )

        df_cap = df_product[
            df_product['use_case'] == capacity_use_case
        ].copy()

        df_cap_g = (
            df_cap.groupby(['model_short', 'cores'])
            .agg({'metric_throughput_requests_per_sec': 'mean'})
            .reset_index()
        )
        df_cap_g['items_per_hour'] = df_cap_g[
            'metric_throughput_requests_per_sec'
        ].apply(compute_items_per_hour)
        df_cap_g['config_label'] = (
            df_cap_g['model_short']
            + '\n'
            + df_cap_g['cores'].astype(str)
            + ' cores'
        )
        df_cap_g = df_cap_g.sort_values('items_per_hour', ascending=False)

        units = get_use_case_units(capacity_use_case)

        fig_cap = go.Figure()
        fig_cap.add_trace(
            go.Bar(
                x=df_cap_g['config_label'],
                y=df_cap_g['items_per_hour'],
                text=df_cap_g['items_per_hour'].round(0).astype(int),
                textposition='auto',
                marker_color='#2ca02c',
                hovertemplate=(
                    '<b>%{x}</b><br>'
                    + f'{units["plural"].capitalize()}/hour: '
                    + '%{y:,.0f}<br><extra></extra>'
                ),
            )
        )
        fig_cap.update_layout(
            xaxis_title="Configuration",
            yaxis_title=f"{units['plural'].capitalize()} per Hour",
            height=400,
            showlegend=False,
        )
        st.plotly_chart(fig_cap, use_container_width=True)

        # Capacity tip — time for 10k items at best config
        best_rps = df_cap_g['metric_throughput_requests_per_sec'].max()
        if best_rps > 0:
            secs_10k = compute_time_for_batch(best_rps, 10_000)
            st.info(
                f"💡 At the best configuration above, 10,000 "
                f"{units['plural']} takes ~**{format_duration(secs_10k)}**."
            )
    else:
        st.info("No product use-case results match the current filters.")

    # ---- Section 2: Processing Time Estimates ----
    st.divider()
    st.subheader("2️⃣ Processing Time Estimates")
    st.markdown("**How long to process a batch?**")

    if use_cases_available:
        col1, col2 = st.columns(2)
        with col1:
            time_use_case = st.selectbox(
                "Use case:",
                options=use_cases_available,
                key="time_use_case",
            )
        with col2:
            batch_size = st.selectbox(
                "Batch size:",
                options=[1000, 5000, 10000, 50000, 100000],
                index=2,
                key="time_batch_size",
            )

        df_time = df_product[
            df_product['use_case'] == time_use_case
        ].copy()
        df_time_g = (
            df_time.groupby(['model_short', 'cores'])
            .agg({'metric_throughput_requests_per_sec': 'mean'})
            .reset_index()
        )
        df_time_g['config_label'] = (
            df_time_g['model_short']
            + '\n'
            + df_time_g['cores'].astype(str)
            + ' cores'
        )
        df_time_g['time_sec'] = df_time_g[
            'metric_throughput_requests_per_sec'
        ].apply(lambda r: compute_time_for_batch(r, batch_size))
        df_time_g['time_minutes'] = df_time_g['time_sec'] / 60.0
        df_time_g = df_time_g[df_time_g['time_sec'] < float('inf')]
        df_time_g = df_time_g.sort_values('time_minutes')

        if not df_time_g.empty:
            units = get_use_case_units(time_use_case)

            max_time = df_time_g['time_minutes'].max()
            if max_time >= 60:
                df_time_g['time_display'] = df_time_g['time_minutes'] / 60
                time_unit = "hours"
                time_labels = [
                    f"{t:.1f}h" for t in df_time_g['time_display']
                ]
            else:
                df_time_g['time_display'] = df_time_g['time_minutes']
                time_unit = "minutes"
                time_labels = [
                    f"{t:.1f}min" for t in df_time_g['time_display']
                ]

            fig_time = go.Figure()
            fig_time.add_trace(
                go.Bar(
                    y=df_time_g['config_label'],
                    x=df_time_g['time_display'],
                    orientation='h',
                    text=time_labels,
                    textposition='auto',
                    marker_color='#ff7f0e',
                    hovertemplate=(
                        '<b>%{y}</b><br>'
                        + f'Time for {batch_size:,} {units["plural"]}: '
                        + '%{text}<br><extra></extra>'
                    ),
                )
            )
            fig_time.update_layout(
                xaxis_title=f"Processing Time ({time_unit})",
                yaxis_title="Configuration",
                height=max(300, len(df_time_g) * 40),
                showlegend=False,
            )
            st.plotly_chart(fig_time, use_container_width=True)

            fastest = time_labels[0]
            slowest = time_labels[-1]
            st.success(
                f"💡 To process {batch_size:,} {units['plural']}, "
                f"fastest: **{fastest}**, slowest: **{slowest}**"
            )
        else:
            st.info("No throughput data available for time estimates.")
    else:
        st.info("No product use-case results match the current filters.")

    # ---- Section 3: Prefill vs Decode ----
    st.divider()
    st.subheader("3️⃣ Prefill vs Decode Throughput")
    st.markdown(
        "**Where is the bottleneck — prompt processing (prefill) "
        "or token generation (decode)?**"
    )

    prefill_col = 'metric_prefill_throughput_tokens_per_sec'
    decode_col = 'metric_decode_throughput_tokens_per_sec'
    has_prefill_data = (
        prefill_col in df_product.columns
        and (df_product[prefill_col].fillna(0) > 0).any()
    )

    if has_prefill_data and use_cases_available:
        pd_use_case = st.selectbox(
            "Use case:",
            options=use_cases_available,
            key="prefill_decode_use_case",
        )

        df_pd = df_product[df_product['use_case'] == pd_use_case].copy()
        df_pd_g = (
            df_pd.groupby(['model_short', 'cores'])
            .agg({
                prefill_col: 'mean',
                decode_col: 'mean',
            })
            .reset_index()
        )
        df_pd_g = df_pd_g[
            (df_pd_g[prefill_col].fillna(0) > 0)
            | (df_pd_g[decode_col].fillna(0) > 0)
        ]

        if not df_pd_g.empty:
            df_pd_g['config_label'] = (
                df_pd_g['model_short']
                + '\n'
                + df_pd_g['cores'].astype(str)
                + ' cores'
            )

            fig_pd = go.Figure()
            fig_pd.add_trace(
                go.Bar(
                    name='Prefill (prompt processing)',
                    x=df_pd_g['config_label'],
                    y=df_pd_g[prefill_col].fillna(0),
                    marker_color='#1f77b4',
                )
            )
            fig_pd.add_trace(
                go.Bar(
                    name='Decode (token generation)',
                    x=df_pd_g['config_label'],
                    y=df_pd_g[decode_col].fillna(0),
                    marker_color='#ff7f0e',
                )
            )
            fig_pd.update_layout(
                barmode='group',
                xaxis_title="Configuration",
                yaxis_title="Throughput (tokens/sec)",
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_pd, use_container_width=True)

            st.caption(
                "**Prefill** = processing the input prompt (higher is "
                "better for long-input workloads). "
                "**Decode** = generating output tokens (higher is better "
                "for long-output workloads). "
                "When prefill >> decode, generation is the bottleneck."
            )
        else:
            st.info(
                "No prefill/decode data for this use case. "
                "These metrics come from vLLM engine streaming logs."
            )
    else:
        st.info(
            "Prefill/decode metrics not available in current results. "
            "These are extracted from vLLM engine streaming logs during "
            "benchmarking."
        )

    # ---- Section 4: Core Scaling ----
    st.divider()
    st.subheader("4️⃣ CPU Core Scaling")
    st.markdown("**How performance scales with CPU cores**")

    if use_cases_available and len(selected_cores) > 1:
        col1, col2 = st.columns(2)
        with col1:
            cs_use_case = st.selectbox(
                "Use case:",
                options=use_cases_available,
                key="core_scaling_use_case",
            )
        with col2:
            cs_models = sorted(
                df_product[df_product['use_case'] == cs_use_case][
                    'model_short'
                ]
                .unique()
                .tolist()
            )
            cs_model = st.selectbox(
                "Model:", options=cs_models, key="core_scaling_model"
            )

        df_cs = df_product[
            (df_product['use_case'] == cs_use_case)
            & (df_product['model_short'] == cs_model)
        ].copy()

        df_cs_g = (
            df_cs.groupby('cores')
            .agg({
                'metric_throughput_total_tokens_per_sec': 'mean',
                'metric_throughput_requests_per_sec': 'mean',
            })
            .reset_index()
            .sort_values('cores')
        )

        if len(df_cs_g) > 1:
            cs_units = get_use_case_units(cs_use_case)
            df_cs_g['items_per_hour'] = df_cs_g[
                'metric_throughput_requests_per_sec'
            ].apply(compute_items_per_hour)
            df_cs_g['tok_per_core'] = (
                df_cs_g['metric_throughput_total_tokens_per_sec']
                / df_cs_g['cores']
            )

            fig_cs = go.Figure()

            # Primary: items/hr
            fig_cs.add_trace(
                go.Scatter(
                    x=df_cs_g['cores'],
                    y=df_cs_g['items_per_hour'],
                    mode='lines+markers',
                    name=f'{cs_units["plural"].capitalize()}/hr',
                    line=dict(width=3, color='#d62728'),
                    marker=dict(size=10),
                    hovertemplate=(
                        '<b>%{x} cores</b><br>'
                        + f'{cs_units["plural"].capitalize()}/hr: '
                        + '%{y:,.0f}<br><extra></extra>'
                    ),
                )
            )

            # Secondary: tokens/sec/core efficiency
            fig_cs.add_trace(
                go.Scatter(
                    x=df_cs_g['cores'],
                    y=df_cs_g['tok_per_core'],
                    mode='lines+markers',
                    name='Tokens/sec/core',
                    line=dict(width=2, dash='dot', color='#9467bd'),
                    marker=dict(size=8),
                    yaxis='y2',
                    hovertemplate=(
                        '<b>%{x} cores</b><br>'
                        'Tokens/sec/core: %{y:.1f}<br><extra></extra>'
                    ),
                )
            )

            fig_cs.update_layout(
                xaxis_title="CPU Cores",
                yaxis_title=f"{cs_units['plural'].capitalize()}/hr",
                yaxis2=dict(
                    title="Tokens/sec/core",
                    overlaying='y',
                    side='right',
                ),
                height=400,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig_cs, use_container_width=True)

            # Best efficiency insight
            best_eff_idx = df_cs_g['tok_per_core'].idxmax()
            best_eff_cores = df_cs_g.loc[best_eff_idx, 'cores']
            best_eff_val = df_cs_g.loc[best_eff_idx, 'tok_per_core']
            best_eff_iph = df_cs_g.loc[best_eff_idx, 'items_per_hour']
            st.info(
                f"💡 **Best efficiency**: {best_eff_cores} cores — "
                f"{best_eff_val:.1f} tokens/sec/core "
                f"({best_eff_iph:,.0f} {cs_units['plural']}/hr)"
            )
        else:
            st.info(
                "Need results with multiple core counts to show scaling. "
                "The suite tests 8, 16, 24, 32 cores."
            )
    elif len(selected_cores) <= 1:
        st.info(
            "Need results with multiple core counts to show scaling. "
            "The suite tests 8, 16, 24, 32 cores."
        )
    else:
        st.info("No product use-case results match the current filters.")

    # ---- Section 5: Model Comparison ----
    if df_product['model'].nunique() > 1 and use_cases_available:
        st.divider()
        st.subheader("5️⃣ Model Comparison")
        st.markdown("**Compare models on the same task (by capacity)**")

        col1, col2 = st.columns(2)
        with col1:
            mc_use_case = st.selectbox(
                "Use case:",
                options=use_cases_available,
                key="model_comp_use_case",
            )
        with col2:
            mc_cores_opts = sorted(
                df_product[df_product['use_case'] == mc_use_case]['cores']
                .unique()
                .tolist()
            )
            if len(mc_cores_opts) > 1:
                mc_cores = st.selectbox(
                    "Core count:",
                    options=mc_cores_opts,
                    key="model_comp_cores",
                )
            else:
                mc_cores = mc_cores_opts[0] if mc_cores_opts else None
                if mc_cores is not None:
                    st.write(f"**Cores:** {mc_cores}")

        if mc_cores is not None:
            df_mc = df_product[
                (df_product['use_case'] == mc_use_case)
                & (df_product['cores'] == mc_cores)
            ].copy()

            agg_dict = {
                'metric_throughput_requests_per_sec': 'mean',
                'metric_throughput_total_tokens_per_sec': 'mean',
            }

            df_mc_g = (
                df_mc.groupby('model_short')
                .agg(agg_dict)
                .reset_index()
            )
            mc_units = get_use_case_units(mc_use_case)
            df_mc_g['items_per_hour'] = df_mc_g[
                'metric_throughput_requests_per_sec'
            ].apply(compute_items_per_hour)
            df_mc_g = df_mc_g.sort_values(
                'items_per_hour', ascending=False
            )

            fig_mc = go.Figure()

            fig_mc.add_trace(
                go.Bar(
                    x=df_mc_g['model_short'],
                    y=df_mc_g['items_per_hour'],
                    text=df_mc_g['items_per_hour'].round(0).astype(int),
                    textposition='auto',
                    marker_color='#1f77b4',
                    hovertemplate=(
                        '<b>%{x}</b><br>'
                        + f'{mc_units["plural"].capitalize()}/hr: '
                        + '%{y:,.0f}<br><extra></extra>'
                    ),
                )
            )

            fig_mc.update_layout(
                xaxis_title="Model",
                yaxis_title=(
                    f"{mc_units['plural'].capitalize()}/hr "
                    f"({mc_cores} cores)"
                ),
                height=400,
                showlegend=False,
            )
            st.plotly_chart(fig_mc, use_container_width=True)

            # Secondary: tokens/sec for reference
            with st.expander("Tokens/sec comparison"):
                fig_mc_tok = go.Figure()
                fig_mc_tok.add_trace(
                    go.Bar(
                        x=df_mc_g['model_short'],
                        y=df_mc_g[
                            'metric_throughput_total_tokens_per_sec'
                        ],
                        text=df_mc_g[
                            'metric_throughput_total_tokens_per_sec'
                        ]
                        .round(0)
                        .astype(int),
                        textposition='auto',
                        marker_color='#17becf',
                    )
                )
                fig_mc_tok.update_layout(
                    xaxis_title="Model",
                    yaxis_title="Throughput (tokens/sec)",
                    height=350,
                    showlegend=False,
                )
                st.plotly_chart(fig_mc_tok, use_container_width=True)

    # ==================================================================
    # TECHNICAL BENCHMARKS
    # ==================================================================
    if not df_technical.empty:
        st.divider()
        st.header("🔬 Technical Benchmarks")

        tech_use_cases = sorted(df_technical['use_case'].unique().tolist())

        # ---- KV-Cache Capacity ----
        kv_label = '📊 KV-Cache Capacity'
        if kv_label in tech_use_cases:
            st.subheader("KV-Cache Capacity")
            st.markdown(
                "**How large a batch before KV-cache saturation?**"
            )

            df_kv = df_technical[
                df_technical['use_case'] == kv_label
            ].copy()
            kv_models = sorted(
                df_kv['model_short'].unique().tolist()
            )
            kv_model = st.selectbox(
                "Model:", options=kv_models, key="kv_model"
            )
            df_kv = df_kv[df_kv['model_short'] == kv_model]

            kv_cache_col = 'metric_max_kv_cache_usage_percent'
            has_kv = (
                kv_cache_col in df_kv.columns
                and (df_kv[kv_cache_col].fillna(0) > 0).any()
            )

            df_kv_g = (
                df_kv.groupby('num_prompts')
                .agg({
                    'metric_throughput_requests_per_sec': 'mean',
                    'metric_throughput_total_tokens_per_sec': 'mean',
                    **(
                        {kv_cache_col: 'mean'} if has_kv else {}
                    ),
                })
                .reset_index()
                .sort_values('num_prompts')
            )

            if len(df_kv_g) > 1:
                fig_kv = go.Figure()

                if has_kv:
                    fig_kv.add_trace(
                        go.Scatter(
                            x=df_kv_g['num_prompts'],
                            y=df_kv_g[kv_cache_col],
                            mode='lines+markers',
                            name='KV Cache Usage %',
                            line=dict(width=3, color='#d62728'),
                            marker=dict(size=10),
                            hovertemplate=(
                                '<b>Batch: %{x}</b><br>'
                                'KV Cache: %{y:.1f}%<br>'
                                '<extra></extra>'
                            ),
                        )
                    )
                    fig_kv.update_layout(
                        yaxis_title="KV Cache Usage (%)",
                    )

                fig_kv.add_trace(
                    go.Scatter(
                        x=df_kv_g['num_prompts'],
                        y=df_kv_g[
                            'metric_throughput_total_tokens_per_sec'
                        ],
                        mode='lines+markers',
                        name='Throughput (tok/s)',
                        line=dict(width=2, dash='dot', color='#2ca02c'),
                        marker=dict(size=8),
                        yaxis='y2',
                        hovertemplate=(
                            '<b>Batch: %{x}</b><br>'
                            'Throughput: %{y:,.0f} tok/s<br>'
                            '<extra></extra>'
                        ),
                    )
                )

                fig_kv.update_layout(
                    xaxis_title="Batch Size (num_prompts)",
                    yaxis2=dict(
                        title="Throughput (tokens/sec)",
                        overlaying='y',
                        side='right',
                    ),
                    height=400,
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02
                    ),
                )
                st.plotly_chart(fig_kv, use_container_width=True)
                st.caption(
                    "KV-cache usage increases with batch size. "
                    "Once saturated, throughput may degrade or "
                    "requests start queueing."
                )
            else:
                st.info(
                    "Need multiple batch sizes for KV capacity analysis."
                )

        # ---- Context Scaling ----
        ctx_label = '📏 Context Scaling'
        if ctx_label in tech_use_cases:
            st.divider()
            st.subheader("Context Length Scaling")
            st.markdown(
                "**How does throughput degrade with longer context?**"
            )

            df_ctx = df_technical[
                df_technical['use_case'] == ctx_label
            ].copy()
            ctx_models = sorted(
                df_ctx['model_short'].unique().tolist()
            )
            ctx_model = st.selectbox(
                "Model:", options=ctx_models, key="ctx_model"
            )
            df_ctx = df_ctx[df_ctx['model_short'] == ctx_model]

            if 'config_input_len' in df_ctx.columns:
                df_ctx_g = (
                    df_ctx.groupby('config_input_len')
                    .agg({
                        'metric_throughput_total_tokens_per_sec': 'mean',
                        'metric_throughput_requests_per_sec': 'mean',
                    })
                    .reset_index()
                    .sort_values('config_input_len')
                )

                if len(df_ctx_g) > 1:
                    fig_ctx = go.Figure()
                    fig_ctx.add_trace(
                        go.Scatter(
                            x=df_ctx_g['config_input_len'],
                            y=df_ctx_g[
                                'metric_throughput_total_tokens_per_sec'
                            ],
                            mode='lines+markers',
                            name='Total tok/s',
                            line=dict(width=3, color='#1f77b4'),
                            marker=dict(size=10),
                            hovertemplate=(
                                '<b>Input: %{x} tokens</b><br>'
                                'Throughput: %{y:,.0f} tok/s<br>'
                                '<extra></extra>'
                            ),
                        )
                    )
                    fig_ctx.add_trace(
                        go.Scatter(
                            x=df_ctx_g['config_input_len'],
                            y=df_ctx_g[
                                'metric_throughput_requests_per_sec'
                            ],
                            mode='lines+markers',
                            name='Req/s',
                            line=dict(
                                width=2, dash='dot', color='#ff7f0e'
                            ),
                            marker=dict(size=8),
                            yaxis='y2',
                            hovertemplate=(
                                '<b>Input: %{x} tokens</b><br>'
                                'Req/s: %{y:.2f}<br>'
                                '<extra></extra>'
                            ),
                        )
                    )
                    fig_ctx.update_layout(
                        xaxis_title="Input Length (tokens)",
                        yaxis_title="Throughput (tokens/sec)",
                        yaxis2=dict(
                            title="Request Rate (req/s)",
                            overlaying='y',
                            side='right',
                        ),
                        height=400,
                        legend=dict(
                            orientation="h", yanchor="bottom", y=1.02
                        ),
                    )
                    st.plotly_chart(fig_ctx, use_container_width=True)
                    st.caption(
                        "Longer input context increases prefill cost. "
                        "Request rate (req/s) drops more steeply than "
                        "total tokens/sec because each request is bigger."
                    )
                else:
                    st.info(
                        "Need multiple input lengths for context scaling."
                    )
            else:
                st.info("No input_len variation found for context scaling.")

        # ---- Batch Size Scaling (for technical data) ----
        # Show batch scaling for any technical use case with varying
        # num_prompts, or for product data when applicable
        st.divider()
        st.subheader("📈 Batch Size Scaling")
        st.markdown("**How batch size affects throughput**")

        # Combine candidates: technical with batch variation,
        # or product with batch variation
        df_batch_candidates = df_filtered[
            df_filtered.groupby(['use_case', 'model_short', 'cores'])[
                'num_prompts'
            ].transform('nunique')
            > 1
        ].copy()

        if not df_batch_candidates.empty:
            batch_uc_opts = sorted(
                df_batch_candidates['use_case'].unique().tolist()
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                batch_uc = st.selectbox(
                    "Use case:",
                    options=batch_uc_opts,
                    key="batch_scaling_use_case",
                )
            with col2:
                batch_models = sorted(
                    df_batch_candidates[
                        df_batch_candidates['use_case'] == batch_uc
                    ]['model_short']
                    .unique()
                    .tolist()
                )
                batch_model = st.selectbox(
                    "Model:",
                    options=batch_models,
                    key="batch_scaling_model",
                )
            with col3:
                batch_cores_opts = sorted(
                    df_batch_candidates[
                        (df_batch_candidates['use_case'] == batch_uc)
                        & (
                            df_batch_candidates['model_short']
                            == batch_model
                        )
                    ]['cores']
                    .unique()
                    .tolist()
                )
                if len(batch_cores_opts) > 1:
                    batch_cores = st.selectbox(
                        "Cores:",
                        options=batch_cores_opts,
                        key="batch_scaling_cores",
                    )
                else:
                    batch_cores = (
                        batch_cores_opts[0] if batch_cores_opts else None
                    )
                    if batch_cores is not None:
                        st.write(f"**Cores:** {batch_cores}")

            if batch_cores is not None:
                df_bs = df_batch_candidates[
                    (df_batch_candidates['use_case'] == batch_uc)
                    & (df_batch_candidates['model_short'] == batch_model)
                    & (df_batch_candidates['cores'] == batch_cores)
                ].copy()

                df_bs_g = (
                    df_bs.groupby('num_prompts')
                    .agg({
                        'metric_throughput_total_tokens_per_sec': 'mean',
                        'metric_throughput_requests_per_sec': 'mean',
                    })
                    .reset_index()
                    .sort_values('num_prompts')
                )

                if len(df_bs_g) > 1:
                    bs_units = get_use_case_units(batch_uc)
                    df_bs_g['items_per_hour'] = df_bs_g[
                        'metric_throughput_requests_per_sec'
                    ].apply(compute_items_per_hour)

                    fig_bs = go.Figure()
                    fig_bs.add_trace(
                        go.Scatter(
                            x=df_bs_g['num_prompts'],
                            y=df_bs_g['items_per_hour'],
                            mode='lines+markers',
                            name=f'{bs_units["plural"].capitalize()}/hr',
                            line=dict(width=3, color='#9467bd'),
                            marker=dict(size=10),
                            hovertemplate=(
                                '<b>Batch: %{x}</b><br>'
                                + f'{bs_units["plural"].capitalize()}/hr: '
                                + '%{y:,.0f}<br><extra></extra>'
                            ),
                        )
                    )
                    fig_bs.add_trace(
                        go.Scatter(
                            x=df_bs_g['num_prompts'],
                            y=df_bs_g[
                                'metric_throughput_total_tokens_per_sec'
                            ],
                            mode='lines+markers',
                            name='Tokens/sec',
                            line=dict(
                                width=2, dash='dot', color='#17becf'
                            ),
                            marker=dict(size=8),
                            yaxis='y2',
                            hovertemplate=(
                                '<b>Batch: %{x}</b><br>'
                                'Tokens/sec: %{y:,.0f}<br>'
                                '<extra></extra>'
                            ),
                        )
                    )
                    fig_bs.update_layout(
                        xaxis_title="Batch Size (number of prompts)",
                        yaxis_title=(
                            f"{bs_units['plural'].capitalize()} per Hour"
                        ),
                        yaxis2=dict(
                            title="Throughput (tokens/sec)",
                            overlaying='y',
                            side='right',
                        ),
                        height=400,
                        legend=dict(
                            orientation="h", yanchor="bottom", y=1.02
                        ),
                    )
                    st.plotly_chart(fig_bs, use_container_width=True)

                    st.info(
                        "💡 Larger batches typically improve throughput up "
                        "to a point, then plateau due to memory/scheduling "
                        "overhead."
                    )
                else:
                    st.info(
                        "Only one batch size found for this configuration."
                    )
        else:
            st.info(
                "No batch size variation in the current results. "
                "Run technical benchmarks (batch-scaling, kv-capacity) "
                "to populate this chart."
            )

    # ==================================================================
    # DETAILED RESULTS TABLE
    # ==================================================================
    st.divider()
    with st.expander("📋 View All Results", expanded=False):
        results_table = df_filtered.copy()

        display_cols = {
            'use_case': 'Use Case',
            'model_short': 'Model',
            'cores': 'Cores',
            'num_prompts': 'Batch Size',
            'metric_throughput_requests_per_sec': 'Req/sec',
            'metric_throughput_total_tokens_per_sec': 'Tokens/sec',
        }

        if 'config_input_len' in results_table.columns:
            display_cols['config_input_len'] = 'Input Len'
        if 'config_output_len' in results_table.columns:
            display_cols['config_output_len'] = 'Output Len'

        if (
            'metric_prefill_throughput_tokens_per_sec'
            in results_table.columns
        ):
            display_cols[
                'metric_prefill_throughput_tokens_per_sec'
            ] = 'Prefill tok/s'
        if (
            'metric_decode_throughput_tokens_per_sec'
            in results_table.columns
        ):
            display_cols[
                'metric_decode_throughput_tokens_per_sec'
            ] = 'Decode tok/s'

        kv_col = 'metric_max_kv_cache_usage_percent'
        if kv_col in results_table.columns:
            display_cols[kv_col] = 'KV Cache %'

        if 'metric_avg_input_tokens' in results_table.columns:
            display_cols['metric_avg_input_tokens'] = 'Avg In Tok'
        if 'metric_avg_output_tokens' in results_table.columns:
            display_cols['metric_avg_output_tokens'] = 'Avg Out Tok'

        if 'metric_total_time_sec' in results_table.columns:
            display_cols['metric_total_time_sec'] = 'Total Time (s)'

        if 'vllm_version' in results_table.columns:
            display_cols['vllm_version'] = 'vLLM Version'
        if 'container_image' in results_table.columns:
            results_table['container_short'] = results_table[
                'container_image'
            ].apply(
                lambda x: x.split('/')[-1] if isinstance(x, str) else x
            )
            display_cols['container_short'] = 'Container'

        available_display_cols = {
            k: v
            for k, v in display_cols.items()
            if k in results_table.columns
        }

        display_df = results_table[
            list(available_display_cols.keys())
        ].copy()
        display_df.columns = list(available_display_cols.values())

        for col in display_df.columns:
            if display_df[col].dtype in ['float64', 'float32']:
                display_df[col] = display_df[col].round(2)

        st.dataframe(
            display_df.sort_values(
                ['Use Case', 'Model', 'Cores', 'Batch Size']
            ),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
