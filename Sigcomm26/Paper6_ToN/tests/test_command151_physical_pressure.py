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

"""Unit tests for physical-pressure Rb. No Mininet."""
import math
import sys
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command148_canary_audit import _qnorm, finite_headlines  # noqa: E402
from command151_physical_pressure import samples_from_rows  # noqa: E402


class TestPressureRb(unittest.TestCase):
    def test_low_load_near_zero(self):
        cap = 10e6
        rows = [{"t": i, "tx_bytes": i * 1000, "rx_bytes": 0} for i in range(10)]
        got = samples_from_rows(rows, cap, 0.02, 0.90)
        self.assertIsNotNone(got["Rb"])
        self.assertLess(got["Rb"], 0.05)
        self.assertTrue(math.isfinite(got["Rb"]))

    def test_near_capacity_high(self):
        cap = 10e6
        # 10 Mbps = 1.25e6 bytes/s
        rows = [{"t": float(i), "tx_bytes": int(i * 1.25e6), "rx_bytes": 0} for i in range(12)]
        got = samples_from_rows(rows, cap, 0.02, 0.90)
        self.assertGreater(got["Rb"], 0.9)

    def test_not_a_function_of_ro(self):
        cap = 10e6
        rows = [{"t": float(i), "tx_bytes": int(i * 1.25e6), "rx_bytes": 0} for i in range(8)]
        rb = samples_from_rows(rows, cap, 0.02, 0.90)["Rb"]
        self.assertGreater(abs(rb - 0.5), 0.2)

    def test_finite_headlines_reject_null(self):
        ok, bad = finite_headlines({"U": 0.5, "Ro_component": 0.9, "Rq": 0.4, "Rb": None, "B_shared": 1, "B_unicast": 2})
        self.assertFalse(ok)
        self.assertTrue(any("Rb=null" in x for x in bad))
        ok2, _ = finite_headlines({"U": 0.5, "Ro_component": 0.9, "Rq": 0.4, "Rb": 0.1, "B_shared": 1, "B_unicast": 2})
        self.assertTrue(ok2)

    def test_qnorm_restored(self):
        qn = _qnorm("redandblack")
        self.assertTrue(isinstance(qn, dict))
        self.assertIn("Rep1", qn)


if __name__ == "__main__":
    unittest.main()
