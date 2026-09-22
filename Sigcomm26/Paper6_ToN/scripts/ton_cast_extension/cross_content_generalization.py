#!/usr/bin/env python3
"""TASK 5: Four-content generalization table from frozen COMMAND153 artifacts. No rerun."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _common import (  # noqa: E402
    RESULTS,
    TON,
    STRAT_LABEL,
    load_dev_rows,
    load_loot_rows,
    mean,
    write_csv,
)

OUT = RESULTS
SEEN = ("redandblack", "longdress")
UNSEEN = ("soldier", "loot")
STRATS = ("MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT", "MOQ_UNICAST_COMPONENT")
CONTENT_LABEL = {
    "redandblack": "Red-and-Black",
    "longdress": "Longdress",
    "soldier": "Soldier",
    "loot": "Loot",
}


def decoded_completion(r: dict) -> float:
    cc = r.get("component_completion_fraction") or {}
    rec = r.get("receiver_set_size") or {}
    num = den = 0.0
    for c, st in cc.items():
        n_req = float(st.get("n_receivers") or rec.get(c) or 0)
        n_ok = float(st.get("n_complete_dump_gt_64") or 0)
        num += n_ok
        den += n_req
    return num / den if den else 0.0


def main() -> int:
    rows = [r for r in load_dev_rows() + load_loot_rows() if r.get("strategy") in STRATS]
    summary = []
    for content in ("redandblack", "longdress", "soldier", "loot"):
        split = "seen" if content in SEEN else "unseen"
        for strat in STRATS:
            sub = [r for r in rows if r["content"] == content and r["strategy"] == strat]
            if not sub:
                continue
            delays = [r.get("stall_last") for r in sub if r.get("stall_last") is not None]
            summary.append(
                {
                    "content": CONTENT_LABEL[content],
                    "split": split,
                    "strategy": STRAT_LABEL[strat],
                    "n": len(sub),
                    "U": mean(r["U"] for r in sub),
                    "decoded_completion": mean(decoded_completion(r) for r in sub),
                    "Rq": mean(r["Rq"] for r in sub),
                    "Ro": mean(r["Ro_component"] for r in sub),
                    "bandwidth_B_shared": mean(float(r.get("B_shared") or 0) for r in sub),
                    "stall_last_s": mean(delays) if delays else "",
                    "p99_delay": "NOT_IN_FINAL_CLAIM_CONTRACT",
                }
            )
    write_csv(OUT / "cross_content_cells_summary.csv", summary)
    tex = [
        r"% Seen = teacher/student training contents. Unseen = Soldier (MAINDEV, unread in training) + Loot holdout.",
        r"\begin{tabular}{llrrrrr}",
        r"\hline",
        r"Split & Content & Strategy & $U$ & Completion & $R_o$ & $B_{\mathrm{shared}}$ \\",
        r"\hline",
    ]
    for r in summary:
        tex.append(
            f"{r['split']} & {r['content']} & {r['strategy']} & {r['U']:.3f} & "
            f"{r['decoded_completion']:.3f} & {r['Ro']:.3f} & {r['bandwidth_B_shared']:.3e} \\\\"
        )
    tex += [r"\hline", r"\end{tabular}", ""]
    (OUT / "cross_content_generalization.tex").write_text("\n".join(tex))
    print(f"Wrote {OUT / 'cross_content_generalization.tex'} n={len(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
