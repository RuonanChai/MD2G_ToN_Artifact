#!/usr/bin/env python3
"""Shared V6 visual grammar. Profile labels + Rb–U redesign. No scientific values."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from _fig_evidence import SAME_STRATEGIES, STRATEGY_LABEL
from _fig_v3 import (
    C,
    COL_W,
    COL_W_MAX,
    LS,
    MK,
    NET_PROFILE_LABEL,
    TP_PANEL_W,
    TP_PANEL_W_MAX,
    apply_v3,
    legend_above,
    pad_lim,
    profile_label,
    save_pdf,
    style_ax,
)

COMPARABLE_TP_NETS = ("4g", "5g", "default_mix")
TRADEOFF_NETS = ("4g", "5g", "wifi", "fiber_optic", "default_mix")
USER_LOADS = [20, 60, 100]

TP_MS = 5.4
TP_LW = {s: (2.7 if s == "MD2G_COMPONENT" else 1.95) for s in SAME_STRATEGIES}

# Trade-off focal encoding (ONLY for Rb–U scatter)
MD2G_STAR_FACE = "#D7191C"
MD2G_STAR_EDGE = "#333333"
TRADE_SIZE = {20: 75, 60: 105, 100: 140}
TRADE_BASE_ALPHA = 0.78
TRADE_RULE_C = "#8E7CC3"
TRADE_MK = {
    "HV3_COMPONENT": "s",
    "CLUSTERING_COMPONENT": "^",
    "RULE_COMPONENT": "D",
}
TRADE_C = {
    "HV3_COMPONENT": "#E69F00",
    "CLUSTERING_COMPONENT": "#009E73",
    "RULE_COMPONENT": TRADE_RULE_C,
}
# Landscape at intended 1×3 Discussion panel width (~2.20–2.25 in)
TRADE_FIGSIZE = (2.25, 2.40)


def _throughput_cells(network: str) -> dict[int, dict[str, list[float]]]:
    from _fig_evidence import load_rows, throughput_mbps

    rows = [r for r in load_rows("dev.json") if r.get("network") == network]
    aggregated: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.get("strategy") not in SAME_STRATEGIES:
            continue
        tp = throughput_mbps(r)
        if tp is None:
            continue
        aggregated[int(r["users"])][r["strategy"]].append(tp)
    return aggregated


def throughput_network_range(network: str) -> tuple[float, float]:
    from _fig_evidence import mean_std

    aggregated = _throughput_cells(network)
    lo = hi = None
    for u in USER_LOADS:
        for s in SAME_STRATEGIES:
            vals = aggregated[u][s]
            if not vals:
                raise SystemExit(f"MISSING throughput {network} u{u} {s}")
            m, _sd = mean_std(vals)
            lo = m if lo is None else min(lo, m)
            hi = m if hi is None else max(hi, m)
    return float(lo), float(hi)


def throughput_ylim_for(network: str) -> tuple[float, float]:
    if network in COMPARABLE_TP_NETS:
        lo, hi = zip(*(throughput_network_range(n) for n in COMPARABLE_TP_NETS))
        return pad_lim(min(lo), max(hi), frac=0.07)
    lo, hi = throughput_network_range(network)
    return pad_lim(lo, hi, frac=0.07)


def plot_throughput_network(network: str, out_pdf, ylim=None, *, show_legend: bool | None = None) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    from _fig_evidence import mean_std, require_frozen_evidence

    require_frozen_evidence()
    aggregated = _throughput_cells(network)
    series = {}
    for s in SAME_STRATEGIES:
        means = []
        for u in USER_LOADS:
            vals = aggregated[u][s]
            if not vals:
                raise SystemExit(f"MISSING throughput {network} u{u} {s}")
            m, _sd = mean_std(vals)
            means.append(m)
        series[s] = means
    if ylim is None:
        ylim = throughput_ylim_for(network)
    # Main-text trio: no per-panel legend (shared legend lives on 1×3 composition)
    if show_legend is None:
        show_legend = network not in COMPARABLE_TP_NETS
    apply_v3()
    fig, ax = plt.subplots(figsize=(TP_PANEL_W, 2.05))
    xs = np.asarray(USER_LOADS, dtype=float)
    for s in SAME_STRATEGIES:
        ax.plot(
            xs,
            series[s],
            color=C[s],
            linestyle=LS[s],
            linewidth=TP_LW[s],
            marker=MK[s],
            markersize=TP_MS,
            markeredgecolor="0.2",
            markeredgewidth=0.25,
            label=STRATEGY_LABEL[s] if show_legend else "_nolegend_",
            zorder=4 if s == "MD2G_COMPONENT" else 3,
        )
    ax.set_xlabel("Number of users")
    ax.set_ylabel("Shared-root TX (Mbps)")
    y0, y1 = ylim
    ax.set_ylim(y0, y1 + 0.16 * (y1 - y0))
    ax.set_xticks(USER_LOADS)
    style_ax(ax)
    if show_legend:
        legend_above(ax, ncol=2, fontsize=9.0)
    profile_label(ax, NET_PROFILE_LABEL[network], loc="upper center")
    save_pdf(fig, out_pdf, max_width_in=TP_PANEL_W_MAX)


def family_rb_u_limits() -> tuple[tuple[float, float], tuple[float, float]]:
    from _fig_evidence import load_rows, mean_std

    rbs, us = [], []
    rows = [
        r
        for r in load_rows("dev.json")
        if r.get("network") in TRADEOFF_NETS and r.get("strategy") in SAME_STRATEGIES
    ]
    by = defaultdict(lambda: {"Rb": [], "U": []})
    for r in rows:
        if r.get("Rb") is None or r.get("U") is None:
            continue
        by[(r["strategy"], int(r["users"]), r["network"])]["Rb"].append(float(r["Rb"]))
        by[(r["strategy"], int(r["users"]), r["network"])]["U"].append(float(r["U"]))
    for rec in by.values():
        if rec["Rb"] and rec["U"]:
            rbs.append(mean_std(rec["Rb"])[0])
            us.append(mean_std(rec["U"])[0])
    if not rbs:
        raise SystemExit("MISSING_TRADEOFF_FAMILY")
    return pad_lim(min(rbs), max(rbs), frac=0.07), pad_lim(min(us), max(us), frac=0.07)


def _corner_occupancy(ax, pts_data, corner: str, box_w=0.28, box_h=0.22) -> int:
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    if corner == "lower right":
        xf0, xf1, yf0, yf1 = 1.0 - box_w, 1.0, 0.0, box_h
    elif corner == "upper right":
        xf0, xf1, yf0, yf1 = 1.0 - box_w, 1.0, 1.0 - box_h, 1.0
    elif corner == "lower left":
        xf0, xf1, yf0, yf1 = 0.0, box_w, 0.0, box_h
    else:
        xf0, xf1, yf0, yf1 = 0.0, box_w, 1.0 - box_h, 1.0
    x0 = xlim[0] + xf0 * (xlim[1] - xlim[0])
    x1 = xlim[0] + xf1 * (xlim[1] - xlim[0])
    y0 = ylim[0] + yf0 * (ylim[1] - ylim[0])
    y1 = ylim[0] + yf1 * (ylim[1] - ylim[0])
    n = 0
    for x, y in pts_data:
        if x0 <= x <= x1 and y0 <= y <= y1:
            n += 1
    return n


def _better_candidates():
    # (xy tip upper-left, xytext start lower-right) in axes fraction
    return [
        ((0.17, 0.84), (0.29, 0.72)),
        ((0.14, 0.88), (0.26, 0.76)),
        ((0.20, 0.86), (0.32, 0.74)),
        ((0.12, 0.82), (0.24, 0.70)),
    ]


def _arrow_box_clear(pts_axes_frac, xy, xytext, pad=0.04) -> bool:
    """Reject if any data point (axes frac) near the Better cue bounding box."""
    xs = [xy[0], xytext[0]]
    ys = [xy[1], xytext[1]]
    x0, x1 = min(xs) - pad, max(xs) + pad
    y0, y1 = min(ys) - pad, max(ys) + pad
    for x, y in pts_axes_frac:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return False
    return True


def _profile_label_slots():
    """Deterministic axes-fraction candidates (prefer upper-left, avoid crowded mid)."""
    return [
        ("upper left", 0.03, 0.97, "left", "top"),
        ("upper mid-left", 0.03, 0.86, "left", "top"),
        ("lower left", 0.03, 0.08, "left", "bottom"),
        ("lower right", 0.97, 0.08, "right", "bottom"),
        ("upper right", 0.97, 0.97, "right", "top"),
        ("upper mid-right", 0.97, 0.86, "right", "top"),
        ("mid right", 0.97, 0.55, "right", "center"),
        ("mid left", 0.03, 0.42, "left", "center"),
    ]


def _label_bbox_axes(x, y, ha, va, text: str) -> tuple[float, float, float, float]:
    """Approximate axes-fraction text bbox (deterministic; no canvas measure)."""
    tw = max(0.22, 0.0195 * len(text))
    th = 0.085
    if ha == "left":
        x0, x1 = x, x + tw
    elif ha == "right":
        x0, x1 = x - tw, x
    else:
        x0, x1 = x - tw / 2, x + tw / 2
    if va == "top":
        y0, y1 = y - th, y
    elif va == "bottom":
        y0, y1 = y, y + th
    else:
        y0, y1 = y - th / 2, y + th / 2
    return x0, x1, y0, y1


def _label_collides(pts_af, x, y, ha="left", va="top", text="", pad=0.06) -> bool:
    """True if label bbox intersects inflated data markers, trajectories, or Better cue."""
    x0, x1, y0, y1 = _label_bbox_axes(x, y, ha, va, text or "XXXX")
    mark_r = 0.095  # large star/diamond visual radius in axes fraction
    for px, py in pts_af:
        cx = min(max(px, x0), x1)
        cy = min(max(py, y0), y1)
        if ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 <= mark_r + pad:
            return True
    # Avoid Better cue zone
    if x0 < 0.42 and x1 > 0.06 and y0 < 0.97 and y1 > 0.60:
        return True
    return False


def _md2g_overlaps_baseline(md_pt, base_pts, tol_frac, xlim, ylim) -> bool:
    mx, my, _u = md_pt
    xspan = xlim[1] - xlim[0]
    yspan = ylim[1] - ylim[0]
    for bx, by, _bu in base_pts:
        dx = abs(mx - bx) / xspan
        dy = abs(my - by) / yspan
        # Visually indistinguishable if within rendered-marker tolerance (euclid or both axes)
        if (dx * dx + dy * dy) ** 0.5 <= tol_frac or (dx <= tol_frac and dy <= tol_frac):
            return True
    return False


def plot_rb_u_tradeoff(network: str, out_pdf) -> None:
    """Trade-off scatter: open red star on overlap; collision-free profile label; quiet Better."""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    from _fig_evidence import load_rows, mean_std, require_frozen_evidence

    require_frozen_evidence()
    rows = [r for r in load_rows("dev.json") if r.get("network") == network and r.get("strategy") in SAME_STRATEGIES]
    if not rows:
        raise SystemExit(f"MISSING_TRADEOFF_NETWORK: {network}")
    by = defaultdict(lambda: {"Rb": [], "U": []})
    for r in rows:
        if r.get("Rb") is None or r.get("U") is None:
            continue
        by[(r["strategy"], int(r["users"]))]["Rb"].append(float(r["Rb"]))
        by[(r["strategy"], int(r["users"]))]["U"].append(float(r["U"]))

    apply_v3()
    fig, ax = plt.subplots(figsize=(2.28, 2.90))

    all_rb, all_u, all_pts = [], [], []
    series_pts: dict[str, list[tuple[float, float, int]]] = {}
    for s in SAME_STRATEGIES:
        pts = []
        for u in USER_LOADS:
            rec = by[(s, u)]
            if not rec["Rb"]:
                raise SystemExit(f"MISSING_POINTS {network} {s} u{u}")
            xr = mean_std(rec["Rb"])[0]
            yu = mean_std(rec["U"])[0]
            pts.append((xr, yu, u))
            all_rb.append(xr)
            all_u.append(yu)
            all_pts.append((xr, yu))
        series_pts[s] = pts
    xlim = pad_lim(min(all_rb), max(all_rb), frac=0.07)
    ylim = pad_lim(min(all_u), max(all_u), frac=0.07)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)

    for s in SAME_STRATEGIES:
        pts = series_pts[s]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if s == "MD2G_COMPONENT":
            ax.plot(xs, ys, color="#7A7A7A", linestyle="-", linewidth=1.0, alpha=0.42, zorder=2)
        else:
            ax.plot(xs, ys, color=TRADE_C[s], linestyle=LS[s], linewidth=0.9, alpha=0.38, zorder=2)

    base_pts = []
    for s in SAME_STRATEGIES:
        if s == "MD2G_COMPONENT":
            continue
        for x, y, u in series_pts[s]:
            base_pts.append((x, y, u))
            ax.scatter(
                [x], [y], s=TRADE_SIZE[u] * 0.55, c=TRADE_C[s], marker=TRADE_MK[s],
                edgecolors="0.25", linewidths=0.35, alpha=TRADE_BASE_ALPHA, zorder=3,
            )

    # MD2G: open star if visually overlapping a baseline; else filled
    for pt in series_pts["MD2G_COMPONENT"]:
        x, y, u = pt
        overlap = _md2g_overlaps_baseline(pt, base_pts, tol_frac=0.055, xlim=xlim, ylim=ylim)
        if overlap:
            ax.scatter(
                [x], [y], s=TRADE_SIZE[u], facecolors="none", edgecolors=MD2G_STAR_FACE,
                marker="*", linewidths=1.4, zorder=7,
            )
        else:
            ax.scatter(
                [x], [y], s=TRADE_SIZE[u], c=MD2G_STAR_FACE, marker="*",
                edgecolors=MD2G_STAR_EDGE, linewidths=0.6, zorder=6,
            )

    xspan = xlim[1] - xlim[0]
    yspan = ylim[1] - ylim[0]
    pts_af = [((x - xlim[0]) / xspan, (y - ylim[0]) / yspan) for x, y in all_pts]

    # Quieter Better cue (~15–20% less prominent)
    placed = False
    for xy, xytext in _better_candidates():
        if _arrow_box_clear(pts_af, xy, xytext, pad=0.045):
            ax.annotate(
                "Better", xy=xy, xytext=xytext, xycoords="axes fraction", textcoords="axes fraction",
                fontsize=10.0, fontstyle="italic", color="#666666",
                arrowprops=dict(arrowstyle="-|>", color="#777777", lw=0.7, mutation_scale=6.5, shrinkA=1, shrinkB=1),
                zorder=8,
            )
            placed = True
            break
    if not placed:
        ax.annotate(
            "Better", xy=(0.12, 0.90), xytext=(0.22, 0.80), xycoords="axes fraction", textcoords="axes fraction",
            fontsize=10.0, fontstyle="italic", color="#666666",
            arrowprops=dict(arrowstyle="-|>", color="#777777", lw=0.7, mutation_scale=6.5, shrinkA=1, shrinkB=1),
            zorder=8,
        )

    ax.set_xlabel(r"$R_b$", fontsize=10.0)
    ax.set_ylabel("System utility $U$", fontsize=10.0)
    style_ax(ax, ygrid=True)
    ax.tick_params(labelsize=9.5)

    # Deterministic profile label: prefer upper-left; verified empty fallback corners
    label = NET_PROFILE_LABEL[network]
    for _name, lx, ly, ha, va in _profile_label_slots():
        if _label_collides(pts_af, lx, ly, ha=ha, va=va, text=label):
            continue
        ax.text(
            lx, ly, label, transform=ax.transAxes, fontsize=10.0,
            fontweight="bold", color="0.25", ha=ha, va=va, zorder=10, clip_on=False,
        )
        break
    else:
        # last resort: lower-right inset (away from Better + high-U cluster)
        ax.text(
            0.97, 0.08, label, transform=ax.transAxes, fontsize=10.0,
            fontweight="bold", color="0.25", ha="right", va="bottom", zorder=10, clip_on=False,
        )

    strat_handles = [
        Line2D([0], [0], marker="*", color="none", markerfacecolor=MD2G_STAR_FACE, markeredgecolor=MD2G_STAR_EDGE,
               markeredgewidth=0.6, markersize=9, label="MD2G"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor=TRADE_C["HV3_COMPONENT"], markeredgecolor="0.25",
               markersize=5.5, alpha=TRADE_BASE_ALPHA, label="Heur."),
        Line2D([0], [0], marker="^", color="none", markerfacecolor=TRADE_C["CLUSTERING_COMPONENT"], markeredgecolor="0.25",
               markersize=6, alpha=TRADE_BASE_ALPHA, label="Clust."),
        Line2D([0], [0], marker="D", color="none", markerfacecolor=TRADE_C["RULE_COMPONENT"], markeredgecolor="0.25",
               markersize=5, alpha=TRADE_BASE_ALPHA, label="Rule"),
    ]
    fig.legend(
        handles=strat_handles, loc="upper center", bbox_to_anchor=(0.58, 0.995), ncol=4, frameon=False,
        fontsize=9.0, handlelength=1.0, columnspacing=0.4, handletextpad=0.2, borderaxespad=0.0,
    )

    size_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="0.45", markeredgecolor="0.25", markersize=ms, label=str(u))
        for u, ms in ((20, 4.5), (60, 6.0), (100, 7.5))
    ]
    # Second legend row under strategies — fully inside MediaBox (not below xlabel)
    fig.legend(
        handles=size_handles, loc="upper center", bbox_to_anchor=(0.58, 0.925), ncol=3,
        title="Users", title_fontsize=9.0, fontsize=9.0, frameon=False, handletextpad=0.2, columnspacing=0.45,
    )
    fig.subplots_adjust(top=0.80, bottom=0.16, left=0.24, right=0.98)
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, format="pdf", bbox_inches=None, pad_inches=0.0)
    plt.close(fig)
