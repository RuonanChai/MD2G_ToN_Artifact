#!/usr/bin/env python3
"""ToN final-figure V6 visual system. Typography targets effective ~10 pt after LaTeX inclusion."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from _fig_evidence import SAME_STRATEGIES, STRATEGY_LABEL

# Intended LaTeX inclusion widths (inches)
COL_W = 3.35  # single-column / two-panel half
COL_W_MAX = 3.45  # tight-bbox tolerance for legends
WIDE_W = 7.00  # two-column combined
TP_PANEL_W = 2.20  # three-panel throughput each
TP_PANEL_W_MAX = 2.30

C = {
    "MD2G_COMPONENT": "#0072B2",
    "HV3_COMPONENT": "#E69F00",
    "CLUSTERING_COMPONENT": "#009E73",
    "RULE_COMPONENT": "#CC79A7",
    "MOQ_UNICAST_COMPONENT": "#7A7A7A",
    "groot": "#56B4E9",
    "rolling": "#D55E00",
    "md2g": "#0072B2",
    "strongest": "#7A7A7A",
}
MK = {
    "MD2G_COMPONENT": "o",
    "HV3_COMPONENT": "s",
    "CLUSTERING_COMPONENT": "^",
    "RULE_COMPONENT": "D",
    "MOQ_UNICAST_COMPONENT": "v",
    "groot": "v",
    "rolling": "X",
    "md2g": "o",
    "strongest": "s",
}
LS = {
    "MD2G_COMPONENT": "-",
    "HV3_COMPONENT": "--",
    "CLUSTERING_COMPONENT": "-.",
    "RULE_COMPONENT": ":",
    "MOQ_UNICAST_COMPONENT": (0, (3, 1.2)),
    "groot": "--",
    "rolling": ":",
    "md2g": "-",
    "strongest": "--",
}
LW = {s: (2.0 if s in ("MD2G_COMPONENT", "md2g") else 1.6) for s in list(C)}
MS = 4.0
MECH = {"Ro": "#009E73", "Rq": "#0072B2", "Rb": "#D55E00", "tot": "#333333"}
DELTA_CMAP = LinearSegmentedColormap.from_list("du_v6", ["#D55E5D", "#F7F7F7", "#0072B2"], N=256)
LOAD_C = {20: "#9ECAE1", 60: "#4292C6", 100: "#08519C"}
LOAD_MK = {20: "o", 60: "s", 100: "D"}

NET_PROFILE_LABEL = {
    "4g": "4G",
    "5g": "5G",
    "wifi": "Wi-Fi",
    "fiber_optic": "Fiber Optic",
    "default_mix": "Default Mix",
    "wifi_dominant": "Wi-Fi Dominant",
    "5g_dominant": "5G Dominant",
}


def apply_v3() -> None:
    """V6 rcParams (name kept for script compatibility). Target ~10 pt after 1:1 inclusion."""
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Liberation Sans", "Arial", "Helvetica", "Nimbus Sans"],
            "font.size": 10.0,
            "axes.labelsize": 10.0,
            "axes.titlesize": 10.0,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "legend.fontsize": 9.5,
            "legend.frameon": False,
            "axes.linewidth": 0.7,
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


def style_ax(ax, *, ygrid: bool = True, xgrid: bool = False) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=2.6, width=0.55)
    if ygrid:
        ax.yaxis.grid(True, linestyle="-", linewidth=0.4, color="0.15", alpha=0.14, zorder=0)
        ax.set_axisbelow(True)
    else:
        ax.yaxis.grid(False)
    if xgrid:
        ax.xaxis.grid(True, linestyle="-", linewidth=0.4, color="0.15", alpha=0.14, zorder=0)
        ax.set_axisbelow(True)
    else:
        ax.xaxis.grid(False)


def legend_above(ax, ncol: int = 4, **kw):
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=ncol,
        handlelength=1.5,
        columnspacing=0.7,
        handletextpad=0.3,
        borderaxespad=0.0,
        fontsize=kw.pop("fontsize", 9.5),
        **kw,
    )


def profile_label(ax, text: str, *, loc: str = "upper center") -> None:
    """Compact bold panel/condition title inside axes (not (a)/(b)/(c) letters)."""
    if "center" in loc:
        ha, x = "center", 0.50
    elif "left" in loc:
        ha, x = "left", 0.03
    else:
        ha, x = "right", 0.97
    y = 0.97 if "upper" in loc else 0.03
    ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        fontsize=10.0,
        fontweight="bold",
        color="0.25",
        ha=ha,
        va="top" if "upper" in loc else "bottom",
        zorder=10,
        clip_on=False,
    )


def save_pdf(fig, out_pdf: Path, *, max_width_in: float | None = COL_W_MAX, tight: bool = True) -> None:
    """Save vector PDF at intended inclusion width (prefer no post-hoc font shrink).

    Pass max_width_in=0 to disable the width guard (appendix wide figures).
    """
    import subprocess

    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    if tight:
        fig.savefig(out_pdf, format="pdf", bbox_inches="tight", pad_inches=0.02)
    else:
        fig.savefig(out_pdf, format="pdf", bbox_inches=None, pad_inches=0.0)

    def _width_in(path: Path) -> float:
        info = subprocess.check_output(["pdfinfo", str(path)], text=True)
        for ln in info.splitlines():
            if ln.startswith("Page size"):
                return float(ln.split(":")[1].strip().split()[0]) / 72.0
        raise SystemExit(f"NO_PAGE_SIZE {path}")

    if max_width_in and max_width_in > 0:
        w = _width_in(out_pdf)
        if w > max_width_in + 0.01:
            raise SystemExit(
                f"PDF_TOO_WIDE {out_pdf.name}: {w:.3f}in > {max_width_in:.3f}in "
                "(resize layout; do not shrink fonts post-hoc)"
            )
    plt.close(fig)


def ecdf_xy(vals):
    x = np.sort(np.asarray(vals, dtype=float))
    y = np.arange(1, x.size + 1, dtype=float) / x.size
    return x, y


def pad_lim(lo, hi, frac=0.06, include_zero=False):
    if include_zero:
        lo = min(lo, 0.0)
        hi = max(hi, 0.0)
    span = hi - lo
    if span <= 0:
        span = 0.1
    return lo - frac * span, hi + frac * span


def plot_ecdf_series(ax, series: dict, order, *, xlabel, ylabel="Empirical CDF"):
    xs_all = []
    for s in order:
        x, y = ecdf_xy(series[s])
        xs_all.append(x)
        every = max(1, len(x) // 8)
        ax.plot(
            x,
            y,
            color=C[s],
            linestyle=LS[s],
            linewidth=LW.get(s, 1.6),
            marker=MK[s],
            markevery=every,
            markersize=MS - 0.4,
            markeredgecolor="0.2",
            markeredgewidth=0.25,
            label=STRATEGY_LABEL.get(s, s),
            zorder=4 if s in ("MD2G_COMPONENT", "md2g") else 3,
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0.0, 1.0)
    xmin = min(float(a.min()) for a in xs_all)
    xmax = max(float(a.max()) for a in xs_all)
    ax.set_xlim(*pad_lim(xmin, xmax, frac=0.03))
    style_ax(ax)
    legend_above(ax, ncol=len(order))


def trend_lines(ax, xs, series, order, *, xlabel, ylabel, ylim=None):
    xs = np.asarray(xs, dtype=float)
    for s in order:
        means = np.asarray(series[s], dtype=float)
        ax.plot(
            xs,
            means,
            color=C[s],
            linestyle=LS[s],
            linewidth=LW.get(s, 1.6),
            marker=MK[s],
            markersize=MS,
            markeredgecolor="0.2",
            markeredgewidth=0.25,
            label=STRATEGY_LABEL.get(s, s),
            zorder=4 if s in ("MD2G_COMPONENT", "md2g") else 3,
        )
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if ylim is not None:
        ax.set_ylim(*ylim)
    style_ax(ax)
    legend_above(ax, ncol=min(4, len(order)))
