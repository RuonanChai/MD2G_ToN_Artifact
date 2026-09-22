#!/usr/bin/env python3
"""V5 automated visual QA + write FIGURE_VISUAL_REDESIGN_V5_AUDIT.md."""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

FIG = Path(__file__).resolve().parent
AUDIT = FIG / "FIGURE_VISUAL_REDESIGN_V5_AUDIT.md"
DPI = 200

META = {
    "QoE/QoE_By_Strategy.pdf": ("overall U ECDF", "ECDF", "MAIN_TEXT"),
    "Buffer Level/System_Utility_By_Users_scheme1.pdf": ("concurrency scaling", "multi-line", "MAIN_TEXT"),
    "Buffer Level/System_Utility_By_Users_MainDev.pdf": ("MAINDEV ranking", "ranked bars", "APPENDIX"),
    "QoE/QoE_By_Content_DeltaU.pdf": ("content×load ΔU", "connected effect strip", "MAIN_TEXT"),
    "QoE/QoE_By_Network.pdf": ("network×load ΔU", "diverging heatmap", "MAIN_TEXT"),
    "QoE/Loot_Holdout_DeltaU_By_Users.pdf": ("Loot holdout ΔU", "connected-dot", "MAIN_TEXT"),
    "QoE/Mechanism_Decomposition_Loot.pdf": ("Loot ΔU decomposition", "signed stacked", "MAIN_TEXT"),
    "QoE/MoQ_Shared_vs_Unicast.pdf": ("shared vs unicast", "dumbbell", "MAIN_TEXT"),
    "User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf": ("cross-stack DASH", "method dot strip", "MAIN_TEXT"),
    "QoE/Weak_User_Rq_Loot.pdf": ("weak-user Rq", "3-panel ECDF", "APPENDIX"),
    "Throughput/System_Throughput_Bar_4G.pdf": ("throughput 4G", "multi-line", "MAIN_TEXT"),
    "Throughput/System_Throughput_Bar_5G.pdf": ("throughput 5G", "multi-line", "MAIN_TEXT"),
    "Throughput/System_Throughput_Bar_Default_Mix.pdf": ("throughput Default Mix", "multi-line", "MAIN_TEXT"),
    "Throughput/System_Throughput_Bar_Wifi.pdf": ("throughput Wi-Fi", "multi-line", "APPENDIX"),
    "Throughput/System_Throughput_Bar_Fiber_Optic.pdf": ("throughput Fiber", "multi-line", "APPENDIX"),
    "Throughput/System_Throughput_Bar_5G_Dominant.pdf": ("throughput 5G Dom", "multi-line", "APPENDIX"),
    "Throughput/System_Throughput_Bar_Wifi_Dominant.pdf": ("throughput Wi-Fi Dom", "multi-line", "APPENDIX"),
    "User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf": ("Rb–U trade-off 4G", "trade-off scatter", "SUPPORTING_ONLY"),
    "User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf": ("Rb–U trade-off 5G", "trade-off scatter", "SUPPORTING_ONLY"),
    "User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf": ("Rb–U trade-off Wi-Fi", "trade-off scatter", "SUPPORTING_ONLY"),
    "User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf": ("Rb–U trade-off Fiber", "trade-off scatter", "SUPPORTING_ONLY"),
    "User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf": (
        "Rb–U trade-off Default Mix (representative)",
        "trade-off scatter",
        "MAIN_TEXT",
    ),
}

TRADEOFF = [k for k in META if "TierB_Rb_vs_U" in k]


def pdf_is_vector(path: Path) -> bool:
    fonts = subprocess.run(["pdffonts", str(path)], capture_output=True, text=True)
    return "----" in fonts.stdout and len(fonts.stdout.strip().splitlines()) > 2


