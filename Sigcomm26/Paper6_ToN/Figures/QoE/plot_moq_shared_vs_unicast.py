#!/usr/bin/env python3
"""Shared MoQ (MD2G) vs MoQ Unicast — ACM pair-4 compact.

Semantic: MOQ_UNICAST_COMPONENT (Ro=0), NOT DASH/HTTP. Filename kept.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import pair_fig, pair_legend, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import load_primary_stats, require_frozen_evidence  # noqa: E402
from _fig_v3 import style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "MoQ_Shared_vs_Unicast.pdf"
METRICS = [
    ("U", r"$U$"),
    ("Rq", "Rq"),
    ("Ro_component", "Ro"),
    ("Rb", "Rb"),
]
C_MD2G = "#0072B2"
C_UNI = "#4D4D4D"


def main() -> int:
    require_frozen_evidence()
    loot = load_primary_stats()["loot_by_strategy"]
    md = loot["MD2G_COMPONENT"]
    uni = loot["MOQ_UNICAST_COMPONENT"]
    if float(uni["Ro_component"]) != 0.0:
        raise SystemExit("UNICAST_RO_NOT_ZERO")

    fig, ax = pair_fig(4)
    ys = list(range(len(METRICS)))[::-1]
    for y, (key, _lab) in zip(ys, METRICS):
        a = float(md[key])
        b = float(uni[key])
        ax.plot([a, b], [y, y], color="0.72", linewidth=1.05, zorder=2, solid_capstyle="round")
        ax.scatter([a], [y], s=28, c=C_MD2G, marker="o", edgecolors="0.1", linewidths=0.35, zorder=4)
        ax.scatter(
            [b], [y], s=28, facecolors="white", edgecolors=C_UNI,
            linewidths=1.15, marker="v", zorder=4, clip_on=False,
        )
    ax.set_yticks(ys)
    ax.set_yticklabels([lab for _k, lab in METRICS], fontsize=9.0)
    ax.set_xlim(-0.08, 1.04)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylim(-0.45, 3.45)
    place_xy_labels(ax, "Loot mean", "")
    ax.set_ylabel("")
    style_ax(ax, ygrid=False, xgrid=True)
    h1 = ax.scatter([], [], s=28, c=C_MD2G, marker="o", edgecolors="0.1", label="MD2G")
    h2 = ax.scatter(
        [], [], s=28, facecolors="white", edgecolors=C_UNI, linewidths=1.15,
        marker="v", label="Unicast",
    )
    pair_legend(fig, [h1, h2], pair_id=4, ncol=2, handlelength=0.9)
    save_pair_pdf(fig, OUT, 4)
    print(
        f"Wrote {OUT} strategy=MOQ_UNICAST_COMPONENT "
        f"Ro={uni['Ro_component']} U_md={md['U']} U_uni={uni['U']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
