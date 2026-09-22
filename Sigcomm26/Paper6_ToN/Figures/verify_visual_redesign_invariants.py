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

"""Verify redesigned figures against frozen COMMAND153 values. No evidence mutation."""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _fig_evidence import (  # noqa: E402
    HEATMAP_NET_ORDER,
    SAME_STRATEGIES,
    U_WEIGHTS,
    aggregate_by_strategy,
    aggregate_by_users_strategy,
    bootstrap_ci95,
    load_primary_stats,
    load_rows,
    match_same_substrate_blocks,
    matched_delta_by_users,
    mean_std,
    require_frozen_evidence,
    wtl_counts,
)

PACK = json.loads(
    Path("str(artifact_root())/Sigcomm26/Paper6_ToN/final/PAPER_REWRITE_INPUT_PACK.json").read_text()
)


def close(a, b, tol=1e-6):
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    require_frozen_evidence()
    fails = []

    stats = load_primary_stats()
    data = aggregate_by_strategy(load_rows("dev.json"), SAME_STRATEGIES)
    strat_pack = PACK["G_maindev"]["strategy_means"]
    for s in SAME_STRATEGIES:
        if len(data[s]) != 189:
            fails.append(f"A n={len(data[s])} {s}")
        m, _ = mean_std(data[s])
        if not close(m, strat_pack[s]["U"], 1e-9):
            fails.append(f"A mean {s} {m} vs {strat_pack[s]['U']}")

    # B. scaling means
    scale = aggregate_by_users_strategy(load_rows("scaling.json"), [10, 20, 40, 60, 100], SAME_STRATEGIES)
    sp = PACK["H_scaling"]["matched_by_users"]
    for u, rec in sp.items():
        m, _ = mean_std(scale[int(u)]["MD2G_COMPONENT"])
        if abs(m - rec["md2g_U"]) > 5e-4:
            fails.append(f"B scaling MD2G u{u} {m:.6f} vs {rec['md2g_U']}")

    # D. content forest
    by_c = defaultdict(list)
    for r in load_rows("matched_blocks.json"):
        by_c[r["content"]].append(float(r["delta_U"]))
    cpack = PACK["G_maindev"]["matched_by_content"]
    for c, rec in cpack.items():
        vals = by_c[c]
        if len(vals) != 63:
            fails.append(f"D n {c}={len(vals)}")
        mean = sum(vals) / len(vals)
        if abs(mean - rec["mean"]) > 5e-4:
            fails.append(f"D mean {c} {mean} vs {rec['mean']}")
        lo, hi = bootstrap_ci95(vals)
        clo, chi = rec["ci95"]
        if abs(lo - clo) > 2e-3 or abs(hi - chi) > 2e-3:
            fails.append(f"D CI {c} ({lo:.6f},{hi:.6f}) vs {rec['ci95']}")

    # F. Loot WTL / means
    loot_d = matched_delta_by_users(load_rows("loot.json"))
    for u, rec in PACK["I_loot"]["matched_by_users"].items():
        vals = loot_d[int(u)]
        mean = sum(vals) / len(vals)
        if abs(mean - rec["mean"]) > 5e-4:
            fails.append(f"F loot mean u{u} {mean} vs {rec['mean']}")
        wtl = wtl_counts(vals)
        if list(wtl) != rec["WTL"]:
            fails.append(f"F WTL u{u} {wtl} vs {rec['WTL']}")
        lo, hi = bootstrap_ci95(vals)
        if abs(lo - rec["ci95"][0]) > 2e-3 or abs(hi - rec["ci95"][1]) > 2e-3:
            fails.append(f"F CI u{u} ({lo:.6f},{hi:.6f}) vs {rec['ci95']}")

    # G. decomp sums to DeltaU (Loot)
    blocks = match_same_substrate_blocks(load_rows("loot.json"))
    for u in (20, 60, 100):
        c_ro = sum(b["contrib_Ro"] for b in blocks if b["users"] == u) / 21
        c_rq = sum(b["contrib_Rq"] for b in blocks if b["users"] == u) / 21
        c_rb = sum(b["contrib_Rb"] for b in blocks if b["users"] == u) / 21
        tot = sum(b["delta_U"] for b in blocks if b["users"] == u) / 21
        if abs((c_ro + c_rq + c_rb) - tot) > 1e-3:
            fails.append(f"G sum!=DeltaU u{u} {c_ro+c_rq+c_rb} vs {tot}")
        expected = PACK["I_loot"]["matched_by_users"][str(u)]["mean"]
        if abs(tot - expected) > 5e-4:
            fails.append(f"G tot u{u} {tot} vs {expected}")

    # H. unicast Ro=0
    loot_s = stats["loot_by_strategy"]
    if loot_s["MOQ_UNICAST_COMPONENT"]["Ro_component"] != 0.0:
        fails.append("H unicast Ro != 0")
    if abs(loot_s["MD2G_COMPONENT"]["U"] - PACK["I_loot"]["strategy_means_MD2G"]["U"]) > 1e-9:
        fails.append("H MD2G U drift")

    # E. heatmap n=9 per cell (3 contents × 3 seeds)
    cells = defaultdict(list)
    for r in load_rows("matched_blocks.json"):
        cells[(r["network"], int(r["users"]))].append(float(r["delta_U"]))
    for net in HEATMAP_NET_ORDER:
        for u in (20, 60, 100):
            vals = cells[(net, u)]
            if len(vals) != 9:
                fails.append(f"E n {net} u{u}={len(vals)}")

    # Weights frozen
    if U_WEIGHTS != (0.25, 0.60, 0.15):
        fails.append("U weights changed")

    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        return 1
    print("SCIENTIFIC_INVARIANT_CHECKS_PASS")
    print("A 189 cells/strategy means match pack")
    print("B scaling MD2G means match pack (tol 5e-4)")
    print("D content means + bootstrap CI match pack")
    print("E heatmap 7×3 cells n=9 each")
    print("F Loot means/CI/WTL match pack")
    print("G Loot weighted components sum to DeltaU")
    print("H unicast Ro=0; MD2G U frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
