#!/usr/bin/env python3
"""
Unit tests for Offline Batch Dashboard (4_📦_Offline_Batch.py)

Tests the key functions in the dashboard:
- Use case inference from test metadata
- Unit mapping for different use cases
- Data loading and parsing
"""

import pytest
from pathlib import Path
import sys

# Add dashboard to path
dashboard_path = Path(__file__).parent / "../../dashboard-examples/vllm_dashboard"
sys.path.insert(0, str(dashboard_path / "pages"))

# Import functions from the dashboard
# Note: Using exec to import from emoji-named file
dashboard_file = dashboard_path / "pages" / "4_📦_Offline_Batch.py"
with open(dashboard_file) as f:
    exec(f.read(), globals())


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

    def test_default_units(self):
        """Unknown use cases should default to requests/request."""
        units = get_use_case_units("Unknown Task")
        assert units == {'singular': 'request', 'plural': 'requests'}


class TestUseCaseInference:
    """Test the infer_use_case function."""

    def test_summarization_sonnet_1000(self):
        """Sonnet with 1000 prompts should be Summarization."""
        metadata = {
            'configuration': {
                'dataset': 'sonnet',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {}
            }
        }
        use_case = infer_use_case(metadata)
        assert use_case == "📝 Summarization"

    def test_etl_pipelines_sonnet_500(self):
        """Sonnet with 500 prompts and 8/16/32 cores should be ETL Pipelines."""
        for cores in [8, 16, 32]:
            metadata = {
                'configuration': {
                    'dataset': 'sonnet',
                    'num_prompts': 500,
                    'cores': cores,
                    'dataset_config': {}
                }
            }
            use_case = infer_use_case(metadata)
            assert use_case == "🔄 ETL Pipelines"

    def test_classification_512_64(self):
        """Random 512→64 with 1000 prompts should be Classification."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {
                    'input_len': 512,
                    'output_len': 64
                }
            }
        }
        use_case = infer_use_case(metadata)
        assert use_case == "🏷️ Classification/Tagging"

    def test_translation_1024_1024(self):
        """Random 1024→1024 with 500 prompts should be Translation."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 500,
                'cores': 16,
                'dataset_config': {
                    'input_len': 1024,
                    'output_len': 1024
                }
            }
        }
        use_case = infer_use_case(metadata)
        assert use_case == "🌐 Translation"

    def test_entity_extraction_1500_128(self):
        """Random 1500→128 with 1000 prompts should be Entity Extraction."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 1000,
                'cores': 16,
                'dataset_config': {
                    'input_len': 1500,
                    'output_len': 128
                }
            }
        }
        use_case = infer_use_case(metadata)
        assert use_case == "🧬 Entity Extraction"

    def test_dataset_generation_256_256_5000(self):
        """Random 256→256 with 5000 prompts should be Dataset Generation."""
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
        use_case = infer_use_case(metadata)
        assert use_case == "🎲 Dataset Generation"

    def test_code_generation_512_512(self):
        """Random 512→512 with 500 prompts should be Code Generation."""
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
        use_case = infer_use_case(metadata)
        assert use_case == "💻 Code Generation"

    def test_fallback_classification_short_output(self):
        """Random with short output should fallback to Classification."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 100,
                'cores': 16,
                'dataset_config': {
                    'input_len': 400,
                    'output_len': 50
                }
            }
        }
        use_case = infer_use_case(metadata)
        assert use_case == "🏷️ Classification/Tagging"

    def test_fallback_translation_balanced(self):
        """Random with balanced 1000→1000 should fallback to Translation."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 100,
                'cores': 16,
                'dataset_config': {
                    'input_len': 1000,
                    'output_len': 1000
                }
            }
        }
        use_case = infer_use_case(metadata)
        assert use_case == "🌐 Translation"

    def test_fallback_entity_extraction_long_input(self):
        """Random with long input short output should fallback to Entity Extraction."""
        metadata = {
            'configuration': {
                'dataset': 'random',
                'num_prompts': 100,
                'cores': 16,
                'dataset_config': {
                    'input_len': 1500,
                    'output_len': 150
                }
            }
        }
        use_case = infer_use_case(metadata)
        assert use_case == "🧬 Entity Extraction"

    def test_fallback_code_generation_moderate(self):
        """Random with moderate balanced lengths should fallback to Code Generation."""
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
        use_case = infer_use_case(metadata)
        assert use_case == "💻 Code Generation"

    def test_fallback_dataset_generation_high_volume(self):
        """Random with 5000+ prompts should fallback to Dataset Generation."""
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
        use_case = infer_use_case(metadata)
        assert use_case == "🎲 Dataset Generation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
