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

"""Retry must keep /anon/; stripping it is a runtime defect, not a network result."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = artifact_root()
SPEC = importlib.util.spec_from_file_location("moq_sub_with_latency", ROOT / "moq_sub_with_latency.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules["moq_sub_with_latency"] = mod
SPEC.loader.exec_module(mod)


class TestRetryPreservesAnon(unittest.TestCase):
    def test_root_url_gains_anon(self):
        url, bcast = mod.canonical_subscriber_url("https://r1.local:4443/", "b0")
        self.assertEqual(url, "https://r1.local:4443/anon/")
        self.assertEqual(bcast, "b0")

    def test_anon_path_kept(self):
        url, bcast = mod.canonical_subscriber_url("https://r1.local:4443/anon/", "e1")
        self.assertEqual(url, "https://r1.local:4443/anon/")
        self.assertEqual(bcast, "e1")

    def test_retry_equals_initial(self):
        initial, _ = mod.canonical_subscriber_url("https://r2.local:4443/", "db2")
        retry, _ = mod.canonical_subscriber_url(initial, "db2")
        self.assertEqual(initial, retry)
        self.assertTrue(retry.endswith("/anon/"))
        self.assertNotEqual(retry, "https://r2.local:4443/")

    def test_never_kill_live_subscriber(self):
        self.assertFalse(mod.should_restart_dead_subscriber(None, 0))
        self.assertFalse(mod.should_restart_dead_subscriber(None, 50))
        self.assertTrue(mod.should_restart_dead_subscriber(1, 0))
        self.assertFalse(mod.should_restart_dead_subscriber(1, 500))


if __name__ == "__main__":
    unittest.main()
