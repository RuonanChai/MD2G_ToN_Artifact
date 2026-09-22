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

from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_nested_runtime import schedule_targets, matrix, N_USERS  # noqa: E402


def test_matrix_is_24():
    rows = matrix()
    assert len(rows) == 24
    assert len({r["key"] for r in rows}) == 24


def test_s0_constant_b1():
    for t in (0, 10, 60, 119):
        tgt = schedule_targets("S0_B1_only", t)
        assert tgt == {f"u{i}": "Rep1" for i in range(1, N_USERS + 1)}


def test_s1_phases():
    assert schedule_targets("S1_B1_B2_B3", 5)["u1"] == "Rep1"
    assert schedule_targets("S1_B1_B2_B3", 20)["u1"] == "Rep1"
    assert schedule_targets("S1_B1_B2_B3", 50)["u1"] == "Rep2"
    assert schedule_targets("S1_B1_B2_B3", 100)["u1"] == "Rep3"


def test_s3_mixed():
    tgt = schedule_targets("S3_mixed_share", 30)
    assert tgt["u1"] == "Rep3"
    assert tgt["u2"] == "Rep8"
    assert tgt["u3"] == "Rep9"
