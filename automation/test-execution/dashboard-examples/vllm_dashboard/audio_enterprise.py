"""Enterprise audio metrics — shared compute for dashboard and CLI.

Single source of truth for capacity planning, sizing, quality (WER/CER),
and warmup metrics.  No Streamlit dependency.

Used by:
  - pages/4_🎧_Audio_Metrics.py  (dashboard)
  - scripts/ansible/audio_enterprise_report.py  (CLI)
"""

import json
import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def discover_run_results(results_dir: str) -> list[dict]:
    """Walk *results_dir*, find benchmarks.json files, join metadata.

    Returns a flat list of dicts (one per stage-benchmark) with all fields
    the Audio Metrics dashboard needs.  Caller may convert to DataFrame.
    """
    results_path = Path(results_dir)
    all_results: list[dict] = []

    if not results_path.exists():
        logger.warning("Results directory not found: %s", results_path)
        return all_results

    for json_file in results_path.rglob("benchmarks.json"):
        try:
            with open(json_file) as fh:
                data = json.load(fh)

            # ---- test-metadata.json (parent.parent then parent) ----------
            metadata_file = json_file.parent.parent / "test-metadata.json"
            if not metadata_file.exists():
                metadata_file = json_file.parent / "test-metadata.json"
            if not metadata_file.exists():
                continue
            with open(metadata_file) as fh:
                metadata = json.load(fh)

            # ---- stage-metadata.json (same dir as benchmarks.json) -------
            stage_metadata: dict = {}
            stage_metadata_file = json_file.parent / "stage-metadata.json"
            if stage_metadata_file.exists():
                try:
                    with open(stage_metadata_file) as fh:
                        stage_metadata = json.load(fh)
                except Exception:
                    pass

            # ---- iterate benchmarks inside the file ----------------------
            for bench in data.get("benchmarks", []):
                metrics = bench["metrics"]
                config = bench["config"]
                requests = bench["requests"]

                concurrency = (config.get("strategy", {})
                               .get("max_concurrency", 0))
                req_rate = (metrics.get("requests_per_second", {})
                            .get("successful", {})
                            .get("mean", concurrency))

                successful_requests = requests.get("successful", [])
                benchmark_duration = bench["duration"]
                audio_agg = calculate_audio_aggregates(
                    successful_requests, benchmark_duration,
                )

                if audio_agg["total_audio_seconds"] == 0:
                    continue

                stage = json_file.parent.name
                totals = metrics["request_totals"]
                latency = metrics["request_latency"]["successful"]

                row: dict = {
                    # -- metadata --
                    "test_run_id": metadata.get("test_run_id", "unknown"),
                    "platform": metadata.get("platform", "unknown"),
                    "model": metadata.get("model", "unknown"),
                    "model_short": metadata.get("model", "unknown").split("/")[-1],
                    "scenario": metadata.get(
                        "scenario_name", metadata.get("scenario", "unknown"),
                    ),
                    "stage": stage,
                    "cores": metadata.get("core_count", 0),
                    "backend": metadata.get("backend", "unknown"),
                    "vllm_version": metadata.get("vllm_version", "unknown"),
                    "guidellm_version": metadata.get("guidellm_version", "unknown"),
                    "tensor_parallel": metadata.get("tensor_parallel", 1),
                    # -- audio format (prefer per-stage) --
                    "audio_format": stage_metadata.get(
                        "audio_format", metadata.get("audio_format", "unknown"),
                    ),
                    "audio_sample_rate": stage_metadata.get(
                        "audio_sample_rate",
                        metadata.get("audio_sample_rate", 0),
                    ),
                    "audio_bitrate": stage_metadata.get(
                        "audio_bitrate",
                        metadata.get("audio_bitrate", "unknown"),
                    ),
                    "dataset_name": metadata.get("dataset_name", "unknown"),
                    "dataset_config": metadata.get("dataset_config", "unknown"),
                    # -- load --
                    "concurrency": concurrency,
                    "request_rate": req_rate,
                    # -- perf --
                    "duration": benchmark_duration,
                    "requests_per_second": (
                        metrics["requests_per_second"]["successful"]["mean"]
                    ),
                    "e2e_mean": latency["mean"],
                    "e2e_p50": latency["percentiles"]["p50"],
                    "e2e_p95": latency["percentiles"]["p95"],
                    "e2e_p99": latency["percentiles"]["p99"],
                    # -- request counts --
                    "total_requests": totals["total"],
                    "successful_requests": totals["successful"],
                    "errored_requests": totals["errored"],
                    "success_rate": (
                        totals["successful"] / totals["total"] * 100
                        if totals["total"] > 0 else 0
                    ),
                    # -- audio aggregates --
                    **{k: audio_agg[k] for k in (
                        "total_audio_seconds", "mean_audio_seconds",
                        "total_audio_samples", "total_audio_bytes",
                        "audio_tokens", "audio_throughput",
                        "rtf_mean", "rtf_p50", "rtf_p95", "rtf_p99",
                    )},
                }

                # ---- warmup / first-request (raw, per-benchmark) ---------
                row["warmup_duration"] = bench.get("warmup_duration")
                if successful_requests:
                    row["first_request_latency"] = successful_requests[0].get(
                        "request_latency",
                    )
                    first_audio = (successful_requests[0]
                                   .get("input_metrics", {})
                                   .get("audio_seconds", 0))
                    if first_audio and first_audio > 0:
                        row["first_rtf"] = (
                            row["first_request_latency"] / first_audio
                        )
                    else:
                        row["first_rtf"] = None
                else:
                    row["first_request_latency"] = None
                    row["first_rtf"] = None

                all_results.append(row)

        except Exception as exc:
            logger.warning("Failed to load %s: %s", json_file, exc)

    return all_results


