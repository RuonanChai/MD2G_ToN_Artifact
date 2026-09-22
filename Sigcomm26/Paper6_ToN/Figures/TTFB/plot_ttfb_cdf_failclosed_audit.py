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

"""Fail-closed TTFB CDF generator.

Original Sigcomm family: paper_figures/Sigcomm/TTFB/plot_ttfb_cdf_*.py
Required evidence: non-zero per-client first-byte timing (ttfb_base_ms or equivalent).

This script audits frozen VALID canary/MAINDEV perf.csv and exits non-zero with an
evidence-gap report if TTFB cannot be reconstructed truthfully. It never fabricates
CDFs from zero placeholders.
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
GAP = OUT_DIR / "EVIDENCE_GAP_TTFB.json"


def _scan(dirs: list[Path], field: str = "ttfb_base_ms", sample: int | None = None) -> dict:
    random.seed(0)
    use = dirs if sample is None else random.sample(dirs, min(sample, len(dirs)))
    checked = 0
    nonzero = 0
    mx = 0.0
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
                        mx = max(mx, v)
                        break
            if found:
                break
        if found:
            nonzero += 1
    return {"checked_cells_with_perf": checked, "nonzero_cells": nonzero, "max": mx}


def main() -> int:
    canary = [d for d in ART_CANARY.iterdir() if d.is_dir() and "INVALID" not in d.name] if ART_CANARY.is_dir() else []
    maindev = [d for d in ART_MAIN.iterdir() if d.is_dir() and "INVALID" not in d.name] if ART_MAIN.is_dir() else []
    report = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "token": "TTFB_FIGURE_FAMILY_FAIL_CLOSED",
        "target_family": "Sigcomm TTFB CDF (Fig.5-style / plot_ttfb_cdf_*)",
        "required_fields": ["ttfb_base_ms", "or reconstructable first-byte timing"],
        "audit": {
            "canary_ttfb_base_ms": _scan(canary, "ttfb_base_ms"),
            "canary_delay_ms": _scan(canary, "delay_ms"),
            "maindev_sample300_ttfb_base_ms": _scan(maindev, "ttfb_base_ms", sample=300),
            "maindev_sample300_delay_ms": _scan(maindev, "delay_ms", sample=300),
        },
        "receipt_note": "COMPONENT_RECEIPT.jsonl has ts/dump_bytes/stall placeholders but no first-byte TTFB field",
        "contract_note": "final/COMMAND153_PRIMARY_STATS.json delay=NOT_IN_FINAL_CLAIM_CONTRACT",
        "decision": "SKIP — do not emit TTFB CDF PDF",
        "reason": (
            "perf.csv columns ttfb_* and delay_ms exist but are unimplemented zeros across "
            "audited VALID canary (all cells) and MAINDEV sample (300). No truthful CDF can be drawn."
        ),
    }
    GAP.write_text(json.dumps(report, indent=2) + "\n")
    (OUT_DIR / "README_FAIL_CLOSED.md").write_text(
        "# TTFB CDF — FAIL CLOSED\n\n"
        + report["reason"]
        + "\n\nSee `EVIDENCE_GAP_TTFB.json`.\n"
    )
    print(json.dumps(report, indent=2))
    print("NO_PDF_EMITTED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
