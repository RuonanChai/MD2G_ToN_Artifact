#!/usr/bin/env python3
"""H2 cross-stack DASH — ACM pair-4 compact. MD2G / GROOT / Rolling."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import complete_yticks, pair_fig, pair_legend, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import load_cross_stack_dash_u, require_frozen_evidence  # noqa: E402
from _fig_v3 import style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "H2_Cross_Stack_DASH.pdf"
USER_COUNTS = [20, 60]
COLORS = {"MD2G": "#0072B2", "GROOT": "#56B4E9", "Rolling": "#E69F00"}
BAR_W = 0.22
METHODS = ("MD2G", "GROOT", "Rolling")


def _means() -> dict[int, dict[str, float]]:
    rows = load_cross_stack_dash_u()
    dash: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    md2g_unique: dict[int, dict[tuple, float]] = defaultdict(dict)
    for r in rows:
        u = int(r["users"])
        dash[u][r["strategy"]].append(float(r["U"]))
        if r.get("MD2G_U") is not None:
            key = (r["content"], r["network"], u, int(r["seed"]))
            md2g_unique[u][key] = float(r["MD2G_U"])
    out: dict[int, dict[str, float]] = {}
    for u in USER_COUNTS:
        out[u] = {
            "MD2G": sum(md2g_unique[u].values()) / len(md2g_unique[u]),
            "GROOT": sum(dash[u]["groot"]) / len(dash[u]["groot"]),
            "Rolling": sum(dash[u]["rolling"]) / len(dash[u]["rolling"]),
        }
        if len(md2g_unique[u]) != 12:
            raise SystemExit(f"BAD_MD2G_N u{u}={len(md2g_unique[u])}")
        if len(dash[u]["groot"]) != 12 or len(dash[u]["rolling"]) != 12:
            raise SystemExit(f"BAD_DASH_N u{u}")
        if not (out[u]["MD2G"] > out[u]["GROOT"] and out[u]["MD2G"] > out[u]["Rolling"]):
            raise SystemExit(f"H2_MD2G_NOT_HIGHER u{u} {out[u]}")
    return out


def main() -> int:
    require_frozen_evidence()
    data = _means()
    fig, ax = pair_fig(4)
    x = np.arange(len(USER_COUNTS), dtype=float)
    offsets = {"MD2G": -BAR_W, "GROOT": 0.0, "Rolling": BAR_W}
    for m in METHODS:
        vals = [data[u][m] for u in USER_COUNTS]
        ax.bar(
            x + offsets[m], vals, width=BAR_W, color=COLORS[m],
            edgecolor="0.15", linewidth=0.3, zorder=3,
        )
    ax.set_xticks(x)
    ax.set_xticklabels([str(u) for u in USER_COUNTS])
    place_xy_labels(ax, "Users", "System utility $U$")
    all_v = [data[u][m] for u in USER_COUNTS for m in METHODS]
    ymax = max(all_v)
    ax.set_ylim(0.0, ymax * 1.12)
    ax.set_xlim(-0.55, len(USER_COUNTS) - 0.45)
    style_ax(ax, ygrid=True)
    complete_yticks(ax, 0.2)
    handles = [
        Patch(facecolor=COLORS[m], edgecolor="0.15", linewidth=0.3, label=m) for m in METHODS
    ]
    pair_legend(fig, handles, pair_id=4, ncol=3, handlelength=0.55, columnspacing=0.18, handletextpad=0.10)
    save_pair_pdf(fig, OUT, 4)
    print(f"Wrote {OUT} data={data}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
