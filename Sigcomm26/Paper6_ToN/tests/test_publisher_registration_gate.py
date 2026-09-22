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

"""command40: publisher gate must match hang announce broadcast=<name> (no anon/)."""
import sys
from pathlib import Path

REPO = artifact_root()
sys.path.insert(0, str(REPO))

import moq_cluster_Sigcomm as m


SAMPLE_HANG = """
2026-07-21T23:30:01Z INFO moq_lite::lite::publisher: announce broadcast=base1
2026-07-21T23:30:01Z INFO moq_lite::session: connected
"""

SAMPLE_WRONG_R0 = """
moq_lite::lite::publisher: announce broadcast=anon/base1
"""


def test_hang_announce_matches_bare_name():
    assert m.publisher_registered_in_hang_log(SAMPLE_HANG, "base1") is True
    assert m.hang_announce_pattern("base1").search(SAMPLE_HANG)


def test_hang_announce_rejects_anon_prefix_as_required_form():
    # Gate looks for bare name; anon/ form is the OLD wrong r0 pattern.
    # Bare matcher must NOT require anon/.
    assert m.hang_announce_pattern("base1").search("announce broadcast=base1\n")
    # anon/base1 should not satisfy the bare-name regex (no anon/ allowed in match group)
    assert not m.hang_announce_pattern("base1").search("announce broadcast=anon/base1\n")


def test_missing_announce_fails_unless_alive_fallback():
    empty = "quic handshake ok"
    assert m.publisher_registered_in_hang_log(empty, "base1", alive=False) is False
    assert m.publisher_registered_in_hang_log("session connected to relay", "base1", alive=True) is True


def test_old_r0_pattern_is_not_used_in_source_gate():
    src = (REPO / "moq_cluster_Sigcomm.py").read_text(encoding="utf-8")
    assert "announce\\s+broadcast=anon/" not in src
    assert "announce broadcast=anon/" not in src or "WITHOUT" in src or "no anon" in src.lower()
    assert "PUBLISHER_REGISTRATION_GATE" in src or "publisher_registered_in_hang_log" in src


if __name__ == "__main__":
    test_hang_announce_matches_bare_name()
    test_hang_announce_rejects_anon_prefix_as_required_form()
    test_missing_announce_fails_unless_alive_fallback()
    test_old_r0_pattern_is_not_used_in_source_gate()
    print("OK test_publisher_registration_gate")
