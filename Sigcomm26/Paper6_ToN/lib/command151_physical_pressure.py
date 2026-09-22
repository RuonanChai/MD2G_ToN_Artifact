#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Canonical physical-pressure Rb. Not volume, not Ro."""
import json
import math
from pathlib import Path

REPO = artifact_root()
CONTRACT_P = REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_CONTRACT.json"
SAMPLES = "PHYSICAL_PRESSURE_TIMESERIES.jsonl"
SUMMARY = "PHYSICAL_PRESSURE_SUMMARY.json"


def load_contract() -> dict:
    return json.loads(CONTRACT_P.read_text())


def clip01(x: float) -> float:
    if not math.isfinite(x):
        return float("nan")
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


def _pct(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    if len(ys) == 1:
        return float(ys[0])
    k = (len(ys) - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return float(ys[lo])
    w = k - lo
    return float(ys[lo] * (1.0 - w) + ys[hi] * w)


def samples_from_rows(rows: list[dict], capacity_bps: float, idle_floor: float, exceed_th: float) -> dict:
    utils: list[float] = []
    pressures: list[float] = []
    denom = max(1.0 - idle_floor, 1e-9)
    raw_tx0 = int(rows[0]["tx_bytes"]) if rows else 0
    raw_rx0 = int(rows[0]["rx_bytes"]) if rows else 0
    raw_tx1 = int(rows[-1]["tx_bytes"]) if rows else 0
    raw_rx1 = int(rows[-1]["rx_bytes"]) if rows else 0
    for i in range(1, len(rows)):
        dt = float(rows[i]["t"]) - float(rows[i - 1]["t"])
        if dt <= 0 or capacity_bps <= 0:
            continue
        dtx = int(rows[i]["tx_bytes"]) - int(rows[i - 1]["tx_bytes"])
        u = (8.0 * max(dtx, 0)) / (capacity_bps * dt)
        utils.append(float(u))
        pressures.append(clip01(max(0.0, u - idle_floor) / denom))
    if not pressures or any(not math.isfinite(x) for x in pressures + utils):
        return {
            "Rb": None,
            "utilization_mean": None,
            "utilization_p95": None,
            "utilization_p99": None,
            "pressure_exceedance_fraction": None,
            "raw_protocol_inclusive_tx_bytes": raw_tx1 - raw_tx0,
            "raw_protocol_inclusive_rx_bytes": raw_rx1 - raw_rx0,
            "capacity_bps": capacity_bps,
            "n_intervals": len(utils),
        }
    n_ex = sum(1 for u in utils if u > exceed_th)
    rb = clip01(float(_pct(pressures, 95.0) or 0.0))
    return {
        "Rb": rb,
        "utilization_mean": sum(utils) / len(utils),
        "utilization_p95": _pct(utils, 95.0),
        "utilization_p99": _pct(utils, 99.0),
        "pressure_exceedance_fraction": n_ex / len(utils),
        "raw_protocol_inclusive_tx_bytes": raw_tx1 - raw_tx0,
        "raw_protocol_inclusive_rx_bytes": raw_rx1 - raw_rx0,
        "capacity_bps": capacity_bps,
        "n_intervals": len(utils),
        "canonical_Rb_formula": "clip(P95((u-idle_floor)/(1-idle_floor)),0,1)",
    }


def summarize_cell(cell: Path) -> dict | None:
    p = cell / SAMPLES
    if not p.is_file() or p.stat().st_size <= 0:
        return None
    rows = [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    if len(rows) < 2:
        return None
    cap = float(rows[-1].get("capacity_bps") or 0.0)
    if cap <= 0 and rows[-1].get("capacity_mbps"):
        cap = float(rows[-1]["capacity_mbps"]) * 1e6
    c = load_contract()
    idle = float((c.get("utilization") or {}).get("idle_floor_util") or 0.02)
    th = float(c.get("pressure_exceedance_threshold_util") or 0.90)
    out = samples_from_rows(rows, cap, idle, th)
    out["bottleneck_identity"] = (c.get("bottleneck") or {}).get("identity")
    out["iface"] = (c.get("bottleneck") or {}).get("iface")
    (cell / SUMMARY).write_text(json.dumps(out, indent=2) + "\n")
    return out
