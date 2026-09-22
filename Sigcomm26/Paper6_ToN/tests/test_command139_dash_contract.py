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

"""Fail-closed command139 invariants: DASH required, no MoQ rewrite, no premature freeze."""
import json
import unittest
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"


class TestCommand139(unittest.TestCase):
    def test_authority_invariants(self):
        a = json.loads((REPO / "state" / "COMMAND139_AGENTS_AUTHORITY.json").read_text())
        self.assertTrue(a["DASH_BASELINES_REQUIRED"])
        self.assertTrue(a["MD2G_DEV_OPTIMIZATION_ALLOWED"])
        self.assertTrue(a["NO_FINAL_FREEZE_WHILE_PAPER_WEAK"])
        self.assertIn("GROOT", a["dash_baselines"])
        self.assertIn("Rolling", a["dash_baselines"])
        self.assertTrue(a["dash_must_not_be_rewritten_as_moq"])
        self.assertTrue(a["u_weights_immutable"])
        self.assertTrue(a["holdout_sealed_until_final_controller_freeze"])

    def test_metric_adapter_u_frozen(self):
        m = json.loads((REPO / "state" / "COMMAND139_DASH_METRIC_ADAPTER_FREEZE.json").read_text())
        self.assertEqual(m["canonical_U"], "clip(0.25*Ro + 0.60*Rq - 0.15*Rb, 0, 1)")
        self.assertTrue(m["no_strategy_specific_U_weights"])

    def test_companion_queue_is_16_dev_only(self):
        import importlib.util

        p = TON / "scripts" / "command139_dash_companion_canary.py"
        spec = importlib.util.spec_from_file_location("c139dash", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(len(mod.QUEUE), 16)
        self.assertTrue(all(c in ("redandblack", "longdress") for c, *_ in mod.QUEUE))
        self.assertEqual({st for *_, st in mod.QUEUE}, {"groot", "rolling"})

    def test_no_moq_cluster_in_dash_companion(self):
        text = (TON / "scripts" / "command139_dash_companion_canary.py").read_text()
        self.assertNotIn("moq_cluster_Sigcomm.py", text)
        self.assertIn("run_authentic_unicast_baseline_cell.py", text)

    def test_paper_viability_blocks_final_now(self):
        v = json.loads((REPO / "state" / "COMMAND139_PAPER_VIABILITY.json").read_text())
        self.assertFalse(v["paper_viability_dev_pass"])
        self.assertTrue(v["final_matrix_blocked"])

    def test_command_text_forbids_premature_freeze(self):
        t = (TON / "commands" / "command139_dash_baselines_and_md2g_dev_optimization.txt").read_text()
        self.assertIn("E018_PREMATURE_MD2G_FREEZE", t)
        self.assertIn("GROOT", t)
        self.assertIn("Rolling", t)


if __name__ == "__main__":
    unittest.main()
