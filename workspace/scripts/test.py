#!/usr/bin/env python3
"""
test.py — Complex demo script for n8n Execute Command / runner testing.

Features:
- Loads config from env + optional JSON config file
- Reads input CSV + JSON (if present)
- Cleans data (types, missing values)
- Computes stats + outlier detection + grouping
- Writes a report JSON file
- Generates a simple PNG chart (uses matplotlib if installed, else skips)
- Structured logging to stdout (great for n8n)
"""

from __future__ import annotations

import os
import sys
import json
import csv
import math
import time
import random
import pathlib
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Utilities
# ----------------------------

def log(level: str, msg: str, **fields: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "msg": msg,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False))


def read_json(path: pathlib.Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log("ERROR", "Failed to read JSON", path=str(path), error=str(e))
        return None


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not (isinstance(x, float) and math.isnan(x)):
        return float(x)
    s = str(x).strip()
    if s == "" or s.lower() in {"na", "null", "none", "nan"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def percentile(sorted_vals: List[float], p: float) -> float:
    """Linear interpolation percentile for p in [0,100]."""
    if not sorted_vals:
        raise ValueError("Empty list")
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


def iqr_outliers(values: List[float], k: float = 1.5) -> Tuple[float, float, List[float]]:
    """Return (low_fence, high_fence, outliers)."""
    vals = sorted(values)
    q1 = percentile(vals, 25)
    q3 = percentile(vals, 75)
    iqr = q3 - q1
    low = q1 - k * iqr
    high = q3 + k * iqr
    out = [v for v in vals if v < low or v > high]
    return low, high, out


# ----------------------------
# Data model
# ----------------------------

@dataclass
class Config:
    workspace_dir: str
    input_csv: str
    input_json: str
    output_report: str
    output_chart: str
    numeric_field: str
    group_field: str
    seed: int
    simulate_if_missing: bool

    @staticmethod
    def from_env_and_file() -> "Config":
        ws = os.environ.get("WORKSPACE", "/workspace")
        cfg_path = pathlib.Path(ws) / "scripts" / "config.json"
        file_cfg = read_json(cfg_path) or {}

        def pick(key: str, default: Any) -> Any:
            env_key = f"TEST_{key.upper()}"
            if env_key in os.environ:
                return os.environ[env_key]
            return file_cfg.get(key, default)

        return Config(
            workspace_dir=str(ws),
            input_csv=str(pick("input_csv", f"{ws}/data/input.csv")),
            input_json=str(pick("input_json", f"{ws}/data/extra.json")),
            output_report=str(pick("output_report", f"{ws}/out/report.json")),
            output_chart=str(pick("output_chart", f"{ws}/out/chart.png")),
            numeric_field=str(pick("numeric_field", "value")),
            group_field=str(pick("group_field", "category")),
            seed=int(pick("seed", "42")),
            simulate_if_missing=str(pick("simulate_if_missing", "true")).lower() in {"1", "true", "yes"},
        )


# ----------------------------
# Data loading: pandas if available, else csv module
# ----------------------------

def load_rows_pure_csv(path: pathlib.Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(r) for r in reader]


def simulate_rows(n: int, numeric_field: str, group_field: str, seed: int) -> List[Dict[str, Any]]:
    random.seed(seed)
    groups = ["alpha", "beta", "gamma", "delta"]
    rows = []
    for i in range(n):
        g = random.choice(groups)
        base = {"alpha": 50, "beta": 80, "gamma": 30, "delta": 60}[g]
        noise = random.gauss(0, 10)
        # occasional outlier
        if random.random() < 0.03:
            noise += random.choice([-1, 1]) * random.uniform(60, 120)
        rows.append({
            "id": f"row_{i+1}",
            group_field: g,
            numeric_field: round(base + noise, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    return rows


def try_load_with_pandas(path: pathlib.Path) -> Optional["Any"]:
    try:
        import pandas as pd  # type: ignore
        return pd.read_csv(path)
    except Exception:
        return None


# ----------------------------
# Analysis
# ----------------------------

def compute_summary(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"count": 0}

    vals = sorted(values)
    mean = statistics.fmean(vals)
    med = statistics.median(vals)
    stdev = statistics.pstdev(vals) if len(vals) > 1 else 0.0

    p10 = percentile(vals, 10)
    p90 = percentile(vals, 90)
    low, high, out = iqr_outliers(vals)

    return {
        "count": len(vals),
        "min": vals[0],
        "max": vals[-1],
        "mean": mean,
        "median": med,
        "stdev_pop": stdev,
        "p10": p10,
        "p90": p90,
        "iqr_low_fence": low,
        "iqr_high_fence": high,
        "outliers_count": len(out),
        "outliers_sample": out[:10],
    }


def group_stats(rows: List[Dict[str, Any]], numeric_field: str, group_field: str) -> Dict[str, Any]:
    buckets: Dict[str, List[float]] = {}
    for r in rows:
        g = str(r.get(group_field, "unknown"))
        v = safe_float(r.get(numeric_field))
        if v is None:
            continue
        buckets.setdefault(g, []).append(v)

    grouped = {}
    for g, vals in buckets.items():
        grouped[g] = compute_summary(vals)

    # rank groups by mean
    ranking = sorted(
        [(g, grouped[g].get("mean", float("-inf"))) for g in grouped.keys()],
        key=lambda x: x[1],
        reverse=True
    )

    return {
        "groups": grouped,
        "ranking_by_mean": ranking,
    }


def write_json(path: pathlib.Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def maybe_make_chart(chart_path: pathlib.Path, rows: List[Dict[str, Any]], numeric_field: str, group_field: str) -> Dict[str, Any]:
    """
    Creates a simple bar chart: mean per group.
    Requires matplotlib. If not installed, returns skipped status.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:
        return {"chart": "skipped", "reason": f"matplotlib not available ({e})"}

    stats = group_stats(rows, numeric_field, group_field)
    means = []
    labels = []
    for g, s in stats["groups"].items():
        if "mean" in s:
            labels.append(g)
            means.append(s["mean"])

    chart_path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure()
    plt.bar(labels, means)
    plt.title(f"Mean {numeric_field} by {group_field}")
    plt.ylabel("mean")
    plt.tight_layout()
    plt.savefig(chart_path.as_posix(), dpi=150)
    plt.close()

    return {"chart": "written", "path": str(chart_path)}


# ----------------------------
# Main
# ----------------------------

def main() -> int:
    t0 = time.time()
    cfg = Config.from_env_and_file()

    ws = pathlib.Path(cfg.workspace_dir)
    csv_path = pathlib.Path(cfg.input_csv)
    json_path = pathlib.Path(cfg.input_json)
    report_path = pathlib.Path(cfg.output_report)
    chart_path = pathlib.Path(cfg.output_chart)

    log("INFO", "Starting test.py", config=asdict(cfg))

    # Load extra JSON config/data if present
    extra = read_json(json_path) if json_path.exists() else None
    if extra is not None:
        log("INFO", "Loaded extra JSON", path=str(json_path), keys=list(extra.keys())[:20])
    else:
        log("INFO", "No extra JSON found (ok)", path=str(json_path))

    rows: List[Dict[str, Any]] = []

    if csv_path.exists():
        # Try pandas for speed/robustness
        df = try_load_with_pandas(csv_path)
        if df is not None:
            # convert to records
            rows = df.to_dict(orient="records")
            log("INFO", "Loaded CSV with pandas", path=str(csv_path), rows=len(rows))
        else:
            rows = load_rows_pure_csv(csv_path)
            log("INFO", "Loaded CSV with csv module", path=str(csv_path), rows=len(rows))
    else:
        log("WARN", "CSV not found", path=str(csv_path))
        if cfg.simulate_if_missing:
            rows = simulate_rows(250, cfg.numeric_field, cfg.group_field, cfg.seed)
            log("INFO", "Simulated dataset", rows=len(rows), seed=cfg.seed)
        else:
            log("ERROR", "No input data and simulation disabled")
            return 2

    # Normalize numeric field values
    cleaned: List[Dict[str, Any]] = []
    missing_count = 0
    for r in rows:
        v = safe_float(r.get(cfg.numeric_field))
        if v is None:
            missing_count += 1
        cleaned.append({**r, cfg.numeric_field: v})

    numeric_vals = [r[cfg.numeric_field] for r in cleaned if isinstance(r.get(cfg.numeric_field), (int, float))]

    overall = compute_summary([float(v) for v in numeric_vals])
    grouped = group_stats(cleaned, cfg.numeric_field, cfg.group_field)

    chart_status = maybe_make_chart(chart_path, cleaned, cfg.numeric_field, cfg.group_field)

    report = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "cwd": os.getcwd(),
            "workspace_exists": ws.exists(),
            "python": sys.version,
            "rows_total": len(rows),
            "rows_cleaned": len(cleaned),
            "missing_numeric_values": missing_count,
        },
        "overall": overall,
        "grouped": grouped,
        "chart": chart_status,
        "extra_json_loaded": extra is not None,
    }

    write_json(report_path, report)
    elapsed = round(time.time() - t0, 3)

    log("INFO", "Report written", report_path=str(report_path), elapsed_s=elapsed)
    log("INFO", "Done", elapsed_s=elapsed)

    # Print a final compact line (easy to read in n8n)
    print(f"OK: wrote report to {report_path} in {elapsed}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
