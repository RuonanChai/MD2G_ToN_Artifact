#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""command124 — local→global UID mapping must never use local + user_offset."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from strategies.native9rep_baseline_common import first_uid_from_offset, local_to_global_uid


def _map_range(user_offset: int, locals_: range) -> list[int]:
    first = first_uid_from_offset(user_offset)
    return [local_to_global_uid(local, first) for local in locals_]


class TestUidMapping(unittest.TestCase):
    def test_r1_offset_1_maps_h1_to_h10(self):
        globals_ = _map_range(1, range(1, 11))
        self.assertEqual(globals_, list(range(1, 11)))
        self.assertNotIn(21, globals_)

    def test_r2_offset_11_maps_h11_to_h20(self):
        globals_ = _map_range(11, range(1, 11))
        self.assertEqual(globals_, list(range(11, 21)))
        self.assertNotIn(21, globals_)

    def test_not_local_plus_offset(self):
        user_offset = 11
        first = first_uid_from_offset(user_offset)
        for local in range(1, 11):
            correct = local_to_global_uid(local, first)
            buggy = int(local) + int(user_offset)
            self.assertEqual(correct, first + local - 1)
            self.assertNotEqual(correct, buggy)
        buggy_set = {local + user_offset for local in range(1, 11)}
        correct_set = set(_map_range(user_offset, range(1, 11)))
        self.assertIn(21, buggy_set)
        self.assertNotIn(21, correct_set)
        self.assertEqual(max(correct_set), 20)

    def test_members_inside_canonical_interval(self):
        for offset, n in ((1, 10), (11, 10), (1, 20)):
            first = first_uid_from_offset(offset)
            last = first + n - 1
            members = _map_range(offset, range(1, n + 1))
            self.assertEqual(members[0], first)
            self.assertEqual(members[-1], last)
            self.assertTrue(all(first <= g <= last for g in members))


if __name__ == "__main__":
    unittest.main()
