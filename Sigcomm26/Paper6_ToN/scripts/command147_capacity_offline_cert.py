#!/usr/bin/env python3
"""COMMAND147 P3 offline: retire 1.50 Mbps full-Rep threshold; certify DeltaR from frozen rates.

Does NOT issue COMMAND147_COMPONENT_CAPACITY_CERTIFIED (needs live estimator recert).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from command147_io import REPO, dump_analysis, dump_dual, ts  # noqa: E402
from ton_ro_component import marginal_components  # noqa: E402

DAG = json.loads((REPO / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json").read_text())
RATE = REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json"
OLD_THRESHOLD_MBPS = 1.50


def rates_mbps(cid: str) -> dict[str, float]:
    body = json.loads(RATE.read_text())
    return {t: float(body["contents"][cid][t]["steady_state_payload_mbps"]) for t in ("b0", "db1", "db2", "e1", "e2")}


def delta_r(target: list[str], active: list[str], rate: dict[str, float]) -> float:
    return sum(rate[c] for c in marginal_components(target, active))


def main() -> int:
    if not RATE.is_file():
        print(json.dumps({"pass": False, "reason": "temporal_contract_missing"}))
        return 2
    cid = "redandblack"
    r = rates_mbps(cid)
    b1, b2, b3 = DAG["base_prefixes"]["B1"], DAG["base_prefixes"]["B2"], DAG["base_prefixes"]["B3"]
    b3e1 = DAG["logical_states"]["Rep8"]["C"]
    b3e2 = DAG["logical_states"]["Rep9"]["C"]
    cases = {
        "B1_to_B2_adds_db1_only": abs(delta_r(b2, b1, r) - r["db1"]) < 1e-9,
        "B2_to_B3_adds_db2_only": abs(delta_r(b3, b2, r) - r["db2"]) < 1e-9,
        "B3_to_B3E1_adds_e1_only": abs(delta_r(b3e1, b3, r) - r["e1"]) < 1e-9,
        "B3E1_to_B3E1E2_adds_e2_only": abs(delta_r(b3e2, b3e1, r) - r["e2"]) < 1e-9,
        "already_active_e1_zero_marginal": abs(delta_r(b3e1, b3e1, r)) < 1e-9,
        "old_1_50_mbps_retired": min(r.values()) > OLD_THRESHOLD_MBPS * 5,
    }
    thresholds = {
        "db1": r["db1"],
        "db2": r["db2"],
        "e1": r["e1"],
        "e2": r["e2"],
        "b0": r["b0"],
        "note": "live estimator cases must be generated below/near/above THESE rates, never 1.50 Mbps",
        "retired_fullrep_threshold_mbps": OLD_THRESHOLD_MBPS,
    }
    offline_pass = all(cases.values())
    contract = {
        "ts": ts(),
        "token": "COMMAND147_COMPONENT_CAPACITY_CONTRACT",
        "status": "OFFLINE_DELTAR_PASS_LIVE_ESTIMATOR_PENDING" if offline_pass else "FAIL",
        "DeltaR": "sum rate(c) for c in C(r) \\ A_g",
        "forbid_mininet_configured_bandwidth_as_policy_input": True,
        "retired_full_representation_threshold_mbps": OLD_THRESHOLD_MBPS,
        "marginal_component_thresholds_mbps": {c: rates_mbps(c) for c in ("redandblack", "longdress", "soldier", "loot")},
        "loot_network_holdout_sealed": True,
        "live_estimator_certified": False,
    }
    dump_dual("COMMAND147_COMPONENT_CAPACITY_CONTRACT.json", contract)
    analysis = {
        "ts": ts(),
        "token": "COMMAND147_COMPONENT_CAPACITY_OFFLINE",
        "pass": offline_pass,
        "cases": cases,
        "thresholds_mbps": thresholds,
        "redandblack_rates_mbps": r,
        "live_estimator_pending": True,
        "COMMAND147_COMPONENT_CAPACITY_CERTIFIED": False,
        "loot_network_holdout_sealed": True,
    }
    dump_analysis("COMMAND147_COMPONENT_CAPACITY_CERTIFICATION.json", analysis)
    dump_dual("COMMAND147_COMPONENT_CAPACITY_OFFLINE_PASS.json", {"ts": ts(), "token": "COMMAND147_COMPONENT_CAPACITY_OFFLINE_PASS", "pass": offline_pass} if offline_pass else {"ts": ts(), "pass": False})
    print(json.dumps({"offline_pass": offline_pass, "cases": cases, "live_certified": False}, indent=2))
    return 0 if offline_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
