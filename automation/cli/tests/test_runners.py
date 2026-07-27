"""Tests for runners.py merge_extra_vars."""

import pytest
from pathlib import Path
from cpueval.runners import merge_extra_vars


def test_merge_extra_vars_precedence():
    """Test that precedence order is correct."""
    suite_defaults = {"key1": "suite", "key2": "suite"}
    profile_vars = {"key2": "profile", "key3": "profile"}
    cli_vars = {"key3": "cli", "key4": "cli"}
    extra_pairs = ["key4=extra", "key5=extra"]

    result = merge_extra_vars(
        suite_defaults, profile_vars, cli_vars, extra_pairs, None
    )

    assert result["key1"] == "suite"  # Only in suite
    assert result["key2"] == "profile"  # Profile overrides suite
    assert result["key3"] == "cli"  # CLI overrides profile
    assert result["key4"] == "extra"  # --extra overrides CLI
    assert result["key5"] == "extra"  # Only in extra


def test_merge_extra_vars_json_parsing():
    """Test that JSON values in --extra are parsed."""
    result = merge_extra_vars(
        {}, {}, {}, ["list=[1,2,3]", 'dict={"a":1}', "bool=true"], None
    )

    assert result["list"] == [1, 2, 3]
    assert result["dict"] == {"a": 1}
    assert result["bool"] is True


def test_merge_extra_vars_string_fallback():
    """Test that non-JSON values stay as strings."""
    result = merge_extra_vars({}, {}, {}, ["key=value"], None)

    assert result["key"] == "value"


def test_merge_extra_vars_invalid_format():
    """Test that invalid --extra format raises ValueError."""
    with pytest.raises(ValueError, match="Invalid --extra format"):
        merge_extra_vars({}, {}, {}, ["invalid_no_equals"], None)


def test_merge_extra_vars_missing_file():
    """Test that missing --extra-vars-file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Extra vars file not found"):
        merge_extra_vars({}, {}, {}, [], "/nonexistent/file.yaml")


def test_merge_extra_vars_file_override(tmp_path):
    """Test that --extra-vars-file has highest precedence."""
    # Create temp YAML file
    vars_file = tmp_path / "vars.yaml"
    vars_file.write_text("key1: file\nkey2: file\n")

    result = merge_extra_vars(
        {"key1": "suite"},
        {"key1": "profile"},
        {"key1": "cli"},
        ["key1=extra"],
        str(vars_file)
    )

    assert result["key1"] == "file"  # File wins
    assert result["key2"] == "file"


def test_merge_extra_vars_empty():
    """Test with no overrides."""
    result = merge_extra_vars({"key": "value"}, {}, {}, [], None)

    assert result == {"key": "value"}
