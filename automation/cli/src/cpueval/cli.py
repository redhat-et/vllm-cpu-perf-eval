"""Main CLI for cpueval."""

import os
import re
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from cpueval import __version__
from cpueval.doctor import run_doctor
from cpueval.paths import (
    get_profiles_dir,
    get_llm_results_dir,
    get_audio_results_dir,
    get_embedding_results_dir,
)
from cpueval.results import (
    run_results_command,
    run_dashboard_command,
    run_dashboard_stop_command,
    save_last_run_hint,
    find_latest_result,
    find_latest_embedding_result,
)
from cpueval.install import run_install
from cpueval.offline_batch import build_offline_batch_args
from cpueval.runners import (
    load_profile,
    merge_extra_vars,
    run_ansible,
    run_script,
)
from cpueval.suite_registry import SuiteRegistry

app = typer.Typer(
    help="cpueval - Thin CLI wrapper over Ansible CPU automation",
    no_args_is_help=True,
)

console = Console()

_PRESET_NAMES = (
    "all", "quick", "small", "large", "medium",
    "tiny", "llama", "qwen", "granite",
)


def _complete_suite(ctx, param, incomplete: str):
    """Return suite names for shell completion."""
    try:
        registry = SuiteRegistry()
        return [
            s.name for s in registry.list_suites()
            if s.name.startswith(incomplete)
        ]
    except Exception:
        return []


def _discovered_models(incomplete: str) -> list[str]:
    """Scan results directories and return matching model names."""
    models: set[str] = set()
    try:
        dirs = (
            get_llm_results_dir(),
            get_audio_results_dir(),
            get_embedding_results_dir(),
        )
        for results_dir in dirs:
            if results_dir.exists():
                for p in results_dir.iterdir():
                    if p.is_dir():
                        model_name = p.name.replace("__", "/")
                        if model_name.startswith(incomplete):
                            models.add(model_name)
    except Exception:
        pass
    return sorted(models)


def _complete_model(ctx, param, incomplete: str):
    """Complete --model: benchmarked model names from results directories."""
    return _discovered_models(incomplete)


def _complete_models(ctx, param, incomplete: str):
    """Complete --models: preset names union benchmarked model names."""
    presets = [p for p in _PRESET_NAMES if p.startswith(incomplete)]
    return presets + [
        m for m in _discovered_models(incomplete) if m not in presets
    ]


def _complete_profile(ctx, param, incomplete: str):
    """Return profile names for shell completion."""
    try:
        profiles_dir = get_profiles_dir()
        return [
            p.stem for p in sorted(profiles_dir.glob("*.yaml"))
            if p.stem.startswith(incomplete)
        ]
    except Exception:
        return []


def _apply_endpoint_env(endpoint_url: Optional[str]) -> None:
    """Configure external endpoint mode when --endpoint-url is set."""
    if endpoint_url:
        os.environ["VLLM_ENDPOINT_MODE"] = "external"
        os.environ["VLLM_ENDPOINT_URL"] = endpoint_url


def _build_script_args(suite_obj, final_vars: dict) -> List[str]:
    """Build script CLI args from merged vars and suite param_mappings."""
    script_args: List[str] = []
    for key, value in final_vars.items():
        if value is None or value == "":
            continue

        flag = suite_obj.param_mappings.get(key)
        if not flag:
            continue

        if not flag.startswith("--"):
            flag = f"--{flag}"

        if isinstance(value, bool):
            if value:
                script_args.append(flag)
            continue

        script_args.extend([flag, str(value)])

    return script_args


def _result_model_hint(
    model: Optional[str],
    models: Optional[str],
    final_vars: dict,
) -> Optional[str]:
    """Pick a model filter for find_latest_result after a script suite run."""
    for candidate in (
        model,
        models,
        final_vars.get("test_model"),
        final_vars.get("models"),
    ):
        if candidate and candidate not in _PRESET_NAMES:
            return candidate
    return None


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        console.print(f"cpueval {__version__}")
        raise typer.Exit()


