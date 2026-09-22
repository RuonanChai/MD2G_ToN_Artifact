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

"""Post-Rb delivery compare is anti-regression, not exact 147 replay."""
import sys
import unittest
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "scripts"))
from command151_24cell_delivery_compare import components_not_regressed  # noqa: E402


class TestComponentsNotRegressed(unittest.TestCase):
    def test_s2_extra_enhancements_allowed(self):
        ok, missing, extra = components_not_regressed(
            ["b0", "db1", "db2"],
            ["b0", "db1", "db2", "e1", "e2"],
        )
        self.assertTrue(ok)
        self.assertEqual(missing, [])
        self.assertEqual(extra, ["e1", "e2"])

    def test_losing_b0_is_regression(self):
        ok, missing, extra = components_not_regressed(["b0", "e1"], ["e1"])
        self.assertFalse(ok)
        self.assertEqual(missing, ["b0"])


if __name__ == "__main__":
    unittest.main()
