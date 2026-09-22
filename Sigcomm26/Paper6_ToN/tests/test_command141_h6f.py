#!/usr/bin/env python3
"""H6-F filters H5 proposed depth; does not replace admission."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
REPO = TON.parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command141_h6_policy import candidate_from_env, completion_likely, sticky_filter_h5, sticky_step  # noqa: E402


class TestH6F(unittest.TestCase):
    def test_filter_flag_only_delta_vs_h6e(self):
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        by = {c["id"]: c for c in blob["candidates"]}
        e, f = by["H6-E_COMPLETION_P_1"]["env"], by["H6-F_FILTER_H5"]["env"]
        self.assertEqual(f.get("MD2G_H6_FILTER_H5"), "1")
        self.assertNotIn("MD2G_H6_FILTER_H5", e)
        for k in set(e):
            self.assertEqual(e[k], f.get(k), k)

    def test_filter_enters_on_h5_proposal_without_headroom(self):
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        f = next(c for c in blob["candidates"] if c["id"] == "H6-F_FILTER_H5")
        cand = candidate_from_env(f["env"])
        self.assertTrue(completion_likely(1.05, cand))
        nd, _, _ = sticky_filter_h5(0, 0.0, 0.0, 1.0, proposed=1, buffer_s=1.05, cand=cand)
        self.assertEqual(nd, 1)
        nd2, _, _ = sticky_step(0, 0.0, 0.0, 1.0, headroom_mbps=0.0, buffer_s=1.05, cand=cand)
        self.assertEqual(nd2, 0)

    def test_follow_h5_exit_drops_immediately_and_cools_reenter(self):
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        f = next(c for c in blob["candidates"] if c["id"] == "H6-H_FOLLOW_H5_EXIT")
        cand = candidate_from_env(f["env"])
        nd, since, e1s = sticky_filter_h5(0, 0.0, 0.0, 10.0, 1, 1.05, cand, follow_h5_exit=True)
        self.assertEqual(nd, 1)
        nd2, since2, e1s2 = sticky_filter_h5(nd, since, e1s, 12.0, 0, 1.05, cand, follow_h5_exit=True)
        self.assertEqual(nd2, 0)
        nd3, _, _ = sticky_filter_h5(nd2, since2, e1s2, 13.0, 1, 1.05, cand, follow_h5_exit=True)
        self.assertEqual(nd3, 0)
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        f = next(c for c in blob["candidates"] if c["id"] == "H6-F_FILTER_H5")
        cand = candidate_from_env(f["env"])
        nd, since, e1s = sticky_filter_h5(0, 0.0, 0.0, 10.0, 1, 1.05, cand)
        nd2, _, _ = sticky_filter_h5(nd, since, e1s, 12.0, proposed=0, buffer_s=1.05, cand=cand)
        self.assertEqual(nd2, 1)

    def test_h7_inflight_hold_then_follow_without_reenter_cooldown(self):
        blob = json.loads((REPO / "state" / "COMMAND141_H6_CANDIDATES.json").read_text())
        row = next(c for c in blob["candidates"] if c["id"] == "H7_INFLIGHT_COMPLETION_HOLD")
        cand = candidate_from_env(row["env"])
        self.assertEqual(row["env"].get("MD2G_H7_INFLIGHT_HOLD"), "1")
        self.assertEqual(cand.min_dwell_s, 0.0)
        nd, since, e1s = sticky_filter_h5(
            0, 0.0, 0.0, 10.0, 1, 1.05, cand, follow_h5_exit=True, inflight_hold=True
        )
        self.assertEqual(nd, 1)
        nd2, since2, e1s2 = sticky_filter_h5(
            nd, since, e1s, 10.5, 0, 1.05, cand, follow_h5_exit=True, inflight_hold=True
        )
        self.assertEqual(nd2, 1)
        nd3, since3, e1s3 = sticky_filter_h5(
            nd2, since2, e1s2, 11.1, 0, 1.05, cand, follow_h5_exit=True, inflight_hold=True
        )
        self.assertEqual(nd3, 0)
        nd4, _, _ = sticky_filter_h5(
            nd3, since3, e1s3, 11.2, 1, 1.05, cand, follow_h5_exit=True, inflight_hold=True
        )
        self.assertEqual(nd4, 1)

    def test_h8_enter_confirm_blocks_first_tick(self):
        from command141_h6_policy import enter_confirm_gate
        g1, s1 = enter_confirm_gate(1, 0, 0, 2)
        self.assertEqual(g1, 0)
        self.assertEqual(s1, 1)
        g2, s2 = enter_confirm_gate(1, 0, s1, 2)
        self.assertEqual(g2, 1)
        self.assertEqual(s2, 2)
        g3, s3 = enter_confirm_gate(0, 1, s2, 2)
        self.assertEqual(g3, 0)
        self.assertEqual(s3, 0)

    def test_h9_exit_confirm_holds_one_isolated_zero(self):
        from command141_h6_policy import exit_confirm_gate
        g1, z1 = exit_confirm_gate(0, 1, 0, 2)
        self.assertEqual(g1, 1)
        self.assertEqual(z1, 1)
        g2, z2 = exit_confirm_gate(0, 1, z1, 2)
        self.assertEqual(g2, 0)
        self.assertEqual(z2, 2)
        g3, z3 = exit_confirm_gate(1, 0, z2, 2)
        self.assertEqual(g3, 1)
        self.assertEqual(z3, 0)


if __name__ == "__main__":
    unittest.main()
