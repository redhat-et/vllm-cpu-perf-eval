#!/usr/bin/env python3
"""Unit tests for analyze_repeatability.py.

Run with: python -m pytest test_repeatability.py -v
Or without pytest: python3 test_repeatability.py
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    # Mock pytest for fallback tests
    class pytest:
        class raises:
            def __init__(self, exc):
                self.exc = exc

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

import numpy as np
from analyze_repeatability import (
    calculate_cv,
    get_repeatability_grade,
    get_letter_grade,
    get_nested_value,
    analyze_metric_repeatability,
    CV_THRESHOLDS,
)


class TestCalculateCV:
    """Test calculate_cv function."""

    def test_perfect_repeatability(self):
        """CV should be 0 for identical values."""
        values = [100.0, 100.0, 100.0]
        cv = calculate_cv(values)
        assert cv == 0.0, f"Expected CV=0.0, got {cv}"

    def test_known_cv_value(self):
        """Test CV calculation with known values."""
        # Values: [10, 12, 14] -> mean=12, std≈2, CV≈16.67%
        values = [10.0, 12.0, 14.0]
        cv = calculate_cv(values)
        expected = (np.std(values, ddof=1) / np.mean(values)) * 100
        assert abs(cv - expected) < 0.01, f"Expected CV≈{expected:.2f}, got {cv:.2f}"
        assert abs(cv - 16.67) < 0.1, f"Expected CV≈16.67%, got {cv:.2f}%"

    def test_single_value_returns_nan(self):
        """CV should be NaN for single value."""
        values = [100.0]
        cv = calculate_cv(values)
        assert np.isnan(cv), "Expected NaN for single value"

    def test_empty_list_returns_nan(self):
        """CV should be NaN for empty list."""
        values = []
        cv = calculate_cv(values)
        assert np.isnan(cv), "Expected NaN for empty list"

    def test_zero_mean_returns_nan(self):
        """CV should be NaN when mean is zero."""
        values = [0.0, 0.0, 0.0]
        cv = calculate_cv(values)
        assert np.isnan(cv), "Expected NaN for zero mean"

    def test_two_values_minimum(self):
        """CV should work with exactly 2 values."""
        values = [10.0, 12.0]
        cv = calculate_cv(values)
        assert not np.isnan(cv), "Should calculate CV for 2 values"
        # mean=11, std≈1.414, CV≈12.86%
        assert abs(cv - 12.86) < 0.1, f"Expected CV≈12.86%, got {cv:.2f}%"

    def test_high_variance(self):
        """Test CV with high variance."""
        values = [1.0, 100.0, 200.0]
        cv = calculate_cv(values)
        assert cv > 50, f"Expected high CV (>50%), got {cv:.2f}%"

    def test_low_variance(self):
        """Test CV with low variance (good repeatability)."""
        values = [100.0, 100.5, 99.5]
        cv = calculate_cv(values)
        assert cv < 1, f"Expected low CV (<1%), got {cv:.2f}%"


class TestGetRepeatabilityGrade:
    """Test get_repeatability_grade function."""

    def test_excellent_grade(self):
        """CV < 1% should be Excellent."""
        assert get_repeatability_grade(0.5) == 'Excellent'
        assert get_repeatability_grade(0.99) == 'Excellent'

    def test_good_grade(self):
        """CV 1-3% should be Good."""
        assert get_repeatability_grade(1.0) == 'Good'
        assert get_repeatability_grade(2.0) == 'Good'
        assert get_repeatability_grade(2.99) == 'Good'

    def test_acceptable_grade(self):
        """CV 3-5% should be Acceptable."""
        assert get_repeatability_grade(3.0) == 'Acceptable'
        assert get_repeatability_grade(4.0) == 'Acceptable'
        assert get_repeatability_grade(4.99) == 'Acceptable'

    def test_poor_grade(self):
        """CV > 5% should be Poor."""
        assert get_repeatability_grade(5.0) == 'Poor'
        assert get_repeatability_grade(10.0) == 'Poor'
        assert get_repeatability_grade(100.0) == 'Poor'

    def test_nan_returns_na(self):
        """NaN CV should return 'N/A'."""
        assert get_repeatability_grade(np.nan) == 'N/A'

    def test_threshold_boundaries(self):
        """Test exact threshold boundaries."""
        assert get_repeatability_grade(CV_THRESHOLDS['excellent'] - 0.01) == 'Excellent'
        assert get_repeatability_grade(CV_THRESHOLDS['excellent']) == 'Good'
        assert get_repeatability_grade(CV_THRESHOLDS['good'] - 0.01) == 'Good'
        assert get_repeatability_grade(CV_THRESHOLDS['good']) == 'Acceptable'


class TestGetLetterGrade:
    """Test get_letter_grade function."""

    def test_a_plus_grade(self):
        """CV < 0.5% should be A+."""
        assert get_letter_grade(0.0) == 'A+'
        assert get_letter_grade(0.49) == 'A+'

    def test_a_grade(self):
        """CV 0.5-1% should be A."""
        assert get_letter_grade(0.5) == 'A'
        assert get_letter_grade(0.99) == 'A'

    def test_a_minus_grade(self):
        """CV 1-2% should be A-."""
        assert get_letter_grade(1.0) == 'A-'
        assert get_letter_grade(1.99) == 'A-'

    def test_b_plus_grade(self):
        """CV 2-3% should be B+."""
        assert get_letter_grade(2.0) == 'B+'
        assert get_letter_grade(2.99) == 'B+'

    def test_b_grade(self):
        """CV 3-5% should be B."""
        assert get_letter_grade(3.0) == 'B'
        assert get_letter_grade(4.99) == 'B'

    def test_b_minus_grade(self):
        """CV 5-7.5% should be B-."""
        assert get_letter_grade(5.0) == 'B-'
        assert get_letter_grade(7.49) == 'B-'

    def test_c_grade(self):
        """CV >= 7.5% should be C."""
        assert get_letter_grade(7.5) == 'C'
        assert get_letter_grade(10.0) == 'C'
        assert get_letter_grade(100.0) == 'C'

    def test_nan_returns_na(self):
        """NaN should return 'N/A'."""
        assert get_letter_grade(np.nan) == 'N/A'


class TestGetNestedValue:
    """Test get_nested_value function."""

    def test_simple_nested_path(self):
        """Test extracting value from nested dict."""
        data = {'a': {'b': {'c': 42}}}
        value = get_nested_value(data, ['a', 'b', 'c'])
        assert value == 42

    def test_single_level_path(self):
        """Test single-level path."""
        data = {'key': 'value'}
        value = get_nested_value(data, ['key'])
        assert value == 'value'

    def test_missing_key_returns_default(self):
        """Test missing key returns default."""
        data = {'a': {'b': 1}}
        value = get_nested_value(data, ['a', 'c'], default='missing')
        assert value == 'missing'

    def test_missing_key_returns_none(self):
        """Test missing key returns None by default."""
        data = {'a': {'b': 1}}
        value = get_nested_value(data, ['x', 'y'])
        assert value is None

    def test_partial_path_exists(self):
        """Test when path exists partially."""
        data = {'a': {'b': 1}}
        value = get_nested_value(data, ['a', 'b', 'c'], default='default')
        assert value == 'default'

    def test_non_dict_in_path(self):
        """Test when non-dict encountered in path."""
        data = {'a': 'string_value'}
        value = get_nested_value(data, ['a', 'b'], default='default')
        assert value == 'default'

    def test_empty_path(self):
        """Test with empty path."""
        data = {'a': 1}
        value = get_nested_value(data, [])
        assert value == data


class TestAnalyzeMetricRepeatability:
    """Test analyze_metric_repeatability function."""

    def test_basic_analysis(self):
        """Test basic repeatability analysis."""
        # Create mock runs
        runs = [
            {
                'benchmark': {
                    'metrics': {
                        'request_latency': {
                            'successful': {
                                'mean': 10.0,
                                'percentiles': {'p90': 12.0, 'p95': 13.0}
                            }
                        }
                    }
                }
            },
            {
                'benchmark': {
                    'metrics': {
                        'request_latency': {
                            'successful': {
                                'mean': 10.5,
                                'percentiles': {'p90': 12.5, 'p95': 13.5}
                            }
                        }
                    }
                }
            },
            {
                'benchmark': {
                    'metrics': {
                        'request_latency': {
                            'successful': {
                                'mean': 9.5,
                                'percentiles': {'p90': 11.5, 'p95': 12.5}
                            }
                        }
                    }
                }
            }
        ]

        metric_config = {
            'path': ['metrics', 'request_latency', 'successful', 'mean'],
            'percentiles': ['p90', 'p95']
        }

        result = analyze_metric_repeatability(runs, metric_config)

        # Check mean stats
        assert 'mean' in result
        assert abs(result['mean']['value'] - 10.0) < 0.1
        assert result['mean']['n_runs'] == 3
        assert not np.isnan(result['mean']['cv'])
        assert result['mean']['grade'] in ['Excellent', 'Good', 'Acceptable', 'Poor']

        # Check percentile stats
        assert 'p90' in result
        assert 'p95' in result
        assert abs(result['p90']['value'] - 12.0) < 0.1
        assert abs(result['p95']['value'] - 13.0) < 0.1

    def test_single_run_returns_nan(self):
        """Test that single run returns NaN for CV."""
        runs = [
            {
                'benchmark': {
                    'metrics': {
                        'tokens_per_second': {
                            'successful': {'mean': 100.0}
                        }
                    }
                }
            }
        ]

        metric_config = {
            'path': ['metrics', 'tokens_per_second', 'successful', 'mean'],
            'percentiles': []
        }

        result = analyze_metric_repeatability(runs, metric_config)

        assert result['mean']['n_runs'] == 1
        assert np.isnan(result['mean']['cv'])
        assert np.isnan(result['mean']['std'])
        assert result['mean']['grade'] == 'N/A'

    def test_missing_metric_data(self):
        """Test handling of missing metric data."""
        runs = [
            {'benchmark': {}},
            {'benchmark': {}}
        ]

        metric_config = {
            'path': ['metrics', 'nonexistent', 'mean'],
            'percentiles': []
        }

        result = analyze_metric_repeatability(runs, metric_config)

        assert result['mean']['n_runs'] == 0
        assert np.isnan(result['mean']['value'])

    def test_excellent_repeatability(self):
        """Test detection of excellent repeatability."""
        # Very small variance
        runs = [
            {'benchmark': {'metrics': {'test': {'mean': 100.0}}}},
            {'benchmark': {'metrics': {'test': {'mean': 100.1}}}},
            {'benchmark': {'metrics': {'test': {'mean': 99.9}}}}
        ]

        metric_config = {
            'path': ['metrics', 'test', 'mean'],
            'percentiles': []
        }

        result = analyze_metric_repeatability(runs, metric_config)

        assert result['mean']['cv'] < 1.0
        assert result['mean']['grade'] == 'Excellent'

    def test_poor_repeatability(self):
        """Test detection of poor repeatability."""
        # High variance
        runs = [
            {'benchmark': {'metrics': {'test': {'mean': 50.0}}}},
            {'benchmark': {'metrics': {'test': {'mean': 100.0}}}},
            {'benchmark': {'metrics': {'test': {'mean': 150.0}}}}
        ]

        metric_config = {
            'path': ['metrics', 'test', 'mean'],
            'percentiles': []
        }

        result = analyze_metric_repeatability(runs, metric_config)

        assert result['mean']['cv'] > 5.0
        assert result['mean']['grade'] == 'Poor'


def run_tests_manually():
    """Run tests manually without pytest."""
    print("Running repeatability tests manually...")

    test_classes = [
        TestCalculateCV,
        TestGetRepeatabilityGrade,
        TestGetLetterGrade,
        TestGetNestedValue,
        TestAnalyzeMetricRepeatability
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        test_instance = test_class()
        test_methods = [m for m in dir(test_instance) if m.startswith('test_')]

        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(test_instance, method_name)
                method()
                print(f"  ✓ {method_name}")
                passed_tests += 1
            except AssertionError as e:
                print(f"  ✗ {method_name}: {e}")
                failed_tests.append((test_class.__name__, method_name, str(e)))
            except Exception as e:
                print(f"  ✗ {method_name}: Unexpected error: {e}")
                failed_tests.append((test_class.__name__, method_name, str(e)))

    print(f"\n{'='*60}")
    print(f"Results: {passed_tests}/{total_tests} tests passed")

    if failed_tests:
        print(f"\nFailed tests:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}: {error}")
        return 1
    else:
        print("\n✓ All tests passed!")
        return 0


if __name__ == '__main__':
    if HAS_PYTEST:
        print("Running tests with pytest...")
        sys.exit(pytest.main([__file__, '-v']))
    else:
        print("pytest not found, running tests manually...")
        sys.exit(run_tests_manually())
