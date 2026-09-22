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

"""COMMAND149 hand-computable missing-component cases. Same physics for all strategies."""
import sys
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command148_component_policy import STRATS, _apply_shared_physics, _project_feasible  # noqa: E402
from command149_marginal_cost import (  # noqa: E402
    FROZEN_SAFETY_MARGIN,
    cumulative_prefix_mbps,
    delta_r_mbps,
    missing_components,
    project_down,
)


class TestCommand149MarginalCost(unittest.TestCase):
    def test_case1_b1_to_b2_charges_db1_only(self):
        ag = ["b0"]
        miss = missing_components("Rep2", ag)
        self.assertEqual(miss, ["db1"])
        dlt = delta_r_mbps("redandblack", "Rep2", ag)
        cum = cumulative_prefix_mbps("redandblack", "Rep2")
        self.assertAlmostEqual(dlt, delta_r_mbps("redandblack", "Rep2", ["b0"]))
        self.assertGreater(cum, dlt + 20.0)
        rec = project_down("Rep2", dlt * FROZEN_SAFETY_MARGIN + 0.01, 0.55, "redandblack", ag)
        self.assertEqual(rec["applied"], "Rep2")
        self.assertEqual(rec["missing_proposed"], ["db1"])
        self.assertLess(abs(rec["DeltaR_proposed_mbps"] - dlt), 1e-9)
        rec_low = project_down("Rep2", 1.0, 0.55, "redandblack", ag)
        self.assertEqual(rec_low["applied"], "Rep1")

    def test_case2_b3_to_e1_charges_e1_only(self):
        ag = ["b0", "db1", "db2"]
        miss = missing_components("Rep8", ag)
        self.assertEqual(miss, ["e1"])
        dlt = delta_r_mbps("redandblack", "Rep8", ag)
        rec = project_down("Rep8", dlt * FROZEN_SAFETY_MARGIN + 0.01, 0.88, "redandblack", ag)
        self.assertEqual(rec["missing_proposed"], ["e1"])
        self.assertEqual(rec["applied"], "Rep8")

    def test_case3_already_shared_zero_marginal(self):
        ag = ["b0", "db1", "db2", "e1"]
        self.assertEqual(missing_components("Rep8", ag), [])
        self.assertEqual(delta_r_mbps("redandblack", "Rep8", ag), 0.0)
        rec = project_down("Rep8", 0.0, 0.88, "redandblack", ag)
        self.assertEqual(rec["applied"], "Rep8")
        self.assertEqual(rec["DeltaR_proposed_mbps"], 0.0)

    def test_cumulative_61_is_not_admission_threshold(self):
        ag = ["b0"]
        dlt = delta_r_mbps("redandblack", "Rep2", ag)
        cum = cumulative_prefix_mbps("redandblack", "Rep2")
        self.assertAlmostEqual(cum * 1.05, 61.271, places=2)
        access = 40.0
        rec = project_down("Rep2", access, 0.55, "redandblack", ag)
        self.assertEqual(rec["applied"], "Rep2")
        self.assertLess(dlt * FROZEN_SAFETY_MARGIN, access)
        self.assertGreater(cum * FROZEN_SAFETY_MARGIN, access)
        self.assertNotEqual(rec["threshold_mbps"], cum * FROZEN_SAFETY_MARGIN)

    def test_all_same_substrate_strats_share_projector(self):
        self.assertIn("MD2G_COMPONENT", STRATS)
        ag = ["b0"]
        a = project_down("Rep2", 40.0, 0.55, "redandblack", ag)["applied"]
        b = _project_feasible(2, 40.0, 0.55, "redandblack", ag)
        self.assertEqual(a, b)
        self.assertEqual(a, "Rep2")

    def test_baseline_physics_uses_same_function(self):
        import os

        os.environ.pop("COMMAND148_CELL_DIR", None)
        raw = {"u1": "Rep2", "u2": "Rep2"}
        # no live access files → access=0 → cannot pay db1 even; group active empty so Rep2 missing={b0,db1}
        out = _apply_shared_physics(
            raw, strategy="HV3_COMPONENT", n_users=2, content="redandblack", log_path=""
        )
        self.assertEqual(out["u1"], "Rep1")
        self.assertEqual(out["u2"], "Rep1")


if __name__ == "__main__":
    unittest.main()
