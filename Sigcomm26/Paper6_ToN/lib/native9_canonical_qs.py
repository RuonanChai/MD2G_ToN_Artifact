#!/usr/bin/env python3
"""Shared native-9 Qs from COMMAND103 paper_quality_score (all strategies).

Affine map paper_quality_score in [1,4] → Qs in [0.4, 1.0]:
  Qs = 0.4 + 0.6 * (paper_q - 1) / 3

This supersedes the dispatch Table-1 hardcode that set Rep3=Rep8=Rep9=0.4.
Enable via SIGCOMM_CANONICAL_QS_FROM_COMMAND103=1 (command125 opt0+).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_TON = Path(__file__).resolve().parents[1]
_MAP = _TON / "state" / "COMMAND103_REP_QUALITY_MAP.json"

# Legacy Table-1 (diagnostic / pre-supersession)
TABLE1_QS = {
    1: 0.8,
    2: 0.6,
    3: 0.4,
    4: 1.0,
    5: 1.0,
    6: 0.6,
    7: 0.8,
    8: 0.4,
    9: 0.4,
}


def paper_to_qs(paper_quality_score: float) -> float:
    return float(max(0.4, min(1.0, 0.4 + 0.6 * ((float(paper_quality_score) - 1.0) / 3.0))))


@lru_cache(maxsize=1)
def load_command103_qs() -> dict[int, float]:
    body = json.loads(_MAP.read_text())
    out: dict[int, float] = {}
    for row in body.get("reps") or []:
        rid = int(row["rep_id"])
        out[rid] = paper_to_qs(float(row["paper_quality_score"]))
    for rid in range(1, 10):
        out.setdefault(rid, 0.4)
    return out


@lru_cache(maxsize=1)
def load_command103_paper_q() -> dict[int, float]:
    body = json.loads(_MAP.read_text())
    return {int(r["rep_id"]): float(r["paper_quality_score"]) for r in body.get("reps") or []}


def canonical_qs_enabled() -> bool:
    return os.environ.get("SIGCOMM_CANONICAL_QS_FROM_COMMAND103", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def qs_for_rep(rep_id: int) -> float:
    rid = int(rep_id)
    if canonical_qs_enabled():
        return float(load_command103_qs().get(rid, 0.4))
    return float(TABLE1_QS.get(rid, 0.4))
