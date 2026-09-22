#!/usr/bin/env python3
"""Loot weak-user Rq — 3-panel horizontal ECDF; V4 compact wide panels."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_evidence import load_rows, match_same_substrate_blocks, require_frozen_evidence  # noqa: E402
from _fig_v3 import C, LS, LW, MK, MS, WIDE_W, apply_v3, ecdf_xy, pad_lim, save_pdf, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "Weak_User_Rq_Loot.pdf"
USER_COUNTS = [20, 60, 100]


def main() -> int:
    require_frozen_evidence()
    blocks = match_same_substrate_blocks(load_rows("loot.json"))
    series = {}
    xs_all = []
    for u in USER_COUNTS:
        md = [b["md2g_weak_user_Rq"] for b in blocks if b["users"] == u]
        st = [b["strong_weak_user_Rq"] for b in blocks if b["users"] == u]
        if not md or not st:
            raise SystemExit(f"MISSING weak-user u{u}")
        series[u] = (md, st)
        xs_all.extend(md)
        xs_all.extend(st)
    xlim = pad_lim(min(xs_all), max(xs_all), frac=0.04)

    apply_v3()
    fig, axes = plt.subplots(1, 3, figsize=(WIDE_W, 2.15), sharex=True, sharey=True)
    for ax, users, lab in zip(axes, USER_COUNTS, ["(a)", "(b)", "(c)"]):
        md, st = series[users]
        for vals, key, lab_s in ((md, "md2g", "MD2G"), (st, "strongest", "Strongest same-substrate")):
            x, y = ecdf_xy(vals)
            every = max(1, len(x) // 8)
            ax.plot(
                x,
                y,
                color=C[key],
                linestyle=LS[key],
                linewidth=LW[key],
                marker=MK[key],
                markevery=every,
                markersize=MS - 0.6,
                markeredgecolor="0.2",
                markeredgewidth=0.25,
                label=lab_s,
                zorder=4 if key == "md2g" else 3,
            )
        ax.set_xlim(*xlim)
        ax.set_ylim(0.0, 1.0)
        ax.set_title(f"{lab}  {users} users", fontsize=8.5, pad=2)
        style_ax(ax)
        ax.set_xlabel("Weak-user $R_q$")
    axes[0].set_ylabel("Empirical CDF")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 1.00),
        ncol=2,
        frameon=False,
        fontsize=8.0,
        handlelength=1.6,
        columnspacing=1.0,
    )
    save_pdf(fig, OUT, max_width_in=0)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