def _uninstall_completion(prog_name: str, shell: Optional[str]) -> None:
    """Remove installed shell completion file and rc-file source line."""
    from pathlib import Path

    if shell is None:
        try:
            import shellingham
            shell, _ = shellingham.detect_shell()
        except Exception:
            console.print(
                "[red]Could not detect shell. "
                "Run the command from inside a bash or zsh session.[/red]"
            )
            raise typer.Exit(1)

    home = Path.home()

    if shell == "zsh":
        path = home / f".zfunc/_{prog_name}"
        if path.exists():
            path.unlink()
            console.print(f"[green]Removed {path}[/green]")
        else:
            console.print(f"[yellow]Not found: {path}[/yellow]")
        # The fpath/compinit lines added to .zshrc during install are intentionally
        # left in place — they may be shared with other tools.
        console.print("[dim]Note: .zshrc setup lines (fpath, compinit) are not removed.[/dim]")
        console.print("[dim]Restart your shell or run 'exec zsh' to apply.[/dim]")

    elif shell == "bash":
        path = home / ".bash_completions" / f"{prog_name}.sh"
        if path.exists():
            path.unlink()
            console.print(f"[green]Removed {path}[/green]")
        else:
            console.print(f"[yellow]Not found: {path}[/yellow]")
        rc = home / ".bashrc"
        # Match both "source" and "." forms, with single, double, or no quotes.
        _src_re = re.compile(
            r'^\s*(?:source|\.)\s+["\']?' + re.escape(str(path)) + r'["\']?\s*$'
        )
        if rc.exists():
            lines = rc.read_text().splitlines(keepends=True)
            filtered = [l for l in lines if not _src_re.match(l)]
            if len(filtered) < len(lines):
                rc.write_text("".join(filtered))
                console.print(f"[green]Removed source line from {rc}[/green]")
        console.print("[dim]Restart your shell or run 'exec bash' to apply.[/dim]")

    else:
        console.print(f"[red]Shell '{shell}' is not supported. Use bash or zsh.[/red]")
        raise typer.Exit(1)


def uninstall_completion_callback(value: bool):
    """Eager callback for --uninstall-completion."""
    if value:
        _uninstall_completion(prog_name="cpueval", shell=None)
        raise typer.Exit()


