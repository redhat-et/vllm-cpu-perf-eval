#!/usr/bin/env python3
"""
Offline Batch Benchmark Dashboard

Displays results from vLLM offline batch benchmarking
(vllm bench throughput). Capacity-planning focus: items/hr,
time estimates, core scaling, prefill/decode.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add parent directory to path for config_manager import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_manager import DashboardConfig, normalize_vllm_version  # noqa: E402


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

# Full-suite prompt counts (run-offline-batch-suite.sh reference values).
REFERENCE_PROMPTS_BY_SLUG: Dict[str, int] = {
    'summarization': 1000,
    'classification': 1000,
    'translation': 500,
    'entity_extraction': 1000,
    'dataset_generation': 5000,
    'code_generation': 500,
    'etl': 500,
    'long_summarization': 500,
    'rag_batch': 500,
    'shared_prefix': 1000,
    'short_labeling': 2000,
}

RUN_AGGREGATION_MODES = ('Latest run only', 'Mean of all runs', 'Best of all runs')

EXPECTED_CORE_COUNTS = (8, 16, 24, 32)
VARIANCE_CV_THRESHOLD = 0.10
SERVER_METRICS_PAGE = 'pages/2_🖥️_Server_Metrics.py'

PRODUCT_USE_CASE_DISPLAYS = [
    USE_CASE_MAP[slug]
    for slug in USE_CASE_MAP
    if slug not in TECHNICAL_USE_CASES
]

METRIC_RPS = 'metric_throughput_requests_per_sec'
METRIC_TOK_S = 'metric_throughput_total_tokens_per_sec'
PREFILL_COL = 'metric_prefill_throughput_tokens_per_sec'
DECODE_COL = 'metric_decode_throughput_tokens_per_sec'

# Bump when dashboard layout/features change (shown in UI for verification).
DASHBOARD_BUILD = '2026-08-06-import'

TAB_GUIDES = {
    'overview': """
**Suite health** — top metrics show how complete your benchmark matrix is.

| Section | What it tells you |
|--------|-------------------|
| **Throughput heatmap** | Best items/hour per model × use case at one core count |
| **Best configuration** | Highest-throughput model@cores per use case |
| **Capacity snapshot** | Planning estimate for one use case (items/hr, time for 10k) |
| **Data completeness** | Missing sweeps (prefill/decode, multi-core) + commands to fix |
| **Expected vs actual** | Which of the 11 product use cases × models have any runs |
| **Run variance** | Spread across repeated runs (high CV = less trustworthy) |
| **Version regression** | Req/s change between vLLM versions |
| **Coverage** | How many runs exist per model@cores × use case |
""",
    'use_cases': """
Pick a **use case** to compare configurations for that workload.

| Chart | Meaning |
|-------|---------|
| **Processing capacity** | Items/hour per model@cores (one bar each — best config if duplicates exist) |
| **Time estimates** | Wall-clock time for a chosen batch size |
| **Workload planner** | Enter volume + deadline → which configs qualify |
| **Cache metrics** | KV-cache usage and prefix-cache hit rate (shared-prefix / RAG) |
| **Prefill vs decode** | Prompt processing vs token generation speed (bottleneck hint) |
""",
    'scaling': """
**Core scaling** needs multiple core counts (8/16/24/32) for the same use case + model.

| Section | Meaning |
|---------|---------|
| **Core scaling chart** | Items/hr and tokens/sec/core vs CPU cores |
| **Scaling efficiency** | Actual speedup vs ideal linear scaling |
| **Technical sweeps** | KV capacity, context length, batch size experiments |
""",
    'all_runs': """
Raw benchmark rows — use for debugging and exports.

| Tool | Purpose |
|------|---------|
| **CSV export** | Download filtered results or capacity summary |
| **Config comparison** | Side-by-side delta for two runs |
| **Log preview** | Tail of `benchmark.log` (engine stats, errors) |
| **Results table** | Every loaded run with config fingerprint |
""",
    'sidebar': """
| Control | Effect |
|---------|--------|
| **Results Directory** | Path to `results/llm/` |
| **Additional directory** | Merge a second `results/llm` tree (e.g. from a teammate) |
| **Import CSV** | Upload a CSV exported from **All Runs → Download** |
| **Run aggregation** | Collapse repeats: latest, mean, or best req/s |
| **Hide capped runs** | Drop smoke tests with fewer prompts than full suite |
| **Minimum runs** | Hide configs with too few repeats |
| **Focus use case** | Pin one use case across tabs |
""",
}


def _render_tab_guide(tab_key: str) -> None:
    """Collapsed help for the active tab."""
    label = {
        'overview': 'ℹ️ How to read Overview',
        'use_cases': 'ℹ️ How to read Use Cases',
        'scaling': 'ℹ️ How to read Scaling',
        'all_runs': 'ℹ️ How to read All Runs',
    }.get(tab_key, 'ℹ️ Help')
    with st.expander(label, expanded=False):
        st.markdown(TAB_GUIDES.get(tab_key, ''))


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


def format_duration(seconds: float) -> str:
    """Human-friendly duration string from seconds."""
    if seconds == float('inf') or seconds != seconds:  # inf or NaN
        return "N/A"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} hr"


def collapse_by_model_cores(
    df: pd.DataFrame,
    metric_col: str = METRIC_RPS,
) -> pd.DataFrame:
    """One row per model@cores for bar charts.

    Plotly stacks bars that share the same x-axis category. Multiple benchmark
    configs (prompt counts, token lengths) can share model@cores labels.
    """
    if df.empty:
        return df.copy()

    working = df.copy()
    if 'items_per_hour' not in working.columns:
        working['items_per_hour'] = working[metric_col].apply(
            compute_items_per_hour
        )

    idx = working.groupby(
        ['model_short', 'cores'], dropna=False
    )[metric_col].idxmax()
    collapsed = working.loc[idx].copy()
    collapsed['config_label'] = (
        collapsed['model_short'].astype(str)
        + '\n'
        + collapsed['cores'].astype(str)
        + ' cores'
    )
    return collapsed.sort_values('items_per_hour', ascending=False)


def config_group_columns(df: pd.DataFrame) -> List[str]:
    """Columns that uniquely identify an offline-batch configuration."""
    cols = ['model_short', 'use_case', 'cores', 'dataset', 'num_prompts']
    for optional in ('config_input_len', 'config_output_len', 'use_case_slug'):
        if optional in df.columns:
            cols.append(optional)
    return cols


def build_config_fingerprint(row: dict) -> str:
    """Compact label for a benchmark configuration."""
    parts = [
        f"{row.get('cores', '?')}c",
        str(row.get('dataset', '?')),
        f"{row.get('num_prompts', '?')} prompts",
    ]
    in_len = row.get('config_input_len')
    out_len = row.get('config_output_len')
    if pd.notna(in_len) if in_len is not None else False:
        parts.append(f"in={int(in_len)}")
    if pd.notna(out_len) if out_len is not None else False:
        parts.append(f"out={int(out_len)}")
    return ' / '.join(parts)


def is_capped_run(use_case_slug: str, num_prompts: int) -> bool:
    """True when num_prompts is below the full-suite reference for this slug."""
    if not use_case_slug:
        return False
    reference = REFERENCE_PROMPTS_BY_SLUG.get(use_case_slug)
    if reference is None:
        return False
    return num_prompts < reference


def capped_run_note(use_case_slug: str, num_prompts: int) -> str:
    """Human-readable note for capped prompt counts, or empty string."""
    if not is_capped_run(use_case_slug, num_prompts):
        return ''
    reference = REFERENCE_PROMPTS_BY_SLUG[use_case_slug]
    return (
        f"Capped run: {num_prompts} prompts "
        f"(full suite uses {reference}; set OFFLINE_BATCH_MAX_PROMPTS=0)"
    )


def apply_run_aggregation(
    df: pd.DataFrame,
    mode: str,
    metric_col: str = METRIC_RPS,
) -> pd.DataFrame:
    """Collapse multiple runs per config to one row per configuration."""
    if df.empty:
        return df.copy()

    group_cols = config_group_columns(df)
    metric_cols = [
        c for c in df.columns
        if c.startswith('metric_') and pd.api.types.is_numeric_dtype(df[c])
    ]

    if mode == 'Latest run only':
        idx = df.groupby(group_cols, dropna=False)['timestamp'].idxmax()
        out = df.loc[idx].copy()
        out['n_runs'] = df.groupby(group_cols, dropna=False).size().values
        return out.reset_index(drop=True)

    if mode == 'Best of all runs':
        idx = df.groupby(group_cols, dropna=False)[metric_col].idxmax()
        out = df.loc[idx].copy()
        out['n_runs'] = df.groupby(group_cols, dropna=False).size().values
        return out.reset_index(drop=True)

    # Mean of all runs (default)
    agg_map = {col: 'mean' for col in metric_cols}
    grouped = df.groupby(group_cols, dropna=False).agg(agg_map)
    stats = df.groupby(group_cols, dropna=False)[metric_col].agg(
        ['count', 'std', 'min', 'max']
    )
    stats = stats.rename(columns={
        'count': 'n_runs',
        'std': f'{metric_col}_std',
        'min': f'{metric_col}_min',
        'max': f'{metric_col}_max',
    })
    out = grouped.join(stats)
    if f'{metric_col}_std' in out.columns:
        out[f'{metric_col}_std'] = out[f'{metric_col}_std'].fillna(0.0)
    latest_idx = df.groupby(group_cols, dropna=False)['timestamp'].idxmax()
    out['latest_timestamp'] = df.loc[latest_idx, 'timestamp'].values
    return out.reset_index()


def build_coverage_pivot(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot: rows=model@cores, columns=use case, values=run count."""
    if df.empty:
        return pd.DataFrame()
    working = df.copy()
    working['model_cores'] = (
        working['model_short'].astype(str)
        + ' @ '
        + working['cores'].astype(str)
        + 'c'
    )
    counts = (
        working.groupby(['model_cores', 'use_case'])
        .size()
        .unstack(fill_value=0)
    )
    return counts.sort_index()


