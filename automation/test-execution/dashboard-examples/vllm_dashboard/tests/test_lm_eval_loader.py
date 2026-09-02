"""Unit tests for load_lm_eval_data() in 6_🎯_LM_Eval.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PAGES_DIR = Path(__file__).parent.parent / "pages"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "lm-eval"


def _import_load_lm_eval_data():
    """Import load_lm_eval_data from the page module without triggering main()."""
    page_file = PAGES_DIR / "6_🎯_LM_Eval.py"
    spec = importlib.util.spec_from_file_location("lm_eval_page", page_file)
    mod = importlib.util.module_from_spec(spec)
    # Ensure parent dir is on sys.path so config_manager import resolves
    parent = str(PAGES_DIR.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    spec.loader.exec_module(mod)
    return mod.load_lm_eval_data


@pytest.fixture(scope="module")
def load_lm_eval_data():
    return _import_load_lm_eval_data()


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
