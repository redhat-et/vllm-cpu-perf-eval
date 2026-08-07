#!/usr/bin/env python3
"""
Unit tests for Offline Batch Dashboard (4_📦_Offline_Batch.py)

Tests the key functions in the dashboard:
- Use case inference from test metadata
- Unit mapping for different use cases
- Pure helper functions (items/hr, duration, technical detection)
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
compute_items_per_hour = _ns["compute_items_per_hour"]
compute_time_for_batch = _ns["compute_time_for_batch"]
is_technical_use_case = _ns["is_technical_use_case"]
format_duration = _ns["format_duration"]
normalize_version = _ns["normalize_vllm_version"]
USE_CASE_REFERENCE = _ns["USE_CASE_REFERENCE"]
build_config_fingerprint = _ns["build_config_fingerprint"]
is_capped_run = _ns["is_capped_run"]
capped_run_note = _ns["capped_run_note"]
apply_run_aggregation = _ns["apply_run_aggregation"]
build_coverage_pivot = _ns["build_coverage_pivot"]
build_best_configs_table = _ns["build_best_configs_table"]
format_run_stats = _ns["format_run_stats"]
parse_streaming_metrics_from_log = _ns["parse_streaming_metrics_from_log"]
use_case_cli_name = _ns["use_case_cli_name"]
compute_coefficient_of_variation = _ns["compute_coefficient_of_variation"]
IMPORT_CSV_COLUMN_MAP = _ns["IMPORT_CSV_COLUMN_MAP"]
normalize_imported_offline_batch_df = _ns["normalize_imported_offline_batch_df"]
PREFILL_COL = _ns["PREFILL_COL"]
DECODE_COL = _ns["DECODE_COL"]
METRIC_RPS = _ns["METRIC_RPS"]
METRIC_TOK_S = _ns["METRIC_TOK_S"]


class TestComputeItemsPerHour:
    """Test the compute_items_per_hour helper."""

    def test_basic(self):
        assert compute_items_per_hour(1.0) == 3600.0

    def test_fractional(self):
        assert compute_items_per_hour(0.5) == 1800.0

    def test_zero(self):
        assert compute_items_per_hour(0.0) == 0.0

    def test_high_rate(self):
        assert compute_items_per_hour(10.0) == 36000.0


class TestComputeTimeForBatch:
    """Test the compute_time_for_batch helper."""

    def test_basic(self):
        assert compute_time_for_batch(10.0, 100) == 10.0

    def test_large_batch(self):
        assert compute_time_for_batch(2.0, 10000) == 5000.0

    def test_zero_rate(self):
        assert compute_time_for_batch(0.0, 100) == float('inf')

    def test_negative_rate(self):
        assert compute_time_for_batch(-1.0, 100) == float('inf')

    def test_single_item(self):
        assert compute_time_for_batch(5.0, 1) == 0.2


class TestIsTechnicalUseCase:
    """Test the is_technical_use_case helper."""

    def test_kv_capacity(self):
        assert is_technical_use_case("kv_capacity") is True

    def test_context_scaling(self):
        assert is_technical_use_case("context_scaling") is True

    def test_batch_scaling(self):
        assert is_technical_use_case("batch_scaling") is True

    def test_baseline(self):
        assert is_technical_use_case("baseline") is True

    def test_product_summarization(self):
        assert is_technical_use_case("summarization") is False

    def test_product_etl(self):
        assert is_technical_use_case("etl") is False

    def test_product_classification(self):
        assert is_technical_use_case("classification") is False

    def test_empty_string(self):
        assert is_technical_use_case("") is False


class TestFormatDuration:
    """Test the format_duration helper."""

    def test_seconds(self):
        assert format_duration(45) == "45s"

    def test_minutes(self):
        assert format_duration(150) == "2.5 min"

    def test_hours(self):
        assert format_duration(7200) == "2.0 hr"

    def test_infinity(self):
        assert format_duration(float('inf')) == "N/A"

    def test_nan(self):
        assert format_duration(float('nan')) == "N/A"

    def test_zero(self):
        assert format_duration(0) == "0s"

    def test_boundary_60(self):
        assert format_duration(60) == "1.0 min"

    def test_boundary_3600(self):
        assert format_duration(3600) == "1.0 hr"


class TestNormalizeVersion:
    """Test the normalize_vllm_version helper (aliased as normalize_version)."""

    def test_empty_string(self):
        assert normalize_version("") == "unknown"

    def test_none(self):
        assert normalize_version(None) == "unknown"

    def test_unknown_string(self):
        assert normalize_version("unknown") == "unknown"

    def test_rhaiis_34_version(self):
        assert normalize_version("0.18.0+rhaiv.7") == "RHAIIS_3.4"

    def test_rhaiis_35_version(self):
        assert normalize_version("0.24.0+rhaiv.2") == "RHAIIS_3.5"

    def test_unmapped_version_passthrough(self):
        assert normalize_version("0.25.1") == "0.25.1"

    def test_v_prefix_passthrough(self):
        assert normalize_version("v0.25.1") == "v0.25.1"


class TestUseCaseReference:
    """Test the USE_CASE_REFERENCE table structure."""

    def test_has_all_columns(self):
        """Every entry should have Use Case, Dataset, Input, Output, Unit."""
        for entry in USE_CASE_REFERENCE:
            assert "Use Case" in entry
            assert "Dataset" in entry
            assert "Input" in entry
            assert "Output" in entry
            assert "Unit" in entry

    def test_shared_prefix_note(self):
        """Shared-Prefix entry should have asterisk (no prefix caching)."""
        shared = [
            e for e in USE_CASE_REFERENCE
            if 'Shared-Prefix' in e['Use Case']
        ]
        assert len(shared) == 1
        assert '*' in shared[0]['Use Case']

    def test_long_doc_input(self):
        """Long-Doc Summary should show input=4096."""
        long_doc = [
            e for e in USE_CASE_REFERENCE
            if 'Long-Doc' in e['Use Case']
        ]
        assert len(long_doc) == 1
        assert long_doc[0]['Input'] == '4096'
        assert long_doc[0]['Output'] == '256'

    def test_rag_input(self):
        """RAG Batch should show input=2048, output=128."""
        rag = [
            e for e in USE_CASE_REFERENCE
            if 'RAG' in e['Use Case']
        ]
        assert len(rag) == 1
        assert rag[0]['Input'] == '2048'
        assert rag[0]['Output'] == '128'

    def test_short_labeling_output(self):
        """Short Labeling should show output=16."""
        short = [
            e for e in USE_CASE_REFERENCE
            if 'Short' in e['Use Case'] or '⚡' in e['Use Case']
        ]
        assert len(short) == 1
        assert short[0]['Output'] == '16'

    def test_count(self):
        """Should have 11 use cases."""
        assert len(USE_CASE_REFERENCE) == 11


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
        units = get_use_case_units("⚡ Ultra-Short Labeling")
        assert units == {'singular': 'item', 'plural': 'items'}

    def test_short_labeling_units_emoji_only(self):
        """⚡ emoji alone should resolve to items (labeling)."""
        units = get_use_case_units("⚡")
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
        """sharegpt + 1000 prompts + no output_len -> Summarization."""
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
        """sharegpt + 1000 prompts + output_len=64 -> Classification."""
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
        """sharegpt + 1000 prompts + output_len=128 -> Entity Extraction."""
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
        """sharegpt + 500 prompts + output_len=1024 -> Translation."""
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
        """Sonnet with 500 prompts and 8/16/32 cores -> ETL Pipelines."""
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
        """Any sonnet dataset -> ETL Pipelines."""
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
        """Random 256->256 with 5000 prompts -> Dataset Generation."""
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
        """Random 512->512 with 500 prompts -> Code Generation."""
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
        """Random with moderate balanced lengths -> Code Generation."""
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
        """Random with 5000+ prompts -> Dataset Generation."""
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
        assert infer_use_case(metadata) == "⚡ Ultra-Short Labeling"

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
        """Explicit use_case=context_scaling -> Context Scaling."""
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
        """sharegpt + output_len=16 -> Ultra-Short Labeling."""
        metadata = {
            'configuration': {
                'dataset': 'sharegpt',
                'num_prompts': 2000,
                'cores': 16,
                'dataset_config': {'output_len': 16}
            }
        }
        assert infer_use_case(metadata) == "⚡ Ultra-Short Labeling"

    def test_random_long_summarization_heuristic(self):
        """Random 4096->256 -> Long-Document Summarization."""
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
        """Random 2048->128, 500 prompts -> RAG Batch."""
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
        """Random 1024->64, 1000 prompts -> Shared-Prefix."""
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
        """Unknown dataset -> General."""
        metadata = {
            'configuration': {
                'dataset': 'custom',
                'num_prompts': 100,
                'cores': 16,
                'dataset_config': {}
            }
        }
        assert infer_use_case(metadata) == "⚙️ General"


class TestConfigFingerprint:
    def test_basic_fingerprint(self):
        row = {
            'cores': 16,
            'dataset': 'sharegpt',
            'num_prompts': 100,
            'config_input_len': None,
            'config_output_len': 64,
        }
        fp = build_config_fingerprint(row)
        assert '16c' in fp
        assert 'sharegpt' in fp
        assert '100 prompts' in fp
        assert 'out=64' in fp


class TestCappedRuns:
    def test_capped_detection(self):
        assert is_capped_run('summarization', 100) is True
        assert is_capped_run('summarization', 1000) is False
        assert is_capped_run('', 100) is False

    def test_capped_note(self):
        note = capped_run_note('summarization', 100)
        assert 'Capped run' in note
        assert capped_run_note('summarization', 1000) == ''


class TestStreamingMetricsParsing:
    SAMPLE_LOG = """
