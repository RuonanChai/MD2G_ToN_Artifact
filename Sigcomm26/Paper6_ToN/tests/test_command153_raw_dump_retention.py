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

"""E025/E026: retention gate + nested_client final teardown keeps dumps."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
sys.path.insert(0, str(TON / "scripts"))
from command153_raw_dump_retention import (  # noqa: E402
    derived_evidence_ready,
    reclaim_valid_dumps_if_allowed,
)


def _minimal_valid_cell(cell: Path) -> None:
    metrics = {
        "target_state_occupancy": {},
        "actual_decoded_state_occupancy": {},
        "component_completion_fraction": 1.0,
        "B_shared": 1.0,
        "B_unicast": 2.0,
        "Rb": 0.1,
        "Ro_component": 0.5,
        "Rq": 0.5,
        "U": 0.5,
    }
    for name in (
        "CELL_VALIDITY.json",
        "CELL_METRICS.json",
        "CELL_DONE.json",
        "CELL_AUDIT.json",
    ):
        body = metrics if name == "CELL_METRICS.json" else {"valid": True}
        (cell / name).write_text(json.dumps(body) + "\n")
    (cell / "PHYSICAL_PRESSURE_TIMESERIES.jsonl").write_text("{}\n")
    (cell / "client_h1_COMPONENT_RECEIPT.jsonl").write_text("{}\n")
    (cell / "client_h1_perf.csv").write_text("ts\n")


class TestRetentionGate(unittest.TestCase):
    def test_valid_hashes_then_deletes_non_sentinel(self):
        if not (REPO / "state" / "COMMAND153_RAW_DUMP_RETENTION_CONTRACT.json").is_file():
            self.skipTest("retention contract not frozen")
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td) / "c148dev_test_non_sentinel"
            cell.mkdir()
            _minimal_valid_cell(cell)
            dump = cell / "dump_h1_b0.bin"
            dump.write_bytes(b"payload-bytes-for-hash")
            ready, missing = derived_evidence_ready(cell)
            self.assertTrue(ready, missing)
            out = reclaim_valid_dumps_if_allowed(cell, cell_key=cell.name, epoch_id="test_epoch")
            self.assertFalse(dump.is_file())
            self.assertTrue((cell / "RAW_DUMP_MANIFEST.json").is_file())
            man = json.loads((cell / "RAW_DUMP_MANIFEST.json").read_text())
            self.assertEqual(len(man.get("dumps") or []), 1)
            self.assertEqual(out["gate"]["reason"], "VALID_HASHED_DERIVED_COMPLETE")


class TestE026NestedClientFinalKeep(unittest.TestCase):
    def test_finally_keeps_dumps(self):
        src = (TON / "lib" / "command147_nested_client.py").read_text()
        self.assertIn("remove_dump: bool = True", src)
        self.assertIn("stop(c, remove_dump=False)", src)


if __name__ == "__main__":
    unittest.main()
