"""Suite registry and loader for cpueval."""

import sys
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
    matrix: bool = False  # True = full matrix by default, --model optional
    args_builder: Optional[str] = None  # e.g. offline_batch for positional scripts


class SuiteRegistry:
    """Registry for loading and managing test suites."""

    def __init__(self, suites_dir: Optional[Path] = None):
        """Initialize the suite registry.

        Args:
            suites_dir: Directory containing suite YAML files.
                Defaults to cpueval/suites.
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

                if not data:
                    print(
                        f"Warning: Empty suite file: {suite_file.name}",
                        file=sys.stderr,
                    )
                    continue

                # Validate required fields
                required = ["name", "runner", "target"]
                missing = [f for f in required if f not in data]
                if missing:
                    print(
                        f"Warning: Suite {suite_file.name} missing "
                        f"required fields: {', '.join(missing)}",
                        file=sys.stderr,
                    )
                    continue

                # Validate types
                name = data["name"]
                runner = data["runner"]
                target = data["target"]
                defaults = data.get("defaults", {})
                param_mappings = data.get("param_mappings", {})

                if not isinstance(name, str):
                    print(
                        f"Warning: Suite {suite_file.name} has non-string name",
                        file=sys.stderr,
                    )
                    continue
                if not isinstance(runner, str):
                    print(
                        f"Warning: Suite {suite_file.name} has non-string runner",
                        file=sys.stderr,
                    )
                    continue
                if not isinstance(target, str):
                    print(
                        f"Warning: Suite {suite_file.name} has non-string target",
                        file=sys.stderr,
                    )
                    continue
                if not isinstance(defaults, dict):
                    print(
                        f"Warning: Suite {suite_file.name} has non-mapping defaults",
                        file=sys.stderr,
                    )
                    continue
                if not isinstance(param_mappings, dict):
                    print(
                        f"Warning: Suite {suite_file.name} has non-mapping param_mappings",
                        file=sys.stderr,
                    )
                    continue

                suite = Suite(
                    name=name,
                    description=data.get("description", ""),
                    runner=runner,
                    target=target,
                    defaults=defaults,
                    param_mappings=param_mappings,
                    matrix=data.get("matrix", False),
                    args_builder=data.get("args_builder"),
                )
                self._suites[suite.name] = suite
            except yaml.YAMLError as e:
                print(
                    f"Warning: Invalid YAML in {suite_file.name}: {e}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"Warning: Failed to load suite {suite_file.name}: {e}",
                    file=sys.stderr,
                )

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
