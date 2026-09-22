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

"""command153: AUTHORIZED exact-key may unstick a FIDELITY fail-closed canary key; CONSUMED may not."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TON = ton_root()
SRC = TON / "scripts" / "command148_canary_cell.py"


def _load():
    spec = importlib.util.spec_from_file_location("command148_canary_cell", SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestExactKeyAuthorized(unittest.TestCase):
    def test_authorized_matches_key(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state" / "COMMAND153_EXACT_KEY_RERUN.json"
            p.parent.mkdir(parents=True)
            p.write_text(
                json.dumps(
                    {
                        "status": "AUTHORIZED",
                        "affected_key": "c148can_redandblack_4g_u20_HV3_COMPONENT_s151",
                        "n_applied": 0,
                    }
                )
            )
            with mock.patch.object(mod, "REPO", Path(td)):
                body = mod.exact_key_authorized("c148can_redandblack_4g_u20_HV3_COMPONENT_s151")
            self.assertIsNotNone(body)

    def test_consumed_does_not_match(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state" / "COMMAND153_EXACT_KEY_RERUN.json"
            p.parent.mkdir(parents=True)
            p.write_text(
                json.dumps(
                    {
                        "status": "CONSUMED",
                        "affected_key": "c148can_redandblack_4g_u20_HV3_COMPONENT_s151",
                        "n_applied": 1,
                    }
                )
            )
            with mock.patch.object(mod, "REPO", Path(td)):
                body = mod.exact_key_authorized("c148can_redandblack_4g_u20_HV3_COMPONENT_s151")
            self.assertIsNone(body)

    def test_wrong_key_does_not_match(self):
        mod = _load()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state" / "COMMAND153_EXACT_KEY_RERUN.json"
            p.parent.mkdir(parents=True)
            p.write_text(
                json.dumps(
                    {
                        "status": "AUTHORIZED",
                        "affected_key": "other_key",
                        "n_applied": 0,
                    }
                )
            )
            with mock.patch.object(mod, "REPO", Path(td)):
                body = mod.exact_key_authorized("c148can_redandblack_4g_u20_HV3_COMPONENT_s151")
            self.assertIsNone(body)


if __name__ == "__main__":
    unittest.main()
