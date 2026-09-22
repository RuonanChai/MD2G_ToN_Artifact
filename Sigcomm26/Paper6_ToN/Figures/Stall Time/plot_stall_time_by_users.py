#!/usr/bin/env python3
"""Sigcomm Stall Time/plot_stall_time_by_users.py — scaling concurrency stall."""
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
    apply_sigcomm_rcparams,
    load_rows,
    mean_std,
    require_frozen_evidence,
    save_pdf,
)

OUT = Path(__file__).resolve().parent / "Stall_Time_By_Users.pdf"
USER_COUNTS = [10, 20, 40, 60, 100]


def main() -> int:
    require_frozen_evidence()
    rows = load_rows("scaling.json")
    apply_sigcomm_rcparams()
    fig, ax = plt.subplots(figsize=(12, 7))
    x = np.arange(len(USER_COUNTS))
    width = 0.18
    for idx, strategy in enumerate(SAME_STRATEGIES):
        means = []
        for users in USER_COUNTS:
            vals = [
                float(r["stall_last"])
                for r in rows
                if int(r["users"]) == users and r.get("strategy") == strategy and r.get("stall_last") is not None
            ]
            means.append(mean_std(vals)[0])
        offset = (idx - 1.5) * width
        ax.bar(x + offset, means, width, label=STRATEGY_LABEL[strategy], color=QOE_COLORS[strategy], alpha=0.9, edgecolor="black", linewidth=1.5)
    ax.set_xlabel("Number of Users", fontsize=25, fontweight="bold")
    ax.set_ylabel("Stall time (s, last interval)", fontsize=23, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([str(u) for u in USER_COUNTS], fontsize=20)
    ax.legend(loc="upper left", fontsize=18, framealpha=0.9, ncol=2)
    ax.grid(True, alpha=0.3, linestyle="--", axis="y")
    plt.tight_layout()
    save_pdf(fig, OUT)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
