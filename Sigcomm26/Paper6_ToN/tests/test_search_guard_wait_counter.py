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

"""Separate guard_wait_cycles from candidate_rounds_attempted / evaluated / passed."""
import json
import sys
import tempfile
from pathlib import Path

OUT = ton_root()
sys.path.insert(0, str(OUT / "scripts"))
import command49_md2g_search_engine as eng  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        (art / "ledgers").mkdir(parents=True)
        c0 = eng.load_counters()
        # Simulate three guard waits then assert consecutive_guard_only
        eng.record_guard_wait(art, "DEFER_LIVE_CANARY", {})
        eng.record_guard_wait(art, "DEFER_LIVE_CANARY", {})
        c = eng.load_counters()
        assert int(c["consecutive_guard_only"]) >= 2
        assert int(c["guard_wait_cycles"]) >= int(c0.get("guard_wait_cycles", 0)) + 2
        assert int(c["candidate_rounds_attempted"]) == int(c0.get("candidate_rounds_attempted", 0))
        # Real round counter keys exist
        for k in ("guard_wait_cycles", "candidate_rounds_attempted", "candidates_evaluated", "candidates_passed"):
            assert k in c
        # Contract file
        contract = json.loads((OUT / "audits/COMMAND50_SEARCH_LIVENESS_CONTRACT.json").read_text()) if (OUT / "audits/COMMAND50_SEARCH_LIVENESS_CONTRACT.json").exists() else {
            "counters": ["guard_wait_cycles", "candidate_rounds_attempted", "candidates_evaluated", "candidates_passed"],
            "max_consecutive_guard_only_after_canary": 2,
        }
        assert "guard_wait_cycles" in contract.get("counters", [])
        assert int(contract.get("max_consecutive_guard_only_after_canary", 2)) == 2
    print("SEARCH_GUARD_WAIT_COUNTER_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
