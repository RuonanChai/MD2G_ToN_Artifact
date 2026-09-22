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

"""MCG greedy core + live policy hook. Does not load the student."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command148_component_policy import STRATS, schedule_strategy_targets  # noqa: E402
from command148_mcg import COMPONENTS, mcg_select, state_of  # noqa: E402
from component_actuation_plan import closure  # noqa: E402


class TestCommand148Mcg(unittest.TestCase):
    def test_strats_include_mcg_without_dropping_md2g(self):
        self.assertIn("MD2G_COMPONENT", STRATS)
        self.assertIn("MCG_COMPONENT", STRATS)

    def test_zero_access_stays_rep1(self):
        n = 4
        sel = mcg_select([0.0] * n, [0.22, 0.55, 0.88, 0.22], "redandblack")
        self.assertEqual(sel["states"], ["Rep1"] * n)
        self.assertEqual(sel["active"], [])
        self.assertFalse(sel["fov_used"])

    def test_prereq_db1_not_before_b0(self):
        sel = mcg_select([80.0] * 3, [0.88] * 3, "redandblack")
        if "db1" in sel["active"]:
            self.assertIn("b0", sel["active"])
            self.assertLess(sel["active"].index("b0"), sel["active"].index("db1"))

    def test_high_access_admits_base(self):
        sel = mcg_select([80.0] * 8, [0.88] * 8, "redandblack")
        self.assertIn("b0", sel["active"])
        self.assertTrue(any(s != "Rep1" for s in sel["states"]))

    def test_state_of_uses_closure(self):
        self.assertIsNone(state_of(set()))
        self.assertEqual(state_of(set(closure("Rep3"))), "Rep3")

    def test_schedule_mcg_same_action_interface(self):
        os.environ.pop("COMMAND148_CELL_DIR", None)
        out = schedule_strategy_targets("MCG_COMPONENT", 0.0, 3, 120.0, content="redandblack")
        self.assertEqual(set(out), {"u1", "u2", "u3"})
        for st in out.values():
            self.assertRegex(st, r"^Rep[1-9]$")

    def test_mcg_writes_decision_not_student(self):
        os.environ.pop("COMMAND148_STUDENT_PATH", None)
        with tempfile.TemporaryDirectory() as td:
            os.environ["COMMAND148_CELL_DIR"] = td
            try:
                schedule_strategy_targets("MCG_COMPONENT", 1.0, 2, 120.0, content="redandblack", log_path=td)
            finally:
                os.environ.pop("COMMAND148_CELL_DIR", None)
            p = Path(td) / "COMMAND148_MCG_DECISION.jsonl"
            self.assertTrue(p.is_file() and p.stat().st_size > 0)
            self.assertFalse((Path(td) / "COMMAND148_STUDENT_INFERENCE.jsonl").is_file())

    def test_components_are_nested_five(self):
        self.assertEqual(COMPONENTS, ("b0", "db1", "db2", "e1", "e2"))


if __name__ == "__main__":
    unittest.main()
