#!/usr/bin/env python3
"""Network × load matched ΔU heatmap — wide-aspect ACM pair-2 (Fig.4).

Horizontal colorbar in the same top band as Fig.3. Same frozen matrix.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from _fig_compact import PAIR_MARGINS, pair_fig, place_xy_labels, save_pair_pdf  # noqa: E402
from _fig_evidence import HEATMAP_NET_ORDER, load_rows, require_frozen_evidence  # noqa: E402
from _fig_v3 import DELTA_CMAP, NET_PROFILE_LABEL  # noqa: E402

OUT = Path(__file__).resolve().parent / "QoE_By_Network.pdf"
USER_COUNTS = [20, 60, 100]


def main() -> int:
    require_frozen_evidence()
    cells: dict[tuple[str, int], list[float]] = defaultdict(list)
    for r in load_rows("matched_blocks.json"):
        cells[(r["network"], int(r["users"]))].append(float(r["delta_U"]))
    mat = np.zeros((len(HEATMAP_NET_ORDER), len(USER_COUNTS)))
    for i, net in enumerate(HEATMAP_NET_ORDER):
        for j, users in enumerate(USER_COUNTS):
            vals = cells[(net, users)]
            if len(vals) != 9:
                raise SystemExit(f"UNEXPECTED n {net} u{users}={len(vals)}")
            mat[i, j] = sum(vals) / len(vals)
    zabs = float(np.max(np.abs(mat)))
    fig, ax = pair_fig(2)
    im = ax.imshow(mat, cmap=DELTA_CMAP, vmin=-zabs, vmax=zabs, aspect="auto")
    ax.set_xticks(range(len(USER_COUNTS)))
    ax.set_xticklabels([str(u) for u in USER_COUNTS], fontsize=8.5)
    ax.set_yticks(range(len(HEATMAP_NET_ORDER)))
    ax.set_yticklabels([NET_PROFILE_LABEL[n] for n in HEATMAP_NET_ORDER], fontsize=7.5)
    ax.set_xlabel("")
    ax.set_ylabel("")
    place_xy_labels(ax, "Users", "")
    ax.tick_params(length=0, pad=0.8, labelsize=7.5)
    ax.tick_params(axis="x", labelsize=8.5)
    for sp in ax.spines.values():
        sp.set_visible(False)
    m = PAIR_MARGINS[2]
    # Same top band as Fig.3 legend (20/60/100).
    cax = fig.add_axes([m["left"], 0.868, m["right"] - m["left"], 0.048])
    cbar = fig.colorbar(im, cax=cax, orientation="horizontal")
    cbar.set_ticks([-0.1, 0.0, 0.1])
    cbar.ax.set_xticklabels(["-.1", "0", ".1"])
    cbar.ax.xaxis.set_ticks_position("bottom")
    cbar.ax.tick_params(labelsize=7.5, length=1.4, width=0.35, pad=1.0)
    cbar.outline.set_linewidth(0.3)
    save_pair_pdf(fig, OUT, 2)
    print(f"Wrote {OUT} zabs={zabs:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
