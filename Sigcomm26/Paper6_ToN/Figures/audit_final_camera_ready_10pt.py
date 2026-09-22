#!/usr/bin/env python3
"""Effective 10pt audit on FINAL_CAMERA_READY_FIGURE_PREVIEW.pdf + native MAIN panels."""
from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path

import pymupdf

FIG = Path(__file__).resolve().parent
PREVIEW = FIG / "FINAL_CAMERA_READY_FIGURE_PREVIEW.pdf"
OUT_JSON = FIG / "_tmp_final_10pt_measure.json"

# Native widths matched to planned inclusion (scale ≈ 1)
MAIN_NATIVE = [
    ("QoE/QoE_By_Strategy.pdf", 3.35),
    ("Buffer Level/System_Utility_By_Users_scheme1.pdf", 3.35),
    ("QoE/QoE_By_Content_DeltaU.pdf", 3.35),
    ("QoE/QoE_By_Network.pdf", 3.35),
    ("QoE/Loot_Holdout_DeltaU_By_Users.pdf", 3.35),
    ("QoE/Mechanism_Decomposition_Loot.pdf", 3.35),
    ("QoE/MoQ_Shared_vs_Unicast.pdf", 3.35),
    ("User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf", 3.35),
    ("Throughput/System_Throughput_MainText_1x3.pdf", 7.00),
    ("User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf", 2.28),
    ("User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf", 2.28),
    ("User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf", 2.28),
]

FLOOR = 9.0
AXIS_LO, AXIS_HI = 9.5, 10.5
OTHER_LO, OTHER_HI = 9.0, 10.5


def pdf_width_in(path: Path) -> float:
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    for ln in info.splitlines():
        if ln.startswith("Page size"):
            return float(ln.split(":")[1].strip().split()[0]) / 72.0
    raise SystemExit(f"NO_PAGE_SIZE {path}")


def classify_spans(path: Path) -> dict[str, list[float]]:
    doc = pymupdf.open(path)
    buckets = {k: [] for k in ("axis_label", "legend", "tick", "better", "panel_label", "all_important")}
    for page in doc:
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = (span.get("text") or "").strip()
                    if not t:
                        continue
                    if len(t) == 1 and t.isalpha():
                        continue
                    s = float(span.get("size") or 0.0)
                    if s <= 0:
                        continue
                    tl = t.lower()
                    role = None
                    if tl == "better":
                        role = "better"
                    elif tl in {
                        "4g", "5g", "default mix", "wi-fi", "fiber optic",
                        "wi-fi dominant", "5g dominant", "(a) 4g", "(b) 5g", "(c) default mix",
                    } or tl.startswith("(a)") or tl.startswith("(b)") or tl.startswith("(c)"):
                        role = "panel_label"
                    elif any(
                        k in tl
                        for k in (
                            "md2g", "heuristic", "clustering", "rule", "groot", "rolling",
                            "observed", "0.25", "0.60", "-0.15", "heur.", "clust.",
                        )
                    ):
                        role = "legend"
                    elif any(
                        k in tl
                        for k in (
                            "utility", "shared-root", "matched", "empirical",
                            "number of", "contribution", "system utility", "loot holdout",
                        )
                    ):
                        role = "axis_label"
                    elif any(ch.isdigit() for ch in t) and len(t) <= 8:
                        role = "tick"
                    if role:
                        buckets[role].append(s)
                        buckets["all_important"].append(s)
    return buckets


def check(role: str, vals: list[float], lo: float, hi: float) -> list[str]:
    if not vals:
        return []
    fails = []
    if min(vals) < FLOOR:
        fails.append(f"{role} min {min(vals):.2f} < {FLOOR}")
    med = statistics.median(vals)
    if med < lo - 0.35 or med > hi + 0.6:
        fails.append(f"{role} median {med:.2f} outside ~{lo}--{hi}")
    return fails


