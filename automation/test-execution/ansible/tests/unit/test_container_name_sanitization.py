#!/usr/bin/env python3
"""
Unit tests for container name sanitization logic.

Tests validate that GuideLLM container names comply with Docker/Podman naming
requirements: [a-zA-Z0-9][a-zA-Z0-9_.-]*

Run with: python -m pytest test_container_name_sanitization.py -v
Or without pytest: python3 test_container_name_sanitization.py
"""

import re

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    # Mock pytest.mark for fallback tests
    class pytest:
        class mark:
            @staticmethod
            def unit(func):
                """No-op decorator for @pytest.mark.unit."""
                return func


# ============================================================================
# Container Name Sanitization Functions
# ============================================================================

def sanitize_numa_value(value):
    """
    Sanitize NUMA configuration values for use in container names.

    Mimics the Ansible Jinja2 filters:
    {{ value | replace('n/a', 'na') | regex_replace('[^a-zA-Z0-9_.-]', '-') }}

    Args:
        value: NUMA configuration value (cpuset_mems or cpuset_cpus)

    Returns:
        str: Sanitized value safe for container names
    """
    # First replace the literal 'n/a' with 'na'
    result = str(value).replace('n/a', 'na')

    # Then replace any remaining invalid characters with hyphens
    result = re.sub(r'[^a-zA-Z0-9_.-]', '-', result)

    return result


def build_container_name(workload_type, core_name, vllm_mems, loadgen_mems):
    """
    Build a GuideLLM container name with sanitized NUMA configuration.

    Mimics the Ansible task at roles/benchmark_guidellm/tasks/main.yml:178

    Args:
        workload_type: Benchmark workload type (e.g., 'chat_lite')
        core_name: Core configuration name (e.g., 'external-endpoint')
        vllm_mems: vLLM NUMA memory configuration (e.g., 'n/a', '0', '0,1')
        loadgen_mems: Load generator NUMA memory config (e.g., '0')

    Returns:
        str: Valid container name
    """
    sanitized_vllm = sanitize_numa_value(vllm_mems)
    sanitized_loadgen = sanitize_numa_value(loadgen_mems)

    return f"guidellm-{workload_type}-{core_name}-vllm-numa{sanitized_vllm}-loadgen-numa{sanitized_loadgen}"


def is_valid_container_name(name):
    """
    Check if a container name is valid per Docker/Podman rules.

    Valid pattern: [a-zA-Z0-9][a-zA-Z0-9_.-]*

    Args:
        name: Container name to validate

    Returns:
        bool: True if valid, False otherwise
    """
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$', name))


# ============================================================================
# Test Classes
# ============================================================================

@pytest.mark.unit
class TestNumaValueSanitization:
    """Test NUMA value sanitization."""

    def test_external_mode_na(self):
        """Test 'n/a' is converted to 'na'."""
        assert sanitize_numa_value('n/a') == 'na'

    def test_single_numa_node(self):
        """Test single NUMA node remains unchanged."""
        assert sanitize_numa_value('0') == '0'
        assert sanitize_numa_value('1') == '1'

    def test_multi_numa_comma(self):
        """Test multi-NUMA with comma converts to hyphen."""
        assert sanitize_numa_value('0,1') == '0-1'
        assert sanitize_numa_value('0,1,2') == '0-1-2'

    def test_cpu_range_preserved(self):
        """Test CPU ranges with hyphens are preserved."""
        assert sanitize_numa_value('16-31') == '16-31'
        assert sanitize_numa_value('0-63') == '0-63'

    def test_mixed_commas_and_ranges(self):
        """Test mixed commas and ranges."""
        # Edge case: "0-31,32-63" → "0-31-32-63"
        assert sanitize_numa_value('0-31,32-63') == '0-31-32-63'

    def test_forward_slash_sanitized(self):
        """Test forward slashes are converted to hyphens."""
        assert sanitize_numa_value('n/a') == 'na'  # Special case handled first
        assert sanitize_numa_value('0/1') == '0-1'  # Generic case

    def test_special_chars_sanitized(self):
        """Test other special characters are converted to hyphens."""
        assert sanitize_numa_value('0:1') == '0-1'
        assert sanitize_numa_value('0 1') == '0-1'
        assert sanitize_numa_value('0@1') == '0-1'

    def test_valid_chars_preserved(self):
        """Test valid characters (alphanumeric, underscore, period, hyphen) are preserved."""
        assert sanitize_numa_value('node_0') == 'node_0'
        assert sanitize_numa_value('1.5') == '1.5'
        assert sanitize_numa_value('auto-detect') == 'auto-detect'


