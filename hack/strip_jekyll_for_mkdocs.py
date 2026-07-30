#!/usr/bin/env python3
"""Remove Jekyll front matter and Liquid {% raw %} wrappers from site markdown."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SITE_PAGES = {
    "documentation/index.md",
    "docs/index.md",
    "docs/sections/getting-started.md",
    "docs/getting-started.md",
    "docs/cpueval-cli.md",
    "docs/test-suites.md",
    "tests/concurrent-load/concurrent-load.md",
    "tests/scalability/scalability.md",
    "tests/offline-batch/offline-batch.md",
    "tests/embedding-models/embedding-models.md",
    "tests/audio-models/README.md",
    "tests/resource-contention/resource-contention.md",
    "docs/sections/running-tests.md",
    "docs/ansible/test-execution.md",
    "docs/ansible/model-predownload.md",
    "docs/scripts-reference.md",
    "docs/environment-variables.md",
    "models/models.md",
    "docs/embedding-models.md",
    "docs/audio-benchmarking.md",
    "docs/sections/results-analysis.md",
    "docs/dashboards-quickstart.md",
    "docs/mlflow.md",
    "docs/terminal-results-viewer.md",
    "docs/metrics-collection.md",
    "docs/sections/mteb-quality-testing.md",
    "docs/mteb-sweep-guide.md",
    "docs/mteb-timing-guide.md",
    "docs/mteb-troubleshooting.md",
    "docs/methodology/overview.md",
    "docs/methodology/testing-phases.md",
    "docs/methodology/metrics.md",
    "docs/methodology/reporting.md",
    "docs/methodology/manual-sweep.md",
    "docs/sections/configuration.md",
    "docs/platform-setup/x86/intel/deterministic-benchmarking.md",
    "docs/vllm-kv-cache-configuration.md",
    # Built but omitted from nav (linked from other pages)
    "docs/docs.md",
    "tests/tests.md",
    "docs/design/README.md",
    "docs/methodology/ietf-alignment.md",
    "docs/methodology/offline-batch.md",
    "tests/concurrent-load/rhaiis-testing.md",
    "tests/embedding-models/baseline-sweep.md",
    "tests/embedding-models/latency-concurrent.md",
    "models/audio-models/audio-models.md",
    "models/llm-models/llm-models.md",
}


def strip_front_matter(text: str) -> str:
    if text.startswith("---"):
        match = re.match(r"^---\n.*?\n---\n?", text, flags=re.DOTALL)
        if match:
            return text[match.end() :]
    return text


def strip_liquid_raw(body: str) -> str:
    stripped = body.lstrip("\n")
    if not stripped.startswith("{% raw %}"):
        return body
    inner = stripped[len("{% raw %}") :]
    if inner.startswith("\n"):
        inner = inner[1:]
    if inner.rstrip().endswith("{% endraw %}"):
        inner = inner.rstrip()[: -len("{% endraw %}")].rstrip("\n")
        return inner + ("\n" if inner else "")
    return body


def clean_file(rel_path: str) -> None:
    path = ROOT / rel_path
    if not path.exists():
        raise FileNotFoundError(path)
    body = strip_front_matter(path.read_text(encoding="utf-8"))
    body = strip_liquid_raw(body)
    path.write_text(body, encoding="utf-8")


def main() -> None:
    for rel_path in sorted(SITE_PAGES):
        clean_file(rel_path)
    print(f"Stripped Jekyll markup from {len(SITE_PAGES)} pages.")


if __name__ == "__main__":
    main()
