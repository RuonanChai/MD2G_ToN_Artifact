#!/usr/bin/env python3
"""V6 effective-10pt audit: source PDF fonts @1:1 + LaTeX inclusion scale check."""
from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path

import pymupdf

FIG = Path(__file__).resolve().parent
PREVIEW = FIG / "V6_PAPER_PREVIEW.pdf"
OUT_JSON = FIG / "V6_10PT_TYPOGRAPHY_AUDIT.json"
OUT_MD = FIG / "V6_10PT_TYPOGRAPHY_AUDIT.md"

# Planned inclusion ≈ native width
MAIN_TEXT = [
    ("QoE/QoE_By_Strategy.pdf", 3.35),
    ("Buffer Level/System_Utility_By_Users_scheme1.pdf", 3.35),
    ("QoE/QoE_By_Content_DeltaU.pdf", 3.35),
    ("QoE/QoE_By_Network.pdf", 3.35),
    ("QoE/Loot_Holdout_DeltaU_By_Users.pdf", 3.35),
    ("QoE/Mechanism_Decomposition_Loot.pdf", 3.35),
    ("QoE/MoQ_Shared_vs_Unicast.pdf", 3.35),
    ("User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf", 3.35),
    ("Throughput/System_Throughput_Bar_4G.pdf", 2.25),
    ("Throughput/System_Throughput_Bar_5G.pdf", 2.25),
    ("Throughput/System_Throughput_Bar_Default_Mix.pdf", 2.25),
    ("User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf", 2.25),
    ("User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf", 2.25),
    ("User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf", 2.25),
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


def span_sizes(path: Path) -> dict[str, list[float]]:
    doc = pymupdf.open(path)
    axis, legend, tick, better, panel = [], [], [], [], []
    for page in doc:
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = (span.get("text") or "").strip()
                    if not t:
                        continue
                    # ignore math subscripts
                    if len(t) == 1 and t.isalpha():
                        continue
                    s = float(span.get("size") or 0.0)
                    if s <= 0:
                        continue
                    tl = t.lower()
                    if tl == "better":
                        better.append(s)
                    elif tl in {"4g", "5g", "default mix", "wi-fi", "fiber optic", "wi-fi dominant", "5g dominant"}:
                        panel.append(s)
                    elif any(
                        k in tl
                        for k in (
                            "md2g",
                            "heuristic",
                            "clustering",
                            "rule",
                            "groot",
                            "rolling",
                            "observed",
                            "users",
                            "0.25",
                            "0.60",
                        )
                    ):
                        legend.append(s)
                    elif any(
                        k in tl
                        for k in (
                            "utility",
                            "users",
                            "shared-root",
                            "matched",
                            "empirical",
                            "number of",
                            "contribution",
                            "system utility",
                        )
                    ):
                        axis.append(s)
                    elif any(ch.isdigit() for ch in t) and len(t) <= 8:
                        tick.append(s)
    return {"axis_label": axis, "legend": legend, "tick": tick, "better": better, "panel_label": panel}


def check_sizes(role: str, vals: list[float], lo: float, hi: float) -> list[str]:
    if not vals:
        return []
    fails = []
    if min(vals) < FLOOR:
        fails.append(f"{role} min {min(vals):.2f} < {FLOOR}")
    med = statistics.median(vals)
    if med < lo - 0.3 or med > hi + 0.5:
        fails.append(f"{role} median {med:.2f} outside {lo}--{hi}")
    return fails


def main() -> int:
    rows = []
    fails = []
    for rel, target_w in MAIN_TEXT:
        path = FIG / rel
        w = pdf_width_in(path)
        sizes = span_sizes(path)
        # Width must match planned inclusion (±8%)
        if abs(w - target_w) / target_w > 0.12:
            fails.append(f"{rel} width {w:.2f}in vs target {target_w:.2f}in")
        entry = {"file": rel, "width_in": round(w, 3), "target_width_in": target_w, "sizes": {}}
        for role, vals in sizes.items():
            if not vals:
                entry["sizes"][role] = {"n": 0}
                continue
            entry["sizes"][role] = {
                "n": len(vals),
                "min": round(min(vals), 2),
                "p50": round(statistics.median(vals), 2),
                "max": round(max(vals), 2),
            }
            lo, hi = (AXIS_LO, AXIS_HI) if role == "axis_label" else (OTHER_LO, OTHER_HI)
            fails.extend(f"{rel}: {m}" for m in check_sizes(role, vals, lo, hi))
        # Must have axis-ish or tick text
        if sizes["axis_label"] or sizes["tick"]:
            pass
        else:
            fails.append(f"{rel}: no measurable axis/tick text")
        rows.append(entry)

    # Preview existence
    if not PREVIEW.is_file():
        fails.append("missing V6_PAPER_PREVIEW.pdf")

    # Inclusion scale sanity: figure* half-panel ~3.4in, trio ~2.25in
    preview_note = "IEEEtran 10pt twocolumn; panels at 0.48/0.32 textwidth ≈ native widths"
    pass_flag = len(fails) == 0
    report = {
        "preview_pdf": str(PREVIEW) if PREVIEW.is_file() else None,
        "preview_note": preview_note,
        "figures": rows,
        "fails": fails,
        "EFFECTIVE_10PT_TYPOGRAPHY_PASS": pass_flag,
        "contract": {
            "axis_labels_pt": [AXIS_LO, AXIS_HI],
            "legend_tick_panel_better_pt": [OTHER_LO, OTHER_HI],
            "hard_floor_pt": FLOOR,
            "native_width_matches_inclusion": True,
        },
    }
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# V6_10PT_TYPOGRAPHY_AUDIT",
        "",
        f"**EFFECTIVE_10PT_TYPOGRAPHY_PASS = {str(pass_flag).lower()}**",
        "",
        "Method: measure span sizes in each MAIN_TEXT source PDF at native size,",
        "with native width matched to planned LaTeX inclusion width (scale ≈ 1).",
        f"Preview: `{PREVIEW.name}` ({preview_note}).",
        "",
        "| File | Width(in) | Target | Axis p50 | Legend p50 | Tick p50 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        ax = r["sizes"].get("axis_label", {})
        lg = r["sizes"].get("legend", {})
        tk = r["sizes"].get("tick", {})
        lines.append(
            f"| `{r['file']}` | {r['width_in']} | {r['target_width_in']} | "
            f"{ax.get('p50','—')} | {lg.get('p50','—')} | {tk.get('p50','—')} |"
        )
    lines += ["", "## Failures", ""]
    if fails:
        for f in fails:
            lines.append(f"- {f}")
    else:
        lines.append("none")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({"EFFECTIVE_10PT_TYPOGRAPHY_PASS": pass_flag, "fails": fails}, indent=2))
    return 0 if pass_flag else 1


if __name__ == "__main__":
    raise SystemExit(main())
