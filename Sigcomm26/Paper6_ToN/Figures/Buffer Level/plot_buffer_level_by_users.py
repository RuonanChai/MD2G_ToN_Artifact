#!/usr/bin/env python3
"""Scaling U vs users — ACM pair-1 compact. Keep 10/20/40/60/100."""
from __future__ import annotations

import sys
from pathlib import Path

from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import COMPACT_LW, COMPACT_MS, STRAT_SHORT, complete_yticks, pair_fig, pair_legend, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import (  # noqa: E402
    COLOR_SCHEMES,
    SAME_STRATEGIES,
    aggregate_by_users_strategy,
    load_rows,
    mean_std,
    require_frozen_evidence,
)
from _fig_v3 import C, LS, MK, pad_lim, style_ax  # noqa: E402

USER_COUNTS = [10, 20, 40, 60, 100]


def plot(users_data, out_pdf: Path) -> None:
    fig, ax = pair_fig(1)
    xs = list(range(len(USER_COUNTS)))
    all_m = []
    for s in SAME_STRATEGIES:
        means = [mean_std(users_data[u][s])[0] for u in USER_COUNTS]
        all_m.extend(means)
        ax.plot(
            xs, means, color=C[s], linestyle=LS[s],
            linewidth=COMPACT_LW["md2g"] if s == "MD2G_COMPONENT" else COMPACT_LW["other"],
            marker=MK[s], markersize=COMPACT_MS,
            markeredgecolor="0.2", markeredgewidth=0.25,
            zorder=4 if s == "MD2G_COMPONENT" else 3,
        )
    place_xy_labels(ax, "Users", "System utility $U$")
    ax.set_xticks(xs)
    ax.set_xticklabels([str(u) for u in USER_COUNTS])
    ax.set_xlim(-0.45, 4.55)
    ax.set_ylim(*pad_lim(min(all_m), max(all_m), frac=0.08))
    style_ax(ax)
    complete_yticks(ax, 0.1)
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
    save_pair_pdf(fig, out_pdf, 1)


def main() -> int:
    require_frozen_evidence()
    data = aggregate_by_users_strategy(load_rows("scaling.json"), USER_COUNTS, SAME_STRATEGIES)
    out_dir = Path(__file__).resolve().parent
    primary = out_dir / "System_Utility_By_Users_scheme1.pdf"
    plot(data, primary)
    blob = primary.read_bytes()
    for name in COLOR_SCHEMES:
        if name == "scheme1":
            continue
        dest = out_dir / f"System_Utility_By_Users_{name}.pdf"
        dest.write_bytes(blob)
    (out_dir / "Buffer_Level_By_Users_scheme1.pdf").write_bytes(blob)
    print(f"Wrote {primary} + scheme aliases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