def _execute_suite(
    suite: str,
    model: Optional[str],
    models: Optional[str],
    cores: Optional[str],
    workload: Optional[str],
    workloads: Optional[str],
    scenario: Optional[str],
    mode: Optional[str],
    runs: Optional[int],
    use_case: Optional[str],
    dataset: Optional[str],
    num_prompts: Optional[int],
    input_len: Optional[int],
    output_len: Optional[int],
    preset: Optional[str],
    tensor_parallel: Optional[int],
    vllm_cpus: Optional[str],
    vllm_cpu_start: Optional[int],
    vllm_numa: Optional[int],
    guidellm_cpus: Optional[str],
    guidellm_numa: Optional[int],
    profile: Optional[str],
    endpoint_url: Optional[str],
    vllm_bench_cpus: Optional[str],
    vllm_bench_numa: Optional[int],
    continue_on_error: bool,
    max_seconds: Optional[int],
    extra: Optional[List[str]],
    extra_vars_file: Optional[str],
    ansible_arg: Optional[List[str]],
    dry_run: bool,
    skip_doctor: bool,
) -> None:
    registry = SuiteRegistry()
    suite_obj = registry.get_suite(suite)

    if not suite_obj:
        console.print(f"[red]Suite not found: {suite}[/red]")
        console.print("\nRun 'cpueval list' to see available suites.")
        raise typer.Exit(1)

    # Validate --model for non-matrix suites (only if suite uses model/models mapping)
    requires_model = "model" in suite_obj.param_mappings or "models" in suite_obj.param_mappings
    if not suite_obj.matrix and requires_model and not model and not models:
        console.print(f"[red]Error: --model is required for suite '{suite}'[/red]")
        console.print(f"\nSuite '{suite}' is not a matrix suite.")
        console.print("Use --model to specify a single model.")
        raise typer.Exit(1)

    # Run doctor unless skipped or dry-run
    if not skip_doctor and not dry_run:
        console.print("[cyan]Running pre-flight checks...[/cyan]")
        doctor_exit = run_doctor(no_ping=True)
        if doctor_exit != 0:
            console.print("\n[yellow]Warning: Some health checks failed. Use --skip-doctor to bypass.[/yellow]")
            raise typer.Exit(doctor_exit)
        console.print()

    # Build CLI vars from options
    cli_vars = {}

    # Handle model/models
    # For script runners: store CLI key (models, model) for later flag mapping
    # For ansible runners: store mapped ansible var name immediately
    if model or models:
        effective_models = models or model
        if suite_obj.runner == "script":
            # Script suites: keep as "models" or "model" key for param_mappings lookup
            cli_vars["models" if models or suite_obj.matrix else "model"] = effective_models
        else:
            # Ansible suites: use mapped ansible var name
            if models or (suite_obj.matrix and "models" in suite_obj.param_mappings):
                mapped_key = suite_obj.param_mappings.get("models", "test_model")
                cli_vars[mapped_key] = effective_models
            elif "model" in suite_obj.param_mappings:
                cli_vars[suite_obj.param_mappings["model"]] = effective_models
            else:
                cli_vars["test_model"] = effective_models

    if cores:
        if suite_obj.runner == "script":
            # Script suites: keep as "cores" for param_mappings lookup
            cli_vars["cores"] = cores
        else:
            # Ansible suites: use mapped ansible var name (e.g., requested_cores)
            mapped_key = suite_obj.param_mappings.get("cores", "requested_cores")
            try:
                cli_vars[mapped_key] = int(cores)
            except ValueError:
                cli_vars[mapped_key] = cores

    if workload or workloads:
        effective_workloads = workloads or workload
        if suite_obj.runner == "script":
            # Script suites: normalize to plural "workloads" to avoid alias conflicts
            cli_vars["workloads"] = effective_workloads
        else:
            # Ansible suites: use mapped ansible var name
            mapped_key = suite_obj.param_mappings.get("workload", "base_workload")
            cli_vars[mapped_key] = effective_workloads

    if scenario:
        if suite_obj.runner == "script":
            # Script suites: normalize to plural "scenarios" if that's what suite uses
            # Check if suite defaults/mappings use plural form
            if "scenarios" in suite_obj.param_mappings or "scenarios" in suite_obj.defaults:
                cli_vars["scenarios"] = scenario
            else:
                cli_vars["scenario"] = scenario
        else:
            # Ansible suites: use mapped ansible var name (e.g., test_scenario)
            mapped_key = suite_obj.param_mappings.get("scenario", "test_scenario")
            cli_vars[mapped_key] = scenario

    if mode:
        cli_vars["mode"] = mode

    if runs is not None:
        cli_vars["runs"] = runs

    if use_case:
        cli_vars["use_case"] = use_case

    if dataset:
        cli_vars["dataset"] = dataset

    if num_prompts is not None:
        cli_vars["num_prompts"] = num_prompts

    if input_len is not None:
        cli_vars["input_len"] = input_len

    if output_len is not None:
        cli_vars["output_len"] = output_len

    if preset:
        # Deprecated, but still support it
        console.print("[yellow]Warning: --preset is deprecated, use --models instead[/yellow]")
        if "models" in suite_obj.param_mappings:
            cli_vars["models"] = preset
        else:
            cli_vars[suite_obj.param_mappings.get("preset", "test_model_preset")] = preset

    if tensor_parallel:
        cli_vars["requested_tensor_parallel"] = tensor_parallel

    # CPU pinning vars
    if vllm_cpus:
        cli_vars["vllm_cpus"] = vllm_cpus
    if vllm_cpu_start is not None:
        if not vllm_cpus:
            console.print(
                "[yellow]Warning: --vllm-cpu-start is deprecated; "
                "use --vllm-cpus (e.g., --vllm-cpus 64-95)[/yellow]"
            )
        cli_vars["vllm_cpu_start"] = vllm_cpu_start

    if vllm_numa is not None:
        cli_vars["vllm_numa_node"] = vllm_numa

    if guidellm_cpus:
        cli_vars["guidellm_cpus"] = guidellm_cpus

    if guidellm_numa is not None:
        cli_vars["guidellm_numa_node"] = guidellm_numa

    if vllm_bench_cpus:
        cli_vars["vllm_bench_cpus"] = vllm_bench_cpus

    if vllm_bench_numa is not None:
        cli_vars["vllm_bench_numa_node"] = vllm_bench_numa

    if continue_on_error:
        cli_vars["continue_on_error"] = True

    if max_seconds is not None:
        cli_vars["guidellm_max_seconds"] = max_seconds

    _apply_endpoint_env(endpoint_url)

    # Load profile if specified
    profile_vars = {}
    if profile:
        try:
            profile_vars = load_profile(profile, get_profiles_dir())
            console.print(f"[cyan]Loaded profile: {profile}[/cyan]")
        except FileNotFoundError:
            console.print(f"[red]Profile not found: {profile}[/red]")
            available = sorted(get_profiles_dir().glob("*.yaml"))
            if available:
                names = ", ".join(p.stem for p in available)
                console.print(
                    f"[dim]Available profiles: {names}[/dim]"
                )
            console.print(
                "[dim]Run 'cpueval profiles' to list profiles.[/dim]"
            )
            raise typer.Exit(1)
        except ValueError as e:
            console.print(f"[red]Invalid profile: {e}[/red]")
            raise typer.Exit(1)

    # Merge all extra vars
    try:
        final_vars = merge_extra_vars(
            suite_defaults=suite_obj.defaults,
            profile_vars=profile_vars,
            cli_vars=cli_vars,
            extra_pairs=extra or [],
            extra_vars_file=extra_vars_file,
        )
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # vllm_cpus (fixed range) takes precedence over vllm_cpu_start (offset).
    # Drop vllm_cpu_start so it is never forwarded alongside vllm_cpus.
    if final_vars.get("vllm_cpus"):
        final_vars.pop("vllm_cpu_start", None)

    # Execute based on runner type
    if suite_obj.runner == "ansible":
        exit_code = run_ansible(suite_obj.target, final_vars, ansible_arg or [], dry_run=dry_run)

        # Save last run hint on success (skip for dry-run)
        if exit_code == 0 and not dry_run:
            result_dir = find_latest_result(
                model=model, audio="audio" in suite
            )
            save_last_run_hint(suite, model, result_dir)

            if result_dir:
                console.print(f"\n[green]✓ Results saved to: {result_dir}[/green]")
                console.print("\nView results:")
                console.print("  cpueval results --last")
                console.print("  cpueval dashboard start\n")

        raise typer.Exit(exit_code)

    elif suite_obj.runner == "script":
        script_args: List[str] = []

        if "args" in final_vars:
            # Explicit override via --extra args="..." (highest precedence)
            raw_args = final_vars["args"]
            script_args = raw_args.split() if isinstance(raw_args, str) else list(raw_args)
        elif suite_obj.args_builder == "offline_batch":
            try:
                script_args = build_offline_batch_args(final_vars)
            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                raise typer.Exit(1)
        else:
            # Flag-based script suites (e.g. rhaiis-sweep)
            script_args = _build_script_args(suite_obj, final_vars)

        exit_code = run_script(suite_obj.target, script_args, dry_run=dry_run)

        # Save last run hint on success (skip for dry-run)
        if exit_code == 0 and not dry_run:
            model_hint = (
                model
                or models
                or final_vars.get("models")
                or final_vars.get("mode")
                or suite
            )
            result_model = _result_model_hint(model, models, final_vars)
            if "embedding" in suite:
                result_dir = find_latest_embedding_result(model=result_model)
            else:
                result_dir = find_latest_result(
                    model=result_model,
                    audio="audio" in suite,
                )
            save_last_run_hint(suite, model_hint, result_dir)

            if result_dir:
                console.print(f"\n[green]✓ Results saved to: {result_dir}[/green]")
                console.print("\nView results:")
                console.print("  cpueval results --last")
                console.print("  cpueval dashboard start\n")

        raise typer.Exit(exit_code)

    else:
        console.print(f"[red]Unknown runner type: {suite_obj.runner}[/red]")
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    uninstall_completion: Optional[bool] = typer.Option(
        None,
        "--uninstall-completion",
        callback=uninstall_completion_callback,
        is_eager=True,
        expose_value=False,
        help="Uninstall completion for the current shell (bash/zsh).",
    ),
    suite: Optional[str] = typer.Option(
        None, "--suite", "-s", help="Suite name",
        shell_complete=_complete_suite,
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model ID (single model)",
        shell_complete=_complete_model,
    ),
    models: Optional[str] = typer.Option(
        None, "--models", help="Models preset or comma-list (matrix suites)",
        shell_complete=_complete_models,
    ),
    cores: Optional[str] = typer.Option(None, "--cores", "-c", help="Core counts (comma-separated or single)"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Workload type"),
    workloads: Optional[str] = typer.Option(None, "--workloads", help="Workloads (comma-separated, matrix suites)"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="Test scenario"),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        help=(
            "Offline-batch mode: use-cases, use-case-sweep, baseline, batch-scaling, "
            "input-scaling, output-scaling, core-scaling, quantization, kv-capacity, "
            "context-scaling, all, run_test"
        ),
    ),
    runs: Optional[int] = typer.Option(
        None, "--runs", help="Iteration count (offline-batch use-cases / use-case-sweep)"
    ),
    use_case: Optional[str] = typer.Option(
        None, "--use-case", help="Use case name (offline-batch use-case-sweep mode)"
    ),
    dataset: Optional[str] = typer.Option(
        None, "--dataset", help="Dataset name (offline-batch run_test mode)"
    ),
    num_prompts: Optional[int] = typer.Option(
        None, "--num-prompts", help="Prompt count (offline-batch run_test / baseline)"
    ),
    input_len: Optional[int] = typer.Option(
        None, "--input-len", help="Input token length (offline-batch random dataset)"
    ),
    output_len: Optional[int] = typer.Option(
        None, "--output-len", help="Output token length (offline-batch random/sharegpt)"
    ),
    preset: Optional[str] = typer.Option(None, "--preset", help="Model preset (deprecated, use --models)"),
    tensor_parallel: Optional[int] = typer.Option(None, "--tensor-parallel", help="Tensor parallel size"),
    vllm_cpus: Optional[str] = typer.Option(None, "--vllm-cpus", help="vLLM CPU range (e.g., 64-95 or 64,65,66)"),
    vllm_cpu_start: Optional[int] = typer.Option(None, "--vllm-cpu-start", help="vLLM CPU start core (deprecated: use --vllm-cpus)"),
    vllm_numa: Optional[int] = typer.Option(None, "--vllm-numa", help="vLLM NUMA node"),
    guidellm_cpus: Optional[str] = typer.Option(None, "--guidellm-cpus", help="GuideLLM CPU range (e.g., 0-31)"),
    guidellm_numa: Optional[int] = typer.Option(None, "--guidellm-numa", help="GuideLLM NUMA node"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Load CPU pinning profile",
        shell_complete=_complete_profile,
    ),
    endpoint_url: Optional[str] = typer.Option(
        None,
        "--endpoint-url",
        help="External vLLM endpoint URL (sets VLLM_ENDPOINT_MODE=external)",
    ),
    vllm_bench_cpus: Optional[str] = typer.Option(
        None, "--vllm-bench-cpus", help="CPU range for embedding vllm-bench container"
    ),
    vllm_bench_numa: Optional[int] = typer.Option(
        None, "--vllm-bench-numa-node", help="NUMA node for embedding vllm-bench container"
    ),
    max_seconds: Optional[int] = typer.Option(
        None, "--max-seconds", help="Per-test time limit in seconds (embedding suite)"
    ),
    continue_on_error: bool = typer.Option(
        False, "--continue-on-error", help="Continue matrix run after a failure"
    ),
    extra: Optional[List[str]] = typer.Option(None, "--extra", help="Extra vars (KEY=VAL, repeatable)"),
    extra_vars_file: Optional[str] = typer.Option(None, "--extra-vars-file", help="Load extra vars from YAML/JSON"),
    ansible_arg: Optional[List[str]] = typer.Option(None, "--ansible-arg", help="Raw ansible-playbook args (repeatable)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print command without running"),
    skip_doctor: bool = typer.Option(False, "--skip-doctor", help="Skip pre-run health check"),
):
    """cpueval - Thin CLI wrapper over Ansible CPU automation.

    Run options below apply when no subcommand is given (e.g. cpueval --suite …).
    Subcommands (list, doctor, run) take precedence when specified.
    """
    if ctx.invoked_subcommand is not None:
        return
    if suite is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    _execute_suite(
        suite=suite,
        model=model,
        models=models,
        cores=cores,
        workload=workload,
        workloads=workloads,
        scenario=scenario,
        mode=mode,
        runs=runs,
        use_case=use_case,
        dataset=dataset,
        num_prompts=num_prompts,
        input_len=input_len,
        output_len=output_len,
        preset=preset,
        tensor_parallel=tensor_parallel,
        vllm_cpus=vllm_cpus,
        vllm_cpu_start=vllm_cpu_start,
        vllm_numa=vllm_numa,
        guidellm_cpus=guidellm_cpus,
        guidellm_numa=guidellm_numa,
        profile=profile,
        endpoint_url=endpoint_url,
        vllm_bench_cpus=vllm_bench_cpus,
        vllm_bench_numa=vllm_bench_numa,
        continue_on_error=continue_on_error,
        max_seconds=max_seconds,
        extra=extra,
        extra_vars_file=extra_vars_file,
        ansible_arg=ansible_arg,
        dry_run=dry_run,
        skip_doctor=skip_doctor,
    )


