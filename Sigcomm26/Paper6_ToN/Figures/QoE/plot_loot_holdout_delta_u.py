#!/usr/bin/env python3
"""Loot holdout — ACM pair-3 compact grouped bars. Filename kept."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import complete_yticks, pair_fig, pair_legend, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import load_rows, match_same_substrate_blocks, require_frozen_evidence  # noqa: E402
from _fig_v3 import style_ax  # noqa: E402

OUT = Path(__file__).resolve().parent / "Loot_Holdout_DeltaU_By_Users.pdf"
USER_COUNTS = [20, 60, 100]
C_MD2G = "#0072B2"
C_BASE = "#595959"
BAR_W = 0.32


def main() -> int:
    require_frozen_evidence()
    blocks = match_same_substrate_blocks(load_rows("loot.json"))
    md2g_u, base_u = [], []
    for u in USER_COUNTS:
        rows = [b for b in blocks if int(b["users"]) == u]
        if len(rows) != 21:
            raise SystemExit(f"MISSING_LOOT_MATCHED u{u} n={len(rows)}")
        md2g_u.append(sum(b["MD2G_U"] for b in rows) / len(rows))
        base_u.append(sum(b["strongest_U"] for b in rows) / len(rows))
        du = md2g_u[-1] - base_u[-1]
        if u == 20 and du >= 0:
            raise SystemExit(f"LOOT_U20_NOT_TRAILING du={du}")
        if u in (60, 100) and du <= 0:
            raise SystemExit(f"LOOT_U{u}_NOT_LEADING du={du}")

    fig, ax = pair_fig(3)
    x = np.arange(len(USER_COUNTS), dtype=float)
    ax.bar(x - BAR_W / 2, md2g_u, width=BAR_W, color=C_MD2G, edgecolor="0.15", linewidth=0.3, zorder=3)
    ax.bar(x + BAR_W / 2, base_u, width=BAR_W, color=C_BASE, edgecolor="0.15", linewidth=0.3, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels([str(u) for u in USER_COUNTS])
    place_xy_labels(ax, "Users", "System utility $U$")
    ymin = min(md2g_u + base_u)
    ymax = max(md2g_u + base_u)
    span = ymax - ymin if ymax > ymin else 0.2
    # Zoomed y: u20 loss vs u60/u100 gain stays visible at compact height.
    ax.set_ylim(max(0.0, ymin - 0.08 * span), ymax + 0.10 * span)
    ax.set_xlim(-0.55, len(USER_COUNTS) - 0.45)
    style_ax(ax, ygrid=True)
    complete_yticks(ax, 0.1)
    handles = [
        Patch(facecolor=C_MD2G, edgecolor="0.15", linewidth=0.3, label="MD2G"),
        Patch(facecolor=C_BASE, edgecolor="0.15", linewidth=0.3, label="Baseline"),
    ]
    pair_legend(fig, handles, pair_id=3, ncol=2, handlelength=0.95)
    save_pair_pdf(fig, OUT, 3)
    print(f"Wrote {OUT} md2g={md2g_u} strongest={base_u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
