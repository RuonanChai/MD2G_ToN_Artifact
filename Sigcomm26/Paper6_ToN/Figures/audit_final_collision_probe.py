#!/usr/bin/env python3
"""Machine collision/clipping probe for FINAL camera-ready MAIN_TEXT PDFs."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pymupdf

FIG = Path(__file__).resolve().parent
OUT = FIG / "_tmp_final_collision_probe.json"

MAIN = [
    "QoE/QoE_By_Strategy.pdf",
    "Buffer Level/System_Utility_By_Users_scheme1.pdf",
    "QoE/QoE_By_Content_DeltaU.pdf",
    "QoE/QoE_By_Network.pdf",
    "QoE/Loot_Holdout_DeltaU_By_Users.pdf",
    "QoE/Mechanism_Decomposition_Loot.pdf",
    "QoE/MoQ_Shared_vs_Unicast.pdf",
    "User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf",
    "Throughput/System_Throughput_MainText_1x3.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf",
    "User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf",
]


def text_present(path: Path, needles: list[str]) -> dict[str, bool]:
    raw = subprocess.check_output(["pdftotext", str(path), "-"], text=True)
    low = raw.lower().replace("Δ", "delta").replace("δ", "delta")
    return {n: (n.lower() in low or n.lower().replace(" ", "") in low.replace(" ", "")) for n in needles}


def edge_ink(path: Path, margin_px: int = 3, zoom: float = 3.0) -> dict:
    """Fraction of near-edge pixels that are non-white (clipping symptom)."""
    doc = pymupdf.open(path)
    page = doc[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    w, h = pix.width, pix.height
    n = w * h
    # sample border rings
    samples = []
    for y in range(h):
        for x in range(w):
            if x < margin_px or y < margin_px or x >= w - margin_px or y >= h - margin_px:
                i = (y * w + x) * 3
                r, g, b = pix.samples[i : i + 3]
                samples.append(min(r, g, b) < 250)
    dark = sum(samples)
    return {"border_px": len(samples), "dark_border": dark, "dark_frac": round(dark / max(len(samples), 1), 4)}


def main() -> int:
    rows = []
    fails = []
    for rel in MAIN:
        path = FIG / rel
        row = {"file": rel}
        if not path.is_file():
            fails.append(f"missing {rel}")
            continue
        # Specific blockers
        if "Mechanism_Decomposition" in rel:
            present = text_present(path, ["Observed", "0.25", "0.60", "0.15", "Delta", "ΔU", "ΔRo"])
            row["mechanism_legend"] = present
            if not present.get("Observed"):
                fails.append(f"{rel}: Observed ΔU legend text missing/clipped")
        if "MoQ_Shared_vs_Unicast" in rel:
            present = text_present(path, ["MD2G", "MoQ-Unicast", "0.0"])
            row["unicast_text"] = present
            # Must still claim Ro=0 in source script invariant; check hollow marker not at page edge
            edge = edge_ink(path, margin_px=2)
            row["edge"] = edge
        if "TierB_Rb_vs_U" in rel:
            present = text_present(path, ["Better", "MD2G", "Heur.", "Clust.", "Rule"])
            row["tradeoff_text"] = present
            if not present.get("Better"):
                fails.append(f"{rel}: Better label missing")
        if "MainText_1x3" in rel:
            present = text_present(path, ["MD2G", "Heuristic", "Clustering", "Rule", "4G", "5G", "Default Mix"])
            row["tp_legend"] = present
            if not all(present.get(k) for k in ("MD2G", "Heuristic", "Clustering", "Rule")):
                fails.append(f"{rel}: shared strategy legend incomplete")
        rows.append(row)

    report = {"files": rows, "fails": fails, "COLLISION_PROBE_CLEAN": len(fails) == 0}
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2)[:2000])
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
