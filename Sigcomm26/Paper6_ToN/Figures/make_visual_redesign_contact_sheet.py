#!/usr/bin/env python3
"""Diagnostic contact sheet only. Does not replace any paper figure."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.image import imread

FIG = Path(__file__).resolve().parent
OUT = FIG / "FIGURE_VISUAL_REDESIGN_CONTACT_SHEET.pdf"
TMP = Path("/tmp/ton_fig_qa")

PANELS = [
    ("QoE/QoE_By_Strategy.pdf", "A  box+mean"),
    ("Buffer Level/System_Utility_By_Users_scheme1.pdf", "B  scaling lines"),
    ("Buffer Level/System_Utility_By_Users_MainDev.pdf", "C  MAINDEV slope"),
    ("QoE/QoE_By_Content_DeltaU.pdf", "D  content forest"),
    ("QoE/QoE_By_Network.pdf", "E  net×load heatmap"),
    ("QoE/Loot_Holdout_DeltaU_By_Users.pdf", "F  Loot ΔU"),
    ("QoE/Mechanism_Decomposition_Loot.pdf", "G  signed decomp"),
    ("QoE/MoQ_Shared_vs_Unicast.pdf", "H  architecture dumbbell"),
    ("User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf", "I  cross-stack lines"),
    ("Throughput/System_Throughput_Bar_4G.pdf", "J  TX 4G lines"),
    ("Throughput/System_Throughput_Bar_5G.pdf", "J  TX 5G lines"),
    ("Throughput/System_Throughput_Bar_Default_Mix.pdf", "J  TX Mix lines"),
    ("QoE/Weak_User_Rq_Loot.pdf", "K  weak-user Rq"),
    ("User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf", "L  Rb–U scatter"),
]


def raster(pdf: Path, dest_png: Path) -> None:
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pdftoppm", "-png", "-r", "110", "-singlefile", str(pdf), str(dest_png.with_suffix(""))]
    subprocess.check_call(cmd)


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    pngs = []
    for rel, title in PANELS:
        pdf = FIG / rel
        if not pdf.is_file():
            raise SystemExit(f"MISSING {rel}")
        png = TMP / (rel.replace("/", "_").replace(".pdf", ".png"))
        raster(pdf, png)
        pngs.append((png, title, rel))

    n = len(pngs)
    ncols = 3
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(11.0, 3.15 * nrows))
    axes = axes.ravel()
    for i, ax in enumerate(axes):
        ax.set_axis_off()
        if i >= n:
            continue
        png, title, rel = pngs[i]
        ax.imshow(imread(str(png)))
        ax.set_title(f"{title}\n{rel}", fontsize=7.5, pad=4)
    fig.suptitle(
        "Diagnostic contact sheet — not a paper figure",
        fontsize=11,
        y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(OUT, format="pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
