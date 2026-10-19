#!/usr/bin/env python3
"""
Contract tests for the benchmark playbooks.

Covers the failure classes found during pipeline validation runs:
  - playbooks must pass ansible syntax check when run from the ansible
    directory (where ansible.cfg and its roles_path live)
  - ansible.cfg must exist and its roles_path must point at an existing
    roles/ directory (include_role inside common/*.yml depends on it —
    running from elsewhere fails with "The role 'vllm_server' was not found")
  - every include_role name used anywhere must exist under roles/
  - extra-vars typing contract: -e "k=v" values stay strings, while a JSON
    document argument is parsed into real lists/dicts (the validation
    harness relies on this to pass embedding_workload_shapes/op_probe_levels)

Run with: python -m pytest unit/test_playbook_contracts.py -v -m unit
Or without pytest: python3 test_playbook_contracts.py
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

    class pytest:  # minimal fallback so the module works without pytest
        class mark:
            @staticmethod
            def unit(func):
                return func

        @staticmethod
        def skip(reason):
            print(f"SKIP: {reason}")

ANSIBLE_DIR = Path(__file__).resolve().parents[2]

# Playbooks exercised by the validation harness (+ their scale-out siblings)
HARNESS_PLAYBOOKS = [
    "llm-benchmark-auto.yml",
    "embedding-benchmark.yml",
    "llm-benchmark-scaleout.yml",
    "embedding-benchmark-scaleout.yml",
    "start-vllm-scaleout.yml",
    "stop-vllm-scaleout.yml",
]

# Files that are task/playbook fragments, not runnable playbooks
NON_PLAYBOOK_DIRS = {"tests", "filter_plugins", "roles"}


def _ansible_bin(name):
    path = shutil.which(name)
    if path is None:
        pytest.skip(f"{name} not installed")
    return path


def _run(cmd, cwd):
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=300
    )


@pytest.mark.unit
def test_ansible_cfg_roles_path_resolves():
    """include_role in common/*.yml only resolves via ansible.cfg roles_path,
    which ansible loads from the CWD — the cfg and its target must exist."""
    cfg = ANSIBLE_DIR / "ansible.cfg"
    assert cfg.is_file(), f"missing {cfg}"
    text = cfg.read_text()
    match = re.search(r"^roles_path\s*=\s*(.+)$", text, re.MULTILINE)
    assert match, "ansible.cfg has no roles_path"
    for entry in match.group(1).split(":"):
        entry = entry.strip()
        if not entry:
            continue
        target = (ANSIBLE_DIR / entry).resolve()
        assert target.is_dir(), f"roles_path entry does not exist: {target}"


@pytest.mark.unit
def test_include_role_names_exist():
    """Every role referenced via include_role must exist under roles/."""
    pattern = re.compile(
        r"include_role:\s*(?:\n\s*name:|\s*name:|\s*\{\s*name:\s*)\s*['\"]?([A-Za-z0-9_.-]+)"
    )
    referenced = set()
    for yml in ANSIBLE_DIR.rglob("*.yml"):
        if any(part in NON_PLAYBOOK_DIRS for part in yml.relative_to(ANSIBLE_DIR).parts):
            continue
        referenced.update(pattern.findall(yml.read_text()))
    assert referenced, "no include_role references found — scanner is broken"
    missing = sorted(
        name for name in referenced
        if not (ANSIBLE_DIR / "roles" / name).is_dir()
    )
    assert not missing, f"include_role references missing roles: {missing}"


@pytest.mark.unit
def test_harness_playbooks_syntax_check():
    """Main playbooks must pass --syntax-check from the ansible directory."""
    ansible_playbook = _ansible_bin("ansible-playbook")
    for playbook in HARNESS_PLAYBOOKS:
        path = ANSIBLE_DIR / playbook
        assert path.is_file(), f"missing playbook {path}"
        result = _run([ansible_playbook, "--syntax-check", str(path)], ANSIBLE_DIR)
        assert result.returncode == 0, (
            f"{playbook} failed syntax check:\n{result.stderr[-2000:]}"
        )


@pytest.mark.unit
def test_extra_vars_typing_contract():
    """-e 'k=v' keeps the value a string; a JSON document is parsed.

    The validation harness passes embedding_workload_shapes / op_probe_levels
    as a JSON document for exactly this reason.  If ansible ever changes this
    behavior, the harness needs updating.
    """
    ansible = _ansible_bin("ansible")
    debug = "msg={{ x | type_debug }}"

    result = _run(
        [ansible, "localhost", "-m", "debug", "-a", debug, "-e", "x=[8]"],
        ANSIBLE_DIR,
    )
    assert result.returncode == 0, result.stderr[-500:]
    assert '"msg": "str"' in result.stdout, (
        f"k=v value unexpectedly typed: {result.stdout}"
    )

    result = _run(
        [ansible, "localhost", "-m", "debug", "-a", debug, "-e", '{"x":[8]}'],
        ANSIBLE_DIR,
    )
    assert result.returncode == 0, result.stderr[-500:]
    assert '"msg": "list"' in result.stdout, (
        f"JSON document value not parsed as a list: {result.stdout}"
    )


@pytest.mark.unit
def test_no_self_referencing_include_vars():
    """Include/role params must not use themselves as a Jinja *fallback*.

    `var: "{{ x | default(var | ...) }}"` in include vars makes the param
    outrank group_vars and Ansible fails at runtime with "recursive loop
    detected in template" (broke single-instance embedding startup).  A var
    at the START of a template (set_fact-style `{{ var | default(...) }}`)
    is fine — only `| default(var ...)` fallbacks recurse.
    """
    pattern = re.compile(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[\"']\{\{.*\|\s*default\(\s*\1\b.*\}\}[\"']"
    )
    offenders = []
    for yml in (ANSIBLE_DIR / "common").glob("*.yml"):
        for lineno, line in enumerate(yml.read_text().splitlines(), 1):
            if pattern.match(line):
                offenders.append(f"{yml.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "self-referencing include vars (recursive template loops):\n  "
        + "\n  ".join(offenders)
    )


if __name__ == "__main__":
    tests = [
        test_ansible_cfg_roles_path_resolves,
        test_include_role_names_exist,
        test_harness_playbooks_syntax_check,
        test_extra_vars_typing_contract,
        test_no_self_referencing_include_vars,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
    sys.exit(1 if failed else 0)
