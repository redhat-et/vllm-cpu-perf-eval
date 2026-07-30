#!/usr/bin/env python3
"""Apply Just the Docs navigation front matter to site markdown pages."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# parent/grand_parent titles must match an existing page title exactly.
NAV: dict[str, dict] = {
    "index.md": {
        "layout": "home",
        "title": "Home",
        "nav_order": 1,
        "description": "Comprehensive performance evaluation framework for vLLM on CPU platforms",
    },
    "docs/index.md": {
        "title": "Documentation",
        "nav_order": 2,
        "has_children": True,
    },
    "docs/sections/getting-started.md": {
        "title": "Getting Started",
        "parent": "Documentation",
        "nav_order": 1,
        "has_children": True,
    },
    "docs/getting-started.md": {
        "title": "Quick Start",
        "parent": "Getting Started",
        "grand_parent": "Documentation",
        "nav_order": 1,
    },
    "docs/cpueval-cli.md": {
        "title": "cpueval CLI",
        "parent": "Getting Started",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
    "docs/test-suites.md": {
        "title": "Test Suites",
        "parent": "Documentation",
        "nav_order": 3,
        "has_children": True,
    },
    "tests/concurrent-load/concurrent-load.md": {
        "title": "Concurrent Load",
        "parent": "Test Suites",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
    "tests/scalability/scalability.md": {
        "title": "Scalability",
        "parent": "Test Suites",
        "grand_parent": "Documentation",
        "nav_order": 3,
    },
    "tests/offline-batch/offline-batch.md": {
        "title": "Offline Batch",
        "parent": "Test Suites",
        "grand_parent": "Documentation",
        "nav_order": 4,
    },
    "tests/embedding-models/embedding-models.md": {
        "title": "Embedding Models",
        "parent": "Test Suites",
        "grand_parent": "Documentation",
        "nav_order": 5,
    },
    "tests/audio-models/README.md": {
        "title": "Audio Models",
        "parent": "Test Suites",
        "grand_parent": "Documentation",
        "nav_order": 6,
    },
    "tests/resource-contention/resource-contention.md": {
        "title": "Resource Contention",
        "parent": "Test Suites",
        "grand_parent": "Documentation",
        "nav_order": 7,
    },
    "docs/sections/running-tests.md": {
        "title": "Running Tests",
        "parent": "Documentation",
        "nav_order": 4,
        "has_children": True,
    },
    "docs/ansible/test-execution.md": {
        "title": "Ansible Automation",
        "parent": "Running Tests",
        "grand_parent": "Documentation",
        "nav_order": 1,
    },
    "docs/ansible/model-predownload.md": {
        "title": "Model Pre-download",
        "parent": "Running Tests",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
    "docs/scripts-reference.md": {
        "title": "Scripts Reference",
        "parent": "Running Tests",
        "grand_parent": "Documentation",
        "nav_order": 3,
    },
    "docs/environment-variables.md": {
        "title": "Environment Variables",
        "parent": "Running Tests",
        "grand_parent": "Documentation",
        "nav_order": 4,
    },
    "models/models.md": {
        "title": "Models",
        "parent": "Documentation",
        "nav_order": 5,
        "has_children": True,
    },
    "docs/embedding-models.md": {
        "title": "Embedding Models Guide",
        "parent": "Models",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
    "docs/audio-benchmarking.md": {
        "title": "Audio Benchmarking",
        "parent": "Models",
        "grand_parent": "Documentation",
        "nav_order": 3,
    },
    "docs/sections/results-analysis.md": {
        "title": "Results & Analysis",
        "parent": "Documentation",
        "nav_order": 6,
        "has_children": True,
    },
    "docs/dashboards-quickstart.md": {
        "title": "Dashboards",
        "parent": "Results & Analysis",
        "grand_parent": "Documentation",
        "nav_order": 1,
    },
    "docs/mlflow.md": {
        "title": "MLflow Tracking",
        "parent": "Results & Analysis",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
    "docs/terminal-results-viewer.md": {
        "title": "Terminal Results Viewer",
        "parent": "Results & Analysis",
        "grand_parent": "Documentation",
        "nav_order": 3,
    },
    "docs/metrics-collection.md": {
        "title": "Metrics Collection",
        "parent": "Results & Analysis",
        "grand_parent": "Documentation",
        "nav_order": 4,
    },
    "docs/sections/mteb-quality-testing.md": {
        "title": "MTEB Quality Testing",
        "parent": "Documentation",
        "nav_order": 7,
        "has_children": True,
    },
    "docs/mteb-sweep-guide.md": {
        "title": "MTEB Quick Start",
        "parent": "MTEB Quality Testing",
        "grand_parent": "Documentation",
        "nav_order": 1,
    },
    "docs/mteb-timing-guide.md": {
        "title": "MTEB Timing Guide",
        "parent": "MTEB Quality Testing",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
    "docs/mteb-troubleshooting.md": {
        "title": "MTEB Troubleshooting",
        "parent": "MTEB Quality Testing",
        "grand_parent": "Documentation",
        "nav_order": 3,
    },
    "docs/methodology/overview.md": {
        "title": "Methodology",
        "parent": "Documentation",
        "nav_order": 8,
        "has_children": True,
    },
    "docs/methodology/testing-phases.md": {
        "title": "Testing Phases",
        "parent": "Methodology",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
    "docs/methodology/metrics.md": {
        "title": "Metrics",
        "parent": "Methodology",
        "grand_parent": "Documentation",
        "nav_order": 3,
    },
    "docs/methodology/reporting.md": {
        "title": "Reporting",
        "parent": "Methodology",
        "grand_parent": "Documentation",
        "nav_order": 4,
    },
    "docs/methodology/manual-sweep.md": {
        "title": "Manual Sweep",
        "parent": "Methodology",
        "grand_parent": "Documentation",
        "nav_order": 5,
    },
    "docs/sections/configuration.md": {
        "title": "Configuration",
        "parent": "Documentation",
        "nav_order": 9,
        "has_children": True,
    },
    "docs/platform-setup/x86/intel/deterministic-benchmarking.md": {
        "title": "Platform Setup (Intel)",
        "parent": "Configuration",
        "grand_parent": "Documentation",
        "nav_order": 1,
    },
    "docs/vllm-kv-cache-configuration.md": {
        "title": "vLLM KV Cache",
        "parent": "Configuration",
        "grand_parent": "Documentation",
        "nav_order": 2,
    },
}

EXCLUDED = {
    "docs/docs.md",
    "tests/tests.md",
    "docs/design/README.md",
    "docs/design/full-testing-deck.md",
    "docs/design/cve-testing-deck.md",
    "docs/design/cve-testing-deck.md",
    "tests/concurrent-load/rhaiis-testing.md",
    "tests/embedding-models/baseline-sweep.md",
    "tests/embedding-models/latency-concurrent.md",
    "models/audio-models/audio-models.md",
    "models/llm-models/llm-models.md",
}


def yaml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def render_front_matter(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {yaml_value(value)}")
    lines.append("---\n")
    return "\n".join(lines)


def strip_front_matter(text: str) -> str:
    if text.startswith("---"):
        match = re.match(r"^---\n.*?\n---\n?", text, flags=re.DOTALL)
        if match:
            return text[match.end() :]
    return text


def apply_file(rel_path: str, meta: dict) -> None:
    path = ROOT / rel_path
    if not path.exists():
        raise FileNotFoundError(path)

    body = strip_front_matter(path.read_text(encoding="utf-8"))
    front = dict(meta)
    if rel_path != "index.md":
        front.setdefault("layout", "default")

  # Remove duplicate markdown H1 when title is set in front matter.
    if body.startswith("# "):
        first_line, _, remainder = body.partition("\n")
        title_from_h1 = first_line[2:].strip()
        if front.get("title") and title_from_h1 == front["title"]:
            body = remainder.lstrip("\n")

    path.write_text(render_front_matter(front) + body, encoding="utf-8")


def apply_excluded(rel_path: str) -> None:
    path = ROOT / rel_path
    if not path.exists():
        return
    body = strip_front_matter(path.read_text(encoding="utf-8"))
    front = {"nav_exclude": True, "layout": "default"}
    path.write_text(render_front_matter(front) + body, encoding="utf-8")


def main() -> None:
    for rel_path, meta in NAV.items():
        apply_file(rel_path, meta)
    for rel_path in EXCLUDED:
        apply_excluded(rel_path)
    print(f"Updated {len(NAV)} navigation pages and {len(EXCLUDED)} excluded pages.")


if __name__ == "__main__":
    main()
