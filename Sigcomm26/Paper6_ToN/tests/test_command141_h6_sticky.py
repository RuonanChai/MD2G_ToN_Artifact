#!/usr/bin/env python3
"""H6 sticky enhancement: dwell/hysteresis, no chatter, emergency drop."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command141_h6_policy import H6Candidate, sticky_step  # noqa: E402


def cand(**kw):
    base = dict(
        id="t",
        enter_headroom_mbps=0.40,
        exit_headroom_mbps=0.12,
        min_dwell_s=8.0,
        enter_buffer_s=1.5,
        exit_buffer_s=0.80,
        completion_p=0.80,
        completion_lat_s=1.02,
        e2_headroom_mbps=3.50,
        e2_min_e1_dwell_s=8.0,
        e2_min_dwell_s=8.0,
        emergency_buffer_s=0.35,
    )
    base.update(kw)
    return H6Candidate(**base)


class TestH6Sticky(unittest.TestCase):
    def test_enter_then_hold_through_headroom_dip(self):
        c = cand()
        d, s, e1 = 0, 0.0, 0.0
        d, s, e1 = sticky_step(d, s, e1, 10.0, 1.0, 4.0, c)
        self.assertEqual(d, 1)
        d2, s2, e1 = sticky_step(d, s, e1, 12.0, 0.20, 4.0, c)  # still in dwell
        self.assertEqual(d2, 1)
        self.assertEqual(s2, s)

    def test_exit_after_dwell_when_headroom_below_exit(self):
        c = cand()
        d, s, e1 = sticky_step(0, 0.0, 0.0, 10.0, 1.0, 4.0, c)
        d, s, e1 = sticky_step(d, s, e1, 20.0, 0.05, 2.0, c)
        self.assertEqual(d, 0)

    def test_emergency_drops_immediately(self):
        c = cand()
        d, s, e1 = sticky_step(0, 0.0, 0.0, 10.0, 1.0, 4.0, c)
        d, _, _ = sticky_step(d, s, e1, 11.0, 2.0, 0.10, c)
        self.assertEqual(d, 0)

    def test_e2_requires_stable_e1(self):
        c = cand()
        d, s, e1 = sticky_step(0, 0.0, 0.0, 10.0, 5.0, 5.0, c)
        self.assertEqual(d, 1)
        d, s, e1 = sticky_step(d, s, e1, 12.0, 5.0, 5.0, c)
        self.assertEqual(d, 1)
        d, s, e1 = sticky_step(d, s, e1, 19.0, 5.0, 5.0, c)
        self.assertEqual(d, 2)

    def test_no_e2_when_guard_huge(self):
        c = cand(e2_headroom_mbps=99.0, e2_min_e1_dwell_s=999.0)
        d, s, e1 = sticky_step(0, 0.0, 0.0, 10.0, 5.0, 5.0, c)
        d, s, e1 = sticky_step(d, s, e1, 30.0, 5.0, 5.0, c)
        self.assertEqual(d, 1)


if __name__ == "__main__":
    unittest.main()