@app.command()
def list():
    """List available test suites."""
    registry = SuiteRegistry()
    suites = registry.list_suites()

    if not suites:
        console.print("[yellow]No suites found. Check automation/cli/suites/[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", width=25)
    table.add_column("Type", width=12)
    table.add_column("Runner", width=10)
    table.add_column("Description")

    for suite in suites:
        suite_type = "[green]Matrix[/green]" if suite.matrix else "[yellow]Single[/yellow]"
        table.add_row(
            suite.name,
            suite_type,
            suite.runner,
            suite.description[:60] + "..." if len(suite.description) > 60 else suite.description,
        )

    console.print()
    console.print(table)
    console.print()
    console.print("[dim]Legend:[/dim] [green]Matrix[/green] = full test matrix by default, [yellow]Single[/yellow] = requires --model")
    console.print()


@app.command()
def show(suite_name: str = typer.Argument(..., help="Suite name", shell_complete=_complete_suite)):
    """Show detailed information about a suite."""
    registry = SuiteRegistry()
    suite = registry.get_suite(suite_name)

    if not suite:
        console.print(f"[red]Suite not found: {suite_name}[/red]")
        console.print("\nRun 'cpueval list' to see available suites.")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Suite: {suite.name}[/bold cyan]\n")
    console.print(f"[dim]Description:[/dim] {suite.description}")
    console.print(f"[dim]Runner:[/dim] {suite.runner}")
    console.print(f"[dim]Target:[/dim] {suite.target}")

    if suite.matrix:
        console.print(
            "[dim]Type:[/dim] [green]Matrix suite[/green]"
            " (runs full test matrix by default)"
        )
    else:
        console.print(
            "[dim]Type:[/dim] [yellow]Single-shot[/yellow] (--model required)"
        )
    console.print()

    if suite.defaults:
        console.print("[bold]Default Parameters:[/bold]")
        for key, value in suite.defaults.items():
            console.print(f"  {key}: {value}")
        console.print()

        if suite.matrix:
            console.print("[dim]This suite runs the full matrix by default.[/dim]")
            console.print("[dim]Use CLI flags to narrow the scope:[/dim]")
            if "models" in suite.defaults:
                console.print("  --models <preset|list> to select specific models")
            if "cores" in suite.defaults:
                console.print("  --cores <list> to select specific core counts")
            if "workloads" in suite.defaults:
                console.print("  --workloads <list> to select specific workloads")
            if suite.args_builder == "offline_batch":
                console.print("  --mode <mode> to select test mode (default: use-cases)")
                console.print("  --runs <n> for use-cases / use-case-sweep iteration count")
                console.print("  --use-case <name> for use-case-sweep mode")
                console.print("  --models / --model for model selection")
                console.print("  --cores <list> for core sweep modes")
                console.print("  --dataset / --num-prompts for run_test mode")
                console.print("  --input-len / --output-len for dataset token lengths")
            console.print()

    if suite.param_mappings:
        console.print("[bold]Parameter Mappings:[/bold]")
        for cli_param, ansible_param in suite.param_mappings.items():
            console.print(f"  --{cli_param} → {ansible_param}")
        console.print()

    if suite.source_path:
        console.print(f"[dim]Suite definition:[/dim] {suite.source_path}")
        console.print(
            "[dim]Edit that file to change permanent defaults.[/dim]"
        )
        console.print()


