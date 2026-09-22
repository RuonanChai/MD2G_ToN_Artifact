#!/usr/bin/env python3
"""MAIN-TEXT throughput 1×3: 4G / 5G / Default Mix, one shared legend.

No external (a)/(b)/(c). Bold in-panel titles. Frozen TX Mbps only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_evidence import SAME_STRATEGIES, STRATEGY_LABEL, mean_std, require_frozen_evidence  # noqa: E402
from _fig_style import _throughput_cells, throughput_ylim_for  # noqa: E402
from _fig_v3 import C, LS, MK, WIDE_W, apply_v3, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "System_Throughput_MainText_1x3.pdf"
NETS = [("4g", "4G"), ("5g", "5G"), ("default_mix", "Default Mix")]
USER_LOADS = [20, 60, 100]
# Stronger than panel defaults for two-column readability
LW = {s: (2.7 if s == "MD2G_COMPONENT" else 1.95) for s in SAME_STRATEGIES}
MS = 5.4


def main() -> int:
    require_frozen_evidence()
    ylim = throughput_ylim_for("4g")
    apply_v3()
    fig, axes = plt.subplots(1, 3, figsize=(WIDE_W, 2.02), sharey=True)
    fig.subplots_adjust(left=0.058, right=0.995, bottom=0.16, top=0.875, wspace=0.10)
    xs = np.asarray(USER_LOADS, dtype=float)
    for ax, (net, panel) in zip(axes, NETS):
        aggregated = _throughput_cells(net)
        for s in SAME_STRATEGIES:
            means = []
            for u in USER_LOADS:
                vals = aggregated[u][s]
                if not vals:
                    raise SystemExit(f"MISSING {net} u{u} {s}")
                means.append(mean_std(vals)[0])
            ax.plot(
                xs, means, color=C[s], linestyle=LS[s], linewidth=LW[s],
                marker=MK[s], markersize=MS, markeredgecolor="0.15", markeredgewidth=0.35,
                zorder=5 if s == "MD2G_COMPONENT" else 3,
            )
        ax.set_xlabel("Number of users", fontsize=10.0)
        ax.set_xticks(USER_LOADS)
        ax.tick_params(labelsize=9.5)
        # Extra headroom so the in-panel title stays above markers after flattening.
        y0, y1 = ylim
        ax.set_ylim(y0, y1 + 0.22 * (y1 - y0))
        style_ax(ax)
        # Compact bold panel title — top-center inside axes (not (a)/(b)/(c)).
        ax.text(
            0.50,
            0.96,
            panel,
            transform=ax.transAxes,
            fontsize=10.0,
            fontweight="bold",
            color="0.15",
            ha="center",
            va="top",
            zorder=6,
        )
    axes[0].set_ylabel("Shared-root TX (Mbps)", fontsize=10.0)
    handles = [
        Line2D(
            [0], [0], color=C[s], linestyle=LS[s], linewidth=LW[s],
            marker=MK[s], markersize=MS, markeredgecolor="0.15", label=STRATEGY_LABEL[s],
        )
        for s in SAME_STRATEGIES
    ]
    fig.legend(
        handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.995), ncol=4,
        frameon=False, fontsize=10.0, handlelength=1.7, columnspacing=0.85, handletextpad=0.3,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # tight pad keeps axis titles inside MediaBox
    fig.savefig(OUT, format="pdf", bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print(f"Wrote {OUT} axes_frac≈{(0.995-0.058)*(0.875-0.16):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
