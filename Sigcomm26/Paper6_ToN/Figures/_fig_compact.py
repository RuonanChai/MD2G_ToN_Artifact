"""ACM single-column pair geometry.

Native width matches 0.495\\columnwidth under acmart sigconf 10pt
(columnwidth=241.14749pt → 0.495 col = 1.658 in). Save with a fixed
MediaBox (no tight crop) so pair widths/heights match.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import subprocess

from _fig_v3 import apply_v3, style_ax  # noqa: F401

# 0.495 ACM columnwidth = 1.658 in. Pair 2 is wider-aspect so the heatmap is not a tall strip.
PAIR_W = 1.658
PAIR_SIZE = {
    1: (1.658, 1.70),
    2: (1.658, 1.28),
    3: (1.658, 1.40),
    4: (1.658, 1.36),
}
PAIR_H = {k: v[1] for k, v in PAIR_SIZE.items()}

# Identical axes box within each pair (figure fraction).
PAIR_MARGINS = {
    1: dict(left=0.32, right=0.985, bottom=0.24, top=0.74),
    2: dict(left=0.44, right=0.995, bottom=0.24, top=0.78),
    3: dict(left=0.38, right=0.98, bottom=0.24, top=0.72),
    4: dict(left=0.32, right=0.97, bottom=0.24, top=0.76),
}

# Full paper names (not Heur./Clust. abbreviations).
STRAT_SHORT = {
    "MD2G_COMPONENT": "MD2G",
    "HV3_COMPONENT": "Heuristic",
    "CLUSTERING_COMPONENT": "Clustering",
    "RULE_COMPONENT": "Rule",
}

# Fig.1/2: same stroke for all series (do not thicken MD2G).
COMPACT_LW = {"md2g": 1.20, "other": 1.20}
COMPACT_MS = 3.5


def apply_compact() -> None:
    apply_v3()
    plt.rcParams.update(
        {
            "font.size": 8.5,
            "axes.labelsize": 9.0,
            "axes.titlesize": 9.0,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.5,
            "axes.labelpad": 1.2,
            "xtick.major.pad": 1.0,
            "ytick.major.pad": 1.0,
            "xtick.major.size": 2.2,
            "ytick.major.size": 2.2,
            "lines.linewidth": 1.20,
        }
    )


def pair_fig(pair_id: int):
    apply_compact()
    w, h = PAIR_SIZE[pair_id]
    fig, ax = plt.subplots(figsize=(w, h))
    fig.subplots_adjust(**PAIR_MARGINS[pair_id])
    return fig, ax


def pair_legend(fig, handles, *, pair_id: int, ncol: int, fontsize: float = 8.5, **kw):
    cx = kw.pop("bbox_x", 0.50)
    fig.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(cx, 0.972),
        ncol=ncol,
        frameon=False,
        fontsize=fontsize,
        handlelength=kw.pop("handlelength", 1.35),
        columnspacing=kw.pop("columnspacing", 0.50),
        handletextpad=kw.pop("handletextpad", 0.22),
        labelspacing=kw.pop("labelspacing", 0.16),
        borderaxespad=0.0,
        **kw,
    )


def complete_yticks(ax, step: float) -> None:
    """Label every `step` from the current ylim so y-numbers are not skipped."""
    import math

    y0, y1 = ax.get_ylim()
    start = math.floor(y0 / step + 1e-12) * step
    ticks = []
    t = start
    n = 0
    while t <= y1 + 0.5 * step and n < 24:
        if t >= y0 - 0.5 * step:
            ticks.append(round(t, 10))
        t = round(t + step, 10)
        n += 1
    if ticks:
        ax.set_yticks(ticks)


def place_xy_labels(ax, xlabel: str, ylabel: str) -> None:
    ax.set_xlabel(xlabel, fontsize=9.0)
    ax.set_ylabel(ylabel, fontsize=9.0)
    ax.xaxis.set_label_coords(0.5, -0.18)
    ax.yaxis.set_label_coords(-0.18, 0.5)


def save_pair_pdf(fig, out_pdf: Path, pair_id: int) -> None:
    width, height = PAIR_SIZE[pair_id]
    fig.set_size_inches(width, height)
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, format="pdf", bbox_inches=None, pad_inches=0.0)
    plt.close(fig)
    info = subprocess.check_output(["pdfinfo", str(out_pdf)], text=True)
    w = h = None
    for ln in info.splitlines():
        if ln.startswith("Page size"):
            parts = ln.split(":")[1].strip().split()
            w = float(parts[0]) / 72.0
            h = float(parts[2]) / 72.0
    if w is None:
        raise SystemExit(f"NO_PAGE_SIZE {out_pdf}")
    if abs(w - width) / width > 0.008 or abs(h - height) / height > 0.008:
        raise SystemExit(
            f"PAIR_SIZE_MISMATCH {out_pdf.name}: {w:.4f}x{h:.4f} in "
            f"want {width:.4f}x{height:.4f} in"
        )


def pdf_size_in(path: Path) -> tuple[float, float]:
    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
    for ln in info.splitlines():
        if ln.startswith("Page size"):
            parts = ln.split(":")[1].strip().split()
            return float(parts[0]) / 72.0, float(parts[2]) / 72.0
    raise SystemExit(f"NO_PAGE_SIZE {path}")
