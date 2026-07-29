"""Results management for cpueval."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.console import Console
from rich.table import Table

from cpueval.paths import (
    get_last_run_hint_path,
    get_llm_results_dir,
    get_audio_results_dir,
    get_dashboard_script,
    get_dashboard_stop_script,
    get_conversion_script,
    get_repo_root,
    find_latest_result,
)


def save_last_run_hint(
    suite: str, model: Optional[str], results_dir: Optional[Path]
) -> None:
    """Save last run hint for quick access.

    Args:
        suite: Suite name
        model: Model name
        results_dir: Path to results directory
    """
    import time

    hint_path = get_last_run_hint_path()
    hint_data = {
        "suite": suite,
        "model": model,
        "timestamp": time.time(),
        "results_hint": str(results_dir) if results_dir else None,
    }

    try:
        hint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(hint_path, "w") as f:
            json.dump(hint_data, f, indent=2)
    except Exception:
        # Silently fail if we can't write hint
        pass


def load_last_run_hint() -> Optional[Dict[str, Any]]:
    """Load last run hint.

    Returns:
        Hint data dict or None
    """
    hint_path = get_last_run_hint_path()
    if not hint_path.exists():
        return None

    try:
        with open(hint_path) as f:
            return json.load(f)
    except Exception:
        return None


def load_benchmarks(result_dir: Path) -> Optional[Dict[str, Any]]:
    """Load benchmarks.json from a result directory.

    Args:
        result_dir: Result directory path

    Returns:
        Benchmarks data or None
    """
    benchmarks_path = result_dir / "benchmarks.json"
    if not benchmarks_path.exists():
        return None

    try:
        with open(benchmarks_path) as f:
            return json.load(f)
    except Exception:
        return None


def load_metadata(result_dir: Path) -> Optional[Dict[str, Any]]:
    """Load test-metadata.json from a result directory.

    Args:
        result_dir: Result directory path

    Returns:
        Metadata or None
    """
    metadata_path = result_dir / "test-metadata.json"
    if not metadata_path.exists():
        return None

    try:
        with open(metadata_path) as f:
            return json.load(f)
    except Exception:
        return None


def extract_metrics(benchmarks: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract key metrics from benchmarks data.

    Args:
        benchmarks: Benchmarks data dict

    Returns:
        List of metrics dicts (one per concurrency point), each with:
        concurrency, req/s, tok/s, TTFT, TPOT, requests
    """
    try:
        # Handle list of benchmarks
        benchmark_list = benchmarks.get("benchmarks", [])
        if not benchmark_list:
            return []

        results = []

        # Process ALL benchmarks (multiple concurrency points)
        for benchmark in benchmark_list:
            # Extract config
            config = benchmark.get("config", {})
            strategy = config.get("strategy", {})

            # Concurrency from strategy
            concurrency = strategy.get("max_concurrency") or strategy.get("streams")

            # Extract metrics (GuideLLM v0.6+)
            metrics_data = benchmark.get("metrics", {})

            def safe_mean(key):
                """Safely extract mean from metrics dict."""
                value = metrics_data.get(key)
                if isinstance(value, dict):
                    successful = value.get("successful", {})
                    if isinstance(successful, dict):
                        return successful.get("mean")
                return None

            # Real GuideLLM field names
            req_per_sec = safe_mean("requests_per_second")
            tok_per_sec = (
                safe_mean("tokens_per_second")
                or safe_mean("output_tokens_per_second")
            )
            ttft_ms = safe_mean("time_to_first_token_ms")
            tpot_ms = (
                safe_mean("time_per_output_token_ms")
                or safe_mean("inter_token_latency_ms")
            )

            # Request totals (GuideLLM v0.6+)
            request_totals = metrics_data.get("request_totals", {})
            ok_requests = request_totals.get("successful", 0)
            total_requests = request_totals.get("total", 0)

            results.append({
                "concurrency": concurrency,
                "req_per_sec": req_per_sec,
                "tok_per_sec": tok_per_sec,
                "ttft_ms": ttft_ms,
                "tpot_ms": tpot_ms,
                "ok_requests": ok_requests,
                "total_requests": total_requests,
            })

        return results
    except Exception:
        return []


