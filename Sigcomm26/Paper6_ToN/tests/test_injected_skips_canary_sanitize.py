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

"""Injected DEV/scaling/loot cells must not sanitize/rewrite the rbv1 canary queue."""
import unittest
from pathlib import Path

TON = ton_root()
CELL = TON / "scripts" / "command148_canary_cell.py"


class TestInjectedSkipsCanarySanitize(unittest.TestCase):
    def test_spec_json_returns_before_sanitize(self):
        txt = CELL.read_text()
        spec_idx = txt.find('spec_env = os.environ.get("COMMAND148_SPEC_JSON"')
        inj_idx = txt.find("return _main_injected(spec_env)")
        san_idx = txt.find("q = sanitize_wrong_treatment(load_q())")
        self.assertGreater(spec_idx, 0)
        self.assertGreater(inj_idx, spec_idx)
        self.assertGreater(san_idx, inj_idx)


if __name__ == "__main__":
    unittest.main()