# ---------------------------------------------------------------------------
# Audio aggregate computation (moved from 4_Audio_Metrics.py)
# ---------------------------------------------------------------------------

def calculate_audio_aggregates(
    successful_requests: list,
    benchmark_duration: float,
) -> dict:
    """Calculate audio-specific aggregate metrics from a request list."""
    zeros = {
        "total_audio_seconds": 0, "mean_audio_seconds": 0,
        "total_audio_samples": 0, "total_audio_bytes": 0,
        "audio_tokens": 0, "audio_throughput": 0,
        "rtf_mean": 0, "rtf_p50": 0, "rtf_p95": 0, "rtf_p99": 0,
    }
    if not successful_requests:
        return zeros

    audio_seconds_list: list[float] = []
    audio_samples_list: list[int] = []
    audio_bytes_list: list[int] = []
    audio_tokens_list: list[int] = []
    rtf_list: list[float] = []

    for req in successful_requests:
        inp = req.get("input_metrics", {})
        audio_sec = inp.get("audio_seconds", 0)
        latency = req.get("request_latency", 0)

        if audio_sec and audio_sec > 0:
            audio_seconds_list.append(audio_sec)
            rtf_list.append(latency / audio_sec)

        if s := inp.get("audio_samples"):
            audio_samples_list.append(s)
        if b := inp.get("audio_bytes"):
            audio_bytes_list.append(b)
        if t := inp.get("audio_tokens"):
            audio_tokens_list.append(t)

    total_audio = sum(audio_seconds_list)
    return {
        "total_audio_seconds": total_audio,
        "mean_audio_seconds": (
            float(np.mean(audio_seconds_list)) if audio_seconds_list else 0
        ),
        "total_audio_samples": sum(audio_samples_list),
        "total_audio_bytes": sum(audio_bytes_list),
        "audio_tokens": sum(audio_tokens_list),
        "audio_throughput": (
            total_audio / benchmark_duration if benchmark_duration > 0 else 0
        ),
        "rtf_mean": float(np.mean(rtf_list)) if rtf_list else 0,
        "rtf_p50": float(np.percentile(rtf_list, 50)) if rtf_list else 0,
        "rtf_p95": float(np.percentile(rtf_list, 95)) if rtf_list else 0,
        "rtf_p99": float(np.percentile(rtf_list, 99)) if rtf_list else 0,
    }


# ---------------------------------------------------------------------------
# Enterprise capacity / sizing
# ---------------------------------------------------------------------------

