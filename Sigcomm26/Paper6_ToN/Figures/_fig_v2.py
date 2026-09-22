#!/usr/bin/env python3
"""ToN final-figure V2 visual system. No scientific values live here."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from _fig_evidence import SAME_STRATEGIES, STRATEGY_LABEL

# IEEE ToN two-column (IEEEtran journal): columnwidth ~3.4 in, textwidth ~7.16 in.
COL_W = 3.40
WIDE_W = 6.59  # 0.92 * 7.16
DUMB_W = 2.89  # 0.85 * 3.40

# Restrained identity (same hex as frozen scheme1; MD2G dominant).
C = {
    "MD2G_COMPONENT": "#0E606B",
    "HV3_COMPONENT": "#1597A5",
    "CLUSTERING_COMPONENT": "#C4A35A",
    "RULE_COMPONENT": "#C16A6A",
    "MOQ_UNICAST_COMPONENT": "#8A8A8A",
    "groot": "#5E7A62",
    "rolling": "#8B5A5A",
    "md2g": "#0E606B",
    "strongest": "#5A5A5A",
}
MK = {
    "MD2G_COMPONENT": "o",
    "HV3_COMPONENT": "s",
    "CLUSTERING_COMPONENT": "^",
    "RULE_COMPONENT": "D",
    "MOQ_UNICAST_COMPONENT": "v",
    "groot": "P",
    "rolling": "X",
    "md2g": "o",
    "strongest": "s",
}
LS = {
    "MD2G_COMPONENT": "-",
    "HV3_COMPONENT": "--",
    "CLUSTERING_COMPONENT": "-.",
    "RULE_COMPONENT": ":",
    "MOQ_UNICAST_COMPONENT": (0, (3, 1, 1, 1)),
    "groot": "--",
    "rolling": ":",
    "md2g": "-",
    "strongest": "--",
}
LW = {s: (1.45 if s in ("MD2G_COMPONENT", "md2g") else 1.25) for s in list(C)}
MS = 5.0
CAP = 2.2
MECH = {"Ro": "#7A9E8A", "Rq": "#0E606B", "Rb": "#9E3150"}
LOAD_MK = {20: "o", 60: "s", 100: "D"}


def apply_v2() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Liberation Sans", "Arial", "Helvetica", "Nimbus Sans"],
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 10,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.fontsize": 9,
            "legend.frameon": False,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "mathtext.fontset": "custom",
            "mathtext.rm": "Liberation Sans",
            "mathtext.it": "Liberation Sans",
            "mathtext.bf": "Liberation Sans",
            "mathtext.cal": "Liberation Sans",
            "mathtext.default": "regular",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "text.usetex": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.transparent": False,
        }
    )


def style_ax(ax, ygrid: bool = True) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3.0, width=0.7)
    if ygrid:
        ax.yaxis.grid(True, linestyle="-", linewidth=0.4, color="0.15", alpha=0.14, zorder=0)
        ax.set_axisbelow(True)
    ax.xaxis.grid(False)


def save_pdf(fig, out_pdf: Path) -> None:
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, format="pdf", bbox_inches=None, pad_inches=0.0)
    plt.close(fig)


def ecdf_xy(vals):
    x = np.sort(np.asarray(vals, dtype=float))
    y = np.arange(1, x.size + 1, dtype=float) / x.size
    return x, y


def pad_lim(lo, hi, frac=0.07, include_zero=False):
    if include_zero:
        lo = min(lo, 0.0)
        hi = max(hi, 0.0)
    span = hi - lo
    if span <= 0:
        span = 0.1
    return lo - frac * span, hi + frac * span


def plot_ecdf_series(ax, series: dict, order, *, xlabel, ylabel="Empirical CDF"):
    for s in order:
        x, y = ecdf_xy(series[s])
        ax.plot(
            x,
            y,
            color=C[s],
            linestyle=LS[s],
            linewidth=LW.get(s, 1.25),
            marker=MK[s],
            markevery=max(1, len(x) // 12),
            markersize=MS - 0.8,
            markeredgecolor="0.15",
            markeredgewidth=0.35,
            label=STRATEGY_LABEL.get(s, s),
            zorder=4 if s in ("MD2G_COMPONENT", "md2g") else 3,
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(-0.02, 1.04)
    style_ax(ax)
    ax.legend(loc="lower right", handlelength=2.2, borderaxespad=0.2)


def ribbon_lines(ax, xs, series, order, *, xlabel, ylabel, ylim=None, direct_label=False, legend=True):
    xs = np.asarray(xs, dtype=float)
    for s in order:
        means, stds = [np.asarray(v, dtype=float) for v in series[s]]
        lo, hi = means - stds, means + stds
        ax.fill_between(xs, lo, hi, color=C[s], alpha=0.16 if s != "MD2G_COMPONENT" else 0.22, linewidth=0, zorder=2)
        ax.plot(
            xs,
            means,
            color=C[s],
            linestyle=LS[s],
            linewidth=LW.get(s, 1.25),
            marker=MK[s],
            markersize=MS,
            markeredgecolor="0.15",
            markeredgewidth=0.4,
            label=STRATEGY_LABEL.get(s, s),
            zorder=4 if s == "MD2G_COMPONENT" else 3,
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if ylim is not None:
        ax.set_ylim(*ylim)
    style_ax(ax)
    if direct_label:
        for s in order:
            means = np.asarray(series[s][0], dtype=float)
            ax.text(xs[-1] + 1.5, means[-1], STRATEGY_LABEL.get(s, s), fontsize=8.5, color=C[s], va="center")
    elif legend:
        ax.legend(loc="best", ncol=2, handlelength=2.0, columnspacing=0.8, borderaxespad=0.15)
