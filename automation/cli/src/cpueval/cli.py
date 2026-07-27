"""Main CLI for cpueval."""

from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from cpueval import __version__
from cpueval.doctor import run_doctor
from cpueval.paths import get_profiles_dir
from cpueval.results import (
    run_results_command,
    run_dashboard_command,
    save_last_run_hint,
    find_latest_result,
)
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


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        console.print(f"cpueval {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """cpueval - Thin CLI wrapper over Ansible CPU automation."""
    pass


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
def show(suite_name: str = typer.Argument(..., help="Suite name")):
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
        console.print(f"[dim]Type:[/dim] [green]Matrix suite[/green] (runs full test matrix by default)")
    else:
        console.print(f"[dim]Type:[/dim] [yellow]Single-shot[/yellow] (--model required)")
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
            console.print()

    if suite.param_mappings:
        console.print("[bold]Parameter Mappings:[/bold]")
        for cli_param, ansible_param in suite.param_mappings.items():
            console.print(f"  --{cli_param} → {ansible_param}")
        console.print()


@app.command()
def doctor(
    no_ping: bool = typer.Option(False, "--no-ping", help="Skip host connectivity check"),
):
    """Run system health checks."""
    exit_code = run_doctor(no_ping=no_ping)
    raise typer.Exit(exit_code)


@app.command()
def run(
    suite: str = typer.Option(..., "--suite", "-s", help="Suite name (required)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model ID (single model)"),
    models: Optional[str] = typer.Option(None, "--models", help="Models preset or comma-list (matrix suites)"),
    cores: Optional[str] = typer.Option(None, "--cores", "-c", help="Core counts (comma-separated or single)"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Workload type"),
    workloads: Optional[str] = typer.Option(None, "--workloads", help="Workloads (comma-separated, matrix suites)"),
    scenario: Optional[str] = typer.Option(None, "--scenario", help="Test scenario"),
    mode: Optional[str] = typer.Option(None, "--mode", help="Test mode (offline-batch: use-cases|baseline|all)"),
    preset: Optional[str] = typer.Option(None, "--preset", help="Model preset (deprecated, use --models)"),
    tensor_parallel: Optional[int] = typer.Option(None, "--tensor-parallel", help="Tensor parallel size"),
    vllm_cpu_start: Optional[int] = typer.Option(None, "--vllm-cpu-start", help="vLLM CPU start core"),
    vllm_numa: Optional[int] = typer.Option(None, "--vllm-numa", help="vLLM NUMA node"),
    guidellm_cpus: Optional[str] = typer.Option(None, "--guidellm-cpus", help="GuideLLM CPU range (e.g., 0-31)"),
    guidellm_numa: Optional[int] = typer.Option(None, "--guidellm-numa", help="GuideLLM NUMA node"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Load CPU pinning profile"),
    extra: Optional[List[str]] = typer.Option(None, "--extra", help="Extra vars (KEY=VAL, repeatable)"),
    extra_vars_file: Optional[str] = typer.Option(None, "--extra-vars-file", help="Load extra vars from YAML/JSON"),
    ansible_arg: Optional[List[str]] = typer.Option(None, "--ansible-arg", help="Raw ansible-playbook args (repeatable)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print command without running"),
    skip_doctor: bool = typer.Option(False, "--skip-doctor", help="Skip pre-run health check"),
):
    """Run a test suite."""
    registry = SuiteRegistry()
    suite_obj = registry.get_suite(suite)

    if not suite_obj:
        console.print(f"[red]Suite not found: {suite}[/red]")
        console.print("\nRun 'cpueval list' to see available suites.")
        raise typer.Exit(1)

    # Validate --model for non-matrix suites
    if not suite_obj.matrix and not model and not models:
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
    if vllm_cpu_start is not None:
        cli_vars["vllm_cpu_start"] = vllm_cpu_start

    if vllm_numa is not None:
        cli_vars["vllm_numa_node"] = vllm_numa

    if guidellm_cpus:
        cli_vars["guidellm_cpus"] = guidellm_cpus

    if guidellm_numa is not None:
        cli_vars["guidellm_numa_node"] = guidellm_numa

    # Load profile if specified
    profile_vars = {}
    if profile:
        try:
            profile_vars = load_profile(profile, get_profiles_dir())
            console.print(f"[cyan]Loaded profile: {profile}[/cyan]")
        except FileNotFoundError:
            console.print(f"[red]Profile not found: {profile}[/red]")
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
                console.print("  cpueval dashboard\n")

        raise typer.Exit(exit_code)

    elif suite_obj.runner == "script":
        # Build script args from param_mappings
        script_args = []

        # For matrix suites, use the param_mappings to convert keys to CLI flags
        for key, value in final_vars.items():
            # Skip empty values
            if value is None or value == "":
                continue

            # Find the script flag for this key
            flag = suite_obj.param_mappings.get(key)
            if flag:
                # param_mappings for script suites should have --flag format
                if not flag.startswith("--"):
                    flag = f"--{flag}"
                script_args.extend([flag, str(value)])

        # Special handling for "direct" args (e.g., offline-batch positional)
        if "args" in final_vars and suite_obj.param_mappings.get("args") == "direct":
            script_args = final_vars["args"]  # Pass as-is (string with spaces)

        exit_code = run_script(suite_obj.target, script_args, dry_run=dry_run)

        # Save last run hint on success (skip for dry-run)
        if exit_code == 0 and not dry_run:
            # For matrix sweeps, use models or mode as hint
            model_hint = final_vars.get("models") or final_vars.get("mode") or suite
            save_last_run_hint(suite, model_hint, None)

        raise typer.Exit(exit_code)

    else:
        console.print(f"[red]Unknown runner type: {suite_obj.runner}[/red]")
        raise typer.Exit(1)


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


@app.command()
def dashboard():
    """Launch the results dashboard."""
    exit_code = run_dashboard_command()
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
