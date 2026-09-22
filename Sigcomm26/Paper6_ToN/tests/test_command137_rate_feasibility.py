from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Regression: RATE_FEASIBILITY_GATE uses the frozen buffer model, not P10 alone."""
import importlib.util
from pathlib import Path

REPO = artifact_root()
MOD = REPO / "Sigcomm26" / "Paper6_ToN" / "scripts" / "command137_rate_feasibility_offline.py"


def _load():
    spec = importlib.util.spec_from_file_location("c137_off", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_p10_below_b3_is_not_automatic_fail():
    m = _load()
    # Capacity always 10 Mbps, B3=0.51: no stall despite any P10 story.
    body = m.simulate([10.0] * 120, 0.51)
    assert body["startup_reached"]
    assert body["stall_s"] == 0.0
    assert body["frac_below_B3"] == 0.0


def test_structural_zero_capacity_stalls():
    m = _load()
    body = m.simulate([0.05] * 120, 0.51)
    assert body["stall_s"] > 5.0
    assert body["deficit_duration_s"] == 120.0
    assert body["deficit_bytes"] > 0


def test_4g_csv_loads_full_series():
    m = _load()
    xs = m.load_4g()
    assert len(xs) >= 900
    assert min(xs) >= 0.0
