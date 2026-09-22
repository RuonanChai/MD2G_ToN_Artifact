#!/usr/bin/env python3
"""MAINDEV per-cell U ECDF — ACM pair-1 compact native canvas."""
from __future__ import annotations

import sys
from pathlib import Path

from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import COMPACT_LW, COMPACT_MS, STRAT_SHORT, complete_yticks, pair_fig, pair_legend, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import SAME_STRATEGIES, aggregate_by_strategy, load_rows, require_frozen_evidence  # noqa: E402
from _fig_v3 import C, LS, MK, ecdf_xy, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "QoE_By_Strategy.pdf"


def main() -> int:
    require_frozen_evidence()
    data = aggregate_by_strategy(load_rows("dev.json"), SAME_STRATEGIES)
    fig, ax = pair_fig(1)
    for s in SAME_STRATEGIES:
        x, y = ecdf_xy(data[s])
        every = max(1, len(x) // 12)
        ax.plot(
            x, y, color=C[s], linestyle=LS[s],
            linewidth=COMPACT_LW["md2g"] if s == "MD2G_COMPONENT" else COMPACT_LW["other"],
            marker=MK[s], markevery=every, markersize=COMPACT_MS,
            markeredgecolor="0.2", markeredgewidth=0.25,
            zorder=4 if s == "MD2G_COMPONENT" else 3,
        )
    place_xy_labels(ax, "System utility $U$", "Empirical CDF")
    ax.set_ylim(-0.02, 1.04)
    xmin = min(float(min(data[s])) for s in SAME_STRATEGIES)
    xmax = max(float(max(data[s])) for s in SAME_STRATEGIES)
    span = xmax - xmin
    ax.set_xlim(xmin - 0.04 * span, xmax + 0.06 * span)
    style_ax(ax)
    complete_yticks(ax, 0.2)
    handles = [
        Line2D(
            [0], [0], color=C[s], linestyle=LS[s],
            linewidth=COMPACT_LW["md2g"] if s == "MD2G_COMPONENT" else COMPACT_LW["other"],
            marker=MK[s], markersize=COMPACT_MS, markeredgecolor="0.2",
            label=STRAT_SHORT[s],
        )
        for s in SAME_STRATEGIES
    ]
    pair_legend(fig, handles, pair_id=1, ncol=2, handlelength=1.25, columnspacing=0.45)
    save_pair_pdf(fig, OUT, 1)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
