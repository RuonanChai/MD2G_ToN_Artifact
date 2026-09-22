"""Supporting stall metric. Not folded into Rq or U.

Frozen: post-warmup seconds with no ACTUALLY DECODABLE composition.
Does not claim MOS. Does not replace Rb. Placeholder zero is forbidden once this
status is COMPUTED.
"""
from __future__ import annotations

WARMUP_S = 10.0
STATUS = "DECODE_GAP_SECONDS_POST_WARMUP"


def _empty_decoded(val) -> bool:
    return val in (None, "", "null", "None")


def stall_seconds_from_receipts(rows: list[dict], *, warmup_s: float = WARMUP_S) -> tuple[float, str]:
    if not rows:
        return 0.0, STATUS
    t0 = None
    stall = 0.0
    prev_t = None
    for rec in rows:
        try:
            t = float(rec.get("ts") or 0.0)
        except (TypeError, ValueError):
            continue
        if t0 is None:
            t0 = t
            prev_t = t
            continue
        dt = max(0.0, t - (prev_t if prev_t is not None else t))
        prev_t = t
        if (t - t0) < float(warmup_s):
            continue
        if _empty_decoded(rec.get("decoded_state")):
            stall += dt
    return float(stall), STATUS
