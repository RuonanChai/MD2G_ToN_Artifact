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

"""Freeze one post-instrumentation scientific epoch. Does not retune controllers."""
import hashlib
import json
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, sha256_file, ts  # noqa: E402

FILES = [
    REPO / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json",
    REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json",
    REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json",
    REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_CONTRACT.json",
    TON / "lib" / "command151_physical_pressure.py",
    TON / "lib" / "command151_stall_supporting.py",
    TON / "lib" / "command148_canary_metrics.py",
    TON / "lib" / "command148_canary_audit.py",
    TON / "lib" / "command147_nested_client.py",
    REPO / "moq_sub_with_latency.py",
    REPO / "moq_cluster_Sigcomm.py",
    TON / "scripts" / "command148_canary_cell.py",
    TON / "scripts" / "command147_24cell_fidelity_smoke.py",
]


def main() -> int:
    files = {}
    h = hashlib.sha256()
    for p in FILES:
        digest = sha256_file(p) if p.is_file() else None
        files[str(p)] = digest
        h.update(p.name.encode())
        h.update((digest or "missing").encode())
    digest = h.hexdigest()
    epoch = f"C152_RBV1_{digest[:12]}"
    body = {
        "ts": ts(),
        "token": "COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE",
        "epoch_id": epoch,
        "sha256": digest,
        "files": files,
        "loot_sealed": True,
        "v2_consumed": False,
    }
    dump_dual("COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE.json", body)
    dump_dual(
        "COMMAND151_RUNTIME_HASH_FREEZE.json",
        {"ts": ts(), "token": "COMMAND151_RUNTIME_HASH_FREEZE", "sha256": digest, "epoch_id": epoch},
    )
    dump_dual(
        "COMMAND151_POST_INSTRUMENTATION_RUNTIME_HASH.json",
        {"ts": ts(), "token": "COMMAND151_POST_INSTRUMENTATION_RUNTIME_HASH", "sha256": digest, "epoch_id": epoch},
    )
    dump_dual(
        "COMMAND153_POST_RB_EPOCH_FREEZE.json",
        {"ts": ts(), "token": "COMMAND153_POST_RB_EPOCH_FREEZE", "sha256": digest, "epoch_id": epoch, "loot_sealed": True},
    )
    print(json.dumps({"pass": True, "epoch_id": epoch, "sha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
