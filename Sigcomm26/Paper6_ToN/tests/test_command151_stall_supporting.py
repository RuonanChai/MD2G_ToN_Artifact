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

"""Deterministic decode-gap stall. Not folded into U."""
import sys
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command151_stall_supporting import STATUS, stall_seconds_from_receipts  # noqa: E402


class TestDecodeGapStall(unittest.TestCase):
    def test_no_stall_when_always_decoded(self):
        rows = [{"ts": 1000.0 + i, "decoded_state": "Rep3"} for i in range(20)]
        stall, status = stall_seconds_from_receipts(rows, warmup_s=10.0)
        self.assertEqual(status, STATUS)
        self.assertEqual(stall, 0.0)

    def test_post_warmup_none_counts(self):
        rows = []
        for i in range(12):
            rows.append({"ts": 1000.0 + i, "decoded_state": "Rep1"})
        for i in range(12, 17):
            rows.append({"ts": 1000.0 + i, "decoded_state": None})
        stall, status = stall_seconds_from_receipts(rows, warmup_s=10.0)
        self.assertEqual(status, STATUS)
        self.assertAlmostEqual(stall, 5.0, places=6)


if __name__ == "__main__":
    unittest.main()
