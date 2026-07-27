"""Suite registry and loader for cpueval."""

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
from cpueval.paths import get_suites_dir


@dataclass
class Suite:
    """Represents a test suite configuration."""

    name: str
    description: str
    runner: str  # 'ansible' or 'script'
    target: str  # playbook name or script path
    defaults: Dict[str, Any]
    param_mappings: Dict[str, str]  # CLI param -> ansible/script param


class SuiteRegistry:
    """Registry for loading and managing test suites."""

    def __init__(self, suites_dir: Optional[Path] = None):
        """Initialize the suite registry.

        Args:
            suites_dir: Directory containing suite YAML files. Defaults to cpueval/suites.
        """
        self.suites_dir = suites_dir or get_suites_dir()
        self._suites: Dict[str, Suite] = {}
        self._load_suites()

    def _load_suites(self) -> None:
        """Load all suite definitions from YAML files."""
        if not self.suites_dir.exists():
            return

        for suite_file in self.suites_dir.glob("*.yaml"):
            try:
                with open(suite_file) as f:
                    data = yaml.safe_load(f)

                suite = Suite(
                    name=data["name"],
                    description=data.get("description", ""),
                    runner=data["runner"],
                    target=data["target"],
                    defaults=data.get("defaults", {}),
                    param_mappings=data.get("param_mappings", {}),
                )
                self._suites[suite.name] = suite
            except Exception as e:
                # Silently skip invalid suite files
                pass

    def list_suites(self) -> List[Suite]:
        """Get all registered suites."""
        return list(self._suites.values())

    def get_suite(self, name: str) -> Optional[Suite]:
        """Get a suite by name.

        Args:
            name: Suite name

        Returns:
            Suite object or None if not found
        """
        return self._suites.get(name)

    def suite_exists(self, name: str) -> bool:
        """Check if a suite exists.

        Args:
            name: Suite name

        Returns:
            True if suite exists
        """
        return name in self._suites
