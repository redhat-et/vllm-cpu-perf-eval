#!/usr/bin/env python3
"""Audio Enterprise Report — plain-text summary of audio benchmark results.

Usage:
    python3 audio_enterprise_report.py RESULTS_DIR
    python3 audio_enterprise_report.py RESULTS_DIR --p95-target 1.5
    python3 audio_enterprise_report.py RESULTS_DIR --eta-files 100000 --eta-audio-hours 500
    python3 audio_enterprise_report.py RESULTS_DIR --json
    python3 audio_enterprise_report.py RESULTS_DIR --run-id 20260723-103307
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_script_dir = Path(__file__).parent
_dashboard_dir = (_script_dir.parent.parent /
                  "dashboard-examples" / "vllm_dashboard")
sys.path.insert(0, str(_dashboard_dir))

from audio_enterprise import (  # noqa: E402
    compute_capacity_metrics,
    discover_run_results,
    format_enterprise_report,
    load_quality_results,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Print an enterprise-oriented summary of audio benchmark results.",
    )
    p.add_argument(
        "results_dir",
        help="Path to audio results directory (one run or parent tree)",
    )
    p.add_argument(
        "--p95-target", type=float, default=2.0,
        help="P95 latency target in seconds (default: 2.0)",
    )
    p.add_argument(
        "--eta-files", type=int, default=None,
        help="Estimate wall-clock for processing this many files",
    )
    p.add_argument(
        "--eta-audio-hours", type=float, default=None,
        help="Estimate wall-clock for processing this many audio hours",
    )
    p.add_argument(
        "--run-id", default=None,
        help="Filter to a specific test_run_id",
    )
    p.add_argument(
        "--json", dest="json_output", action="store_true",
        help="Print machine-readable JSON instead of plain text",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()
    results_dir = args.results_dir

    if not Path(results_dir).exists():
        print(f"Error: results directory not found: {results_dir}",
              file=sys.stderr)
        return 1

    rows = discover_run_results(results_dir)
    if not rows:
        print(f"No audio benchmark results found in {results_dir}",
              file=sys.stderr)
        return 1

    quality_rows = load_quality_results(results_dir)
    quality_by_run: dict[str, dict] = {}
    for q in quality_rows:
        quality_by_run[q["test_run_id"]] = q

    runs: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        runs[r["test_run_id"]].append(r)

    if args.run_id:
        if args.run_id not in runs:
            print(f"Run ID '{args.run_id}' not found. Available: "
                  f"{', '.join(sorted(runs.keys()))}",
                  file=sys.stderr)
            return 1
        runs = {args.run_id: runs[args.run_id]}

    json_reports: list[dict] = []

    for run_id, stages in sorted(runs.items()):
        model = stages[0].get("model", "unknown")
        scenario = stages[0].get("scenario", "unknown")
        cores = stages[0].get("cores", 0)
        quality = quality_by_run.get(run_id)

        if args.json_output:
            cap = compute_capacity_metrics(stages, cores, args.p95_target)
            json_reports.append({
                "run_id": run_id,
                "model": model,
                "scenario": scenario,
                "cores": cores,
                "quality": {"wer": quality["wer"], "cer": quality["cer"]}
                if quality else None,
                **cap,
            })
        else:
            report = format_enterprise_report(
                stages, cores,
                p95_target=args.p95_target,
                eta_files=args.eta_files,
                eta_audio_hours=args.eta_audio_hours,
                quality=quality,
                model=model,
                scenario=scenario,
                run_id=run_id,
            )
            print(report)
            print()

    if args.json_output:
        print(json.dumps(json_reports, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
