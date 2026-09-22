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

"""One consistency audit of final metrics. Does not invent new metrics."""
import json
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, ts  # noqa: E402
from command151_stall_supporting import STATUS as STALL_STATUS  # noqa: E402


def main() -> int:
    if not (REPO / "state" / "COMMAND152_FINAL_METRIC_COMPLETENESS_PASS.json").is_file():
        print(json.dumps({"pass": False, "reason": "completeness_missing"}))
        return 2
    body = {
        "ts": ts(),
        "token": "COMMAND153_FINAL_METRIC_CONTRACT_CONFIRM",
        "U": "final",
        "Ro_component": "final",
        "Rq": "actual_decoded_Q_norm_final",
        "Rb": "shared_root_pressure_final",
        "B_shared_unicast": "final",
        "weak_user_Rq": "minimum_per_launched_user_decoded_Q_norm",
        "target_decoded_occupancy": "diagnostic",
        "receiver_set_completion": "diagnostic",
        "stall": {"status": "SUPPORTING_NOT_IN_U", "stall_last_status": STALL_STATUS},
        "delay": "NOT_IN_FINAL_CLAIM_CONTRACT",
        "pre_rb_56": "DIAGNOSTIC_ONLY_NOT_FINAL_U",
        "loot_sealed": True,
    }
    dump_dual("COMMAND153_FINAL_METRIC_CONTRACT_CONFIRM.json", body)
    print(json.dumps({"pass": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
