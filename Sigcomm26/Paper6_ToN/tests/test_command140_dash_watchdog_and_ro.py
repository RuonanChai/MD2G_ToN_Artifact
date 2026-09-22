#!/usr/bin/env python3
"""Regression: DASH companion next_action unchanged is not stall while live signals move.

Also: hardcoded DASH Ro=0.20 is not the physical-sharing formula.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TON / "scripts"))
from command140_dash_live_progress import classify_stall  # noqa: E402
from command96_cross_transport_metric import physical_sharing_ro, u_eval  # noqa: E402


class TestCommand140Watchdog(unittest.TestCase):
    def test_next_action_unchanged_with_rising_perf_is_not_stall(self):
        prev = {
            "next": "DASH_COMPANION_16",
            "dash_done": 10,
            "live_perf_rows": 100,
            "live_rx_bytes_sum": 1e6,
            "live_latest_perf_timestamp": 1.0,
            "live_latest_perf_mtime": 1.0,
            "live_perf_files": 20,
        }
        sig = dict(prev)
        sig["live_perf_rows"] = 180
        sig["live_rx_bytes_sum"] = 2e6
        sig["live_latest_perf_timestamp"] = 2.0
        v = classify_stall(idle_s=2000.0, deadline_s=180.0, sig=sig, prev_sig=prev)
        self.assertFalse(v["stall"])
        self.assertEqual(v["reason"], "live_cell_progress")
        self.assertTrue(v["next_action_unchanged_is_not_stall_while_live_progress"])

    def test_frozen_live_signals_past_deadline_is_stall(self):
        sig = {
            "next": "DASH_COMPANION_16",
            "dash_done": 10,
            "live_perf_rows": 100,
            "live_rx_bytes_sum": 1e6,
            "live_latest_perf_timestamp": 1.0,
            "live_latest_perf_mtime": 1.0,
            "live_perf_files": 20,
        }
        v = classify_stall(idle_s=2000.0, deadline_s=180.0, sig=sig, prev_sig=sig)
        self.assertTrue(v["stall"])

    def test_short_idle_is_not_stall_even_if_frozen(self):
        sig = {"next": "DASH_COMPANION_16", "live_perf_rows": 1}
        v = classify_stall(idle_s=10.0, deadline_s=180.0, sig=sig, prev_sig=sig)
        self.assertFalse(v["stall"])


class TestCommand140Ro(unittest.TestCase):
    def test_u_weights_frozen(self):
        self.assertAlmostEqual(u_eval(0.0, 1.0, 0.0), 0.60)
        self.assertAlmostEqual(u_eval(1.0, 1.0, 0.0), 0.85)

    def test_independent_unicast_bytes_yield_ro_near_zero(self):
        with tempfile.TemporaryDirectory() as d:
            cell = Path(d)
            (cell / "UNICAST_AUTHENTICITY_PROOF.json").write_text(
                json.dumps({"independent_http_sessions": True, "shared_moq_broadcast": False})
            )
            (cell / "LINK_IFACE_COUNTERS.json").write_text(
                json.dumps({"byte_deltas": {"r0_r1": 108030780, "r1_hosts": 108038993}})
            )
            ro = physical_sharing_ro(cell)
            self.assertIsNotNone(ro)
            self.assertLess(ro, 0.01)
            self.assertNotAlmostEqual(ro, 0.20, places=2)

    def test_occupancy_fallback_zero_without_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            cell = Path(d)
            (cell / "UNICAST_AUTHENTICITY_PROOF.json").write_text(
                json.dumps({"independent_http_sessions": True, "shared_moq_broadcast": False})
            )
            self.assertEqual(physical_sharing_ro(cell), 0.0)


if __name__ == "__main__":
    unittest.main()
