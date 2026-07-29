"""Tests for dashboard config path resolution."""

from pathlib import Path

from config_manager import (
    DashboardConfig,
    default_llm_results_dir,
    resolve_results_path,
)


def test_default_llm_results_dir_points_to_repo_results():
    path = Path(default_llm_results_dir())
    assert path.name == "llm"
    assert path.parent.name == "results"
    assert path.parent.parent.name == Path(__file__).resolve().parents[4].name


def test_legacy_relative_path_is_migrated():
    config = DashboardConfig.__new__(DashboardConfig)
    migrated = config._normalize_results_path(
        "../../../../results/llm",
        {"../../../../results/llm", "../../../../../results/llm", "results/llm"},
        default_llm_results_dir(),
    )
    assert migrated == default_llm_results_dir()


def test_resolve_results_path_from_dashboard_dir():
    resolved = Path(resolve_results_path("results/llm"))
    assert resolved == Path(default_llm_results_dir())
