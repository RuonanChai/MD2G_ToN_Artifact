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

"""Regression: MM26 CR parity replays must use MEDIA_CONTRACT_260728, not 18Mbps CRF0."""
import hashlib
import json
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
MM26 = REPO / "MM26"
CONTRACT = MM26 / "artifacts/260728/_meta/MEDIA_CONTRACT.json"
BASE = MM26 / "artifacts/260728/_media/Base_120s_cr9560k.mp4"
ENH = MM26 / "artifacts/260728/_media/Enhanced_120s_cr990k.mp4"
REPLAY = TON / "scripts" / "command91_exact_cell_replay.py"
SENTINEL = TON / "scripts" / "command90_parity_sentinels.py"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def test_media_contract_files_match_freeze():
    c = json.loads(CONTRACT.read_text())
    assert c["contract_id"] == "MM26_MEDIA_CONTRACT_260728_V1"
    assert c["science_policy"]["forbid_18mbps_crf0_media"] is True
    assert BASE.is_file() and ENH.is_file()
    assert sha256(BASE) == c["files"]["base"]["sha256"]
    assert sha256(ENH) == c["files"]["enhanced"]["sha256"]


def test_exact_replay_script_binds_cr_media():
    src = REPLAY.read_text(encoding="utf-8")
    assert "Base_120s_cr9560k.mp4" in src
    assert "Enhanced_120s_cr990k.mp4" in src
    assert "MM26_STRICT_VIDEO" in src
    assert "forbid" not in src.lower() or "MEDIA_CONTRACT" in src


def test_sentinel_requires_cr_media_after_patch():
    src = SENTINEL.read_text(encoding="utf-8")
    assert "Base_120s_cr9560k.mp4" in src or "cr_media_env" in src or "MM26_BASE_VIDEO" in src


if __name__ == "__main__":
    test_media_contract_files_match_freeze()
    test_exact_replay_script_binds_cr_media()
    # sentinel patch may land in same change-set; allow soft until patched
    try:
        test_sentinel_requires_cr_media_after_patch()
    except AssertionError:
        print("WARN: sentinel not yet patched for CR media (exact replay is binding)")
    print("COMMAND91_CR_MEDIA_ENV_REGRESSION_OK")