def compute_capacity_metrics(
    stages: list[dict],
    cores: int,
    p95_target: float = 2.0,
) -> dict:
    """Compute enterprise capacity metrics from a single run's stages.

    *stages* is a list of row dicts (from discover_run_results) that share
    one test_run_id.
    """
    if not stages:
        return _empty_capacity()

    best_throughput = max(s.get("audio_throughput", 0) for s in stages)
    best_rps = max(s.get("requests_per_second", 0) for s in stages)

    concurrency_info = compute_max_concurrency_at_target(stages, p95_target)

    throughput_per_core = best_throughput / cores if cores > 0 else None
    core_hours = cores / best_throughput if best_throughput > 0 else None

    return {
        "audio_hours_per_hour": best_throughput,
        "files_per_hour": best_rps * 3600,
        "best_requests_per_second": best_rps,
        "max_concurrency_at_p95": (
            concurrency_info["max_concurrency"] if concurrency_info else None
        ),
        "p95_at_max_concurrency": (
            concurrency_info["p95_at_max"] if concurrency_info else None
        ),
        "p95_target": p95_target,
        "throughput_per_core": throughput_per_core,
        "core_hours_per_audio_hour": core_hours,
        "cores": cores,
    }


def _empty_capacity() -> dict:
    return {k: None for k in (
        "audio_hours_per_hour", "files_per_hour", "best_requests_per_second",
        "max_concurrency_at_p95", "p95_at_max_concurrency", "p95_target",
        "throughput_per_core", "core_hours_per_audio_hour", "cores",
    )}


def compute_max_concurrency_at_target(
    stages: list[dict],
    p95_target: float,
) -> dict | None:
    """Find highest concurrency where P95 latency <= *p95_target*.

    Returns ``{"max_concurrency": int, "p95_at_max": float}`` or *None*.
    """
    candidates = [
        s for s in stages
        if s.get("concurrency") and s.get("e2e_p95") is not None
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda s: s["concurrency"])
    best = None
    for s in candidates:
        if s["e2e_p95"] <= p95_target:
            best = {
                "max_concurrency": s["concurrency"],
                "p95_at_max": s["e2e_p95"],
            }
    return best


def compute_batch_eta(
    files_per_second: float | None = None,
    total_files: int | None = None,
    audio_hours_per_hour: float | None = None,
    target_audio_hours: float | None = None,
) -> dict:
    """Estimate wall-clock time for batch processing."""
    result: dict = {}
    if files_per_second and files_per_second > 0 and total_files:
        result["eta_files_seconds"] = total_files / files_per_second
    if audio_hours_per_hour and audio_hours_per_hour > 0 and target_audio_hours:
        result["eta_audio_hours_seconds"] = (
            target_audio_hours / audio_hours_per_hour * 3600
        )
    return result


# ---------------------------------------------------------------------------
# Warmup
# ---------------------------------------------------------------------------

def compute_warmup_metrics(stages: list[dict]) -> dict:
    """Derive warmup info from a run's stages.

    Looks for the sequential/single-user stage (concurrency 0 or 1), then
    computes first-request vs steady-state RTF.
    """
    baseline = None
    for s in stages:
        if s.get("concurrency", 0) <= 1:
            baseline = s
            break
    if not baseline:
        baseline = stages[0] if stages else None
    if not baseline:
        return {
            "warmup_duration": None, "first_request_latency": None,
            "first_rtf": None, "steady_rtf": None,
        }

    return {
        "warmup_duration": baseline.get("warmup_duration"),
        "first_request_latency": baseline.get("first_request_latency"),
        "first_rtf": baseline.get("first_rtf"),
        "steady_rtf": baseline.get("rtf_mean"),
    }


# ---------------------------------------------------------------------------
# Quality (WER / CER)
# ---------------------------------------------------------------------------

def load_quality_results(results_dir: str) -> list[dict]:
    """Walk *results_dir* for ``quality-results.json`` files.

    Returns list of dicts ready for DataFrame conversion, or ``[]``.
    """
    results_path = Path(results_dir)
    out: list[dict] = []

    if not results_path.exists():
        return out

    for qf in results_path.rglob("quality-results.json"):
        try:
            with open(qf) as fh:
                qdata = json.load(fh)

            # Try to find the associated test-metadata.json
            meta: dict = {}
            for candidate in (qf.parent.parent / "test-metadata.json",
                              qf.parent / "test-metadata.json"):
                if candidate.exists():
                    with open(candidate) as fh:
                        meta = json.load(fh)
                    break

            out.append({
                "test_run_id": meta.get("test_run_id", "unknown"),
                "model": qdata.get("model", meta.get("model", "unknown")),
                "model_short": qdata.get(
                    "model", meta.get("model", "unknown"),
                ).split("/")[-1],
                "scenario": meta.get("scenario_name", "transcription-quality"),
                "cores": meta.get("core_count", 0),
                "wer": qdata.get("wer"),
                "cer": qdata.get("cer"),
                "num_clips": qdata.get("num_clips", 0),
                "num_successful": qdata.get("num_successful", 0),
                "dataset": qdata.get("dataset", "unknown"),
                "dataset_config": qdata.get("dataset_config", "unknown"),
                "audio_format": qdata.get("audio_format", "unknown"),
                "timestamp": qdata.get("timestamp", ""),
                "per_clip": qdata.get("per_clip", []),
            })
        except Exception as exc:
            logger.warning("Failed to load %s: %s", qf, exc)

    return out


