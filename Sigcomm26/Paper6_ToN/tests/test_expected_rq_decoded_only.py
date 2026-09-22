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

"""E015: undecoded users have Rq=0; never expect target_state Q."""
import sys
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command148_canary_audit import expected_rq, finite_headlines  # noqa: E402

QN = {"Rep1": 0.3, "Rep2": 0.5}


class TestExpectedRqDecodedOnly(unittest.TestCase):
    def test_undecoded_is_zero_not_target(self):
        self.assertEqual(expected_rq(None, QN), 0.0)
        self.assertEqual(expected_rq("", QN), 0.0)
        self.assertNotEqual(expected_rq(None, QN), QN["Rep2"])

    def test_decoded_uses_frozen_q(self):
        self.assertEqual(expected_rq("Rep2", QN), 0.5)

    def test_finite_headlines_is_a_real_function(self):
        ok, bad = finite_headlines(
            {"U": 0.4, "Ro_component": 0.9, "Rq": 0.3, "Rb": 0.04, "B_shared": 1, "B_unicast": 2}
        )
        self.assertTrue(ok)
        self.assertEqual(bad, [])
        ok2, bad2 = finite_headlines(None)
        self.assertFalse(ok2)
        self.assertIn("metrics_not_dict", bad2)


if __name__ == "__main__":
    unittest.main()
