"""ToN corpus-claim audit helpers. NOT_IN_CONTRACT surfaces are N/A, not conjunction failures."""
from __future__ import annotations

NA_TON_SURFACES = (
    "GPU_provenance_PASS",
    "no_black_blue_solid_color_visual_failure",
    "valid_HTTP_206_range",
)

TON_CONJUNCTION_KEYS = (
    "validator_PASS",
    "DATA_SANITY_finite_U_Ro_Rq_Rb_Bshared_Bunicast",
    "paper_facing_metrics_complete_for_frozen_ToN_contract",
    "finite_throughput_latency_QoE_system_utility",
)

PASS_STATUSES = {"PASS", "PASS_ON_CONTRACTED_U"}


def report_surface(name: str, *, n: int = 0, note: str = "") -> dict:
    """GPU / RGB visual / HTTP 206 are out of the nested-MoQ ToN contract."""
    if name in NA_TON_SURFACES:
        return {
            "status": "N/A",
            "contract_status": "NOT_IN_CONTRACT",
            "in_ton_conjunction": False,
            "n_hits": n,
            "note": note,
        }
    return {"status": "UNSET", "in_ton_conjunction": True, "note": note}


def ton_conjunction_pass(checklist: dict) -> bool:
    """True only if contracted ToN gates PASS. N/A / NOT_IN_CONTRACT surfaces are excluded."""
    for key in TON_CONJUNCTION_KEYS:
        rec = checklist.get(key) or {}
        st = str(rec.get("status") or "")
        if st not in PASS_STATUSES:
            return False
    for key in NA_TON_SURFACES:
        rec = checklist.get(key) or {}
        if rec.get("in_ton_conjunction") is True:
            return False
        st = str(rec.get("status") or "")
        if st not in ("N/A", "NOT_IN_CONTRACT", ""):
            if rec.get("in_ton_conjunction", False):
                return False
    return True


def corpus_claim_verdict(
    *,
    loot_sealed: bool,
    maindev_n: int,
    loot_frozen: bool,
    ton_conjunction_ok: bool,
) -> str:
    """Claim readiness. Incomplete DEV or sealed holdout cannot be SUPPORTED.

    ``ton_conjunction_ok`` is recorded by the caller. N/A surfaces must not
    be the reason this returns INCONCLUSIVE.
    """
    _ = ton_conjunction_ok
    if loot_sealed or (not loot_frozen) or int(maindev_n) < 945:
        return "INCONCLUSIVE"
    return "INCONCLUSIVE"