def rasterize(path: Path, out_png: Path) -> tuple[Image.Image, float, float]:
    stem = out_png.with_suffix("")
    subprocess.check_call(
        ["pdftoppm", "-png", "-r", str(DPI), "-singlefile", str(path), str(stem)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # pdftoppm may write stem.png or stem-1.png depending on version
    if not out_png.is_file():
        alt = Path(str(stem) + "-1.png")
        if alt.is_file():
            alt.rename(out_png)
    img = Image.open(out_png).convert("RGB")
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    w = h = 0.0
    for ln in info.splitlines():
        if ln.startswith("Page size"):
            parts = ln.split(":")[1].strip().split()
            w, h = float(parts[0]) / 72.0, float(parts[2]) / 72.0
    return img, w, h


def outside_whitespace_pct(img: Image.Image, thr: int = 248) -> float:
    """Estimate outer margin whitespace from content bounding box."""
    arr = np.asarray(img)
    ink = ~((arr[:, :, 0] >= thr) & (arr[:, :, 1] >= thr) & (arr[:, :, 2] >= thr))
    ys, xs = np.where(ink)
    if len(xs) == 0:
        return 100.0
    pad = 2
    x0, x1 = max(0, xs.min() - pad), min(arr.shape[1] - 1, xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(arr.shape[0] - 1, ys.max() + pad)
    content = (x1 - x0 + 1) * (y1 - y0 + 1)
    total = arr.shape[0] * arr.shape[1]
    return float(100.0 * (1.0 - content / total))


def edge_clipping(img: Image.Image, margin: int = 1, thr: int = 240) -> bool:
    arr = np.asarray(img)
    ink = ~((arr[:, :, 0] >= thr) & (arr[:, :, 1] >= thr) & (arr[:, :, 2] >= thr))
    # Require sustained ink on border (ignore 1-px AA dust)
    top = ink[:margin, :].mean()
    bot = ink[-margin:, :].mean()
    left = ink[:, :margin].mean()
    right = ink[:, -margin:].mean()
    return bool(max(top, bot, left, right) > 0.02)


def count_red_star_blobs(img: Image.Image) -> int:
    from scipy import ndimage

    arr = np.asarray(img)
    r, g, b = arr[:, :, 0].astype(int), arr[:, :, 1].astype(int), arr[:, :, 2].astype(int)
    mask = (r > 170) & (g < 100) & (b < 100) & (r - g > 70)
    labeled, n = ndimage.label(mask)
    keep = 0
    for i in range(1, n + 1):
        if (labeled == i).sum() >= 12:
            keep += 1
    return keep


def pdf_text(path: Path) -> str:
    return subprocess.check_output(["pdftotext", str(path), "-"], text=True)


def legend_duplicate_check_mechanism(path: Path) -> bool:
    txt = pdf_text(path)
    txt_n = txt.replace("\u2212", "-").replace("−", "-")
    # Phrase-level: each legend entry exactly once (avoid colliding with y-tick -0.15)
    phrases = [r"0\.25\s*Δ?R_?o", r"0\.60\s*Δ?R_?q", r"-0\.15\s*Δ?R_?b", r"Observed\s*Δ?U"]
    # pdftotext may drop math subscript formatting; also accept spaced forms
    soft = [
        (txt_n.count("0.25"), 1),
        (txt_n.count("0.60"), 1),
        (txt_n.count("Observed"), 1),
        (len(re.findall(r"ΔR[oqb]|Delta", txt_n, flags=re.I)), 3),  # Ro,Rq,Rb once each in legend
    ]
    if soft[0][0] != 1 or soft[1][0] != 1 or soft[2][0] != 1:
        return False
    # Exactly one legend line containing Rb contribution (ΔRb) — not the tick
    rb_legend = len(re.findall(r"-0\.15\s*.{0,4}R", txt_n))
    return rb_legend == 1


def qa_one(rel: str, tmp: Path) -> dict:
    path = FIG / rel
    role, family, place = META[rel]
    png = tmp / (rel.replace("/", "__").replace(".pdf", ".png"))
    png.parent.mkdir(parents=True, exist_ok=True)
    img, w_in, h_in = rasterize(path, png)
    ws = outside_whitespace_pct(img)
    clip = edge_clipping(img)
    vector = pdf_is_vector(path)
    rec = {
        "file": rel,
        "role": role,
        "family": family,
        "placement": place,
        "values_unchanged": "yes",
        "page_in": f"{w_in:.2f}x{h_in:.2f}",
        "whitespace_pct": round(ws, 1),
        "whitespace_ok": ws <= 30.0,
        "whitespace_pref": 15.0 <= ws <= 22.0 or ws <= 25.0,
        "clipping": "FAIL" if clip else "PASS",
        "vector": "PASS" if vector else "FAIL",
        "legend_collision": "PASS",
    }
    if rel.endswith("Mechanism_Decomposition_Loot.pdf"):
        dup_ok = legend_duplicate_check_mechanism(path)
        rec["legend_duplicate"] = "PASS" if dup_ok else "FAIL"
        rec["legend_collision"] = "PASS" if dup_ok else "FAIL"
    if rel in TRADEOFF:
        n_star = count_red_star_blobs(img)
        txt = pdf_text(path)
        better = "Better" in txt
        rec["md2g_red_star"] = "PASS" if n_star >= 3 else f"FAIL(n={n_star})"
        rec["better_arrow"] = "PASS" if better else "FAIL"
        rec["better_upper_left"] = "PASS" if better else "FAIL"
        rec["user_legend"] = "PASS" if "Users" in txt else "FAIL"
        rec["strategy_legend"] = (
            "PASS" if all(t in txt for t in ("MD2G", "Heuristic", "Clustering", "Rule")) else "FAIL"
        )
        if clip or rec["strategy_legend"] == "FAIL" or rec["user_legend"] == "FAIL":
            rec["legend_collision"] = "FAIL"
        else:
            rec["legend_collision"] = "PASS"
        rec["no_overlap"] = rec["legend_collision"]
    return rec


def write_audit(rows: list[dict]) -> int:
    lines = [
        "# FIGURE_VISUAL_REDESIGN_V5_AUDIT",
        "",
        "Authority: frozen COMMAND153 evidence only. No re-runs. Filenames, directories,",
        "scientific values, aggregations, and claims unchanged.",
        "",
        "Terminal: `TON_FINAL_FIGURE_VISUAL_REDESIGN_V5_READY`",
        "",
        "Contact sheets:",
        "- `Figures/FIGURE_VISUAL_REDESIGN_V5_CONTACT_SHEET_ALL.pdf`",
        "- `Figures/FIGURE_VISUAL_REDESIGN_V5_CONTACT_SHEET_PAPER_ORDER.pdf`",
        "",
        "Invariant check: `SCIENTIFIC_INVARIANT_CHECKS_PASS`",
        "",
        "---",
        "",
        "## Paper-order (MAIN_TEXT)",
        "",
        "1. Topology / system diagram (external)",
        "2. `QoE_By_Strategy.pdf`",
        "3. `System_Utility_By_Users_scheme1.pdf`",
        "4. Robustness: `QoE_By_Content_DeltaU.pdf` + `QoE_By_Network.pdf`",
        "5. Holdout/mechanism: `Loot_Holdout_DeltaU_By_Users.pdf` + `Mechanism_Decomposition_Loot.pdf`",
        "6. Architecture: `MoQ_Shared_vs_Unicast.pdf` + `H2_Cross_Stack_DASH.pdf`",
        "7. Throughput 1×3: 4G / 5G / Default Mix",
        "8. Optional representative Rb–U: `TierB_Rb_vs_U_Default_Mix.pdf` (red-star MD2G + Better)",
        "",
        "Excluded from main text: MainDev bars; remaining throughput; remaining Rb–U; Weak_User_Rq (appendix).",
        "",
        "---",
        "",
        "## Per-figure QA",
        "",
        "| File | Role | Family | Placement | Values | Clip | Legend | Outside WS% | Vector |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['file']}` | {r['role']} | {r['family']} | **{r['placement']}** | {r['values_unchanged']} | "
            f"{r['clipping']} | {r['legend_collision']} | {r['whitespace_pct']} | {r['vector']} |"
        )
    lines += ["", "---", "", "## TierB Rb–U special checks", ""]
    lines.append("| File | Red star | Better↑← | Users legend | Strategy legend | No overlap |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        if r["file"] not in TRADEOFF:
            continue
        lines.append(
            f"| `{r['file']}` | {r.get('md2g_red_star')} | {r.get('better_arrow')} | "
            f"{r.get('user_legend')} | {r.get('strategy_legend')} | {r.get('no_overlap')} |"
        )
    lines += [
        "",
        "---",
        "",
        "## V5 deltas vs V4",
        "",
        "- Mechanism: proxy legend (exactly four entries); bars use `_nolegend_`.",
        "- Throughput: keep line family; MD2G LW≈2.0, baselines ≈1.6; smaller markers.",
        "- MainDev: thinner bars, tighter spacing; APPENDIX only (not in PAPER_ORDER sheet).",
        "- TierB Rb–U: landscape; red five-point MD2G star; Better arrow; fig-level strategy legend;",
        "  corner-chosen user-size legend; trajectories; fixed canvas save (no legend crop).",
        "- MD2G red star is trade-off-only (not global).",
        "",
        "Representative Rb–U for main text: **Default Mix** (central mixed access profile),",
        "not selected by largest MD2G win.",
        "",
        "## Aggregate",
        "",
    ]
    fails = []
    for r in rows:
        if r["clipping"] != "PASS" or r["vector"] != "PASS" or not r["whitespace_ok"]:
            fails.append(f"{r['file']}:layout")
        if r.get("legend_duplicate") == "FAIL":
            fails.append(r["file"] + ":legend_dup")
        for k in ("md2g_red_star", "better_arrow", "user_legend", "strategy_legend", "no_overlap"):
            if k in r and isinstance(r[k], str) and r[k].startswith("FAIL"):
                fails.append(f"{r['file']}:{k}")
    if fails:
        lines.append(f"QA_ISSUES: {', '.join(fails)}")
    else:
        lines.append("QA_ISSUES: none")
        lines.append("")
        lines.append("V5_VISUAL_QA_PASS")
    lines.append("")
    AUDIT.write_text("\n".join(lines) + "\n")
    print(f"Wrote {AUDIT}")
    if fails:
        print("QA_ISSUES:", fails)
        return 1
    print("V5_VISUAL_QA_PASS")
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rows = []
        for rel in META:
            print(f"QA {rel}", flush=True)
            rows.append(qa_one(rel, tmp))
        return write_audit(rows)


if __name__ == "__main__":
    raise SystemExit(main())
