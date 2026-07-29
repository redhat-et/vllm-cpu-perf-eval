"""Configuration manager for vLLM Dashboard.

Handles persistent storage of user configuration across dashboard sessions.
"""

import configparser
import os
from pathlib import Path

_LEGACY_LLM_RESULTS_DIRS = {
    "../../../../results/llm",
    "../../../../../results/llm",
    "results/llm",
}
_LEGACY_AUDIO_RESULTS_DIRS = {
    "../../../../results/audio-models",
    "../../../../../results/audio-models",
    "results/audio-models",
}


def _dashboard_dir() -> Path:
    return Path(__file__).resolve().parent


def _repo_root() -> Path:
    # vllm_dashboard -> dashboard-examples -> test-execution -> automation -> repo
    return _dashboard_dir().parent.parent.parent.parent


def default_llm_results_dir() -> str:
    return str(_repo_root() / "results" / "llm")


def default_audio_results_dir() -> str:
    return str(_repo_root() / "results" / "audio-models")


def resolve_results_path(path: str) -> str:
    """Resolve configured paths to an absolute path."""
    if path in _LEGACY_LLM_RESULTS_DIRS:
        return default_llm_results_dir()
    if path in _LEGACY_AUDIO_RESULTS_DIRS:
        return default_audio_results_dir()

    expanded = Path(path).expanduser()
    if expanded.is_absolute():
        return str(expanded)
    return str((_dashboard_dir() / expanded).resolve())


class DashboardConfig:
    """Manage dashboard configuration with persistent storage."""

    def __init__(self):
        """Initialize config manager."""
        # Config file location (in same directory as dashboard)
        self.config_dir = Path(__file__).parent
        self.config_file = self.config_dir / ".dashboard_config.ini"
        self.config = configparser.ConfigParser()

        # Load existing config or create default
        if self.config_file.exists():
            self.config.read(self.config_file)
        else:
            self._create_default_config()

    def _create_default_config(self):
        """Create default configuration."""
        self.config['Paths'] = {
            'results_directory': default_llm_results_dir(),
            'audio_results_directory': default_audio_results_dir(),
        }
        self._save_config()

    def _save_config(self):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def _normalize_results_path(self, path: str, legacy_paths: set[str], default: str) -> str:
        if path in legacy_paths:
            return default
        return resolve_results_path(path)

    def get_results_directory(self):
        """Get configured results directory path.

        Returns:
            str: Path to results directory
        """
        # Check environment variable first (highest priority)
        env_path = os.getenv('VLLM_DASHBOARD_RESULTS_DIR')
        if env_path:
            return resolve_results_path(env_path)

        # Fall back to config file
        if 'Paths' in self.config:
            stored = self.config['Paths'].get(
                'results_directory',
                default_llm_results_dir(),
            )
        else:
            stored = default_llm_results_dir()

        return self._normalize_results_path(
            stored, _LEGACY_LLM_RESULTS_DIRS, default_llm_results_dir()
        )

    def set_results_directory(self, path: str):
        """Set and persist results directory path.

        Args:
            path: Path to results directory
        """
        if 'Paths' not in self.config:
            self.config['Paths'] = {}

        self.config['Paths']['results_directory'] = resolve_results_path(path)
        self._save_config()

    def get_audio_results_directory(self):
        """Get configured audio results directory path.

        Returns:
            str: Path to audio results directory
        """
        env_path = os.getenv('VLLM_DASHBOARD_AUDIO_RESULTS_DIR')
        if env_path:
            return resolve_results_path(env_path)

        if 'Paths' in self.config:
            stored = self.config['Paths'].get(
                'audio_results_directory',
                default_audio_results_dir(),
            )
        else:
            stored = default_audio_results_dir()

        return self._normalize_results_path(
            stored, _LEGACY_AUDIO_RESULTS_DIRS, default_audio_results_dir()
        )

    def set_audio_results_directory(self, path: str):
        """Set and persist audio results directory path.

        Does not affect the LLM results directory.

        Args:
            path: Path to audio results directory
        """
        if 'Paths' not in self.config:
            self.config['Paths'] = {}

        self.config['Paths']['audio_results_directory'] = resolve_results_path(path)
        self._save_config()

def normalize_vllm_version(version_string):
    """Normalize vLLM version for display.

    Maps RHAIIS vLLM version strings to user-friendly display names.
    Future versions are displayed as-is until a new mapping is added.

    Args:
        version_string: Raw vLLM version from metadata

    Returns:
        Friendly RHAIIS label, or the original string if unmapped
    """
    if not version_string or version_string == 'unknown':
        return 'unknown'

    _RHAIIS_VERSION_MAP = {
        '0.18.0+rhaiv.7': 'RHAIIS_3.4',
        '0.24.0+rhaiv.2': 'RHAIIS_3.5',
    }

    return _RHAIIS_VERSION_MAP.get(version_string, version_string)
