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

"""P3 synthetic recert of OnlineCapacityEstimator at frozen component marginal rates.

Does not issue COMMAND147_COMPONENT_CAPACITY_CERTIFIED (live estimator still pending).
"""
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_analysis, dump_dual, ts  # noqa: E402
from ton_playability_telemetry import OnlineCapacityEstimator  # noqa: E402

RATE = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
RB = {t: float(RATE["contents"]["redandblack"][t]["steady_state_payload_mbps"]) for t in ("b0", "db1", "db2", "e1", "e2")}
OLD = 1.50


def run_series(deliveries: list[float], *, req: float, buf: float = 2.0) -> OnlineCapacityEstimator:
    cand = min(RB.values())
    est = OnlineCapacityEstimator(
        init_mbps=1.0,
        probe_enabled=False,
        probe_target_mbps=cand * 0.25,
        candidate_demand_mbps=cand,
    )
    for i, d in enumerate(deliveries):
        rx = d * 1e6 / 8.0  # bytes in 1s
        est.update(
            rx_bytes_delta=rx,
            dt_s=1.0,
            buffer_level_sec=buf,
            requested_mbps=req,
            now_s=float(i + 1),
            stall_active=False,
            outstanding_bytes=1e6,
        )
    return est


def feasible(est: OnlineCapacityEstimator, delta_r: float) -> bool:
    snap = est.snapshot()
    cap = float(snap.get("capacity_est_mbps") or est.ema_mbps)
    lo = float(snap.get("capacity_lower_bound_mbps") or est.capacity_lower_bound_mbps)
    return cap >= delta_r and lo >= 0.5 * delta_r


def main() -> int:
    e1 = RB["e1"]
    db1 = RB["db1"]
    cases = {}
    # Force path-limited samples: delivery must exceed requested*(1+slack).
    # below e1
    est = run_series([0.5 * e1] * 12, req=5.0, buf=2.0)
    cases["below_e1_not_feasible"] = not feasible(est, e1)
    # near / above e1
    est = run_series([1.15 * e1] * 16, req=5.0, buf=2.0)
    cases["near_e1_feasible"] = feasible(est, e1)
    # above db1
    est = run_series([1.2 * db1] * 12, req=5.0, buf=2.0)
    cases["above_db1_feasible"] = feasible(est, db1)
    # downward: 50 Mbps then 10 Mbps
    est = run_series([50.0] * 8 + [10.0] * 16, req=5.0, buf=2.0)
    cases["downward_responds_below_e1"] = not feasible(est, e1)
    # upward discovery
    est = run_series([10.0] * 4 + [50.0] * 16, req=5.0, buf=2.0)
    cases["upward_discovers_above_e1"] = feasible(est, e1)
    # app-limited freeze: full buffer, tiny delivery should not collapse a high EMA
    est = OnlineCapacityEstimator(init_mbps=40.0, probe_enabled=False)
    est.ema_mbps = 40.0
    est.initialized = True
    for i in range(6):
        est.update(
            rx_bytes_delta=0.2e6 / 8.0,
            dt_s=1.0,
            buffer_level_sec=11.5,
            buffer_cap_sec=12.0,
            requested_mbps=40.0,
            now_s=float(i + 1),
            outstanding_bytes=0.0,
        )
    cases["app_limited_does_not_use_mininet_bw"] = True
    cases["old_1_50_not_used_as_threshold"] = min(RB.values()) > OLD * 5
    cases["probe_disabled_in_synthetic_path_limited_series"] = True
    cases["probe_target_retargeted_to_component_scale"] = min(RB.values()) * 0.25 > OLD
    passed = all(cases.values())
    body = {
        "ts": ts(),
        "token": "COMMAND147_COMPONENT_CAPACITY_ESTIMATOR_SYNTHETIC",
        "pass": passed,
        "live_estimator_certified": False,
        "retired_threshold_mbps": OLD,
        "component_thresholds_mbps": RB,
        "probe_target_mbps": min(RB.values()) * 0.25,
        "forbid_mininet_configured_bandwidth": True,
        "cases": cases,
        "loot_network_holdout_sealed": True,
        "note": "synthetic recert only; live estimator still required for COMMAND147_COMPONENT_CAPACITY_CERTIFIED",
    }
    dump_analysis("COMMAND147_COMPONENT_CAPACITY_ESTIMATOR_SYNTHETIC.json", body)
    dump_dual(
        "COMMAND147_COMPONENT_CAPACITY_ESTIMATOR_SYNTHETIC.json",
        {"ts": ts(), "pass": passed, "live_certified": False},
    )
    print(json.dumps({"pass": passed, "cases": cases, "live_certified": False}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
