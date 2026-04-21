#!/usr/bin/env python3
"""Validate workload configuration consistency across files."""
import pytest
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
MODELS_DIR = REPO_ROOT / "models"
ANSIBLE_DIR = REPO_ROOT / "automation" / "test-execution" / "ansible"


@pytest.mark.smoke
class TestWorkloadConsistency:
    """Validate workload definitions are consistent."""

    @pytest.fixture
    def llm_matrix(self):
        """Load LLM model matrix."""
        matrix_file = MODELS_DIR / "llm-models" / "model-matrix.yaml"
        with open(matrix_file) as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def test_workloads(self):
        """Load test workload configurations."""
        workloads_file = (
            ANSIBLE_DIR / "inventory" / "group_vars" /
            "all" / "test-workloads.yml"
        )
        with open(workloads_file) as f:
            return yaml.safe_load(f)

    def test_model_workloads_defined_in_configs(
        self, llm_matrix, test_workloads
    ):
        """Workloads in model matrix should exist in test configs."""
        matrix_workloads = set(llm_matrix["matrix"]["workloads"].keys())
        config_workloads = set(test_workloads["test_configs"].keys())

        # Core workloads that must exist in test configs
        missing = matrix_workloads - config_workloads

        # Filter out acceptable missing workloads
        # (chat_lite is an optional profile variant)
        acceptable_missing = set()

        actual_missing = missing - acceptable_missing

        msg = (
            f"Workloads in model-matrix.yaml missing from "
            f"test-workloads.yml: {actual_missing}"
        )
        assert not actual_missing, msg

    def test_workload_parameters_reasonable(self, test_workloads):
        """All workloads should have reasonable parameters."""
        errors = []

        for name, config in test_workloads["test_configs"].items():
            # Check required fields
            required = {"workload_type", "isl", "osl", "backend"}
            missing = required - set(config.keys())
            if missing:
                errors.append(f"{name}: missing fields {missing}")
                continue

            # Validate parameter ranges
            isl = config["isl"]
            osl = config["osl"]

            if not (1 <= isl <= 128000):
                errors.append(
                    f"{name}: isl={isl} outside valid range [1, 128000]"
                )

            if not (1 <= osl <= 4096):
                errors.append(
                    f"{name}: osl={osl} outside valid range [1, 4096]"
                )

            # Check backend is valid
            valid_backends = {
                "openai-chat",
                "openai-completions",
                "openai-embeddings"
            }
            if config["backend"] not in valid_backends:
                errors.append(
                    f"{name}: invalid backend '{config['backend']}'. "
                    f"Valid: {valid_backends}"
                )

        msg = "Workload parameter errors:\n" + "\n".join(errors)
        assert not errors, msg

    def test_no_duplicate_workload_types(self, test_workloads):
        """Each workload should have a unique workload_type."""
        workload_types = [
            cfg["workload_type"]
            for cfg in test_workloads["test_configs"].values()
            if "workload_type" in cfg
        ]

        duplicates = [
            wt for wt in workload_types if workload_types.count(wt) > 1
        ]

        msg = f"Duplicate workload_type values: {set(duplicates)}"
        assert not duplicates, msg

    def test_variable_workloads_have_stdev_params(self, test_workloads):
        """Variable workloads must have stdev parameters."""
        errors = []

        for name, config in test_workloads["test_configs"].items():
            if not config.get("variability", False):
                continue

            # Variable workloads need stdev parameters
            required_var = {
                "isl_stdev",
                "osl_stdev",
            }

            missing = required_var - set(config.keys())
            if missing:
                errors.append(
                    f"{name}: variable workload missing {missing}"
                )

        msg = "Variable workload validation errors:\n" + "\n".join(errors)
        assert not errors, msg
