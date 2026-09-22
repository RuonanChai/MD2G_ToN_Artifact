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

"""Ensure BLOCKED/DEFER/missing-search-art do not increment candidate_rounds_attempted."""
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

OUT = ton_root()
sys.path.insert(0, str(OUT / "scripts"))
import command49_md2g_search_engine as eng  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as td:
        art = Path(td)
        for d in ("candidates", "canaries", "reviews", "ablations", "logs", "ledgers"):
            (art / d).mkdir()
        # Reset counters path via STATE override is hard; use record_guard_wait and check it does not touch ledger CSV candidate count
        before = eng.load_counters()
        gw0 = int(before.get("guard_wait_cycles", 0))
        cr0 = int(before.get("candidate_rounds_attempted", 0))
        eng.record_guard_wait(art, "BLOCKED_HOLDOUT_LIVE", {"test": True})
        eng.record_guard_wait(art, "DEFER_LIVE_CANARY", {"test": True})
        after = eng.load_counters()
        assert int(after["guard_wait_cycles"]) == gw0 + 2
        assert int(after["candidate_rounds_attempted"]) == cr0
        # Guard wait must not write CANDIDATE_LEDGER
        cand_ledger = art / "ledgers" / "CANDIDATE_LEDGER.jsonl"
        assert not cand_ledger.exists() or cand_ledger.read_text().strip() == ""
        gw_ledger = art / "ledgers" / "GUARD_WAIT.jsonl"
        assert gw_ledger.exists() and "BLOCKED_HOLDOUT_LIVE" in gw_ledger.read_text()

        # Missing --search-art with --require-search-art must nonzero and not bump rounds
        with mock.patch.object(sys, "argv", ["command49_md2g_search_engine.py", "--require-search-art", "--max-rounds", "1"]):
            # clear env
            import os

            os.environ.pop("SEARCH_ART_ROOT", None)
            rc = eng.main()
            assert rc == 2
        after2 = eng.load_counters()
        assert int(after2["candidate_rounds_attempted"]) == cr0

    print("SEARCH_NOOP_ROUND_REGRESSION_PASS")
    print("SEARCH_NOOP_ADVANCEMENT_ELIMINATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
