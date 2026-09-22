#!/usr/bin/env python3
"""Development-matrix mechanism decomposition.

Same stacked-contribution geometry as the Loot pair panel.
Source is dest.json (3 contents × 7 nets × 3 seeds = 63 blocks / load).
Does not overwrite Mechanism_Decomposition_Loot.pdf.
Does not change the contribution formula (0.25 ΔRo / 0.60 ΔRq / −0.15 ΔRb).
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import complete_yticks, pair_fig, pair_legend, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import load_rows, match_same_substrate_blocks, require_frozen_evidence  # noqa: E402
from _fig_v3 import MECH, pad_lim, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "Mechanism_Decomposition_Development.pdf"
USER_COUNTS = [20, 60, 100]
TOL = 1e-3
# Frozen Table-7 contribution digits (development). ΔU column in the
# current PDF mixes Loot means; this figure uses dest.json only.
FROZEN_CONTRIB = {
    20: (0.0005, -0.1470, 0.0097),
    60: (0.0003, 0.0783, -0.0001),
    100: (0.0002, 0.1033, 0.0023),
}


def main() -> int:
    require_frozen_evidence()
    blocks = match_same_substrate_blocks(load_rows("dev.json"))
    means_c = {"Ro": [], "Rq": [], "Rb": []}
    means_du = []
    for u in USER_COUNTS:
        rows = [b for b in blocks if int(b["users"]) == u and "contrib_Ro" in b]
        if len(rows) != 63:
            raise SystemExit(f"MISSING_DEV_MECH u{u} n={len(rows)} want 63")
        c_ro = sum(b["contrib_Ro"] for b in rows) / len(rows)
        c_rq = sum(b["contrib_Rq"] for b in rows) / len(rows)
        c_rb = sum(b["contrib_Rb"] for b in rows) / len(rows)
        du = sum(b["delta_U"] for b in rows) / len(rows)
        if abs((c_ro + c_rq + c_rb) - du) > TOL:
            raise SystemExit(f"MECH_MISMATCH u{u} recon={c_ro+c_rq+c_rb} du={du}")
        want = FROZEN_CONTRIB[u]
        if abs(c_ro - want[0]) > 5e-4 or abs(c_rq - want[1]) > 5e-4 or abs(c_rb - want[2]) > 5e-4:
            raise SystemExit(f"FROZEN_CONTRIB_DRIFT u{u} got={(c_ro, c_rq, c_rb)} want={want}")
        means_c["Ro"].append(c_ro)
        means_c["Rq"].append(c_rq)
        means_c["Rb"].append(c_rb)
        means_du.append(du)

    fig, ax = pair_fig(3)
    plt.rcParams.update(
        {
            "font.size": 9.0,
            "axes.labelsize": 9.5,
            "xtick.labelsize": 9.0,
            "ytick.labelsize": 9.0,
            "legend.fontsize": 9.0,
        }
    )
    x = np.arange(len(USER_COUNTS))
    width = 0.52
    ax.axhline(0.0, color="0.25", linewidth=0.7, zorder=2)
    pos_bottom = np.zeros(len(USER_COUNTS))
    neg_bottom = np.zeros(len(USER_COUNTS))
    for name, color in (("Ro", MECH["Ro"]), ("Rq", MECH["Rq"]), ("Rb", MECH["Rb"])):
        vals = np.asarray(means_c[name], dtype=float)
        for i, v in enumerate(vals):
            if v >= 0:
                ax.bar(x[i], v, width=width, bottom=pos_bottom[i], color=color, edgecolor="0.25", linewidth=0.25, zorder=3)
                pos_bottom[i] += v
            else:
                ax.bar(x[i], v, width=width, bottom=neg_bottom[i], color=color, edgecolor="0.25", linewidth=0.25, zorder=3)
                neg_bottom[i] += v
    ax.scatter(
        x, means_du, s=22, c=MECH["tot"], marker="D",
        edgecolors="0.15", linewidths=0.3, zorder=5,
    )
    ax.set_xticks(x)
    ax.set_xticklabels([str(u) for u in USER_COUNTS])
    place_xy_labels(ax, "Users", r"$\Delta U$")
    ax.tick_params(axis="both", labelsize=9.0)
    ax.yaxis.set_label_coords(-0.36, 0.5)
    ymin = min(float(min(neg_bottom)), min(means_du))
    ymax = max(float(max(pos_bottom)), max(means_du))
    ax.set_ylim(*pad_lim(ymin, ymax, frac=0.08, include_zero=True))
    style_ax(ax)
    complete_yticks(ax, 0.05)
    ax.tick_params(axis="y", labelsize=9.0, pad=1.0)
    handles = [
        Patch(facecolor=MECH["Ro"], edgecolor="0.25", linewidth=0.25, label=r"$0.25\Delta Ro$"),
        Patch(facecolor=MECH["Rq"], edgecolor="0.25", linewidth=0.25, label=r"$0.60\Delta Rq$"),
        Patch(facecolor=MECH["Rb"], edgecolor="0.25", linewidth=0.25, label=r"$-0.15\Delta Rb$"),
        Line2D(
            [0], [0], marker="D", color="none", markerfacecolor=MECH["tot"],
            markeredgecolor="0.15", markeredgewidth=0.3, markersize=4.5, label=r"$\Delta U$",
        ),
    ]
    pair_legend(fig, handles, pair_id=3, ncol=2, fontsize=9.0, handlelength=0.80, columnspacing=0.30)
    save_pair_pdf(fig, OUT, 3)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
