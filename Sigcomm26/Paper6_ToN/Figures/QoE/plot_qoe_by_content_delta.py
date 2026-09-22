#!/usr/bin/env python3
"""Content × load matched ΔU — dense ACM pair-2 (Fig.3). Same frozen means."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import pair_fig, pair_legend, save_pair_pdf  # noqa: E402
from _fig_evidence import load_rows, require_frozen_evidence  # noqa: E402
from _fig_v3 import LOAD_C, LOAD_MK, pad_lim, style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "QoE_By_Content_DeltaU.pdf"
CONTENTS = ["redandblack", "longdress", "soldier"]
LABELS = {"redandblack": "Red&Black", "longdress": "Longdress", "soldier": "Soldier"}
USER_COUNTS = [20, 60, 100]
EXPECTED_N = 21
# plot() markersize is the diameter in typographic points.
MARKER_PT = 3.5


def main() -> int:
    require_frozen_evidence()
    cells: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in load_rows("matched_blocks.json"):
        c = r.get("content")
        if c not in CONTENTS:
            continue
        cells[(c, int(r["users"]))].append(float(r["delta_U"]))

    means: dict[str, dict[int, float]] = {}
    all_v: list[float] = []
    for c in CONTENTS:
        means[c] = {}
        for u in USER_COUNTS:
            vals = cells.get((c, u), [])
            if len(vals) != EXPECTED_N:
                raise SystemExit(f"MISSING_OR_BAD_N content={c} users={u} n={len(vals)}")
            m = sum(vals) / len(vals)
            means[c][u] = m
            all_v.append(m)

    fig, ax = pair_fig(2)
    ys = list(range(len(CONTENTS)))[::-1]
    ax.axvline(0.0, color="0.25", linewidth=0.65, zorder=2)
    for yi, c in zip(ys, CONTENTS):
        xs = [means[c][u] for u in USER_COUNTS]
        ax.plot(xs, [yi] * 3, color="0.55", linewidth=0.9, zorder=2, solid_capstyle="round")
        for u, x in zip(USER_COUNTS, xs):
            ax.plot(
                [x], [yi],
                linestyle="None",
                marker=LOAD_MK[u],
                markersize=MARKER_PT,
                color=LOAD_C[u],
                markeredgecolor="0.15",
                markeredgewidth=0.40,
                zorder=4,
                clip_on=False,
            )
    ax.set_yticks(ys)
    ax.set_yticklabels([LABELS[c] for c in CONTENTS], fontsize=7.5)
    ax.set_xlabel(r"Matched $\Delta U$", fontsize=9.0, labelpad=4.0)
    ax.set_ylabel("")
    lo, hi = pad_lim(min(all_v), max(all_v), frac=0.08, include_zero=True)
    # Extra right room so Red&Black u=100 diamond is not clipped by the axes.
    ax.set_xlim(lo, hi + 0.020)
    ax.set_xticks([-0.1, 0.0, 0.1])
    ax.set_xticklabels(["-0.1", "0.0", "0.1"])
    ax.set_ylim(-0.48, len(CONTENTS) - 0.52)
    style_ax(ax, ygrid=False, xgrid=True)
    ax.tick_params(axis="y", pad=0.8, labelsize=7.5)
    ax.tick_params(axis="x", labelsize=8.5, pad=1.0)
    handles = [
        ax.plot(
            [], [], linestyle="None", marker=LOAD_MK[u], markersize=MARKER_PT,
            color=LOAD_C[u], markeredgecolor="0.15", markeredgewidth=0.40, label=str(u),
        )[0]
        for u in USER_COUNTS
    ]
    pair_legend(
        fig, handles, pair_id=2, ncol=3,
        handlelength=0.70, columnspacing=0.55, handletextpad=0.28,
    )
    save_pair_pdf(fig, OUT, 2)
    print(f"Wrote {OUT} MARKER_PT={MARKER_PT} xlim=({lo:.4f},{hi + 0.020:.4f}) means={means}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