def coverage_cell_style(value: int) -> str:
    """Background color for coverage heatmap cells."""
    if value <= 0:
        return 'background-color: #f0f0f0; color: #888'
    if value < 3:
        return 'background-color: #fff3cd; color: #664d03'
    return 'background-color: #d1e7dd; color: #0f5132'


def style_coverage_pivot(pivot: pd.DataFrame):
    """Return a pandas Styler for the coverage matrix."""
    return pivot.style.map(coverage_cell_style).format('{:.0f}')


def build_best_configs_table(
    df: pd.DataFrame,
    metric_col: str = METRIC_RPS,
) -> pd.DataFrame:
    """One best row per product use case (highest req/s)."""
    if df.empty:
        return pd.DataFrame()

    rows = []
    for use_case in sorted(df['use_case'].unique()):
        uc_df = df[df['use_case'] == use_case]
        best_idx = uc_df[metric_col].idxmax()
        best = uc_df.loc[best_idx]
        units = get_use_case_units(use_case)
        rps = best.get(metric_col, 0) or 0
        rows.append({
            'Use Case': use_case,
            'Model': best['model_short'],
            'Cores': best['cores'],
            'Config': best.get('config_fingerprint', ''),
            'Req/s': round(rps, 3),
            f"{units['plural'].capitalize()}/hr": int(compute_items_per_hour(rps)),
            'Runs': int(best.get('n_runs', 1)),
        })
    return pd.DataFrame(rows)


def apply_quality_filters(
    df: pd.DataFrame,
    hide_capped: bool = False,
    min_runs: int = 1,
) -> pd.DataFrame:
    """Filter raw runs by capped status and minimum run count per config."""
    if df.empty:
        return df.copy()

    out = df.copy()
    if hide_capped and 'is_capped' in out.columns:
        out = out[~out['is_capped'].fillna(False)]

    if min_runs > 1:
        group_cols = config_group_columns(out)
        counts = out.groupby(group_cols, dropna=False).transform('size')
        out = out[counts >= min_runs]

    return out.reset_index(drop=True)


def _has_prefill_decode(row: pd.Series) -> bool:
    prefill = row.get(PREFILL_COL, 0) or 0
    decode = row.get(DECODE_COL, 0) or 0
    return prefill > 0 or decode > 0


def build_completeness_report(df_product: pd.DataFrame) -> Dict[str, object]:
    """Summarize suite data quality and gaps."""
    if df_product.empty:
        return {
            'total_runs': 0,
            'use_cases_seen': 0,
            'use_cases_expected': len(PRODUCT_USE_CASE_DISPLAYS),
            'models_seen': 0,
            'prefill_decode_pct': 0.0,
            'multi_core_pct': 0.0,
            'capped_count': 0,
            'suite_completion_pct': 0.0,
        }

    use_cases_seen = set(df_product['use_case'].unique())
    models_seen = set(df_product['model_short'].unique())
    prefill_ok = int(df_product.apply(_has_prefill_decode, axis=1).sum())
    capped_count = int(df_product['is_capped'].sum()) if 'is_capped' in df_product.columns else 0

    multi_core_use_cases = 0
    for _, group in df_product.groupby('use_case'):
        if len(group['cores'].dropna().unique()) > 1:
            multi_core_use_cases += 1

    expected_cells = (
        len(PRODUCT_USE_CASE_DISPLAYS) * max(len(models_seen), 1)
    )
    actual_cells = len(
        df_product.groupby(['use_case', 'model_short']).size()
    )
    suite_pct = (
        min(100.0, (actual_cells / expected_cells) * 100)
        if expected_cells > 0
        else 0.0
    )

    return {
        'total_runs': len(df_product),
        'use_cases_seen': len(use_cases_seen),
        'use_cases_expected': len(PRODUCT_USE_CASE_DISPLAYS),
        'models_seen': len(models_seen),
        'prefill_decode_pct': round(
            100.0 * prefill_ok / len(df_product), 1
        ),
        'multi_core_pct': round(
            100.0 * multi_core_use_cases / max(len(use_cases_seen), 1), 1
        ),
        'capped_count': capped_count,
        'suite_completion_pct': round(suite_pct, 1),
    }


