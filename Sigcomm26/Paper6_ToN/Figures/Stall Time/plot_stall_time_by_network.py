#!/usr/bin/env python3
"""Sigcomm Stall Time/plot_stall_time_by_network.py — supporting stall_last."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_evidence import (  # noqa: E402
    NET_LABEL,
    NET_ORDER,
    QOE_COLORS,
    SAME_STRATEGIES,
    STRATEGY_LABEL,
    apply_sigcomm_rcparams,
    load_rows,
    mean_std,
    require_frozen_evidence,
    save_pdf,
)

OUT = Path(__file__).resolve().parent / "Stall_Time_By_Network.pdf"


def main() -> int:
    require_frozen_evidence()
    rows = load_rows("dev.json")
    apply_sigcomm_rcparams()
    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(NET_ORDER))
    width = 0.18
    for idx, strategy in enumerate(SAME_STRATEGIES):
        means, stds = [], []
        for net in NET_ORDER:
            vals = [
                float(r["stall_last"])
                for r in rows
                if r.get("network") == net and r.get("strategy") == strategy and r.get("stall_last") is not None
            ]
            if not vals:
                raise SystemExit(f"MISSING stall net={net} strategy={strategy}")
            m, sd = mean_std(vals)
            means.append(m)
            stds.append(sd)
        offset = (idx - 1.5) * width
        ax.bar(
            x + offset,
            means,
            width,
            label=STRATEGY_LABEL[strategy],
            color=QOE_COLORS[strategy],
            alpha=0.9,
            edgecolor="black",
            linewidth=1.5,
            yerr=stds,
            capsize=4,
            error_kw={"elinewidth": 2},
        )
    ax.set_xlabel("Network trace", fontsize=25, fontweight="bold")
    ax.set_ylabel("Stall time (s, last interval)", fontsize=23, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([NET_LABEL[n] for n in NET_ORDER], fontsize=18, rotation=20, ha="right")
    ax.legend(loc="upper right", fontsize=16, framealpha=0.9, ncol=2)
    ax.grid(True, alpha=0.3, linestyle="--", axis="y")
    plt.tight_layout()
    save_pdf(fig, OUT)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
