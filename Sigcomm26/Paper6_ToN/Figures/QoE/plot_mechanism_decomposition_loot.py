#!/usr/bin/env python3
"""Loot mechanism decomposition — ACM pair-3 compact stacked contributions."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import complete_yticks, pair_fig, pair_legend, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import load_rows, match_same_substrate_blocks, require_frozen_evidence  # noqa: E402
from _fig_v3 import MECH, pad_lim, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "Mechanism_Decomposition_Loot.pdf"
USER_COUNTS = [20, 60, 100]
TOL = 1e-3


def main() -> int:
    require_frozen_evidence()
    blocks = match_same_substrate_blocks(load_rows("loot.json"))
    means_c = {"Ro": [], "Rq": [], "Rb": []}
    means_du = []
    for u in USER_COUNTS:
        rows = [b for b in blocks if int(b["users"]) == u and "contrib_Ro" in b]
        if len(rows) != 21:
            raise SystemExit(f"MISSING_LOOT_MECH u{u} n={len(rows)}")
        c_ro = sum(b["contrib_Ro"] for b in rows) / len(rows)
        c_rq = sum(b["contrib_Rq"] for b in rows) / len(rows)
        c_rb = sum(b["contrib_Rb"] for b in rows) / len(rows)
        du = sum(b["delta_U"] for b in rows) / len(rows)
        if abs((c_ro + c_rq + c_rb) - du) > TOL:
            raise SystemExit(f"MECH_MISMATCH u{u} recon={c_ro+c_rq+c_rb} du={du}")
        means_c["Ro"].append(c_ro)
        means_c["Rq"].append(c_rq)
        means_c["Rb"].append(c_rb)
        means_du.append(du)

    fig, ax = pair_fig(3)
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
    ax.yaxis.set_label_coords(-0.36, 0.5)
    ymin = min(float(min(neg_bottom)), min(means_du))
    ymax = max(float(max(pos_bottom)), max(means_du))
    ax.set_ylim(*pad_lim(ymin, ymax, frac=0.08, include_zero=True))
    style_ax(ax)
    complete_yticks(ax, 0.05)
    ax.tick_params(axis="y", labelsize=7.5, pad=1.0)
    handles = [
        Patch(facecolor=MECH["Ro"], edgecolor="0.25", linewidth=0.25, label=r"$0.25\Delta Ro$"),
        Patch(facecolor=MECH["Rq"], edgecolor="0.25", linewidth=0.25, label=r"$0.60\Delta Rq$"),
        Patch(facecolor=MECH["Rb"], edgecolor="0.25", linewidth=0.25, label=r"$-0.15\Delta Rb$"),
        Line2D(
            [0], [0], marker="D", color="none", markerfacecolor=MECH["tot"],
            markeredgecolor="0.15", markeredgewidth=0.3, markersize=4.5, label=r"$\Delta U$",
        ),
    ]
    pair_legend(fig, handles, pair_id=3, ncol=2, handlelength=0.80, columnspacing=0.30)
    save_pair_pdf(fig, OUT, 3)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
