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

"""P5 hand-computable Ro_component case from frozen rates (not a live cell)."""
import json
import sys
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_dual, ts  # noqa: E402
from component_actuation_plan import closure  # noqa: E402
from ton_ro_component import b_shared, b_unicast, paper_u, ro_component  # noqa: E402

Q = json.loads((REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json").read_text())["Q_norm"]["redandblack"]
RATE = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
RB = {
    t: int(round(float(RATE["contents"]["redandblack"][t]["steady_state_payload_mbps"]) * 1e6 / 8.0 * 90.0))
    for t in ("b0", "db1", "db2", "e1", "e2")
}  # measurement-window bytes at frozen rate


def main() -> int:
    users = {"U1": closure("Rep3"), "U2": closure("Rep8"), "U3": closure("Rep9")}
    shared = ["b0", "db1", "db2", "e1", "e2"]
    bu = b_unicast(users, RB)
    bs = b_shared(shared, RB)
    ro = ro_component(bs, bu)
    # Rq from actually decodable states (here = targets because closure complete)
    rq = (Q["Rep3"] + Q["Rep8"] + Q["Rep9"]) / 3.0
    rb = 0.0  # not computed here; physical Rb stays separate
    u = paper_u(ro, rq, rb)
    expect_uni = (
        sum(RB[c] for c in users["U1"])
        + sum(RB[c] for c in users["U2"])
        + sum(RB[c] for c in users["U3"])
    )
    ok = (
        set(shared) == {"b0", "db1", "db2", "e1", "e2"}
        and abs(bu - expect_uni) < 1e-6
        and bs == sum(RB[c] for c in shared)
        and 0.0 < ro < 1.0
    )
    body = {
        "ts": ts(),
        "token": "COMMAND147_LIVE_METRIC_HANDCOMPUTE",
        "pass": ok,
        "live_certified": False,
        "users": users,
        "shared_once": shared,
        "B_unicast_component": bu,
        "B_shared_component": bs,
        "Ro_component": ro,
        "Rq_from_decoded_Q": rq,
        "Rb_not_from_Ro": True,
        "paper_U_if_Rb0": u,
        "loot_network_holdout_sealed": True,
        "note": "hand-computable identity only; live byte ledgers still required",
    }
    dump_dual("COMMAND147_LIVE_METRIC_HANDCOMPUTE.json", body)
    print(json.dumps({"pass": ok, "Ro_component": ro, "Rq": rq, "live_certified": False}, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
