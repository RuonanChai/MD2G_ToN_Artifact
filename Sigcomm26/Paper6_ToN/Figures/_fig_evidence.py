#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Frozen final-evidence loader + SIGCOMM style constants (not a figure generator)."""
import json
import statistics
from collections import defaultdict
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
FIG = TON / "Figures"
FINAL = TON / "final"
ART_DASH = TON / "artifacts" / "command153_cross_stack_dash"

REQUIRED_TOKENS = [
    REPO / "state" / "TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B.json",
    REPO / "state" / "TON_COMPONENT_MD2G_EVIDENCE_PACKAGE_READY.json",
    REPO / "state" / "COMMAND153_LOOT_HOLDOUT_FROZEN.json",
    FINAL / "COMMAND153_PRIMARY_STATS.json",
    REPO / "state" / "COMMAND153_CLAIM_EVIDENCE_MATRIX.json",
]

SAME_STRATEGIES = [
    "MD2G_COMPONENT",
    "HV3_COMPONENT",
    "CLUSTERING_COMPONENT",
    "RULE_COMPONENT",
]

MOQ_DELIVERY = ["MD2G_COMPONENT", "MOQ_UNICAST_COMPONENT"]

STRATEGY_LABEL = {
    "MD2G_COMPONENT": "MD2G",
    "HV3_COMPONENT": "Heuristic",
    "CLUSTERING_COMPONENT": "Clustering",
    "RULE_COMPONENT": "Rule",
    "MOQ_UNICAST_COMPONENT": "MOQ Unicast",
    "groot": "GROOT",
    "rolling": "Rolling",
    "groot_dash": "GROOT",
}

QOE_COLORS = {
    "MD2G_COMPONENT": "#FBF0C3",
    "HV3_COMPONENT": "#54686F",
    "CLUSTERING_COMPONENT": "#E57B7F",
    "RULE_COMPONENT": "#9E3150",
    "MOQ_UNICAST_COMPONENT": "#87BBA4",
    "groot": "#87BBA4",
    "rolling": "#9E3150",
}

QOE_NETWORK_COLORS = {
    "MD2G_COMPONENT": "#A1A9D0",
    "HV3_COMPONENT": "#F0988C",
    "CLUSTERING_COMPONENT": "#7F7F7F",
    "RULE_COMPONENT": "#B883D4",
}

SCHEME1_COLORS = {
    "MD2G_COMPONENT": "#0E606B",
    "HV3_COMPONENT": "#1597A5",
    "CLUSTERING_COMPONENT": "#FFC24B",
    "RULE_COMPONENT": "#F66F69",
    "MOQ_UNICAST_COMPONENT": "#FEB3AE",
    "groot": "#FEB3AE",
    "rolling": "#F66F69",
}

COLOR_SCHEMES = {
    f"scheme{i}": SCHEME1_COLORS if i == 1 else dict(SCHEME1_COLORS)
    for i in range(1, 6)
}

NET_ORDER = ["wifi", "4g", "5g", "5g_dominant", "wifi_dominant", "default_mix", "fiber_optic"]
NET_ORDER_SIGCOMM = ["wifi", "4g", "5g", "fiber_optic", "default_mix"]
NET_LABEL = {
    "4g": "4G",
    "5g": "5G",
    "5g_dominant": "5G dom.",
    "wifi": "WiFi",
    "wifi_dominant": "WiFi dom.",
    "default_mix": "Mix",
    "fiber_optic": "Fiber",
}

U_WEIGHTS = (0.25, 0.60, 0.15)


def require_frozen_evidence() -> None:
    missing = [str(p) for p in REQUIRED_TOKENS if not p.is_file()]
    if missing:
        raise SystemExit(f"FROZEN_EVIDENCE_MISSING: {missing}")


def load_json(path: Path):
    if not path.is_file():
        raise SystemExit(f"MISSING_ARTIFACT: {path}")
    return json.loads(path.read_text())


