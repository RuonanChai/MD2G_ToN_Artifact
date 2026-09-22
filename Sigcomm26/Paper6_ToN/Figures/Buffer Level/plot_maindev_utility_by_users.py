#!/usr/bin/env python3
"""MAINDEV ranking at u20/60/100 — three-panel horizontal ranked bars (V4).

Scientific question: at the three MAINDEV loads, how are the four same-substrate
policies ranked? Does not duplicate the five-point scaling line.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_evidence import (  # noqa: E402
    SAME_STRATEGIES,
    STRATEGY_LABEL,
    aggregate_by_users_strategy,
    load_rows,
    mean_std,
    require_frozen_evidence,
)
from _fig_v3 import C, WIDE_W, apply_v3, pad_lim, save_pdf, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "System_Utility_By_Users_MainDev.pdf"
ORDER = list(SAME_STRATEGIES)
USER_COUNTS = [20, 60, 100]
PANEL_LABS = ["(a) 20 users", "(b) 60 users", "(c) 100 users"]


def main() -> int:
    require_frozen_evidence()
    data = aggregate_by_users_strategy(load_rows("dev.json"), USER_COUNTS, SAME_STRATEGIES)
    means: dict[int, dict[str, float]] = {}
    all_m: list[float] = []
    for u in USER_COUNTS:
        means[u] = {}
        for s in ORDER:
            m, _sd = mean_std(data[u][s])
            means[u][s] = m
            all_m.append(m)
    # Common x range over observed means (not forced from 0).
    xlim = pad_lim(min(all_m), max(all_m), frac=0.08)
    x0 = float(xlim[0])

    apply_v3()
    fig, axes = plt.subplots(1, 3, figsize=(WIDE_W, 2.20), sharex=True, sharey=True)
    fig.subplots_adjust(wspace=0.08)
    y = np.arange(len(ORDER))
    labels = [STRATEGY_LABEL[s] for s in ORDER]
    for ax, users, title in zip(axes, USER_COUNTS, PANEL_LABS):
        vals = [means[users][s] for s in ORDER]
        colors = [C[s] for s in ORDER]
        widths = [v - x0 for v in vals]
        ax.barh(y, widths, left=x0, height=0.52, color=colors, edgecolor="0.25", linewidth=0.35, zorder=3)
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_xlim(*xlim)
        ax.set_title(title, fontsize=8.5, pad=2)
        ax.set_xlabel("Mean system utility $U$")
        style_ax(ax, ygrid=False, xgrid=True)
        ax.invert_yaxis()
    axes[1].tick_params(labelleft=False)
    axes[2].tick_params(labelleft=False)
    save_pdf(fig, OUT, max_width_in=0)
    print(f"Wrote {OUT} xlim={xlim}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
