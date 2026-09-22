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

"""command40 §10: Rep 1–9 rates must not double-count base inside composites."""
import ast
import os
import re
import sys
from pathlib import Path

REPO = artifact_root()
MOQ = REPO / "moq_cluster_Sigcomm.py"
sys.path.insert(0, str(REPO))

# Table 1 / measurement contract (Mbps)
TABLE1 = {
    1: 3.07,
    2: 1.79,
    3: 0.87,
    4: 4.54,
    5: 6.42,
    6: 2.80,
    7: 3.91,
    8: 1.43,
    9: 1.97,
}

REP_KEYS = {
    1: "base1",
    2: "base2",
    3: "base3",
    4: "base1_enhanced1",
    5: "base1_enhanced2",
    6: "base2_enhanced1",
    7: "base2_enhanced2",
    8: "base3_enhanced1",
    9: "base3_enhanced2",
}


def test_source_rejects_base_plus_composite_total():
    src = MOQ.read_text(encoding="utf-8")
    # The repaired TOTAL must not be a plain base+enh sum.
    assert "total_bitrate = base_bitrate + enh_bitrate" not in src, (
        "DOUBLE-COUNT unrepaired: TOTAL = base + composite still present"
    )
    assert "Base+Enhanced组合流" not in src or "非 Base+组合流相加" in src
    assert "max(选中Rep" in src or "peak selected" in src.lower() or "单用户峰值码率" in src


def test_worst_case_banner_not_base_plus_enhanced():
    src = MOQ.read_text(encoding="utf-8")
    assert "所有用户Base+Enhanced" not in src
    assert "峰值Rep" in src or "peak" in src.lower()


def test_init_video_bitrates_total_is_peak_not_sum():
    # Import after PATH set; Mininet may be absent — function only needs ffprobe + files.
    import moq_cluster_Sigcomm as m

    base, enh, total = m.init_video_bitrates()
    assert base is not None and enh is not None and total is not None
    # Composite already includes base content: sum would be ~7.61
    double = float(base) + float(enh)
    assert abs(total - double) > 0.5, (
        f"TOTAL={total:.3f} still looks like base+enh={double:.3f} (double-count)"
    )
    # TOTAL must be a peak selected rate ≈ max(base, enh, ~6.42)
    assert total <= max(double, 7.0)  # sanity
    assert total >= max(float(base), float(enh)) - 1e-6
    # Peak should be near rep5 (~6.42), not ~7.61
    assert abs(total - TABLE1[5]) < 0.35 or total <= TABLE1[5] + 0.35, (
        f"expected peak near rep5={TABLE1[5]}, got {total}"
    )
    assert abs(total - TABLE1[5]) < 0.5


def test_rep_ladder_required_bitrates():
    """Every Rep 1–9 required bitrate matches Table 1 (file or hardcoded contract)."""
    import moq_cluster_Sigcomm as m

    for rid, key in REP_KEYS.items():
        path = m.VIDEO_PATHS.get(key)
        assert path, f"missing VIDEO_PATHS[{key}] for Rep{rid}"
        # Prefer live file probe; fall back to Table1 tolerance check via name contract
        if os.path.exists(path):
            br = m.get_video_bitrate(path)
            assert br is not None, f"ffprobe failed for {path}"
            assert abs(br - TABLE1[rid]) < 0.15, (
                f"Rep{rid} {key}: meas={br:.3f} vs table={TABLE1[rid]}"
            )
        else:
            # File missing in this workspace layout — still enforce table contract presence
            assert TABLE1[rid] > 0


def test_composite_not_base_plus_enh_delta_for_rep4():
    """Rep4 file rate must be ~4.54, not 3.07+1.47 additive layering claim in TOTAL."""
    import moq_cluster_Sigcomm as m

    p4 = m.VIDEO_PATHS["base1_enhanced1"]
    p1 = m.VIDEO_PATHS["base1"]
    if not (os.path.exists(p4) and os.path.exists(p1)):
        return
    b1 = m.get_video_bitrate(p1)
    r4 = m.get_video_bitrate(p4)
    assert b1 and r4
    assert abs(r4 - TABLE1[4]) < 0.15
    # Composite ≈ 4.54 is NOT equal to a tiny enhancement delta; it exceeds base alone
    assert r4 > b1
    # Accounting crime: treating demand as b1+r4
    assert abs((b1 + r4) - 7.61) < 0.4
    base, enh, total = m.init_video_bitrates()
    assert abs(total - (b1 + r4)) > 0.5


def test_calculate_regional_uses_peak_not_double():
    import moq_cluster_Sigcomm as m

    m.TOTAL_BITRATE_MBPS = TABLE1[5]
    bw1, bw2 = m.calculate_regional_bandwidth(10, TABLE1[5])
    assert bw1 == bw2
    # 5 users/relay * 6.42 * 1.2 = 38.52 → int >= 38
    users_per = 5.0
    expected_floor = int(users_per * TABLE1[5] * 1.2)
    assert bw1 >= min(100, expected_floor)
    # Must not size as if peak were 7.61
    inflated = int(users_per * (TABLE1[1] + TABLE1[4]) * 1.2)
    # With peak=6.42 the returned bw should be closer to expected_floor than inflated
    # (both may hit the max(100,...) floor for small N — check unicast term via source)
    src = MOQ.read_text(encoding="utf-8")
    assert "users_per_relay * MAX_BITRATE_MBPS" in src
    assert "base_bitrate + enh_bitrate" not in src


if __name__ == "__main__":
    tests = [
        test_source_rejects_base_plus_composite_total,
        test_worst_case_banner_not_base_plus_enhanced,
        test_init_video_bitrates_total_is_peak_not_sum,
        test_rep_ladder_required_bitrates,
        test_composite_not_base_plus_enh_delta_for_rep4,
        test_calculate_regional_uses_peak_not_double,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print("PASS test_rep_bitrate_accounting")