def load_rows(name: str) -> list[dict]:
    return load_json(FINAL / "COMMAND153_FIGURE_SOURCE_DATA" / name)


def load_primary_stats() -> dict:
    return load_json(FINAL / "COMMAND153_PRIMARY_STATS.json")


def clip_u(ro: float, rq: float, rb: float) -> float:
    return max(0.0, min(1.0, U_WEIGHTS[0] * ro + U_WEIGHTS[1] * rq - U_WEIGHTS[2] * rb))


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        raise SystemExit("EMPTY_AGGREGATE")
    return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def aggregate_by_strategy(rows: list[dict], strategies: list[str] | None = None) -> dict[str, list[float]]:
    strategies = strategies or SAME_STRATEGIES
    out: dict[str, list[float]] = {s: [] for s in strategies}
    for r in rows:
        s = r.get("strategy")
        u = r.get("U")
        if s in out and u is not None:
            out[s].append(float(u))
    for s in strategies:
        if not out[s]:
            raise SystemExit(f"NO_VALID_ROWS_FOR_STRATEGY: {s}")
    return out


def aggregate_by_users_strategy(
    rows: list[dict], users_list: list[int], strategies: list[str] | None = None
) -> dict[int, dict[str, list[float]]]:
    strategies = strategies or SAME_STRATEGIES
    out: dict[int, dict[str, list[float]]] = {u: {s: [] for s in strategies} for u in users_list}
    for r in rows:
        u = int(r["users"])
        s = r.get("strategy")
        val = r.get("U")
        if u in out and s in out[u] and val is not None:
            out[u][s].append(float(val))
    return out


def aggregate_metric_by_strategy(rows: list[dict], metric: str, strategies: list[str] | None = None) -> dict[str, list[float]]:
    strategies = strategies or SAME_STRATEGIES
    out: dict[str, list[float]] = {s: [] for s in strategies}
    for r in rows:
        s = r.get("strategy")
        v = r.get(metric)
        if s in out and v is not None:
            out[s].append(float(v))
    for s in strategies:
        if not out[s]:
            raise SystemExit(f"NO_VALID_ROWS_FOR_STRATEGY: {s} metric={metric}")
    return out


def aggregate_by_network_strategy(rows: list[dict], networks: list[str], strategies: list[str] | None = None) -> dict[str, dict[str, list[float]]]:
    strategies = strategies or SAME_STRATEGIES
    out: dict[str, dict[str, list[float]]] = {n: {s: [] for s in strategies} for n in networks}
    for r in rows:
        net = r.get("network")
        s = r.get("strategy")
        v = r.get("U")
        if net in out and s in out[net] and v is not None:
            out[net][s].append(float(v))
    return out


def aggregate_stall_by_network_strategy(rows: list[dict], networks: list[str], strategies: list[str] | None = None) -> dict[str, dict[str, list[float]]]:
    strategies = strategies or SAME_STRATEGIES
    out: dict[str, dict[str, list[float]]] = {n: {s: [] for s in strategies} for n in networks}
    for r in rows:
        net = r.get("network")
        s = r.get("strategy")
        v = r.get("stall_last")
        if net in out and s in out[net] and v is not None:
            out[net][s].append(float(v))
    return out


def throughput_mbps(row: dict) -> float | None:
    pp = row.get("physical_pressure") or {}
    tx = pp.get("raw_protocol_inclusive_tx_bytes")
    n = int(pp.get("n_intervals") or 0)
    if tx is None or n <= 0:
        return None
    return float(tx) * 8.0 / (n * 1_000_000.0)


def matched_delta_by_users(rows: list[dict]) -> dict[int, list[float]]:
    groups: dict[tuple, dict[str, float]] = defaultdict(dict)
    for r in rows:
        key = (r.get("network"), r.get("users"), r.get("seed"))
        s = r.get("strategy")
        if s in SAME_STRATEGIES and r.get("U") is not None:
            groups[key][s] = float(r["U"])
    by_u: dict[int, list[float]] = defaultdict(list)
    for (_net, users, _seed), strats in groups.items():
        md = strats.get("MD2G_COMPONENT")
        base = [strats[s] for s in ("HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT") if s in strats]
        if md is None or not base:
            continue
        by_u[int(users)].append(md - max(base))
    return by_u