# ---------------------------------------------------------------------------
# Plain-text enterprise report
# ---------------------------------------------------------------------------

def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    if seconds < 60:
        return f"~{seconds:.0f}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"~{int(m)}m {int(s)}s"
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"~{int(h)}h {int(m)}m"


def _fmt(val, fmt=".2f", suffix="", na="n/a"):
    if val is None:
        return na
    return f"{val:{fmt}}{suffix}"


def format_enterprise_report(
    run_stages: list[dict],
    cores: int,
    *,
    p95_target: float = 2.0,
    eta_files: int | None = None,
    eta_audio_hours: float | None = None,
    quality: dict | None = None,
    model: str = "unknown",
    scenario: str = "unknown",
    run_id: str = "unknown",
) -> str:
    """Render a plain-text enterprise report for a single run."""
    cap = compute_capacity_metrics(run_stages, cores, p95_target)
    warmup = compute_warmup_metrics(run_stages)
    eta = compute_batch_eta(
        files_per_second=cap.get("best_requests_per_second"),
        total_files=eta_files,
        audio_hours_per_hour=cap.get("audio_hours_per_hour"),
        target_audio_hours=eta_audio_hours,
    )

    lines = [
        "=" * 50,
        "  Audio Enterprise Report",
        f"  Model: {model} | Cores: {cores}",
        f"  Scenario: {scenario}",
        f"  Run: {run_id}",
        "=" * 50,
        "",
    ]

    # Quality
    if quality and quality.get("wer") is not None:
        wer_pct = quality["wer"] * 100
        n = quality.get("num_clips", "?")
        cer_str = ""
        if quality.get("cer") is not None:
            cer_str = f"  CER: {quality['cer'] * 100:.1f}%"
        lines += [
            "Quality",
            f"  WER: {wer_pct:.1f}% (n={n}){cer_str}",
            "",
        ]
    else:
        lines += ["Quality", "  WER: n/a", ""]

    # Offline batch
    lines += [
        "Offline Batch",
        f"  Audio hours/hour:  {_fmt(cap.get('audio_hours_per_hour'))}",
        f"  Files/hour:        {_fmt(cap.get('files_per_hour'), ',.0f')}",
    ]
    if eta.get("eta_files_seconds") is not None:
        lines.append(
            f"  ETA for {eta_files:,} files: "
            f"{_fmt_duration(eta['eta_files_seconds'])}",
        )
    if eta.get("eta_audio_hours_seconds") is not None:
        lines.append(
            f"  ETA for {eta_audio_hours:,.1f} audio hours: "
            f"{_fmt_duration(eta['eta_audio_hours_seconds'])}",
        )
    lines.append("")

    # Online
    mc = cap.get("max_concurrency_at_p95")
    if mc is not None:
        lines += [
            f"Online (P95 ≤ {p95_target}s)",
            f"  Max concurrency: {mc}",
            f"  P95 @ max:       {_fmt(cap.get('p95_at_max_concurrency'))}s",
            "",
        ]
    else:
        lines += [
            f"Online (P95 ≤ {p95_target}s)",
            "  Max concurrency: n/a (single stage or all exceed target)",
            "",
        ]

    # Efficiency
    lines += [
        "Efficiency",
        f"  Throughput/core:        {_fmt(cap.get('throughput_per_core'))}",
        f"  Core-hours/audio-hour:  {_fmt(cap.get('core_hours_per_audio_hour'))}",
        "",
    ]

    # Warmup
    lines += [
        "Warmup",
        f"  Ready time:       {_fmt(warmup.get('warmup_duration'))}s",
        f"  First RTF:        {_fmt(warmup.get('first_rtf'))}",
        f"  Steady RTF:       {_fmt(warmup.get('steady_rtf'), '.3f')}",
    ]

    lines.append("=" * 50)
    return "\n".join(lines)
