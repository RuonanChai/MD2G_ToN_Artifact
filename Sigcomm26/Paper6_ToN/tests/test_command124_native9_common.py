#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command124 — native9rep_baseline_common contract tests (stdlib)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
TON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from strategies.native9rep_baseline_common import (  # noqa: E402
    BASE_ENH_TO_REP,
    REP_TO_BASE_ENH,
    base_enh_to_rep,
    highest_quality_feasible_rep,
    load_content_bitrate_map,
    rep_bitrate,
    rep_quality,
    rep_to_base_enh,
)

BITRATE_MAP = TON / "state" / "COMMAND106_CONTENT_REP_BITRATES.json"


class TestNative9Common(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        os.environ["TON_CONTENT_REP_BITRATES_JSON"] = str(BITRATE_MAP)
        os.environ["TON_BITRATE_FAIL_CLOSED"] = "1"
        for rid in range(1, 10):
            os.environ.pop(f"REP{rid}_BITRATE_MBPS", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_rep1_to_rep9_round_trip(self):
        for rid in range(1, 10):
            base, depth = rep_to_base_enh(rid)
            self.assertEqual((base, depth), REP_TO_BASE_ENH[rid])
            self.assertEqual(base_enh_to_rep(base, depth), rid)
            self.assertEqual(BASE_ENH_TO_REP[(base, depth)], rid)

    def test_quality_ordering_uses_quality_map_not_numeric_id(self):
        qmap = {1: 1.0, 2: 9.0, 3: 5.0, 4: 2.0, 5: 3.0, 6: 4.0, 7: 6.0, 8: 7.0, 9: 8.0}
        with mock.patch(
            "strategies.native9rep_baseline_common.load_quality_map", return_value=qmap
        ), mock.patch(
            "strategies.native9rep_baseline_common.rep_bitrate", return_value=0.1
        ), mock.patch(
            "strategies.native9rep_baseline_common.device_feasible", return_value=True
        ):
            chosen = highest_quality_feasible_rep(
                capacity_mbps=100.0, device_score=1.0, content="redandblack"
            )
        self.assertEqual(chosen, 2)
        self.assertNotEqual(chosen, 9)
        self.assertGreater(rep_quality(2, qmap), rep_quality(9, qmap))

    def test_redandblack_vs_longdress_bitrates_from_command106(self):
        self.assertTrue(BITRATE_MAP.is_file())
        rb = load_content_bitrate_map("redandblack")
        ld = load_content_bitrate_map("longdress")
        self.assertAlmostEqual(rb[1], 2.873301, places=6)
        self.assertAlmostEqual(ld[1], 3.005783, places=6)
        self.assertNotEqual(rb[1], ld[1])
        self.assertAlmostEqual(rep_bitrate(1, "redandblack"), rb[1])
        self.assertAlmostEqual(rep_bitrate(5, "longdress"), ld[5])

    def test_missing_bitrate_fails_closed(self):
        os.environ["TON_BITRATE_FAIL_CLOSED"] = "1"
        os.environ["TON_CONTENT_REP_BITRATES_JSON"] = str(BITRATE_MAP)
        os.environ["TON_CONTENT_ID"] = "no_such_content_xyz"
        rates = load_content_bitrate_map("no_such_content_xyz")
        self.assertEqual(rates, {})
        with self.assertRaisesRegex(RuntimeError, "BITRATE_FAIL_CLOSED"):
            rep_bitrate(3, "no_such_content_xyz")


if __name__ == "__main__":
    unittest.main()