@pytest.mark.unit
class TestContainerNameGeneration:
    """Test full container name generation."""

    def test_external_mode_name(self):
        """Test container name for external endpoint mode."""
        name = build_container_name(
            workload_type='chat_lite',
            core_name='external-endpoint',
            vllm_mems='n/a',
            loadgen_mems='0'
        )
        assert name == 'guidellm-chat_lite-external-endpoint-vllm-numana-loadgen-numa0'
        assert is_valid_container_name(name)

    def test_single_numa_name(self):
        """Test container name for single NUMA configuration."""
        name = build_container_name(
            workload_type='chat',
            core_name='32cores-single-socket',
            vllm_mems='0',
            loadgen_mems='0'
        )
        assert name == 'guidellm-chat-32cores-single-socket-vllm-numa0-loadgen-numa0'
        assert is_valid_container_name(name)

    def test_multi_numa_name(self):
        """Test container name for multi-NUMA configuration."""
        name = build_container_name(
            workload_type='rag',
            core_name='96cores-dual-socket-tp3',
            vllm_mems='0,1',
            loadgen_mems='0,1'
        )
        assert name == 'guidellm-rag-96cores-dual-socket-tp3-vllm-numa0-1-loadgen-numa0-1'
        assert is_valid_container_name(name)

    def test_workload_with_underscore(self):
        """Test workload types with underscores."""
        name = build_container_name(
            workload_type='chat_var',
            core_name='64cores-single-socket-tp2',
            vllm_mems='1',
            loadgen_mems='0'
        )
        assert is_valid_container_name(name)

    def test_no_forward_slashes(self):
        """Test that generated names never contain forward slashes."""
        # This was the original bug: exit code 125 from Docker/Podman
        name = build_container_name(
            workload_type='chat',
            core_name='test',
            vllm_mems='n/a',  # Contains forward slash
            loadgen_mems='n/a'
        )
        assert '/' not in name
        assert is_valid_container_name(name)

    def test_no_commas(self):
        """Test that generated names never contain commas."""
        name = build_container_name(
            workload_type='code',
            core_name='test',
            vllm_mems='0,1,2',  # Contains commas
            loadgen_mems='0,1'
        )
        assert ',' not in name
        assert is_valid_container_name(name)


@pytest.mark.unit
class TestContainerNameValidation:
    """Test container name validation against Docker/Podman rules."""

    def test_valid_names(self):
        """Test that valid names pass validation."""
        valid_names = [
            'guidellm-chat-test-vllm-numa0-loadgen-numa0',
            'guidellm-chat_lite-external-endpoint-vllm-numana-loadgen-numa0',
            'guidellm-rag-96cores-dual-socket-tp3-vllm-numa0-1-loadgen-numa0-1',
            'test-container_name.123',
        ]
        for name in valid_names:
            assert is_valid_container_name(name), f"Expected valid: {name}"

    def test_invalid_names_with_slash(self):
        """Test that names with slashes fail validation."""
        invalid_names = [
            'guidellm-chat-test-vllm-numan/a-loadgen-numa0',  # Original bug
            'test/container',
            'container/name/with/slashes',
        ]
        for name in invalid_names:
            assert not is_valid_container_name(name), f"Expected invalid: {name}"

    def test_invalid_names_with_comma(self):
        """Test that names with commas fail validation."""
        invalid_names = [
            'guidellm-chat-test-vllm-numa0,1-loadgen-numa0',
            'test,container',
        ]
        for name in invalid_names:
            assert not is_valid_container_name(name), f"Expected invalid: {name}"

    def test_invalid_names_with_other_chars(self):
        """Test that names with other invalid characters fail validation."""
        invalid_names = [
            'container@name',
            'container:tag',
            'container name',  # Space
            'container#123',
        ]
        for name in invalid_names:
            assert not is_valid_container_name(name), f"Expected invalid: {name}"

    def test_cannot_start_with_period(self):
        """Test that names starting with period fail validation."""
        assert not is_valid_container_name('.container')

    def test_cannot_start_with_hyphen(self):
        """Test that names starting with hyphen fail validation."""
        assert not is_valid_container_name('-container')

    def test_can_contain_period_hyphen_middle(self):
        """Test that period and hyphen are allowed in the middle."""
        assert is_valid_container_name('container.name')
        assert is_valid_container_name('container-name')
        assert is_valid_container_name('con.tainer-name_123')


