"""Unit tests for load_lm_eval_data() in 6_🎯_LM_Eval.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PAGES_DIR = Path(__file__).parent.parent / "pages"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "lm-eval"


@pytest.fixture(scope="module")
def lm_eval_page():
    page_file = PAGES_DIR / "6_🎯_LM_Eval.py"
    spec = importlib.util.spec_from_file_location("lm_eval_page", page_file)
    mod = importlib.util.module_from_spec(spec)
    parent = str(PAGES_DIR.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def load_lm_eval_data(lm_eval_page):
    return lm_eval_page.load_lm_eval_data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_directory_returns_empty_dataframe(tmp_path, load_lm_eval_data):
    """Empty results directory → empty DataFrame, no exception."""
    df = load_lm_eval_data(str(tmp_path))
    assert df.empty


def test_nonexistent_directory_returns_empty_dataframe(load_lm_eval_data):
    """Non-existent path → empty DataFrame."""
    df = load_lm_eval_data("/tmp/this-path-does-not-exist-cpueval-test")
    assert df.empty


def test_fixture_loads_correct_row_count(load_lm_eval_data):
    """Fixture with 2 tasks × 1 run → 2 rows."""
    df = load_lm_eval_data(str(FIXTURE_DIR))
    assert not df.empty
    # Fixture has hellaswag + arc_easy for one model/run
    assert len(df) == 2


def test_fixture_has_required_columns(load_lm_eval_data):
    """DataFrame must contain the columns the dashboard relies on."""
    df = load_lm_eval_data(str(FIXTURE_DIR))
    required = {"model", "model_short", "cores", "platform", "task", "task_label"}
    assert required.issubset(set(df.columns))


def test_model_slug_restored_to_slash_form(load_lm_eval_data):
    """meta-llama__Llama-3-2-1B-Instruct directory → model with '/' separator."""
    df = load_lm_eval_data(str(FIXTURE_DIR))
    # Loader replaces __ with / to restore the original HuggingFace model ID
    assert df["model"].str.contains("/").all()


def test_accuracy_metric_present(load_lm_eval_data):
    """acc,none column is present and values are in [0, 1]."""
    df = load_lm_eval_data(str(FIXTURE_DIR))
    assert "acc,none" in df.columns
    assert df["acc,none"].between(0.0, 1.0).all()


def test_cores_from_metadata(load_lm_eval_data):
    """requested_cores from metadata is surfaced as integer cores column."""
    df = load_lm_eval_data(str(FIXTURE_DIR))
    assert (df["cores"] == 16).all()


def test_gsm8k_default_metric_uses_exact_match(lm_eval_page):
    """GSM8K-only frames should default to flexible exact match, not acc."""
    import pandas as pd

    df = pd.DataFrame(
        [{
            "task": "gsm8k",
            "exact_match,flexible-extract": 0.25,
            "exact_match,strict-match": 0.1,
        }]
    )
    available = lm_eval_page._available_metrics(df)
    assert lm_eval_page._default_metric(df, available) == "exact_match,flexible-extract"


def test_gsm8k_score_fallback_when_accuracy_selected(lm_eval_page):
    """Selecting acc,none should still surface GSM8K exact-match scores."""
    import pandas as pd

    df = pd.DataFrame(
        [{
            "task": "gsm8k",
            "task_label": "GSM8K",
            "exact_match,flexible-extract": 0.39,
            "exact_match_stderr,flexible-extract": 0.02,
        }]
    )
    scored = lm_eval_page._with_effective_scores(df, "acc,none")
    assert scored.iloc[0]["score"] == pytest.approx(0.39)
    assert scored.iloc[0]["effective_metric"] == "exact_match,flexible-extract"


def test_task_score_pivot_uses_task_labels_not_metric_name(lm_eval_page):
    """Heatmap columns must be task names, not the score column label."""
    import pandas as pd

    df = pd.DataFrame(
        [
            {"model": "org/a", "task_label": "GSM8K", "score": 0.25},
            {"model": "org/a", "task_label": "ARC-Easy", "score": 0.70},
            {"model": "org/b", "task_label": "GSM8K", "score": 0.40},
            {"model": "org/b", "task_label": "ARC-Easy", "score": 0.60},
        ]
    )
    pivot = lm_eval_page._task_score_pivot(df)
    assert list(pivot.columns) == ["ARC-Easy", "GSM8K"]
    assert pivot.loc["org/a", "GSM8K"] == pytest.approx(0.25)


def test_stderr_col_maps_exact_match_metrics(lm_eval_page):
    """stderr column helper must handle GSM8K exact-match metric names."""
    assert (
        lm_eval_page._stderr_col("exact_match,flexible-extract")
        == "exact_match_stderr,flexible-extract"
    )
    assert lm_eval_page._stderr_col("acc,none") == "acc_stderr,none"
    assert lm_eval_page._stderr_col("unknown-metric") is None


def test_directory_without_metadata_is_skipped(tmp_path, load_lm_eval_data):
    """Run directories without test-metadata.json are silently skipped."""
    model_dir = tmp_path / "some-model"
    run_dir = model_dir / "run-20260101-000000"
    run_dir.mkdir(parents=True)
    # Write results JSON but no test-metadata.json
    results = {"results": {"hellaswag": {"acc,none": 0.5}}}
    (run_dir / "results_20260101.json").write_text(json.dumps(results))

    df = load_lm_eval_data(str(tmp_path))
    assert df.empty