Throughput: 1.23 requests/s, 456.78 total tokens/s
Engine 000: Avg prompt throughput: 100.5 tokens/s, Avg generation throughput: 45.2 tokens/s, Running: 1 reqs
Engine 000: Avg prompt throughput: 110.0 tokens/s, Avg generation throughput: 50.0 tokens/s, Running: 0 reqs
Engine 000: CPU KV cache usage: 12.5%, Prefix cache hit rate: 33.3%
"""

    def test_parse_prefill_decode_averages(self):
        metrics = parse_streaming_metrics_from_log(self.SAMPLE_LOG)
        assert metrics[PREFILL_COL] == 105.25
        assert metrics[DECODE_COL] == 47.6

    def test_parse_kv_and_prefix(self):
        metrics = parse_streaming_metrics_from_log(self.SAMPLE_LOG)
        assert metrics['metric_max_kv_cache_usage_percent'] == 12.5
        assert metrics['metric_avg_prefix_cache_hit_rate_percent'] == 33.3

    def test_empty_log(self):
        metrics = parse_streaming_metrics_from_log('')
        assert metrics[PREFILL_COL] == 0.0
        assert metrics[DECODE_COL] == 0.0


class TestUseCaseCliName:
    def test_from_slug(self):
        assert use_case_cli_name('ignored', 'long_summarization') == 'long-summarization'

    def test_from_display(self):
        assert use_case_cli_name('📝 Summarization') == 'summarization'


class TestCoefficientOfVariation:
    def test_basic(self):
        assert compute_coefficient_of_variation(10.0, 1.0) == 0.1

    def test_zero_mean(self):
        assert compute_coefficient_of_variation(0.0, 1.0) == 0.0


class TestCsvImportMap:
    def test_export_headers_mapped(self):
        assert IMPORT_CSV_COLUMN_MAP['Req/sec'] == METRIC_RPS
        assert IMPORT_CSV_COLUMN_MAP['Use Case'] == 'use_case'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
