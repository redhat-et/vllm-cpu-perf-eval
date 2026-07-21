#!/usr/bin/env python3
"""
Unit tests for Offline Batch Dashboard (4_📦_Offline_Batch.py)

Tests the key functions in the dashboard:
- Use case inference from test metadata
- Unit mapping for different use cases
- Data loading and parsing
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Resolve dashboard root so config_manager imports work from any CWD.
# The page does: sys.path.insert(0, Path(__file__).parent.parent)
# so exec must set __file__ to the page path (not this test file).
_DASHBOARD_ROOT = (
    Path(__file__).resolve().parents[2]
    / "dashboard-examples"
    / "vllm_dashboard"
)
_DASHBOARD_PAGE = _DASHBOARD_ROOT / "pages" / "4_📦_Offline_Batch.py"

sys.path.insert(0, str(_DASHBOARD_ROOT))

# Heavy UI deps are not needed for pure helper tests.
for _mod in (
    "streamlit",
    "plotly",
    "plotly.graph_objects",
    "pandas",
):
    sys.modules.setdefault(_mod, MagicMock())

_ns = {
    "__file__": str(_DASHBOARD_PAGE),
    "__name__": "offline_batch_dashboard_under_test",
}
exec(compile(_DASHBOARD_PAGE.read_text(), str(_DASHBOARD_PAGE), "exec"), _ns)

get_use_case_units = _ns["get_use_case_units"]
infer_use_case = _ns["infer_use_case"]


class TestUseCaseUnits:
    """Test the get_use_case_units function."""

    def test_translation_units(self):
        """Translation should use docs/doc units."""
        units = get_use_case_units("🌐 Translation")
        assert units == {'singular': 'doc', 'plural': 'docs'}

    def test_classification_units(self):
        """Classification should use items/item units."""
        units = get_use_case_units("🏷️ Classification/Tagging")
        assert units == {'singular': 'item', 'plural': 'items'}

    def test_summarization_units(self):
        """Summarization should use docs/doc units."""
        units = get_use_case_units("📝 Summarization")
        assert units == {'singular': 'doc', 'plural': 'docs'}

    def test_code_generation_units(self):
        """Code generation should use functions/function units."""
        units = get_use_case_units("💻 Code Generation")
        assert units == {'singular': 'function', 'plural': 'functions'}

    def test_dataset_generation_units(self):
        """Dataset generation should use examples/example units."""
        units = get_use_case_units("🎲 Dataset Generation")
        assert units == {'singular': 'example', 'plural': 'examples'}

    def test_entity_extraction_units(self):
        """Entity extraction should use docs/doc units."""
        units = get_use_case_units("🧬 Entity Extraction")
        assert units == {'singular': 'doc', 'plural': 'docs'}

    def test_etl_units(self):
        """ETL pipelines should use records/record units."""
        units = get_use_case_units("🔄 ETL Pipelines")
        assert units == {'singular': 'record', 'plural': 'records'}

    def test_long_summarization_units(self):
        """Long-document summarization should use docs/doc units."""
        units = get_use_case_units("📜 Long-Document Summarization")
        assert units == {'singular': 'doc', 'plural': 'docs'}

    def test_rag_batch_units(self):
        """RAG batch should use queries/query units."""
        units = get_use_case_units("🔍 Batch RAG / Grounded Q&A")
        assert units == {'singular': 'query', 'plural': 'queries'}

    def test_shared_prefix_units(self):
        """Shared-prefix should use items/item units."""
        units = get_use_case_units("📋 Shared-Prefix / Template Batch")
        assert units == {'singular': 'item', 'plural': 'items'}

    def test_short_labeling_units(self):
        """Ultra-short labeling should use items/item units."""
        units = get_use_case_units("🏷️ Ultra-Short Labeling")
        assert units == {'singular': 'item', 'plural': 'items'}

    def test_kv_capacity_units(self):
        """KV-cache capacity should use requests/request units."""
        units = get_use_case_units("📊 KV-Cache Capacity")
        assert units == {'singular': 'request', 'plural': 'requests'}

    def test_context_scaling_units(self):
        """Context scaling should use requests/request units."""
        units = get_use_case_units("📏 Context Scaling")
        assert units == {'singular': 'request', 'plural': 'requests'}

    def test_default_units(self):
        """Unknown use cases should default to requests/request."""
        units = get_use_case_units("Unknown Task")
        assert units == {'singular': 'request', 'plural': 'requests'}


class TestUseCaseInference:
    """Test the infer_use_case function."""

    # ---- Explicit use_case field overrides inference ----

    def test_explicit_use_case_classification(self):
        """Explicit use_case field should override inference."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'classification',
                    'output_len': 64
                }
            }
        }
        assert infer_use_case(metadata) == "🏷️ Classification/Tagging"

    def test_explicit_use_case_summarization(self):
        """Explicit use_case=summarization should return Summarization."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'summarization'
                }
            }
        }
        assert infer_use_case(metadata) == "📝 Summarization"

    def test_explicit_use_case_etl(self):
        """Explicit use_case=etl should return ETL Pipelines."""
        metadata = {
            'configuration': {
                'dataset': 'sonnet',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'etl'
                }
            }
        }
        assert infer_use_case(metadata) == "🔄 ETL Pipelines"

    def test_explicit_use_case_code_generation(self):
        """Explicit use_case=code_generation should return Code Gen."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'code_generation',
                    'input_len': 512,
                    'output_len': 512
                }
            }
        }
        assert infer_use_case(metadata) == "💻 Code Generation"

    # ---- ShareGPT exact matches ----

    def test_sharegpt_summarization(self):
        """sharegpt + 1000 prompts + no output_len → Summarization."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {}
            }
        }
        assert infer_use_case(metadata) == "📝 Summarization"

    def test_sharegpt_classification(self):
        """sharegpt + 1000 prompts + output_len=64 → Classification."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {'output_len': 64}
            }
        }
        assert infer_use_case(metadata) == "🏷️ Classification/Tagging"

    def test_sharegpt_entity_extraction(self):
        """sharegpt + 1000 prompts + output_len=128 → Entity Extraction."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {'output_len': 128}
            }
        }
        assert infer_use_case(metadata) == "🧬 Entity Extraction"

    def test_sharegpt_translation(self):
        """sharegpt + 500 prompts + output_len=1024 → Translation."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {'output_len': 1024}
            }
        }
        assert infer_use_case(metadata) == "🌐 Translation"

    # ---- Sonnet ----

    def test_sonnet_etl_pipelines(self):
        """Sonnet with 500 prompts and 8/16/32 cores → ETL Pipelines."""
        for cores in [8, 16, 32]:
            metadata = {
                'configuration': {
                    'dataset': 'sonnet',
                    'num_prompts': 500,
                    'cores': cores,
                    'dataset_config': {}
                }
            }
            assert infer_use_case(metadata) == "🔄 ETL Pipelines"

    def test_sonnet_default_etl(self):
        """Any sonnet dataset → ETL Pipelines."""
        metadata = {
            'configuration': {
                'dataset': 'sonnet',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {}
            }
        }
        assert infer_use_case(metadata) == "🔄 ETL Pipelines"

    # ---- Random exact matches ----

    def test_random_dataset_generation(self):
        """Random 256→256 with 5000 prompts → Dataset Generation."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 5000,
                'cores': 32,
                'dataset_config': {
                    'input_len': 256,
                    'output_len': 256
                }
            }
        }
        assert infer_use_case(metadata) == "🎲 Dataset Generation"

    def test_random_code_generation(self):
        """Random 512→512 with 500 prompts → Code Generation."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'input_len': 512,
                    'output_len': 512
                }
            }
        }
        assert infer_use_case(metadata) == "💻 Code Generation"

    # ---- Random fuzzy matches ----

    def test_random_fuzzy_code_generation(self):
        """Random with moderate balanced lengths → Code Generation."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 100,
                'cores': 16,
                'dataset_config': {
                    'input_len': 500,
                    'output_len': 500
                }
            }
        }
        assert infer_use_case(metadata) == "💻 Code Generation"

    def test_random_fuzzy_dataset_generation(self):
        """Random with 5000+ prompts → Dataset Generation."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 6000,
                'cores': 32,
                'dataset_config': {
                    'input_len': 300,
                    'output_len': 300
                }
            }
        }
        assert infer_use_case(metadata) == "🎲 Dataset Generation"

    # ---- Explicit new use cases ----

    def test_explicit_use_case_long_summarization(self):
        """Explicit use_case=long_summarization should return Long-Doc."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'long_summarization',
                    'input_len': 4096,
                    'output_len': 256
                }
            }
        }
        assert infer_use_case(metadata) == "📜 Long-Document Summarization"

    def test_explicit_use_case_rag_batch(self):
        """Explicit use_case=rag_batch should return RAG."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'rag_batch',
                    'input_len': 2048,
                    'output_len': 128
                }
            }
        }
        assert infer_use_case(metadata) == "🔍 Batch RAG / Grounded Q&A"

    def test_explicit_use_case_shared_prefix(self):
        """Explicit use_case=shared_prefix should return Shared-Prefix."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'shared_prefix',
                    'input_len': 1024,
                    'output_len': 64
                }
            }
        }
        assert infer_use_case(metadata) == "📋 Shared-Prefix / Template Batch"

    def test_explicit_use_case_short_labeling(self):
        """Explicit use_case=short_labeling should return Ultra-Short."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 2000,
                'cores': 16,
                'dataset_config': {
                    'use_case': 'short_labeling',
                    'output_len': 16
                }
            }
        }
        assert infer_use_case(metadata) == "🏷️ Ultra-Short Labeling"

    def test_explicit_use_case_kv_capacity(self):
        """Explicit use_case=kv_capacity should return KV-Cache."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 2000,
                'cores': 32,
                'dataset_config': {
                    'use_case': 'kv_capacity',
                    'input_len': 512,
                    'output_len': 256
                }
            }
        }
        assert infer_use_case(metadata) == "📊 KV-Cache Capacity"

    def test_explicit_use_case_context_scaling(self):
        """Explicit use_case=context_scaling should return Context Scaling."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 100,
                'cores': 32,
                'dataset_config': {
                    'use_case': 'context_scaling',
                    'input_len': 4096,
                    'output_len': 128
                }
            }
        }
        assert infer_use_case(metadata) == "📏 Context Scaling"

    # ---- Heuristic inference for new use cases ----

    def test_sharegpt_short_labeling_heuristic(self):
        """sharegpt + output_len=16 → Ultra-Short Labeling."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 2000,
                'cores': 16,
                'dataset_config': {'output_len': 16}
            }
        }
        assert infer_use_case(metadata) == "🏷️ Ultra-Short Labeling"

    def test_random_long_summarization_heuristic(self):
        """Random 4096→256 → Long-Document Summarization."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'input_len': 4096,
                    'output_len': 256
                }
            }
        }
        assert infer_use_case(metadata) == "📜 Long-Document Summarization"

    def test_random_rag_heuristic(self):
        """Random 2048→128, 500 prompts → RAG Batch."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'input_len': 2048,
                    'output_len': 128
                }
            }
        }
        assert infer_use_case(metadata) == "🔍 Batch RAG / Grounded Q&A"

    def test_random_shared_prefix_heuristic(self):
        """Random 1024→64, 1000 prompts → Shared-Prefix."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {
                    'input_len': 1024,
                    'output_len': 64
                }
            }
        }
        assert infer_use_case(metadata) == "📋 Shared-Prefix / Template Batch"

    # ---- Fallback ----

    def test_unknown_dataset_general(self):
        """Unknown dataset → General."""
        metadata = {
            'configuration': {
                'dataset': 'custom',
                'num_prompts': 100,
                'cores': 16,
                'dataset_config': {}
            }
        }
        assert infer_use_case(metadata) == "⚙️ General"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
