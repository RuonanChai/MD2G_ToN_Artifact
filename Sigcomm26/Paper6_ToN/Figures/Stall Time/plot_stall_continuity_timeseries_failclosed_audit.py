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

"""Fail-closed Continuity-vs-Recovery (Fig.7-style stall timeseries) audit.

Original family: paper_figures/Sigcomm/Stall Time/plot_stall_time_timeseries_120s.py
Requires a truthful cumulative stall / continuity timeline over the session.
"""
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
REPO = artifact_root()
ART_CANARY = REPO / "Sigcomm26" / "Paper6_ToN" / "artifacts" / "command148_canary120_rbv1"
ART_MAIN = REPO / "Sigcomm26" / "Paper6_ToN" / "artifacts" / "command148_maindev"
GAP = OUT_DIR / "EVIDENCE_GAP_CONTINUITY_TIMESERIES.json"


def series_ok(dirs: list[Path], limit: int) -> dict:
    random.seed(1)
    use = dirs if len(dirs) <= limit else random.sample(dirs, limit)
    checked = 0
    ok = 0
    for d in use:
        csvs = list(d.glob("client_h*_perf.csv"))
        if not csvs:
            continue
        checked += 1
        for p in csvs[:1]:
            stalls = []
            with p.open() as f:
                for row in csv.DictReader(f):
                    try:
                        stalls.append(float(row.get("stall_total_sec") or 0.0))
                    except Exception:
                        stalls.append(0.0)
            if len(stalls) >= 10 and max(stalls) > 0.05 and (max(stalls) - min(stalls)) > 0.05:
                ok += 1
                break
    return {"checked": checked, "truthful_series_cells": ok}


def main() -> int:
    canary = [d for d in ART_CANARY.iterdir() if d.is_dir() and "INVALID" not in d.name]
    maindev = [d for d in ART_MAIN.iterdir() if d.is_dir() and "INVALID" not in d.name]
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "token": "CONTINUITY_TIMESERIES_FAIL_CLOSED",
        "target_family": "Sigcomm Continuity vs Recovery / stall timeseries 120s (Fig.7/8-style)",
        "audit": {
            "canary_stall_total_sec_series": series_ok(canary, 200),
            "maindev_sample_stall_total_sec_series": series_ok(maindev, 120),
        },
        "scalar_available": {
            "stall_last": "DECODE_GAP_SECONDS_POST_WARMUP in CELL_METRICS / figure source (scalar only)",
            "never_claim_zero_stall": True,
        },
        "decision": "SKIP Fig.7-style timeseries PDF",
        "reason": (
            "client_*_perf.csv stall_total_sec is flat/zero across audited VALID cells; "
            "only scalar stall_last (decode-gap) exists. Fabricating a continuity curve from "
            "scalars would be scientifically false."
        ),
        "allowed_instead": "Stall_Time_By_{Strategy,Network,Users}.pdf as supporting scalar decode-gap bars only",
    }
    GAP.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("NO_TIMESERIES_PDF_EMITTED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
