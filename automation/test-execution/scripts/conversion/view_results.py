#!/usr/bin/env python3
"""Terminal viewer for vLLM CPU benchmark results.

Supports both LLM (GuideLLM benchmarks.json) and embedding
(vllm bench serve sweep-*.json / concurrent-*.json) result
formats. Auto-detects the format based on directory contents.

No external dependencies -- stdlib only.

Usage:
    # LLM results (GuideLLM)
    python3 view_results.py <path/to/benchmarks.json>
    python3 view_results.py <path/to/results-directory/>

    # Embedding results (vllm bench serve)
    python3 view_results.py <path/to/embedding-test-run-dir/>

    python3 view_results.py --no-header <path>
"""

import argparse
import json
import sys
from pathlib import Path

TABLE_WIDTH = 95


# -----------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------

def load_json(path):
    """Load a JSON file, returning None on failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(
            f"Warning: could not load {path}: {e}",
            file=sys.stderr,
        )
        return None


def safe_get(d, *keys, default=None):
    """Traverse nested dicts safely."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key)
        if d is None:
            return default
    return d


def clean_platform(platform):
    """Clean platform string for display."""
    if not platform:
        return "N/A"
    name = platform.replace("_", " ")
    for suffix in [" Core Processor", " C"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    name = name.replace(" R ", " ")
    return name.strip()


def fmt_f(val, decimals=1):
    """Format float, or '-' if None."""
    if val is None:
        return "-"
    return f"{val:.{decimals}f}"


def fmt_i(val):
    """Format as integer, or '-' if None."""
    if val is None:
        return "-"
    return str(int(round(val)))


def fmt_ms(val, from_seconds=False):
    """Format as integer milliseconds, or '-' if None."""
    if val is None:
        return "-"
    if from_seconds:
        val = val * 1000
    return str(int(round(val)))


def _extract_date(run_id):
    """Extract YYYY-MM-DD from a test_run_id string."""
    if not run_id:
        return "N/A"
    for part in run_id.split("-"):
        if len(part) == 8 and part.isdigit():
            return (
                f"{part[:4]}-{part[4:6]}-{part[6:8]}"
            )
    if len(run_id) >= 8 and run_id[:8].isdigit():
        return (
            f"{run_id[:4]}-{run_id[4:6]}-{run_id[6:8]}"
        )
    return "N/A"


# -----------------------------------------------------------
# Format detection
# -----------------------------------------------------------

def detect_format(path):
    """Detect result format.

    Returns (format_type, resolved_dir, benchmarks_path|None).
    format_type: 'llm' or 'embedding'
    """
    p = Path(path)

    if p.is_file() and p.name == "benchmarks.json":
        return "llm", p.parent, p

    if p.is_dir():
        benchmarks = p / "benchmarks.json"
        if benchmarks.exists():
            return "llm", p, benchmarks

        has_baseline = (p / "baseline").is_dir()
        has_latency = (p / "latency").is_dir()
        if has_baseline or has_latency:
            return "embedding", p, None

        has_sweep = list(p.glob("sweep-*.json"))
        has_conc = list(p.glob("concurrent-*.json"))
        if has_sweep or has_conc:
            return "embedding", p, None

    print(
        f"Error: could not detect result format at {path}",
        file=sys.stderr,
    )
    print(
        "Expected: benchmarks.json (LLM) "
        "or baseline/latency subdirs (embedding)",
        file=sys.stderr,
    )
    sys.exit(1)


# -----------------------------------------------------------
# LLM results (GuideLLM)
# -----------------------------------------------------------

def format_llm_header(metadata):
    """Build the LLM metadata header block."""
    if metadata is None:
        metadata = {}

    model = metadata.get("model", "N/A")
    workload = metadata.get("workload", "N/A")
    cores = metadata.get("core_count", "N/A")
    platform = clean_platform(metadata.get("platform"))
    vllm_ver = metadata.get("vllm_version", "N/A")
    caching = metadata.get("vllm_caching_mode", "N/A")
    date = _extract_date(metadata.get("test_run_id", ""))

    bar = "━" * TABLE_WIDTH
    lines = [
        bar,
        " vLLM CPU Benchmark Results — LLM",
        bar,
        f" Model:    {model}",
        (
            f" Workload: {workload}"
            f" | Cores: {cores}"
            f" | Platform: {platform}"
        ),
        (
            f" vLLM: {vllm_ver}"
            f" | Caching: {caching}"
            f" | Date: {date}"
        ),
        bar,
    ]
    return "\n".join(lines)


def _ttft(metrics, stat):
    """Get TTFT metric by stat name."""
    base = safe_get(
        metrics, "time_to_first_token_ms", "successful",
    )
    if base is None:
        return None
    if stat == "median":
        return base.get("median")
    return safe_get(base, "percentiles", stat)


def _itl(metrics, stat):
    """Get ITL metric by stat name."""
    base = safe_get(
        metrics, "inter_token_latency_ms", "successful",
    )
    if base is None:
        return None
    if stat == "median":
        return base.get("median")
    return safe_get(base, "percentiles", stat)


def _lat(metrics, stat):
    """Get request latency metric by stat name."""
    base = safe_get(
        metrics, "request_latency", "successful",
    )
    if base is None:
        return None
    if stat == "median":
        return base.get("median")
    return safe_get(base, "percentiles", stat)


def extract_llm_row(benchmark):
    """Extract metrics from a single GuideLLM benchmark."""
    config = safe_get(benchmark, "config", default={})
    strategy = safe_get(config, "strategy", default={})
    metrics = safe_get(benchmark, "metrics", default={})
    sched = safe_get(
        benchmark, "scheduler_metrics", default={},
    )

    concurrency = (
        strategy.get("streams")
        or strategy.get("max_concurrency")
        or 0
    )

    return {
        "conc": concurrency,
        "tok_s": safe_get(
            metrics, "tokens_per_second",
            "successful", "mean",
        ),
        "ttft_med": _ttft(metrics, "median"),
        "ttft_p95": _ttft(metrics, "p95"),
        "ttft_p99": _ttft(metrics, "p99"),
        "itl_med": _itl(metrics, "median"),
        "itl_p95": _itl(metrics, "p95"),
        "itl_p99": _itl(metrics, "p99"),
        "lat_med": _lat(metrics, "median"),
        "lat_p95": _lat(metrics, "p95"),
        "lat_p99": _lat(metrics, "p99"),
        "reqs": safe_get(
            sched, "requests_made", "successful",
            default=0,
        ),
        "errs": safe_get(
            sched, "requests_made", "errored",
            default=0,
        ),
    }


def build_llm_table(rows):
    """Build the formatted LLM results table."""
    if not rows:
        return "No benchmark data found."

    rows.sort(key=lambda r: r["conc"])

    sep = "│"
    hsep = "─"
    cross = "┼"

    wc = 5   # Conc
    wt = 8   # Tok/s
    wf = 6   # TTFT / ITL sub-columns
    wl = 7   # Latency sub-columns
    wr = 5   # Reqs
    we = 4   # Err

    ttft_w = wf * 3 + 4
    itl_w = wf * 3 + 4
    lat_w = wl * 3 + 4

    h1 = (
        f" {'Conc':>{wc}} {sep} {'Tok/s':>{wt}} {sep}"
        f" {'TTFT (ms)':^{ttft_w}} {sep}"
        f" {'ITL (ms)':^{itl_w}} {sep}"
        f" {'E2E Latency (ms)':^{lat_w}} {sep}"
        f" {'Reqs':>{wr}} {sep} {'Err':>{we}}"
    )

    h2 = (
        f" {'':>{wc}} {sep} {'(mean)':>{wt}} {sep}"
        f"  {'med':>{wf}}  {'p95':>{wf}}"
        f"  {'p99':>{wf}} {sep}"
        f"  {'med':>{wf}}  {'p95':>{wf}}"
        f"  {'p99':>{wf}} {sep}"
        f"  {'med':>{wl}}  {'p95':>{wl}}"
        f"  {'p99':>{wl}} {sep}"
        f" {'':>{wr}} {sep} {'':>{we}}"
    )

    def seg(w):
        return hsep * (w + 2)

    sep_line = (
        f" {hsep * wc}{cross}{seg(wt)}{cross}"
        f"{hsep * (ttft_w + 2)}{cross}"
        f"{hsep * (itl_w + 2)}{cross}"
        f"{hsep * (lat_w + 2)}{cross}"
        f"{seg(wr)}{cross}{seg(we)}"
    )

    lines = [h1, h2, sep_line]

    for r in rows:
        line = (
            f" {fmt_i(r['conc']):>{wc}} {sep}"
            f" {fmt_f(r['tok_s']):>{wt}} {sep}"
            f"  {fmt_ms(r['ttft_med']):>{wf}}"
            f"  {fmt_ms(r['ttft_p95']):>{wf}}"
            f"  {fmt_ms(r['ttft_p99']):>{wf}} {sep}"
            f"  {fmt_f(r['itl_med']):>{wf}}"
            f"  {fmt_f(r['itl_p95']):>{wf}}"
            f"  {fmt_f(r['itl_p99']):>{wf}} {sep}"
            f"  {fmt_ms(r['lat_med'], True):>{wl}}"
            f"  {fmt_ms(r['lat_p95'], True):>{wl}}"
            f"  {fmt_ms(r['lat_p99'], True):>{wl}}"
            f" {sep}"
            f" {fmt_i(r['reqs']):>{wr}} {sep}"
            f" {fmt_i(r['errs']):>{we}}"
        )
        lines.append(line)

    return "\n".join(lines)


def view_llm(benchmarks_path, result_dir, show_header):
    """Display LLM benchmark results."""
    data = load_json(benchmarks_path)
    if data is None:
        print(
            "Error: could not parse benchmarks.json",
            file=sys.stderr,
        )
        sys.exit(1)

    benchmarks = data.get("benchmarks", [])
    if not benchmarks:
        print(
            "No benchmark data found in file.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_parts = []

    if show_header:
        metadata_path = result_dir / "test-metadata.json"
        metadata = (
            load_json(metadata_path)
            if metadata_path.exists()
            else None
        )
        output_parts.append(format_llm_header(metadata))
        output_parts.append("")

    rows = [extract_llm_row(b) for b in benchmarks]
    output_parts.append(build_llm_table(rows))
    output_parts.append("━" * TABLE_WIDTH)

    print("\n".join(output_parts))


# -----------------------------------------------------------
# Embedding results (vllm bench serve)
# -----------------------------------------------------------

def format_embedding_header(metadata):
    """Build the embedding metadata header block."""
    if metadata is None:
        metadata = {}

    model = metadata.get("model", "N/A")
    scenario = metadata.get("scenario", "N/A")
    cores = (
        metadata.get("requested_cores")
        or metadata.get("core_count")
        or "N/A"
    )
    if str(cores) in ("None", "null", ""):
        cores = "N/A"
    platform = clean_platform(metadata.get("platform"))
    vllm_ver = metadata.get("vllm_version", "N/A")
    num_prompts = metadata.get("num_prompts", "N/A")
    input_len = metadata.get(
        "embedding_random_input_len", "N/A",
    )
    date = _extract_date(
        metadata.get("test_run_id", ""),
    )

    bar = "━" * TABLE_WIDTH
    lines = [
        bar,
        " vLLM CPU Benchmark Results — Embedding",
        bar,
        f" Model:    {model}",
        (
            f" Scenario: {scenario}"
            f" | Cores: {cores}"
            f" | Platform: {platform}"
        ),
        (
            f" vLLM: {vllm_ver}"
            f" | Prompts: {num_prompts}"
            f" | Input len: {input_len}"
            f" | Date: {date}"
        ),
        bar,
    ]
    return "\n".join(lines)


def collect_embedding_results(result_dir):
    """Collect embedding result files.

    Returns list of (test_type, label, data_dict) tuples.
    """
    results = []

    for subdir_name in ["baseline", "latency"]:
        subdir = result_dir / subdir_name
        if not subdir.is_dir():
            continue
        for json_file in sorted(subdir.glob("*.json")):
            data = load_json(json_file)
            if data is None:
                continue
            stem = json_file.stem
            if stem.startswith("sweep-"):
                test_type = "baseline"
                label = stem.replace("sweep-", "")
            elif stem.startswith("concurrent-"):
                test_type = "concurrent"
                label = stem.replace(
                    "concurrent-", "",
                )
            else:
                continue
            results.append((test_type, label, data))

    sweep = list(result_dir.glob("sweep-*.json"))
    conc = list(result_dir.glob("concurrent-*.json"))
    for json_file in sorted(sweep + conc):
        data = load_json(json_file)
        if data is None:
            continue
        stem = json_file.stem
        if stem.startswith("sweep-"):
            results.append((
                "baseline",
                stem.replace("sweep-", ""),
                data,
            ))
        elif stem.startswith("concurrent-"):
            results.append((
                "concurrent",
                stem.replace("concurrent-", ""),
                data,
            ))

    return results


def _sort_key_embedding(item):
    """Sort: baseline first (inf, then pct), then concurrent."""
    test_type, label, _ = item
    if test_type == "baseline":
        if label == "inf":
            return (0, 0)
        pct = label.replace("pct", "")
        try:
            return (0, int(pct))
        except ValueError:
            return (0, 999)
    else:
        try:
            return (1, int(label))
        except ValueError:
            return (1, 999)


def build_embedding_table(results):
    """Build the formatted embedding results table."""
    if not results:
        return "No embedding data found."

    results.sort(key=_sort_key_embedding)

    sep = "│"
    hsep = "─"
    cross = "┼"

    wty = 10  # Type
    wlb = 8   # Label
    wrp = 10  # RPS
    wtk = 12  # Tok/s
    wla = 10  # Latency sub-columns (x4)
    wre = 6   # Reqs
    wdu = 7   # Duration

    lat_w = wla * 4 + 6

    h1 = (
        f" {'Type':>{wty}} {sep}"
        f" {'Label':>{wlb}} {sep}"
        f" {'RPS':>{wrp}} {sep}"
        f" {'Tok/s':>{wtk}} {sep}"
        f" {'E2E Latency (ms)':^{lat_w}} {sep}"
        f" {'Reqs':>{wre}} {sep}"
        f" {'Dur(s)':>{wdu}}"
    )

    h2 = (
        f" {'':>{wty}} {sep} {'':>{wlb}} {sep}"
        f" {'':>{wrp}} {sep} {'':>{wtk}} {sep}"
        f"  {'mean':>{wla}}  {'med':>{wla}}"
        f"  {'std':>{wla}}  {'p99':>{wla}} {sep}"
        f" {'':>{wre}} {sep} {'':>{wdu}}"
    )

    def seg(w):
        return hsep * (w + 2)

    sep_line = (
        f" {hsep * wty}{cross}{seg(wlb)}{cross}"
        f"{seg(wrp)}{cross}{seg(wtk)}{cross}"
        f"{hsep * (lat_w + 2)}{cross}"
        f"{seg(wre)}{cross}{seg(wdu)}"
    )

    lines = [h1, h2, sep_line]

    for test_type, label, data in results:
        rps = data.get("request_throughput")
        tok_s = data.get("total_token_throughput")
        mean_lat = data.get("mean_e2el_ms")
        med_lat = data.get("median_e2el_ms")
        std_lat = data.get("std_e2el_ms")
        p99_lat = data.get("p99_e2el_ms")
        completed = data.get("completed")
        duration = data.get("duration")

        line = (
            f" {test_type:>{wty}} {sep}"
            f" {label:>{wlb}} {sep}"
            f" {fmt_f(rps, 2):>{wrp}} {sep}"
            f" {fmt_f(tok_s, 1):>{wtk}} {sep}"
            f"  {fmt_f(mean_lat, 1):>{wla}}"
            f"  {fmt_f(med_lat, 1):>{wla}}"
            f"  {fmt_f(std_lat, 1):>{wla}}"
            f"  {fmt_f(p99_lat, 1):>{wla}} {sep}"
            f" {fmt_i(completed):>{wre}} {sep}"
            f" {fmt_f(duration, 1):>{wdu}}"
        )
        lines.append(line)

    return "\n".join(lines)


def view_embedding(result_dir, show_header):
    """Display embedding benchmark results."""
    results = collect_embedding_results(result_dir)
    if not results:
        print(
            "No embedding result files found.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_parts = []

    if show_header:
        metadata_path = (
            result_dir / "test-metadata.json"
        )
        metadata = (
            load_json(metadata_path)
            if metadata_path.exists()
            else None
        )
        output_parts.append(
            format_embedding_header(metadata),
        )
        output_parts.append("")

    output_parts.append(build_embedding_table(results))
    output_parts.append("━" * TABLE_WIDTH)

    print("\n".join(output_parts))


# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "View vLLM CPU benchmark results "
            "in the terminal."
        ),
    )
    parser.add_argument(
        "path",
        help=(
            "Path to benchmarks.json, a results "
            "directory (LLM), or an embedding "
            "test-run directory"
        ),
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Suppress the metadata header block",
    )
    args = parser.parse_args()

    fmt, result_dir, benchmarks_path = detect_format(
        args.path,
    )
    show_header = not args.no_header

    if fmt == "llm":
        view_llm(benchmarks_path, result_dir, show_header)
    elif fmt == "embedding":
        view_embedding(result_dir, show_header)


if __name__ == "__main__":
    main()
