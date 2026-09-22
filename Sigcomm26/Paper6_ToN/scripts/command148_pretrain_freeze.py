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

"""Freeze pretrain science after 24/24 smoke. No Loot network outcomes. No Q rerun."""
import hashlib
import json
from pathlib import Path

import sys

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_dual, sha256_file, token, ts  # noqa: E402

NEED = [
    "COMMAND147_24CELL_COMPONENT_FIDELITY_SMOKE_PASS",
    "COMMAND147_COMPONENT_QUALITY_FROZEN",
    "COMMAND147_TEMPORAL_BITRATE_FROZEN",
    "COMMAND147_COMPONENT_CAPACITY_CERTIFIED",
    "COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED",
    "COMMAND147_LIVE_COMPONENT_METRIC_CERTIFIED",
]


def filesha(rel: str) -> str:
    p = REPO / rel
    return sha256_file(p) if p.is_file() else ""


def main() -> int:
    missing = [n for n in NEED if not (REPO / "state" / f"{n}.json").is_file()]
    if missing:
        print(json.dumps({"pass": False, "missing": missing}))
        return 2
    epoch = json.loads((REPO / "state" / "COMMAND146_CORRECTED_EPOCH_SPLIT.json").read_text())
    body = {
        "ts": ts(),
        "token": "COMMAND147_PRETRAIN_SCIENTIFIC_FREEZE",
        "component_dag_sha256": filesha("state/COMMAND146_COMPONENT_DAG_CONTRACT.json"),
        "quality_contract_sha256": filesha("state/COMMAND147_COMPONENT_QUALITY_CONTRACT.json"),
        "temporal_bitrate_sha256": filesha("state/COMMAND147_TEMPORAL_BITRATE_CONTRACT.json"),
        "capacity_sha256": filesha("state/COMMAND147_COMPONENT_CAPACITY_CONTRACT.json"),
        "actuation_lib_sha256": filesha("Sigcomm26/Paper6_ToN/lib/component_actuation_plan.py"),
        "metric_cert_sha256": filesha("state/COMMAND147_LIVE_COMPONENT_METRIC_CERTIFICATION.json"),
        "epoch_split": epoch,
        "U": "clip(0.25*Ro_component+0.60*Rq-0.15*Rb,0,1)",
        "loot_network_unread": True,
        "train_dev_contents": ["redandblack", "longdress", "soldier"],
        "holdout_content": ["loot"],
        "dev_seeds": [151, 152, 153],
        "holdout_seeds": [91, 92, 93],
        "smoke_seeds": [141, 142],
        "learned_md2g_not_yet": True,
        "do_not_rerun_quality": True,
    }
    dump_dual("COMMAND147_PRETRAIN_SCIENTIFIC_FREEZE.json", body)
    token("COMMAND147_READY_FOR_COMMAND146_TEACHER", {"pretrain_freeze": True, "loot_sealed": True})
    print(json.dumps({"pass": True, "token": "COMMAND147_READY_FOR_COMMAND146_TEACHER"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
