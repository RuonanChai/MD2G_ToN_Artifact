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

"""E014: open b0 before incrementals; do not treat this as a B/C result."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command147_nested_client import (  # noqa: E402
    B0_READY_BYTES,
    b0_dump_ready,
    ordered_open_batches,
)
from command153_classify_and_repair import classify_cell  # noqa: E402


class TestB0FirstStartOrder(unittest.TestCase):
    def test_rep8_opens_b0_alone_first(self):
        first, rest = ordered_open_batches(["b0", "db1", "db2", "e1"])
        self.assertEqual(first, ["b0"])
        self.assertEqual(rest, ["db1", "db2", "e1"])

    def test_no_b0_keeps_order(self):
        first, rest = ordered_open_batches(["e1", "e2"])
        self.assertEqual(first, [])
        self.assertEqual(rest, ["e1", "e2"])

    def test_dump_ready_threshold(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "dump_h2_b0.bin"
            p.write_bytes(b"x" * 10)
            self.assertFalse(b0_dump_ready(p))
            p.write_bytes(b"x" * (B0_READY_BYTES + 1))
            self.assertTrue(b0_dump_ready(p))


class TestClassifyDoesNotReuseE013(unittest.TestCase):
    def test_subscribe_started_no_retry_is_e014(self):
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            rec = {
                "decoded_state": None,
                "dump_bytes": {"b0": 0, "db1": 0, "db2": 130000, "e1": 200000, "e2": 0},
            }
            (cell / "client_h2_COMPONENT_RECEIPT.jsonl").write_text(json.dumps(rec) + "\n")
            (cell / "client_h2_gst_b0.log").write_text(
                'path: "/anon/"\nsubscribe started id=1 broadcast=b0 track=video0\n'
            )
            (cell / "client_h2_dispatch_stdout.log").write_text("OPEN b0 pid=1\n")
            out = classify_cell("c147smoke_S3_mixed_share_4g_s141", cell)
            self.assertEqual(out["failure_id"], "E014_S3_CONCURRENT_SUBSCRIBE_B0_DUMP_ZERO")
            self.assertTrue(out["not_e013"])


if __name__ == "__main__":
    unittest.main()
