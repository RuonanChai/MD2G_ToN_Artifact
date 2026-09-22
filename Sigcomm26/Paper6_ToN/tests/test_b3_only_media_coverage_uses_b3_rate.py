from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""COMMAND138: B3-only media coverage must use S3/B3 rate, never S9 or native9 Rep3."""
import sys
from pathlib import Path

sys.path.insert(0, str(artifact_root()))
from strategies.true_content_layered_lifecycle import (
    media_seconds_from_useful_bytes,
    playable_bitrate_bps,
)

TRACKS = {
    "base3": {"bit_rate_bps": 321389},
    "base3_enh1_only": {"bit_rate_bps": 356685},
    "base3_enh2_only": {"bit_rate_bps": 360960},
}


def test_s3_bytes_use_b3_rate_not_s9():
    useful = 4_605_841
    s3 = playable_bitrate_bps(TRACKS, 3, 0)
    s9 = playable_bitrate_bps(TRACKS, 3, 2)
    assert s3 == 321389
    assert s9 == 321389 + 356685 + 360960
    cov_s3 = media_seconds_from_useful_bytes(useful, s3)
    cov_s9 = media_seconds_from_useful_bytes(useful, s9)
    assert cov_s3 > 100.0
    assert cov_s9 < 40.0
    assert abs(cov_s3 / cov_s9 - s9 / s3) < 1e-9


def test_e1_e2_change_denom_only_when_subscribed():
    useful = 1_000_000
    b3 = playable_bitrate_bps(TRACKS, 3, 0)
    b3e1 = playable_bitrate_bps(TRACKS, 3, 1)
    b3e1e2 = playable_bitrate_bps(TRACKS, 3, 2)
    assert b3e1 == b3 + 356685
    assert b3e1e2 == b3e1 + 360960
    assert media_seconds_from_useful_bytes(useful, b3) > media_seconds_from_useful_bytes(useful, b3e1)
    assert media_seconds_from_useful_bytes(useful, b3e1) > media_seconds_from_useful_bytes(useful, b3e1e2)


def test_native9_rep3_087_is_not_s3():
    s3 = playable_bitrate_bps(TRACKS, 3, 0) / 1e6
    assert abs(s3 - 0.87) / 0.87 > 0.5
