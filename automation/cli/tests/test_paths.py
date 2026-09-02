"""Unit tests for cpueval path helpers."""

import pytest
from pathlib import Path

from cpueval.paths import (
    find_latest_result,
    find_latest_embedding_result,
    find_latest_lm_eval_result,
    find_latest_suite_result,
)


def _make_llm_result(base: Path, model: str, run: str) -> Path:
    """Create a fake LLM result dir with benchmarks.json."""
    d = base / "llm" / model / run
    d.mkdir(parents=True)
    (d / "benchmarks.json").write_text("{}")
    return d


def _make_embedding_result(base: Path, model: str, run: str) -> Path:
    """Create a fake embedding result dir with test-metadata.json."""
    d = base / "embedding" / model / run
    d.mkdir(parents=True)
    (d / "test-metadata.json").write_text("{}")
    return d


def _make_lm_eval_result(base: Path, model: str, run: str) -> Path:
    """Create a fake lm-eval result dir with test-metadata.json."""
    d = base / "lm-eval" / model / run
    d.mkdir(parents=True)
    (d / "test-metadata.json").write_text("{}")
    return d


# ---------------------------------------------------------------------------
# find_latest_embedding_result
# ---------------------------------------------------------------------------

def test_find_latest_embedding_result_basic(tmp_path):
    """Returns the most-recently modified embedding result dir."""
    _make_embedding_result(tmp_path, "RedHatAI__all-MiniLM-L6-v2", "run-4C")
    latest = _make_embedding_result(
        tmp_path, "RedHatAI__all-MiniLM-L6-v2", "run-8C"
    )

    from cpueval import paths as paths_mod
    orig = paths_mod.get_embedding_results_dir
    paths_mod.get_embedding_results_dir = lambda: tmp_path / "embedding"
    try:
        result = find_latest_embedding_result()
    finally:
        paths_mod.get_embedding_results_dir = orig

    assert result == latest


def test_find_latest_embedding_result_model_filter(tmp_path):
    """Model filter restricts results to the specified model directory."""
    _make_embedding_result(
        tmp_path, "RedHatAI__nomic-embed-text-v1.5", "run-8C"
    )
    target = _make_embedding_result(
        tmp_path, "RedHatAI__all-MiniLM-L6-v2", "run-8C"
    )

    from cpueval import paths as paths_mod
    orig = paths_mod.get_embedding_results_dir
    paths_mod.get_embedding_results_dir = lambda: tmp_path / "embedding"
    try:
        result = find_latest_embedding_result(
            model="RedHatAI/all-MiniLM-L6-v2"
        )
    finally:
        paths_mod.get_embedding_results_dir = orig

    assert result == target


def test_find_latest_embedding_result_returns_none_when_empty(tmp_path):
    """Returns None when the embedding results dir has no metadata files."""
    (tmp_path / "embedding").mkdir()

    from cpueval import paths as paths_mod
    orig = paths_mod.get_embedding_results_dir
    paths_mod.get_embedding_results_dir = lambda: tmp_path / "embedding"
    try:
        result = find_latest_embedding_result()
    finally:
        paths_mod.get_embedding_results_dir = orig

    assert result is None


def test_embedding_suite_does_not_fall_back_to_llm(tmp_path):
    """Embedding lookup must not return a path inside results/llm."""
    _make_llm_result(tmp_path, "SomeModel__v1", "chat-run-1")
    # No embedding results exist

    from cpueval import paths as paths_mod
    orig_emb = paths_mod.get_embedding_results_dir
    orig_llm = paths_mod.get_llm_results_dir
    paths_mod.get_embedding_results_dir = lambda: tmp_path / "embedding"
    paths_mod.get_llm_results_dir = lambda: tmp_path / "llm"
    try:
        result = find_latest_embedding_result()
    finally:
        paths_mod.get_embedding_results_dir = orig_emb
        paths_mod.get_llm_results_dir = orig_llm

    assert result is None


# ---------------------------------------------------------------------------
# find_latest_lm_eval_result
# ---------------------------------------------------------------------------

def test_find_latest_lm_eval_result_basic(tmp_path):
    """Returns the most-recently modified lm-eval result dir."""
    _make_lm_eval_result(tmp_path, "meta-llama__Llama-3-2-1B-Instruct", "run-8C")
    latest = _make_lm_eval_result(
        tmp_path, "meta-llama__Llama-3-2-1B-Instruct", "run-16C"
    )

    from cpueval import paths as paths_mod
    orig = paths_mod.get_lm_eval_results_dir
    paths_mod.get_lm_eval_results_dir = lambda: tmp_path / "lm-eval"
    try:
        result = find_latest_lm_eval_result()
    finally:
        paths_mod.get_lm_eval_results_dir = orig

    assert result == latest


def test_lm_eval_suite_does_not_fall_back_to_llm(tmp_path):
    """lm-eval lookup must not return a path inside results/llm."""
    _make_llm_result(tmp_path, "SomeModel__v1", "run-1")

    from cpueval import paths as paths_mod
    orig = paths_mod.get_lm_eval_results_dir
    paths_mod.get_lm_eval_results_dir = lambda: tmp_path / "lm-eval"
    try:
        result = find_latest_lm_eval_result()
    finally:
        paths_mod.get_lm_eval_results_dir = orig

    assert result is None


# ---------------------------------------------------------------------------
# find_latest_suite_result
# ---------------------------------------------------------------------------

def test_find_latest_suite_result_routes_lm_eval(tmp_path):
    """Suite name lm-eval resolves under results/lm-eval."""
    target = _make_lm_eval_result(
        tmp_path, "Qwen__Qwen3-0.6B", "smoke-test-20260101"
    )

    from cpueval import paths as paths_mod
    orig = paths_mod.get_lm_eval_results_dir
    paths_mod.get_lm_eval_results_dir = lambda: tmp_path / "lm-eval"
    try:
        result = find_latest_suite_result("lm-eval")
    finally:
        paths_mod.get_lm_eval_results_dir = orig

    assert result == target
