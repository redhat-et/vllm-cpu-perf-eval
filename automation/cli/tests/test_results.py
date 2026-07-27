"""Tests for results.py metrics extraction."""

import pytest
from cpueval.results import extract_metrics


def test_extract_metrics_guidellm_v06():
    """Test metrics extraction with GuideLLM v0.6+ format."""
    benchmarks = {
        "benchmarks": [
            {
                "config": {
                    "strategy": {"max_concurrency": 8}
                },
                "metrics": {
                    "requests_per_second": {
                        "successful": {"mean": 0.20}
                    },
                    "tokens_per_second": {
                        "successful": {"mean": 283.42}
                    },
                    "time_to_first_token_ms": {
                        "successful": {"mean": 12262.48}
                    },
                    "time_per_output_token_ms": {
                        "successful": {"mean": 78.87}
                    },
                    "request_totals": {
                        "successful": 56,
                        "total": 56
                    }
                }
            }
        ]
    }

    result = extract_metrics(benchmarks)

    assert len(result) == 1
    assert result[0]["concurrency"] == 8
    assert result[0]["req_per_sec"] == 0.20
    assert result[0]["tok_per_sec"] == 283.42
    assert result[0]["ttft_ms"] == 12262.48
    assert result[0]["tpot_ms"] == 78.87
    assert result[0]["ok_requests"] == 56
    assert result[0]["total_requests"] == 56


def test_extract_metrics_multiple_concurrency():
    """Test that ALL concurrency points are extracted."""
    benchmarks = {
        "benchmarks": [
            {
                "config": {"strategy": {"max_concurrency": 2}},
                "metrics": {
                    "requests_per_second": {"successful": {"mean": 1.5}},
                    "request_totals": {"successful": 10, "total": 10}
                }
            },
            {
                "config": {"strategy": {"max_concurrency": 4}},
                "metrics": {
                    "requests_per_second": {"successful": {"mean": 2.8}},
                    "request_totals": {"successful": 20, "total": 20}
                }
            },
            {
                "config": {"strategy": {"max_concurrency": 8}},
                "metrics": {
                    "requests_per_second": {"successful": {"mean": 4.2}},
                    "request_totals": {"successful": 30, "total": 30}
                }
            }
        ]
    }

    result = extract_metrics(benchmarks)

    assert len(result) == 3
    assert result[0]["concurrency"] == 2
    assert result[1]["concurrency"] == 4
    assert result[2]["concurrency"] == 8


def test_extract_metrics_fallback_field_names():
    """Test fallback to alternative field names."""
    benchmarks = {
        "benchmarks": [
            {
                "config": {"strategy": {"streams": 5}},
                "metrics": {
                    "output_tokens_per_second": {"successful": {"mean": 100.0}},
                    "inter_token_latency_ms": {"successful": {"mean": 50.0}},
                    "request_totals": {"successful": 10, "total": 10}
                }
            }
        ]
    }

    result = extract_metrics(benchmarks)

    assert len(result) == 1
    assert result[0]["concurrency"] == 5  # From streams fallback
    assert result[0]["tok_per_sec"] == 100.0  # Fallback field
    assert result[0]["tpot_ms"] == 50.0  # Fallback field


def test_extract_metrics_empty():
    """Test graceful handling of empty benchmarks."""
    assert extract_metrics({}) == []
    assert extract_metrics({"benchmarks": []}) == []


def test_extract_metrics_missing_fields():
    """Test graceful handling of missing fields."""
    benchmarks = {
        "benchmarks": [
            {
                "config": {"strategy": {"max_concurrency": 8}},
                "metrics": {
                    "request_totals": {"successful": 5, "total": 5}
                }
            }
        ]
    }

    result = extract_metrics(benchmarks)

    assert len(result) == 1
    assert result[0]["concurrency"] == 8
    assert result[0]["req_per_sec"] is None
    assert result[0]["tok_per_sec"] is None
    assert result[0]["ok_requests"] == 5
