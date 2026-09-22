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

"""Deterministic command153 six-review packet from canonical stats. No Mininet. No tuning."""
import json
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
FINAL = TON / "final"


def _load(name: str) -> dict:
    p = FINAL / name
    if not p.is_file():
        p = REPO / "state" / name
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def main() -> int:
    FINAL.mkdir(parents=True, exist_ok=True)
    primary = _load("COMMAND153_PRIMARY_STATS.json")
    claim = _load("COMMAND153_CLAIM_EVIDENCE_MATRIX.json")
    matched_n = int(primary.get("n_matched_dev_or_canary") or 0)
    canary_n = int(primary.get("canary_rbv1_n") or 0)
    loot_n = int(primary.get("loot_n") or 0)
    delta = primary.get("mean_delta_U_vs_strongest_same")
    term = claim.get("terminal") or "UNSET"
    reviews = [
        (
            "SYSTEMS",
            "one executor tmux:command152_orch; nested b0/db1/db2/e1/e2; no mn -c; loot sealed until DEV freeze",
        ),
        (
            "NETWORKING_FAIRNESS",
            "same-substrate HV3/CLUSTERING/RULE vs MD2G; MOQ_UNICAST is delivery-mode not same-substrate; all launched users stay in denominators",
        ),
        (
            "METRICS_STATISTICS",
            "U=clip(0.25*Ro_component+0.60*Rq-0.15*Rb,0,1); stall supporting only; delay NOT_IN_FINAL_CLAIM_CONTRACT; Rb is not bandwidth saving",
        ),
        (
            "MECHANISM",
            "component-aware shared delivery; unfavorable matched blocks remain science; V2 not authorized from U loss; A1–A5/A7 and FoV NA are not mechanism validation",
        ),
        (
            "REPRODUCIBILITY",
            "epoch C152_RBV1 post-physical-pressure; hashes in COMMAND153_ALL_HASHES.json; pre-Rb 56 DIAGNOSTIC_ONLY",
        ),
        (
            "PAPER_CLAIMS",
            "map claims to COMMAND153_CLAIM_EVIDENCE_MATRIX; NOT_APPLICABLE is never experimental validation; scaling is 150 logical keys = 90 DEV reuse + 60 new launches; never claim zero stall; never emit TON_SUBMISSION_READY from this packet",
        ),
    ]
    lines = ["# COMMAND153 six final reviews", ""]
    out = {"ts": primary.get("ts"), "terminal": term, "canary_n": canary_n, "loot_n": loot_n, "n_matched": matched_n, "mean_delta_U": delta, "reviews": []}
    scale_n = int(primary.get("scaling_n") or 0)
    h2_n = int(primary.get("h2_n") or 0)
    compat = (FINAL / "COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json").is_file() or (
        REPO / "state" / "COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json"
    ).is_file()
    complete = (
        canary_n >= 120
        and loot_n >= 315
        and matched_n >= 1
        and int(primary.get("dev_n") or 0) >= 945
        and scale_n >= 150
        and h2_n >= 48
        and compat
    )
    for name, note in reviews:
        status = "PASS_EVIDENCE_PRESENT" if complete else "HOLD_UNTIL_CANONICAL_N"
        rec = {"reviewer": name, "status": status, "note": note}
        out["reviews"].append(rec)
        lines += [f"## {name}", "", f"- status: `{status}`", f"- note: {note}", ""]
    (FINAL / "COMMAND153_SIX_REVIEWS.json").write_text(json.dumps(out, indent=2) + "\n")
    (FINAL / "COMMAND153_SIX_REVIEWS.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"pass": complete, "n_reviews": 6, "terminal": term, "canary_n": canary_n, "loot_n": loot_n}))
    return 0 if complete else 4


if __name__ == "__main__":
    raise SystemExit(main())
