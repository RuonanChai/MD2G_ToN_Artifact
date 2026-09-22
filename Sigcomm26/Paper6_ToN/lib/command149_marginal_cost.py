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

"""Corrected nested-component missing-set marginal cost. Frozen 1.05 margin. Not V2."""
import json
import os
from pathlib import Path

from component_actuation_plan import TRACKS, closure

REPO = artifact_root()
STATES = [f"Rep{i}" for i in range(1, 10)]
FROZEN_SAFETY_MARGIN = 1.05
DEVICE_NEED = {
    "Rep1": 0.0,
    "Rep2": 0.15,
    "Rep3": 0.25,
    "Rep4": 0.2,
    "Rep5": 0.35,
    "Rep6": 0.3,
    "Rep7": 0.4,
    "Rep8": 0.35,
    "Rep9": 0.45,
}

_RATES: dict[str, dict[str, float]] | None = None
_QNORM: dict | None = None


def _holdout_released() -> bool:
    return (REPO / "state" / "COMMAND153_FINAL_DEV_FROZEN.json").is_file()


def _rates(content: str) -> dict[str, float]:
    global _RATES
    if _RATES is None:
        body = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
        _RATES = {
            c: {t: float(body["contents"][c][t]["steady_state_payload_mbps"]) for t in TRACKS}
            for c in body["contents"]
            if c != "loot" or _holdout_released()
        }
    if content not in _RATES and _holdout_released():
        body = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
        if content in body["contents"]:
            _RATES[content] = {
                t: float(body["contents"][content][t]["steady_state_payload_mbps"]) for t in TRACKS
            }
    return _RATES[content]


def _qnorm(content: str) -> dict:
    global _QNORM
    if _QNORM is None:
        _QNORM = json.loads((REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json").read_text())["Q_norm"]
    return dict(_QNORM[content])


def missing_components(state: str, active: list[str] | set[str] | None) -> list[str]:
    a = set(active or [])
    return [c for c in closure(state) if c not in a]


def delta_r_mbps(content: str, state: str, active: list[str] | set[str] | None) -> float:
    r = _rates(content)
    return float(sum(r[c] for c in missing_components(state, active)))


def cumulative_prefix_mbps(content: str, state: str) -> float:
    """Non-authoritative diagnostic: full C(r). Must not be used for admission."""
    r = _rates(content)
    return float(sum(r[c] for c in closure(state)))


def active_from_plan(cell_dir: Path | None) -> list[str]:
    if cell_dir is None:
        env = (os.environ.get("COMMAND148_CELL_DIR") or "").strip()
        cell_dir = Path(env) if env else None
    if cell_dir is None:
        return []
    p = Path(cell_dir) / "COMPONENT_ACTUATION_PLAN_CURRENT.json"
    if not p.is_file():
        return []
    try:
        body = json.loads(p.read_text())
    except Exception:
        return []
    active = list(body.get("currently_active_component_set") or [])
    req = list(body.get("required_component_set") or [])
    out = [c for c in (active or req) if c in TRACKS]
    return out


def user_active_unicast(user_key: str, publisher_keys: list[str] | None) -> list[str]:
    hid = str(user_key).replace("u", "")
    prefix = f"u{hid}_"
    got = []
    for k in publisher_keys or []:
        if k.startswith(prefix):
            c = k.rsplit("_", 1)[-1]
            if c in TRACKS and c not in got:
                got.append(c)
        elif k in TRACKS and k not in got:
            got.append(k)
    return got


def project_down(
    proposed: str,
    access_mbps: float,
    device: float,
    content: str,
    active: list[str] | set[str] | None,
) -> dict:
    q = _qnorm(content)
    try:
        cand = max(1, min(9, int(str(proposed).replace("Rep", ""))))
    except Exception:
        cand = 1
    best, bq = 1, float(q.get("Rep1") or 0.0)
    chosen_delta = delta_r_mbps(content, "Rep1", active)
    for i, st in enumerate(STATES, start=1):
        if i > cand:
            continue
        if float(device) + 1e-9 < DEVICE_NEED[st]:
            continue
        dlt = delta_r_mbps(content, st, active)
        if float(access_mbps) + 1e-9 < dlt * FROZEN_SAFETY_MARGIN:
            continue
        qq = float(q.get(st) or 0.0)
        if qq >= bq:
            bq, best, chosen_delta = qq, i, dlt
    applied = f"Rep{best}"
    return {
        "proposed": f"Rep{cand}",
        "applied": applied,
        "C_proposed": list(closure(f"Rep{cand}")),
        "C_applied": list(closure(applied)),
        "active": [c for c in TRACKS if c in set(active or [])],
        "missing_proposed": missing_components(f"Rep{cand}", active),
        "missing_applied": missing_components(applied, active),
        "DeltaR_proposed_mbps": delta_r_mbps(content, f"Rep{cand}", active),
        "DeltaR_applied_mbps": chosen_delta,
        "cumulative_proposed_mbps": cumulative_prefix_mbps(content, f"Rep{cand}"),
        "threshold_mbps": chosen_delta * FROZEN_SAFETY_MARGIN,
        "margin": FROZEN_SAFETY_MARGIN,
        "access_mbps": float(access_mbps),
        "device": float(device),
        "feasible": True,
        "physics": "missing_component_DeltaR",
    }
