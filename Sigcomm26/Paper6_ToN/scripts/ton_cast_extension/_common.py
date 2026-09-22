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

"""Shared paths and frozen loaders for the MD2G-Cast ToN extension evidence pack.

Does not modify MD2G-Cast, frozen metrics, or existing artifacts.
"""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
RESULTS = TON / "results"
DEV_JSON = TON / "final" / "COMMAND153_FIGURE_SOURCE_DATA" / "dev.json"
LOOT_JSON = TON / "final" / "COMMAND153_FIGURE_SOURCE_DATA" / "loot.json"
CANARY_JSON = TON / "final" / "COMMAND153_FIGURE_SOURCE_DATA" / "canary_rbv1.json"
MAINDEV = TON / "artifacts" / "command148_maindev"
CAST_SUMMARY = REPO / "MM26" / "paper_figures" / "data" / "camera_ready_summary.csv"
QUALITY = REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json"
BITRATE = REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json"
DAG = REPO / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json"

USERS = (20, 60, 100)
NETS = ("4g", "wifi", "fiber_optic")
SEEDS = (151, 152, 153)
CONTENT = "redandblack"
WARMUP_S = 30.0
FROZEN_U = (0.25, 0.60, 0.15)
STRAT_LIVE = ("MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT")
STRAT_LABEL = {
    "MD2G_COMPONENT": "MD2G-Cast",
    "HV3_COMPONENT": "Heuristic",
    "CLUSTERING_COMPONENT": "Clustering",
    "MOQ_UNICAST_COMPONENT": "MoQ Unicast",
    "MCG": "MCG",
    "rolling": "Rolling",
}

# Command82 handbook (Cast camera-ready, 105/105). Rolling 4G/Fiber are not in command69 summary.
CAST_ROLLING_U = {
    ("fiber_optic", 20): 0.000,
    ("fiber_optic", 60): 0.038,
    ("fiber_optic", 100): 0.040,
    ("4g", 20): 0.020,
    ("4g", 60): 0.000,
    ("4g", 100): 0.000,
    ("wifi", 20): 0.001,
    ("wifi", 60): 0.044,
    ("wifi", 100): 0.020,
}


def clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def utility(ro: float, rq: float, rb: float, w=FROZEN_U) -> float:
    return clip01(w[0] * float(ro) + w[1] * float(rq) - w[2] * float(rb))


def load_json(path: Path):
    return json.loads(path.read_text())


def frozen_q(content: str) -> dict[str, float]:
    return {k: float(v) for k, v in load_json(QUALITY)["Q_norm"][content].items()}


def frozen_rates(content: str) -> dict[str, float]:
    body = load_json(BITRATE)["contents"][content]
    return {t: float(body[t]["steady_state_payload_mbps"]) for t in ("b0", "db1", "db2", "e1", "e2")}


def closures() -> dict[str, list[str]]:
    return {st: list(spec["C"]) for st, spec in load_json(DAG)["logical_states"].items()}


def prereq() -> dict[str, tuple[str, ...]]:
    return {
        "b0": (),
        "db1": ("b0",),
        "db2": ("b0", "db1"),
        "e1": ("b0",),
        "e2": ("b0", "e1"),
    }


def load_dev_rows() -> list[dict]:
    return load_json(DEV_JSON)


def load_loot_rows() -> list[dict]:
    return load_json(LOOT_JSON)


def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def pct(xs, p: float) -> float:
    xs = sorted(float(x) for x in xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p / 100.0
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - k) + xs[hi] * (k - lo)


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields = fields or list(rows[0].keys())
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def filter_scope(rows, *, content=CONTENT, nets=NETS, users=USERS, strategies=None):
    out = []
    for r in rows:
        if r.get("content") != content:
            continue
        if r.get("network") not in nets:
            continue
        if int(r.get("users") or 0) not in users:
            continue
        if strategies is not None and r.get("strategy") not in strategies:
            continue
        out.append(r)
    return out


def aggregate_live(rows) -> dict[tuple, dict]:
    buckets: dict[tuple, list] = defaultdict(list)
    for r in rows:
        key = (r["strategy"], r["network"], int(r["users"]), int(r["seed"]))
        buckets[key].append(r)
    out = {}
    for k, vs in buckets.items():
        out[k] = {
            "U": mean(v["U"] for v in vs),
            "Rq": mean(v["Rq"] for v in vs),
            "Ro": mean(v["Ro_component"] for v in vs),
            "Rb": mean(v["Rb"] for v in vs),
            "n": len(vs),
            "B_shared": mean(v.get("B_shared") or 0 for v in vs),
            "B_unicast": mean(v.get("B_unicast") or 0 for v in vs),
            "mean_rx": mean(v.get("mean_rx") or 0 for v in vs),
            "stall_last": mean(v.get("stall_last") or 0 for v in vs),
            "rows": vs,
        }
    return out