def build_data_gaps_table(df_product: pd.DataFrame) -> pd.DataFrame:
    """Actionable gaps: missing prefill/decode, single-core, capped, low runs."""
    if df_product.empty:
        return pd.DataFrame()

    rows = []
    group_cols = config_group_columns(df_product)

    for (keys, group) in df_product.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        use_case = row.get('use_case', '')
        slug = row.get('use_case_slug', '') or _get_use_case_slug(use_case)
        cli_name = use_case_cli_name(use_case, slug)
        n_runs = len(group)
        cores = sorted(group['cores'].dropna().unique().tolist())
        has_pd = group.apply(_has_prefill_decode, axis=1).any()
        is_cap = bool(group['is_capped'].any()) if 'is_capped' in group.columns else False

        gaps = []
        if not has_pd:
            gaps.append('prefill/decode')
        if len(cores) <= 1:
            gaps.append('multi-core')
        if is_cap:
            gaps.append('capped')
        if n_runs < 3:
            gaps.append(f'low runs ({n_runs})')

        if gaps:
            cmd = (
                f'./run-offline-batch-suite.sh use-case-sweep '
                f'{cli_name} all 8,16,24,32'
            )
            rows.append({
                'Use Case': use_case,
                'Model': row.get('model_short', ''),
                'Cores': ', '.join(str(c) for c in cores),
                'Runs': n_runs,
                'Gaps': ', '.join(gaps),
                'Suggested Command': cmd,
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(['Use Case', 'Model'])


def build_expected_vs_actual_matrix(
    df_product: pd.DataFrame,
    models: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """Expected product use cases vs models; cell = run count (0 if missing)."""
    if models is None:
        models = sorted(df_product['model_short'].unique().tolist()) if not df_product.empty else []

    matrix = []
    for uc in PRODUCT_USE_CASE_DISPLAYS:
        row = {'Use Case': uc}
        for model in models:
            if df_product.empty:
                count = 0
            else:
                count = len(df_product[
                    (df_product['use_case'] == uc)
                    & (df_product['model_short'] == model)
                ])
            row[model] = count
        matrix.append(row)
    return pd.DataFrame(matrix)


def build_model_usecase_heatmap(
    df_product_view: pd.DataFrame,
    cores: Optional[int] = None,
    metric_col: str = METRIC_RPS,
) -> pd.DataFrame:
    """Pivot for heatmap: rows=models, columns=use cases, values=items/hr."""
    if df_product_view.empty:
        return pd.DataFrame()

    working = df_product_view.copy()
    if cores is not None:
        working = working[working['cores'] == cores]
    if working.empty:
        return pd.DataFrame()

    working['items_per_hour'] = working[metric_col].apply(
        compute_items_per_hour
    )
    pivot = working.pivot_table(
        index='model_short',
        columns='use_case',
        values='items_per_hour',
        aggfunc='max',
    )
    return pivot.sort_index()


def compute_coefficient_of_variation(mean: float, std: float) -> float:
    if mean <= 0 or std != std:  # NaN check
        return 0.0
    return std / mean


def build_variance_summary(df_product: pd.DataFrame) -> pd.DataFrame:
    """Per-config run variance from raw (unaggregated) data."""
    if df_product.empty:
        return pd.DataFrame()

    group_cols = config_group_columns(df_product)
    rows = []
    for keys, group in df_product.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        n = len(group)
        mean_rps = group[METRIC_RPS].mean()
        std_rps = group[METRIC_RPS].std() if n > 1 else 0.0
        cv = compute_coefficient_of_variation(mean_rps, std_rps or 0.0)
        high_var = n > 1 and cv > VARIANCE_CV_THRESHOLD
        rows.append({
            'Use Case': row.get('use_case', ''),
            'Model': row.get('model_short', ''),
            'Cores': row.get('cores', ''),
            'Runs': n,
            'Mean Req/s': round(mean_rps, 3),
            'Std Dev': round(std_rps or 0.0, 3),
            'CV %': round(cv * 100, 1),
            'High Variance': '⚠️ Yes' if high_var else 'No',
        })
    return pd.DataFrame(rows).sort_values(['Use Case', 'Model', 'Cores'])


def build_scaling_efficiency_table(df_cs: pd.DataFrame) -> pd.DataFrame:
    """Actual vs theoretical core scaling speedup."""
    if df_cs.empty or len(df_cs) < 2:
        return pd.DataFrame()

    sorted_df = df_cs.sort_values('cores')
    base = sorted_df.iloc[0]
    base_cores = float(base['cores'])
    base_rps = float(base.get(METRIC_RPS, 0) or 0)
    if base_rps <= 0:
        return pd.DataFrame()

    rows = []
    for _, row in sorted_df.iloc[1:].iterrows():
        cores = float(row['cores'])
        rps = float(row.get(METRIC_RPS, 0) or 0)
        theoretical = cores / base_cores
        actual = rps / base_rps if base_rps > 0 else 0
        efficiency = (actual / theoretical * 100) if theoretical > 0 else 0

        if actual < 1.0:
            verdict = '❌ Degraded'
        elif efficiency < 50:
            verdict = '⚠️ Poor'
        elif efficiency < 80:
            verdict = '⚠️ Fair'
        else:
            verdict = '✅ Good'

        rows.append({
            'Baseline': f"{int(base_cores)}c",
            'Comparison': f"{int(cores)}c",
            'Theoretical': f"{theoretical:.1f}x",
            'Actual': f"{actual:.2f}x",
            'Efficiency %': f"{efficiency:.1f}%",
            'Verdict': verdict,
        })
    return pd.DataFrame(rows)


def find_configs_for_deadline(
    df: pd.DataFrame,
    use_case: str,
    batch_size: int,
    deadline_hours: float,
) -> pd.DataFrame:
    """Configs that can process batch_size within deadline_hours."""
    if df.empty or deadline_hours <= 0:
        return pd.DataFrame()

    uc_df = df[df['use_case'] == use_case].copy()
    if uc_df.empty:
        return pd.DataFrame()

    units = get_use_case_units(use_case)
    deadline_sec = deadline_hours * 3600.0
    uc_df['time_sec'] = uc_df[METRIC_RPS].apply(
        lambda r: compute_time_for_batch(r, batch_size)
    )
    uc_df['items_per_hour'] = uc_df[METRIC_RPS].apply(compute_items_per_hour)
    qualifying = uc_df[uc_df['time_sec'] <= deadline_sec].copy()
    if qualifying.empty:
        return pd.DataFrame()

    qualifying = qualifying.sort_values('time_sec')
    return qualifying[[
        'model_short', 'cores', 'config_fingerprint',
        METRIC_RPS, 'items_per_hour', 'time_sec',
    ]].assign(
        time_display=lambda d: d['time_sec'].apply(format_duration),
        unit=units['plural'],
    )


def build_version_regression_table(df_product: pd.DataFrame) -> pd.DataFrame:
    """Compare latest version vs previous per use case / model / cores."""
    if df_product.empty or df_product['vllm_version'].nunique() < 2:
        return pd.DataFrame()

    rows = []
    group_cols = ['use_case', 'model_short', 'cores']
    for keys, group in df_product.groupby(group_cols, dropna=False):
        versions = sorted(group['vllm_version'].unique())
        if len(versions) < 2:
            continue
        prev_v, latest_v = versions[-2], versions[-1]
        prev_rps = group[group['vllm_version'] == prev_v][METRIC_RPS].mean()
        latest_rps = group[group['vllm_version'] == latest_v][METRIC_RPS].mean()
        if prev_rps <= 0:
            continue
        pct_change = ((latest_rps - prev_rps) / prev_rps) * 100
        if pct_change < -5:
            flag = '🔴 Regression'
        elif pct_change > 5:
            flag = '🟢 Improvement'
        else:
            flag = '— Stable'
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        rows.append({
            'Use Case': row['use_case'],
            'Model': row['model_short'],
            'Cores': row['cores'],
            'Previous': prev_v,
            'Latest': latest_v,
            'Prev Req/s': round(prev_rps, 3),
            'Latest Req/s': round(latest_rps, 3),
            'Change %': f"{pct_change:+.1f}%",
            'Status': flag,
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(['Use Case', 'Model'])


def build_time_trend_data(df_product: pd.DataFrame) -> pd.DataFrame:
    """Items/hr over time per config for trend charts."""
    if df_product.empty or 'timestamp' not in df_product.columns:
        return pd.DataFrame()

    working = df_product.copy()
    working['items_per_hour'] = working[METRIC_RPS].apply(compute_items_per_hour)
    working['config_label'] = (
        working['use_case'].astype(str)
        + ' / '
        + working['model_short'].astype(str)
        + ' @ '
        + working['cores'].astype(str)
        + 'c'
    )
    return working[[
        'timestamp', 'config_label', 'items_per_hour', METRIC_RPS,
        'use_case', 'model_short', 'cores', 'vllm_version',
    ]].sort_values('timestamp')


def compare_config_rows(row_a: pd.Series, row_b: pd.Series) -> pd.DataFrame:
    """Side-by-side delta for two benchmark rows."""
    metrics = [
        ('Req/s', METRIC_RPS),
        ('Items/hr', None),
        ('Tokens/s', METRIC_TOK_S),
        ('Prefill tok/s', PREFILL_COL),
        ('Decode tok/s', DECODE_COL),
        ('KV Cache %', 'metric_max_kv_cache_usage_percent'),
        ('Prefix Cache %', 'metric_avg_prefix_cache_hit_rate_percent'),
    ]
    rows = []
    for label, col in metrics:
        if label == 'Items/hr':
            val_a = compute_items_per_hour(row_a.get(METRIC_RPS, 0) or 0)
            val_b = compute_items_per_hour(row_b.get(METRIC_RPS, 0) or 0)
        else:
            val_a = row_a.get(col, 0) or 0
            val_b = row_b.get(col, 0) or 0
        delta = val_b - val_a
        pct = (delta / val_a * 100) if val_a else 0
        rows.append({
            'Metric': label,
            'Config A': round(val_a, 3),
            'Config B': round(val_b, 3),
            'Delta': round(delta, 3),
            'Change %': f"{pct:+.1f}%" if val_a else 'N/A',
        })

    rows.append({
        'Metric': 'Config fingerprint',
        'Config A': row_a.get('config_fingerprint', ''),
        'Config B': row_b.get('config_fingerprint', ''),
        'Delta': '',
        'Change %': '',
    })
    return pd.DataFrame(rows)


def config_diff_notes(row_a: pd.Series, row_b: pd.Series) -> List[str]:
    """Human-readable config differences."""
    diffs = []
    for field, label in [
        ('cores', 'cores'),
        ('num_prompts', 'prompts'),
        ('config_input_len', 'input len'),
        ('config_output_len', 'output len'),
        ('vllm_version', 'vLLM version'),
        ('dataset', 'dataset'),
    ]:
        a, b = row_a.get(field), row_b.get(field)
        if pd.notna(a) and pd.notna(b) and a != b:
            diffs.append(f"{label}: {a} → {b}")
    if row_a.get('is_capped') != row_b.get('is_capped'):
        diffs.append('capped status differs')
    return diffs


def tail_benchmark_log(result_dir: str, max_lines: int = 40) -> str:
    """Return trailing lines from benchmark.log, engine stats highlighted."""
    log_path = Path(result_dir) / 'benchmark.log'
    if not log_path.exists():
        return '(benchmark.log not found)'
    try:
        lines = log_path.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError as exc:
        return f'(error reading log: {exc})'
    tail = lines[-max_lines:] if len(lines) > max_lines else lines
    return '\n'.join(tail)


def build_capacity_summary_csv(df_product_view: pd.DataFrame) -> str:
    """CSV export of best config per use case."""
    best_df = build_best_configs_table(df_product_view)
    if best_df.empty:
        return ''
    return best_df.to_csv(index=False)


def build_filtered_results_csv(df: pd.DataFrame) -> str:
    """CSV export of all filtered runs."""
    if df.empty:
        return ''
    export = df.copy()
    if METRIC_RPS in export.columns:
        export['items_per_hour'] = export[METRIC_RPS].apply(compute_items_per_hour)
    cols = [
        c for c in [
            'timestamp', 'use_case', 'model_short', 'cores', 'num_prompts',
            'config_fingerprint', METRIC_RPS, 'items_per_hour', METRIC_TOK_S,
            PREFILL_COL, DECODE_COL, 'vllm_version', 'test_run_id', 'result_dir',
        ]
        if c in export.columns
    ]
    return export[cols].to_csv(index=False)


# Friendly CSV headers (from All Runs export) → internal column names
IMPORT_CSV_COLUMN_MAP: Dict[str, str] = {
    'Req/sec': METRIC_RPS,
    'Tokens/sec': METRIC_TOK_S,
    'Prefill tok/s': PREFILL_COL,
    'Decode tok/s': DECODE_COL,
    'Items/hr': 'items_per_hour',
    'Use Case': 'use_case',
    'Model': 'model_short',
    'Cores': 'cores',
    'Batch Size': 'num_prompts',
    'Config': 'config_fingerprint',
    'Run ID': 'test_run_id',
    'vLLM Version': 'vllm_version',
    'Result Path': 'result_dir',
    'Input Len': 'config_input_len',
    'Output Len': 'config_output_len',
    'Timestamp': 'timestamp',
}

IMPORT_CSV_BARE_METRICS: Dict[str, str] = {
    'throughput_requests_per_sec': METRIC_RPS,
    'throughput_total_tokens_per_sec': METRIC_TOK_S,
    'prefill_throughput_tokens_per_sec': PREFILL_COL,
    'decode_throughput_tokens_per_sec': DECODE_COL,
}


def enrich_offline_batch_row(row: dict) -> dict:
    """Fill derived fields on a directory-loaded or imported row."""
    combined = dict(row)
    model = combined.get('model') or combined.get('model_short') or 'unknown'
    combined['model'] = model
    combined['model_short'] = str(model).split('/')[-1]

    if METRIC_RPS not in combined or pd.isna(combined.get(METRIC_RPS)):
        items_hr = combined.get('items_per_hour')
        if items_hr not in (None, '', 0):
            combined[METRIC_RPS] = float(items_hr) / 3600.0

    slug = combined.get('use_case_slug') or _get_use_case_slug(
        combined.get('use_case', '')
    )
    combined['use_case_slug'] = slug
    if not combined.get('config_fingerprint'):
        combined['config_fingerprint'] = build_config_fingerprint(combined)

    num_prompts = int(combined.get('num_prompts', 0) or 0)
    combined['is_capped'] = is_capped_run(slug, num_prompts)
    combined['capped_note'] = capped_run_note(slug, num_prompts)
    combined.setdefault('dataset', 'unknown')
    combined.setdefault('container_image', 'imported')
    if combined.get('vllm_version'):
        combined['vllm_version'] = normalize_vllm_version(
            str(combined['vllm_version'])
        )
    else:
        combined['vllm_version'] = 'imported'
    combined.setdefault(
        'test_run_id',
        f"imported-{combined.get('timestamp', '')}",
    )
    combined['source'] = combined.get('source', 'import')
    return combined


def normalize_imported_offline_batch_df(df: pd.DataFrame) -> pd.DataFrame:
    """Map an uploaded CSV to the internal offline-batch schema."""
    if df.empty:
        return df.copy()

    out = df.copy()
    for src, dst in IMPORT_CSV_COLUMN_MAP.items():
        if src in out.columns and dst not in out.columns:
            out[dst] = out[src]

    for bare, col in IMPORT_CSV_BARE_METRICS.items():
        if bare in out.columns and col not in out.columns:
            out[col] = pd.to_numeric(out[bare], errors='coerce')

    if METRIC_RPS not in out.columns and 'items_per_hour' in out.columns:
        out[METRIC_RPS] = (
            pd.to_numeric(out['items_per_hour'], errors='coerce') / 3600.0
        )

    missing = [
        c for c in ('use_case', 'cores', METRIC_RPS)
        if c not in out.columns
    ]
    if missing:
        raise ValueError(
            f"CSV missing required columns: {missing}. "
            "Export from **All Runs → Download filtered runs (CSV)** "
            "or include Use Case, Cores, and Req/sec."
        )

    out['cores'] = pd.to_numeric(out['cores'], errors='coerce')
    out[METRIC_RPS] = pd.to_numeric(out[METRIC_RPS], errors='coerce')
    if 'timestamp' in out.columns:
        out['timestamp'] = pd.to_datetime(out['timestamp'])
    else:
        out['timestamp'] = pd.Timestamp.utcnow()
    if 'num_prompts' in out.columns:
        out['num_prompts'] = (
            pd.to_numeric(out['num_prompts'], errors='coerce')
            .fillna(0)
            .astype(int)
        )
    else:
        out['num_prompts'] = 0

    rows = [enrich_offline_batch_row(r) for r in out.to_dict('records')]
    return pd.DataFrame(rows)


def merge_benchmark_dataframes(*frames: pd.DataFrame) -> pd.DataFrame:
    """Concatenate directory + imported data, dedupe on test_run_id."""
    parts = [f for f in frames if f is not None and not f.empty]
    if not parts:
        return pd.DataFrame()
    merged = pd.concat(parts, ignore_index=True)
    if 'test_run_id' in merged.columns:
        merged = merged.drop_duplicates(subset=['test_run_id'], keep='last')
    if 'model' in merged.columns:
        merged['model_short'] = merged['model'].apply(
            lambda x: str(x).split('/')[-1]
        )
    return merged


def parse_streaming_metrics_from_log(log_text: str) -> Dict[str, float]:
    """Extract prefill/decode/KV metrics from vLLM engine log lines.

    vLLM prints periodic engine stats (often on stderr) like:
    Engine 000: Avg prompt throughput: X tokens/s, Avg generation throughput: Y ...
    """
    prefill_samples: List[float] = []
    decode_samples: List[float] = []
    kv_samples: List[float] = []
    prefix_samples: List[float] = []

    for line in log_text.splitlines():
        prefill_m = re.search(
            r'Avg prompt throughput:\s*([0-9.]+)\s*tokens/s', line
        )
        if prefill_m:
            prefill_samples.append(float(prefill_m.group(1)))

        decode_m = re.search(
            r'Avg generation throughput:\s*([0-9.]+)\s*tokens/s', line
        )
        if decode_m:
            decode_samples.append(float(decode_m.group(1)))

        kv_m = re.search(
            r'(?:GPU|CPU) KV cache usage:\s*([0-9.]+)%', line
        )
        if kv_m:
            kv_samples.append(float(kv_m.group(1)))

        prefix_m = re.search(
            r'Prefix cache hit rate:\s*([0-9.]+)%', line
        )
        if prefix_m:
            prefix_samples.append(float(prefix_m.group(1)))

    def _avg(values: List[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    return {
        PREFILL_COL: _avg(prefill_samples),
        DECODE_COL: _avg(decode_samples),
        'metric_max_kv_cache_usage_percent': (
            round(max(kv_samples), 2) if kv_samples else 0.0
        ),
        'metric_avg_prefix_cache_hit_rate_percent': _avg(prefix_samples),
    }


def backfill_streaming_metrics(combined: dict, config_dir: Path) -> None:
    """Fill missing streaming metrics from benchmark.log when results.json has zeros."""
    log_path = config_dir / 'benchmark.log'
    if not log_path.exists():
        return

    needs_backfill = (
        combined.get(PREFILL_COL, 0) in (0, None, 0.0)
        or combined.get(DECODE_COL, 0) in (0, None, 0.0)
    )
    if not needs_backfill:
        return

    try:
        log_metrics = parse_streaming_metrics_from_log(
            log_path.read_text(encoding='utf-8', errors='replace')
        )
    except OSError:
        return

    for key, value in log_metrics.items():
        if value and combined.get(key, 0) in (0, None, 0.0):
            combined[key] = value


def format_run_stats(row: pd.Series, metric_col: str = METRIC_RPS) -> str:
    """Short stats string for hover text or captions."""
    n = int(row.get('n_runs', 1))
    val = row.get(metric_col, 0) or 0
    if n <= 1:
        return f"{val:.3f} req/s (n=1)"
    std_col = f'{metric_col}_std'
    if std_col in row.index and pd.notna(row[std_col]):
        return (
            f"{val:.3f} ± {row[std_col]:.3f} req/s "
            f"(n={n}, min={row.get(f'{metric_col}_min', val):.3f}, "
            f"max={row.get(f'{metric_col}_max', val):.3f})"
        )
    return f"{val:.3f} req/s (n={n})"


def resolve_focus_use_case(
    focus_choice: str,
    available: Sequence[str],
    tab_key: str,
) -> Optional[str]:
    """Pick the active use case from sidebar focus or a tab-local selectbox."""
    if focus_choice != 'All':
        return focus_choice
    if not available:
        return None
    return st.selectbox(
        'Use case:',
        options=available,
        key=tab_key,
    )


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

def _load_result_from_config_dir(config_dir: Path) -> Optional[dict]:
    """Load one offline-batch result from a config directory."""
    results_file = config_dir / 'results.json'
    metadata_file = config_dir / 'test-metadata.json'
    if not (results_file.exists() and metadata_file.exists()):
        return None

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
        'num_prompts': metadata['configuration']['num_prompts'],
        'container_image': metadata['environment'].get(
            'container_image', 'unknown'
        ),
        'vllm_version': normalize_vllm_version(
            metadata['environment'].get('vllm_version', 'unknown')
        ),
        'result_dir': str(config_dir),
        'source': 'directory',
    }

    dataset_config = metadata['configuration'].get('dataset_config', {})
    if 'input_len' in dataset_config:
        combined['config_input_len'] = dataset_config['input_len']
    if 'output_len' in dataset_config:
        combined['config_output_len'] = dataset_config['output_len']

    combined['use_case_slug'] = dataset_config.get('use_case', '')

    metrics = result_data.get('metrics', {})
    for metric_name, metric_value in metrics.items():
        combined[f'metric_{metric_name}'] = metric_value

    combined['use_case'] = infer_use_case(metadata)
    combined['config_fingerprint'] = build_config_fingerprint(combined)
    slug = combined.get('use_case_slug', '')
    combined['is_capped'] = is_capped_run(slug, int(combined['num_prompts']))
    combined['capped_note'] = capped_run_note(
        slug,
        int(combined['num_prompts']),
    )

    backfill_streaming_metrics(combined, config_dir)
    return combined


def scan_results_directory(results_path: Path) -> List[dict]:
    """Walk a results/llm tree and return raw result dicts."""
    results: List[dict] = []
    if not results_path.exists():
        return results

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
                try:
                    row = _load_result_from_config_dir(config_dir)
                    if row:
                        results.append(row)
                except Exception as exc:
                    st.warning(f"Error loading {config_dir}: {exc}")

    return results


def results_list_to_dataframe(results: List[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


@st.cache_data
def load_benchmark_results_from_dirs(*dir_paths: str) -> pd.DataFrame:
    """Load and merge offline-batch results from one or more directories."""
    all_rows: List[dict] = []
    for dir_path in dir_paths:
        if not dir_path or not str(dir_path).strip():
            continue
        path = Path(dir_path)
        if not path.exists():
            continue
        all_rows.extend(scan_results_directory(path))
    return results_list_to_dataframe(all_rows)


def load_benchmark_results(results_base_dir: str) -> pd.DataFrame:
    """Load all offline batch benchmark results from a single directory."""
    path = Path(results_base_dir)
    if not path.exists():
        return pd.DataFrame()
    return results_list_to_dataframe(scan_results_directory(path))


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def _safe_metric(df: pd.DataFrame, col: str, default: float = 0.0):
    """Return column values with fallback to *default* when missing."""
    if col in df.columns:
        return df[col].fillna(default)
    return pd.Series([default] * len(df), index=df.index)


def _render_environment_banner(df_filtered: pd.DataFrame) -> None:
    if 'container_image' not in df_filtered.columns:
        return

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
                    df_filtered[df_filtered['container_image'] == container]
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


def _render_overview_tab(
    df_product: pd.DataFrame,
    df_product_view: pd.DataFrame,
    focus_use_case: str,
    all_models: List[str],
) -> None:
    """Suite overview: completeness, coverage, heatmap, best configs, trends."""
    _render_tab_guide('overview')
    st.subheader("Suite Overview")

    if df_product.empty:
        st.info("No product use-case results match the current filters.")
        return

    report = build_completeness_report(df_product)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Raw runs", report['total_runs'])
    with col2:
        st.metric(
            "Use cases",
            f"{report['use_cases_seen']}/{report['use_cases_expected']}",
        )
    with col3:
        st.metric("Suite completion", f"{report['suite_completion_pct']}%")
    with col4:
        st.metric("Prefill/decode coverage", f"{report['prefill_decode_pct']}%")

    capped_count = report['capped_count']
    if capped_count > 0:
        st.warning(
            f"**{capped_count} capped run(s)** detected. "
            "Enable **Hide capped runs** in the sidebar for planning views."
        )

    # --- Primary visuals (always visible) ---
    st.markdown("### Throughput heatmap")
    st.caption(
        "Items per hour by model (rows) and use case (columns) at one core count. "
        "Darker green = higher throughput — quick answer to *which model for which job?*"
    )
    heatmap_cores_opts = sorted(df_product_view['cores'].unique().tolist())
    hm_cores = (
        st.selectbox(
            "Core count for heatmap:",
            heatmap_cores_opts,
            key="heatmap_cores",
        )
        if len(heatmap_cores_opts) > 1
        else heatmap_cores_opts[0]
    )
    heatmap_pivot = build_model_usecase_heatmap(df_product_view, cores=hm_cores)
    if not heatmap_pivot.empty:
        fig_hm = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values,
            x=heatmap_pivot.columns.tolist(),
            y=heatmap_pivot.index.tolist(),
            colorscale='Greens',
            hovertemplate='%{y}<br>%{x}<br>%{z:,.0f} items/hr<extra></extra>',
        ))
        fig_hm.update_layout(
            xaxis_title="Use Case",
            yaxis_title="Model",
            height=max(300, len(heatmap_pivot) * 50),
        )
        st.plotly_chart(fig_hm, use_container_width=True)
    else:
        st.info(
            "No throughput data for the selected core count. "
            "Check sidebar filters or load product use-case results."
        )

    st.markdown("### Best configuration per use case")
    st.caption("Highest req/s per use case after run aggregation (sidebar setting).")
    best_df = build_best_configs_table(df_product_view)
    if not best_df.empty:
        st.dataframe(best_df, hide_index=True, use_container_width=True)

    use_cases_available = sorted(df_product['use_case'].unique().tolist())
    active_uc = resolve_focus_use_case(
        focus_use_case, use_cases_available, 'overview_use_case'
    )
    if active_uc:
        st.markdown("### Capacity snapshot")
        st.caption(
            "Planning estimate for one use case — throughput, 10k-item runtime, "
            "and prefill/decode bottleneck if available."
        )
        uc_df = df_product_view[df_product_view['use_case'] == active_uc]
        if not uc_df.empty:
            best_idx = uc_df[METRIC_RPS].idxmax()
            best = uc_df.loc[best_idx]
            units = get_use_case_units(active_uc)
            rps = best.get(METRIC_RPS, 0) or 0
            items_hr = compute_items_per_hour(rps)
            secs_10k = compute_time_for_batch(rps, 10_000)

            prefill = best.get(PREFILL_COL, 0) or 0
            decode = best.get(DECODE_COL, 0) or 0
            bottleneck = ''
            if prefill > 0 and decode > 0:
                if decode < prefill * 0.5:
                    bottleneck = 'Decode-bound (generation is the bottleneck).'
                elif prefill < decode * 0.5:
                    bottleneck = 'Prefill-bound (prompt processing is the bottleneck).'
                else:
                    bottleneck = 'Balanced prefill/decode.'

            st.markdown(
                f"**{active_uc}** — {best['model_short']} @ "
                f"{best['cores']} cores  \n"
                f"Config: `{best.get('config_fingerprint', '')}`  \n"
                f"**{items_hr:,.0f}** {units['plural']}/hour "
                f"({format_run_stats(best)})  \n"
                f"10,000 {units['plural']} → ~**{format_duration(secs_10k)}**"
            )
            if best.get('capped_note'):
                st.caption(best['capped_note'])
            if bottleneck:
                st.caption(bottleneck)

    # --- Detail tables (collapsed by default) ---
    gaps_df = build_data_gaps_table(df_product)
    gap_label = (
        f"Data completeness & gaps ({len(gaps_df)} items)"
        if not gaps_df.empty
        else "Data completeness & gaps"
    )
    with st.expander(gap_label, expanded=False):
        st.markdown(
            "Shows configs missing **prefill/decode metrics**, **multi-core sweeps**, "
            "**full prompt counts**, or **enough repeated runs**. "
            "Use the suggested `use-case-sweep` command to fill gaps."
        )
        if not gaps_df.empty:
            st.dataframe(gaps_df, hide_index=True, use_container_width=True)
        else:
            st.success("No major data gaps for current filters.")

    with st.expander("Expected vs actual matrix", expanded=False):
        st.markdown(
            "All 11 product use cases × each model in your results. "
            "Cell = number of raw runs (0 = never benchmarked)."
        )
        expected_df = build_expected_vs_actual_matrix(df_product, all_models)
        if not expected_df.empty:
            st.dataframe(expected_df, hide_index=True, use_container_width=True)

    variance_df = build_variance_summary(df_product)
    if not variance_df.empty and (variance_df['Runs'] > 1).any():
        with st.expander("Run variance (repeatability)", expanded=False):
            st.markdown(
                f"Coefficient of variation (CV) across repeated runs. "
                f"Flagged when CV > {VARIANCE_CV_THRESHOLD * 100:.0f}% — "
                "treat those configs with caution."
            )
            st.dataframe(variance_df, hide_index=True, use_container_width=True)

    version_df = build_version_regression_table(df_product)
    if not version_df.empty:
        with st.expander("Version regression", expanded=False):
            st.markdown(
                "Compares mean req/s between the two newest vLLM versions "
                "per use case / model / cores."
            )
            st.dataframe(version_df, hide_index=True, use_container_width=True)

    trend_df = build_time_trend_data(df_product)
    if not trend_df.empty and trend_df['timestamp'].nunique() > 1:
        with st.expander("Performance over time", expanded=False):
            st.markdown(
                "Track items/hour across benchmark dates — useful after "
                "vLLM upgrades or hardware changes."
            )
            trend_configs = sorted(trend_df['config_label'].unique().tolist())
            selected_trends = st.multiselect(
                "Configs to plot:",
                trend_configs,
                default=trend_configs[: min(5, len(trend_configs))],
                key="trend_configs",
            )
            if selected_trends:
                plot_df = trend_df[trend_df['config_label'].isin(selected_trends)]
                fig_trend = go.Figure()
                for label in selected_trends:
                    sub = plot_df[plot_df['config_label'] == label]
                    fig_trend.add_trace(go.Scatter(
                        x=sub['timestamp'],
                        y=sub['items_per_hour'],
                        mode='lines+markers',
                        name=label,
                    ))
                fig_trend.update_layout(
                    xaxis_title="Timestamp",
                    yaxis_title="Items/hour",
                    height=400,
                )
                st.plotly_chart(fig_trend, use_container_width=True)

    with st.expander("Coverage matrix (runs per model@cores × use case)", expanded=False):
        st.markdown(
            "How many raw runs exist for each combination. "
            "**Green** ≥3 runs · **Yellow** 1–2 · **Gray** 0."
        )
        pivot = build_coverage_pivot(df_product)
        if not pivot.empty:
            st.dataframe(style_coverage_pivot(pivot), use_container_width=True)


def _render_use_cases_tab(
    df_product_view: pd.DataFrame,
    focus_use_case: str,
    selected_cores: List,
) -> None:
    """Capacity, planner, cache metrics, prefill/decode, model comparison."""
    _render_tab_guide('use_cases')
    use_cases_available = sorted(
        df_product_view['use_case'].unique().tolist()
    ) if not df_product_view.empty else []

    if not use_cases_available:
        st.info("No product use-case results match the current filters.")
        return

    active_uc = resolve_focus_use_case(
        focus_use_case, use_cases_available, 'usecases_use_case'
    )
    if not active_uc:
        return

    st.subheader(f"Use Case: {active_uc}")
    uc_df = df_product_view[df_product_view['use_case'] == active_uc].copy()
    units = get_use_case_units(active_uc)

    # Processing capacity
    st.markdown("**Processing capacity (items per hour)**")
    st.caption(
        "Throughput per model@cores. One bar each — if multiple configs share "
        "the same label, the best req/s is shown."
    )
    df_cap_g = collapse_by_model_cores(uc_df)
    if len(uc_df) > len(df_cap_g):
        st.caption(
            "Multiple configs share the same model@cores — "
            "showing best throughput per bar (Plotly stacks duplicate labels)."
        )

    fig_cap = go.Figure()
    error_y = None
    std_col = f'{METRIC_RPS}_std'
    if std_col in df_cap_g.columns and (df_cap_g['n_runs'].fillna(1) > 1).any():
        error_y = dict(
            type='data',
            array=df_cap_g[std_col].fillna(0).tolist(),
            visible=True,
        )
    fig_cap.add_trace(
        go.Bar(
            x=df_cap_g['config_label'],
            y=df_cap_g['items_per_hour'],
            text=df_cap_g['items_per_hour'].round(0).astype(int),
            textposition='auto',
            marker_color='#2ca02c',
            error_y=error_y,
            customdata=df_cap_g.apply(
                lambda r: format_run_stats(r), axis=1
            ),
            hovertemplate=(
                '<b>%{x}</b><br>'
                + f'{units["plural"].capitalize()}/hour: %{{y:,.0f}}<br>'
                + '%{customdata}<extra></extra>'
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

    best_rps = df_cap_g[METRIC_RPS].max()
    if best_rps > 0:
        secs_10k = compute_time_for_batch(best_rps, 10_000)
        st.info(
            f"At the best configuration, 10,000 {units['plural']} "
            f"takes ~**{format_duration(secs_10k)}**."
        )

    # Time estimates
    st.divider()
    with st.expander("Processing time estimates", expanded=True):
        st.caption(
            "Wall-clock time to finish a batch at each model@cores configuration."
        )
        batch_size = st.selectbox(
            "Batch size:",
            options=[1000, 5000, 10000, 50000, 100000],
            index=2,
            key="time_batch_size",
        )
        df_time_g = collapse_by_model_cores(uc_df)
        df_time_g['time_sec'] = df_time_g[METRIC_RPS].apply(
            lambda r: compute_time_for_batch(r, batch_size)
        )
        df_time_g['time_minutes'] = df_time_g['time_sec'] / 60.0
        df_time_g = df_time_g[df_time_g['time_sec'] < float('inf')]
        df_time_g = df_time_g.sort_values('time_minutes')

        if not df_time_g.empty:
            max_time = df_time_g['time_minutes'].max()
            if max_time >= 60:
                df_time_g['time_display'] = df_time_g['time_minutes'] / 60
                time_unit = "hours"
                time_labels = [f"{t:.1f}h" for t in df_time_g['time_display']]
            else:
                df_time_g['time_display'] = df_time_g['time_minutes']
                time_unit = "minutes"
                time_labels = [f"{t:.1f}min" for t in df_time_g['time_display']]

            fig_time = go.Figure()
            fig_time.add_trace(
                go.Bar(
                    y=df_time_g['config_label'],
                    x=df_time_g['time_display'],
                    orientation='h',
                    text=time_labels,
                    textposition='auto',
                    marker_color='#ff7f0e',
                )
            )
            fig_time.update_layout(
                xaxis_title=f"Processing Time ({time_unit})",
                yaxis_title="Configuration",
                height=max(300, len(df_time_g) * 40),
                showlegend=False,
            )
            st.plotly_chart(fig_time, use_container_width=True)

    # Workload planner
    with st.expander("Workload planner", expanded=False):
        st.markdown(
            "Enter how many items you need to process and a deadline — "
            "lists configs that meet the SLA at current throughput."
        )
        plan_col1, plan_col2, plan_col3 = st.columns(3)
        with plan_col1:
            plan_batch = st.number_input(
                "Items to process:",
                min_value=100,
                value=10000,
                step=1000,
                key="planner_batch",
            )
        with plan_col2:
            plan_hours = st.number_input(
                "Deadline (hours):",
                min_value=0.1,
                value=8.0,
                step=0.5,
                key="planner_hours",
            )
        with plan_col3:
            st.write("")
            st.write("")
            plan_clicked = st.button("Find qualifying configs", key="planner_go")

        if plan_clicked:
            qualifying = find_configs_for_deadline(
                df_product_view, active_uc, int(plan_batch), float(plan_hours)
            )
            if qualifying.empty:
                st.warning(
                    f"No configuration can process **{plan_batch:,}** "
                    f"{units['plural']} within **{plan_hours}** hours."
                )
            else:
                st.success(
                    f"**{len(qualifying)}** config(s) meet the deadline."
                )
                show_cols = {
                    'model_short': 'Model',
                    'cores': 'Cores',
                    'config_fingerprint': 'Config',
                    METRIC_RPS: 'Req/s',
                    'items_per_hour': 'Items/hr',
                    'time_display': 'Est. Time',
                }
                avail = {k: v for k, v in show_cols.items() if k in qualifying.columns}
                st.dataframe(
                    qualifying[list(avail.keys())].rename(columns=avail),
                    hide_index=True,
                    use_container_width=True,
                )

    # Prefix / KV cache (product use cases)
    kv_col = 'metric_max_kv_cache_usage_percent'
    prefix_col = 'metric_avg_prefix_cache_hit_rate_percent'
    has_cache = (
        (kv_col in uc_df.columns and (uc_df[kv_col].fillna(0) > 0).any())
        or (prefix_col in uc_df.columns and (uc_df[prefix_col].fillna(0) > 0).any())
    )
    cache_relevant = any(
        k in active_uc.lower() or e in active_uc
        for k, e in [('prefix', '📋'), ('rag', '🔍'), ('shared', '📋')]
    )
    if has_cache or cache_relevant:
        with st.expander("Cache metrics (KV & prefix)", expanded=False):
            st.caption(
                "KV-cache pressure and prefix-cache hit rate — "
                "most relevant for shared-prefix and RAG workloads."
            )
            df_cache = uc_df.copy()
            df_cache['config_label'] = (
                df_cache['model_short'] + ' @ ' + df_cache['cores'].astype(str) + 'c'
            )
            fig_cache = go.Figure()
            if kv_col in df_cache.columns and (df_cache[kv_col].fillna(0) > 0).any():
                fig_cache.add_trace(go.Bar(
                    name='KV Cache %',
                    x=df_cache['config_label'],
                    y=df_cache[kv_col].fillna(0),
                    marker_color='#9467bd',
                ))
            if prefix_col in df_cache.columns and (df_cache[prefix_col].fillna(0) > 0).any():
                fig_cache.add_trace(go.Bar(
                    name='Prefix Cache Hit %',
                    x=df_cache['config_label'],
                    y=df_cache[prefix_col].fillna(0),
                    marker_color='#17becf',
                ))
            if fig_cache.data:
                fig_cache.update_layout(
                    barmode='group',
                    yaxis_title='Percent',
                    height=350,
                )
                st.plotly_chart(fig_cache, use_container_width=True)
            elif cache_relevant:
                st.info("Cache metrics not yet captured for this use case.")

    # Prefill vs decode
    with st.expander("Prefill vs decode throughput", expanded=True):
        st.caption(
            "**Prefill** = prompt processing speed. **Decode** = generation speed. "
            "If decode is much lower, generation is the bottleneck."
        )
        has_prefill = (
            PREFILL_COL in uc_df.columns
            and (uc_df[PREFILL_COL].fillna(0) > 0).any()
        )
        if has_prefill:
            df_pd_g = collapse_by_model_cores(
                uc_df[
                    (uc_df[PREFILL_COL].fillna(0) > 0)
                    | (uc_df[DECODE_COL].fillna(0) > 0)
                ]
            )
            if not df_pd_g.empty:
                fig_pd = go.Figure()
                fig_pd.add_trace(go.Bar(
                    name='Prefill',
                    x=df_pd_g['config_label'],
                    y=df_pd_g[PREFILL_COL].fillna(0),
                    marker_color='#1f77b4',
                ))
                fig_pd.add_trace(go.Bar(
                    name='Decode',
                    x=df_pd_g['config_label'],
                    y=df_pd_g[DECODE_COL].fillna(0),
                    marker_color='#ff7f0e',
                ))
                fig_pd.update_layout(
                    barmode='group',
                    xaxis_title="Configuration",
                    yaxis_title="Throughput (tokens/sec)",
                    height=400,
                )
                st.plotly_chart(fig_pd, use_container_width=True)
        else:
            st.info(
                "Prefill/decode metrics are not in your results yet. "
                "They come from vLLM engine log lines (`Avg prompt throughput` / "
                "`Avg generation throughput`) captured during the benchmark.\n\n"
                "**If you ran before a recent fix:** engine stats were on stderr — "
                "re-run the benchmark to populate them.\n\n"
                "**Check:** `benchmark.log` in the **All Runs** tab."
            )

    # Model comparison
    if uc_df['model_short'].nunique() > 1:
        with st.expander("Model comparison", expanded=False):
            st.caption("Items/hour across models at a fixed core count.")
            mc_cores_opts = sorted(uc_df['cores'].unique().tolist())
            mc_cores = (
                st.selectbox("Core count:", mc_cores_opts, key="model_comp_cores")
                if len(mc_cores_opts) > 1
                else mc_cores_opts[0]
            )
            df_mc = collapse_by_model_cores(
                uc_df[uc_df['cores'] == mc_cores]
            )
            fig_mc = go.Figure()
            fig_mc.add_trace(go.Bar(
                x=df_mc['model_short'],
                y=df_mc['items_per_hour'],
                text=df_mc['items_per_hour'].round(0).astype(int),
                textposition='auto',
                marker_color='#1f77b4',
            ))
            fig_mc.update_layout(
                xaxis_title="Model",
                yaxis_title=f"{units['plural'].capitalize()}/hr ({mc_cores} cores)",
                height=400,
                showlegend=False,
            )
            st.plotly_chart(fig_mc, use_container_width=True)


def use_case_cli_name(use_case_display: str, slug: str = '') -> str:
    """Map dashboard use-case label to run-offline-batch-suite.sh CLI name."""
    if slug:
        return slug.replace('_', '-')
    reverse = {v: k for k, v in USE_CASE_MAP.items()}
    return reverse.get(use_case_display, use_case_display).replace('_', '-')


def build_core_availability(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize which core counts exist per use case (from raw results)."""
    if df.empty or 'cores' not in df.columns:
        return pd.DataFrame()

    if 'use_case_slug' in df.columns:
        product_df = df[~df['use_case_slug'].apply(is_technical_use_case)].copy()
    else:
        product_df = df.copy()

    if product_df.empty:
        return pd.DataFrame()

    rows = []
    for use_case, group in product_df.groupby('use_case'):
        cores = sorted(group['cores'].dropna().unique().tolist())
        rows.append({
            'use_case': use_case,
            'cores_tested': ', '.join(str(c) for c in cores),
            'core_count': len(cores),
        })
    return pd.DataFrame(rows).sort_values('use_case')


def _render_scaling_tab(
    df_product_view: pd.DataFrame,
    df_technical: pd.DataFrame,
    df_filtered: pd.DataFrame,
    focus_use_case: str,
    selected_cores: List,
) -> None:
    """Core scaling and technical benchmark sweeps."""
    _render_tab_guide('scaling')
    use_cases_available = sorted(
        df_product_view['use_case'].unique().tolist()
    ) if not df_product_view.empty else []

    st.subheader("CPU core scaling")
    st.caption(
        "Requires benchmark runs at multiple core counts (8, 16, 24, 32) "
        "for the same use case + model. Run: "
        "`use-case-sweep <use-case> all 8,16,24,32`"
    )

    core_availability = build_core_availability(df_filtered)
    if not core_availability.empty:
        with st.expander("Core counts in your results", expanded=False):
            st.dataframe(
                core_availability,
                use_container_width=True,
                hide_index=True,
            )

    if not use_cases_available:
        st.info("No product use-case results found yet.")
    elif len(selected_cores) <= 1:
        st.info(
            "Need results at **multiple core counts** (8, 16, 24, 32) to plot "
            "scaling. Your current filter has only "
            f"**{selected_cores[0] if selected_cores else 'one'}** core(s).\n\n"
            "The default `use-cases` suite runs most workloads at **16 cores** "
            "only (ETL sweeps 8–32). For scaling charts, run:\n\n"
            "```\n"
            "./run-offline-batch-suite.sh use-case-sweep <use-case> all "
            "8,16,24,32\n"
            "```"
        )
    else:
        active_uc = resolve_focus_use_case(
            focus_use_case, use_cases_available, 'scaling_use_case'
        )
        if active_uc:
            cs_models = sorted(
                df_product_view[df_product_view['use_case'] == active_uc][
                    'model_short'
                ].unique().tolist()
            )
            cs_model = st.selectbox(
                "Model:", options=cs_models, key="core_scaling_model"
            )
            df_cs = df_product_view[
                (df_product_view['use_case'] == active_uc)
                & (df_product_view['model_short'] == cs_model)
            ].copy().sort_values('cores')

            if len(df_cs) <= 1:
                raw_subset = df_filtered[
                    (df_filtered['use_case'] == active_uc)
                    & (df_filtered['model_short'] == cs_model)
                ]
                raw_cores = sorted(
                    raw_subset['cores'].dropna().unique().tolist()
                )
                slug = (
                    raw_subset['use_case_slug'].iloc[0]
                    if not raw_subset.empty
                    and 'use_case_slug' in raw_subset.columns
                    else ''
                )
                cli_name = use_case_cli_name(active_uc, slug)
                st.info(
                    f"Only **{len(raw_cores)}** core count(s) found for "
                    f"**{active_uc}** / **{cs_model}**: "
                    f"{', '.join(str(c) for c in raw_cores) or 'none'}.\n\n"
                    "Run a multi-core sweep to populate this chart:\n\n"
                    "```\n"
                    f"./run-offline-batch-suite.sh use-case-sweep "
                    f"{cli_name} all 8,16,24,32\n"
                    "```"
                )
            else:
                cs_units = get_use_case_units(active_uc)
                df_cs['items_per_hour'] = df_cs[METRIC_RPS].apply(
                    compute_items_per_hour
                )
                df_cs['tok_per_core'] = df_cs[METRIC_TOK_S] / df_cs['cores']

                fig_cs = go.Figure()
                fig_cs.add_trace(go.Scatter(
                    x=df_cs['cores'],
                    y=df_cs['items_per_hour'],
                    mode='lines+markers',
                    name=f'{cs_units["plural"].capitalize()}/hr',
                    line=dict(width=3, color='#d62728'),
                ))
                fig_cs.add_trace(go.Scatter(
                    x=df_cs['cores'],
                    y=df_cs['tok_per_core'],
                    mode='lines+markers',
                    name='Tokens/sec/core',
                    yaxis='y2',
                    line=dict(width=2, dash='dot', color='#9467bd'),
                ))
                fig_cs.update_layout(
                    xaxis_title="CPU Cores",
                    yaxis_title=f"{cs_units['plural'].capitalize()}/hr",
                    yaxis2=dict(
                        title="Tokens/sec/core",
                        overlaying='y',
                        side='right',
                    ),
                    height=400,
                )
                st.plotly_chart(fig_cs, use_container_width=True)

                eff_df = build_scaling_efficiency_table(df_cs)
                if not eff_df.empty:
                    with st.expander("Scaling efficiency table", expanded=False):
                        st.markdown(
                            "Compares actual speedup to ideal linear scaling "
                            "from the lowest core count. "
                            "**Good** ≥80% efficiency · **Poor** <50% · "
                            "**Degraded** = slower than baseline."
                        )
                        st.dataframe(
                            eff_df, hide_index=True, use_container_width=True
                        )

    if not df_technical.empty:
        with st.expander("Technical benchmark sweeps (KV, context, batch)", expanded=False):
            st.header("Technical Benchmarks")
            tech_use_cases = sorted(df_technical['use_case'].unique().tolist())

            kv_label = '📊 KV-Cache Capacity'
            if kv_label in tech_use_cases:
                st.subheader("KV-Cache Capacity")
                df_kv = df_technical[df_technical['use_case'] == kv_label].copy()
                kv_model = st.selectbox(
                    "Model:", sorted(df_kv['model_short'].unique()), key="kv_model"
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
                        METRIC_RPS: 'mean',
                        METRIC_TOK_S: 'mean',
                        **({kv_cache_col: 'mean'} if has_kv else {}),
                    })
                    .reset_index()
                    .sort_values('num_prompts')
                )
                if len(df_kv_g) > 1:
                    fig_kv = go.Figure()
                    if has_kv:
                        fig_kv.add_trace(go.Scatter(
                            x=df_kv_g['num_prompts'],
                            y=df_kv_g[kv_cache_col],
                            mode='lines+markers',
                            name='KV Cache %',
                        ))
                    fig_kv.add_trace(go.Scatter(
                        x=df_kv_g['num_prompts'],
                        y=df_kv_g[METRIC_TOK_S],
                        mode='lines+markers',
                        name='Throughput (tok/s)',
                        yaxis='y2',
                    ))
                    fig_kv.update_layout(
                        xaxis_title="Batch Size (num_prompts)",
                        yaxis2=dict(
                            title="Throughput (tokens/sec)",
                            overlaying='y',
                            side='right',
                        ),
                        height=400,
                    )
                    st.plotly_chart(fig_kv, use_container_width=True)

            ctx_label = '📏 Context Scaling'
            if ctx_label in tech_use_cases:
                st.subheader("Context Length Scaling")
                df_ctx = df_technical[df_technical['use_case'] == ctx_label].copy()
                ctx_model = st.selectbox(
                    "Model:", sorted(df_ctx['model_short'].unique()), key="ctx_model"
                )
                df_ctx = df_ctx[df_ctx['model_short'] == ctx_model]
                if 'config_input_len' in df_ctx.columns:
                    df_ctx_g = (
                        df_ctx.groupby('config_input_len')
                        .agg({METRIC_TOK_S: 'mean', METRIC_RPS: 'mean'})
                        .reset_index()
                        .sort_values('config_input_len')
                    )
                    if len(df_ctx_g) > 1:
                        fig_ctx = go.Figure()
                        fig_ctx.add_trace(go.Scatter(
                            x=df_ctx_g['config_input_len'],
                            y=df_ctx_g[METRIC_TOK_S],
                            mode='lines+markers',
                            name='Total tok/s',
                        ))
                        fig_ctx.update_layout(
                            xaxis_title="Input Length (tokens)",
                            yaxis_title="Throughput (tokens/sec)",
                            height=400,
                        )
                        st.plotly_chart(fig_ctx, use_container_width=True)

    with st.expander("Batch size scaling", expanded=False):
        st.caption("Throughput vs number of prompts when batch size was varied.")
        df_batch_candidates = df_filtered[
            df_filtered.groupby(['use_case', 'model_short', 'cores'])['num_prompts']
            .transform('nunique') > 1
        ].copy()
        if not df_batch_candidates.empty:
            batch_uc_opts = sorted(df_batch_candidates['use_case'].unique())
            batch_uc = st.selectbox(
                "Use case:", batch_uc_opts, key="batch_scaling_use_case"
            )
            batch_models = sorted(
                df_batch_candidates[df_batch_candidates['use_case'] == batch_uc][
                    'model_short'
                ].unique().tolist()
            )
            batch_model = st.selectbox(
                "Model:", batch_models, key="batch_scaling_model"
            )
            df_bs = df_batch_candidates[
                (df_batch_candidates['use_case'] == batch_uc)
                & (df_batch_candidates['model_short'] == batch_model)
            ]
            df_bs_g = (
                df_bs.groupby('num_prompts')
                .agg({METRIC_TOK_S: 'mean', METRIC_RPS: 'mean'})
                .reset_index()
                .sort_values('num_prompts')
            )
            if len(df_bs_g) > 1:
                bs_units = get_use_case_units(batch_uc)
                df_bs_g['items_per_hour'] = df_bs_g[METRIC_RPS].apply(
                    compute_items_per_hour
                )
                fig_bs = go.Figure()
                fig_bs.add_trace(go.Scatter(
                    x=df_bs_g['num_prompts'],
                    y=df_bs_g['items_per_hour'],
                    mode='lines+markers',
                    name=f'{bs_units["plural"].capitalize()}/hr',
                ))
                fig_bs.update_layout(
                    xaxis_title="Batch Size (number of prompts)",
                    yaxis_title=f"{bs_units['plural'].capitalize()} per Hour",
                    height=400,
                )
                st.plotly_chart(fig_bs, use_container_width=True)
        else:
            st.info("No batch size variation in current results.")


def _render_all_runs_tab(
    df_filtered: pd.DataFrame,
    df_product_view: pd.DataFrame,
) -> None:
    """Detailed table, comparison, log preview, exports."""
    _render_tab_guide('all_runs')
    st.subheader("All Results")

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        csv_all = build_filtered_results_csv(df_filtered)
        if csv_all:
            st.download_button(
                "⬇️ Download filtered runs (CSV)",
                csv_all,
                file_name="offline_batch_runs.csv",
                mime="text/csv",
                key="dl_all_runs",
            )
    with col_exp2:
        csv_summary = build_capacity_summary_csv(df_product_view)
        if csv_summary:
            st.download_button(
                "⬇️ Download capacity summary (CSV)",
                csv_summary,
                file_name="offline_batch_capacity_summary.csv",
                mime="text/csv",
                key="dl_capacity_summary",
            )

    if len(df_filtered) >= 2:
        with st.expander("Compare two runs side-by-side", expanded=False):
            st.caption(
                "Pick any two benchmark runs to see metric deltas and "
                "config fingerprint differences."
            )
            run_labels = df_filtered.apply(
                lambda r: (
                    f"{r['timestamp']} | {r['use_case']} | {r['model_short']} "
                    f"@ {r['cores']}c | {r.get('config_fingerprint', '')}"
                ),
                axis=1,
            ).tolist()
            cmp_col1, cmp_col2 = st.columns(2)
            with cmp_col1:
                idx_a = st.selectbox(
                    "Config A:", range(len(run_labels)),
                    format_func=lambda i: run_labels[i],
                    key="cmp_a",
                )
            with cmp_col2:
                idx_b = st.selectbox(
                    "Config B:", range(len(run_labels)),
                    format_func=lambda i: run_labels[i],
                    index=min(1, len(run_labels) - 1),
                    key="cmp_b",
                )
            row_a = df_filtered.iloc[idx_a]
            row_b = df_filtered.iloc[idx_b]
            st.dataframe(
                compare_config_rows(row_a, row_b),
                hide_index=True,
                use_container_width=True,
            )
            diffs = config_diff_notes(row_a, row_b)
            if diffs:
                st.caption("Config differences: " + '; '.join(diffs))

    if 'result_dir' in df_filtered.columns and not df_filtered.empty:
        with st.expander("Benchmark log preview", expanded=False):
            st.caption(
                "Tail of `benchmark.log` — look for `Avg prompt throughput` "
                "and error messages."
            )
            log_labels = df_filtered.apply(
                lambda r: (
                    f"{r['timestamp']} | {r['use_case']} | {r['model_short']} "
                    f"@ {r['cores']}c"
                ),
                axis=1,
            ).tolist()
            log_idx = st.selectbox(
                "Select run:", range(len(log_labels)),
                format_func=lambda i: log_labels[i],
                key="log_preview_select",
            )
            log_row = df_filtered.iloc[log_idx]
            st.code(
                tail_benchmark_log(log_row['result_dir']),
                language='text',
            )
            if 'test_run_id' in log_row.index:
                run_id = log_row['test_run_id']
                st.caption(f"Run ID: `{run_id}`")
                try:
                    st.page_link(
                        SERVER_METRICS_PAGE,
                        label="Open Server Metrics (search by Run ID)",
                        icon="🖥️",
                    )
                except Exception:
                    st.caption(
                        "Open the **Server Metrics** page and filter by this Run ID."
                    )

    with st.expander(f"Full results table ({len(df_filtered)} runs)", expanded=False):
        results_table = df_filtered.copy()
        results_table['items_per_hour'] = results_table[METRIC_RPS].apply(
            compute_items_per_hour
        )

        display_cols = {
            'timestamp': 'Timestamp',
            'use_case': 'Use Case',
            'model_short': 'Model',
            'cores': 'Cores',
            'config_fingerprint': 'Config',
            'num_prompts': 'Batch Size',
            'items_per_hour': 'Items/hr',
            METRIC_RPS: 'Req/sec',
            METRIC_TOK_S: 'Tokens/sec',
            'test_run_id': 'Run ID',
        }
        for optional, label in [
            ('config_input_len', 'Input Len'),
            ('config_output_len', 'Output Len'),
            (PREFILL_COL, 'Prefill tok/s'),
            (DECODE_COL, 'Decode tok/s'),
            ('metric_max_kv_cache_usage_percent', 'KV Cache %'),
            ('metric_total_time_sec', 'Total Time (s)'),
            ('vllm_version', 'vLLM Version'),
            ('capped_note', 'Notes'),
            ('result_dir', 'Result Path'),
        ]:
            if optional in results_table.columns:
                display_cols[optional] = label

        if 'container_image' in results_table.columns:
            results_table['container_short'] = results_table['container_image'].apply(
                lambda x: x.split('/')[-1] if isinstance(x, str) else x
            )
            display_cols['container_short'] = 'Container'

        available = {k: v for k, v in display_cols.items() if k in results_table.columns}
        display_df = results_table[list(available.keys())].copy()
        display_df.columns = list(available.values())

        for col in display_df.columns:
            if display_df[col].dtype in ['float64', 'float32']:
                display_df[col] = display_df[col].round(2)

        st.dataframe(
            display_df.sort_values(
                ['Timestamp', 'Use Case', 'Model', 'Cores'],
                ascending=[False, True, True, True],
            ),
            use_container_width=True,
            hide_index=True,
        )


def _render_export_sidebar(
    df_filtered: pd.DataFrame,
    df_product_view: pd.DataFrame,
) -> None:
    """Sidebar export section (called after data is ready)."""
    st.markdown("---")
    st.subheader("Export")
    csv_all = build_filtered_results_csv(df_filtered)
    if csv_all:
        st.download_button(
            "Filtered runs CSV",
            csv_all,
            file_name="offline_batch_runs.csv",
            mime="text/csv",
            key="sidebar_dl_runs",
        )
    csv_summary = build_capacity_summary_csv(df_product_view)
    if csv_summary:
        st.download_button(
            "Capacity summary CSV",
            csv_summary,
            file_name="offline_batch_capacity_summary.csv",
            mime="text/csv",
            key="sidebar_dl_summary",
        )


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
    st.caption(
        f"Dashboard build: **{DASHBOARD_BUILD}** — expand **ℹ️ How to read** "
        "on each tab for a feature guide."
    )
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

        with st.expander("📥 Import results", expanded=False):
            st.markdown(
                "Merge data from another machine without copying files into "
                "your main `results/llm` tree."
            )
            st.text_input(
                "Additional results directory",
                value="",
                placeholder="/path/to/other/results/llm",
                help="Optional second results/llm path to merge with the primary directory.",
                key="offline_batch_extra_dir",
            )
            uploaded_csv = st.file_uploader(
                "Upload CSV",
                type=["csv"],
                help=(
                    "Use a file exported via **All Runs → Download filtered runs**. "
                    "Required columns: Use Case, Cores, Req/sec (or Items/hr)."
                ),
                key="offline_batch_csv_upload",
            )
            if uploaded_csv is not None:
                try:
                    imported_raw = pd.read_csv(uploaded_csv)
                    imported_df = normalize_imported_offline_batch_df(imported_raw)
                    st.session_state["imported_offline_batch_df"] = imported_df
                    st.success(
                        f"✓ {len(imported_df)} row(s) from **{uploaded_csv.name}** "
                        "(merged on reload)"
                    )
                except Exception as exc:
                    st.error(f"CSV import failed: {exc}")

            if "imported_offline_batch_df" in st.session_state:
                n_imp = len(st.session_state["imported_offline_batch_df"])
                st.caption(f"{n_imp} CSV row(s) in this browser session")
                if st.button("Clear imported CSV", key="clear_offline_batch_csv"):
                    del st.session_state["imported_offline_batch_df"]
                    st.rerun()

        with st.expander("ℹ️ Sidebar controls", expanded=False):
            st.markdown(TAB_GUIDES['sidebar'])

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
                "Reference configs use full prompt counts. "
                "Capped runs (OFFLINE_BATCH_MAX_PROMPTS) show fewer prompts."
            )

    # Load data (primary dir + optional extra dir + optional CSV import)
    extra_results_dir = st.session_state.get("offline_batch_extra_dir", "").strip()
    df_disk = load_benchmark_results_from_dirs(
        results_dir_input,
        extra_results_dir,
    )
    imported_count = 0
    if "imported_offline_batch_df" in st.session_state:
        imported_df = st.session_state["imported_offline_batch_df"]
        imported_count = len(imported_df)
        df = merge_benchmark_dataframes(df_disk, imported_df)
    else:
        df = df_disk

    if df.empty:
        st.warning("No benchmark results found.")
        st.info(
            "**Load results:** set **Results Directory** to your `results/llm` path, "
            "add an **Additional results directory**, or **Import CSV** in the sidebar "
            "(export from **All Runs → Download filtered runs**)."
        )
        st.code(
            "# Run a benchmark (from repository root):\n"
            "./cpueval --suite offline-batch\n"
            "./cpueval --suite offline-batch --mode use-cases --runs 5 --models all\n"
            "\n"
            "# Or via bash script:\n"
            "cd automation/test-execution/scripts/bash\n"
            "./run-offline-batch-suite.sh use-cases 5 all\n"
            "./run-offline-batch-suite.sh run_test all sonnet 1000 16\n"
            "\n"
            "# Or single test via Ansible:\n"
            "cd automation/test-execution\n"
            "ansible-playbook -i ansible/inventory/hosts.yml "
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

    disk_count = len(df_disk)
    msg = f"Loaded {len(df)} benchmark results ({disk_count} from disk"
    if imported_count:
        msg += f", {imported_count} from CSV"
    msg += ")"
    st.success(msg)

    # Short model names (if not already set by merge)
    if 'model_short' not in df.columns:
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

        st.markdown("---")
        st.subheader("Analysis")

        run_aggregation = st.selectbox(
            "Run aggregation",
            options=list(RUN_AGGREGATION_MODES),
            index=1,
            help=(
                "How to collapse multiple runs of the same configuration: "
                "latest, mean, or best throughput."
            ),
            key="global_run_agg",
        )

        hide_capped = st.checkbox(
            "Hide capped runs",
            value=False,
            help="Exclude runs with prompt counts below full-suite reference.",
            key="global_hide_capped",
        )
        min_runs = st.slider(
            "Minimum runs per config",
            min_value=1,
            max_value=10,
            value=1,
            help="Filter out configurations with fewer than N raw runs.",
            key="global_min_runs",
        )

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

    _render_environment_banner(df_filtered)

    df_filtered['_is_technical'] = df_filtered['use_case_slug'].apply(
        is_technical_use_case
    )
    df_product = df_filtered[~df_filtered['_is_technical']].copy()
    df_technical = df_filtered[df_filtered['_is_technical']].copy()

    df_product = apply_quality_filters(
        df_product, hide_capped=hide_capped, min_runs=min_runs
    )
    if df_product.empty and not df_technical.empty:
        st.warning(
            "All product use-case runs were filtered out. "
            "Try disabling **Hide capped runs** or lowering **Minimum runs**."
        )

    df_product_view = apply_run_aggregation(df_product, run_aggregation)
    all_models = sorted(df['model_short'].unique().tolist())

    product_use_cases = sorted(df_product['use_case'].unique().tolist())
    with st.sidebar:
        focus_use_case = st.selectbox(
            "Focus use case",
            options=['All'] + product_use_cases,
            help="Pin a use case across tabs, or pick per tab with All.",
            key="global_focus_uc",
        )
        _render_export_sidebar(df_filtered, df_product_view)

    tab_overview, tab_use_cases, tab_scaling, tab_runs = st.tabs([
        "Overview",
        "Use Cases",
        "Scaling",
        "All Runs",
    ])

    with tab_overview:
        _render_overview_tab(
            df_product, df_product_view, focus_use_case, all_models
        )

    with tab_use_cases:
        _render_use_cases_tab(
            df_product_view, focus_use_case, selected_cores
        )

    with tab_scaling:
        _render_scaling_tab(
            df_product_view,
            df_technical,
            df_filtered,
            focus_use_case,
            selected_cores,
        )

    with tab_runs:
        _render_all_runs_tab(df_filtered, df_product_view)


if __name__ == "__main__":
    main()
