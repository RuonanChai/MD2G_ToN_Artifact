#!/usr/bin/env python3
"""Pair MediaBox + ACM inclusion-size audit. Layout only; no data change."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _fig_compact import PAIR_SIZE  # noqa: E402

PAIRS = [
    (
        1,
        ROOT / "QoE/QoE_By_Strategy.pdf",
        ROOT / "Buffer Level/System_Utility_By_Users_scheme1.pdf",
    ),
    (
        2,
        ROOT / "QoE/QoE_By_Content_DeltaU.pdf",
        ROOT / "QoE/QoE_By_Network.pdf",
    ),
    (
        3,
        ROOT / "QoE/Loot_Holdout_DeltaU_By_Users.pdf",
        ROOT / "QoE/Mechanism_Decomposition_Loot.pdf",
    ),
    (
        4,
        ROOT / "QoE/MoQ_Shared_vs_Unicast.pdf",
        ROOT / "User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf",
    ),
]


def pdf_wh(path: Path) -> tuple[float, float]:
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    for ln in info.splitlines():
        if ln.startswith("Page size"):
            p = ln.split(":")[1].strip().split()
            return float(p[0]) / 72.0, float(p[2]) / 72.0
    raise SystemExit(f"NO_PAGE_SIZE {path}")


def main() -> int:
    fails = []
    for pid, a, b in PAIRS:
        wa, ha = pdf_wh(a)
        wb, hb = pdf_wh(b)
        dw = abs(wa - wb) / max(wa, wb) * 100
        dh = abs(ha - hb) / max(ha, hb) * 100
        print(
            f"P{pid} {a.name} {wa:.4f}x{ha:.4f} | {b.name} {wb:.4f}x{hb:.4f} "
            f"dw={dw:.3f}% dh={dh:.3f}%"
        )
        if dw > 1.5 or dh > 1.5:
            fails.append(f"P{pid} bbox dw={dw:.2f}% dh={dh:.2f}%")
        tw, th = PAIR_SIZE[pid]
        for name, w, h in ((a.name, wa, ha), (b.name, wb, hb)):
            if abs(w - tw) / tw > 0.015:
                fails.append(f"{name} width {w:.4f} vs {tw}")
            if abs(h - th) / th > 0.015:
                fails.append(f"{name} height {h:.4f} vs {th}")
    if fails:
        print("PAIR_HEIGHT_ALIGNMENT_FAIL")
        for f in fails:
            print(" ", f)
        return 1
    print("PAIR_HEIGHT_ALIGNMENT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
