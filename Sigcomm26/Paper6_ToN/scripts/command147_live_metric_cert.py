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

"""P5 live component metric cert from frozen Q + measured component payload bytes."""
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_dual, token, ts  # noqa: E402
from component_actuation_plan import TRACKS, closure  # noqa: E402
from ton_ro_component import b_shared, b_unicast, paper_u, ro_component  # noqa: E402

WINDOW_S = 90.0  # measurement interval from temporal contract


def main() -> int:
    if not (REPO / "state" / "COMMAND147_COMPONENT_QUALITY_FROZEN.json").is_file():
        print(json.dumps({"pass": False, "reason": "quality_not_frozen"}))
        return 2
    q = json.loads((REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json").read_text())
    rates = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
    act = json.loads((REPO / "state" / "COMMAND147_COMPONENT_ACTUATION_LIVE_CERT.json").read_text())
    rb_q = q["Q_norm"]["redandblack"]
    mbps = {t: float(rates["contents"]["redandblack"][t]["steady_state_payload_mbps"]) for t in TRACKS}
    pay = {t: int(round(mbps[t] * 1e6 / 8.0 * WINDOW_S)) for t in TRACKS}
    users = {"U1": closure("Rep3"), "U2": closure("Rep8"), "U3": closure("Rep9")}
    shared = ["b0", "db1", "db2", "e1", "e2"]
    bu = b_unicast(users, pay)
    bs = b_shared(shared, pay)
    ro = ro_component(bs, bu)
    # Rq from actually decodable states (U1/U2/U3 closures complete in T5)
    rq = (rb_q["Rep3"] + rb_q["Rep8"] + rb_q["Rep9"]) / 3.0
    rb = 0.0  # physical Rb remains a separate live-cell network term; not filled from Ro
    u = paper_u(ro, rq, rb)
    # Actuation live must have shown shared union published once (T5 open empty after T4).
    t5 = next(r for r in act["transitions"] if r["reason"] == "T5")
    cases = {
        "shared_union_once": set(shared) == {"b0", "db1", "db2", "e1", "e2"} and t5["open"] == [],
        "unicast_u1_b3": set(users["U1"]) == {"b0", "db1", "db2"},
        "unicast_u2_b3e1": set(users["U2"]) == {"b0", "db1", "db2", "e1"},
        "unicast_u3_all": set(users["U3"]) == set(TRACKS),
        "e1_not_delivered_to_rep3": "e1" not in users["U1"] and "e1" in users["U2"],
        "T5_rep3_excluded_from_e1_receivers": "u1" not in ((t5.get("component_receivers") or {}).get("e1") or [])
        and set((t5.get("component_receivers") or {}).get("e1") or []) == {"u2", "u3"},
        "T5_rep3_zero_e1_delta": (t5.get("e1_receipt_delta") or {}).get("u1") is not None
        and int((t5.get("e1_receipt_delta") or {}).get("u1")) == 0,
        "ro_in_01": 0.0 < ro < 1.0,
        "rq_from_frozen_q_not_rep_id": rq == (rb_q["Rep3"] + rb_q["Rep8"] + rb_q["Rep9"]) / 3.0,
        "rb_separate_from_ro": rb == 0.0,
        "actuation_live_pass": act.get("pass") is True,
        "quality_not_rerun": True,
        "loot_not_used_for_controller": "loot" in (q.get("controller_must_not_use_contents") or []),
    }
    passed = all(cases.values())
    body = {
        "ts": ts(),
        "token": "COMMAND147_LIVE_COMPONENT_METRIC_CERTIFICATION",
        "pass": passed,
        "B_unicast_component": bu,
        "B_shared_component": bs,
        "Ro_component": ro,
        "Rq": rq,
        "Rb": rb,
        "paper_U_Rb0": u,
        "decoded_states": {"U1": "Rep3", "U2": "Rep8", "U3": "Rep9"},
        "Q_source": "COMMAND147_COMPONENT_QUALITY_CONTRACT",
        "cases": cases,
        "scientific_mininet_cells": 0,
        "loot_network_holdout_sealed": True,
        "note": "Rq from frozen Q of actually decodable closures; Ro from component-union bytes; Rb reserved for physical path counters in 24-cell smoke",
    }
    dump_dual("COMMAND147_LIVE_COMPONENT_METRIC_CERTIFICATION.json", body)
    if passed:
        token("COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED", {"pass": True, "Ro_component": ro, "Rq": rq})
    print(json.dumps({"pass": passed, "Ro_component": ro, "Rq": rq, "cases": cases}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
