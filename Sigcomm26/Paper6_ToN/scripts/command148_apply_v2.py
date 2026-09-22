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

"""Apply the single predeclared V2 repair. Frozen before V2 canary results."""
import json
import shutil
import sys
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import dump_dual, ts  # noqa: E402

POLICY = TON / "lib" / "command148_component_policy.py"
QUEUE = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"


def main() -> int:
    freeze = REPO / "state" / "COMMAND148_V2_REPAIR_FROZEN.json"
    if not freeze.is_file():
        print(json.dumps({"pass": False, "reason": "v2_not_frozen"}))
        return 2
    text = POLICY.read_text()
    old = "if access + 1e-9 < state_rate_mbps(content, st) * 1.05:"
    new = "if access + 1e-9 < state_rate_mbps(content, st) * 0.85:  # V2: one-step live-RX headroom, not Mininet oracle"
    if "V2: one-step live-RX headroom" in text:
        print(json.dumps({"pass": True, "already": True}))
        return 0
    if old not in text:
        print(json.dumps({"pass": False, "reason": "anchor_missing"}))
        return 3
    POLICY.write_text(text.replace(old, new, 1))
    if QUEUE.is_file():
        q = json.loads(QUEUE.read_text())
        q["completed"] = []
        q["failed"] = None
        q["status"] = "V2_RERUN_0/120"
        q["v2"] = True
        q["ts"] = ts()
        dump_dual("COMMAND148_CANARY120_QUEUE.json", q)
    dump_dual(
        "COMMAND148_V2_APPLIED.json",
        {"ts": ts(), "repair": "live_rx_headroom_0.85x_state_rate", "canary_rerun": True, "no_v3": True},
    )
    print(json.dumps({"pass": True, "v2_applied": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
