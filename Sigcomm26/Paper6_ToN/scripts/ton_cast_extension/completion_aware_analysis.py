#!/usr/bin/env python3
"""TASK 4: Completion-aware analysis from frozen live cells. No rerun."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _common import (  # noqa: E402
    CAST_ROLLING_U,
    RESULTS,
    STRAT_LABEL,
    USERS,
    filter_scope,
    load_dev_rows,
    mean,
    write_csv,
)

OUT = RESULTS / "completion_analysis"
STRATS = ("MD2G_COMPONENT", "HV3_COMPONENT", "CLUSTERING_COMPONENT", "MOQ_UNICAST_COMPONENT")


def decoded_completion(r: dict) -> float:
    cc = r.get("component_completion_fraction") or {}
    rec = r.get("receiver_set_size") or {}
    num = den = 0.0
    for c, st in cc.items():
        n_req = float(st.get("n_receivers") or rec.get(c) or 0)
        n_ok = float(st.get("n_complete_dump_gt_64") or 0)
        num += n_ok
        den += n_req
    return num / den if den else 0.0


def bw_per_completion(r: dict, completion: float) -> float:
    """Shared-root bytes per completed visible component-slot (B_shared / (N * completion))."""
    n = max(1, int(r["users"]))
    b = float(r.get("B_shared") or 0.0)
    return b / max(n * max(completion, 1e-9), 1e-9)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = filter_scope(load_dev_rows(), strategies=STRATS)
    out = []
    for r in rows:
        comp = decoded_completion(r)
        out.append(
            {
                "strategy": STRAT_LABEL[r["strategy"]],
                "content": r["content"],
                "network": r["network"],
                "users": r["users"],
                "seed": r["seed"],
                "U": r["U"],
                "Rq": r["Rq"],
                "decoded_completion_ratio": comp,
                "component_reuse_ratio": r["Ro_component"],
                "B_shared": r.get("B_shared"),
                "B_unicast": r.get("B_unicast"),
                "bandwidth_per_completed_visible": bw_per_completion(r, comp),
                "mean_rx": r.get("mean_rx"),
            }
        )
    write_csv(OUT / "completion_analysis_cells.csv", out)

    summary = []
    for strat in ("MD2G-Cast", "Heuristic", "Clustering", "MoQ Unicast"):
        for u in USERS:
            sub = [x for x in out if x["strategy"] == strat and int(x["users"]) == u]
            if not sub:
                continue
            summary.append(
                {
                    "strategy": strat,
                    "users": u,
                    "n": len(sub),
                    "decoded_completion_ratio": mean(x["decoded_completion_ratio"] for x in sub),
                    "component_reuse_ratio": mean(x["component_reuse_ratio"] for x in sub),
                    "bandwidth_per_completed_visible": mean(x["bandwidth_per_completed_visible"] for x in sub),
                    "Rq": mean(x["Rq"] for x in sub),
                    "U": mean(x["U"] for x in sub),
                }
            )
    write_csv(OUT / "completion_analysis_by_users.csv", summary)

    tex = [
        r"\begin{tabular}{lrrr}",
        r"\hline",
        r"Strategy (users) & Decoded completion & Reuse $R_o$ & Shared bytes / completed slot \\",
        r"\hline",
    ]
    for r in summary:
        if int(r["users"]) not in (20, 60, 100):
            continue
        tex.append(
            f"{r['strategy']} ({r['users']}) & {r['decoded_completion_ratio']:.3f} & "
            f"{r['component_reuse_ratio']:.3f} & {r['bandwidth_per_completed_visible']:.2e} \\\\"
        )
    tex += [r"\hline", r"\end{tabular}", ""]
    (OUT / "completion_analysis.tex").write_text("\n".join(tex))

    def series(metric):
        ys = {}
        for strat in ("MD2G-Cast", "Heuristic", "Clustering", "MoQ Unicast"):
            ys[strat] = [next((s[metric] for s in summary if s["strategy"] == strat and s["users"] == u), np.nan) for u in USERS]
        return ys

    styles = {
        "MD2G-Cast": ("#2171B5", "-", "o"),
        "Heuristic": ("#D94801", ":", "s"),
        "Clustering": ("#238B45", "-.", "^"),
        "MoQ Unicast": ("#6A51A3", "--", "v"),
    }
    fig, ax = plt.subplots(figsize=(7.0, 2.35))
    for strat, (c, ls, mk) in styles.items():
        ax.plot(USERS, series("decoded_completion_ratio")[strat], color=c, ls=ls, marker=mk, lw=1.8, ms=6, label=strat)
    ax.set_xticks(USERS)
    ax.set_xlabel("Number of users")
    ax.set_ylabel("Decoded completion ratio")
    ax.set_ylim(0.0, 1.05)
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.18), fontsize=8)
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.22, top=0.82)
    fig.savefig(OUT / "completion_vs_users.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 2.35))
    for strat, (c, ls, mk) in styles.items():
        ys = np.array(series("bandwidth_per_completed_visible")[strat], dtype=float)
        ax.plot(USERS, ys / 1e6, color=c, ls=ls, marker=mk, lw=1.8, ms=6, label=strat)
    ax.set_xticks(USERS)
    ax.set_xlabel("Number of users")
    ax.set_ylabel("Shared bytes per completed slot (×10⁶)")
    ax.grid(True, axis="y", alpha=0.35)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.18), fontsize=8)
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.22, top=0.82)
    fig.savefig(OUT / "bandwidth_per_completion.pdf")
    plt.close(fig)
    print(f"Wrote {OUT} n={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