def measure_preview_figure_fonts() -> dict:
    """Measure effective figure typography AFTER inclusion (LiberationSans = matplotlib)."""
    if not PREVIEW.is_file():
        return {"error": "missing preview"}
    doc = pymupdf.open(PREVIEW)
    fig_sizes: list[float] = []
    fig_roles = {k: [] for k in ("axis_label", "legend", "tick", "better", "panel_label")}
    body_sizes = []
    for page in doc:
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = (span.get("text") or "").strip()
                    s = float(span.get("size") or 0.0)
                    font = span.get("font") or ""
                    if not t or s <= 0:
                        continue
                    if len(t) == 1 and t.isalpha():
                        continue  # math subscripts o/q/b
                    if "Liberation" in font:
                        fig_sizes.append(s)
                        tl = t.lower()
                        if tl == "better":
                            fig_roles["better"].append(s)
                        elif any(k in tl for k in ("md2g", "heuristic", "clustering", "rule", "observed", "0.25", "0.60", "heur", "clust")):
                            fig_roles["legend"].append(s)
                        elif any(k in tl for k in ("utility", "shared-root", "number of", "contribution", "loot holdout", "system utility", "matched", "empirical")):
                            fig_roles["axis_label"].append(s)
                        elif tl in {"4g", "5g", "default mix", "fiber optic", "wi-fi"} or tl.startswith("("):
                            fig_roles["panel_label"].append(s)
                        elif any(ch.isdigit() for ch in t) and len(t) <= 8:
                            fig_roles["tick"].append(s)
                    elif "Nimbus" in font or font.startswith("CM"):
                        body_sizes.append(s)
    fails = []
    if not fig_sizes:
        fails.append("no LiberationSans figure text in preview")
    else:
        if min(fig_sizes) < FLOOR:
            fails.append(f"preview figure min {min(fig_sizes):.2f} < {FLOOR}")
        for role, vals in fig_roles.items():
            lo, hi = (AXIS_LO, AXIS_HI) if role == "axis_label" else (OTHER_LO, OTHER_HI)
            fails.extend(check(f"preview:{role}", vals, lo, hi))
    return {
        "n_figure_spans": len(fig_sizes),
        "figure_min": round(min(fig_sizes), 2) if fig_sizes else None,
        "figure_p50": round(statistics.median(fig_sizes), 2) if fig_sizes else None,
        "figure_max": round(max(fig_sizes), 2) if fig_sizes else None,
        "roles": {
            k: {
                "n": len(v),
                "min": round(min(v), 2) if v else None,
                "p50": round(statistics.median(v), 2) if v else None,
            }
            for k, v in fig_roles.items()
        },
        "fails": fails,
    }


def main() -> int:
    fails = []
    rows = []
    for rel, target_w in MAIN_NATIVE:
        path = FIG / rel
        if not path.is_file():
            fails.append(f"missing {rel}")
            continue
        w = pdf_width_in(path)
        sizes = classify_spans(path)
        if abs(w - target_w) / target_w > 0.14:
            fails.append(f"{rel} width {w:.2f}in vs target {target_w:.2f}in")
        entry = {"file": rel, "width_in": round(w, 3), "target_width_in": target_w, "sizes": {}}
        for role, vals in sizes.items():
            if role == "all_important":
                # exclude already filtered single-letter in classify
                if vals and min(vals) < FLOOR:
                    fails.append(f"{rel}: important text min {min(vals):.2f} < {FLOOR}")
                entry["sizes"][role] = {
                    "n": len(vals),
                    "min": round(min(vals), 2) if vals else None,
                    "p50": round(statistics.median(vals), 2) if vals else None,
                }
                continue
            entry["sizes"][role] = {
                "n": len(vals),
                "min": round(min(vals), 2) if vals else None,
                "p50": round(statistics.median(vals), 2) if vals else None,
                "max": round(max(vals), 2) if vals else None,
            }
            lo, hi = (AXIS_LO, AXIS_HI) if role == "axis_label" else (OTHER_LO, OTHER_HI)
            fails.extend(f"{rel}: {m}" for m in check(role, vals, lo, hi))
        rows.append(entry)

    preview = measure_preview_figure_fonts()
    if preview.get("error"):
        fails.append(preview["error"])
    fails.extend(preview.get("fails") or [])

    report = {
        "preview_pdf": str(PREVIEW) if PREVIEW.is_file() else None,
        "preview_figure_typography": preview,
        "figures": rows,
        "fails": fails,
        "EFFECTIVE_10PT_PASS": len(fails) == 0,
        "contract": {
            "axis_labels_pt": [AXIS_LO, AXIS_HI],
            "legend_tick_panel_better_pt": [OTHER_LO, OTHER_HI],
            "hard_floor_pt": FLOOR,
            "method": "PyMuPDF span sizes on LiberationSans AFTER IEEEtran inclusion; native width≈inclusion ⇒ scale≈1",
        },
    }
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"EFFECTIVE_10PT_PASS": report["EFFECTIVE_10PT_PASS"], "n_fails": len(fails), "fails": fails, "preview_figure_min": preview.get("figure_min"), "preview_figure_p50": preview.get("figure_p50")}, indent=2))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
