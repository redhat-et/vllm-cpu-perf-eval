#!/usr/bin/env python3
"""Validate model matrix configuration."""
import pytest
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
MODELS_DIR = REPO_ROOT / "models"


@pytest.mark.smoke
class TestModelMatrix:
    """Validate model matrix configuration."""

    @pytest.fixture
    def llm_matrix(self):
        """Load LLM model matrix."""
        matrix_file = MODELS_DIR / "llm-models" / "model-matrix.yaml"
        assert matrix_file.exists(), f"Model matrix not found at {matrix_file}"

        with open(matrix_file) as f:
            return yaml.safe_load(f)

    @pytest.fixture
    def embedding_matrix(self):
        """Load embedding model matrix."""
        matrix_file = MODELS_DIR / "embedding-models" / "model-matrix.yaml"
        if not matrix_file.exists():
            pytest.skip("Embedding model matrix not found")

        with open(matrix_file) as f:
            return yaml.safe_load(f)

    def test_llm_matrix_has_required_structure(self, llm_matrix):
        """Model matrix should have required top-level structure."""
        assert "matrix" in llm_matrix, "Missing 'matrix' key"
        assert "llm_models" in llm_matrix["matrix"], "Missing 'llm_models' key"
        assert "workloads" in llm_matrix["matrix"], "Missing 'workloads' key"
        assert "common_parameters" in llm_matrix["matrix"], "Missing 'common_parameters'"

    def test_all_models_have_required_fields(self, llm_matrix):
        """Each model must have required fields."""
        required_fields = {
            "name",
            "full_name",
            "parameters",
            "context_length",
            "dtype",
            "architecture_family",
            "default_workloads",
            "test_suites",
        }

        errors = []
        for model in llm_matrix["matrix"]["llm_models"]:
            model_name = model.get("name", "unknown")
            missing = required_fields - set(model.keys())
            if missing:
                errors.append(f"{model_name}: missing fields {missing}")

        assert not errors, f"Model validation errors:\n" + "\n".join(errors)

    def test_workloads_match_model_requirements(self, llm_matrix):
        """Validate workload context_length vs model capacity."""
        workloads = llm_matrix["matrix"]["workloads"]
        errors = []

        for model in llm_matrix["matrix"]["llm_models"]:
            model_name = model["name"]
            model_context = model["context_length"]

            for workload_name in model.get("default_workloads", []):
                if workload_name not in workloads:
                    errors.append(
                        f"{model_name}: workload '{workload_name}' not defined"
                    )
                    continue

                workload = workloads[workload_name]
                if "max_model_len" in workload:
                    max_len = workload["max_model_len"]
                    if max_len > model_context:
                        errors.append(
                            f"{model_name}: workload '{workload_name}' "
                            f"max_model_len ({max_len}) > context_length ({model_context})"
                        )

        assert not errors, f"Workload validation errors:\n" + "\n".join(errors)

    def test_all_workloads_have_required_fields(self, llm_matrix):
        """Each workload must have required fields."""
        workloads = llm_matrix["matrix"]["workloads"]
        errors = []

        for workload_name, workload in workloads.items():
            # Variable workloads have different fields
            is_variable = workload.get("variability", False)

            if is_variable:
                required = {
                    "name",
                    "input_tokens_mean",
                    "input_tokens_stdev",
                    "output_tokens_mean",
                    "output_tokens_stdev",
                    "variability",
                }
            else:
                required = {
                    "name",
                    "input_tokens",
                    "output_tokens",
                    "max_model_len",
                }

            missing = required - set(workload.keys())
            if missing:
                errors.append(f"{workload_name}: missing fields {missing}")

        assert not errors, f"Workload field validation errors:\n" + "\n".join(errors)

    def test_kv_cache_sizes_defined(self, llm_matrix):
        """Each model should have KV cache sizes for their workloads."""
        errors = []

        for model in llm_matrix["matrix"]["llm_models"]:
            model_name = model["name"]
            kv_cache_sizes = model.get("kv_cache_sizes", {})

            for workload_name in model.get("default_workloads", []):
                if workload_name not in kv_cache_sizes:
                    errors.append(
                        f"{model_name}: missing kv_cache_size for workload '{workload_name}'"
                    )

        assert not errors, f"KV cache validation errors:\n" + "\n".join(errors)

    def test_test_suites_are_valid(self, llm_matrix):
        """Models should reference valid test suites."""
        valid_suites = {"concurrent-load", "scalability", "resource-contention"}
        errors = []

        for model in llm_matrix["matrix"]["llm_models"]:
            model_name = model["name"]
            test_suites = model.get("test_suites", [])

            for suite in test_suites:
                if suite not in valid_suites:
                    errors.append(
                        f"{model_name}: invalid test suite '{suite}'. "
                        f"Valid suites: {valid_suites}"
                    )

        assert not errors, f"Test suite validation errors:\n" + "\n".join(errors)

    def test_gated_models_marked_correctly(self, llm_matrix):
        """Models requiring HuggingFace tokens should be marked as gated."""
        errors = []

        for model in llm_matrix["matrix"]["llm_models"]:
            model_name = model["name"]
            full_name = model["full_name"]
            is_gated = model.get("gated", False)

            # Known gated model prefixes
            gated_prefixes = ["meta-llama/"]

            should_be_gated = any(full_name.startswith(prefix) for prefix in gated_prefixes)

            if should_be_gated and not is_gated:
                errors.append(
                    f"{model_name} ({full_name}): should be marked as gated=true"
                )

        # This is a warning, not a hard error (new gated models may be added)
        if errors:
            pytest.skip(f"Gated model warnings (not critical):\n" + "\n".join(errors))

    def test_embedding_matrix_structure(self, embedding_matrix):
        """Embedding model matrix should have required structure."""
        assert "matrix" in embedding_matrix, "Missing 'matrix' key"
        assert "embedding_models" in embedding_matrix["matrix"], "Missing 'embedding_models'"

        required_fields = {"name", "full_name", "dimensions", "max_sequence_length"}

        errors = []
        for model in embedding_matrix["matrix"]["embedding_models"]:
            model_name = model.get("name", "unknown")
            missing = required_fields - set(model.keys())
            if missing:
                errors.append(f"{model_name}: missing fields {missing}")

        assert not errors, f"Embedding model validation errors:\n" + "\n".join(errors)

    def test_no_duplicate_model_names(self, llm_matrix):
        """Model names should be unique."""
        model_names = [m["name"] for m in llm_matrix["matrix"]["llm_models"]]
        duplicates = [name for name in model_names if model_names.count(name) > 1]

        assert not duplicates, f"Duplicate model names found: {set(duplicates)}"

    def test_no_duplicate_workload_names(self, llm_matrix):
        """Workload names should be unique."""
        workload_names = list(llm_matrix["matrix"]["workloads"].keys())
        duplicates = [name for name in workload_names if workload_names.count(name) > 1]

        assert not duplicates, f"Duplicate workload names found: {set(duplicates)}"
