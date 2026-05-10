"""Repeatability analysis utilities for dashboard integration.

This module provides functions to calculate and display Coefficient of Variation (CV)
metrics for benchmark repeatability analysis within the dashboard.
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


# Repeatability grade thresholds
CV_THRESHOLDS = {
    'excellent': 1.0,  # CV < 1%
    'good': 3.0,       # CV 1-3%
    'acceptable': 5.0,  # CV 3-5%
    # CV > 5% is 'poor'
}


def calculate_cv(values: pd.Series) -> float:
    """Calculate coefficient of variation as percentage.

    Args:
        values: Pandas Series of numeric values

    Returns:
        CV as percentage, or NaN if calculation not possible
    """
    if len(values) < 2:
        return np.nan

    mean = values.mean()
    if mean == 0:
        return np.nan

    std = values.std(ddof=1)  # Sample standard deviation
    return (std / mean) * 100


def get_repeatability_grade(cv: float) -> str:
    """Assign repeatability grade based on CV value.

    Args:
        cv: Coefficient of variation as percentage

    Returns:
        Grade string: 'Excellent', 'Good', 'Acceptable', or 'Poor'
    """
    if np.isnan(cv):
        return 'N/A'

    if cv < CV_THRESHOLDS['excellent']:
        return 'Excellent'
    elif cv < CV_THRESHOLDS['good']:
        return 'Good'
    elif cv < CV_THRESHOLDS['acceptable']:
        return 'Acceptable'
    else:
        return 'Poor'


def get_grade_color(grade: str) -> str:
    """Get color for repeatability grade.

    Args:
        grade: Repeatability grade string

    Returns:
        Color string for Streamlit styling
    """
    grade_colors = {
        'Excellent': 'green',
        'Good': 'blue',
        'Acceptable': 'orange',
        'Poor': 'red',
        'N/A': 'gray'
    }
    return grade_colors.get(grade, 'gray')


def calculate_repeatability_metrics(
    df: pd.DataFrame,
    group_cols: List[str],
    metric_cols: List[str]
) -> pd.DataFrame:
    """Calculate repeatability metrics for grouped data.

    Args:
        df: DataFrame with benchmark results
        group_cols: Columns to group by (e.g., ['platform', 'cores', 'concurrency'])
        metric_cols: Metric columns to analyze (e.g., ['ttft_mean', 'throughput_mean'])

    Returns:
        DataFrame with CV metrics and grades for each group
    """
    results = []

    # Group data
    grouped = df.groupby(group_cols)

    for group_name, group_df in grouped:
        if len(group_df) < 2:
            # Need at least 2 runs for CV calculation
            continue

        row = {}

        # Add group identifiers
        if isinstance(group_name, tuple):
            for col, val in zip(group_cols, group_name):
                row[col] = val
        else:
            row[group_cols[0]] = group_name

        # Calculate CV for each metric
        for metric_col in metric_cols:
            if metric_col not in group_df.columns:
                continue

            values = group_df[metric_col].dropna()
            if len(values) < 2:
                continue

            cv = calculate_cv(values)
            grade = get_repeatability_grade(cv)

            row[f'{metric_col}_mean'] = values.mean()
            row[f'{metric_col}_std'] = values.std(ddof=1)
            row[f'{metric_col}_cv'] = cv
            row[f'{metric_col}_grade'] = grade
            row[f'{metric_col}_n_runs'] = len(values)

        if row:
            results.append(row)

    return pd.DataFrame(results) if results else pd.DataFrame()


def format_metric_with_cv(value: float, cv: float, unit: str = '') -> str:
    """Format a metric value with its CV percentage.

    Args:
        value: Metric value
        cv: Coefficient of variation (%)
        unit: Unit string (e.g., 'ms', 's', 'tok/s')

    Returns:
        Formatted string like "123.4ms (±2.1%)"
    """
    if np.isnan(value) or np.isnan(cv):
        return 'N/A'

    # Format value based on magnitude
    if abs(value) >= 1000:
        value_str = f"{value:.0f}"
    elif abs(value) >= 100:
        value_str = f"{value:.1f}"
    else:
        value_str = f"{value:.2f}"

    return f"{value_str}{unit} (±{cv:.2f}%)"


def get_repeatability_summary(cv_df: pd.DataFrame, metric_col: str) -> Dict[str, any]:
    """Get summary statistics for a metric's repeatability.

    Args:
        cv_df: DataFrame with CV metrics (from calculate_repeatability_metrics)
        metric_col: Base metric column name (e.g., 'ttft_mean')

    Returns:
        Dictionary with summary statistics
    """
    cv_col = f'{metric_col}_cv'

    if cv_col not in cv_df.columns:
        return {
            'available': False
        }

    cv_values = cv_df[cv_col].dropna()

    if len(cv_values) == 0:
        return {
            'available': False
        }

    # Count by grade
    grade_col = f'{metric_col}_grade'
    grade_counts = cv_df[grade_col].value_counts().to_dict() if grade_col in cv_df.columns else {}

    return {
        'available': True,
        'mean_cv': cv_values.mean(),
        'median_cv': cv_values.median(),
        'min_cv': cv_values.min(),
        'max_cv': cv_values.max(),
        'n_configs': len(cv_values),
        'grade_counts': grade_counts,
        'overall_grade': get_repeatability_grade(cv_values.mean())
    }


def create_repeatability_comparison_table(
    cv_df: pd.DataFrame,
    group_col: str,
    metric_cols: List[str],
    metric_names: Dict[str, str] = None
) -> pd.DataFrame:
    """Create a comparison table showing repeatability across configurations.

    Args:
        cv_df: DataFrame with CV metrics
        group_col: Column to compare (e.g., 'cores', 'platform')
        metric_cols: List of metric columns to include
        metric_names: Optional dict mapping metric_col to display name

    Returns:
        DataFrame formatted for display
    """
    if metric_names is None:
        metric_names = {col: col for col in metric_cols}

    rows = []

    for group_value in sorted(cv_df[group_col].unique()):
        group_data = cv_df[cv_df[group_col] == group_value]

        row = {group_col: group_value}

        for metric_col in metric_cols:
            cv_col = f'{metric_col}_cv'
            grade_col = f'{metric_col}_grade'

            if cv_col in group_data.columns:
                # Average CV for this group
                avg_cv = group_data[cv_col].mean()
                row[metric_names[metric_col]] = f"{avg_cv:.2f}%"

                if grade_col in group_data.columns:
                    # Most common grade
                    grades = group_data[grade_col].mode()
                    if len(grades) > 0:
                        row[f'{metric_names[metric_col]}_grade'] = grades[0]

        rows.append(row)

    return pd.DataFrame(rows)


def filter_by_repeatability(
    df: pd.DataFrame,
    cv_df: pd.DataFrame,
    min_runs: int = 2,
    max_cv: float = None,
    required_grade: str = None
) -> pd.DataFrame:
    """Filter benchmark results to only include repeatable configurations.

    Args:
        df: Original benchmark DataFrame
        cv_df: DataFrame with CV metrics
        min_runs: Minimum number of runs required
        max_cv: Maximum acceptable CV (%)
        required_grade: Minimum grade ('Excellent', 'Good', 'Acceptable')

    Returns:
        Filtered DataFrame
    """
    # Get configurations that meet criteria
    valid_configs = cv_df.copy()

    # Filter by number of runs
    run_cols = [col for col in valid_configs.columns if col.endswith('_n_runs')]
    if run_cols:
        for col in run_cols:
            valid_configs = valid_configs[valid_configs[col] >= min_runs]

    # Filter by CV threshold
    if max_cv is not None:
        cv_cols = [col for col in valid_configs.columns if col.endswith('_cv')]
        for col in cv_cols:
            valid_configs = valid_configs[valid_configs[col] <= max_cv]

    # Filter by grade
    if required_grade is not None:
        grade_order = ['Excellent', 'Good', 'Acceptable', 'Poor']
        min_grade_idx = grade_order.index(required_grade)

        grade_cols = [col for col in valid_configs.columns if col.endswith('_grade')]
        for col in grade_cols:
            valid_configs = valid_configs[
                valid_configs[col].apply(
                    lambda g: grade_order.index(g) <= min_grade_idx if g in grade_order else False
                )
            ]

    # Get group columns (exclude metric columns)
    metric_suffixes = ['_mean', '_std', '_cv', '_grade', '_n_runs']
    group_cols = [
        col for col in valid_configs.columns
        if not any(col.endswith(suffix) for suffix in metric_suffixes)
    ]

    # Merge back with original data
    if group_cols:
        return df.merge(valid_configs[group_cols], on=group_cols, how='inner')
    else:
        return df


def add_cv_annotations_to_plot(
    fig,
    cv_df: pd.DataFrame,
    metric_col: str,
    x_col: str,
    trace_names: List[str]
) -> None:
    """Add CV annotations to a Plotly figure.

    Args:
        fig: Plotly figure object
        cv_df: DataFrame with CV metrics
        metric_col: Metric column name
        x_col: X-axis column name
        trace_names: List of trace names in the figure
    """
    cv_col = f'{metric_col}_cv'

    if cv_col not in cv_df.columns:
        return

    # Add annotations for each configuration
    annotations = []

    for _, row in cv_df.iterrows():
        if x_col in row and cv_col in row:
            cv = row[cv_col]
            if not np.isnan(cv):
                # Create annotation
                annotations.append({
                    'x': row[x_col],
                    'y': row[f'{metric_col}_mean'] if f'{metric_col}_mean' in row else 0,
                    'text': f'CV: {cv:.1f}%',
                    'showarrow': True,
                    'arrowhead': 2,
                    'arrowsize': 1,
                    'arrowwidth': 1,
                    'arrowcolor': get_grade_color(row.get(f'{metric_col}_grade', 'N/A')),
                    'font': {'size': 10},
                    'bgcolor': 'white',
                    'borderpad': 2
                })

    if annotations:
        fig.update_layout(annotations=annotations)
