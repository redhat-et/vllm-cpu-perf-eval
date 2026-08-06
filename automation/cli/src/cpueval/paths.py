"""Path management for cpueval."""

from pathlib import Path
from typing import Optional


def get_repo_root() -> Path:
    """Get the repository root directory."""
    # automation/cli/src/cpueval -> automation/cli -> automation -> repo root
    return Path(__file__).parent.parent.parent.parent.parent.resolve()


def get_ansible_dir() -> Path:
    """Get the Ansible directory."""
    return get_repo_root() / "automation" / "test-execution" / "ansible"


def get_inventory_path() -> Path:
    """Get the Ansible inventory path."""
    return get_ansible_dir() / "inventory" / "hosts.yml"


def get_playbook_path(playbook_name: str) -> Path:
    """Get the full path to an Ansible playbook."""
    return get_ansible_dir() / playbook_name


def get_results_dir() -> Path:
    """Get the results directory."""
    return get_repo_root() / "results"


def get_llm_results_dir() -> Path:
    """Get the LLM results directory."""
    return get_results_dir() / "llm"


def get_audio_results_dir() -> Path:
    """Get the audio results directory."""
    return get_results_dir() / "audio-models"


def get_embedding_results_dir() -> Path:
    """Get the embedding results directory."""
    return get_results_dir() / "embedding"


def get_dashboard_script() -> Path:
    """Get the dashboard launch script."""
    return (
        get_repo_root()
        / "automation"
        / "test-execution"
        / "dashboard-examples"
        / "vllm_dashboard"
        / "launch-dashboard.sh"
    )


def get_dashboard_stop_script() -> Path:
    """Get the dashboard stop script."""
    return (
        get_repo_root()
        / "automation"
        / "test-execution"
        / "dashboard-examples"
        / "vllm_dashboard"
        / "stop-dashboard.sh"
    )


def get_conversion_script() -> Path:
    """Get the batch conversion script."""
    return (
        get_repo_root()
        / "automation"
        / "test-execution"
        / "scripts"
        / "conversion"
        / "convert_batch.py"
    )


def get_last_run_hint_path() -> Path:
    """Get the last run hint file path."""
    return get_results_dir() / ".cpueval-last.json"


def get_suites_dir() -> Path:
    """Get the suites directory."""
    # Check for installed package data first
    pkg_suites = Path(__file__).parent / "suites"
    if pkg_suites.exists():
        return pkg_suites
    # Fall back to dev layout
    return Path(__file__).parent.parent.parent / "suites"


def get_profiles_dir() -> Path:
    """Get the profiles directory."""
    return Path(__file__).parent.parent.parent / "profiles"


def find_latest_result(
    model: Optional[str] = None, audio: bool = False
) -> Optional[Path]:
    """Find the latest result directory matching criteria.

    Args:
        model: Model name to filter by (optional)
        audio: Look in audio-models directory instead of llm

    Returns:
        Path to the latest matching result directory, or None if not found
    """
    base_dir = get_audio_results_dir() if audio else get_llm_results_dir()

    if not base_dir.exists():
        return None

    # Find all benchmark.json files
    benchmarks = list(base_dir.rglob("benchmarks.json"))
    if not benchmarks:
        return None

    # Get directories containing benchmarks.json
    result_dirs = [b.parent for b in benchmarks]

    # Filter by model if specified
    if model:
        # Model name is sanitized with __ instead of / in directory names
        model_safe = model.replace("/", "__")
        # Match model directory name exactly, not as substring
        result_dirs = [
            d for d in result_dirs
            if any(part == model_safe for part in d.parts)
        ]

    # Sort by modification time and return the latest
    if result_dirs:
        return max(result_dirs, key=lambda p: p.stat().st_mtime)

    return None


def find_latest_embedding_result(model: Optional[str] = None) -> Optional[Path]:
    """Find the latest embedding result directory.

    Embedding results use test-metadata.json (not benchmarks.json) under
    results/embedding/<model_dir>/<run_dir>/.

    Args:
        model: Model name to filter by (optional)

    Returns:
        Path to the latest matching result directory, or None if not found
    """
    base_dir = get_embedding_results_dir()

    if not base_dir.exists():
        return None

    metadata_files = list(base_dir.rglob("test-metadata.json"))
    if not metadata_files:
        return None

    result_dirs = [m.parent for m in metadata_files]

    if model:
        model_safe = model.replace("/", "__")
        result_dirs = [
            d for d in result_dirs
            if any(part == model_safe for part in d.parts)
        ]

    if result_dirs:
        return max(result_dirs, key=lambda p: p.stat().st_mtime)

    return None