def print_result_summary(result_dir: Path, console: Console) -> None:
    """Print a terminal summary of benchmark results.

    Args:
        result_dir: Result directory path
        console: Rich console
    """
    benchmarks = load_benchmarks(result_dir)
    metadata = load_metadata(result_dir)

    console.print(f"\n[bold cyan]Results: {result_dir}[/bold cyan]\n")

    if metadata:
        table = Table(show_header=False)
        table.add_column("Key", style="dim")
        table.add_column("Value")

        # Real test-metadata.json structure
        table.add_row("Model", metadata.get("model", "unknown"))
        table.add_row(
            "Workload",
            metadata.get("workload")
            or metadata.get("use_case")
            or metadata.get("test_type")
            or "unknown",
        )
        table.add_row("Timestamp", metadata.get("timestamp", "unknown"))

        # Core count from top-level or configuration
        cores = (
            metadata.get("core_count")
            or metadata.get("cores")
            or (
                metadata.get("configuration", {}).get("cores")
                if "configuration" in metadata
                else None
            )
        )
        if cores:
            table.add_row("Cores", str(cores))

        console.print(table)
        console.print()

    if benchmarks:
        metrics_list = extract_metrics(benchmarks)

        if metrics_list:
            # Show all concurrency points
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Concurrency")
            table.add_column("Req/s", justify="right")
            table.add_column("Tok/s", justify="right")
            table.add_column("TTFT (ms)", justify="right")
            table.add_column("TPOT (ms)", justify="right")
            table.add_column("Requests", justify="right")

            for m in metrics_list:
                table.add_row(
                    str(m.get("concurrency", "-")),
                    (
                        f'{m["req_per_sec"]:.2f}'
                        if m.get("req_per_sec") is not None
                        else "-"
                    ),
                    (
                        f'{m["tok_per_sec"]:.2f}'
                        if m.get("tok_per_sec") is not None
                        else "-"
                    ),
                    f'{m["ttft_ms"]:.2f}' if m.get("ttft_ms") is not None else "-",
                    f'{m["tpot_ms"]:.2f}' if m.get("tpot_ms") is not None else "-",
                    f'{m.get("ok_requests", 0)}/{m.get("total_requests", 0)}',
                )

            console.print(table)
            console.print()
        else:
            msg = (
                "[yellow]Could not extract metrics "
                "from benchmarks.json[/yellow]\n"
            )
            console.print(msg)
    else:
        console.print("[yellow]No benchmarks.json found[/yellow]\n")


def list_results(limit: int = 10, audio: bool = False) -> None:
    """List recent results.

    Args:
        limit: Maximum number of results to show
        audio: Show audio results instead of LLM
    """
    console = Console()

    base_dir = get_audio_results_dir() if audio else get_llm_results_dir()

    if not base_dir.exists():
        console.print(f"[yellow]No results found in {base_dir}[/yellow]")
        return

    # Find all benchmarks.json files
    benchmarks = list(base_dir.rglob("benchmarks.json"))

    if not benchmarks:
        console.print(f"[yellow]No benchmark results found in {base_dir}[/yellow]")
        return

    # Sort by modification time (newest first)
    benchmarks.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Limit results
    benchmarks = benchmarks[:limit]

    console.print(f"\n[bold cyan]Recent results ({len(benchmarks)})[/bold cyan]\n")

    for bench_path in benchmarks:
        result_dir = bench_path.parent
        rel_path = result_dir.relative_to(base_dir)
        console.print(f"  {rel_path}")

    console.print()


def run_results_command(
    path: Optional[str] = None,
    last: bool = False,
    list_results_flag: bool = False,
    limit: int = 10,
    open_dashboard: bool = False,
    convert: bool = False,
    view: bool = True,
) -> int:
    """Handle results command.

    Args:
        path: Specific result path
        last: Use last run hint
        list_results_flag: List recent results
        limit: Limit for list
        open_dashboard: Launch dashboard
        convert: Run conversion script
        view: Show terminal summary

    Returns:
        Exit code
    """
    console = Console()

    # Handle --open / dashboard
    if open_dashboard:
        dashboard_script = get_dashboard_script()
        if not dashboard_script.exists():
            console.print(f"[red]Dashboard script not found: {dashboard_script}[/red]")
            return 1

        console.print("[cyan]Launching dashboard...[/cyan]")
        env = os.environ.copy()
        env.setdefault("VLLM_DASHBOARD_RESULTS_DIR", str(get_llm_results_dir()))
        env.setdefault(
            "VLLM_DASHBOARD_AUDIO_RESULTS_DIR", str(get_audio_results_dir())
        )
        return subprocess.run([str(dashboard_script)], env=env).returncode

    # Handle --list
    if list_results_flag:
        list_results(limit=limit)
        return 0

    # Find result directory
    result_dir = None

    if path:
        result_dir = Path(path)
        if not result_dir.exists():
            console.print(f"[red]Path not found: {result_dir}[/red]")
            return 1
    elif last:
        hint = load_last_run_hint()
        if hint and hint.get("results_hint"):
            result_dir = Path(hint["results_hint"])
        else:
            # Fall back to finding latest
            result_dir = find_latest_result()

        if not result_dir:
            console.print("[yellow]No last run found. Try --list to see available results.[/yellow]")
            return 1
    else:
        # Default to latest
        result_dir = find_latest_result()

        if not result_dir:
            console.print("[yellow]No results found. Try --list or specify a path.[/yellow]")
            return 0

    # Handle --convert
    if convert:
        conversion_script = get_conversion_script()
        if not conversion_script.exists():
            console.print(f"[red]Conversion script not found: {conversion_script}[/red]")
            return 1

        console.print(f"[cyan]Converting results in {result_dir}...[/cyan]")
        return subprocess.run(
            ["python3", str(conversion_script)], cwd=get_repo_root()
        ).returncode

    # Show terminal summary
    if view:
        print_result_summary(result_dir, console)

    return 0


def run_dashboard_command() -> int:
    """Launch the dashboard."""
    return run_results_command(open_dashboard=True)


def run_dashboard_stop_command() -> int:
    """Stop the running dashboard."""
    console = Console()
    stop_script = get_dashboard_stop_script()
    if not stop_script.exists():
        console.print(f"[red]Stop script not found: {stop_script}[/red]")
        return 1
    return subprocess.run([str(stop_script)]).returncode
