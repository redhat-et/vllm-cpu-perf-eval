"""Interactive wizard for launching cpueval test suites."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table

from cpueval.suite_registry import Suite, SuiteRegistry

MODEL_PRESETS = ("tiny", "quick", "small", "medium", "large", "llama", "qwen", "granite", "all")

OFFLINE_BATCH_MODES = (
    "use-cases",
    "use-case-sweep",
    "baseline",
    "batch-scaling",
    "input-scaling",
    "output-scaling",
    "core-scaling",
    "quantization",
    "kv-capacity",
    "context-scaling",
    "all",
    "run_test",
)

# CLI flag aliases in suite YAML — wizard shows one canonical field per group.
_ALIAS_GROUPS: Tuple[Tuple[str, ...], ...] = (
    ("models", "model"),
    ("workloads", "workload"),
    ("scenarios", "scenario"),
)

# Matrix LLM suites get a shorter customize flow (models + optional core/workload tailoring).
_LLM_MATRIX_SUITES = frozenset({"concurrent-load", "rhaiis-sweep"})

# Prompt order and help text for suite default keys.
FIELD_META: Dict[str, Dict[str, str]] = {
    "models": {
        "label": "Models",
        "help": f"Preset ({', '.join(MODEL_PRESETS)}) or comma-separated model IDs",
    },
    "model": {
        "label": "Model",
        "help": f"Preset ({', '.join(MODEL_PRESETS)}) or HuggingFace model ID",
    },
    "cores": {
        "label": "CPU cores",
        "help": "Comma-separated core counts (e.g. 8,16,32)",
    },
    "workloads": {
        "label": "Workloads",
        "help": "Comma-separated workloads (chat, code, summarization, rag)",
    },
    "workload": {
        "label": "Workload",
        "help": "Workload type (chat, code, summarization, rag)",
    },
    "scenario": {
        "label": "Scenario",
        "help": "Test scenario (suite-specific)",
    },
    "scenarios": {
        "label": "Scenarios",
        "help": "Comma-separated scenarios (suite-specific)",
    },
    "mode": {
        "label": "Offline-batch mode",
        "help": f"One of: {', '.join(OFFLINE_BATCH_MODES)}",
    },
    "runs": {
        "label": "Runs",
        "help": "Iteration count for offline-batch modes",
    },
    "tasks": {
        "label": "LM-eval tasks",
        "help": "Task preset (default) or comma-separated task names",
    },
    "batch_size": {
        "label": "Batch size",
        "help": "LM-eval batch size",
    },
    "num_prompts": {
        "label": "Number of prompts",
        "help": "Prompt count for embedding / offline-batch tests",
    },
    "phase": {
        "label": "Concurrent-load phase",
        "help": "Phase number for concurrent-load suite",
    },
    "dtype": {
        "label": "dtype",
        "help": "Model dtype (e.g. bfloat16, float16)",
    },
}

# Keys we expose in the wizard, in display order.
WIZARD_FIELD_ORDER = (
    "model",
    "models",
    "cores",
    "workloads",
    "workload",
    "scenario",
    "scenarios",
    "mode",
    "runs",
    "tasks",
    "batch_size",
    "num_prompts",
    "phase",
    "dtype",
)


@dataclass
class WizardResult:
    """Collected parameters from the wizard."""

    suite: str
    model: Optional[str] = None
    models: Optional[str] = None
    cores: Optional[str] = None
    workload: Optional[str] = None
    workloads: Optional[str] = None
    scenario: Optional[str] = None
    mode: Optional[str] = None
    runs: Optional[int] = None
    num_prompts: Optional[int] = None
    vllm_cpus: Optional[str] = None
    vllm_numa: Optional[int] = None
    guidellm_cpus: Optional[str] = None
    guidellm_numa: Optional[int] = None
    tag: Optional[str] = None
    extra: Optional[List[str]] = None
    dry_run: bool = False
    skip_doctor: bool = False

    def as_execute_kwargs(self) -> Dict[str, Any]:
        """Convert to kwargs for _execute_suite (unset fields are None)."""
        return {
            "suite": self.suite,
            "model": self.model,
            "models": self.models,
            "cores": self.cores,
            "workload": self.workload,
            "workloads": self.workloads,
            "scenario": self.scenario,
            "mode": self.mode,
            "runs": self.runs,
            "use_case": None,
            "dataset": None,
            "num_prompts": self.num_prompts,
            "input_len": None,
            "output_len": None,
            "preset": None,
            "tensor_parallel": None,
            "vllm_cpus": self.vllm_cpus,
            "vllm_cpu_start": None,
            "vllm_numa": self.vllm_numa,
            "guidellm_cpus": self.guidellm_cpus,
            "guidellm_numa": self.guidellm_numa,
            "profile": None,
            "endpoint_url": None,
            "vllm_bench_cpus": None,
            "vllm_bench_numa": None,
            "max_seconds": None,
            "continue_on_error": False,
            "tag": self.tag,
            "extra": self.extra,
            "extra_vars_file": None,
            "ansible_arg": None,
            "dry_run": self.dry_run,
            "skip_doctor": self.skip_doctor,
        }


class _PromptDriver:
    """Prompt helper with optional scripted inputs for tests."""

    def __init__(
        self,
        inputs: Optional[List[str]] = None,
        prompt_fn: Optional[Callable[..., str]] = None,
        confirm_fn: Optional[Callable[..., bool]] = None,
    ):
        self._inputs = list(inputs or [])
        self._index = 0
        self._prompt_fn = prompt_fn or typer.prompt
        self._confirm_fn = confirm_fn or typer.confirm

    def prompt(self, text: str, default: Optional[str] = None) -> str:
        if self._index < len(self._inputs):
            value = self._inputs[self._index]
            self._index += 1
            if value == "" and default is not None:
                return str(default)
            return value
        return self._prompt_fn(text, default=default)

    def confirm(self, text: str, default: bool = False) -> bool:
        if self._index < len(self._inputs):
            value = self._inputs[self._index].strip().lower()
            self._index += 1
            if value in ("y", "yes", "true", "1"):
                return True
            if value in ("n", "no", "false", "0"):
                return False
            return default
        return self._confirm_fn(text, default=default)


def _sorted_suites(registry: SuiteRegistry) -> List[Suite]:
    """Return suites with quick-start suites first, then alphabetical."""
    priority = {"chat-smoke": 0, "health": 1}
    suites = registry.list_suites()
    return sorted(suites, key=lambda s: (priority.get(s.name, 100), s.name))


def _suite_requires_model(suite: Suite) -> bool:
    if suite.matrix:
        return False
    return "model" in suite.param_mappings or "models" in suite.param_mappings


def _pick_alias_field(suite: Suite, group: Tuple[str, ...], present: List[str]) -> str:
    """Pick one CLI field when a suite maps several aliases to the same flag."""
    if suite.matrix:
        if group[0] in present:
            return group[0]
        return present[0]
    if len(group) > 1 and group[1] in present:
        return group[1]
    return present[0]


def _wizard_fields_for_suite(suite: Suite) -> List[str]:
    """Determine which parameters the wizard should offer for a suite."""
    raw_keys = set(suite.defaults.keys()) | set(suite.param_mappings.keys())
    chosen: List[str] = []
    consumed: set[str] = set()

    for group in _ALIAS_GROUPS:
        present = [key for key in group if key in raw_keys]
        if not present:
            continue
        chosen.append(_pick_alias_field(suite, group, present))
        consumed.update(group)

    order_index = {key: index for index, key in enumerate(WIZARD_FIELD_ORDER)}
    for key in WIZARD_FIELD_ORDER:
        if key in raw_keys and key not in consumed:
            chosen.append(key)

    if _suite_requires_model(suite) and "model" not in chosen and "models" not in chosen:
        chosen.insert(0, "model")

    return sorted(chosen, key=lambda key: order_index.get(key, 999))


def _default_for_field(suite: Suite, field: str) -> Optional[str]:
    if field in suite.defaults:
        return str(suite.defaults[field])
    mapped = suite.param_mappings.get(field)
    if mapped and mapped in suite.defaults:
        return str(suite.defaults[mapped])
    return None


def get_host_env_status() -> Dict[str, Any]:
    """Return configured target host environment for display in the wizard."""
    mode = os.getenv("VLLM_ENDPOINT_MODE", "managed")
    status: Dict[str, Any] = {
        "mode": mode,
        "dut_hostname": os.getenv("DUT_HOSTNAME"),
        "loadgen_hostname": os.getenv("LOADGEN_HOSTNAME"),
        "endpoint_url": os.getenv("VLLM_ENDPOINT_URL"),
        "hf_token_set": bool(os.getenv("HF_TOKEN")),
    }
    if mode == "external":
        status["hosts_ready"] = bool(status["endpoint_url"])
        status["missing"] = [] if status["hosts_ready"] else ["VLLM_ENDPOINT_URL"]
    else:
        missing = []
        if not status["dut_hostname"]:
            missing.append("DUT_HOSTNAME")
        if not status["loadgen_hostname"]:
            missing.append("LOADGEN_HOSTNAME")
        status["missing"] = missing
        status["hosts_ready"] = not missing
    return status


def _print_target_hosts(console: Console) -> bool:
    """Show target host configuration. Returns True when ready to continue."""
    status = get_host_env_status()
    console.print("[bold]Target hosts[/bold]")

    if status["mode"] == "external":
        if status["endpoint_url"]:
            console.print(f"  Mode: external")
            console.print(f"  VLLM_ENDPOINT_URL: [green]{status['endpoint_url']}[/green]")
        else:
            console.print("  Mode: external")
            console.print("  [red]VLLM_ENDPOINT_URL is not set[/red]")
    else:
        console.print("  Mode: managed")
        if status["dut_hostname"]:
            console.print(f"  DUT_HOSTNAME: [green]{status['dut_hostname']}[/green]")
        else:
            console.print("  DUT_HOSTNAME: [red]not set[/red]")
        if status["loadgen_hostname"]:
            console.print(f"  LOADGEN_HOSTNAME: [green]{status['loadgen_hostname']}[/green]")
        else:
            console.print("  LOADGEN_HOSTNAME: [red]not set[/red]")

    if status["hf_token_set"]:
        console.print("  HF_TOKEN: [green]set[/green]")
    else:
        console.print("  HF_TOKEN: [yellow]not set[/yellow] (needed for some gated models)")

    if not status["hosts_ready"]:
        console.print()
        console.print("[dim]Set hosts before running benchmarks:[/dim]")
        if status["mode"] == "external":
            console.print("  export VLLM_ENDPOINT_MODE=external")
            console.print("  export VLLM_ENDPOINT_URL=http://<host>:8000/v1")
        else:
            console.print("  export DUT_HOSTNAME=<dut-host>")
            console.print("  export LOADGEN_HOSTNAME=<loadgen-host>")

    console.print()
    return status["hosts_ready"]


def _parse_optional_int(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{field} must be an integer, got: {value}") from exc


def _suite_supports_cpu_pinning(suite: Suite) -> bool:
    return "vllm_cpus" in suite.param_mappings or "guidellm_cpus" in suite.param_mappings


def _prompt_keep_default(driver: _PromptDriver, label: str, default: str) -> str:
    """Prompt for an override; Enter keeps the default value."""
    value = driver.prompt(f"{label} [{default}] (Enter to keep default)", default="").strip()
    return value or default


def _prompt_optional_pinning(driver: _PromptDriver, label: str, hint: str) -> Optional[str]:
    """Prompt for an optional CPU pinning value; Enter skips."""
    value = driver.prompt(f"{label} ({hint}, Enter to skip)", default="").strip()
    return value or None


def select_suite_by_index(suites: List[Suite], choice: str) -> Optional[Suite]:
    """Resolve a numeric menu choice to a suite."""
    choice = choice.strip()
    if not choice.isdigit():
        return None
    index = int(choice) - 1
    if index < 0 or index >= len(suites):
        return None
    return suites[index]


def build_params_from_answers(
    suite: Suite,
    answers: Dict[str, str],
    *,
    tag: Optional[str] = None,
    dry_run: bool = False,
    skip_doctor: bool = False,
) -> WizardResult:
    """Build a WizardResult from explicit answers (used by tests and review step)."""
    result = WizardResult(
        suite=suite.name,
        tag=tag,
        dry_run=dry_run,
        skip_doctor=skip_doctor,
    )
    extra_pairs: List[str] = []

    for field, value in answers.items():
        if value is None or value == "":
            continue
        if field == "model":
            result.model = value
        elif field == "models":
            result.models = value
        elif field == "cores":
            result.cores = value
        elif field == "workload":
            result.workload = value
        elif field == "workloads":
            result.workloads = value
        elif field == "scenario":
            result.scenario = value
        elif field == "scenarios":
            result.scenario = value
        elif field == "mode":
            result.mode = value
        elif field == "runs":
            result.runs = _parse_optional_int(value, "runs")
        elif field == "num_prompts":
            result.num_prompts = _parse_optional_int(value, "num_prompts")
        elif field == "vllm_cpus":
            result.vllm_cpus = value
        elif field == "vllm_numa_node":
            result.vllm_numa = _parse_optional_int(value, "vllm_numa_node")
        elif field == "guidellm_cpus":
            result.guidellm_cpus = value
        elif field == "guidellm_numa_node":
            result.guidellm_numa = _parse_optional_int(value, "guidellm_numa_node")
        elif field in ("tasks", "batch_size", "phase", "dtype"):
            extra_pairs.append(f"{field}={value}")

    if extra_pairs:
        result.extra = extra_pairs

    return result


def _matrix_scope_warning(suite: Suite, answers: Dict[str, str]) -> Optional[str]:
    """Return a warning when the selected scope may be large."""
    if not suite.matrix:
        return None
    models = answers.get("models") or answers.get("model") or suite.defaults.get("models") or suite.defaults.get("model")
    if models == "all":
        return (
            f"[yellow]'{suite.name}' with models=all may run a large matrix "
            f"(many combinations). Consider --models tiny for a quick run.[/yellow]"
        )
    return None


def _print_suite_menu(console: Console, suites: List[Suite]) -> None:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Suite", style="cyan", width=22)
    table.add_column("Type", width=10)
    table.add_column("Description")

    for idx, suite in enumerate(suites, start=1):
        suite_type = "Matrix" if suite.matrix else "Single"
        description = suite.description
        if len(description) > 55:
            description = description[:52] + "..."
        table.add_row(str(idx), suite.name, suite_type, description)

    console.print()
    console.print("[bold]Select a test suite[/bold]")
    console.print(table)
    console.print()


def _print_defaults(console: Console, suite: Suite) -> None:
    console.print(f"\n[bold cyan]{suite.name}[/bold cyan] — {suite.description}\n")
    if suite.defaults:
        console.print("[bold]Defaults[/bold]")
        for key, value in suite.defaults.items():
            console.print(f"  {key}: {value}")
        console.print()
    elif _suite_requires_model(suite):
        console.print("[dim]No defaults — model is required for this suite.[/dim]\n")
    else:
        console.print("[dim]No configurable defaults — ready to run as-is.[/dim]\n")


def _prompt_field(
    driver: _PromptDriver,
    suite: Suite,
    field: str,
    *,
    required: bool = False,
) -> str:
    meta = FIELD_META.get(field, {"label": field, "help": ""})
    default = _default_for_field(suite, field)
    label = meta["label"]
    help_text = meta["help"]
    prompt_text = f"{label}"
    if help_text:
        prompt_text += f" ({help_text})"

    while True:
        value = driver.prompt(prompt_text, default=default)
        value = value.strip()
        if required and not value:
            continue
        return value


def _collect_cpu_pinning(
    driver: _PromptDriver,
    console: Console,
    suite: Suite,
    answers: Dict[str, str],
) -> None:
    """Collect optional DUT / load-generator CPU pinning for LLM matrix suites."""
    if not _suite_supports_cpu_pinning(suite):
        return

    console.print()
    console.print(
        "[bold]CPU pinning[/bold] (optional — pin vLLM on DUT and GuideLLM on load generator)"
    )
    console.print(
        "[dim]Example: DUT vLLM 64-95 NUMA 1, load generator 0-31 NUMA 0 "
        "(see profiles/dual-socket-split.yaml)[/dim]"
    )

    vllm_cpus = _prompt_optional_pinning(driver, "DUT vLLM CPU range", "e.g. 64-95")
    if vllm_cpus:
        answers["vllm_cpus"] = vllm_cpus

    vllm_numa = _prompt_optional_pinning(driver, "DUT vLLM NUMA node", "e.g. 1")
    if vllm_numa:
        answers["vllm_numa_node"] = vllm_numa

    guidellm_cpus = _prompt_optional_pinning(
        driver, "Load generator CPU range", "e.g. 0-31"
    )
    if guidellm_cpus:
        answers["guidellm_cpus"] = guidellm_cpus

    guidellm_numa = _prompt_optional_pinning(
        driver, "Load generator NUMA node", "e.g. 0"
    )
    if guidellm_numa:
        answers["guidellm_numa_node"] = guidellm_numa


def _collect_llm_matrix_answers(
    driver: _PromptDriver,
    suite: Suite,
    console: Console,
) -> Dict[str, str]:
    """Tailored prompts for concurrent-load style matrix suites."""
    answers: Dict[str, str] = {}

    models_default = _default_for_field(suite, "models") or "all"
    models = driver.prompt(
        f"Models ({FIELD_META['models']['help']})",
        default=models_default,
    ).strip()
    if models:
        answers["models"] = models

    cores_default = _default_for_field(suite, "cores") or "8,16,32"
    answers["cores"] = _prompt_keep_default(driver, "CPU cores", cores_default)

    _collect_cpu_pinning(driver, console, suite, answers)

    workloads_default = _default_for_field(suite, "workloads") or "chat,code,summarization,rag"
    answers["workloads"] = _prompt_keep_default(driver, "Workloads", workloads_default)

    phase_default = _default_for_field(suite, "phase")
    if phase_default:
        answers["phase"] = phase_default

    return answers


def _collect_answers(
    driver: _PromptDriver,
    suite: Suite,
    console: Console,
    *,
    customize: bool,
) -> Dict[str, str]:
    fields = _wizard_fields_for_suite(suite)
    answers: Dict[str, str] = {}

    if not customize:
        for field in fields:
            default = _default_for_field(suite, field)
            if default is not None:
                answers[field] = default
        return answers

    if suite.name in _LLM_MATRIX_SUITES:
        return _collect_llm_matrix_answers(driver, suite, console)

    requires_model = _suite_requires_model(suite)
    for field in fields:
        required = requires_model and field in ("model", "models")
        value = _prompt_field(driver, suite, field, required=required)
        if value:
            answers[field] = value

    if requires_model and not answers.get("model") and not answers.get("models"):
        raise typer.Exit(1)

    return answers


def _print_summary(console: Console, suite: Suite, answers: Dict[str, str], result: WizardResult) -> None:
    console.print("\n[bold]Run summary[/bold]")
    console.print(f"  Suite: [cyan]{suite.name}[/cyan]")
    for field in _wizard_fields_for_suite(suite):
        value = answers.get(field, _default_for_field(suite, field) or "—")
        label = FIELD_META.get(field, {}).get("label", field)
        console.print(f"  {label}: {value}")
    if result.vllm_cpus:
        console.print(f"  DUT vLLM CPUs: {result.vllm_cpus}")
    if result.vllm_numa is not None:
        console.print(f"  DUT vLLM NUMA: {result.vllm_numa}")
    if result.guidellm_cpus:
        console.print(f"  Load generator CPUs: {result.guidellm_cpus}")
    if result.guidellm_numa is not None:
        console.print(f"  Load generator NUMA: {result.guidellm_numa}")
    if result.tag:
        console.print(f"  Tag: {result.tag}")
    flags = []
    if result.dry_run:
        flags.append("dry-run")
    if result.skip_doctor:
        flags.append("skip-doctor")
    if flags:
        console.print(f"  Flags: {', '.join(flags)}")
    console.print()


def run_wizard(
    console: Console,
    registry: Optional[SuiteRegistry] = None,
    *,
    inputs: Optional[List[str]] = None,
    force_dry_run: bool = False,
    force_skip_doctor: bool = False,
) -> Optional[WizardResult]:
    """Run the interactive wizard. Returns None if the user cancels."""
    registry = registry or SuiteRegistry()
    suites = _sorted_suites(registry)
    if not suites:
        console.print("[red]No suites found.[/red]")
        raise typer.Exit(1)

    driver = _PromptDriver(inputs=inputs)

    _print_suite_menu(console, suites)
    while True:
        choice = driver.prompt("Suite number (or q to quit)", default="1")
        if choice.strip().lower() in ("q", "quit", "exit"):
            return None
        suite = select_suite_by_index(suites, choice)
        if suite is not None:
            break
        console.print("[red]Invalid choice — enter a number from the list.[/red]")

    _print_defaults(console, suite)

    hosts_ready = _print_target_hosts(console)
    if not hosts_ready and not driver.confirm(
        "Host configuration is incomplete. Continue anyway?",
        default=False,
    ):
        console.print("[dim]Cancelled.[/dim]")
        return None

    has_fields = bool(_wizard_fields_for_suite(suite))
    customize = False
    if has_fields:
        customize = driver.confirm("Customize parameters?", default=False)

    answers = _collect_answers(driver, suite, console, customize=customize)

    warning = _matrix_scope_warning(suite, answers)
    if warning:
        console.print(f"\n{warning}\n")

    tag = driver.prompt("Result tag (optional, Enter to skip)", default="").strip() or None

    dry_run = force_dry_run
    if not force_dry_run:
        dry_run = driver.confirm("Dry run only (show command, do not execute)?", default=False)

    skip_doctor = force_skip_doctor
    if not force_skip_doctor:
        skip_doctor = driver.confirm("Skip pre-flight health checks?", default=False)

    result = build_params_from_answers(
        suite,
        answers,
        tag=tag,
        dry_run=dry_run,
        skip_doctor=skip_doctor,
    )
    _print_summary(console, suite, answers, result)

    if not driver.confirm("Launch benchmark?", default=True):
        console.print("[dim]Cancelled.[/dim]")
        return None

    return result
