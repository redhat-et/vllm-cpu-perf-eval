"""Build positional arguments for run-offline-batch-suite.sh from cpueval flags."""

from typing import Any, Dict, List, Optional

MODES_REQUIRING_MODEL = {
    "batch-scaling",
    "input-scaling",
    "output-scaling",
    "core-scaling",
    "kv-capacity",
    "context-scaling",
    "all",
}

MODES_WITH_OPTIONAL_CORES = {
    "batch-scaling",
    "input-scaling",
    "output-scaling",
    "kv-capacity",
    "context-scaling",
    "all",
}


DEFAULT_USE_CASE_SWEEP_MODELS = "all"
DEFAULT_USE_CASE_SWEEP_CORES = "8,16,24,32"
DEFAULT_BASELINE_CORES = "32"


def _resolve_models(vars: Dict[str, Any]) -> Optional[str]:
    return vars.get("models") or vars.get("model")


def build_offline_batch_args(vars: Dict[str, Any]) -> List[str]:
    """Translate structured cpueval vars into bash script positional arguments."""
    mode = str(vars.get("mode", "use-cases"))
    models = _resolve_models(vars)
    cores = vars.get("cores")
    runs = vars.get("runs")
    use_case = vars.get("use_case")
    dataset = vars.get("dataset")
    num_prompts = vars.get("num_prompts") or vars.get("prompts")

    args: List[str] = [mode]

    if mode == "use-cases":
        if runs is not None:
            args.append(str(runs))
        if models:
            args.append(str(models))

    elif mode == "use-case-sweep":
        if not use_case:
            raise ValueError(
                "use-case-sweep mode requires --use-case "
                "(e.g. summarization, classification, rag)"
            )
        args.append(str(use_case))

        effective_models = models
        effective_cores = cores
        if runs is not None and not (models and cores):
            effective_models = effective_models or DEFAULT_USE_CASE_SWEEP_MODELS
            effective_cores = effective_cores or DEFAULT_USE_CASE_SWEEP_CORES
        elif cores and not models:
            effective_models = DEFAULT_USE_CASE_SWEEP_MODELS

        if effective_models:
            args.append(str(effective_models))
        if effective_cores:
            args.append(str(effective_cores))
        if runs is not None:
            args.append(str(runs))

    elif mode == "baseline":
        effective_cores = cores
        if num_prompts is not None and not cores:
            effective_cores = DEFAULT_BASELINE_CORES
        if effective_cores:
            args.append(str(effective_cores))
        if num_prompts is not None:
            args.append(str(num_prompts))

    elif mode == "quantization":
        if cores:
            args.append(str(cores))
        if num_prompts is not None:
            args.append(str(num_prompts))

    elif mode in MODES_REQUIRING_MODEL:
        if not models:
            raise ValueError(f"{mode} mode requires --model or --models")
        args.append(str(models))
        if cores and mode in MODES_WITH_OPTIONAL_CORES:
            args.append(str(cores))

    elif mode in ("run_test", "run-test"):
        missing = []
        if not models:
            missing.append("--model")
        if not dataset:
            missing.append("--dataset")
        if num_prompts is None:
            missing.append("--num-prompts")
        if not cores:
            missing.append("--cores")
        if missing:
            raise ValueError(
                f"run_test mode requires {', '.join(missing)}"
            )
        args.extend([str(models), str(dataset), str(num_prompts), str(cores)])

    else:
        raise ValueError(
            f"Unknown offline-batch mode: {mode}. "
            "Use --extra args=\"...\" for unsupported modes."
        )

    return args