def matched_blocks_delta_by_users() -> dict[int, list[float]]:
    mb = load_rows("matched_blocks.json")
    by_u: dict[int, list[float]] = defaultdict(list)
    for r in mb:
        by_u[int(r["users"])].append(float(r["delta_U"]))
    return by_u


BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 153
WTL_NOISE_ABS = 0.03

# Manuscript heatmap row order (not sorted by MD2G performance).
HEATMAP_NET_ORDER = [
    "4g",
    "5g",
    "wifi",
    "fiber_optic",
    "default_mix",
    "wifi_dominant",
    "5g_dominant",
]
HEATMAP_NET_LABEL = {
    "4g": "4G",
    "5g": "5G",
    "wifi": "Wi-Fi",
    "fiber_optic": "Fiber Optic",
    "default_mix": "Default Mix",
    "wifi_dominant": "Wi-Fi Dominant",
    "5g_dominant": "5G Dominant",
}

STRATEGY_MARKERS = {
    "MD2G_COMPONENT": "o",
    "HV3_COMPONENT": "s",
    "CLUSTERING_COMPONENT": "^",
    "RULE_COMPONENT": "D",
    "MOQ_UNICAST_COMPONENT": "v",
    "groot": "P",
    "rolling": "X",
    "md2g": "o",
}
STRATEGY_LINESTYLES = {
    "MD2G_COMPONENT": "-",
    "HV3_COMPONENT": "--",
    "CLUSTERING_COMPONENT": "-.",
    "RULE_COMPONENT": ":",
    "MOQ_UNICAST_COMPONENT": (0, (3, 1, 1, 1)),
    "groot": "--",
    "rolling": ":",
    "md2g": "-",
}
MECH_COLORS = {
    "Ro": "#87BBA4",
    "Rq": "#0E606B",
    "Rb": "#9E3150",
}


def bootstrap_ci95(values, n_boot: int = BOOTSTRAP_N, seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    """Percentile 95% CI of the mean. Resample the provided list with replacement.

    Indexing matches the frozen paper-pack convention (seed 153, n_boot=10000).
    """
    import random

    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0:
        raise SystemExit("EMPTY_BOOTSTRAP")
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        s = [vals[rng.randrange(n)] for _ in range(n)]
        means.append(sum(s) / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot) - 1]
    return float(lo), float(hi)


def wtl_counts(deltas, noise: float = WTL_NOISE_ABS) -> tuple[int, int, int]:
    w = t = l = 0
    for d in deltas:
        if d > noise:
            w += 1
        elif d < -noise:
            l += 1
        else:
            t += 1
    return w, t, l


def match_same_substrate_blocks(rows: list[dict]) -> list[dict]:
    """Matched blocks from cell rows. Strongest = max U among HV3/CLUSTERING/RULE."""
    groups: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        s = r.get("strategy")
        if s not in SAME_STRATEGIES and s != "MOQ_UNICAST_COMPONENT":
            continue
        key = (r.get("content"), r.get("network"), int(r["users"]), int(r["seed"]))
        groups[key][s] = r
    out = []
    for (content, network, users, seed), strat in groups.items():
        md = strat.get("MD2G_COMPONENT")
        same = [strat[s] for s in ("HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT") if s in strat]
        if md is None or not same or md.get("U") is None:
            continue
        strongest = max(same, key=lambda x: float(x["U"]))
        d_u = float(md["U"]) - float(strongest["U"])
        rec = {
            "content": content,
            "network": network,
            "users": int(users),
            "seed": int(seed),
            "delta_U": d_u,
            "MD2G_U": float(md["U"]),
            "strongest": strongest["strategy"],
            "strongest_U": float(strongest["U"]),
        }
        if md.get("Ro_component") is not None and strongest.get("Ro_component") is not None:
            rec["delta_Ro"] = float(md["Ro_component"]) - float(strongest["Ro_component"])
            rec["contrib_Ro"] = 0.25 * rec["delta_Ro"]
        if md.get("Rq") is not None and strongest.get("Rq") is not None:
            rec["delta_Rq"] = float(md["Rq"]) - float(strongest["Rq"])
            rec["contrib_Rq"] = 0.60 * rec["delta_Rq"]
        if md.get("Rb") is not None and strongest.get("Rb") is not None:
            rec["delta_Rb"] = float(md["Rb"]) - float(strongest["Rb"])
            rec["contrib_Rb"] = -0.15 * rec["delta_Rb"]
        if md.get("weak_user_Rq") is not None:
            rec["md2g_weak_user_Rq"] = float(md["weak_user_Rq"])
        if strongest.get("weak_user_Rq") is not None:
            rec["strong_weak_user_Rq"] = float(strongest["weak_user_Rq"])
        out.append(rec)
    return out