@pytest.mark.unit
class TestRealWorldScenarios:
    """Test real-world scenarios from the codebase."""

    def test_external_endpoint_chat_lite(self):
        """Test the exact scenario that caused the original bug."""
        # Original error: guidellm-chat_lite-external-endpoint-vllm-numan/a-loadgen-numa0
        # Container exited with code 125
        name = build_container_name(
            workload_type='chat_lite',
            core_name='external-endpoint',
            vllm_mems='n/a',
            loadgen_mems='0'
        )

        # Verify no slash in name
        assert '/' not in name

        # Verify it's valid
        assert is_valid_container_name(name)

        # Verify expected output
        assert name == 'guidellm-chat_lite-external-endpoint-vllm-numana-loadgen-numa0'

    def test_aws_multi_socket_deployment(self):
        """Test AWS multi-socket deployment scenario."""
        # Hardware profile: 96cores-dual-socket-tp3 with cpuset_mems: "0,1"
        name = build_container_name(
            workload_type='summarization',
            core_name='96cores-dual-socket-tp3',
            vllm_mems='0,1',
            loadgen_mems='0,1'
        )

        assert is_valid_container_name(name)
        assert ',' not in name
        assert 'numa0-1' in name  # Comma should be converted to hyphen

    def test_variable_workload_types(self):
        """Test various workload type patterns."""
        workload_types = ['chat', 'chat_lite', 'chat_var', 'code', 'rag', 'summarization']

        for workload in workload_types:
            name = build_container_name(
                workload_type=workload,
                core_name='32cores-single-socket',
                vllm_mems='0',
                loadgen_mems='0'
            )
            assert is_valid_container_name(name), f"Invalid name for workload: {workload}"


if __name__ == "__main__":
    # Run tests if pytest not available
    import sys

    if HAS_PYTEST:
        sys.exit(pytest.main([__file__, "-v"]))
    else:
        print("pytest not available, running basic tests...")

        # Basic smoke tests
        test = TestNumaValueSanitization()
        test.test_external_mode_na()
        test.test_multi_numa_comma()
        test.test_cpu_range_preserved()
        print("✓ TestNumaValueSanitization passed")

        test2 = TestContainerNameGeneration()
        test2.test_external_mode_name()
        test2.test_multi_numa_name()
        test2.test_no_forward_slashes()
        test2.test_no_commas()
        print("✓ TestContainerNameGeneration passed")

        test3 = TestContainerNameValidation()
        test3.test_valid_names()
        test3.test_invalid_names_with_slash()
        test3.test_invalid_names_with_comma()
        print("✓ TestContainerNameValidation passed")

        test4 = TestRealWorldScenarios()
        test4.test_external_endpoint_chat_lite()
        test4.test_aws_multi_socket_deployment()
        test4.test_variable_workload_types()
        print("✓ TestRealWorldScenarios passed")

        print("\n✓ All basic tests passed!")
        sys.exit(0)
