"""Shared loaders for scale-out (llm-d) benchmark result directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


def _parse_podman_bytes(s: str) -> float:
    s = (s or "").strip().upper()
    if not s:
        return 0.0
    multipliers = {
        "B": 1,
        "KB": 1e3,
        "KIB": 1024,
        "MB": 1e6,
        "MIB": 1024**2,
        "GB": 1e9,
        "GIB": 1024**3,
        "TB": 1e12,
        "TIB": 1024**4,
    }
    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            try:
                return float(s[: -len(suffix)].strip()) * mult
            except ValueError:
                return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_podman_pct(s: str) -> float:
    try:
        return float((s or "").replace("%", "").strip())
    except ValueError:
        return 0.0


def _run_label(meta: Dict[str, Any], run_dir: Path, n_instance_files: int) -> str:
    policy = meta.get("routing_policy", "unknown")
    model_raw = meta.get("model_name") or meta.get("model") or ""
    model_short = model_raw.split("/")[-1] if model_raw else ""
    n_inst = meta.get("num_instances", n_instance_files or "?")
    lmcache = (
        "lmcache"
        if meta.get("lmcache_backend", "none") not in ("none", "", None)
        else "no-lmcache"
    )
    run_id = meta.get("test_run_id") or run_dir.name
    parts = [str(run_id), f"{n_inst}inst", str(policy), lmcache]
    if model_short:
        parts.append(model_short)
    return " | ".join(parts)


def _is_scaleout_run(meta: Dict[str, Any], run_dir: Path) -> bool:
    if meta.get("deployment_type") == "scaleout":
        return True
    run_id = str(meta.get("test_run_id") or "")
    if run_id.startswith("scaleout-"):
        return True
    if list(run_dir.glob("vllm-metrics-instance-*.json")):
        return True
    if (run_dir / "container-stats-scaleout.jsonl").exists():
        return True
    if (run_dir / "epp-metrics.json").exists():
        return True
    return False


def resolve_benchmarks_file(run_dir: Path) -> Optional[Path]:
    direct = run_dir / "benchmarks.json"
    if direct.exists():
        return direct
    for parent in [run_dir.parent, run_dir.parent.parent]:
        candidate = parent / "benchmarks.json"
        if candidate.exists():
            return candidate
    return None


def find_scaleout_runs(base_dir: str) -> List[Dict[str, Any]]:
    """Discover scale-out runs under a results tree."""
    runs: List[Dict[str, Any]] = []
    base = Path(base_dir)
    if not base.exists():
        return runs

    seen_dirs: set[str] = set()
    for meta_file in base.rglob("test-metadata.json"):
        run_dir = meta_file.parent
        key = str(run_dir.resolve())
        if key in seen_dirs:
            continue
        seen_dirs.add(key)

        meta: Dict[str, Any] = {}
        meta_ok = True
        try:
            meta = json.loads(meta_file.read_text())
        except Exception:
            meta_ok = False

        instance_files = sorted(run_dir.glob("vllm-metrics-instance-*.json"))
        if not _is_scaleout_run(meta, run_dir):
            continue

        benchmarks_file = resolve_benchmarks_file(run_dir)
        runs.append({
            "path": run_dir,
            "meta": meta,
            "meta_ok": meta_ok,
            "instance_files": instance_files,
            "epp_file": run_dir / "epp-metrics.json",
            "benchmarks_file": benchmarks_file,
            "container_stats_file": run_dir / "container-stats-scaleout.jsonl",
            "label": _run_label(meta, run_dir, len(instance_files)),
        })
    return runs


def _metric_successful(metrics: Dict[str, Any], key: str) -> Dict[str, Any]:
    return metrics.get(key, {}).get("successful", {}) or {}


def _percentile(stats: Dict[str, Any], p: str) -> Optional[float]:
    pcts = stats.get("percentiles") or {}
    return pcts.get(p)


def load_guidellm_client_df(benchmarks_path: Path) -> Optional[pd.DataFrame]:
    """Parse GuideLLM benchmarks.json into a concurrency-indexed DataFrame."""
    try:
        bench_data = json.loads(benchmarks_path.read_text())
    except Exception:
        return None

    client_rows: List[Dict[str, Any]] = []
    for b in bench_data.get("benchmarks", []):
        cfg = b.get("config", {})
        m = b.get("metrics", {})
        strategy = cfg.get("strategy", {})
        conc = (
            strategy.get("streams")
            or strategy.get("max_concurrency")
            or strategy.get("worker_count")
        )
        ttft = _metric_successful(m, "time_to_first_token_ms")
        itl = _metric_successful(m, "inter_token_latency_ms")
        tpot = _metric_successful(m, "time_per_output_token_ms")
        if not tpot.get("mean"):
            tpot = itl
        tps = _metric_successful(m, "tokens_per_second")
        if not tps.get("mean"):
            tps = _metric_successful(m, "output_tokens_per_second")
        rps = _metric_successful(m, "requests_per_second")
        e2e = _metric_successful(m, "end_to_end_latency_ms")

        has_signal = (
            ttft.get("mean")
            or tps.get("mean")
            or rps.get("mean")
            or e2e.get("mean")
        )
        if not has_signal:
            continue

        client_rows.append({
            "Concurrency": conc,
            "RPS": rps.get("mean", 0) or 0,
            "Output TPS": tps.get("mean", 0) or 0,
            "TTFT mean (ms)": ttft.get("mean"),
            "TTFT P50 (ms)": _percentile(ttft, "p50"),
            "TTFT P95 (ms)": _percentile(ttft, "p95"),
            "TTFT P99 (ms)": _percentile(ttft, "p99"),
            "TPOT mean (ms)": tpot.get("mean"),
            "TPOT P50 (ms)": _percentile(tpot, "p50"),
            "TPOT P95 (ms)": _percentile(tpot, "p95"),
            "TPOT P99 (ms)": _percentile(tpot, "p99"),
            "ITL mean (ms)": itl.get("mean"),
            "ITL P95 (ms)": _percentile(itl, "p95"),
            "E2E mean (ms)": e2e.get("mean"),
            "E2E P99 (ms)": _percentile(e2e, "p99"),
        })

    if not client_rows:
        return None
    df = pd.DataFrame(client_rows)
    if "Concurrency" in df.columns:
        df = df.sort_values("Concurrency", na_position="last")
    return df


def load_embedding_client_df(run_dir: Path) -> Optional[pd.DataFrame]:
    """Load vllm-bench embedding results from latency/ and operating_point/."""
    rows: List[Dict[str, Any]] = []
    for subdir_name in ("latency", "operating_point"):
        subdir = run_dir / subdir_name
        if not subdir.is_dir():
            continue
        for json_file in sorted(subdir.glob("*.json")):
            try:
                result = json.loads(json_file.read_text())
            except Exception:
                continue
            if "request_throughput" not in result:
                continue
            stem = json_file.stem
            if stem.startswith("concurrent-") or stem.startswith("conc-"):
                param = stem.split("-", 1)[-1]
                try:
                    conc = int(param)
                except ValueError:
                    conc = result.get("max_concurrency")
            else:
                conc = result.get("max_concurrency")

            rows.append({
                "Concurrency": conc,
                "RPS": result.get("request_throughput", 0),
                "Output TPS": result.get("total_token_throughput")
                or result.get("output_throughput"),
                "E2E mean (ms)": result.get("mean_e2el_ms"),
                "E2E P99 (ms)": result.get("p99_e2el_ms"),
                "TTFT mean (ms)": None,
                "TPOT mean (ms)": None,
            })

    if not rows:
        return None
    return pd.DataFrame(rows).sort_values("Concurrency", na_position="last")


def load_client_results_for_run(run: Dict[str, Any]) -> Tuple[Optional[pd.DataFrame], str]:
    """Return (dataframe, source) where source is guidellm, embedding, or none."""
    bf = run.get("benchmarks_file")
    if bf is not None and Path(bf).exists():
        df = load_guidellm_client_df(Path(bf))
        if df is not None:
            return df, "guidellm"
    run_dir = Path(run["path"])
    df = load_embedding_client_df(run_dir)
    if df is not None:
        return df, "embedding"
    return None, "none"


def _parse_podman_stats_record(item: Dict[str, Any]) -> Dict[str, Any]:
    cpu_str = item.get("CPUPerc") or item.get("cpu_percent", "0%")
    mem_str = item.get("MemUsage") or item.get("mem_usage", "0B / 0B")
    pids = item.get("PIDs") or item.get("pids", 0)
    ts = item.get("timestamp", "")
    name = (
        item.get("Name")
        or item.get("name")
        or item.get("Container")
        or item.get("container")
        or "unknown"
    )
    mem_parts = str(mem_str).split("/")
    mem_used = _parse_podman_bytes(mem_parts[0].strip()) if mem_parts else 0.0
    mem_limit = _parse_podman_bytes(mem_parts[1].strip()) if len(mem_parts) > 1 else 0.0
    return {
        "timestamp": pd.to_datetime(ts, utc=True, errors="coerce"),
        "container": str(name).lstrip("/"),
        "cpu_pct": _parse_podman_pct(str(cpu_str)),
        "mem_usage_gb": mem_used / 1e9,
        "mem_limit_gb": mem_limit / 1e9,
        "mem_pct": _parse_podman_pct(
            str(item.get("MemPerc") or item.get("mem_percent", "0%"))
        ),
        "pids": int(str(pids)) if str(pids).isdigit() else 0,
    }


def load_scaleout_container_stats(run_dir: Path) -> Dict[str, pd.DataFrame]:
    """Per-container time series from container-stats-scaleout.jsonl."""
    stats_file = run_dir / "container-stats-scaleout.jsonl"
    if not stats_file.exists():
        return {}

    by_container: Dict[str, List[Dict[str, Any]]] = {}
    try:
        with open(stats_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row = _parse_podman_stats_record(item)
                if pd.isna(row["timestamp"]):
                    continue
                by_container.setdefault(row["container"], []).append(row)
    except OSError:
        return {}

    out: Dict[str, pd.DataFrame] = {}
    for name, rows in by_container.items():
        df = (
            pd.DataFrame(rows)
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        t0 = df["timestamp"].min()
        df["elapsed_min"] = (df["timestamp"] - t0).dt.total_seconds() / 60.0
        out[name] = df
    return out


def aggregate_container_stats_for_run(
    container_dfs: Dict[str, pd.DataFrame],
    role_filter: Optional[str] = None,
) -> pd.DataFrame:
    """Sum CPU/mem across containers at each timestamp (for embedding-style charts)."""
    frames: List[pd.DataFrame] = []
    for name, df in container_dfs.items():
        if role_filter and role_filter not in name:
            continue
        frames.append(df.assign(_key=name))
    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    agg = (
        combined.groupby("timestamp", as_index=False)
        .agg(
            cpu_pct=("cpu_pct", "sum"),
            mem_usage_gb=("mem_usage_gb", "sum"),
            mem_limit_gb=("mem_limit_gb", "sum"),
            pids=("pids", "sum"),
        )
        .sort_values("timestamp")
    )
    t0 = agg["timestamp"].min()
    agg["elapsed_min"] = (agg["timestamp"] - t0).dt.total_seconds() / 60.0
    return agg