def apply_sigcomm_rcparams() -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.size": 10,
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.linewidth": 0.9,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8,
            "legend.frameon": True,
            "legend.framealpha": 0.92,
            "legend.edgecolor": "0.75",
            "legend.fancybox": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "text.usetex": False,
        }
    )


def style_ax(ax, ygrid: bool = True) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3.5, width=0.8)
    if ygrid:
        ax.yaxis.grid(True, linestyle="-", linewidth=0.4, color="0.85", zorder=0)
        ax.set_axisbelow(True)
    ax.xaxis.grid(False)


def fig_size(kind: str = "default") -> tuple[float, float]:
    return {
        "default": (6.6, 4.2),
        "heat": (6.9, 5.1),
        "wide": (7.0, 4.4),
        "box": (6.6, 4.3),
        "forest": (6.4, 3.6),
        "dumbbell": (6.6, 4.0),
        "scatter": (6.6, 4.4),
    }.get(kind, (6.6, 4.2))


def save_pdf(fig, out_pdf: Path) -> None:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_pdf, dpi=600, bbox_inches="tight", format="pdf")
    import matplotlib.pyplot as plt

    plt.close(fig)


def dash_u_from_cell_done(body: dict) -> float | None:
    score = body.get("score") or {}
    rows = score.get("native_user_rows") or []
    if not rows:
        return None
    vals = [clip_u(float(r.get("Ro") or 0.0), float(r.get("Rq") or 0.0), float(r.get("Rb") or 0.0)) for r in rows]
    return statistics.mean(vals)


def load_cross_stack_dash_u() -> list[dict]:
    rows = []
    if not ART_DASH.is_dir():
        raise SystemExit(f"MISSING_ARTIFACT: {ART_DASH}")
    dev_index: dict[tuple, float] = {}
    for r in load_rows("dev.json"):
        if r.get("strategy") == "MD2G_COMPONENT" and r.get("U") is not None:
            dev_index[(r["content"], r["network"], int(r["users"]), int(r["seed"]))] = float(r["U"])
    for d in sorted(ART_DASH.iterdir()):
        if not d.is_dir():
            continue
        done = d / "CELL_DONE.json"
        if not done.is_file():
            continue
        body = json.loads(done.read_text())
        if not body.get("valid"):
            continue
        u_val = dash_u_from_cell_done(body)
        if u_val is None:
            continue
        key = (body["content"], body["network"], int(body["users"]), int(body["seed"]))
        dash_s = body.get("dash_strategy") or str(body.get("strategy", "")).replace("_dash", "")
        rows.append(
            {
                "key": body["key"],
                "strategy": dash_s,
                "content": body["content"],
                "network": body["network"],
                "users": int(body["users"]),
                "seed": int(body["seed"]),
                "U": u_val,
                "MD2G_U": dev_index.get(key),
            }
        )
    if len(rows) < 48:
        raise SystemExit(f"CROSS_STACK_INCOMPLETE: n={len(rows)}")
    return rows
