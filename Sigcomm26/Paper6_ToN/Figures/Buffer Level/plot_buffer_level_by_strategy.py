#!/usr/bin/env python3
"""Sigcomm Buffer Level/plot_buffer_level_by_strategy.py — MAINDEV U by strategy."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_evidence import (  # noqa: E402
    COLOR_SCHEMES,
    SAME_STRATEGIES,
    STRATEGY_LABEL,
    aggregate_by_strategy,
    apply_sigcomm_rcparams,
    load_rows,
    mean_std,
    require_frozen_evidence,
    save_pdf,
)


def main() -> int:
    require_frozen_evidence()
    data = aggregate_by_strategy(load_rows("dev.json"), SAME_STRATEGIES)
    out_dir = Path(__file__).resolve().parent
    for scheme_name, colors in COLOR_SCHEMES.items():
        apply_sigcomm_rcparams()
        fig, ax = plt.subplots(figsize=(12, 7))
        x = np.arange(len(SAME_STRATEGIES))
        means, stds = [], []
        for s in SAME_STRATEGIES:
            m, sd = mean_std(data[s])
            means.append(m)
            stds.append(sd)
        ax.bar(
            x,
            means,
            color=[colors[s] for s in SAME_STRATEGIES],
            alpha=0.9,
            edgecolor="black",
            linewidth=1.5,
            yerr=stds,
            capsize=5,
            error_kw={"elinewidth": 2},
        )
        ax.set_xlabel("Strategy", fontsize=25, fontweight="bold")
        ax.set_ylabel("Average System Utility U", fontsize=23, fontweight="bold")
        ax.set_xticks(x)
        ax.set_xticklabels([STRATEGY_LABEL[s] for s in SAME_STRATEGIES], fontsize=20)
        ax.grid(True, alpha=0.3, linestyle="--", axis="y")
        ax.set_ylim(0, 1.0)
        out_pdf = out_dir / f"System_Utility_By_Strategy_{scheme_name}.pdf"
        plt.tight_layout()
        save_pdf(fig, out_pdf)
        print(f"Wrote {out_pdf}")
    alias = out_dir / "Buffer_Level_By_Strategy_scheme1.pdf"
    alias.write_bytes((out_dir / "System_Utility_By_Strategy_scheme1.pdf").read_bytes())
    print(f"Wrote alias {alias}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
