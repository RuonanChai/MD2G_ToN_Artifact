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

"""E017: canary launch must set SKIP_PING_ALL, the name moq_cluster actually reads."""
import unittest
from pathlib import Path

TON = ton_root()
CELL = TON / "scripts" / "command148_canary_cell.py"
CLUSTER = Path("str(artifact_root())/moq_cluster_Sigcomm.py")


class TestSkipPingAllEnv(unittest.TestCase):
    def test_canary_cell_sets_cluster_env_name(self):
        txt = CELL.read_text()
        self.assertIn('"SKIP_PING_ALL": "1"', txt)

    def test_cluster_honors_mm26_alias(self):
        txt = CLUSTER.read_text()
        self.assertIn("MM26_SKIP_PING_ALL", txt)
        self.assertIn("SIGCOMM_SKIP_PINGALL", txt)


if __name__ == "__main__":
    unittest.main()
