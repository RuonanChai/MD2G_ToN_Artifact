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

"""Fail-closed Fig.4-style fluidity–QoE trade-off audit.

Original family: User_Experience_Trade-off scatter with
  X = Average Data Arrival Interval (ms)
  Y = Average QoE
Requires non-zero delay/arrival-interval evidence + grounded quality axis.
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
GAP = OUT_DIR / "EVIDENCE_GAP_FIG4_TRADEOFF.json"


def nonzero_cells(dirs: list[Path], field: str, sample: int | None = None) -> dict:
    random.seed(0)
    use = dirs if sample is None else random.sample(dirs, min(sample, len(dirs)))
    checked = 0
    hit = 0
    for d in use:
        csvs = list(d.glob("client_h*_perf.csv"))
        if not csvs:
            continue
        checked += 1
        found = False
        for p in csvs[:2]:
            with p.open() as f:
                for row in csv.DictReader(f):
                    try:
                        v = float(row.get(field) or 0.0)
                    except Exception:
                        v = 0.0
                    if v > 0:
                        found = True
                        break
            if found:
                break
        if found:
            hit += 1
    return {"checked": checked, "nonzero": hit}


def main() -> int:
    canary = [d for d in ART_CANARY.iterdir() if d.is_dir() and "INVALID" not in d.name]
    maindev = [d for d in ART_MAIN.iterdir() if d.is_dir() and "INVALID" not in d.name]
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "token": "FIG4_FLUIDITY_QOE_TRADEOFF_FAIL_CLOSED",
        "target_family": "Sigcomm User_Experience_Trade-off (Fig.4/5-style fluidity–QoE scatter)",
        "required_axes": {
            "x": "Average Data Arrival Interval (ms) from delay_ms / equivalent",
            "y": "Average QoE / utility",
        },
        "audit": {
            "canary_delay_ms": nonzero_cells(canary, "delay_ms"),
            "maindev_sample300_delay_ms": nonzero_cells(maindev, "delay_ms", 300),
            "y_axis_U_Rq": "AVAILABLE in final/COMMAND153_FIGURE_SOURCE_DATA/*.json",
        },
        "decision": "SKIP Fig.4-style PDF — do not substitute bar charts or Rb–U as Fig.4",
        "reason": (
            "X-axis (data arrival interval / delay_ms) is unimplemented zero in audited VALID "
            "perf.csv; PRIMARY_STATS marks delay NOT_IN_FINAL_CLAIM_CONTRACT. Y-axis alone is "
            "insufficient to claim Fig.4 family fidelity."
        ),
        "tierB_scatter_note": (
            "Separate Tier-B scatter PDFs (Rb vs U) may exist under this folder for mechanism "
            "context; they are NOT Fig.4-family figures."
        ),
    }
    GAP.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print("NO_FIG4_PDF_EMITTED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