@app.command()
def profiles():
    """List available CPU pinning profiles."""
    profiles_dir = get_profiles_dir()
    if not profiles_dir.exists():
        console.print(
            f"[yellow]No profiles directory found at {profiles_dir}[/yellow]"
        )
        return

    profile_files = sorted(profiles_dir.glob("*.yaml"))
    if not profile_files:
        console.print("[yellow]No profiles found.[/yellow]")
        console.print(
            f"Add YAML files to {profiles_dir} to create profiles."
        )
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", width=25)
    table.add_column("Path", style="dim")

    for pf in profile_files:
        table.add_row(pf.stem, str(pf))

    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]Profile directory:[/dim] {profiles_dir}")
    console.print(
        "[dim]Use with:[/dim] cpueval --suite <suite> --profile <name>"
    )
    console.print()


@app.command()
def install(
    skip_system_deps: bool = typer.Option(
        False, "--skip-system-deps", help="Skip system package installation (dnf)"
    ),
    skip_collections: bool = typer.Option(
        False, "--skip-collections", help="Skip Ansible collection installation"
    ),
    skip_completion: bool = typer.Option(
        False, "--skip-completion", help="Skip shell tab-completion setup"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print commands without running them"),
):
    """Install prerequisites: system packages, Ansible collections, and shell completion."""
    exit_code = run_install(
        skip_system_deps=skip_system_deps,
        skip_collections=skip_collections,
        skip_completion=skip_completion,
        dry_run=dry_run,
    )
    raise typer.Exit(exit_code)


@app.command()
def doctor(
    no_ping: bool = typer.Option(False, "--no-ping", help="Skip host connectivity check"),
):
    """Run system health checks."""
    exit_code = run_doctor(no_ping=no_ping)
    raise typer.Exit(exit_code)


# Keep in sync with main() callback options.
@app.command()
def run(
    suite: str = typer.Option(
        ..., "--suite", "-s", help="Suite name (required)",
        shell_complete=_complete_suite,
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Model ID (single model)",
        shell_complete=_complete_model,
    ),
    models: Optional[str] = typer.Option(
        None, "--models", help="Models preset or comma-list (matrix suites)",
        shell_complete=_complete_models,
    ),
    cores: Optional[str] = typer.Option(None, "--cores", "-c", help="Core counts (comma-separated or single)"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Workload type"),
    workloads: Optional[str] = typer.Option(None, "--workloads", help="Workloads (comma-separated, matrix suites)"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="Test scenario"),
    mode: Optional[str] = typer.Option(
        None,
        "--mode",
        help=(
            "Offline-batch mode: use-cases, use-case-sweep, baseline, batch-scaling, "
            "input-scaling, output-scaling, core-scaling, quantization, kv-capacity, "
            "context-scaling, all, run_test"
        ),
    ),
    runs: Optional[int] = typer.Option(
        None, "--runs", help="Iteration count (offline-batch use-cases / use-case-sweep)"
    ),
    use_case: Optional[str] = typer.Option(
        None, "--use-case", help="Use case name (offline-batch use-case-sweep mode)"
    ),
    dataset: Optional[str] = typer.Option(
        None, "--dataset", help="Dataset name (offline-batch run_test mode)"
    ),
    num_prompts: Optional[int] = typer.Option(
        None, "--num-prompts", help="Prompt count (offline-batch run_test / baseline)"
    ),
    input_len: Optional[int] = typer.Option(
        None, "--input-len", help="Input token length (offline-batch random dataset)"
    ),
    output_len: Optional[int] = typer.Option(
        None, "--output-len", help="Output token length (offline-batch random/sharegpt)"
    ),
    preset: Optional[str] = typer.Option(None, "--preset", help="Model preset (deprecated, use --models)"),
    tensor_parallel: Optional[int] = typer.Option(None, "--tensor-parallel", help="Tensor parallel size"),
    vllm_cpus: Optional[str] = typer.Option(None, "--vllm-cpus", help="vLLM CPU range (e.g., 64-95 or 64,65,66)"),
    vllm_cpu_start: Optional[int] = typer.Option(None, "--vllm-cpu-start", help="vLLM CPU start core (deprecated: use --vllm-cpus)"),
    vllm_numa: Optional[int] = typer.Option(None, "--vllm-numa", help="vLLM NUMA node"),
    guidellm_cpus: Optional[str] = typer.Option(None, "--guidellm-cpus", help="GuideLLM CPU range (e.g., 0-31)"),
    guidellm_numa: Optional[int] = typer.Option(None, "--guidellm-numa", help="GuideLLM NUMA node"),
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Load CPU pinning profile",
        shell_complete=_complete_profile,
    ),
    endpoint_url: Optional[str] = typer.Option(
        None,
        "--endpoint-url",
        help="External vLLM endpoint URL (sets VLLM_ENDPOINT_MODE=external)",
    ),
    vllm_bench_cpus: Optional[str] = typer.Option(
        None, "--vllm-bench-cpus", help="CPU range for embedding vllm-bench container"
    ),
    vllm_bench_numa: Optional[int] = typer.Option(
        None, "--vllm-bench-numa-node", help="NUMA node for embedding vllm-bench container"
    ),
    max_seconds: Optional[int] = typer.Option(
        None, "--max-seconds", help="Per-test time limit in seconds (embedding suite)"
    ),
    continue_on_error: bool = typer.Option(
        False, "--continue-on-error", help="Continue matrix run after a failure"
    ),
    extra: Optional[List[str]] = typer.Option(None, "--extra", help="Extra vars (KEY=VAL, repeatable)"),
    extra_vars_file: Optional[str] = typer.Option(None, "--extra-vars-file", help="Load extra vars from YAML/JSON"),
    ansible_arg: Optional[List[str]] = typer.Option(None, "--ansible-arg", help="Raw ansible-playbook args (repeatable)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print command without running"),
    skip_doctor: bool = typer.Option(False, "--skip-doctor", help="Skip pre-run health check"),
):
    """Run a test suite (alias; prefer: cpueval --suite …)."""
    _execute_suite(
        suite=suite,
        model=model,
        models=models,
        cores=cores,
        workload=workload,
        workloads=workloads,
        scenario=scenario,
        mode=mode,
        runs=runs,
        use_case=use_case,
        dataset=dataset,
        num_prompts=num_prompts,
        input_len=input_len,
        output_len=output_len,
        preset=preset,
        tensor_parallel=tensor_parallel,
        vllm_cpus=vllm_cpus,
        vllm_cpu_start=vllm_cpu_start,
        vllm_numa=vllm_numa,
        guidellm_cpus=guidellm_cpus,
        guidellm_numa=guidellm_numa,
        profile=profile,
        endpoint_url=endpoint_url,
        vllm_bench_cpus=vllm_bench_cpus,
        vllm_bench_numa=vllm_bench_numa,
        continue_on_error=continue_on_error,
        max_seconds=max_seconds,
        extra=extra,
        extra_vars_file=extra_vars_file,
        ansible_arg=ansible_arg,
        dry_run=dry_run,
        skip_doctor=skip_doctor,
    )


@app.command()
def results(
    path: Optional[str] = typer.Argument(None, help="Specific result path"),
    last: bool = typer.Option(False, "--last", "-l", help="Show last run results"),
    list_flag: bool = typer.Option(False, "--list", help="List recent results"),
    limit: int = typer.Option(10, "--limit", help="Limit for --list"),
    open_dashboard: bool = typer.Option(False, "--open", help="Launch dashboard"),
    convert: bool = typer.Option(False, "--convert", help="Run conversion script"),
    view: bool = typer.Option(True, "--view/--no-view", help="Show terminal summary"),
):
    """View and manage benchmark results."""
    exit_code = run_results_command(
        path=path,
        last=last,
        list_results_flag=list_flag,
        limit=limit,
        open_dashboard=open_dashboard,
        convert=convert,
        view=view,
    )
    raise typer.Exit(exit_code)


dashboard_app = typer.Typer(help="Manage the results dashboard", no_args_is_help=True)
app.add_typer(dashboard_app, name="dashboard")


@dashboard_app.command("start")
def dashboard_start():
    """Start the results dashboard (background, port 8501)."""
    exit_code = run_dashboard_command()
    raise typer.Exit(exit_code)


@dashboard_app.command("stop")
def dashboard_stop():
    """Stop the running results dashboard."""
    exit_code = run_dashboard_stop_command()
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
