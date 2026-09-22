#!/usr/bin/env python3
"""Optional Discussion Rb–U 1×3 with ONE shared strategy legend (no per-panel strategy legend)."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_evidence import SAME_STRATEGIES, load_rows, mean_std, require_frozen_evidence  # noqa: E402
from _fig_style import (  # noqa: E402
    MD2G_STAR_EDGE,
    MD2G_STAR_FACE,
    TRADE_BASE_ALPHA,
    TRADE_C,
    TRADE_MK,
    TRADE_SIZE,
    USER_LOADS,
    _arrow_box_clear,
    _better_candidates,
    _md2g_overlaps_baseline,
)
from _fig_v3 import LS, WIDE_W, apply_v3, pad_lim, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "TierB_Rb_vs_U_Discussion_1x3.pdf"
NETS = [("4g", "(a) 4G"), ("5g", "(b) 5G"), ("default_mix", "(c) Default Mix")]


def _series(network: str):
    rows = [r for r in load_rows("dev.json") if r.get("network") == network and r.get("strategy") in SAME_STRATEGIES]
    by = defaultdict(lambda: {"Rb": [], "U": []})
    for r in rows:
        if r.get("Rb") is None or r.get("U") is None:
            continue
        by[(r["strategy"], int(r["users"]))]["Rb"].append(float(r["Rb"]))
        by[(r["strategy"], int(r["users"]))]["U"].append(float(r["U"]))
    series = {}
    all_rb, all_u = [], []
    for s in SAME_STRATEGIES:
        pts = []
        for u in USER_LOADS:
            rec = by[(s, u)]
            if not rec["Rb"]:
                raise SystemExit(f"MISSING {network} {s} u{u}")
            xr = mean_std(rec["Rb"])[0]
            yu = mean_std(rec["U"])[0]
            pts.append((xr, yu, u))
            all_rb.append(xr)
            all_u.append(yu)
        series[s] = pts
    return series, all_rb, all_u


def main() -> int:
    require_frozen_evidence()
    apply_v3()
    fig, axes = plt.subplots(1, 3, figsize=(WIDE_W, 2.85), sharey=False)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.14, top=0.78, wspace=0.28)
    for ax, (net, panel) in zip(axes, NETS):
        series, all_rb, all_u = _series(net)
        xlim = pad_lim(min(all_rb), max(all_rb), frac=0.07)
        ylim = pad_lim(min(all_u), max(all_u), frac=0.07)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        for s in SAME_STRATEGIES:
            pts = series[s]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if s == "MD2G_COMPONENT":
                ax.plot(xs, ys, color="#7A7A7A", linestyle="-", linewidth=1.0, alpha=0.42, zorder=2)
            else:
                ax.plot(xs, ys, color=TRADE_C[s], linestyle=LS[s], linewidth=0.9, alpha=0.38, zorder=2)
        base_pts = []
        for s in SAME_STRATEGIES:
            if s == "MD2G_COMPONENT":
                continue
            for x, y, u in series[s]:
                base_pts.append((x, y, u))
                ax.scatter(
                    [x], [y], s=TRADE_SIZE[u] * 0.55, c=TRADE_C[s], marker=TRADE_MK[s],
                    edgecolors="0.25", linewidths=0.35, alpha=TRADE_BASE_ALPHA, zorder=3,
                )
        for pt in series["MD2G_COMPONENT"]:
            x, y, u = pt
            overlap = _md2g_overlaps_baseline(pt, base_pts, tol_frac=0.055, xlim=xlim, ylim=ylim)
            if overlap:
                ax.scatter(
                    [x], [y], s=TRADE_SIZE[u], facecolors="none", edgecolors=MD2G_STAR_FACE,
                    marker="*", linewidths=1.4, zorder=7,
                )
            else:
                ax.scatter(
                    [x], [y], s=TRADE_SIZE[u], c=MD2G_STAR_FACE, marker="*",
                    edgecolors=MD2G_STAR_EDGE, linewidths=0.6, zorder=6,
                )
        xspan = xlim[1] - xlim[0]
        yspan = ylim[1] - ylim[0]
        pts_af = [((x - xlim[0]) / xspan, (y - ylim[0]) / yspan) for x, y in zip(all_rb, all_u)]
        for xy, xytext in _better_candidates():
            if _arrow_box_clear(pts_af, xy, xytext, pad=0.045):
                ax.annotate(
                    "Better", xy=xy, xytext=xytext, xycoords="axes fraction", textcoords="axes fraction",
                    fontsize=10.0, fontstyle="italic", color="#666666",
                    arrowprops=dict(arrowstyle="-|>", color="#777777", lw=0.7, mutation_scale=6.5, shrinkA=1, shrinkB=1),
                    zorder=8,
                )
                break
        ax.set_xlabel(r"$R_b$", fontsize=10.0)
        style_ax(ax, ygrid=True)
        ax.tick_params(labelsize=9.5)
        ax.set_title(panel, fontsize=10.0, pad=3, color="0.25", fontweight="bold")
    axes[0].set_ylabel("System utility $U$", fontsize=10.0)
    strat_handles = [
        Line2D([0], [0], marker="*", color="none", markerfacecolor=MD2G_STAR_FACE, markeredgecolor=MD2G_STAR_EDGE,
               markeredgewidth=0.6, markersize=9, label="MD2G"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=TRADE_C["HV3_COMPONENT"], markeredgecolor="0.25",
               markersize=5.5, alpha=TRADE_BASE_ALPHA, label="Heur."),
        Line2D([0], [0], marker="^", color="none", markerfacecolor=TRADE_C["CLUSTERING_COMPONENT"], markeredgecolor="0.25",
               markersize=6, alpha=TRADE_BASE_ALPHA, label="Clust."),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=TRADE_C["RULE_COMPONENT"], markeredgecolor="0.25",
               markersize=5, alpha=TRADE_BASE_ALPHA, label="Rule"),
    ]
    fig.legend(
        handles=strat_handles, loc="upper left", bbox_to_anchor=(0.07, 0.995), ncol=4, frameon=False,
        fontsize=9.5, handlelength=1.0, columnspacing=0.55, handletextpad=0.25,
    )
    size_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="0.45", markeredgecolor="0.25", markersize=ms, label=str(u))
        for u, ms in ((20, 4.5), (60, 6.0), (100, 7.5))
    ]
    fig.legend(
        handles=size_handles, loc="upper right", bbox_to_anchor=(0.99, 0.995), ncol=3,
        title="Users", title_fontsize=9.5, fontsize=9.5, frameon=False, handletextpad=0.25, columnspacing=0.55,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, format="pdf", bbox_inches=None, pad_inches=0.02)
    plt.close(fig)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
