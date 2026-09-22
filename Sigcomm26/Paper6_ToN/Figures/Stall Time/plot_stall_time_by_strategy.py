#!/usr/bin/env python3
"""Sigcomm Stall Time/plot_stall_time_by_strategy.py — supporting stall_last metric."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_evidence import (  # noqa: E402
    QOE_COLORS,
    SAME_STRATEGIES,
    STRATEGY_LABEL,
    aggregate_metric_by_strategy,
    apply_sigcomm_rcparams,
    load_rows,
    mean_std,
    require_frozen_evidence,
    save_pdf,
)

OUT = Path(__file__).resolve().parent / "Stall_Time_By_Strategy.pdf"


def main() -> int:
    require_frozen_evidence()
    data = aggregate_metric_by_strategy(load_rows("dev.json"), "stall_last", SAME_STRATEGIES)
    apply_sigcomm_rcparams()
    fig, ax = plt.subplots(figsize=(12, 7))
    x = np.arange(len(SAME_STRATEGIES))
    means, stds, colors, labels = [], [], [], []
    for s in SAME_STRATEGIES:
        m, sd = mean_std(data[s])
        means.append(m)
        stds.append(sd)
        colors.append(QOE_COLORS[s])
        labels.append(STRATEGY_LABEL[s])
    ax.bar(x, means, color=colors, alpha=0.9, edgecolor="black", linewidth=1.5, yerr=stds, capsize=5, error_kw={"elinewidth": 2})
    ax.set_xlabel("Strategy", fontsize=25, fontweight="bold")
    ax.set_ylabel("Stall time (s, last interval)", fontsize=23, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=20)
    ax.grid(True, alpha=0.3, linestyle="--", axis="y")
    ax.tick_params(labelsize=22)
    plt.tight_layout()
    save_pdf(fig, OUT)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
