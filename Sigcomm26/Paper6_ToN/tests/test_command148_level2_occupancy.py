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

"""Level-2 occupancy / receiver / completion helpers. Frozen Q, not Rep-ID rank."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command148_canary_metrics import composition_delivery_stats  # noqa: E402


class TestLevel2DeliveryStats(unittest.TestCase):
    def test_target_decoded_receiver_completion(self):
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            plan = {
                "user_target_states": {"u1": "Rep8", "u2": "Rep3"},
                "component_receivers": {
                    "b0": ["u1", "u2"],
                    "db1": ["u1", "u2"],
                    "db2": ["u1", "u2"],
                    "e1": ["u1"],
                    "e2": [],
                },
            }
            (cell / "COMPONENT_ACTUATION_PLAN_CURRENT.json").write_text(json.dumps(plan))
            (cell / "client_h1_COMPONENT_RECEIPT.jsonl").write_text(
                json.dumps(
                    {
                        "target_state": "Rep8",
                        "decoded_state": "Rep3",
                        "dump_bytes": {"b0": 1000, "db1": 1000, "db2": 1000, "e1": 0, "e2": 0},
                    }
                )
                + "\n"
            )
            (cell / "client_h2_COMPONENT_RECEIPT.jsonl").write_text(
                json.dumps(
                    {
                        "target_state": "Rep3",
                        "decoded_state": "Rep3",
                        "dump_bytes": {"b0": 1000, "db1": 1000, "db2": 1000, "e1": 0, "e2": 0},
                    }
                )
                + "\n"
            )
            spec = {"users": 2, "content": "redandblack"}
            got = composition_delivery_stats(cell, spec)
            self.assertFalse(got["quality_ranked_by_rep_id"])
            self.assertAlmostEqual(got["target_state_occupancy"]["Rep8"], 0.5)
            self.assertAlmostEqual(got["target_state_occupancy"]["Rep3"], 0.5)
            self.assertAlmostEqual(got["actual_decoded_state_occupancy"]["Rep3"], 1.0)
            self.assertAlmostEqual(got["actual_decoded_state_occupancy"]["Rep8"], 0.0)
            self.assertEqual(got["receiver_set_size"]["e1"], 1)
            self.assertEqual(got["receiver_set_size"]["e2"], 0)
            self.assertEqual(got["component_completion_fraction"]["e1"]["n_complete_dump_gt_64"], 0)
            self.assertAlmostEqual(got["component_completion_fraction"]["b0"]["fraction"], 1.0)
            self.assertIsNone(got["component_completion_fraction"]["e2"]["fraction"])
            self.assertLess(got["Q_norm_frozen"]["Rep4"], got["Q_norm_frozen"]["Rep3"])

    def test_undecoded_does_not_credit_target(self):
        with tempfile.TemporaryDirectory() as td:
            cell = Path(td)
            (cell / "COMPONENT_ACTUATION_PLAN_CURRENT.json").write_text(
                json.dumps({"user_target_states": {"u1": "Rep9"}, "component_receivers": {"b0": ["u1"]}})
            )
            (cell / "client_h1_COMPONENT_RECEIPT.jsonl").write_text(
                json.dumps(
                    {
                        "target_state": "Rep9",
                        "decoded_state": None,
                        "dump_bytes": {"b0": 0, "db1": 1000, "db2": 1000, "e1": 0, "e2": 0},
                    }
                )
                + "\n"
            )
            got = composition_delivery_stats(cell, {"users": 1, "content": "redandblack"})
            self.assertEqual(got["target_state_occupancy"]["Rep9"], 1.0)
            self.assertEqual(got["actual_decoded_state_occupancy"]["Rep9"], 0.0)
            self.assertEqual(got["actual_decoded_state_occupancy"]["Rep3"], 0.0)


if __name__ == "__main__":
    unittest.main()
