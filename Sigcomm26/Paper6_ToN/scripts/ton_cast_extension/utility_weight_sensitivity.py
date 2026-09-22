#!/usr/bin/env python3
"""TASK 2: Offline utility-weight sensitivity. No retraining. Frozen Ro/Rq/Rb only."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _common import (  # noqa: E402
    RESULTS,
    filter_scope,
    load_dev_rows,
    mean,
    utility,
    write_csv,
    write_json,
)

OUT = RESULTS / "utility_sensitivity"
CFGS = {
    "A_quality_dominant": (0.2, 0.7, 0.1),
    "B_balanced": (0.33, 0.33, 0.34),
    "C_bandwidth_aware": (0.5, 0.25, 0.25),
    "frozen_paper": (0.25, 0.60, 0.15),
}
STRATS = ("MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT")
LABEL = {"MD2G_COMPONENT": "MD2G-Cast", "HV3_COMPONENT": "Heuristic", "CLUSTERING_COMPONENT": "Clustering"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = filter_scope(
        load_dev_rows(),
        nets=("4g", "wifi"),
        users=(60,),
        strategies=STRATS,
    )
    cell_rows = []
    for r in rows:
        rec = {
            "strategy": LABEL[r["strategy"]],
            "network": r["network"],
            "users": r["users"],
            "seed": r["seed"],
            "Ro": r["Ro_component"],
            "Rq": r["Rq"],
            "Rb": r["Rb"],
        }
        for name, w in CFGS.items():
            rec[name] = utility(r["Ro_component"], r["Rq"], r["Rb"], w)
        cell_rows.append(rec)
    write_csv(OUT / "utility_sensitivity_cells.csv", cell_rows)

    summary = []
    rank_notes = []
    for name, w in CFGS.items():
        means = {}
        for strat in STRATS:
            lab = LABEL[strat]
            vals = [c[name] for c in cell_rows if c["strategy"] == lab]
            means[lab] = mean(vals)
            summary.append(
                {
                    "config": name,
                    "lambda_Ro": w[0],
                    "lambda_Rq": w[1],
                    "lambda_Rb": w[2],
                    "strategy": lab,
                    "U_mean": means[lab],
                    "n": len(vals),
                }
            )
        ranked = sorted(means, key=lambda s: -means[s])
        rank_notes.append(
            {
                "config": name,
                "ranking": " > ".join(f"{s}={means[s]:.4f}" for s in ranked),
                "md2g_rank": ranked.index("MD2G-Cast") + 1,
                "md2g_best": ranked[0] == "MD2G-Cast",
            }
        )
    write_csv(OUT / "utility_sensitivity_summary.csv", summary)
    write_json(OUT / "utility_sensitivity_ranking.json", rank_notes)

    lines = [
        r"\begin{tabular}{lcccc}",
        r"\hline",
        r"Config ($\lambda_o,\lambda_q,\lambda_b$) & MD2G-Cast & Heuristic & Clustering & MD2G rank \\",
        r"\hline",
    ]
    sm = {(s["config"], s["strategy"]): s["U_mean"] for s in summary}
    pretty = {
        "A_quality_dominant": r"A quality (0.20,0.70,0.10)",
        "B_balanced": r"B balanced (0.33,0.33,0.34)",
        "C_bandwidth_aware": r"C bandwidth (0.50,0.25,0.25)",
        "frozen_paper": r"Frozen paper (0.25,0.60,0.15)",
    }
    for name in CFGS:
        rn = next(x for x in rank_notes if x["config"] == name)
        lines.append(
            f"{pretty[name]} & {sm[(name,'MD2G-Cast')]:.3f} & {sm[(name,'Heuristic')]:.3f} & "
            f"{sm[(name,'Clustering')]:.3f} & {rn['md2g_rank']} \\\\"
        )
    lines += [r"\hline", r"\end{tabular}", ""]
    (OUT / "utility_sensitivity_table.tex").write_text("\n".join(lines))

    fig, ax = plt.subplots(figsize=(7.0, 2.40))
    x = np.arange(len(CFGS))
    width = 0.22
    colors = {"MD2G-Cast": "#2171B5", "Heuristic": "#D94801", "Clustering": "#238B45"}
    names = list(CFGS)
    for i, strat in enumerate(("MD2G-Cast", "Heuristic", "Clustering")):
        ys = [sm[(n, strat)] for n in names]
        ax.bar(x + (i - 1) * width, ys, width, color=colors[strat], label=strat)
    ax.set_xticks(x)
    ax.set_xticklabels(["A quality", "B balanced", "C bandwidth", "Frozen paper"], fontsize=8.5)
    ax.set_ylabel(r"Reweighted $U$")
    ax.set_ylim(0.0, 1.0)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.16, top=0.84)
    fig.savefig(OUT / "utility_weight_sensitivity.pdf")
    plt.close(fig)
    print(f"Wrote {OUT} ranking={rank_notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
