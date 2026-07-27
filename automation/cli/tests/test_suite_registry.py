"""Tests for suite registry and matrix suite handling."""

import pytest
from pathlib import Path
from cpueval.suite_registry import Suite, SuiteRegistry


def test_suite_matrix_field():
    """Test that Suite dataclass accepts matrix field."""
    suite = Suite(
        name="test-suite",
        description="Test suite",
        runner="script",
        target="test.sh",
        defaults={"models": "all"},
        param_mappings={"models": "--models"},
        matrix=True,
    )
    assert suite.matrix is True


def test_suite_matrix_defaults_to_false():
    """Test that matrix defaults to False for single-shot suites."""
    suite = Suite(
        name="test-suite",
        description="Test suite",
        runner="ansible",
        target="test.yml",
        defaults={},
        param_mappings={},
    )
    assert suite.matrix is False


def test_matrix_suite_loading(tmp_path):
    """Test loading a matrix suite from YAML."""
    suite_yaml = tmp_path / "test-matrix.yaml"
    suite_yaml.write_text("""
name: test-matrix
description: Test matrix suite
runner: script
target: test.sh
matrix: true

defaults:
  models: all
  cores: "8,16,32"

param_mappings:
  models: --models
  cores: --cores
""")

    registry = SuiteRegistry(suites_dir=tmp_path)
    suite = registry.get_suite("test-matrix")

    assert suite is not None
    assert suite.name == "test-matrix"
    assert suite.matrix is True
    assert suite.defaults["models"] == "all"
    assert suite.defaults["cores"] == "8,16,32"


def test_single_shot_suite_loading(tmp_path):
    """Test loading a single-shot suite (matrix: false or omitted)."""
    suite_yaml = tmp_path / "test-single.yaml"
    suite_yaml.write_text("""
name: test-single
description: Test single-shot suite
runner: ansible
target: test.yml

defaults:
  test_model: TinyLlama/TinyLlama-1.1B-Chat-v1.0

param_mappings:
  model: test_model
""")

    registry = SuiteRegistry(suites_dir=tmp_path)
    suite = registry.get_suite("test-single")

    assert suite is not None
    assert suite.name == "test-single"
    assert suite.matrix is False
    assert suite.defaults["test_model"] == "TinyLlama/TinyLlama-1.1B-Chat-v1.0"


def test_rhaiis_sweep_is_matrix_suite():
    """Test that rhaiis-sweep is loaded as a matrix suite."""
    registry = SuiteRegistry()
    suite = registry.get_suite("rhaiis-sweep")

    if suite:  # Only run if suite exists
        assert suite.matrix is True
        assert "models" in suite.defaults
        assert suite.defaults["models"] == "all"
        assert "cores" in suite.defaults
        assert "workloads" in suite.defaults


def test_embedding_is_matrix_suite():
    """Test that embedding is loaded as a matrix suite."""
    registry = SuiteRegistry()
    suite = registry.get_suite("embedding")

    if suite:  # Only run if suite exists
        assert suite.matrix is True
        assert "models" in suite.defaults
        assert suite.defaults["models"] == "all"


def test_chat_smoke_is_single_shot():
    """Test that chat-smoke requires model (not a matrix suite)."""
    registry = SuiteRegistry()
    suite = registry.get_suite("chat-smoke")

    if suite:  # Only run if suite exists
        assert suite.matrix is False


def test_concurrent_load_is_matrix():
    """Test that concurrent-load is a matrix suite."""
    registry = SuiteRegistry()
    suite = registry.get_suite("concurrent-load")

    if suite:  # Only run if suite exists
        assert suite.matrix is True
