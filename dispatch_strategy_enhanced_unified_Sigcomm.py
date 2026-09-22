# ======================================================================
# dispatch_strategy.py
# ======================================================================

import argparse, os, sys, json, time, subprocess, traceback, math, re, glob
import random
import pandas as pd
from collections import deque
import numpy as np
import threading

# Optional psutil for CPU measurement
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[WARN] psutil is not installed; CPU measurement disabled. pip install psutil", file=sys.stderr, flush=True)

# Federation-off: all users attach to r0
# Federation OFF r0

print(f"[DEBUG] Running dispatch_strategy from: {os.path.abspath(__file__)}", file=sys.stderr, flush=True)

from strategies.rep_lifecycle_v2 import (  # noqa: E402
    RepLifecycle,
    map_to_rep_id,
    plan_transition,
    rep_to_broadcast,
)
from strategies.true_content_layered_lifecycle import (  # noqa: E402
    playable_bitrate_bps as layered_playable_bitrate_bps,
    same_family_delta,
)
from strategies.instrumentation_v2 import InstrumentationV2  # noqa: E402
from strategies.media_timeline_buffer_v4 import (  # noqa: E402
    payload_ttfb_ms as v4_payload_ttfb_ms,
    playable_buffer_seconds,
    timeline_metrics_at,
)

try:
    from ton_playability_telemetry import (  # noqa: E402
        OnlineCapacityEstimator as _PlayCapEst,
        build_playability_payload as _build_playability_payload,
        run_bounded_headroom_probe as _c122_probe_burst,
        try_acquire_probe as _c122_probe_admit,
    )
except ImportError:
    _ton_lib = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Sigcomm26", "Paper6_ToN", "lib",
    )
    if _ton_lib not in sys.path:
        sys.path.insert(0, _ton_lib)
    try:
        from ton_playability_telemetry import (  # noqa: E402
            OnlineCapacityEstimator as _PlayCapEst,
            build_playability_payload as _build_playability_payload,
            run_bounded_headroom_probe as _c122_probe_burst,
            try_acquire_probe as _c122_probe_admit,
        )
    except ImportError:
        _PlayCapEst = None
        _build_playability_payload = None
        _c122_probe_burst = None
        _c122_probe_admit = None


def _metric_v4_timeline_enabled() -> bool:
    """Media-timeline buffer/stall/TTFB (command60/61); default ON."""
    return os.environ.get("SIGCOMM_METRIC_V4_TIMELINE", "1") != "0"


def _true_content_layering() -> bool:
    """COMMAND135: additive Base + enhancement-only tracks, not exclusive native9."""
    if _nested_components_enabled():
        return False
    return os.environ.get("TON_TRUE_CONTENT_LAYERING", "").strip().lower() in ("1", "true", "yes", "on")


def _nested_components_enabled() -> bool:
    """COMMAND146/147 nested incremental components b0/db1/db2/e1/e2."""
    return os.environ.get("TON_NESTED_COMPONENTS", "").strip().lower() in ("1", "true", "yes", "on")


def _md2g_h6_sticky_enabled() -> bool:
    """command141: MD2G-only completion-aware sticky enhancement. No Base/grouping."""
    if not _true_content_layering():
        return False
    if os.environ.get("MD2G_LAYERED_STICKY_ENH", "").strip().lower() not in ("1", "true", "yes", "on"):
        return False
    return str(os.environ.get("TON_STRATEGY_FINGERPRINT") or "").startswith("MD2G")


def _md2g_h6_filter_h5_enabled() -> bool:
    """H6-F: sticky filters H5/controller; does not replace admission."""
    if _md2g_h10_enabled():
        return False
    if not _md2g_h6_sticky_enabled():
        return False
    return os.environ.get("MD2G_H6_FILTER_H5", "").strip().lower() in ("1", "true", "yes", "on")


def _md2g_h10_enabled() -> bool:
    """command142: one APPLIED state, cost-amortized commit. Not N-tick hold."""
    if not _true_content_layering():
        return False
    if os.environ.get("MD2G_H10_TRANSITION_COMMIT", "").strip().lower() not in ("1", "true", "yes", "on"):
        return False
    return str(os.environ.get("TON_STRATEGY_FINGERPRINT") or "").startswith("MD2G")


def _md2g_h10_apply(run_client, proposed, buffer_s) -> int:
    try:
        _scripts = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sigcomm26", "Paper6_ToN", "scripts")
        if _scripts not in sys.path:
            sys.path.insert(0, _scripts)
        from command142_h10_policy import contract_from_env, transition_commit  # noqa: WPS433
        c = contract_from_env(os.environ)
        now = time.time()
        applied = int(getattr(run_client, "_h10_applied", 0) or 0)
        since = float(getattr(run_client, "_h10_since", now) or now)
        pending = getattr(run_client, "_h10_pending", None)
        pending = None if pending is None else int(pending)
        psince = float(getattr(run_client, "_h10_pending_since", now) or now)
        nd, ns, npn, nps = transition_commit(
            applied, since, pending, psince, now, int(proposed or 0), float(buffer_s or 0.0), c
        )
        run_client._h10_applied = int(nd)
        run_client._h10_since = float(ns)
        run_client._h10_pending = npn
        run_client._h10_pending_since = float(nps)
        return int(nd)
    except Exception:
        return int(proposed or 0)


def _md2g_h6_apply(run_client, Bu, base_rate, buffer_s) -> int:
    """Filter H5 per-tick enhancement chatter. Keep in sync with command141_h6_policy.py."""
    try:
        _scripts = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sigcomm26", "Paper6_ToN", "scripts")
        if _scripts not in sys.path:
            sys.path.insert(0, _scripts)
        from command141_h6_policy import candidate_from_env, sticky_step  # noqa: WPS433
        cand = candidate_from_env(os.environ)
        now = time.time()
        depth = int(getattr(run_client, "_h6_depth", 0) or 0)
        since = float(getattr(run_client, "_h6_since", now) or now)
        e1s = float(getattr(run_client, "_h6_e1_since", now) or now)
        hr = max(0.0, float(Bu or 0.0) - float(base_rate or 0.0))
        nd, ns, ne = sticky_step(depth, since, e1s, now, hr, float(buffer_s or 0.0), cand)
        run_client._h6_depth = int(nd)
        run_client._h6_since = float(ns)
        run_client._h6_e1_since = float(ne)
        return int(nd)
    except Exception:
        return 0


def _md2g_h6_filter_apply(run_client, proposed, buffer_s) -> int:
    try:
        _scripts = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Sigcomm26", "Paper6_ToN", "scripts")
        if _scripts not in sys.path:
            sys.path.insert(0, _scripts)
        from command141_h6_policy import candidate_from_env, enter_confirm_gate, exit_confirm_gate, sticky_filter_h5  # noqa: WPS433
        cand = candidate_from_env(os.environ)
        now = time.time()
        depth = int(getattr(run_client, "_h6_depth", 0) or 0)
        since = float(getattr(run_client, "_h6_since", now) or now)
        e1s = float(getattr(run_client, "_h6_e1_since", now) or now)
        follow = os.environ.get("MD2G_H6_FOLLOW_H5_EXIT", "").strip().lower() in ("1", "true", "yes", "on")
        inflight = os.environ.get("MD2G_H7_INFLIGHT_HOLD", "").strip().lower() in ("1", "true", "yes", "on")
        try:
            confirm = int(float(os.environ.get("MD2G_H8_ENTER_CONFIRM_TICKS", "1") or 1))
        except (TypeError, ValueError):
            confirm = 1
        try:
            exit_n = int(float(os.environ.get("MD2G_H9_EXIT_CONFIRM_TICKS", "1") or 1))
        except (TypeError, ValueError):
            exit_n = 1
        streak = int(getattr(run_client, "_h8_streak", 0) or 0)
        zstreak = int(getattr(run_client, "_h9_zero_streak", 0) or 0)
        gated, streak = enter_confirm_gate(int(proposed or 0), depth, streak, confirm)
        gated, zstreak = exit_confirm_gate(gated, depth, zstreak, exit_n)
        run_client._h8_streak = int(streak)
        run_client._h9_zero_streak = int(zstreak)
        nd, ns, ne = sticky_filter_h5(
            depth,
            since,
            e1s,
            now,
            gated,
            float(buffer_s or 0.0),
            cand,
            follow_h5_exit=follow,
            inflight_hold=inflight,
        )
        run_client._h6_depth = int(nd)
        run_client._h6_since = float(ns)
        run_client._h6_e1_since = float(ne)
        return int(nd)
    except Exception:
        return int(proposed or 0)


def _rep_lifecycle_v2_enabled() -> bool:
    """FULL_INDEPENDENT_REPS atomic lifecycle (command60/61); default enabled.

    True content-layering must not use exclusive single-Rep switches.
    """
    if _true_content_layering():
        return False
    return os.environ.get("SIGCOMM_REP_LIFECYCLE_V2", "1") != "0"


def _ton_native9rep_md2g_enabled() -> bool:
    """command108/113: honor controller native Rep1–9 selections when gated on."""
    return os.environ.get("TON_NATIVE9REP_MD2G", "").strip().lower() in ("1", "true", "yes", "on")


def _sigcomm_native9rep_decision_enabled() -> bool:
    """command124: strategy-independent native Rep1–9 actuation gate.

    SIGCOMM_NATIVE9REP_DECISION is the primary scientific gate for all four
    primary strategies (md2g_g2 / g2_rule / hv3_native9 / clustering_native9).
    TON_NATIVE9REP_MD2G remains a backward-compatible alias.
    """
    if os.environ.get("SIGCOMM_NATIVE9REP_DECISION", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    return _ton_native9rep_md2g_enabled()  # backward-compatible alias


def _opt4_structural() -> bool:
    return os.environ.get("TON_G2_OPT4_STRUCTURAL", "").strip().lower() in ("1", "true", "yes", "on")


def _opt6_honor_base_switch() -> bool:
    """command131 opt6: switch moq-sub when honored base/target_rep changes."""
    return os.environ.get("TON_G2_OPT6_HONOR_BASE_SWITCH", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _common_native9_base_switch() -> bool:
    """command131: proven opt6 base-only switch is now the common native9 contract.

    All SIGCOMM_NATIVE9REP_DECISION strategies (md2g_g2 / g2_rule / hv3_native9 /
    clustering_native9) must actuate honor base changes. This is a fidelity
    repair, not a baseline retune. Pre-promotion DEV cells are provenance-
    incompatible for gain-rep/Qs actuation claims.
    """
    return _sigcomm_native9rep_decision_enabled() or _opt6_honor_base_switch()


def _opt7_make_before_break() -> bool:
    return os.environ.get("TON_G2_OPT7_MAKE_BEFORE_BREAK", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


_EVAL_QS_TABLE1 = {
    1: 0.8, 2: 0.6, 3: 0.4, 4: 1.0, 5: 1.0, 6: 0.6, 7: 0.8, 8: 0.4, 9: 0.4,
}


def _opt7_overlap_justified(old_rep, new_rep, cap_mbps, br_old, br_new) -> bool:
    """Permit a temporary second full stream only if canonical ΔU is positive
    and the online capacity estimate can finish the new base.
    """
    try:
        old_r, new_r = int(old_rep), int(new_rep)
        cap = float(cap_mbps)
        bo, bn = float(br_old), float(br_new)
    except (TypeError, ValueError):
        return False
    if cap <= 1e-9 or bn <= 0:
        return False
    if cap + 1e-9 < bn * 1.05:
        return False
    dqs = float(_EVAL_QS_TABLE1.get(new_r, 0.4)) - float(_EVAL_QS_TABLE1.get(old_r, 0.4))
    if dqs <= 0:
        return False
    rb_overlap = min(1.0, max(0.0, (bo + bn) / max(cap, 0.15)))
    rb_single = min(1.0, max(0.0, bo / max(cap, 0.15)))
    delta_u = 0.60 * dqs - 0.15 * (rb_overlap - rb_single)
    return delta_u > 0.0


def _buffer_protection_demote_to_base3(
    *,
    host_id: int,
    current_buffer: float,
    threshold: float,
    controller_selected_rep,
    rendered_rep_before,
    iteration: int,
    reason: str,
) -> tuple[int, int, int]:
    """Common buffer-protection demotion for all native9 strategies.

    Returns (base_version, enh_level, decision) always (3, 0, 0).
    Logs controller_selected_rep, rendered_rep before/after, and exact reason.
    """
    rendered_after = 3  # map_to_rep_id(3, 0)
    if iteration % 10 == 0:
        print(
            f"[BUFFER-PROTECTION] h{host_id}: demoted "
            f"controller_selected_rep={controller_selected_rep} "
            f"rendered_rep_before={rendered_rep_before} "
            f"rendered_rep={rendered_after} "
            f"reason={reason} "
            f"(buffer={current_buffer:.2f}s < threshold={threshold}s; "
            f"common_rule=_buffer_protection_blocks_enhanced)",
            file=sys.stderr,
            flush=True,
        )
    return 3, 0, 0


def _ton_gen3_probe_arm() -> str:
    """command123: causal-arm cells use ActuationPlan as sole physical writer."""
    return (os.environ.get("TON_GEN3_PROBE_ARM") or "").strip()


def _rep_to_base_enh(rep_id: int) -> tuple[int, int]:
    """Inverse of map_to_rep_id for FULL_INDEPENDENT_REPS ladder."""
    rid = int(rep_id)
    inv = {
        1: (1, 0), 2: (2, 0), 3: (3, 0),
        4: (1, 1), 5: (1, 2),
        6: (2, 1), 7: (2, 2),
        8: (3, 1), 9: (3, 2),
    }
    if rid not in inv:
        raise ValueError(f"invalid rep_id: {rep_id}")
    return inv[rid]


def _instrumentation_v2_enabled() -> bool:
    """Direct instrumentation V2 (command60/61); SIGCOMM_INSTRUMENTATION_V2 default ON."""
    return InstrumentationV2.enabled()


def _initial_probe_duration_s() -> float:
    return float(os.environ.get("SIGCOMM_INITIAL_PROBE_S", "20"))


def _buffer_protection_threshold_s() -> float:
    env_val = os.environ.get("SIGCOMM_BUFFER_PROTECTION_S")
    if env_val is not None and str(env_val).strip() != "":
        return float(env_val)
    if _metric_v4_timeline_enabled():
        return 0.25
    return 2.0


def _buffer_protection_blocks_enhanced(
    current_buffer: float,
    *,
    payload_ttfb_ms,
    media_covered_sec: float,
) -> tuple[bool, float]:
    """Return (should_block, threshold). Metric V4 skips until first media object."""
    threshold = _buffer_protection_threshold_s()
    if _metric_v4_timeline_enabled():
        if payload_ttfb_ms is None or float(media_covered_sec) < 1.0:
            return False, threshold
    return current_buffer < threshold, threshold


def _scientific_bitrate_fail_closed() -> bool:
    """command110: scientific / ToN DEV must not silently use RB hardcoded rates."""
    for key in ("TON_BITRATE_FAIL_CLOSED", "TON_COMMAND108_DEV", "TON_SCIENTIFIC_MODE"):
        if os.environ.get(key, "").strip().lower() in ("1", "true", "yes", "on"):
            return True
    return False


def _load_content_rep_bitrate_map() -> dict:
    """Optional per-content map: TON_CONTENT_REP_BITRATES_JSON + TON_CONTENT_ID."""
    path = os.environ.get("TON_CONTENT_REP_BITRATES_JSON", "").strip()
    content = os.environ.get("TON_CONTENT_ID", "").strip()
    if not path or not content or not os.path.isfile(path):
        return {}
    try:
        blob = json.load(open(path, "r"))
        raw = blob.get(content) or {}
        return {int(k): float(v) for k, v in raw.items()}
    except Exception:
        return {}


def resolve_rep_bitrate_mbps(rep_id: int) -> float:
    """Resolve measured Rep bitrate. Scientific mode fails closed if map/env missing."""
    rid = int(rep_id)
    env_v = os.environ.get(f"REP{rid}_BITRATE_MBPS")
    if env_v not in (None, ""):
        return float(env_v)
    cmap = _load_content_rep_bitrate_map()
    if rid in cmap:
        return float(cmap[rid])
    if _scientific_bitrate_fail_closed():
        content = os.environ.get("TON_CONTENT_ID", "")
        raise RuntimeError(
            f"BITRATE_FAIL_CLOSED: missing REP{rid}_BITRATE_MBPS and content-map entry "
            f"(content={content!r}). Refusing hardcoded Red-and-Black fallback."
        )
    # Legacy non-scientific fallback only (command109 WARN / pre-command110).
    legacy = {
        1: 3.07, 2: 1.79, 3: 0.87, 4: 4.54, 5: 6.42, 6: 2.80,
        7: 3.91, 8: 1.43, 9: 1.97, 10: 1.43, 11: 1.97, 12: 1.97,
    }
    return float(legacy.get(rid, 0.87))


def _layered_manifest_tracks() -> dict:
    path = os.environ.get("COMMAND135_PATHS", "").strip()
    content = (
        os.environ.get("TON_CONTENT_ID", "").strip()
        or os.environ.get("MM26_CONTENT_ID", "").strip()
        or "redandblack"
    )
    roots = []
    if path and os.path.isfile(path):
        try:
            blob = json.load(open(path, "r"))
            for key in ("layered_media_root", "transport_layered_media_root", "scientific_media_root"):
                if blob.get(key):
                    roots.append(blob[key])
        except Exception:
            pass
    repo = os.path.dirname(os.path.abspath(__file__))
    default_paths = os.path.join(repo, "state", "COMMAND135_PATHS.json")
    if os.path.isfile(default_paths):
        try:
            blob = json.load(open(default_paths, "r"))
            for key in ("transport_layered_media_root", "layered_media_root"):
                if blob.get(key):
                    roots.append(blob[key])
        except Exception:
            pass
    for root in roots:
        man = os.path.join(str(root), content, "media_manifest.json")
        if os.path.isfile(man):
            return json.load(open(man, "r")).get("tracks") or {}
    return {}


def resolve_playable_media_bitrate_mbps(base_version: int, enh_depth: int, rep_id: int) -> float:
    """Bytes→media-seconds denominator. Layered B3-only must use S3/B3, never S9/native9."""
    if _true_content_layering():
        tracks = _layered_manifest_tracks()
        bps = layered_playable_bitrate_bps(tracks, int(base_version), int(enh_depth))
        return float(bps) / 1e6
    return float(resolve_rep_bitrate_mbps(int(rep_id)))


# === MD2G-PLUS TUNING ===
MD2G_TREND_WIN = 5
MD2G_ENABLE_GOOD_CNT = 1
MD2G_DISABLE_BAD_CNT = 2

MD2G_ON_BASE_THRESHOLD = 1.02
MD2G_OFF_BASE_THRESHOLD = 1.05
MD2G_TREND_UP_ADJ = 0.90
MD2G_TREND_DOWN_ADJ = 1.01

MD2G_STAB_BONUS_MAX = 0.15
MD2G_STAB_STD_CAP  = 0.10

# DecisionQuality
MD2G_DQ_W_BW = 0.80
MD2G_DQ_W_DLY = 0.20


def _parse_qoe_weights_from_env():
    """ MM26/dispatch_strategy_enhanced_unified_NOSSDAV.py::_parse_qoe_weights_from_env """
    defaults = {
        "delay": 0.28,
        "stall": 0.30,
        "stability": 0.18,
        "quality": 0.14,
        "system": 0.10,
    }
    vals = {}
    for k, v in defaults.items():
        env_key = f"MM26_QOE_W_{k.upper()}"
        try:
            vals[k] = max(0.0, float(os.environ.get(env_key, str(v))))
        except Exception:
            vals[k] = v
    s = sum(vals.values())
    if s <= 1e-9:
        return defaults
    return {k: vals[k] / s for k in vals}


def _parse_reward_lambdas_from_env():
    """ MM26 λ MM26_REWARD_LAMBDA_* """
    try:
        o = float(os.environ.get("MM26_REWARD_LAMBDA_O", "0.25"))
        qv = float(os.environ.get("MM26_REWARD_LAMBDA_Q", "0.625"))
        b = float(os.environ.get("MM26_REWARD_LAMBDA_B", "0.125"))
    except ValueError:
        o, qv, b = 0.25, 0.625, 0.125
    s = o + qv + b
    if s <= 1e-9:
        return 0.25, 0.625, 0.125
    return o / s, qv / s, b / s


def _sigcomm_cell_state_dir():
    """Cell-scoped client state root (command60/61)."""
    explicit = (os.environ.get("SIGCOMM_CELL_STATE_DIR") or "").strip()
    if explicit:
        return explicit
    cell_tmp = (os.environ.get("SIGCOMM_CELL_TMP") or "").strip()
    if cell_tmp:
        return f"/tmp/{cell_tmp}client_state"
    return "/tmp/mininet_shared"


def _client_state_file(host_id):
    return os.path.join(_sigcomm_cell_state_dir(), f"client_h{host_id}_state.json")


def _ensure_client_state_dir():
    state_dir = _sigcomm_cell_state_dir()
    os.makedirs(state_dir, exist_ok=True)
    try:
        os.chmod(state_dir, 0o777)
    except (OSError, PermissionError):
        pass
    return state_dir


QOE_WEIGHTS = _parse_qoe_weights_from_env()
QOE_STABILITY_STD_CAP = 0.08
_SIGCOMM_QOE_EQ9_ACTIVE = os.environ.get("SIGCOMM_QOE_EQ9", "").strip().lower() in ("1", "true", "yes", "on")
if _SIGCOMM_QOE_EQ9_ACTIVE:
    print(
        "[QOE_CONTRACT] SIGCOMM_QOE_EQ9=1 active: paper Eq.9 "
        "R_q=Q_s-0.5*D_n-0.5*S_n with Q_s from final Rep ID (Table 1). "
        "MM26 five-part weights below are INACTIVE legacy (not used for R_q).",
        file=sys.stderr,
        flush=True,
    )
    print(f"[DEBUG] (inactive legacy) MM26 five-part weight table: {QOE_WEIGHTS}", file=sys.stderr, flush=True)
else:
    print(f"[DEBUG] MM26-aligned QoE 5-part weights: {QOE_WEIGHTS}", file=sys.stderr, flush=True)
    print(
        "[QOE_CONTRACT] SIGCOMM_QOE_EQ9 unset/0: using MM26 five-part R_q "
        "(not paper Eq.9). Set SIGCOMM_QOE_EQ9=1 for SIGCOMM campaign.",
        file=sys.stderr,
        flush=True,
    )

# ==============================================================================
# ==============================================================================
# ==============================================================================
# MD2G_W_ON = dict(w_r=0.40, w_b=0.30, w_ln=0.20, w_d=0.07, w_f=0.03) #
# MD2G_W_OFF = dict(w_r=0.40, w_b=0.38, w_ln=0.14, w_d=0.06, w_f=0.02) #

# Fail-closed: SIGCOMM_DATASET_DIR or <repo>/datasets (no legacy home-directory fallback).
_REPO_ROOT_DS = os.path.dirname(os.path.abspath(__file__))
_ds_env = (os.environ.get("SIGCOMM_DATASET_DIR") or "").strip()
DATASET_DIR = _ds_env if _ds_env else os.path.join(_REPO_ROOT_DS, "datasets")
if not os.path.isdir(DATASET_DIR):
    raise FileNotFoundError(
        f"SIGCOMM dataset dir missing: {DATASET_DIR} "
        "(set SIGCOMM_DATASET_DIR; legacy home-directory fallbacks disabled)"
    )
print("[DEBUG] dispatch_strategy.py :", DATASET_DIR, file=sys.stderr)
df_wifi = pd.read_csv(os.path.join(DATASET_DIR, "wifi_clean.csv"))
df_4g   = pd.read_csv(os.path.join(DATASET_DIR, "4G-network-data_clean.csv"))
# ✅ 5G 5g_final_trace.csv 5g_network_data_clean.csv
df_5g   = pd.read_csv(os.path.join(DATASET_DIR, "5g_final_trace.csv"))
df_opt  = pd.read_csv(os.path.join(DATASET_DIR, "Optic_Bandwidth_clean_2.csv"))
df_dev  = pd.read_csv(os.path.join(DATASET_DIR, "Headset device performance.csv"))

print(f"[DEBUG] Using datasets from: {DATASET_DIR}", file=sys.stderr)

# ✅ 4G "DL_bitrate_Mbps" "bytes_sec (Mbps)"
def get_bandwidth_column(df, default_col="bytes_sec (Mbps)"):
    if default_col in df.columns:
        return default_col
    elif "DL_bitrate_Mbps" in df.columns:
        return "DL_bitrate_Mbps"
    elif "bitrate" in df.columns.str.lower().values:
        bitrate_cols = [c for c in df.columns if "bitrate" in c.lower()]
        return bitrate_cols[0] if bitrate_cols else None
    else:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        return numeric_cols[0] if len(numeric_cols) > 0 else None

bw_col_wifi = get_bandwidth_column(df_wifi)
bw_col_4g = get_bandwidth_column(df_4g, "DL_bitrate_Mbps")
bw_col_5g = get_bandwidth_column(df_5g)
bw_col_opt = get_bandwidth_column(df_opt)

print(f"[DEBUG] Bandwidth columns: wifi={bw_col_wifi}, 4g={bw_col_4g}, 5g={bw_col_5g}, opt={bw_col_opt}", file=sys.stderr)

B_MAX_BY_NETWORK = {
    "wifi": np.percentile(df_wifi[bw_col_wifi], 95) if bw_col_wifi else 100.0,
    "4g": np.percentile(df_4g[bw_col_4g], 95) if bw_col_4g else 50.0,
    "5g": np.percentile(df_5g[bw_col_5g], 95) if bw_col_5g else 200.0,
    "fiber_optic": np.percentile(df_opt[bw_col_opt], 95) if bw_col_opt else 1000.0
}

all_bw = pd.concat([
    df_wifi[bw_col_wifi] if bw_col_wifi else pd.Series([100.0]),
    df_4g[bw_col_4g] if bw_col_4g else pd.Series([50.0]),
    df_5g[bw_col_5g] if bw_col_5g else pd.Series([200.0]),
    df_opt[bw_col_opt] if bw_col_opt else pd.Series([1000.0])
])
B_MAX = np.percentile(all_bw, 95)
EPS = 1e-6

print(f"[DEBUG] B_MAX: {B_MAX_BY_NETWORK}", file=sys.stderr)
print(f"[DEBUG] B_MAX: {B_MAX:.2f} Mbps", file=sys.stderr)

# ---------- Rolling-DRL ----------
try:
    from strategies.rolling_drl_strategy_v2_refined import RollingDRLStrategy
except ImportError:
    RollingDRLStrategy = None

class SmartEnhancementState:
    def __init__(self):
        self.enh_enabled = False
        self.good_cnt = 0
        self.bad_cnt = 0
        self.bw_ema = 0.0
        self.bw_window = deque(maxlen=MD2G_TREND_WIN)
        self.alpha = 0.6
        self.qoe_window = deque(maxlen=MD2G_TREND_WIN)
        self.bandwidth_trend = 0  # -1/0/+1
        self.qoe_trend = 0        # -1/0/+1
        self.dynamic_threshold_multiplier = 1.0
        
        # - ✅ WiFi WiFi 20-30%
        self.thresholds = {
            # ✅ WiFi
            # "on": 1.25 -> 25% Enhanced
            # "off": 1.10 -> 10% Base
            # "load_max": 0.70 -> Relay 70% WiFi
            "wifi": {
                "on": 1.25,
                "off": 1.10,
                "jfi_min": 0.85, 
                "load_max": 0.70,
                "load_off": 0.85
            },
            "4g": {"on": 0.98, "off": 0.95, "jfi_min": 0.88, "load_max": 0.90, "load_off": 0.95},
            "5g": {"on": 1.00, "off": 0.98, "jfi_min": 0.90, "load_max": 0.85, "load_off": 0.93},
            "fiber_optic": {"on": 1.02, "off": 1.00, "jfi_min": 0.92, "load_max": 0.75, "load_off": 0.88},
            "mixed_4g_heavy": {"on": 1.00, "off": 0.98, "jfi_min": 0.88, "load_max": 0.90, "load_off": 0.95},
            "mixed_balanced": {"on": 1.00, "off": 0.98, "jfi_min": 0.90, "load_max": 0.85, "load_off": 0.93},
            "mixed_wifi_heavy": {"on": 1.00, "off": 0.98, "jfi_min": 0.90, "load_max": 0.80, "load_off": 0.90}
        }
        
        self.user_groups = {
            "high_performance": [],
            "medium_performance": [],
            "low_performance": []
        }
        
        self.network_adaptation = {
            "bandwidth_trend": 0,
            "stability_score": 1.0,
            "adaptation_factor": 1.0
        }
    
    def _trend_from_window(self, seq, pos=0.05, neg=-0.05):
        if len(seq) < 3:
            return 0
        diffs = np.diff(np.array(seq, dtype=float))
        avg = np.mean(diffs)
        if avg > pos:  return 1
        if avg < neg:  return -1
        return 0

    def update_windows(self, bandwidth_mbps, qoe_smooth):
        self.bw_window.append(float(bandwidth_mbps))
        self.qoe_window.append(float(qoe_smooth))
        self.bandwidth_trend = self._trend_from_window(self.bw_window)
        self.qoe_trend = self._trend_from_window(self.qoe_window, pos=0.01, neg=-0.01)

    def update_bandwidth(self, inst_bw: float):
        if self.bw_ema == 0:
            self.bw_ema = inst_bw
        else:
            self.bw_ema = self.alpha * self.bw_ema + (1 - self.alpha) * inst_bw
        
        self.bw_window.append(inst_bw)
    
    def get_pessimistic_bandwidth(self) -> float:
        if len(self.bw_window) < 3:
            return self.bw_ema
        return min(self.bw_ema, np.percentile(list(self.bw_window), 10))
    
    def update_qoe_and_adjust_threshold(self, qoe_value: float):
        self.qoe_window.append(qoe_value)
        
        if len(self.qoe_window) >= 10:
            qoe_std = np.std(list(self.qoe_window))
            
            if qoe_std < 0.02:
                self.dynamic_threshold_multiplier = 0.95
            elif qoe_std > 0.05:
                self.dynamic_threshold_multiplier = 1.05
            else:
                self.dynamic_threshold_multiplier = 1.0
    
    def should_enable_enhancement(self, network_type: str, base_rate: float, 
                                 relay_jfi: float, relay_load: float, federation_on: bool = False) -> tuple:
        if network_type not in self.thresholds:
            network_type = "wifi"
        
        specific_th = self.thresholds[network_type]
        
        threshold_val = specific_th["on"] if not self.enh_enabled else specific_th["off"]
        
        if self.bandwidth_trend > 0:
            threshold_val *= MD2G_TREND_UP_ADJ
        elif self.bandwidth_trend < 0:
            threshold_val *= MD2G_TREND_DOWN_ADJ
        
        # ✅ WiFi
        estimated_bw = self.get_pessimistic_bandwidth()
        
        # ✅ WiFi " "
        # WiFi 15%
        if network_type == "wifi":
            estimated_bw *= 0.85
            # ( * 0.85) >= (base_rate * 1.25)
            # base_rate 1.47 (1.25 / 0.85) Enhanced

        ok_bw   = (estimated_bw >= base_rate * threshold_val)
        ok_jfi  = (relay_jfi >= specific_th["jfi_min"])
        ok_load = (relay_load <= (specific_th["load_max"] if not self.enh_enabled else specific_th["load_off"]))
        ok = ok_bw and ok_jfi and ok_load

        if ok:
            self.good_cnt += 1
            self.bad_cnt = 0
        else:
            self.bad_cnt += 1
            self.good_cnt = 0

        if not self.enh_enabled and self.good_cnt >= MD2G_ENABLE_GOOD_CNT:
            self.enh_enabled = True
            print(f"[SmartEnhancement-Plus] : network={network_type}, bw_pess={estimated_bw:.2f}, jfi={relay_jfi:.3f}, load={relay_load:.3f}, threshold={threshold_val:.3f}")
            return True, threshold_val
        if self.enh_enabled and self.bad_cnt >= MD2G_DISABLE_BAD_CNT:
            self.enh_enabled = False
            print(f"[SmartEnhancement-Plus] : network={network_type}, bw_pess={estimated_bw:.2f}, jfi={relay_jfi:.3f}, load={relay_load:.3f}, threshold={threshold_val:.3f}")
            return False, threshold_val
        return self.enh_enabled, threshold_val

smart_enhancement = SmartEnhancementState()

def decision_quality_v2(Bu, base_rate, delay_penalty, network_type=None):
    if network_type and network_type in ['mixed_4g_heavy', 'mixed_balanced', 'mixed_wifi_heavy']:
        w_bw = 0.80
        w_dly = 0.20
    else:
        w_bw = MD2G_DQ_W_BW
        w_dly = MD2G_DQ_W_DLY
    
    util = min(1.0, float(Bu) / max(1e-6, base_rate * 1.2))
    resp = 1.0 / (1.0 + max(0.0, float(delay_penalty)))
    return min(1.0, w_bw * util + w_dly * resp)

def stability_bonus(qoe_window):
    if not qoe_window:
        return 0.0
    std = float(np.std(list(qoe_window)))
    factor = max(0.0, 1.0 - min(std, MD2G_STAB_STD_CAP) / MD2G_STAB_STD_CAP)
    return MD2G_STAB_BONUS_MAX * factor

def sample_bandwidth(net_type: str) -> float:
    def _slice(df, key):
        a = os.environ.get(f"TON_GEN3_ROW_{key}_START")
        b = os.environ.get(f"TON_GEN3_ROW_{key}_END")
        if not a or not b:
            return df
        sub = df.iloc[int(a):int(b)]
        return sub if len(sub) else df
    if net_type == "wifi":
        col = bw_col_wifi or "bytes_sec (Mbps)"
        return float(_slice(df_wifi, "WIFI").sample(1)[col].iloc[0])
    elif net_type == "4g":
        col = bw_col_4g or "DL_bitrate_Mbps"
        return float(_slice(df_4g, "4G").sample(1)[col].iloc[0])
    elif net_type == "5g":
        col = bw_col_5g or "bytes_sec (Mbps)"
        return float(_slice(df_5g, "5G").sample(1)[col].iloc[0])
    elif net_type == "fiber_optic":
        col = bw_col_opt or "bytes_sec (Mbps)"
        return float(_slice(df_opt, "FIBER_OPTIC").sample(1)[col].iloc[0])
    else:
        return random.uniform(1, 10)

def gpu_boost(device_score: float) -> float:
    gpu_vals = df_dev["GPU Clock (MHz)"]
    min_gpu, max_gpu = gpu_vals.min(), gpu_vals.max()
    scale = 0.8 + 0.4 * (device_score - min_gpu) / (max_gpu - min_gpu + 1e-6)
    return max(0.8, min(scale, 1.2))

def nic_name(host_id, retries=5):
    """ h{host_id}-eth0"""
    # h{host_id}-eth0
    primary_iface = f"h{host_id}-eth0"
    if os.path.exists(f"/sys/class/net/{primary_iface}"):
        return primary_iface
    
    for _ in range(retries):
        ifaces = glob.glob(f"/sys/class/net/h{host_id}-eth*")
        if ifaces:
            return os.path.basename(ifaces[0])
        time.sleep(1)
    
    print(f"[WARN] h{host_id}: h{host_id}-eth0", file=sys.stderr, flush=True)
    return primary_iface

def measure_bandwidth(server_ip, duration=10, parallel=5):
    """
     iperf3 client server 
    
    Args:
        server_ip: IP relay 
        duration: 
        parallel: 
    
    Returns:
         Mbps None
    """
    cmd = f"iperf3 -c {server_ip} -t {duration} -P {parallel} -J"
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=duration+5)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            bits_per_second = data.get('end', {}).get('sum_received', {}).get('bits_per_second', 0)
            if bits_per_second > 0:
                return bits_per_second / 1e6
    except Exception as e:
        pass
    return None


def ping_rtt(host, iface=None):
    """
     ping RTT 
    
    Args:
        host: IP
        iface: 
    
    Returns:
         -1
    """
    try:
        cmd = ["ping", "-c", "1", "-W", "1", host]
        if iface:
            cmd += ["-I", iface]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True, timeout=3)
        match = re.search(r'time=(\d+\.\d+)', output)
        if match:
            return float(match.group(1))
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # ping -1
        return -1
    except Exception:
        return -1
    return -1

def get_real_trace_delay(network_type):
    """ trace """
    try:
        import pickle
        with open('real_trace_delays.pkl', 'rb') as f:
            delay_distributions = pickle.load(f)
        
        if network_type in delay_distributions:
            delays = delay_distributions[network_type]
            return random.choice(delays)
        else:
            return random.uniform(20, 120)
    except:
        return random.uniform(20, 120)

def kill(p: subprocess.Popen | None):
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=1)
        except subprocess.TimeoutExpired:
            p.kill()

# ==============================================================================
# ✅ DataDrainer
# ==============================================================================
# "Download & Discard"
# read(4096) Pipe
# Base Enhanced Enhanced decision /
# ==============================================================================
class DataDrainer(threading.Thread):
    """
     
    
     
    1. stdout/stderr 
    2. read(4096) 
    3. 
    4. 
    
     
    - readline() 
    - read(4096) 
    - 
    - Pipe 64KB 
    """
    def __init__(self, process, name, log_file_path=None, start_time_epoch=None):
        super().__init__()
        self.process = process
        self.name = name
        self.log_file_path = log_file_path
        self.start_time_epoch = start_time_epoch if start_time_epoch is not None else time.time()
        self.running = True
        self.daemon = True
        self._latest_line = ""
        self.bytes_read = 0
        self.last_activity_time = time.time()
        
        # ✅ TTFB/TTLB
        self.ttfb_ms = None
        self.ttlb_ms = None
        self.total_bytes = 0
        
        self.last_data_ts = None
        self.last_read_dt_ms = None
        
    def run(self):
        """ TTFB TTLB"""
        print(f"[DataDrainer] {self.name}: Pipe ", file=sys.stderr, flush=True)
        
        log_file = None
        if self.log_file_path:
            try:
                log_file = open(self.log_file_path, 'ab')
            except Exception as e:
                print(f"[DataDrainer] {self.name}: {self.log_file_path}: {e}", file=sys.stderr, flush=True)
        
        # ✅ TTFB/TTLB
        has_received_first_byte = False
        last_arrival_time = None
        
        try:
            while self.running:
                try:
                    data = self.process.stdout.read(4096)
                except Exception as e:
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.01)
                    continue
                
                if not data:
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.01)
                    continue
                
                current_time = time.time()
                self.bytes_read += len(data)
                self.total_bytes += len(data)
                self.last_activity_time = current_time
                last_arrival_time = current_time
                
                if self.last_data_ts is not None:
                    # read
                    dt_ms = (current_time - self.last_data_ts) * 1000.0
                    # EWMA
                    if self.last_read_dt_ms is None:
                        self.last_read_dt_ms = dt_ms
                    else:
                        self.last_read_dt_ms = 0.8 * self.last_read_dt_ms + 0.2 * dt_ms
                self.last_data_ts = current_time
                
                # ✅ TTFB
                if not has_received_first_byte:
                    self.ttfb_ms = (current_time - self.start_time_epoch) * 1000.0
                    print(f"⏱️ [{self.name}] TTFB ( ): {self.ttfb_ms:.2f} ms", file=sys.stderr, flush=True)
                    has_received_first_byte = True
                
                if log_file:
                    try:
                        log_file.write(data)
                        log_file.flush()
                    except Exception as e:
                        if self.bytes_read % (4096 * 100) == 0:
                            print(f"[DataDrainer] {self.name}: : {e}", file=sys.stderr, flush=True)
                
                try:
                    text_chunk = data.decode('utf-8', errors='ignore')
                    if len(text_chunk.strip()) > 0:
                        lines = text_chunk.split('\n')
                        if lines:
                            self._latest_line = lines[-1]
                except:
                    pass
                
                # " " Pipe " "
                
        except Exception as e:
            print(f"[DataDrainer] {self.name} : {e}", file=sys.stderr, flush=True)
        finally:
            # ✅ TTLB
            if last_arrival_time:
                self.ttlb_ms = (last_arrival_time - self.start_time_epoch) * 1000.0
                
                # (Throughput)
                duration_sec = self.ttlb_ms / 1000.0
                avg_speed_mbps = (self.total_bytes * 8 / 1000000) / duration_sec if duration_sec > 0 else 0
                
                print(f"🏁 [{self.name}] ! TTLB ( ): {self.ttlb_ms:.2f} ms | "
                      f" : {self.total_bytes/1024/1024:.2f} MB | "
                      f" : {avg_speed_mbps:.2f} Mbps", file=sys.stderr, flush=True)
            else:
                print(f"⚠️ [{self.name}] (TTLB )", file=sys.stderr, flush=True)
            
            if log_file:
                try:
                    log_file.close()
                except:
                    pass
        
        print(f"[DataDrainer] {self.name}: {self.bytes_read} ", file=sys.stderr, flush=True)
    
    @property
    def latest_data(self):
        return self._latest_line
    
    @property
    def lines_read(self):
        return self.bytes_read // 1024
    
    def stop(self):
        self.running = False

def assign_relay_ip(host_id: int, num_clients: int = 10) -> str:
    """
    ✅ host_id r1 r2
    
     
    - h1-h5 r1
    - h6-h10 r2
    
    Relay IP 
    - r1-eth0: 10.0.2.2 ( r0 )
    - r2-eth0: 10.0.3.2 ( r0 )
    """
    r1_sub_count = num_clients // 2
    if host_id <= r1_sub_count:
        return "10.0.2.2"
    else:
        return "10.0.3.2"

def parse_rebuffer_from_debug(log_path, last_size=[0]):
    """ GST_DEBUG rebuffer """
    import os, re, time
    try:
        if not os.path.exists(log_path):
            return 0.0, 0
        
        cur = os.path.getsize(log_path)
        start = last_size[0]
        last_size[0] = cur
        if cur <= start:
            return 0.0, 0
        
        with open(log_path, "r", errors="ignore") as fp:
            fp.seek(start)
            chunk = fp.read()

        # buffering
        stall_time = 0.0
        stall_cnt = 0
        
        # buffering
        buffering_patterns = [
            r'buffering.*?(\d+)%',  # buffering 0% -> 100%
            r'buffering done',
            r'underflow',
            r'stall'
        ]
        
        # "buffering done" "underflow"
        stall_cnt = len(re.findall(r'buffering done|underflow|stall', chunk, re.IGNORECASE))
        
        return stall_time, stall_cnt
    except Exception as e:
        print(f"[WARN] rebuffer : {e}", file=sys.stderr, flush=True)
        return 0.0, 0

def calculate_jain_fairness_index(load_rates):
    """ Jain's Fairness Index (JFI)"""
    if not load_rates or len(load_rates) == 0:
        return 1.0
    
    # (1 - load_rate)
    available_margins = [1.0 - rate for rate in load_rates]
    
    if sum(available_margins) == 0:
        return 0.0
    
    # JFI = (sum(x))^2 / (n * sum(x^2))
    n = len(available_margins)
    sum_x = sum(available_margins)
    sum_x_squared = sum(x * x for x in available_margins)
    
    if sum_x_squared == 0:
        return 1.0
    
    jfi = (sum_x * sum_x) / (n * sum_x_squared)
    return max(0.0, min(1.0, jfi))

def measure_cpu_usage():
    """
     CPU 
    
    Returns:
        dict: {
            'cpu_bottleneck_node_percent': float,
            'cpu_relay_process_percent': float,
            'cpu_controller_process_percent': float,
            'cpu_dash_server_process_percent': float,
            'cpu_system_percent': float
        }
    """
    cpu_data = {
        'cpu_bottleneck_node_percent': 0.0,
        'cpu_relay_process_percent': 0.0,
        'cpu_controller_process_percent': 0.0,
        'cpu_dash_server_process_percent': 0.0,
        'cpu_system_percent': 0.0
    }
    
    if not PSUTIL_AVAILABLE:
        return cpu_data
    
    try:
        # interval=None CPU
        # interval>0 interval=None
        if not hasattr(measure_cpu_usage, 'initialized'):
            cpu_system = psutil.cpu_percent(interval=0.1)
            measure_cpu_usage.initialized = True
        else:
            # interval=None
            cpu_system = psutil.cpu_percent(interval=None)
        
        cpu_data['cpu_system_percent'] = cpu_system
        
        # Mininet host namespace CPU
        # CPU Mininet host CPU CPU
        # CPU psutil per-cpu
        cpu_data['cpu_bottleneck_node_percent'] = cpu_system
        
        # ✅ CPU Controller
        # ✅ cpu_stats_r0.json, cpu_stats_r1.json, cpu_stats_r2.json
        SHARED_CPU_DIR = "/tmp/mininet_shared"
        cpu_stats_files = [
            f"{SHARED_CPU_DIR}/cpu_stats_r0.json",  # r0: moq-relay-ietf
            f"{SHARED_CPU_DIR}/cpu_stats_r1.json",  # r1: controller
            f"{SHARED_CPU_DIR}/cpu_stats_r2.json",  # r2: controller
        ]
        
        for cpu_stats_file in cpu_stats_files:
            if os.path.exists(cpu_stats_file):
                try:
                    with open(cpu_stats_file, 'r') as f:
                        cpu_stats = json.load(f)
                        cpu_data['cpu_relay_process_percent'] += cpu_stats.get('moq_relay_ietf_cpu', 0.0)
                        cpu_data['cpu_controller_process_percent'] += cpu_stats.get('controller_cpu', 0.0)
                        cpu_data['cpu_dash_server_process_percent'] += cpu_stats.get('dash_server_cpu', 0.0)
                except Exception as e:
                    if not hasattr(measure_cpu_usage, 'warn_count'):
                        measure_cpu_usage.warn_count = 0
                    if measure_cpu_usage.warn_count < 3:
                        print(f"[WARN] CPU {cpu_stats_file} : {e}", file=sys.stderr, flush=True)
                        measure_cpu_usage.warn_count += 1
    except Exception as e:
        if not hasattr(measure_cpu_usage, 'error_count'):
            measure_cpu_usage.error_count = 0
        if measure_cpu_usage.error_count < 3:
            print(f"[WARN] CPU : {e}", file=sys.stderr, flush=True)
            measure_cpu_usage.error_count += 1
    
    return cpu_data

def calculate_system_load_balance(relay_loads):
    if not relay_loads:
        return 1.0
    
    # Jain's Fairness Index
    return calculate_jain_fairness_index(relay_loads)

# ---------- base ----------
# map_to_rep_id imported from strategies.rep_lifecycle_v2 (FULL_INDEPENDENT_REPS ladder)

def select_base_version_by_group_minimum(host_id, group_id, total_clients, decision_data=None):
    """
     base 
    
    Args:
        host_id: ID 
        group_id: ID (1, 2, 3) - 1-based ID
        total_clients: 
        decision_data: group_members None 
    
    Returns:
        base_version: 1, 2, 3 ( base1, base2, base3)
    """
    # command124: resolve via content/env map (fail-closed under scientific mode).
    # Hardcoded RB tables live only inside resolve_rep_bitrate_mbps fail-open.
    base_bitrates = {
        1: float(resolve_rep_bitrate_mbps(1)),
        2: float(resolve_rep_bitrate_mbps(2)),
        3: float(resolve_rep_bitrate_mbps(3)),
    }
    
    # ✅ Controller
    group_member_ids = []
    
    # decision_data
    if decision_data is None:
        try:
            decision_file = os.environ.get('DECISION_FILE', '/tmp/r1_decisions.json')
            if os.path.exists(decision_file):
                with open(decision_file, 'r') as f:
                    decision_data = json.load(f)
        except Exception as e:
            print(f"[WARN] h{host_id}: : {e} fallback ", file=sys.stderr, flush=True)
            decision_data = None
    
    # ✅ group_members
    if decision_data and "group_members" in decision_data:
        # group_id 1-based key
        group_id_str = str(group_id - 1)
        if group_id_str in decision_data["group_members"]:
            group_member_ids = decision_data["group_members"][group_id_str]
            print(f"[DEBUG] h{host_id}: Group {group_id} : {group_member_ids}", file=sys.stderr, flush=True)
        else:
            for user_id_str, user_decision in decision_data.get("decisions", {}).items():
                if user_decision.get("md2g_group_id") == (group_id - 1):
                    if "md2g_group_members" in user_decision:
                        group_member_ids = user_decision["md2g_group_members"]
                        print(f"[DEBUG] h{host_id}: Group {group_id} : {group_member_ids}", file=sys.stderr, flush=True)
                        break
    
    # ✅ Fallback
    if not group_member_ids:
        print(f"[WARN] h{host_id}: Group {group_id} fallback ", file=sys.stderr, flush=True)
        for member_id in range(1, total_clients + 1):
            if (member_id - 1) % 3 + 1 == group_id:
                group_member_ids.append(member_id)

    # Fail-closed: ignore phantom members outside this cell's launched hosts.
    group_member_ids = [
        int(m) for m in group_member_ids
        if 1 <= int(m) <= int(total_clients)
    ]
    
    if not group_member_ids:
        # base3
        print(f"[WARN] h{host_id}: Group {group_id} base3", file=sys.stderr, flush=True)
        return 3
    
    min_throughput = float('inf')
    min_device_score = float('inf')
    
    # ✅ throughput < 2 Mbps
    MIN_VALID_THROUGHPUT = 2.0
    
    for member_id in group_member_ids:
        client_state_file = _client_state_file(member_id)
        try:
            if os.path.exists(client_state_file):
                with open(client_state_file, 'r') as f:
                    state = json.load(f)
                    throughput = state.get('throughput_mbps', 0.0)
                    device_score = state.get('device_score', 1.0)
                    
                    # ✅ throughput
                    # B_MAX_BY_NETWORK 30% fallback
                    if throughput < MIN_VALID_THROUGHPUT:
                        network_type = state.get('network_type', 'wifi')
                        if network_type in B_MAX_BY_NETWORK:
                            throughput = max(B_MAX_BY_NETWORK[network_type] * 0.3, MIN_VALID_THROUGHPUT)
                        else:
                            throughput = max(10.0, MIN_VALID_THROUGHPUT)
                        print(f"[DEBUG] h{host_id}: Group {group_id} h{member_id} throughput {state.get('throughput_mbps', 0.0):.2f} Mbps {throughput:.2f} Mbps", file=sys.stderr, flush=True)
                    
                    min_throughput = min(min_throughput, throughput)
                    min_device_score = min(min_device_score, device_score)
        except Exception as e:
            if member_id == host_id:
                print(f"[WARN] h{host_id}: : {e}", file=sys.stderr, flush=True)
            continue
    
    # base3
    if min_throughput == float('inf'):
        print(f"[DEBUG] h{host_id}: Group {group_id} base3", file=sys.stderr, flush=True)
        return 3
    
    # ✅ base
    # base
    # Bitrate floors come from resolve_rep_bitrate_mbps (content/env), not RB literals.
    
    # ✅ base
    base_device_requirements = {1: 0.7, 2: 0.5, 3: 0.3}
    
    available_bw = min_throughput * 0.8
    
    # base
    for base_ver in [1, 2, 3]:
        required_bw = base_bitrates[base_ver]
        required_device_score = base_device_requirements[base_ver]
        
        bw_sufficient = available_bw >= required_bw
        device_sufficient = min_device_score >= required_device_score
        
        if bw_sufficient and device_sufficient:
            print(f"[DEBUG] h{host_id}: Group {group_id} - throughput={min_throughput:.2f}Mbps, device_score={min_device_score:.3f}, base{base_ver} ( {required_bw:.2f}Mbps, {required_device_score:.2f})", file=sys.stderr, flush=True)
            return base_ver
        elif not bw_sufficient and not device_sufficient:
            if base_ver == 3:
                print(f"[WARN] h{host_id}: Group {group_id} {min_throughput:.2f}Mbps {min_device_score:.3f} base3 base3", file=sys.stderr, flush=True)
        elif not bw_sufficient:
            if base_ver == 3:
                print(f"[WARN] h{host_id}: Group {group_id} {min_throughput:.2f}Mbps base3 {required_bw:.2f}Mbps base3", file=sys.stderr, flush=True)
        elif not device_sufficient:
            if base_ver == 3:
                print(f"[WARN] h{host_id}: Group {group_id} {min_device_score:.3f} base3 {required_device_score:.2f} base3", file=sys.stderr, flush=True)
    
    # base3 base3
    print(f"[WARN] h{host_id}: Group {group_id} {min_throughput:.2f}Mbps, {min_device_score:.3f} base3 base3", file=sys.stderr, flush=True)
    return 3

def calculate_multicast_saving(group_assignments, enh_levels, num_users, num_groups=3):
    """
     

    LEGACY / non-scientific two-track Ro (base + enhanced deltas).
    Scientific native-9 cells must use calculate_native9_multicast_saving via
    TON_NATIVE9REP_RO + _sigcomm_native9rep_decision_enabled(). RB hardcodes below
    are intentionally retained only for this legacy path.
    
    Args:
        group_assignments: [num_users] - ID 0..K-1 
        enh_levels: [num_users] - enh_level 0/1/2 ** pull_enhanced 0/1 **
        num_users: 
        num_groups: K
    
    Returns:
        R_o: [0, 1]
    
     
        - enh_levels 0/1/2 pull_enhanced 0/1 
        - group_base[g] multicast actual 
        - user_base[u] unicast baseline 
    """
    # LEGACY_NON_SCIENTIFIC_RB_HARDCODE: do not use on scientific native9 Ro path.
    base_bitrates = {1: 3.07, 2: 1.79, 3: 0.87}
    # Enhanced rep4-rep1=4.54-3.07=1.47, rep5-rep1=6.42-3.07=3.35
    enhanced_bitrate = 1.47
    enhanced_bitrate_level2 = 3.35
    
    # Step 1: base group_base[g] -
    group_base_versions = {}  # {group_id: base_version}
    for g in range(num_groups):
        group_members = [u for u in range(num_users) if group_assignments[u] == g]
        if group_members:
            min_throughput = float('inf')
            min_device_score = float('inf')
            for user_id in group_members:
                state_file = _client_state_file(user_id + 1)
                try:
                    if os.path.exists(state_file):
                        with open(state_file, 'r') as f:
                            state = json.load(f)
                            throughput = state.get('throughput_mbps', 0.0)
                            device_score = state.get('device_score', 1.0)
                            if throughput > 0:
                                min_throughput = min(min_throughput, throughput)
                            min_device_score = min(min_device_score, device_score)
                except:
                    pass
            
            # base
            if min_throughput != float('inf'):
                base_device_requirements = {1: 0.7, 2: 0.5, 3: 0.3}
                available_bw = min_throughput * 0.8
                for base_ver in [1, 2, 3]:
                    required_bw = base_bitrates[base_ver]
                    required_device = base_device_requirements[base_ver]
                    if available_bw >= required_bw and min_device_score >= required_device:
                        group_base_versions[g] = base_ver
                        break
                if g not in group_base_versions:
                    group_base_versions[g] = 3
            else:
                group_base_versions[g] = 3
    
    # Step 2: base user_base[u] - unicast baseline
    user_base_versions = {}  # {user_id: base_version}
    for u in range(num_users):
        state_file = _client_state_file(u + 1)
        try:
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    user_throughput = state.get('throughput_mbps', 0.0)
                    user_device_score = state.get('device_score', 1.0)
                    
                    if user_throughput > 0:
                        base_device_requirements = {1: 0.7, 2: 0.5, 3: 0.3}
                        available_bw = user_throughput * 0.8
                        for base_ver in [1, 2, 3]:
                            required_bw = base_bitrates[base_ver]
                            required_device = base_device_requirements[base_ver]
                            if available_bw >= required_bw and user_device_score >= required_device:
                                user_base_versions[u] = base_ver
                                break
                        if u not in user_base_versions:
                            user_base_versions[u] = 3
                    else:
                        user_base_versions[u] = 3
        except:
            user_base_versions[u] = 3
    
    # Step 3: Unicast Baseline
    # user_base[u] base
    unicast_bytes = 0.0
    for u in range(num_users):
        user_base = user_base_versions.get(u, 3)
        unicast_bytes += base_bitrates[user_base]
        
        # ✅ enh_level 0/1/2 pull_enhanced 0/1
        if enh_levels[u] == 1:
            unicast_bytes += enhanced_bitrate  # base+enh1
        elif enh_levels[u] == 2:
            unicast_bytes += enhanced_bitrate_level2  # base+enh1+enh2
        # enh_levels[u] == 0 enhanced
    
    # Step 4: Multicast Actual
    # group_base[g]
    multicast_bytes = 0.0
    for g in range(num_groups):
        group_members = [u for u in range(num_users) if group_assignments[u] == g]
        if group_members:
            # base
            group_base = group_base_versions.get(g, 3)
            multicast_bytes += base_bitrates[group_base]
            
            # Enhanced
            for u in group_members:
                # ✅ enh_level 0/1/2 pull_enhanced 0/1
                if enh_levels[u] == 1:
                    multicast_bytes += enhanced_bitrate
                elif enh_levels[u] == 2:
                    multicast_bytes += enhanced_bitrate_level2
    
    # Step 5: R_o
    R_o = 1.0 - (multicast_bytes / (unicast_bytes + 1e-9))
    R_o = max(0.0, min(1.0, R_o))
    
    return R_o, unicast_bytes, multicast_bytes


def calculate_native9_multicast_saving(group_assignments, selected_reps, num_users):
    """Native Rep1–9 Ro: unique (group, selected_rep) streams counted once.

    paper_U weights unchanged. Two-track Enhanced-as-unicast is MM26 leftover and
    mechanically collapses Ro whenever independently-decodable Rep8/9 are mapped
    to enh_level 1/2. Gated by TON_NATIVE9REP_RO + scientific decision gate.
    Rates come only from resolve_rep_bitrate_mbps (env/content map; fail-closed).
    """
    uni = 0.0
    streams = {}
    for u in range(num_users):
        try:
            rid = int(selected_reps[u] or 0)
        except Exception:
            rid = 0
        if rid < 1 or rid > 9:
            continue
        br = float(resolve_rep_bitrate_mbps(rid))
        uni += br
        gid = int(group_assignments[u]) if u < len(group_assignments) else 0
        streams[(gid, rid)] = br
    multi = float(sum(streams.values()))
    if uni <= 1e-9:
        return 0.0, uni, multi
    ro = max(0.0, min(1.0, 1.0 - multi / uni))
    return ro, uni, multi


def run_client(a):
    # ✅ os UnboundLocalError
    _ = os.path
    if _nested_components_enabled():
        _lib = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "Sigcomm26",
            "Paper6_ToN",
            "lib",
        )
        if _lib not in sys.path:
            sys.path.insert(0, _lib)
        from command147_nested_client import run_nested_component_client  # noqa: E402

        print(
            f"[COMPONENT-SCRIPT] h{a.host_id}: nested component client (no learned MD2G)",
            file=sys.stderr,
            flush=True,
        )
        return run_nested_component_client(a)
    
    # ✅ Rolling RL MD2G, Heuristic, Clustering, Groot, Pano
    # controller
    # 2. controller
    # 3. perf.csv
    if a.strategy == "rolling":
        # ✅ Rolling r1/r2 SC-DDQN
        strat = None
        print(f"[INFO] h{a.host_id}: Rolling - (regional_relay_controller) ", file=sys.stderr, flush=True)
    elif a.strategy == "md2g":
        # ✅ MD2G regional_relay_controller.py
        # MD2G relay
        strat = None
        print(f"[INFO] h{a.host_id}: MD2G - (regional_relay_controller) ", file=sys.stderr, flush=True)
    else:
        # ✅ Heuristic, Clustering, Groot, Pano
        # controller
        strat = None
        print(f"[INFO] h{a.host_id}: {a.strategy} - ", file=sys.stderr, flush=True)

    state_window, qoe_window = deque(maxlen=3), deque(maxlen=15)

    os.makedirs(a.log_path, exist_ok=True)
    perf_log = os.path.join(a.log_path, f"client_h{a.host_id}_perf.log")
    perf_csv = os.path.join(a.log_path, f"client_h{a.host_id}_perf.csv")
    gst_log = os.path.join(a.log_path, f"client_h{a.host_id}_gst.log")
    
    # ✅ CSV CSV TTLB
    # ✅ Phase 0 rep_id buffer_level_sec buffer_level_sec rep_id
    csv_header = "timestamp,user_id,network_type,device_score,base_version,enhanced_level,subscription_type," \
                 "ttfb_base_ms,ttfb_enh1_ms,ttfb_enh2_ms,ttfb_enh3_ms,delay_ms," \
                 "stall_count,stall_count_inc,stall_total_sec,rx_bytes," \
                 "buffer_level_sec,rep_id,qoe,reward_R_o,reward_R_q,reward_R_b,reward_final," \
                 "grouping_id,grouping_efficiency,load_balance_jfi,decision_step," \
                 "quality_level,quality_score," \
                 "cpu_bottleneck_node_percent,cpu_relay_process_percent,cpu_controller_process_percent," \
                 "cpu_dash_server_process_percent,cpu_system_percent,retransmission_count"
    if _metric_v4_timeline_enabled():
        csv_header += ",payload_ttfb_ms,media_covered_sec"
    csv_header += "\n"
    
    with open(perf_log, "w") as f:
        # R_t = λ_o*R_o + λ_q*R_q - λ_b*R_b
        # ✅ Time to Last Byte (ttlb_ms)
        f.write(csv_header)
    
    with open(perf_csv, "w") as f:
        f.write(csv_header)
    
    print(f"[INFO] h{a.host_id}: ✅ CSV : {perf_csv}", file=sys.stderr, flush=True)
    _c137_sha = os.environ.get("COMMAND137_RUN_CONTRACT_SHA", "").strip()
    if _c137_sha:
        _c137_echo = {
            "run_contract_sha256": _c137_sha,
            "transport_profile_id": os.environ.get("COMMAND137_TRANSPORT_PROFILE_ID", "").strip(),
            "b3_sha256": os.environ.get("COMMAND137_B3_SHA256", "").strip(),
            "source": "subscriber_perf_metadata",
            "host_id": a.host_id,
        }
        _c137_dir = os.environ.get("COMMAND137_CELL_DIR") or os.path.dirname(perf_csv)
        try:
            with open(os.path.join(_c137_dir, f"client_h{a.host_id}_run_contract.json"), "w", encoding="utf-8") as _cf:
                json.dump(_c137_echo, _cf, indent=2)
                _cf.write("\n")
        except Exception as _ce:
            print(f"[COMMAND137-RUN-CONTRACT] write failed: {_ce}", file=sys.stderr, flush=True)
        print(
            f"[COMMAND137-RUN-CONTRACT] sha={_c137_sha} profile={_c137_echo['transport_profile_id']} b3={_c137_echo['b3_sha256']}",
            file=sys.stderr,
            flush=True,
        )

    # --- Instrumentation V2 (command60/61): early cell/user sink ---
    instr_v2 = None
    instr_v2_jsonl = None
    if _instrumentation_v2_enabled():
        _cell_id = (
            os.environ.get("SIGCOMM_CELL_TMP")
            or os.environ.get("SIGCOMM_CELL_ID")
            or a.log_path
            or "unknown"
        )
        instr_v2 = InstrumentationV2(cell=str(_cell_id).strip(), user=a.host_id)
        instr_v2_jsonl = os.path.join(
            os.environ.get("SIGCOMM_CELL_LOG_PATH", "/tmp"),
            f"instrumentation_v2_h{a.host_id}.jsonl",
        )
        print(
            f"[INSTR-V2] h{a.host_id}: enabled cell={_cell_id} jsonl={instr_v2_jsonl}",
            file=sys.stderr,
            flush=True,
        )

    if int(a.host_id) == 1:
        _eq9_banner = os.environ.get("SIGCOMM_QOE_EQ9", "").strip().lower() in ("1", "true", "yes", "on")
        if _eq9_banner:
            qoe_note = (
                "QoE → qoe / reward_R_q via SIGCOMM Eq.9 "
                "(Q_s from final Rep ID → Q1–Q4); quality_score=Q_s"
            )
        else:
            qoe_note = (
                "QoE → qoe = MM26 qoe_mcast_aware md2g/clustering/heuristic R_q R_o "
                "rolling/pcc-dash R_q , reward_final, quality_score(MM26 ), delay_ms"
            )
        print(
            "[METRICS] Sigcomm client_h*_perf.csv / perf.log Buffer/QoE/Stall/TTFB/Throughput/CPU \n"
            "  Buffer Level → buffer_level_sec\n"
            f"  {qoe_note}\n"
            " Stall Time → stall_count, stall_count_inc, stall_total_sec timestamp \n"
            " Throughput → rx_bytes + timestamp + user_id Throughput/plot_system_throughput.py \n"
            "  TTFB → ttfb_base_ms, ttfb_enh1_ms, ttfb_enh2_ms, ttfb_enh3_ms\n"
            "  CPU usage → cpu_bottleneck_node_percent, cpu_relay_process_percent, "
            "cpu_controller_process_percent, cpu_dash_server_process_percent, cpu_system_percent\n",
            file=sys.stderr,
            flush=True,
        )

    # 3) GStreamer
    # ✅ relay_ip r1/r2
    # relay_ip host_id r1 r2
    # ✅ relay_ip
    if a.relay_ip and a.relay_ip.strip():
        # ✅ relay_ip r1 r2 IP
        relay_ip = a.relay_ip.strip()
        if relay_ip == "10.0.2.1":
            relay_name = "r0"
        elif relay_ip == "10.0.2.2":
            relay_name = "r1"
        elif relay_ip == "10.0.3.2":
            relay_name = "r2"
        else:
            relay_name = "unknown"
            print(f"[WARN] h{a.host_id}: relay_ip={relay_ip} ", file=sys.stderr, flush=True)
            # relay_ip
            relay_ip = assign_relay_ip(a.host_id, a.clients)
            relay_name = "r1" if relay_ip == "10.0.2.2" else "r2"
    else:
        relay_ip = assign_relay_ip(a.host_id, a.clients)
        relay_name = "r1" if relay_ip == "10.0.2.2" else "r2"
    current_relay_ip = relay_ip
    print(f"[DEBUG] h{a.host_id}: relay_ip={relay_ip} ( {relay_name})", file=sys.stderr, flush=True)
    # IPv4 hangsrc GST_DEBUG
    # GStreamer hangsrc
    # a.gst_plugin_path libgsthang.so
    system_gst_path = "/usr/lib/x86_64-linux-gnu/gstreamer-1.0"
    GST_ENV = f"GST_PLUGIN_PATH={a.gst_plugin_path}:{system_gst_path} "
    GST_ENV += "RUST_BACKTRACE=1 RUST_LOG=info "
    GST_ENV += "MOQ_HANGSRC_FORCE_IPV4=1 MOQ_HANGSRC_DISABLE_ZERO_COPY=1 "
    GST_ENV += "GST_DEBUG=hangsrc:4,pipeline:3,queue:3,decodebin:3 "
    GST_ENV += f"GST_DEBUG_FILE=/tmp/client_logs/client_h{a.host_id}_gstdebug.log "
    
    # pipeline decodebin
    # pipeline
    # hangsrc
    # 
    # SIMPLE -> MEDIUM -> FULL
    # SIMPLE: hangsrc
    # MEDIUM: decodebin
    # FULL: pipeline videoconvert
    #
    # async=false fakesink preroll
    # pipeline NULL pipeline PAUSED/PLAYING
    
    # ========== hangsrc moq-sub ==========
    # Fail-closed SIGCOMM path: SIGCOMM_MOQ_BIN_DIR or in-repo release dirs.
    def _resolve_moq_sub_path():
        env = (os.environ.get("SIGCOMM_MOQ_BIN_DIR") or "").strip()
        candidates = []
        if env:
            candidates.append(os.path.join(env, "moq-sub"))
        repo = os.path.dirname(os.path.abspath(__file__))
        candidates.extend([
            os.path.join(repo, "V-PCC", "MoQ", "moq-main_3", "moq-main", "target", "release", "moq-sub"),
        ])
        for c in candidates:
            if c and os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return candidates[0] if candidates else "moq-sub"

    MOQ_SUB_PATH = _resolve_moq_sub_path()
    
    # ✅ MoQ dump hangsrc
    moq_dump_file = f"/tmp/moq_h{a.host_id}.bin"
    
    def check_moq_sub():
        # ✅ subprocess
        import subprocess as sp
        try:
            if not os.path.exists(MOQ_SUB_PATH):
                print(f"[WARN] h{a.host_id}: moq-sub : {MOQ_SUB_PATH}", file=sys.stderr, flush=True)
                return False
            check_cmd = [MOQ_SUB_PATH, "--help"]
            result = sp.run(check_cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"[DEBUG] h{a.host_id}: moq-sub ", file=sys.stderr, flush=True)
                return True
            else:
                print(f"[WARN] h{a.host_id}: moq-sub : {result.stderr}", file=sys.stderr, flush=True)
                return False
        except Exception as e:
            print(f"[WARN] h{a.host_id}: moq-sub : {e}", file=sys.stderr, flush=True)
            return False
    
    def build_moq_sub_cmd(track_url: str, output_file: str):
        """ moq-sub 
        track_url: MoQ URL ( track https://relay:4443/track hang namespace)
        output_file: 
        """
        # moq-sub https:// moql://
        # URL https:// moq:// https://
        if track_url.startswith("moq://"):
            track_url = track_url.replace("moq://", "https://", 1)
        elif not track_url.startswith("https://"):
            # https://
            if not track_url.startswith("http"):
                track_url = f"https://{track_url}"
        
        # ✅ track URL --track
        # ✅ --tls-disable-verify
        cmd = [
            MOQ_SUB_PATH,
            track_url,
            "--dump", output_file,
            "--tls-disable-verify"
        ]
        
        return cmd
    
    moq_sub_available = check_moq_sub()
    base_p = None
    
    if not moq_sub_available:
        print(f"[ERROR] h{a.host_id}: ❌ moq-sub ", file=sys.stderr, flush=True)
        sys.exit(1)
    else:
        print(f"[DEBUG] h{a.host_id}: base moq-sub ", file=sys.stderr, flush=True)
        
        # ============================================================
        # Module 3: Client-side cache-aware fetch (Federation ON)
        # ============================================================
        # Try to fetch from federation cache first if federation is ON
        if a.federation == 'on':
            # Import relay_cache from topo module (will be available at runtime)
            try:
                # Try to fetch cached segment
                segment_seq = 0  # Start with first segment
                cache_key = f"redandblack_base_segment_{segment_seq}"
                
                # Note: In a real implementation, relay_cache would be accessible
                # For now, we simulate cache check via file system or shared memory
                cache_file = f"/tmp/federation_cache_{cache_key}"
                if os.path.exists(cache_file):
                    print(f"[CACHE HIT] h{a.host_id}: {cache_key}", file=sys.stderr, flush=True)
                    # Load from cache
                    with open(cache_file, 'rb') as f:
                        cached_data = f.read()
                    if cached_data:
                        with open(moq_dump_file, 'wb') as f:
                            f.write(cached_data)
                        print(f"[CACHE] h{a.host_id}: Base loaded from federation cache", file=sys.stderr, flush=True)
                        # Continue with moq-sub for subsequent segments
                else:
                    print(f"[CACHE MISS] h{a.host_id}: {cache_key}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[WARN] h{a.host_id}: Cache check failed: {e}", file=sys.stderr, flush=True)
        
        # ✅ simple_moq_test.py URL + --broadcast
        # ✅ relay_ip relay URL
        # ⚠️ simple_moq_test.py
        # - URL: https://r1.local:4443/ https://r2.local:4443/ ( /base)
        # - --broadcast base ( )
        # - --track video0 ( )
        # 
        # Relay
        # - r1.local:4443
        # - r2.local:4443
        # - r1 r2 moq-relay 4443
        # ✅ relay_ip relay URL
        # ⚠️ relay_ip relay
        print(f"[DEBUG] h{a.host_id}: relay URL relay_ip={relay_ip}", file=sys.stderr, flush=True)
        if relay_ip == "10.0.2.2":  # r1
            track_url = f"https://r1.local:4443/"
            relay_domain = "r1.local"
            relay_name_for_url = "r1"
            print(f"[DEBUG] h{a.host_id}: ✅ r1 (relay_ip={relay_ip})", file=sys.stderr, flush=True)
        elif relay_ip == "10.0.3.2":  # r2
            track_url = f"https://r2.local:4443/"
            relay_domain = "r2.local"
            relay_name_for_url = "r2"
            print(f"[DEBUG] h{a.host_id}: ✅ r2 (relay_ip={relay_ip})", file=sys.stderr, flush=True)
        else:
            # ⚠️ relay_ip r1/r2
            print(f"[ERROR] h{a.host_id}: ❌ relay_ip={relay_ip} r1/r2 r0 ", file=sys.stderr, flush=True)
            track_url = f"https://r0.local:4443/"
            relay_domain = "r0.local"
            relay_name_for_url = "r0"
        
        print(f"[DEBUG] h{a.host_id}: ...", file=sys.stderr, flush=True)
        
        # ✅ relay_ip ping
        relay_ip_to_ping = relay_ip
        
        try:
            import socket
            relay_ip_resolved = socket.gethostbyname(relay_domain)
            print(f"[DEBUG] h{a.host_id}: ✅ {relay_domain} {relay_ip_resolved}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[ERROR] h{a.host_id}: ❌ {relay_domain}: {e}", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: /etc/hosts...", file=sys.stderr, flush=True)
            try:
                with open('/etc/hosts', 'r') as f:
                    hosts_content = f.read()
                    if relay_domain in hosts_content:
                        print(f"[DEBUG] h{a.host_id}: /etc/hosts {relay_domain} ", file=sys.stderr, flush=True)
                    else:
                        print(f"[ERROR] h{a.host_id}: /etc/hosts {relay_domain} ", file=sys.stderr, flush=True)
                        # ✅ subprocess
                        import subprocess as sp_check
                        sp_check.run(['sh', '-c', f'echo "{relay_ip} {relay_domain}" >> /etc/hosts'], check=False)
                        print(f"[DEBUG] h{a.host_id}: {relay_domain} ({relay_ip}) /etc/hosts", file=sys.stderr, flush=True)
            except Exception as e2:
                print(f"[WARN] h{a.host_id}: /etc/hosts : {e2}", file=sys.stderr, flush=True)
        
        # ping relay IP
        # ✅ subprocess
        import subprocess as sp_check
        try:
            ping_result = sp_check.run(['ping', '-c', '1', '-W', '1', relay_ip_to_ping], 
                                       capture_output=True, timeout=3)
            if ping_result.returncode == 0:
                print(f"[DEBUG] h{a.host_id}: ✅ ping {relay_name} ({relay_ip_to_ping})", file=sys.stderr, flush=True)
            else:
                print(f"[WARN] h{a.host_id}: ⚠️ ping {relay_name} ({relay_ip_to_ping})", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[WARN] h{a.host_id}: ping : {e}", file=sys.stderr, flush=True)
        
        # nc telnet relay 4443
        try:
            nc_result = sp_check.run(['nc', '-z', '-w', '1', relay_ip_to_ping, '4443'], 
                                      capture_output=True, timeout=3)
            if nc_result.returncode == 0:
                print(f"[DEBUG] h{a.host_id}: ✅ {relay_name}:4443 ", file=sys.stderr, flush=True)
            else:
                print(f"[WARN] h{a.host_id}: ⚠️ {relay_name}:4443 ", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[WARN] h{a.host_id}: nc : {e}", file=sys.stderr, flush=True)
        
        # ✅ PPO Controller
        # Controller
        print(f"[DEBUG] h{a.host_id}: Controller 5 ...", file=sys.stderr, flush=True)
        time.sleep(5)
        
        # Controller
        user_group = None
        max_retries = 10
        retry_interval = 0.5
        for retry in range(max_retries):
            try:
                if os.path.exists(a.decision_file):
                    with open(a.decision_file, 'r') as f:
                        decision_data = json.load(f)
                    
                    if 'decisions' in decision_data and str(a.host_id) in decision_data['decisions']:
                        user_decision = decision_data['decisions'][str(a.host_id)]
                        user_group = user_decision.get('md2g_group_id')
                        if user_group is not None:
                            user_group = int(user_group) + 1
                            break
            except Exception as e:
                if retry == 0:
                    print(f"[WARN] h{a.host_id}: : {e}", file=sys.stderr, flush=True)
                time.sleep(retry_interval)
        
        # fallback
        if user_group is None:
            print(f"[WARN] h{a.host_id}: fallback ", file=sys.stderr, flush=True)
            user_group = (a.host_id - 1) % 3 + 1
        
        # ✅ base
        print(f"[DEBUG] h{a.host_id}: 5 ...", file=sys.stderr, flush=True)
        time.sleep(5)
        
        # base
        base_version = select_base_version_by_group_minimum(a.host_id, user_group, a.clients)
        base_broadcast_name = f"base{base_version}"
        print(f"[INFO] h{a.host_id}: : Group {user_group} ( Controller), Base : {base_broadcast_name}", file=sys.stderr, flush=True)
        
        # moq-sub latency wrapper
        print(f"[DEBUG] h{a.host_id}: moq-sub base ", file=sys.stderr, flush=True)
        
        # ✅ latency wrapper
        # Fail-closed: repo-local wrapper.
        _repo = os.path.dirname(os.path.abspath(__file__))
        latency_wrapper = os.path.join(_repo, "moq_sub_with_latency.py")
        if not os.path.isfile(latency_wrapper):
            latency_wrapper = os.path.join(_repo, "Sigcomm26", "moq_sub_with_latency.py")
        latency_log_file = f"/tmp/moq_latency_h{a.host_id}_base.log"
        sub_start_time = time.time()
        
        if not os.path.isfile(latency_wrapper):
            print(f"[ERROR] h{a.host_id}: latency wrapper missing: {latency_wrapper}", file=sys.stderr, flush=True)
            return

        # Track/broadcast must match hang publish defaults.
        track_name = "video0"
        broadcast_name = base_broadcast_name
        base_cmd_wrapper = [
            sys.executable,
            latency_wrapper,
            MOQ_SUB_PATH,
            track_name,
            track_url,
            moq_dump_file,
            gst_log,
            latency_log_file,
            str(sub_start_time),
            broadcast_name,
        ]
        print(f"[INFO] h{a.host_id}: moq-sub base latency wrapper ", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: Track : {track_name} ( Publisher )", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: URL: {track_url}", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: moq-sub dump : {moq_dump_file}", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: : {latency_log_file} ( )", file=sys.stderr, flush=True)
        
        # 300s Mininet
        # 1800s 30 Publisher Relay
        env = os.environ.copy()
        env['MOQ_TLS_DISABLE_VERIFY'] = '1'
        env['MOQ_TRANSPORT_IDLE_TIMEOUT'] = '1800s'
        env['QUIC_IDLE_TIMEOUT'] = '1800s'
        env['RUST_LOG'] = 'info'
        env['RUST_BACKTRACE'] = '1'
        
        # ✅ PIPE + DataDrainer Pipe
        # stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0
        # bufsize=0
        base_p = subprocess.Popen(
            base_cmd_wrapper,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            env=env
        )
        
        # ✅ Base DataDrainer
        # ✅ TTFB/TTLB
        base_start_time = time.time()
        reader_base = DataDrainer(base_p, "Base_Stream", gst_log, start_time_epoch=base_start_time)
        reader_base.start()
        run_client._llc_base = int(base_version)
        print(f"[INFO] h{a.host_id}: ✅ Base DataDrainer Pipe ", file=sys.stderr, flush=True)
        
        print(f"[INFO] h{a.host_id}: moq-sub PID: {base_p.pid} ...", file=sys.stderr, flush=True)
        
        # ✅ publisher 30
        connection_timeout = 30
        connection_start = time.time()
        session_started = False
        
        while time.time() - connection_start < connection_timeout:
            if base_p.poll() is not None:
                exit_code = base_p.returncode
                print(f"[WARN] h{a.host_id}: moq-sub : {exit_code} ", file=sys.stderr, flush=True)
                try:
                    with open(gst_log, "r", errors="ignore") as f:
                        log_content = f.read()
                        if "ApplicationClosed" in log_content:
                            print(f"[ERROR] h{a.host_id}: ❌ ApplicationClosed - Track ", file=sys.stderr, flush=True)
                            print(f"[ERROR] h{a.host_id}: : 1) TLS 2) Track Publisher ", file=sys.stderr, flush=True)
                        elif "TimedOut" in log_content or "timeout" in log_content.lower():
                            print(f"[ERROR] h{a.host_id}: ❌ TimedOut - UDP ", file=sys.stderr, flush=True)
                            print(f"[ERROR] h{a.host_id}: : 1) 2) 3) ", file=sys.stderr, flush=True)
                        elif "session started" in log_content.lower() or "Session started" in log_content:
                            session_started = True
                            print(f"[INFO] h{a.host_id}: ✅ moq-sub session started ✓", file=sys.stderr, flush=True)
                            break
                        log_lines = log_content.split('\n')
                        if len(log_lines) > 5:
                            print(f"[DEBUG] h{a.host_id}: 5 :", file=sys.stderr, flush=True)
                            for line in log_lines[-5:]:
                                if line.strip():
                                    print(f"[DEBUG] h{a.host_id}: {line}", file=sys.stderr, flush=True)
                except Exception as e:
                    print(f"[WARN] h{a.host_id}: : {e}", file=sys.stderr, flush=True)
                break
            
            # session started
            try:
                with open(gst_log, "r", errors="ignore") as f:
                    log_content = f.read()
                    if "session started" in log_content.lower() or "Session started" in log_content:
                        session_started = True
                        print(f"[INFO] h{a.host_id}: ✅ moq-sub session started ✓", file=sys.stderr, flush=True)
                        break
            except Exception:
                pass
            
            time.sleep(0.5)
        
        if not session_started:
            print(f"[ERROR] h{a.host_id}: ❌ moq-sub {connection_timeout} ", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: ⚠️ : 1) Publisher 2) Broadcast 3) Track ", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: : 1) Publisher n0 2) Relay publish=base", file=sys.stderr, flush=True)
            try:
                with open(gst_log, "r", errors="ignore") as f:
                    log_lines = f.readlines()
                    if log_lines:
                        print(f"[ERROR] h{a.host_id}: moq-sub 10 :", file=sys.stderr, flush=True)
                        for line in log_lines[-10:]:
                            print(f"  {line.rstrip()}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[WARN] h{a.host_id}: moq-sub : {e}", file=sys.stderr, flush=True)
            if base_p.poll() is None:
                base_p.terminate()
                time.sleep(0.5)
                if base_p.poll() is None:
                    base_p.kill()
            # ✅ topo
            print(f"[ERROR] h{a.host_id}: moq-sub ", file=sys.stderr, flush=True)
            # sys.exit(1) #
        
        print(f"[INFO] h{a.host_id}: moq-sub ...", file=sys.stderr, flush=True)
        data_timeout = 30
        data_start = time.time()
        startup_success = False
        
        while time.time() - data_start < data_timeout:
            try:
                if os.path.exists(moq_dump_file):
                    file_size = os.path.getsize(moq_dump_file)
                    if file_size > 0:
                        print(f"[INFO] h{a.host_id}: ✅ : {file_size} bytes moq-sub ✓", file=sys.stderr, flush=True)
                        startup_success = True
                        # ✅ Time to Last Byte
                        if not hasattr(run_client, 'sub_start_time'):
                            run_client.sub_start_time = time.time()
                        break
            except Exception as e:
                print(f"[WARN] h{a.host_id}: : {e}", file=sys.stderr, flush=True)
            
            if base_p.poll() is not None:
                print(f"[WARN] h{a.host_id}: moq-sub : {base_p.returncode} ", file=sys.stderr, flush=True)
                break
            
            time.sleep(1)
        
        if not startup_success:
            print(f"[ERROR] h{a.host_id}: ❌ moq-sub {data_timeout} 0 ", file=sys.stderr, flush=True)
            try:
                with open(gst_log, "r", errors="ignore") as f:
                    log_lines = f.readlines()
                    if log_lines:
                        print(f"[ERROR] h{a.host_id}: moq-sub 10 :", file=sys.stderr, flush=True)
                        for line in log_lines[-10:]:
                            print(f"  {line.rstrip()}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[WARN] h{a.host_id}: moq-sub : {e}", file=sys.stderr, flush=True)
            # dump
            if os.path.exists(moq_dump_file):
                file_size = os.path.getsize(moq_dump_file)
                print(f"[ERROR] h{a.host_id}: dump {file_size} bytes", file=sys.stderr, flush=True)
            else:
                print(f"[ERROR] h{a.host_id}: dump : {moq_dump_file}", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: ", file=sys.stderr, flush=True)
            # ✅ topo
            # if base_p.poll() is None:
            #     base_p.terminate()
            #     time.sleep(0.5)
            #     if base_p.poll() is None:
            #         base_p.kill()
            # sys.exit(1) #
        
        print(f"[INFO] h{a.host_id}: ✅ moq-sub base ✓", file=sys.stderr, flush=True)
        
        # ✅ Time to Last Byte
        run_client.sub_start_time = time.time()

    # --- FULL_INDEPENDENT_REPS lifecycle (command60/61) ---
    rep_lc_v2 = _rep_lifecycle_v2_enabled()
    rep_lc = RepLifecycle() if rep_lc_v2 else None
    rep_subs = {}  # rep_id -> {proc, reader, dump, broadcast}
    rep_sub_dump_sizes = {}
    current_rep_id = map_to_rep_id(base_version, 0)
    rep_lc_jsonl = os.path.join(
        os.environ.get("SIGCOMM_CELL_LOG_PATH", "/tmp"),
        f"rep_lifecycle_h{a.host_id}.jsonl",
    )

    initial_rep_id = current_rep_id
    if rep_lc_v2 and rep_lc is not None:
        rep_lc.seed_rendered(initial_rep_id)
        rep_subs[initial_rep_id] = {
            "proc": base_p,
            "reader": reader_base,
            "dump": moq_dump_file,
            "broadcast": base_broadcast_name,
        }
        rep_sub_dump_sizes[initial_rep_id] = (
            os.path.getsize(moq_dump_file) if os.path.exists(moq_dump_file) else 0
        )
        print(
            f"[REP-LC-V2] h{a.host_id}: seeded rep{initial_rep_id} ({base_broadcast_name}), "
            f"jsonl={rep_lc_jsonl}",
            file=sys.stderr,
            flush=True,
        )

    def _rep_lc_append_snapshot() -> None:
        if not rep_lc_v2 or rep_lc is None:
            return
        rec = rep_lc.snapshot()
        rec["host_id"] = a.host_id
        rec["ts"] = time.time()
        try:
            with open(rep_lc_jsonl, "a") as jf:
                jf.write(json.dumps(rec) + "\n")
        except Exception as exc:
            print(f"[WARN] h{a.host_id}: rep lifecycle jsonl write failed: {exc}", file=sys.stderr, flush=True)

    def _instr_v2_tick() -> None:
        """Periodic client-side direct records (payload, overlap, cpu/mem)."""
        if instr_v2 is None or instr_v2_jsonl is None:
            return
        payload_bytes = 0
        if rep_lc_v2 and rep_subs:
            for _rid, sub in rep_subs.items():
                dump_path = sub.get("dump")
                if dump_path and os.path.exists(dump_path):
                    try:
                        payload_bytes += os.path.getsize(dump_path)
                    except OSError:
                        pass
        elif os.path.exists(moq_dump_file):
            try:
                payload_bytes = os.path.getsize(moq_dump_file)
            except OSError:
                payload_bytes = 0
        rep_id = rep_lc.rendered_rep if rep_lc_v2 and rep_lc is not None else None
        epoch = rep_lc.decision_epoch if rep_lc_v2 and rep_lc is not None else 0
        instr_v2.record_client_payload_bytes(payload_bytes, rep=rep_id, epoch=epoch)
        if rep_lc_v2 and rep_lc is not None:
            instr_v2.record_simultaneous_active_reps(
                rep_lc.simultaneous_active_count(), epoch=epoch
            )
        instr_v2.record_cpu_memory(instr_v2.overhead_snapshot(), epoch=epoch)
        try:
            instr_v2.write_jsonl(instr_v2_jsonl, append=True)
        except Exception as exc:
            print(
                f"[WARN] h{a.host_id}: instrumentation v2 jsonl write failed: {exc}",
                file=sys.stderr,
                flush=True,
            )

    def _terminate_rep_sub(rid: int) -> bool:
        sub = rep_subs.get(rid)
        if not sub:
            return False
        proc = sub.get("proc")
        try:
            reader = sub.get("reader")
            if reader is not None:
                reader.stop()
            if proc is not None and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=2)
        except Exception as exc:
            print(f"[WARN] h{a.host_id}: terminate rep{rid} sub failed: {exc}", file=sys.stderr, flush=True)
            try:
                if proc is not None and proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
        rep_subs.pop(rid, None)
        rep_sub_dump_sizes.pop(rid, None)
        return True

    def _start_rep_moq_sub(rep_id: int, broadcast_name: str) -> None:
        if rep_id in rep_subs:
            return
        dump_file = (
            moq_dump_file if rep_id == initial_rep_id else f"/tmp/moq_h{a.host_id}_rep{rep_id}.bin"
        )
        log_file = (
            gst_log if rep_id == initial_rep_id else gst_log.replace(".log", f"_rep{rep_id}.log")
        )
        latency_log_file = f"/tmp/moq_latency_h{a.host_id}_rep{rep_id}.log"
        sub_start_time = time.time()
        cmd_wrapper = [
            sys.executable,
            latency_wrapper,
            MOQ_SUB_PATH,
            "video0",
            track_url,
            dump_file,
            log_file,
            latency_log_file,
            str(sub_start_time),
            broadcast_name,
        ]
        cmd_wrapper = ["taskset", "-c", str(a.host_id % 32)] + cmd_wrapper
        env_sub = os.environ.copy()
        env_sub["MOQ_TLS_DISABLE_VERIFY"] = "1"
        env_sub["MOQ_TRANSPORT_IDLE_TIMEOUT"] = "1800s"
        env_sub["QUIC_IDLE_TIMEOUT"] = "1800s"
        env_sub["RUST_LOG"] = "info"
        env_sub["RUST_BACKTRACE"] = "1"
        proc = subprocess.Popen(
            cmd_wrapper,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            env=env_sub,
        )
        reader = DataDrainer(
            proc,
            f"Rep{rep_id}_Stream",
            log_file,
            start_time_epoch=sub_start_time,
        )
        reader.start()
        rep_lc.begin_subscribe(rep_id)
        rep_subs[rep_id] = {
            "proc": proc,
            "reader": reader,
            "dump": dump_file,
            "broadcast": broadcast_name,
        }
        rep_sub_dump_sizes[rep_id] = 0
        print(
            f"[REP-LC-V2] h{a.host_id}: moq-sub rep{rep_id} ({broadcast_name}) PID={proc.pid}",
            file=sys.stderr,
            flush=True,
        )

    def _rep_lc_maintain() -> None:
        """Per-iteration dump promotion, pending cancel, overlap fault."""
        if not rep_lc_v2 or rep_lc is None:
            return
        nonlocal current_rep_id

        for rid, sub in list(rep_subs.items()):
            dump_path = sub["dump"]
            prev_sz = rep_sub_dump_sizes.get(rid, 0)
            try:
                cur_sz = os.path.getsize(dump_path) if os.path.exists(dump_path) else 0
            except OSError:
                cur_sz = prev_sz
            if cur_sz > prev_sz and cur_sz > 0:
                if rep_lc.intended_rep == rid and rep_lc.delivered_rep != rid:
                    ready = True
                    if _opt7_make_before_break() and rep_lc.rendered_rep not in (None, rid):
                        try:
                            br = float(resolve_rep_bitrate_mbps(int(rid)))
                        except Exception:
                            br = 1.0
                        need = max(8000.0, br * 1e6 / 8.0 * 1.0)
                        buf = float(buffer_level_sec) if iteration > 0 else 0.0
                        ready = cur_sz >= need and buf >= 1.0
                        if not ready and buf < 0.5 and rid != rep_lc.rendered_rep:
                            print(
                                f"[OPT7-HANDOFF] h{a.host_id}: abort prefetch rep{rid} "
                                f"buffer={buf:.2f}s dump={cur_sz}",
                                file=sys.stderr,
                                flush=True,
                            )
                            if _terminate_rep_sub(int(rid)):
                                if rep_lc.rendered_rep is not None:
                                    rep_lc.request_target(int(rep_lc.rendered_rep))
                            ready = False
                    if ready:
                        rep_lc.on_first_valid_object(rid)
                        if rep_lc.rendered_rep is not None:
                            current_rep_id = rep_lc.rendered_rep
                        _rep_lc_append_snapshot()
            rep_sub_dump_sizes[rid] = cur_sz

        snap = rep_lc.snapshot()
        pending = snap.get("pending_cancel")
        if pending is not None:
            old_rep = int(pending)
            if old_rep in rep_subs:
                if _terminate_rep_sub(old_rep):
                    rep_lc.ack_cancel(old_rep)
                    _rep_lc_append_snapshot()

        if _opt7_make_before_break() and rep_lc.intended_rep not in (None, rep_lc.rendered_rep):
            # Prefetch overlap is allowed; do not invalidate the cell.
            pass
        elif rep_lc.overlap_violation:
            fault_path = os.path.join(
                os.environ.get("SIGCOMM_CELL_LOG_PATH", "/tmp"),
                "REP_OVERLAP_VIOLATION.json",
            )
            try:
                with open(fault_path, "w") as ff:
                    json.dump(
                        {
                            "ts": time.time(),
                            "host_id": a.host_id,
                            "snapshot": snap,
                            "invalidate_cell": True,
                        },
                        ff,
                    )
            except Exception as exc:
                print(
                    f"[WARN] h{a.host_id}: REP_OVERLAP_VIOLATION write failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )


    # ✅ Base Enhanced decision
    # / decision Enhanced
    # decision buffer/stall/
    print(f"[DEBUG] h{a.host_id}: [ ] Base Enhanced decision ...", file=sys.stderr, flush=True)
    
    # ✅ Enhanced 1-2 enhanced enhanced3
    # decision = 1: base{base_version}_enhanced1 ( )
    # decision = 2: base{base_version}_enhanced2 ( )
    # ✅ 9 enhanced3 decision 2
    # ✅ base_version broadcast name
    enh_dump_files = {}  # {1: dump_file1, 2: dump_file2}
    enh_log_files = {}   # {1: log_file1, 2: log_file2}
    enh_latency_log_files = {}  # {1: latency_log1, 2: latency_log2}
    enh_track_name = "video0"
    if (os.environ.get("TON_TRUE_CONTENT_LAYERING") or "").strip().lower() in ("1", "true", "yes", "on"):
        enh_broadcast_names = {1: f"base{base_version}_enh1_only", 2: f"base{base_version}_enh2_only"}
    else:
        enh_broadcast_names = {1: f"base{base_version}_enhanced1", 2: f"base{base_version}_enhanced2"}
    enh_processes = {}
    enh_readers = {}
    enh_sub_start_times = {}  # {1: start_time1, 2: start_time2}
    enh_start_times = {}      # {1: start_time1, 2: start_time2}
    last_decision = 0
    
    # enhanced
    for i in [1, 2, 3]:
        enh_dump_files[i] = f"/tmp/moq_h{a.host_id}_enh{i}.bin"
        enh_log_files[i] = gst_log.replace(".log", f"_enh{i}.log")
        enh_latency_log_files[i] = f"/tmp/moq_latency_h{a.host_id}_enhanced{i}.log"
    
    # Base
    print(f"[DEBUG] h{a.host_id}: Base 2 ...", file=sys.stderr, flush=True)
    time.sleep(2)
    
    start = time.time()
    enh_on = False
    iteration = 0
    
    # rebuffer
    stall_total_sec = 0.0
    stall_count = 0
    last_debug_size = [0]
    # ✅ stall
    last_stall_total_sec = 0.0
    stall_inc_smooth = 0.0
    
    # ✅ Stall
    prev_in_stall = False
    
    # ✅ Buffer Level
    buffer_level_sec = 0.0 if _metric_v4_timeline_enabled() else 5.0
    _metric_v4 = _metric_v4_timeline_enabled()
    if _metric_v4:
        run_client.media_events = []
        run_client.media_timeline_end_sec = 0.0
        run_client.payload_ttfb_ms = None
        run_client.media_covered_sec = 0.0
        run_client._v4_stall_interval_count = 0
    last_buffer_bytes = 0
    last_buffer_update_time = None
    last_total_bitrate_bps = None
    last_decision = 0
    
    # ✅ Delay EMA DASH
    last_delay_ms = None
    
    # ✅ iperf
    # ❌ last_check_time = time.time() if last_check_time <= 0:
    # ✅ last_check_time = 0.0 1
    # ✅ last_total_bytes rx_bytes
    last_check_time = 0.0
    Bu = 0.0
    if _PlayCapEst is not None and not hasattr(run_client, "_gen3_cap_est"):
        run_client._gen3_cap_est = _PlayCapEst(alpha=0.35, init_mbps=1.0)
    if not hasattr(run_client, "_stall_started_ts"):
        run_client._stall_started_ts = None
    if not hasattr(run_client, "_last_playable_ts"):
        run_client._last_playable_ts = None
    if not hasattr(run_client, "_last_switch_ts"):
        run_client._last_switch_ts = start
    if not hasattr(run_client, "_last_rep_for_switch"):
        run_client._last_rep_for_switch = None
    # ✅ delta_bytes=0
    zero_delta_count = 0
    MAX_ZERO_DELTA_COUNT = 3
    # ✅ enh_dump_file 921
    
    if not hasattr(run_client, 'sub_start_time'):
        run_client.sub_start_time = start
    
    # " host "
    _ensure_client_state_dir()
    client_state_file = _client_state_file(a.host_id)
    try:
        # ✅ throughput 0.0
        # sample_bandwidth B_MAX_BY_NETWORK
        if a.network_type in B_MAX_BY_NETWORK:
            initial_throughput = B_MAX_BY_NETWORK[a.network_type] * 0.3
        else:
            # sample_bandwidth
            initial_throughput = sample_bandwidth(a.network_type) if a.network_type else 10.0
        # ✅ throughput 1 Mbps base3 0.87Mbps
        initial_throughput = max(initial_throughput, 1.0)
        
        initial_state = {
            "host_id": a.host_id,
            "network_type": a.network_type,
            "throughput_mbps": initial_throughput,
            "delay_ms": 50.0,
            "device_score": float(a.device_score),
            "last_decision_layer": 0,
            "reward_R_o": 0.0,
            "reward_R_q": 0.0,
            "reward_R_b": 0.0,
            "reward_final": 0.0,
            "timestamp": time.time(),
            "viewpoint": "front_center"
        }
        temp_file = f"{client_state_file}.tmp"
        with open(temp_file, 'w') as sf:
            json.dump(initial_state, sf)
            sf.flush()
            os.fsync(sf.fileno())
        os.rename(temp_file, client_state_file)
        os.chmod(client_state_file, 0o666)
        print(f"[DEBUG] h{a.host_id}: ✅ : {client_state_file} ( )", file=sys.stderr, flush=True)
        if os.path.exists(client_state_file):
            file_size = os.path.getsize(client_state_file)
            print(f"[DEBUG] h{a.host_id}: ✅ : {file_size} ", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[WARN] h{a.host_id}: : {e}", file=sys.stderr, flush=True)

    perf_log_file = open(perf_log, "a", buffering=1)  # ✅ line buffered
    perf_csv_file = open(perf_csv, "a", buffering=1)
    
    try:
        print(f"[DEBUG] h{a.host_id}: ", file=sys.stderr, flush=True)
        while time.time() - start < a.duration - 5:

            # ✅ base
            # 3 host_id % 3
            # Base
            # - base3
            # - base1
            # ✅ PPO Controller
            user_group = None
            decision_data = None
            try:
                if os.path.exists(a.decision_file):
                    with open(a.decision_file, 'r') as f:
                        decision_data = json.load(f)
                    if 'decisions' in decision_data and str(a.host_id) in decision_data['decisions']:
                        user_decision = decision_data['decisions'][str(a.host_id)]
                        group_id_from_controller = user_decision.get('md2g_group_id')
                        if group_id_from_controller is not None:
                            user_group = int(group_id_from_controller) + 1
            except Exception as e:
                print(f"[WARN] h{a.host_id}: : {e}", file=sys.stderr, flush=True)
            
            # Fallback
            if user_group is None:
                user_group = (a.host_id - 1) % 3 + 1
                print(f"[WARN] h{a.host_id}: fallback : group={user_group}", file=sys.stderr, flush=True)
            
            # ✅ base 10
            # base
            # base
            if not _ton_gen3_probe_arm() and iteration % 10 == 0:
                # base
                # ✅ decision_data
                recommended_base_version = select_base_version_by_group_minimum(a.host_id, user_group, a.clients, decision_data)
                if not hasattr(run_client, 'current_base_version'):
                    run_client.current_base_version = recommended_base_version
                elif recommended_base_version != run_client.current_base_version:
                    # base
                    print(f"[INFO] h{a.host_id}: Group {user_group} base : base{recommended_base_version} ( : base{run_client.current_base_version})", file=sys.stderr, flush=True)
            elif not _ton_gen3_probe_arm():
                # base_version
                if not hasattr(run_client, 'current_base_version'):
                    # ✅ decision_data
                    run_client.current_base_version = select_base_version_by_group_minimum(a.host_id, user_group, a.clients, decision_data)
            elif not hasattr(run_client, 'current_base_version'):
                run_client.current_base_version = 3

            # ✅ buffer<threshold Base3
            # Metric V4 media object media_covered_sec>=1s
            # command123: probe arms forbid independent dispatch demotion.
            current_buffer = buffer_level_sec if iteration > 0 else 5.0
            _payload_ttfb = getattr(run_client, "payload_ttfb_ms", None)
            _media_covered = float(getattr(run_client, "media_covered_sec", 0.0))
            if _ton_gen3_probe_arm():
                _buf_block, BUFFER_PROTECTION_THRESHOLD = False, 0.0
            else:
                _buf_block, BUFFER_PROTECTION_THRESHOLD = _buffer_protection_blocks_enhanced(
                    current_buffer,
                    payload_ttfb_ms=_payload_ttfb,
                    media_covered_sec=_media_covered,
                )
            
            # base
            base_version = run_client.current_base_version
            
            # Early pre-decision demotion: skip under native9 scientific gate so ONE
            # common post-honor rule (_buffer_protection_demote_to_base3) applies
            # identically for md2g_g2 / g2_rule / hv3_native9 / clustering_native9.
            if _buf_block and not _sigcomm_native9rep_decision_enabled():
                if base_version < 3:
                    old_base_version = base_version
                    base_version = 3
                    run_client.current_base_version = 3
                    if iteration % 10 == 0:
                        print(
                            f"[BUFFER-PROTECTION] h{a.host_id}: buffer={current_buffer:.2f}s < "
                            f"{BUFFER_PROTECTION_THRESHOLD}s, Base3"
                            f" : base{old_base_version}; legacy_pre_decision ",
                            file=sys.stderr,
                            flush=True,
                        )
            
            # Scientific path: resolve_rep_bitrate_mbps (env/content). Legacy fail-open
            # RB table lives only inside resolve_rep_bitrate_mbps.
            try:
                base_rate = float(resolve_rep_bitrate_mbps(int(base_version)))
            except Exception:
                # LEGACY_NON_SCIENTIFIC_RB_HARDCODE fail-open only when resolve raises.
                base_rate = {1: 3.07, 2: 1.79, 3: 0.87}.get(int(base_version), 0.87)
            
            # ✅ enhanced
            # - decision = 0: enhanced
            # - decision = 1: 1 enhanced enhanced1, 1.0 Mbps
            # - decision = 2: 2 enhanced enhanced1 + enhanced2, 1.8 Mbps
            # ✅ 9 enhanced3 decision 2
            decision = 0
            # ✅ MD2G, Rolling, Heuristic, Clustering, GROOT r1/r2
            # controller r1/r2 DASH
            target_relay_ip = relay_ip
            base_bitrate_level = base_version - 1  # 0=base1, 1=base2, 2=base3

            # ✅ 3 + 20 Base
            # " " Base Enhanced
            elapsed_time = time.time() - start
            INITIAL_PROBE_DURATION = _initial_probe_duration_s()
            
            _scripted_mt = (
                _true_content_layering()
                and os.environ.get("COMMAND135_SCRIPTED_MICROTEST", "").strip().lower()
                in ("1", "true", "yes", "on")
            )
            _b3_only = os.environ.get("COMMAND137_B3_ONLY", "").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            if _b3_only:
                base_version = 3
                decision = 0
                run_client.current_base_version = 3
                if iteration % 10 == 0:
                    print(
                        f"[RATE-FEAS] h{a.host_id}: B3-only sentinel (no controller credit)",
                        file=sys.stderr,
                        flush=True,
                    )
            elif elapsed_time < INITIAL_PROBE_DURATION:
                # ✅ decision=0 Base
                # Enhanced enh_p decision=1
                decision = 0
                if iteration % 10 == 0:
                    print(f"[ 3] h{a.host_id}: {elapsed_time:.1f}s/{INITIAL_PROBE_DURATION}s Base Enhanced ", 
                          file=sys.stderr, flush=True)
            elif _scripted_mt:
                _script = [(3, 0), (3, 1), (3, 2), (2, 1), (1, 2), (1, 0)]
                _dwell = float(os.environ.get("COMMAND135_SCRIPTED_DWELL_S", "8"))
                _idx = min(
                    int((elapsed_time - INITIAL_PROBE_DURATION) / max(_dwell, 0.1)),
                    len(_script) - 1,
                )
                base_version, decision = _script[_idx]
                run_client.current_base_version = int(base_version)
                if iteration % 5 == 0:
                    print(
                        f"[LAYERED-SCRIPT] h{a.host_id}: step={_idx} "
                        f"base={base_version} depth={decision}",
                        file=sys.stderr,
                        flush=True,
                    )
            else:
                pass

            # ✅ Rolling
            # Rolling r1/r2 SC-DDQN
            decision_data = None
            # ==============================================================================
            # 
            # 1. {"decisions": {"1": {"pull_enhanced": bool, ...}, ...}}
            # 2. {"layers": [0, 1, 0, ...]}
            # 
            # Controller
            # - MD2G: regional_relay_controller.py → /tmp/r1_decisions.json /tmp/r2_decisions.json
            # - Rolling: regional_relay_controller.py → /tmp/r1_decisions.json /tmp/r2_decisions.json ( SC-DDQN )
            # - Heuristic: heuristic_controller_v2_refined.py → /tmp/r0_decisions.json (layers )
            # - Clustering: predictive_controller_v2_refined.py → /tmp/r0_decisions.json (layers )
            # - Groot: groot_controller.py → /tmp/r1_decisions.json /tmp/r2_decisions.json (decisions )
            # - Pano: pano_controller.py → /tmp/r0_decisions.json (decisions )
            # ==============================================================================
            if a.strategy in ["md2g", "rolling", "heuristic", "clustering", "groot", "pano"]:
                max_retries = 10
                retry_interval = 0.5
                for retry in range(max_retries):
                    try:
                        if os.path.exists(a.decision_file):
                            with open(a.decision_file, 'r') as df:
                                decision_data = json.load(df)
                            break
                        else:
                            if retry == 0:
                                print(f"[DEBUG] h{a.host_id}: Decision file not found: {a.decision_file}, waiting...", file=sys.stderr, flush=True)
                            time.sleep(retry_interval)
                    except (IOError, json.JSONDecodeError) as e:
                        if retry < max_retries - 1:
                            time.sleep(retry_interval)
                            continue
                        else:
                            print(f"[DEBUG] h{a.host_id}: Failed to read decision file {a.decision_file}: {e}", file=sys.stderr, flush=True)
                            decision_data = None
                            break
                
                if decision_data and not _scripted_mt and not _b3_only:
                    try:
                        # ==============================================================================
                        # ==============================================================================
                        # decisions[user_id] = {
                        #   "pull_enhanced": bool,
                        #   "target_relay_ip": str,
                        #   "base_bitrate_level": int
                        # }
                        # ==============================================================================
                        # ✅ 3 + Controller
                        # decision=0
                        if elapsed_time >= INITIAL_PROBE_DURATION:
                            if 'decisions' in decision_data and str(a.host_id) in decision_data['decisions']:
                                user_decision = decision_data['decisions'][str(a.host_id)]
                                # ✅ PPO pull_enhanced 0/1 enh_level 0/1/2
                                # pull_enhanced[u]: PPO 0/1
                                # enh_level[u]: 0/1/2 pull_enhanced
                                #
                                # command113/124 fidelity: when SIGCOMM_NATIVE9REP_DECISION
                                # (or legacy TON_NATIVE9REP_MD2G alias) is on and the
                                # controller wrote selected_rep / base_version+enhanced_level,
                                # honor that selection instead of group-min base + client-side
                                # bandwidth remapping (which re-locks base-only upgrades to Rep3).

                                _native_honored = False
                                _probe_arm = _ton_gen3_probe_arm()
                                _ctrl_sel_rep = user_decision.get(
                                    "selected_rep", user_decision.get("rep_id")
                                )
                                if _sigcomm_native9rep_decision_enabled() or _probe_arm:
                                    try:
                                        _sel = _ctrl_sel_rep
                                        _bv = user_decision.get("base_version")
                                        _el = user_decision.get(
                                            "enhanced_level", user_decision.get("enh_level")
                                        )
                                        if _bv is not None and _el is not None:
                                            base_version = int(_bv)
                                            enh_level = int(_el)
                                        elif _sel is not None:
                                            base_version, enh_level = _rep_to_base_enh(int(_sel))
                                        else:
                                            base_version = None  # type: ignore
                                            enh_level = None  # type: ignore
                                        if base_version is not None and enh_level is not None:
                                            run_client.current_base_version = int(base_version)
                                            base_rate = float(
                                                resolve_rep_bitrate_mbps(int(base_version))
                                            )
                                            pull_enhanced = 1 if int(enh_level) > 0 else 0
                                            decision = int(enh_level)
                                            _native_honored = True
                                            if iteration % 10 == 0:
                                                print(
                                                    f"[Client] h{a.host_id}: NATIVE9REP honor "
                                                    f"selected_rep={user_decision.get('selected_rep')} "
                                                    f"base={base_version} enh={enh_level} "
                                                    f"seq={user_decision.get('actuation_decision_seq')} "
                                                    f"rep_id={map_to_rep_id(base_version, decision)}",
                                                    file=sys.stderr,
                                                    flush=True,
                                                )
                                    except (TypeError, ValueError, KeyError, RuntimeError) as _ne:
                                        if iteration % 10 == 0:
                                            print(
                                                f"[WARN] h{a.host_id}: native9rep honor failed: {_ne}",
                                                file=sys.stderr,
                                                flush=True,
                                            )
                                        _native_honored = False

                                if _probe_arm and not _native_honored:
                                    # Fail closed: never independently open a secondary.
                                    pull_enhanced = 0
                                    enh_level = 0
                                    decision = 0
                                    base_version = 3
                                    run_client.current_base_version = 3
                                    print(
                                        f"[ACTUATION-PLAN] h{a.host_id}: missing plan selected_rep; HOLD base3",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                                elif not _native_honored:
                                    pull_enhanced = 1 if user_decision.get('pull_enhanced', False) else 0
                                    # O1-H5: MD2G-only action projection. Do not apply to HV3/Clustering/Rule.
                                    if (
                                        _true_content_layering()
                                        and os.environ.get("MD2G_LAYERED_HEADROOM_ENH_PROJECTION", "").strip().lower()
                                        in ("1", "true", "yes", "on")
                                        and str(os.environ.get("TON_STRATEGY_FINGERPRINT") or "").startswith("MD2G")
                                        and pull_enhanced == 0
                                    ):
                                        try:
                                            _hr = max(0.0, float(Bu) - float(base_rate)) if Bu else 0.0
                                            _min_hr = float(os.environ.get("MD2G_LAYERED_ENH_MIN_HEADROOM_MBPS", "0.25") or 0.25)
                                            _buf = float(buffer_level_sec if iteration > 0 else 5.0)
                                            _min_buf = float(os.environ.get("MD2G_LAYERED_ENH_MIN_BUFFER_SEC", "1.0") or 1.0)
                                            if _hr >= _min_hr and _buf >= _min_buf:
                                                pull_enhanced = 1
                                                if iteration % 10 == 0:
                                                    print(
                                                        f"[O1-H5] h{a.host_id}: project pull_enhanced=1 "
                                                        f"headroom={_hr:.3f}Mbps buf={_buf:.2f}s",
                                                        file=sys.stderr,
                                                        flush=True,
                                                    )
                                        except Exception:
                                            pass
                                    
                                    # ✅ buffer enhanced
                                    current_buffer = buffer_level_sec if iteration > 0 else 5.0
                                    _payload_ttfb = getattr(run_client, "payload_ttfb_ms", None)
                                    _media_covered = float(getattr(run_client, "media_covered_sec", 0.0))
                                    _buf_block, BUFFER_PROTECTION_THRESHOLD = _buffer_protection_blocks_enhanced(
                                        current_buffer,
                                        payload_ttfb_ms=_payload_ttfb,
                                        media_covered_sec=_media_covered,
                                    )
                                    
                                    if _buf_block:
                                        # enhanced
                                        pull_enhanced = 0
                                        enh_level = 0
                                        if _md2g_h10_enabled():
                                            run_client._h10_applied = 0
                                            run_client._h10_since = time.time()
                                            run_client._h10_pending = None
                                        if _md2g_h6_sticky_enabled():
                                            run_client._h6_depth = 0
                                            run_client._h6_since = time.time()
                                        if iteration % 10 == 0:
                                            print(f"[BUFFER-PROTECTION] h{a.host_id}: buffer={current_buffer:.2f}s < {BUFFER_PROTECTION_THRESHOLD}s, "
                                                  f" enhanced : pull_enhanced={user_decision.get('pull_enhanced', False)} ", 
                                                  file=sys.stderr, flush=True)
                                    elif _md2g_h6_sticky_enabled() and not _md2g_h6_filter_h5_enabled() and not _md2g_h10_enabled():
                                        enh_level = _md2g_h6_apply(run_client, Bu, base_rate, current_buffer)
                                        pull_enhanced = 1 if int(enh_level) > 0 else 0
                                        if iteration % 10 == 0:
                                            print(
                                                f"[O1-H6] h{a.host_id}: sticky enh_level={enh_level} "
                                                f"buf={current_buffer:.2f}s",
                                                file=sys.stderr,
                                                flush=True,
                                            )
                                    else:
                                        # ✅ enh_level pull_enhanced=1 bandwidth_headroom level
                                        enh_level = 0
                                        if pull_enhanced == 1:
                                            bandwidth_headroom = max(0, Bu - base_rate) if Bu > 0 else 0
                                            THRESHOLD_LEVEL2 = 2.0  # Mbps
                                            MIN_BUFFER_LEVEL2 = 3.0
                                            
                                            if bandwidth_headroom >= THRESHOLD_LEVEL2 and current_buffer >= MIN_BUFFER_LEVEL2:
                                                enh_level = 2  # base+enh1+enh2
                                            else:
                                                enh_level = 1  # base+enh1
                                        # pull_enhanced=0 enh_level=0 base
                                        if _md2g_h10_enabled():
                                            _prop = int(enh_level)
                                            enh_level = _md2g_h10_apply(run_client, enh_level, current_buffer)
                                            pull_enhanced = 1 if int(enh_level) > 0 else 0
                                            if (
                                                iteration % 10 == 0
                                                or int(_prop) != int(enh_level)
                                                or getattr(run_client, "_h10_pending", None) is not None
                                            ):
                                                print(
                                                    f"[O1-H10] h{a.host_id}: proposed={_prop} "
                                                    f"applied={enh_level} pending={getattr(run_client, '_h10_pending', None)} "
                                                    f"buf={current_buffer:.2f}s held="
                                                    f"{time.time() - float(getattr(run_client, '_h10_since', time.time()) or time.time()):.2f}s",
                                                    file=sys.stderr,
                                                    flush=True,
                                                )
                                        elif _md2g_h6_filter_h5_enabled():
                                            _prop = int(enh_level)
                                            enh_level = _md2g_h6_filter_apply(run_client, enh_level, current_buffer)
                                            pull_enhanced = 1 if int(enh_level) > 0 else 0
                                            if iteration % 10 == 0:
                                                print(
                                                    f"[O1-H6F] h{a.host_id}: filter proposed={_prop} "
                                                    f"enh_level={enh_level} buf={current_buffer:.2f}s",
                                                    file=sys.stderr,
                                                    flush=True,
                                                )
                                    
                                    # decision enh_level rep_id
                                    decision = int(enh_level)
                                    
                                    if iteration % 10 == 0:
                                        print(f"[Client] h{a.host_id}: group_id={user_group}, base_version={base_version}, "
                                              f"pull_enhanced={pull_enhanced}, enh_level={enh_level}, rep_id={map_to_rep_id(base_version, decision)}", 
                                              file=sys.stderr, flush=True)
                                else:
                                    # Native path: common buffer-protection demotion for ALL
                                    # primary strategies (no strategy-specific demotion).
                                    # command123 probe arms must not independently demote.
                                    if not _ton_gen3_probe_arm():
                                        current_buffer = buffer_level_sec if iteration > 0 else 5.0
                                        _payload_ttfb = getattr(run_client, "payload_ttfb_ms", None)
                                        _media_covered = float(getattr(run_client, "media_covered_sec", 0.0))
                                        _buf_block, BUFFER_PROTECTION_THRESHOLD = _buffer_protection_blocks_enhanced(
                                            current_buffer,
                                            payload_ttfb_ms=_payload_ttfb,
                                            media_covered_sec=_media_covered,
                                        )
                                        if _buf_block and _opt4_structural():
                                            if iteration % 10 == 0:
                                                print(
                                                    f"[BUFFER-HOLD] h{a.host_id}: opt4 completion-first "
                                                    f"keep controller_selected_rep={_ctrl_sel_rep} "
                                                    f"(buffer={current_buffer:.2f}s < {BUFFER_PROTECTION_THRESHOLD}s; "
                                                    f"do not wipe to base3)",
                                                    file=sys.stderr,
                                                    flush=True,
                                                )
                                        elif _buf_block:
                                            _rendered_before = map_to_rep_id(
                                                int(base_version), int(decision)
                                            )
                                            base_version, enh_level, decision = (
                                                _buffer_protection_demote_to_base3(
                                                    host_id=int(a.host_id),
                                                    current_buffer=float(current_buffer),
                                                    threshold=float(BUFFER_PROTECTION_THRESHOLD),
                                                    controller_selected_rep=_ctrl_sel_rep,
                                                    rendered_rep_before=_rendered_before,
                                                    iteration=int(iteration),
                                                    reason="buffer_below_protection_threshold",
                                                )
                                            )
                                            pull_enhanced = 0
                                            run_client.current_base_version = 3
                                            try:
                                                base_rate = float(resolve_rep_bitrate_mbps(3))
                                            except Exception:
                                                base_rate = 0.87

                                # ✅ r1/r2 target_relay_ip
                                target_relay_ip = relay_ip
                                base_bitrate_level = user_decision.get('base_bitrate_level', 0)
                            elif 'layers' in decision_data:
                                # layers
                                # command60/61: robust coerce avoid KeyError on enh=3 and
                                # numpy/bool types that previously fell into silent Base.
                                layers = decision_data.get('layers') or []
                                idx = int(a.host_id) - 1
                                if isinstance(layers, (list, tuple)) and 0 <= idx < len(layers):
                                    try:
                                        raw_decision = int(layers[idx])
                                    except (TypeError, ValueError):
                                        raw_decision = 1 if bool(layers[idx]) else 0
                                    # pull_enhanced semantics: 0=base-only, 1=request enhanced
                                    # Map to enh_level 0/1/2 via bandwidth (max enh=2; no enh3).
                                    if raw_decision >= 1:
                                        enhanced_bitrates = {1: 1.0, 2: 1.8}
                                        available_bw = Bu if Bu > 0 else base_rate * 1.2
                                        decision = 0
                                        for num_enh in (2, 1):
                                            total_bitrate = base_rate + enhanced_bitrates[num_enh]
                                            if total_bitrate <= available_bw * 0.9:
                                                decision = num_enh
                                                break
                                        if decision == 0 and raw_decision >= 1:
                                            # Still request at least enh1 when controller said enhanced
                                            decision = 1
                                        if iteration % 10 == 0:
                                            print(
                                                f"[DEBUG] h{a.host_id}: layers→enh_level "
                                                f"raw={raw_decision} available_bw={available_bw:.2f}Mbps "
                                                f"base_rate={base_rate:.2f}Mbps decision={decision}",
                                                file=sys.stderr,
                                                flush=True,
                                            )
                                    else:
                                        decision = 0
                    except (KeyError, IndexError, TypeError, ValueError) as e:
                        # Fail-visible: do not silently pretend Base forever without a marker.
                        # Keep decision=0 for this tick but stamp parse fault for cell validity.
                        if iteration % 10 == 0:
                            print(f"[DEBUG] h{a.host_id}: Failed to parse decision data: {e}", file=sys.stderr, flush=True)
                        try:
                            fault_path = os.path.join(
                                os.environ.get("SIGCOMM_CELL_LOG_PATH", "/tmp"),
                                "DECISION_PARSE_FAULT.json",
                            )
                            with open(fault_path, "w") as ff:
                                json.dump(
                                    {
                                        "ts": time.time(),
                                        "host_id": a.host_id,
                                        "error": str(e),
                                        "invalidate_cell": True,
                                    },
                                    ff,
                                )
                        except Exception:
                            pass
                        decision_data = None
                
                # ==============================================================================
                # ⚠️ fallback
                # ==============================================================================
                # 2. MD2G PPO regional_relay_controller
                # 3. decision 0 enhanced
                # ==============================================================================
                # fallback Bu
                # ==============================================================================

            # ==============================================================================
            # ✅ Rolling SC-DDQN
            # ==============================================================================
            # Rolling

            # ==============================================================================
            # ==============================================================================
            # ✅ MD2G, Rolling, Heuristic, Clustering, GROOT r1/r2
            # relay_ip r1 r2
            target_relay_ip = relay_ip
            current_relay_ip = relay_ip
            print(f"[DEBUG] h{a.host_id}: {a.strategy} {relay_name} (relay_ip={relay_ip})", file=sys.stderr, flush=True)
            
            # 2. base_bitrate_level base
            # base_bitrate_level: 0=low, 1=medium, 2=high
            # level manifest representation
            # base_rate network_type
            
            # ==============================================================================
            # ==============================================================================
            if iteration % 10 == 0:
                print(f"[DEBUG] h{a.host_id}: Decision execution - "
                      f"pull_enhanced={decision}, target_relay={target_relay_ip}, "
                      f"base_bitrate_level={base_bitrate_level}, "
                      f"enh_on={enh_on}", 
                      file=sys.stderr, flush=True)

            # ✅ Rep subscription: COMMAND135 additive tracks XOR V2 exclusive native9 XOR legacy dual
            if _true_content_layering():
                enh_broadcast_names = {
                    1: f"base{base_version}_enh1_only",
                    2: f"base{base_version}_enh2_only",
                }
                prev_b = int(getattr(run_client, "_llc_base", base_version))
                prev_d = int(last_decision)
                cur_b = int(base_version)
                cur_d = int(decision)
                if prev_b != cur_b or prev_d != cur_d:
                    delta = same_family_delta(prev_b, prev_d, cur_b, cur_d)
                    if delta["cross_family"]:
                        print(
                            f"[LAYERED] h{a.host_id}: cross-family base{prev_b}d{prev_d} → "
                            f"base{cur_b}d{cur_d} start={delta['start']} stop={delta['stop']}",
                            file=sys.stderr,
                            flush=True,
                        )
                        for version in [1, 2]:
                            if version in enh_processes and enh_processes[version]:
                                try:
                                    if enh_readers.get(version):
                                        enh_readers[version].stop()
                                    enh_processes[version].terminate()
                                    enh_processes[version].wait(timeout=2)
                                except Exception:
                                    try:
                                        enh_processes[version].kill()
                                    except Exception:
                                        pass
                                enh_processes[version] = None
                        try:
                            if reader_base:
                                reader_base.stop()
                            if base_p:
                                base_p.terminate()
                                base_p.wait(timeout=2)
                        except Exception:
                            try:
                                if base_p:
                                    base_p.kill()
                            except Exception:
                                pass
                        base_broadcast_name = f"base{cur_b}"
                        broadcast_name = base_broadcast_name
                        sub_start_time = time.time()
                        base_cmd_wrapper = [
                            sys.executable,
                            latency_wrapper,
                            MOQ_SUB_PATH,
                            track_name,
                            track_url,
                            moq_dump_file,
                            gst_log,
                            latency_log_file,
                            str(sub_start_time),
                            broadcast_name,
                        ]
                        env_base = os.environ.copy()
                        env_base["MOQ_TLS_DISABLE_VERIFY"] = "1"
                        env_base["MOQ_TRANSPORT_IDLE_TIMEOUT"] = "1800s"
                        env_base["QUIC_IDLE_TIMEOUT"] = "1800s"
                        env_base["RUST_LOG"] = "info"
                        env_base["RUST_BACKTRACE"] = "1"
                        base_p = subprocess.Popen(
                            ["taskset", "-c", str(a.host_id % 32)] + base_cmd_wrapper,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            bufsize=0,
                            env=env_base,
                        )
                        base_start_time = time.time()
                        reader_base = DataDrainer(
                            base_p, "Base_Stream", gst_log, start_time_epoch=base_start_time
                        )
                        reader_base.start()
                    else:
                        if delta.get("base_restarts"):
                            raise RuntimeError(
                                f"enhancement-only transition restarted Base: {delta}"
                            )
                    target_enhanced_versions = list(range(1, cur_d + 1)) if cur_d > 0 else []
                    current_enhanced_versions = [
                        v for v in [1, 2] if v in enh_processes and enh_processes[v] is not None
                    ]
                    for version in current_enhanced_versions:
                        if version not in target_enhanced_versions:
                            print(
                                f"[LAYERED] h{a.host_id}: stop {enh_broadcast_names[version]}",
                                file=sys.stderr,
                                flush=True,
                            )
                            try:
                                if version in enh_readers and enh_readers[version]:
                                    enh_readers[version].stop()
                                if version in enh_processes and enh_processes[version]:
                                    enh_processes[version].terminate()
                                    enh_processes[version].wait(timeout=2)
                            except Exception as e:
                                print(
                                    f"[WARN] h{a.host_id}: stop enh{version}: {e}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                                try:
                                    if version in enh_processes and enh_processes[version]:
                                        enh_processes[version].kill()
                                except Exception:
                                    pass
                            enh_processes[version] = None
                            if version in enh_readers:
                                enh_readers[version] = None
                    for version in target_enhanced_versions:
                        if version not in enh_processes or enh_processes.get(version) is None:
                            enh_broadcast_name = enh_broadcast_names[version]
                            print(
                                f"[LAYERED] h{a.host_id}: start {enh_broadcast_name}",
                                file=sys.stderr,
                                flush=True,
                            )
                            enh_sub_start_times[version] = time.time()
                            enh_cmd_wrapper = [
                                sys.executable,
                                latency_wrapper,
                                MOQ_SUB_PATH,
                                enh_track_name,
                                track_url,
                                enh_dump_files[version],
                                enh_log_files[version],
                                enh_latency_log_files[version],
                                str(enh_sub_start_times[version]),
                                enh_broadcast_name,
                            ]
                            enh_cmd_wrapper = ["taskset", "-c", str(a.host_id % 32)] + enh_cmd_wrapper
                            env_enh = os.environ.copy()
                            env_enh["MOQ_TLS_DISABLE_VERIFY"] = "1"
                            env_enh["MOQ_TRANSPORT_IDLE_TIMEOUT"] = "1800s"
                            env_enh["QUIC_IDLE_TIMEOUT"] = "1800s"
                            env_enh["RUST_LOG"] = "info"
                            env_enh["RUST_BACKTRACE"] = "1"
                            enh_p = subprocess.Popen(
                                enh_cmd_wrapper,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                bufsize=0,
                                env=env_enh,
                            )
                            enh_processes[version] = enh_p
                            enh_start_times[version] = time.time()
                            enh_readers[version] = DataDrainer(
                                enh_p,
                                f"Enhanced{version}_Stream",
                                enh_log_files[version],
                                start_time_epoch=enh_start_times[version],
                            )
                            enh_readers[version].start()
                    last_decision = cur_d
                    run_client._llc_base = cur_b
                    enh_on = cur_d > 0
            elif rep_lc_v2:
                target_rep, need_switch = plan_transition(
                    rep_lc.rendered_rep, base_version, decision
                )
                # Common native9: enh-only last_decision missed base3→base2 switches.
                if (
                    decision != last_decision
                    or _ton_gen3_probe_arm()
                    or (need_switch and _common_native9_base_switch())
                ):
                    rep_lc.request_target(target_rep)
                    if target_rep == rep_lc.rendered_rep and rep_lc.steady_single_subscription() and not _ton_gen3_probe_arm():
                        if iteration % 10 == 0:
                            print(
                                f"[REP-LC-V2] h{a.host_id}: steady on rep{target_rep}, no-op",
                                file=sys.stderr,
                                flush=True,
                            )
                    elif need_switch or _ton_gen3_probe_arm():
                        try:
                            if _ton_gen3_probe_arm():
                                min_dwell = 0.0
                            else:
                                min_dwell = float(os.environ.get("SIGCOMM_REP_MIN_DWELL_S", "8"))
                        except ValueError:
                            min_dwell = 0.0 if _ton_gen3_probe_arm() else 8.0
                        last_sw = float(getattr(run_client, "_rep_last_switch_ts", 0.0) or 0.0)
                        _now = time.time()
                        if (
                            rep_lc.rendered_rep is not None
                            and last_sw > 0
                            and (_now - last_sw) < min_dwell
                        ):
                            print(
                                f"[REP-LC-V2] h{a.host_id}: dwell hold "
                                f"rep{rep_lc.rendered_rep} (want {target_rep}, "
                                f"left={min_dwell - (_now - last_sw):.1f}s)",
                                file=sys.stderr,
                                flush=True,
                            )
                        else:
                            skip_start = False
                            if (
                                _opt7_make_before_break()
                                and rep_lc.rendered_rep not in (None, target_rep)
                            ):
                                cap = 0.0
                                try:
                                    if "user_decision" in locals() and isinstance(user_decision, dict):
                                        cap = float(
                                            user_decision.get("access_capacity_mbps")
                                            or user_decision.get("throughput_mbps")
                                            or 0.0
                                        )
                                except (TypeError, ValueError):
                                    cap = 0.0
                                if cap <= 0:
                                    try:
                                        cap = float(getattr(run_client, "_last_bu", 0.0) or 0.0)
                                    except (TypeError, ValueError):
                                        cap = 0.0
                                try:
                                    br_old = float(resolve_rep_bitrate_mbps(int(rep_lc.rendered_rep)))
                                    br_new = float(resolve_rep_bitrate_mbps(int(target_rep)))
                                except Exception:
                                    br_old, br_new = 1.0, 1.0
                                if not _opt7_overlap_justified(
                                    rep_lc.rendered_rep, target_rep, cap, br_old, br_new
                                ):
                                    print(
                                        f"[OPT7-HANDOFF] h{a.host_id}: skip overlap "
                                        f"rep{rep_lc.rendered_rep}→{target_rep} cap={cap:.2f}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                                    skip_start = True
                            if not skip_start:
                                bcast = rep_to_broadcast(target_rep)
                                print(
                                    f"[REP-LC-V2] h{a.host_id}: decision→rep{target_rep} ({bcast})",
                                    file=sys.stderr,
                                    flush=True,
                                )
                                _start_rep_moq_sub(target_rep, bcast)
                                run_client._rep_last_switch_ts = _now
                            if _ton_gen3_probe_arm():
                                closed = []
                                for _rid in list(rep_subs):
                                    if int(_rid) != int(target_rep):
                                        closed.append(int(_rid))
                                        _terminate_rep_sub(int(_rid))
                                try:
                                    _lp = os.environ.get("SIGCOMM_CELL_LOG_PATH") or "/tmp"
                                    _apply_rec = {
                                        "record": "SUBSCRIPTION_APPLY",
                                        "t": time.time(),
                                        "host_id": a.host_id,
                                        "decision_seq": (user_decision.get("actuation_decision_seq")
                                                         if 'user_decision' in locals() else None),
                                        "plan_hash": (user_decision.get("actuation_plan_hash")
                                                      if 'user_decision' in locals() else None),
                                        "requested_open": [int(target_rep)],
                                        "requested_close": closed,
                                        "resulting_subscription_set": [int(x) for x in rep_subs],
                                        "broadcast": bcast,
                                    }
                                    with open(os.path.join(_lp, "actuation_subscription_apply.jsonl"), "a") as _sf:
                                        _sf.write(json.dumps(_apply_rec) + "\n")
                                except Exception:
                                    pass
                    last_decision = decision
                    _rep_lc_append_snapshot()
                enh_on = decision > 0
                if rep_lc.rendered_rep is not None:
                    current_rep_id = rep_lc.rendered_rep
            elif decision != last_decision:
                # enhanced
                target_enhanced_versions = list(range(1, decision + 1)) if decision > 0 else []
                current_enhanced_versions = [v for v in [1, 2] if v in enh_processes and enh_processes[v] is not None]
                
                # enhanced
                for version in current_enhanced_versions:
                    if version not in target_enhanced_versions:
                        print(f"[INFO] h{a.host_id}: Enhanced{version} ...", file=sys.stderr, flush=True)
                        try:
                            if version in enh_readers and enh_readers[version]:
                                enh_readers[version].stop()
                            if version in enh_processes and enh_processes[version]:
                                enh_processes[version].terminate()
                                enh_processes[version].wait(timeout=2)
                        except Exception as e:
                            print(f"[WARN] h{a.host_id}: Enhanced{version} : {e}", file=sys.stderr, flush=True)
                            try:
                                if version in enh_processes and enh_processes[version]:
                                    enh_processes[version].kill()
                            except:
                                pass
                        enh_processes[version] = None
                        if version in enh_readers:
                            enh_readers[version] = None
                
                # enhanced
                for version in target_enhanced_versions:
                    if version not in enh_processes or enh_processes.get(version) is None:
                        enh_broadcast_name = enh_broadcast_names.get(
                            version, f"base{base_version}_enhanced{version}"
                        )
                        print(f"[INFO] h{a.host_id}: Decision={decision} Enhanced{version} {enh_broadcast_name} ...", file=sys.stderr, flush=True)
                        enh_sub_start_times[version] = time.time()
                        enh_track_url = track_url
                        enh_cmd_wrapper = [
                            sys.executable,
                            latency_wrapper,
                            MOQ_SUB_PATH,
                            enh_track_name,
                            enh_track_url,
                            enh_dump_files[version],
                            enh_log_files[version],
                            enh_latency_log_files[version],
                            str(enh_sub_start_times[version]),
                            enh_broadcast_name,
                        ]
                        enh_cmd_wrapper = ["taskset", "-c", str(a.host_id % 32)] + enh_cmd_wrapper
                        
                        with open(enh_log_files[version], "a", errors="ignore") as enh_log:
                            enh_log.write(f"\n=== moq-sub {enh_broadcast_name} stream started at {time.strftime('%Y-%m-%d %H:%M:%S')} ( ) ===\n")
                            enh_log.write(f"Command: {' '.join(enh_cmd_wrapper)}\n\n")
                        
                        env_enh = os.environ.copy()
                        env_enh['MOQ_TLS_DISABLE_VERIFY'] = '1'
                        env_enh['MOQ_TRANSPORT_IDLE_TIMEOUT'] = '1800s'
                        env_enh['QUIC_IDLE_TIMEOUT'] = '1800s'
                        env_enh['RUST_LOG'] = 'info'
                        env_enh['RUST_BACKTRACE'] = '1'
                        
                        enh_p = subprocess.Popen(
                            enh_cmd_wrapper,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            bufsize=0,
                            env=env_enh
                        )
                        enh_processes[version] = enh_p
                        enh_start_times[version] = time.time()
                        enh_readers[version] = DataDrainer(enh_p, f"Enhanced{version}_Stream", enh_log_files[version], start_time_epoch=enh_start_times[version])
                        enh_readers[version].start()
                        print(f"[INFO] h{a.host_id}: ✅ Enhanced{version} moq-sub PID: {enh_p.pid} ", file=sys.stderr, flush=True)
                
                last_decision = decision
                enh_on = (decision > 0 and any(enh_processes.get(v) is not None for v in [1, 2]))

            # V2: maintain overlap/cancel even when decision unchanged
            if rep_lc_v2:
                _rep_lc_maintain()
            if instr_v2 is not None:
                _instr_v2_tick()

            # ==============================================================================
            # ✅ ( iperf)
            # ==============================================================================
            # dump
            # = (Δ * 8) / (Δ * 1e6) Mbps
            # ==============================================================================
            current_time = time.time()
            time_diff = current_time - last_check_time
            
            # ✅ rx_bytes /proc/net/dev
            # Linux os.path.getsize()
            # /proc/net/dev
            def get_real_rx_bytes():
                """ /proc/net/dev Namespace """
                try:
                    with open('/proc/net/dev', 'r') as f:
                        for line in f:
                            if 'eth0:' in line:
                                return int(line.split()[1])
                except (FileNotFoundError, IOError, ValueError, IndexError):
                    return 0
            
            # ✅ rx_bytes
            if iteration == 0:
                if not hasattr(run_client, 'initial_rx_bytes'):
                    run_client.initial_rx_bytes = get_real_rx_bytes()
                    last_rx_bytes = run_client.initial_rx_bytes
                else:
                    last_rx_bytes = run_client.initial_rx_bytes
            else:
                if not hasattr(run_client, 'last_rx_bytes'):
                    run_client.last_rx_bytes = run_client.initial_rx_bytes if hasattr(run_client, 'initial_rx_bytes') else get_real_rx_bytes()
                last_rx_bytes = run_client.last_rx_bytes
            
            # ✅ rx_bytes
            current_rx_bytes = get_real_rx_bytes()
            
            # ✅ delta_bytes = -
            if iteration == 0:
                delta_bytes = 0
                # ✅ Phase 0
                if not hasattr(run_client, 'prev_rx_bytes'):
                    run_client.prev_rx_bytes = current_rx_bytes
                if not hasattr(run_client, 'prev_buffer_level'):
                    run_client.prev_buffer_level = 5.0
                if not hasattr(run_client, 'prev_rep_id'):
                    run_client.prev_rep_id = None
                if not hasattr(run_client, 'rx_bytes_stall_count'):
                    run_client.rx_bytes_stall_count = 0
            else:
                delta_bytes = current_rx_bytes - last_rx_bytes
                # ✅ delta_bytes < 0 0
                if delta_bytes < 0:
                    if iteration % 20 == 0:
                        print(f"[WARN] h{a.host_id}: delta_bytes < 0 ({delta_bytes}), 0", file=sys.stderr, flush=True)
                    delta_bytes = 0
            
            # ✅ Phase 0 rx_bytes
            rx_bytes_growing = current_rx_bytes > run_client.prev_rx_bytes if hasattr(run_client, 'prev_rx_bytes') else True
            if not rx_bytes_growing:
                run_client.rx_bytes_stall_count += 1
            else:
                run_client.rx_bytes_stall_count = 0
            
            if iteration % 10 == 0:
                print(f"[DEBUG] h{a.host_id}: - time_diff={time_diff:.3f}s, delta_bytes={delta_bytes}, "
                      f"current_rx_bytes={current_rx_bytes}, last_rx_bytes={last_rx_bytes}, Bu={Bu:.4f}Mbps", file=sys.stderr, flush=True)
            
            # ✅ (Bu) rx_bytes
            # Bu = (delta_bytes * 8) / (time_diff * 1e6) (Mbps)
            if last_check_time <= 0:
                run_client.last_rx_bytes = current_rx_bytes
                last_check_time = current_time
                Bu = 0.0
            elif time_diff > 0.001:
                if delta_bytes > 0:
                    inst_bw = (delta_bytes * 8.0) / time_diff / 1e6
                    
                    # inst_bw 60M Cache Catch-up Bu
                    if inst_bw > 60.0:
                        inst_bw = Bu if Bu > 0 else 5.0
                        if iteration % 10 == 0:
                            print(f"[DEBUG] h{a.host_id}: ⚠️ {inst_bw:.2f} Mbps ", file=sys.stderr, flush=True)
                    
                    # ✅ EMA DASH 0.3 0.7
                    # inst_bw EMA
                    # DASH
                    Bu = 0.3 * Bu + 0.7 * inst_bw if Bu > 0 else inst_bw
                    zero_delta_count = 0
                elif delta_bytes == 0:
                    # ✅ delta_bytes == 0
                    # delta_bytes=0 0
                    zero_delta_count += 1
                    if zero_delta_count >= MAX_ZERO_DELTA_COUNT:
                        Bu = 0.0
                        if iteration % 10 == 0:
                            print(f"[DEBUG] h{a.host_id}: {zero_delta_count} delta_bytes=0 ", file=sys.stderr, flush=True)
                    else:
                        Bu = 0.95 * Bu
                        if iteration % 20 == 0:
                            print(f"[DEBUG] h{a.host_id}: delta_bytes=0 ( {zero_delta_count} ) {Bu:.2f}Mbps", file=sys.stderr, flush=True)
                else:
                    # delta_bytes < 0 0
                    Bu = 0.0
                    zero_delta_count = 0
                
                # ✅ delta_bytes
                run_client.last_rx_bytes = current_rx_bytes
                last_check_time = current_time
            else:
                # ✅ time_diff <= 0.001 last_check_time
                if time_diff > 0:
                    last_check_time = current_time
                    # last_rx_bytes delta_bytes
                    run_client.last_rx_bytes = current_rx_bytes
            
            # ✅ Buffer Level
            # buffer = buffer_prev + ( - ) /
            if last_buffer_update_time is not None:
                dt = current_time - last_buffer_update_time
            else:
                dt = a.interval
                last_buffer_update_time = current_time
            
            # ✅ rx_bytes buffer
            # ✅ delta_bytes
            # delta_bytes 2022
            if not hasattr(run_client, 'last_buffer_rx_bytes'):
                run_client.last_buffer_rx_bytes = run_client.initial_rx_bytes if hasattr(run_client, 'initial_rx_bytes') else current_rx_bytes
            
            if iteration == 0:
                # delta_rx_bytes = 0 buffer
                delta_rx_bytes = 0
                run_client.last_buffer_rx_bytes = current_rx_bytes
            else:
                # ✅ delta_bytes 2022
                # buffer
                delta_rx_bytes = delta_bytes
                # ✅ delta_rx_bytes < 0 0
                if delta_rx_bytes < 0:
                    if iteration % 20 == 0:
                        print(f"[WARN] h{a.host_id}: buffer delta_rx_bytes < 0 ({delta_rx_bytes}), 0", file=sys.stderr, flush=True)
                    delta_rx_bytes = 0
            
            # ✅ Relay
            # Relay :
            # - r1 5 : 27.86 Mbps → : 5.57 Mbps
            # - r2 5 : 22.57 Mbps → : 4.51 Mbps
            # - : 5.04 Mbps
            # 4.0-4.5 Mbps
            # base_rate_mbps=3.5 Mbps delivery (4.0-4.5M) > consumption (3.5M) buffer
            base_rate_mbps = 3.5
            enh_rate_mbps = 1.0
            # ✅ enhanced interval
            # size>0 " " " interval "
            # interval
            enh_receiving_data = False
            enh_delta_bytes = 0
            if rep_lc_v2 and decision > 0 and rep_lc is not None:
                rid = rep_lc.rendered_rep
                if rid is not None and rid in rep_subs and rid > 3:
                    dump_path = rep_subs[rid]["dump"]
                    attr_prev = f"rep{rid}_bytes_prev"
                    if not hasattr(run_client, attr_prev):
                        setattr(run_client, attr_prev, 0)
                    if os.path.exists(dump_path):
                        bytes_now = os.path.getsize(dump_path)
                        bytes_prev = getattr(run_client, attr_prev)
                        enh_delta_bytes = max(0, bytes_now - bytes_prev)
                        if enh_delta_bytes > 0:
                            enh_receiving_data = True
                            setattr(run_client, attr_prev, bytes_now)
            elif decision == 1 and enh_on and enh_p is not None:
                # ✅ decision==1 enh_p None enh_on True
                # ✅ enhanced
                # ✅ enhanced dump
                enh_bytes_total = 0
                last_enh_bytes = None
                for version in [1, 2, 3]:
                    if version in enh_processes and enh_processes[version] is not None:
                        attr_name_prev = f'enh{version}_bytes_prev'
                        if not hasattr(run_client, attr_name_prev):
                            setattr(run_client, attr_name_prev, 0)
                        # enhanced{version} dump
                        if os.path.exists(enh_dump_files[version]):
                            enh_bytes_now = os.path.getsize(enh_dump_files[version])
                            # ✅ interval
                            enh_bytes_prev = getattr(run_client, attr_name_prev)
                            enh_delta_bytes = max(0, enh_bytes_now - enh_bytes_prev)
                            enh_bytes_total += enh_delta_bytes
                            # ✅ interval >0
                            if enh_delta_bytes > 0:
                                enh_receiving_data = True
                                setattr(run_client, attr_name_prev, enh_bytes_now)
                            last_enh_bytes = enh_bytes_now
                # Never reference enh_bytes_now when no dump file existed (command40 hard-fail root cause).
                if last_enh_bytes is not None:
                    run_client.enh_bytes_prev = last_enh_bytes
                else:
                    run_client.enh_bytes_prev = 0
            else:
                # Enhanced
                if hasattr(run_client, 'enh_bytes_prev'):
                    delattr(run_client, 'enh_bytes_prev')
            
            # ✅ enhanced
            # enhanced
            current_bitrate_bps = (base_rate_mbps + (enh_rate_mbps if enh_receiving_data else 0)) * 1e6
            
            # ✅ Buffer " "
            # (B) buffer time_diff downloaded_play_sec
            # (C) stall buffer >0 0
            prev_buffer_level_sec = buffer_level_sec
            
            # ✅ PPO base_version enhanced_level rep_id
            # rep1-3: base only (base1, base2, base3)
            # rep4-6: base + enhanced1 (base1+enh1, base2+enh1, base3+enh1)
            # rep7-9: base + enhanced1+enhanced2 (base1+enh1+enh2, base2+enh1+enh2, base3+enh1+enh2)
            # 
            # Step 1: PPO → group_id[u]
            # Step 2: Base → base_group[g]
            # Step 3: Enhanced level PPO → enhanced_level[u] ∈ {0,1,2}
            # Step 4: rep_id V2: rendered rep; legacy: decision ladder
            if rep_lc_v2 and rep_lc is not None and rep_lc.rendered_rep is not None:
                rep_id = current_rep_id
            else:
                rep_id = map_to_rep_id(base_version, decision)
            
            # ✅ / content rep fail-closed command110
            total_mbps = resolve_playable_media_bitrate_mbps(base_version, decision, rep_id)
            total_bps = total_mbps * 1e6
            if iteration == 1 or not getattr(run_client, "_c138_bitrate_echoed", False):
                echo = {
                    "token": "COMMAND138_PLAYABLE_BITRATE",
                    "base_version": int(base_version),
                    "enh_depth": int(decision),
                    "rep_id": int(rep_id),
                    "playable_bitrate_mbps": float(total_mbps),
                    "source": (
                        "layered_subscribed_physical_sum"
                        if _true_content_layering()
                        else "resolve_rep_bitrate_mbps"
                    ),
                    "native9_legacy_rep3_mbps": 0.87,
                }
                try:
                    outp = os.path.join(a.log_path, "COMMAND138_PLAYABLE_BITRATE.json")
                    with open(outp, "w", encoding="utf-8") as _bf:
                        json.dump(echo, _bf, indent=2)
                        _bf.write("\n")
                    print(
                        f"[COMMAND138-DENOM] h{a.host_id}: {total_mbps:.6f} Mbps "
                        f"base={base_version} depth={decision} source={echo['source']}",
                        file=sys.stderr,
                        flush=True,
                    )
                    run_client._c138_bitrate_echoed = True
                except Exception as _be:
                    print(f"[COMMAND138-DENOM] write failed: {_be}", file=sys.stderr, flush=True)
            
            # ✅ time_diff interval
            # time_diff 0 interval
            actual_time_diff = time_diff if time_diff > 0.01 else a.interval
            
            if iteration > 0 and actual_time_diff > 0:
                if _metric_v4:
                    # Metric V4: buffer/stall from rendered-rep dump media timeline (not RX).
                    delta_dump_bytes = 0
                    dump_path = None
                    if rep_id in rep_subs:
                        dump_path = rep_subs[rep_id]["dump"]
                    elif os.path.exists(moq_dump_file):
                        dump_path = moq_dump_file
                    if dump_path and os.path.exists(dump_path):
                        bytes_now = os.path.getsize(dump_path)
                        attr_prev = f"media_dump_bytes_prev_{rep_id}"
                        if not hasattr(run_client, attr_prev):
                            setattr(
                                run_client,
                                attr_prev,
                                rep_sub_dump_sizes.get(rep_id, bytes_now),
                            )
                        bytes_prev = getattr(run_client, attr_prev)
                        delta_dump_bytes = max(0, bytes_now - bytes_prev)
                        setattr(run_client, attr_prev, bytes_now)
                        rep_sub_dump_sizes[rep_id] = bytes_now

                    if delta_dump_bytes > 0:
                        media_sec = (delta_dump_bytes * 8.0) / max(1.0, total_bps)
                        t_start = run_client.media_timeline_end_sec
                        t_end = t_start + media_sec
                        run_client.media_events.append(
                            {
                                "t_wall": current_time,
                                "t_media_start": t_start,
                                "t_media_end": t_end,
                                "rep_id": rep_id,
                                "bytes": delta_dump_bytes,
                            }
                        )
                        run_client.media_timeline_end_sec = t_end
                        if run_client.payload_ttfb_ms is None:
                            run_client.payload_ttfb_ms = v4_payload_ttfb_ms(current_time, start)

                    elapsed = current_time - start
                    buffer_level_sec, playhead, stalls = timeline_metrics_at(
                        run_client.media_events, elapsed
                    )
                    MAX_BUFFER_LIMIT = 60.0
                    buffer_level_sec = min(buffer_level_sec, MAX_BUFFER_LIMIT)
                    run_client.buffer_level_sec = buffer_level_sec
                    run_client.media_covered_sec = playhead
                    run_client._v4_timeline_stalls = stalls
                else:
                    # (A) legacy RX SIGCOMM_METRIC_V4_TIMELINE=0
                    downloaded_play_sec = (
                        (delta_rx_bytes * 8.0) / max(1.0, total_bps) if delta_rx_bytes > 0 else 0.0
                    )

                    # (B) buffer actual_time_diff downloaded_play_sec
                    buffer_level_sec = max(
                        0.0, buffer_level_sec + downloaded_play_sec - actual_time_diff
                    )

                    # ✅ Buffer buffer 30-60
                    MAX_BUFFER_LIMIT = 60.0
                    buffer_level_sec = min(buffer_level_sec, MAX_BUFFER_LIMIT)
                    # ✅ run_client
                    run_client.buffer_level_sec = buffer_level_sec

                    # (C) stall buffer >0 0
                    if prev_buffer_level_sec > 0.0 and buffer_level_sec == 0.0:
                        # 0 stall
                        if not hasattr(run_client, "stall_count_from_buffer"):
                            run_client.stall_count_from_buffer = 0
                        run_client.stall_count_from_buffer += 1
                        if iteration % 10 == 0:
                            print(
                                f"[DEBUG] h{a.host_id}: ⚠️ Buffer buffer "
                                f"buffer {prev_buffer_level_sec:.3f}s 0.0s",
                                file=sys.stderr,
                                flush=True,
                            )
            elif iteration == 0:
                # buffer
                pass
            
            run_client.last_buffer_rx_bytes = current_rx_bytes
            last_buffer_update_time = current_time
            
            # ✅ TTLB TTLB

            # --- interval ---
            # ✅ delay_ms " "
            # last_data_ts
            # TTFB / steady-state delay
            # ✅ last_data_ts delay_ms stall
            dly = None
            dly_valid = False
            
            if hasattr(reader_base, 'last_data_ts') and reader_base.last_data_ts is not None:
                data_arrival_interval_ms = (current_time - reader_base.last_data_ts) * 1000.0
                # ✅ 500ms EWMA
                if data_arrival_interval_ms > 500.0 and hasattr(reader_base, 'last_read_dt_ms') and reader_base.last_read_dt_ms is not None:
                    data_arrival_interval_ms = reader_base.last_read_dt_ms
                # ✅ 1ms 500ms DASH
                data_arrival_interval_ms = max(1.0, min(500.0, data_arrival_interval_ms))
                
                # ✅ EMA DASH 0.3 0.7
                # delay_ms " "
                if iteration == 1 or last_delay_ms is None:
                    dly = data_arrival_interval_ms
                else:
                    # ✅ EMA delay_ms = 0.3 * last_delay_ms + 0.7 * data_arrival_interval_ms
                    dly = 0.3 * last_delay_ms + 0.7 * data_arrival_interval_ms
                
                # ✅ last_delay_ms EMA
                last_delay_ms = dly
                dly_valid = True
            elif hasattr(reader_base, 'ttfb_ms') and reader_base.ttfb_ms is not None:
                # ✅ TTFB
                dly = reader_base.ttfb_ms
                # ✅ last_delay_ms
                if last_delay_ms is None:
                    last_delay_ms = dly
                dly_valid = False
            elif current_rx_bytes > (run_client.initial_rx_bytes if hasattr(run_client, 'initial_rx_bytes') else 0) and hasattr(run_client, 'sub_start_time'):
                data_arrival_interval_ms = (current_time - run_client.sub_start_time) * 1000.0
                data_arrival_interval_ms = max(1.0, min(500.0, data_arrival_interval_ms))
                
                # ✅ EMA DASH
                if iteration == 1 or last_delay_ms is None:
                    dly = data_arrival_interval_ms
                else:
                    dly = 0.3 * last_delay_ms + 0.7 * data_arrival_interval_ms
                
                # ✅ last_delay_ms
                last_delay_ms = dly
                dly_valid = False
            else:
                dly = 50.0
                # ✅ last_delay_ms
                if last_delay_ms is None:
                    last_delay_ms = dly
                dly_valid = False
                if iteration % 10 == 0:
                    print(f"[DEBUG] h{a.host_id}: ⏳ : {dly:.2f} ms", file=sys.stderr, flush=True)
            
            # ✅ Stall not in_stall in_stall stall_count_inc
            # ✅ Stall delay_ms > 500 buffer_level_sec <= 0 delay_ms
            # ✅ rx_bytes > 0 stall
            stall_count_inc = 0
            stall_sec_inc = 0.0

            if _metric_v4 and iteration > 0 and actual_time_diff > 0:
                stalls = getattr(run_client, "_v4_timeline_stalls", [])
                elapsed = current_time - start
                new_stall_total = sum(e - s for s, e in stalls)
                stall_sec_inc = max(0.0, new_stall_total - last_stall_total_sec)
                stall_total_sec = new_stall_total
                last_stall_total_sec = new_stall_total

                prev_count = run_client._v4_stall_interval_count
                if len(stalls) > prev_count:
                    stall_count_inc = len(stalls) - prev_count
                    stall_count += stall_count_inc
                run_client._v4_stall_interval_count = len(stalls)

                in_stall = any(s <= elapsed <= e + 0.001 for s, e in stalls)
                if not prev_in_stall and in_stall and iteration % 10 == 0:
                    print(
                        f"[DEBUG] h{a.host_id}: ⚠️ Metric V4 stall interval "
                        f"(buffer={buffer_level_sec:.3f}s)",
                        file=sys.stderr,
                        flush=True,
                    )
                prev_in_stall = in_stall
            else:
                # ✅ rx_bytes > 0 stall
                has_received_data = current_rx_bytes > (
                    run_client.initial_rx_bytes if hasattr(run_client, "initial_rx_bytes") else 0
                )

                if iteration > 0 and actual_time_diff > 0 and has_received_data:
                    # ✅ Stall delay_ms > 500 buffer_level_sec <= 0
                    in_stall = False

                    # 1 buffer_level_sec <= 0
                    if buffer_level_sec <= 0.0:
                        in_stall = True

                    # 2 delay_ms > 500 delay_ms
                    if dly_valid and dly is not None and dly > 500.0:
                        in_stall = True

                    # ✅ not in_stall in_stall stall_count_inc
                    if not prev_in_stall and in_stall:
                        # stall stall stall
                        stall_count_inc = 1
                        stall_count += stall_count_inc
                        if iteration % 10 == 0:
                            stall_reason = []
                            if buffer_level_sec <= 0.0:
                                stall_reason.append(f"buffer={buffer_level_sec:.3f}s")
                            if dly_valid and dly is not None and dly > 500.0:
                                stall_reason.append(f"delay={dly:.2f}ms")
                            print(
                                f"[DEBUG] h{a.host_id}: ⚠️ Stall {' & '.join(stall_reason)}, "
                                f"stall_count_inc={stall_count_inc}, stall_count={stall_count}",
                                file=sys.stderr,
                                flush=True,
                            )
                    elif prev_in_stall and not in_stall:
                        # stall stall
                        if iteration % 10 == 0:
                            print(
                                f"[DEBUG] h{a.host_id}: ✅ Stall "
                                f"buffer={buffer_level_sec:.3f}s, delay={dly:.2f}ms",
                                file=sys.stderr,
                                flush=True,
                            )

                    # ✅ Stall stall actual_time_diff
                    if in_stall:
                        stall_sec_inc = actual_time_diff
                        stall_total_sec += stall_sec_inc

                    # ✅ prev_in_stall
                    prev_in_stall = in_stall

                    # ✅ Phase 0 client " " " "
                    if iteration > 0:
                        rx_bytes_changed = current_rx_bytes != (
                            run_client.prev_rx_bytes
                            if hasattr(run_client, "prev_rx_bytes")
                            else current_rx_bytes
                        )
                        rx_bytes_delta = current_rx_bytes - (
                            run_client.prev_rx_bytes
                            if hasattr(run_client, "prev_rx_bytes")
                            else current_rx_bytes
                        )
                        buffer_stuck_at_zero = buffer_level_sec <= 0.0 and (
                            run_client.prev_buffer_level
                            if hasattr(run_client, "prev_buffer_level")
                            else 5.0
                        ) <= 0.0
                        rep_id_changed = rep_id != (
                            run_client.prev_rep_id if hasattr(run_client, "prev_rep_id") else None
                        )
                        in_stall_now = in_stall
                        should_print_diagnosis = (
                            iteration % 5 == 0
                            or not rx_bytes_changed
                            or buffer_stuck_at_zero
                            or rep_id_changed
                            or in_stall_now
                        )
                        if should_print_diagnosis:
                            diagnosis_status = []
                            if not rx_bytes_changed:
                                diagnosis_status.append(
                                    f"⚠️ rx_bytes ( {run_client.rx_bytes_stall_count} )"
                                )
                            else:
                                diagnosis_status.append(f"✅ rx_bytes +{rx_bytes_delta} ")
                            if buffer_stuck_at_zero:
                                diagnosis_status.append("⚠️ buffer 0")
                            elif buffer_level_sec <= 0.0:
                                diagnosis_status.append("⚠️ buffer=0( )")
                            else:
                                diagnosis_status.append(f"✅ buffer={buffer_level_sec:.3f}s")
                            if in_stall_now:
                                diagnosis_status.append("⚠️ stall ")
                            if rep_id_changed:
                                diagnosis_status.append(
                                    f"🔄 rep_id : {run_client.prev_rep_id}→{rep_id}"
                                )
                            else:
                                diagnosis_status.append(f"rep_id={rep_id}")
                            if not rx_bytes_changed and run_client.rx_bytes_stall_count >= 3:
                                conclusion = "🔴 rx_bytes "
                            elif buffer_stuck_at_zero and not rx_bytes_changed:
                                conclusion = (
                                    "🔴 + buffer 0 rx_bytes "
                                )
                            elif buffer_stuck_at_zero:
                                conclusion = "🟡 buffer 0 rx_bytes "
                            elif in_stall_now and Bu < 1.0:
                                conclusion = "🟡 stall Bu<1Mbps"
                            elif in_stall_now:
                                conclusion = "🟡 stall Bu "
                            else:
                                conclusion = "✅ "
                            print(
                                f"[Phase0-DIAGNOSIS] h{a.host_id}: iter={iteration}, "
                                f"rx_bytes={current_rx_bytes}(Δ={rx_bytes_delta:+d}), "
                                f"buffer={buffer_level_sec:.3f}s, rep_id={rep_id}, Bu={Bu:.2f}Mbps, "
                                f"{' | '.join(diagnosis_status)} | {conclusion}",
                                file=sys.stderr,
                                flush=True,
                            )

                    run_client.prev_rx_bytes = current_rx_bytes
                    run_client.prev_buffer_level = buffer_level_sec
                    run_client.prev_rep_id = rep_id

                    if not in_stall:
                        debug_log_path = os.path.join(a.log_path, f"client_h{a.host_id}_gst.log")
                        if os.path.exists(debug_log_path):
                            stall_sec_inc_gst, stall_cnt_inc_gst = parse_rebuffer_from_debug(
                                debug_log_path, last_debug_size
                            )
                            if stall_sec_inc_gst > 0 or stall_cnt_inc_gst > 0:
                                stall_total_sec += stall_sec_inc_gst
                                stall_count += stall_cnt_inc_gst
                                stall_count_inc = stall_cnt_inc_gst
                                if iteration % 10 == 0:
                                    print(
                                        f"[DEBUG] h{a.host_id}: ⚠️ GStreamer rebuffer "
                                        f"stall_sec_inc={stall_sec_inc_gst:.3f}s, "
                                        f"stall_count_inc={stall_cnt_inc_gst}, stall_count={stall_count}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                else:
                    # stall prev_in_stall
                    if iteration == 0:
                        prev_in_stall = False
                        if not hasattr(run_client, "prev_rx_bytes"):
                            run_client.prev_rx_bytes = current_rx_bytes
                        if not hasattr(run_client, "prev_buffer_level"):
                            run_client.prev_buffer_level = 5.0
                        if not hasattr(run_client, "prev_rep_id"):
                            run_client.prev_rep_id = None
                        if not hasattr(run_client, "rx_bytes_stall_count"):
                            run_client.rx_bytes_stall_count = 0

                    if iteration % 10 == 0:
                        print(
                            f"[Phase0-DIAGNOSIS] h{a.host_id}: iter={iteration}, "
                            f"rx_bytes={current_rx_bytes}, buffer={buffer_level_sec:.3f}s, "
                            f"rep_id={rep_id}, : ",
                            file=sys.stderr,
                            flush=True,
                        )

                    run_client.prev_rx_bytes = current_rx_bytes
                    run_client.prev_buffer_level = buffer_level_sec
                    run_client.prev_rep_id = rep_id
            
            # ✅ dly dly None
            if dly is None:
                dly = 50.0
            
            # ✅ buffer RTT
            if not hasattr(run_client, 'last_buffer_level'):
                run_client.last_buffer_level = buffer_level_sec
            run_client.last_buffer_level = buffer_level_sec
            
            # ✅ Ping
            # 1. Ping Mininet CPU
            # 2. Ping
            # 3. TTFB QoE
            # 
            # iface = nic_name(a.host_id)
            # server_ip = "10.0.1.100" # n0 IP
            # dly = ping_rtt(server_ip, iface=iface)
            # if dly < 0 or dly > 500:
            # print(f"[DEBUG] h{a.host_id} measured end-to-end delay (client→n0): {dly:.2f}ms for {a.network_type}", file=sys.stderr, flush=True)

            dev_score = float(a.device_score)
            dev = df_dev.sample(1).iloc[0]
            gpu = dev['GPU Clock (MHz)'] / df_dev['GPU Clock (MHz)'].max()
            ram = dev['RAM(GB)'] / df_dev['RAM(GB)'].max()
            refresh = dev['Refresh Rate (Hz)'] / df_dev['Refresh Rate (Hz)'].max()
            resolution_str = str(dev['Resolution (per eye)'])
            res_w = int(resolution_str.split('×')[0]) if '×' in resolution_str else 1920
            res = res_w / df_dev['Resolution (per eye)'].apply(
                lambda x: int(str(x).split('×')[0]) if '×' in str(x) else 1920
            ).max()

            Qr = min(1.2, max(0.2,
                (0.4 * dev_score + 0.3 * gpu + 0.2 * ram + 0.1 * refresh + 0.2 * res)
                * gpu_boost(gpu)
            ))

            # --- rebuffer ---
            debug_log_path = f"/tmp/client_logs/client_h{a.host_id}_gstdebug.log"
            stall_sec_inc, stall_cnt_inc = parse_rebuffer_from_debug(debug_log_path, last_debug_size)
            stall_total_sec += stall_sec_inc
            stall_count += stall_cnt_inc
            
            # relay
            # ⚠️ /fallback /tmp/relay_loads.json
            # fallback
            DEFAULT_OFF_LOADS = [0.9]
            DEFAULT_ON_LOADS = [0.2, 0.5, 0.8, 0.3]
            
            def read_relay_loads_from_json():
                """
                 /tmp/relay_loads.json relay 
                
                Returns:
                    list: relay None
                """
                try:
                    with open("/tmp/relay_loads.json", "r") as f:
                        data = json.load(f)
                        loads = data.get("loads", None)
                        
                        if not loads or not isinstance(loads, list) or len(loads) == 0:
                            raise ValueError("Invalid loads in JSON: empty or not a list")
                        
                        if not all(0.0 <= load <= 1.0 for load in loads):
                            raise ValueError("Invalid loads in JSON: values not in [0, 1]")
                        
                        return loads
                        
                except (IOError, json.JSONDecodeError, KeyError, ValueError) as e:
                    # None fallback
                    if iteration % 20 == 0:
                        print(f"[WARN] h{a.host_id}: Failed to read relay_loads.json: {e}", 
                              file=sys.stderr, flush=True)
                    return None
            
            # ==============================================================================
            # ✅ JFI ON relay_loads.json JFI
            # ==============================================================================
            if a.federation == 'on':
                # Federation ON: JFI
                relay_loads = read_relay_loads_from_json()
                
                if relay_loads and len(relay_loads) > 0:
                    valid_loads = [l for l in relay_loads if l >= 0.001]
                    if len(valid_loads) > 0:
                        load_balance_jfi = calculate_system_load_balance(valid_loads)
                        print(f"[JFI] h{a.host_id}: ON JFI={load_balance_jfi:.4f}, relay_loads={valid_loads}", 
                              file=sys.stderr, flush=True)
                    else:
                        # fallback
                        load_balance_jfi = 1.0
                        if iteration % 20 == 0:
                            print(f"[WARN] h{a.host_id}: ON fallback JFI=1.0", 
                                  file=sys.stderr, flush=True)
                else:
                    # fallback
                    load_balance_jfi = 1.0
                    if iteration % 20 == 0:
                        print(f"[WARN] h{a.host_id}: ON fallback JFI=1.0 (relay_loads.json )", 
                              file=sys.stderr, flush=True)
            else:
                # Federation OFF: relay JFI=1.0 QoE w_ln=0
                relay_loads = [0.8]
                load_balance_jfi = 1.0
            
            # QoE = w_r*Qr + w_b*Rb + w_ln*L_net - w_d*D - w_f*F
            Rq = 5.0 * (math.log1p(Qr) / math.log(2.5))
            
            network_b_max = B_MAX_BY_NETWORK.get(a.network_type, B_MAX)
            Rb = math.log1p(Bu) / math.log1p(network_b_max + EPS)
            delay_penalty = dly / 200.0
            rebuffer_penalty = min(1.0, stall_count * 0.1)
            
            # ==============================================================================
            # ==============================================================================
            # R_o: Grouping Efficiency
            # R_q: User Perceived Quality
            # R_b: Bandwidth Efficiency Penalty
            # ==============================================================================
            
            lambda_o, lambda_q, lambda_b = _parse_reward_lambdas_from_env()
            
            # --- R_q ---
            # SIGCOMM paper Eq.9: R_q = α Q_s − β D_n − γ S_n with α=1, β=γ=0.5,
            # Q_s ∈ {0.4,0.6,0.8,1.0} ↔ Q1–Q4. Enable with SIGCOMM_QOE_EQ9=1.
            # Default remains MM26 five-component for legacy callers.
            _use_eq9 = os.environ.get("SIGCOMM_QOE_EQ9", "").strip().lower() in ("1", "true", "yes", "on")
            if _use_eq9:
                # Table 1: final executed Rep ID → Q_s (Q1=0.4 Q4=1.0). Never MM26 shortcut.
                _REP_TO_QS = {
                    1: 0.8, 2: 0.6, 3: 0.4,  # Q3, Q2, Q1
                    4: 1.0, 5: 1.0,          # Q4
                    6: 0.6, 7: 0.8,          # Q2, Q3
                    8: 0.4, 9: 0.4,          # Q1
                }
                try:
                    _rid = int(map_to_rep_id(base_version, decision))
                except Exception:
                    _rid = int(base_version) if str(base_version).isdigit() else 3
                Q_s = float(_REP_TO_QS.get(_rid, 0.4))
                D_n = min(dly / 200.0, 1.0) if dly > 0 else 0.0
                S_n = 1.0 - np.exp(-stall_total_sec / 3.0) if stall_total_sec > 0 else 0.0
                alpha_q, beta_q, gamma_q = 1.0, 0.5, 0.5
                R_q = alpha_q * float(Q_s) - beta_q * float(D_n) - gamma_q * float(S_n)
                R_q = max(0.0, min(1.0, float(R_q)))
                q_delay = max(0.0, 1.0 - D_n)
                q_stall = max(0.0, 1.0 - S_n)
                q_quality = float(Q_s)
                q_system = max(0.0, min(1.0, Bu / max(1e-6, network_b_max)))
                q_stability = 1.0
                qs_mm26 = float(Q_s)
            else:
                # MM26 QoE MM26/dispatch_strategy_enhanced_unified_NOSSDAV.py
                qs_mm26 = float(min(1.0, 0.6 + 0.4 * (float(decision) / 2.0)))
                delay_norm = min(dly / 200.0, 1.0) if dly > 0 else 0.0
                stall_norm = 1.0 - np.exp(-stall_total_sec / 3.0) if stall_total_sec > 0 else 0.0

                q_delay = max(0.0, 1.0 - delay_norm)
                q_stall = max(0.0, 1.0 - stall_norm)
                q_quality = max(0.0, min(1.0, (qs_mm26 - 0.6) / 0.4))
                q_system = max(0.0, min(1.0, Bu / max(1e-6, network_b_max)))

                q_pre = (
                    0.35 * q_delay
                    + 0.30 * q_stall
                    + 0.20 * q_quality
                    + 0.15 * q_system
                )
                qoe_window.append(float(q_pre))
                if len(qoe_window) >= 3:
                    q_std = float(np.std(list(qoe_window)))
                    q_stability = max(0.0, 1.0 - min(q_std, QOE_STABILITY_STD_CAP) / QOE_STABILITY_STD_CAP)
                else:
                    q_stability = 1.0

                R_q = (
                    QOE_WEIGHTS["delay"] * q_delay
                    + QOE_WEIGHTS["stall"] * q_stall
                    + QOE_WEIGHTS["stability"] * q_stability
                    + QOE_WEIGHTS["quality"] * q_quality
                    + QOE_WEIGHTS["system"] * q_system
                )
                R_q = max(0.0, min(1.0, R_q))
                try:
                    _gscale = float(os.environ.get("MM26_REWARD_RQ_GLOBAL_SCALE", "1.0"))
                except ValueError:
                    _gscale = 1.0
                _gscale = max(0.5, min(1.5, _gscale))
                R_q = max(0.0, min(1.0, R_q * _gscale))
            
            # --- R_o: Grouping Efficiency ---
            grouping_id = a.host_id
            grouping_size = 1
            
            # ✅ FOV relay Base
            # r1 grouping_id=1 r2 grouping_id=2
            # Base
            r1_sub_count = a.clients // 2
            if a.host_id <= r1_sub_count:
                # r1 grouping_id=1
                default_grouping_id = 1
                default_grouping_size = r1_sub_count
            else:
                # r2 grouping_id=2
                default_grouping_id = 2
                default_grouping_size = a.clients - r1_sub_count
            
            try:
                # r1/r2 relay
                # ✅ relay_ip
                # relay_ip assign_relay_ip
                if relay_ip == "10.0.2.2":  # r1
                    decision_file = "/tmp/r1_decisions.json"
                elif relay_ip == "10.0.3.2":  # r2
                    decision_file = "/tmp/r2_decisions.json"
                else:
                    decision_file = "/tmp/r1_decisions.json"
                
                if os.path.exists(decision_file):
                    with open(decision_file, 'r') as f:
                        decisions_data = json.load(f)
                    # ✅ {"decisions": {"1": {...}, "2": {...}}} {"h1": {...}, "h2": {...}}
                    if "decisions" in decisions_data:
                        # 1 {"decisions": {"1": {...}, "2": {...}}}
                        decisions_dict = decisions_data["decisions"]
                        user_key = str(a.host_id)
                    else:
                        decisions_dict = decisions_data
                        user_key = f"h{a.host_id}"
                    
                    if user_key in decisions_dict:
                        user_decision = decisions_dict[user_key]
                        # ✅ md2g_group_id Controller
                        # Controller 0-based ID 1-based
                        if "md2g_group_id" in user_decision:
                            grouping_id = user_decision["md2g_group_id"] + 1
                            if "md2g_group_size" in user_decision:
                                grouping_size = user_decision["md2g_group_size"]
                            else:
                                grouping_size = len(user_decision.get("md2g_group_members", []))
                            print(f"[DEBUG] h{a.host_id}: MD2G : group_id={grouping_id}, size={grouping_size}", file=sys.stderr, flush=True)
                        elif "fov_group_id" in user_decision:
                            grouping_id = user_decision["fov_group_id"]
                            if "fov_group_size" in user_decision:
                                grouping_size = user_decision["fov_group_size"]
                            else:
                                grouping_size = 1
                        # ✅ relay
                        else:
                            grouping_id = default_grouping_id
                            grouping_size = default_grouping_size
                    else:
                        # relay
                        grouping_id = default_grouping_id
                        grouping_size = default_grouping_size
                else:
                    # relay
                    grouping_id = default_grouping_id
                    grouping_size = default_grouping_size
            except Exception as e:
                # relay
                grouping_id = default_grouping_id
                grouping_size = default_grouping_size
                if iteration % 20 == 0:
                    print(f"[DEBUG] h{a.host_id}: : {e} relay grouping_id={grouping_id}, size={grouping_size} ", file=sys.stderr, flush=True)
            
            # calculate_multicast_saving
            
            # ✅ rep_id V2: rendered; legacy: ladder
            if not (rep_lc_v2 and rep_lc is not None and rep_lc.rendered_rep is not None):
                current_rep_id = map_to_rep_id(base_version, decision)
            
            # calculate_multicast_saving
            
            # ✅ PPO enh_level 0/1/2
            total_users = a.clients
            group_assignments = np.zeros(total_users, dtype=np.int32)
            enh_levels = np.zeros(total_users, dtype=np.int32)
            selected_reps = np.zeros(total_users, dtype=np.int32)
            
            try:
                # a.decision_file
                decision_file = a.decision_file
                if os.path.exists(decision_file):
                    with open(decision_file, 'r') as f:
                        all_decisions = json.load(f)
                    
                    # ✅ enh_level 0/1/2 pull_enhanced
                    # R_o enh_level pull_enhanced
                    for user_id_str, user_decision in all_decisions.get('decisions', {}).items():
                        user_id = int(user_id_str)
                        if 1 <= user_id <= total_users:
                            user_idx = user_id - 1
                            group_id = user_decision.get('md2g_group_id', (user_id - 1) % 3)
                            group_assignments[user_idx] = int(group_id)
                            
                            # ✅ enh_level 0/1/2 pull_enhanced 0/1
                            # Controller enhanced_level
                            # pull_enhanced fallback Controller
                            enh_level = user_decision.get('enhanced_level', None)
                            if enh_level is None:
                                # Fallback pull_enhanced level=1
                                pull_enhanced = user_decision.get('pull_enhanced', False)
                                enh_level = 1 if pull_enhanced else 0
                            enh_levels[user_idx] = int(enh_level)
                            try:
                                srep = user_decision.get("selected_rep", user_decision.get("rep_id"))
                                selected_reps[user_idx] = int(srep) if srep is not None else 0
                            except Exception:
                                selected_reps[user_idx] = 0
            except Exception as e:
                # fallback
                if iteration % 20 == 0:
                    print(f"[DEBUG] h{a.host_id}: R_o: {e} fallback", file=sys.stderr, flush=True)
                for u in range(total_users):
                    group_assignments[u] = u % 3
                    enh_levels[u] = 0
                    selected_reps[u] = 0
            
            # command115/124: native-9 Ro when TON_NATIVE9REP_RO=1 and scientific
            # decision gate (SIGCOMM_NATIVE9REP_DECISION or MD2G alias) not MD2G-only.
            try:
                _n9ro = os.environ.get("TON_NATIVE9REP_RO", "").strip().lower() in ("1", "true", "yes", "on")
                if (
                    _n9ro
                    and _sigcomm_native9rep_decision_enabled()
                    and int(np.max(selected_reps) or 0) >= 1
                ):
                    result = calculate_native9_multicast_saving(group_assignments, selected_reps, total_users)
                else:
                    result = calculate_multicast_saving(group_assignments, enh_levels, total_users, num_groups=3)
                if isinstance(result, tuple):
                    R_o, unicast_baseline, multicast_actual = result
                else:
                    R_o = result
                    unicast_baseline = 0.0
                    multicast_actual = 0.0
                
                if iteration % 20 == 0:
                    print(f"[Client] h{a.host_id}: R_o - unicast_baseline={unicast_baseline:.2f}Mbps, "
                          f"multicast_actual={multicast_actual:.2f}Mbps, R_o={R_o:.4f}", 
                          file=sys.stderr, flush=True)
            except Exception as e:
                # fallback rep
                if iteration % 20 == 0:
                    print(f"[DEBUG] h{a.host_id}: calculate_multicast_saving : {e} fallback R_o", file=sys.stderr, flush=True)
                # Fallback: rep
                same_rep_users = 1
                try:
                    decision_file = a.decision_file
                    if os.path.exists(decision_file):
                        with open(decision_file, 'r') as f:
                            all_decisions = json.load(f)
                        rep_subscription_count = {}
                        for user_id_str, user_decision in all_decisions.get('decisions', {}).items():
                            user_base = user_decision.get('base_version', base_version)
                            # ✅ enh_level 0/1/2 pull_enhanced 0/1
                            user_enh_level = user_decision.get('enhanced_level', decision)
                            if user_enh_level is None:
                                # Fallback pull_enhanced
                                pull_enhanced = user_decision.get('pull_enhanced', False)
                                user_enh_level = 1 if pull_enhanced else 0
                            user_rep_id = map_to_rep_id(user_base, user_enh_level)
                            rep_subscription_count[user_rep_id] = rep_subscription_count.get(user_rep_id, 0) + 1
                        same_rep_users = rep_subscription_count.get(current_rep_id, 1)
                except:
                    pass
                R_o = same_rep_users / total_users if total_users > 0 else 0.1
                R_o = max(0.1, min(1.0, R_o))
            
            grouping_efficiency = R_o
            
            if iteration % 20 == 0:
                print(f"[DEBUG] h{a.host_id}: R_o={R_o:.4f} ( )", file=sys.stderr, flush=True)
            
            # --- R_b: Bandwidth Efficiency Penalty ---
            # ✅ DASH R_b = 1.0 - (Bu / Target_Bitrate)
            # ✅ DASH rep_id base+enhanced
            if rep_lc_v2 and rep_lc is not None and rep_lc.rendered_rep is not None:
                rep_id = current_rep_id
            else:
                rep_id = map_to_rep_id(base_version, decision)
            
            # ✅ content map/env abort command110
            TARGET_BITRATE = resolve_rep_bitrate_mbps(rep_id)
            
            if Bu > 0 and TARGET_BITRATE > 0:
                bandwidth_utilization = min(1.0, Bu / TARGET_BITRATE)
                # Bu=1.0 Mbps, Target=4.5 Mbps → util=0.22 → R_b=0.78
                # Bu=3.5 Mbps, Target=4.5 Mbps → util=0.78 → R_b=0.22
                R_b = 1.0 - bandwidth_utilization
                R_b = max(0.0, min(1.0, R_b))
            else:
                # ✅ Bu=0 DASH
                R_b = 0.5
            
            # --- Load Balance JFI reward ---
            # ✅ load_balance_jfi
            # load_balance_jfi
            if 'load_balance_jfi' not in locals():
                load_balance_jfi = 1.0
            
            if a.federation == 'off':
                # ✅ load_balance_jfi
                if grouping_size > 1:
                    load_balance_jfi = 0.9 + 0.1 * (1.0 / grouping_size)
                else:
                    load_balance_jfi = 1.0
            else:
                # ✅ load_balance_jfi relay 1794
                # ✅ load_balance_jfi iteration
                if 'load_balance_jfi' not in locals() or load_balance_jfi is None:
                    load_balance_jfi = 1.0
            
            reward_final = lambda_o * R_o + lambda_q * R_q - lambda_b * R_b
            reward_final = max(0.0, reward_final)
            
            strategy_key = str(getattr(a, "strategy", "")).strip().lower()
            if strategy_key in ("md2g", "clustering", "heuristic"):
                qoe_mcast_aware = R_q * R_o
            else:
                qoe_mcast_aware = R_q
            
            Rq_legacy = 5.0 * (math.log1p(Qr) / math.log(2.5))
            Rb_legacy = math.log1p(Bu) / math.log1p(network_b_max + EPS)
            delay_penalty = dly / 200.0
            rebuffer_penalty = min(1.0, stall_count * 0.1)
            # Legacy QoE 0.15*jfi Rq/Rb
            QoE_inst_legacy = max(0.0,
                                    0.425 * Rq_legacy + 0.425 * Rb_legacy
                                    - 0.10 * delay_penalty - 0.05 * rebuffer_penalty)
            
            if a.strategy == "md2g":
                # MD2G legacy QoE
                smart_enhancement.update_windows(bandwidth_mbps=Bu, qoe_smooth=QoE_inst_legacy)
                
                network_type = getattr(a, 'network_type', None) or getattr(a, 'network', None)
                
                dq = decision_quality_v2(Bu, base_rate, delay_penalty, network_type=network_type)
                sb = stability_bonus(smart_enhancement.qoe_window)
                
                # relay_loads
                current_load_rate = np.mean(relay_loads) if relay_loads else 0.5
                
                # ============================================================
                # Module 5: Cache hit-aware strategy (Federation ON)
                # ============================================================
                # If federation ON: prefer enhanced only when cache warmed-up
                cache_aware_decision = decision
                if a.federation == 'on':
                    try:
                        # Check cache statistics (simulated via file system)
                        cache_stats_file = "/tmp/federation_cache_stats.json"
                        cache_ok = False
                        if os.path.exists(cache_stats_file):
                            with open(cache_stats_file, 'r') as f:
                                cache_stats = json.load(f)
                                cache_size = cache_stats.get("cache_size", 0)
                                cache_ok = cache_size > 50  # Cache warmed up
                        
                        if not cache_ok:
                            # Cache not warmed up yet, reduce enhanced layer usage
                            if decision == 1 and random.random() < 0.5:
                                cache_aware_decision = 0
                                if iteration % 10 == 0:
                                    print(f"[CACHE-AWARE] h{a.host_id}: Cache not ready, reducing enhanced layer usage", 
                                          file=sys.stderr, flush=True)
                    except Exception as e:
                        if iteration % 20 == 0:
                            print(f"[WARN] h{a.host_id}: Cache-aware check failed: {e}", file=sys.stderr, flush=True)
                
                enh_target, dyn_th = smart_enhancement.should_enable_enhancement(
                    network_type=a.network_type, base_rate=base_rate, 
                    relay_jfi=load_balance_jfi, relay_load=current_load_rate,
                    federation_on=(a.federation == 'on')
                )
                smart_enhancement.enh_enabled = enh_target
                
                # Apply cache-aware decision override if federation is ON
                if a.federation == 'on' and cache_aware_decision != decision:
                    decision = cache_aware_decision
            else:
                dq, sb, dyn_th = 0.0, 0.0, 0.0
            
            # --- MD2G-Plus MD2G ---
            if a.strategy == "md2g" and iteration > 10:
                # legacy QoE
                if not hasattr(run_client, 'qoe_smooth_prev'):
                    run_client.qoe_smooth_prev = QoE_inst_legacy
                QoE_smooth_legacy = 0.85 * run_client.qoe_smooth_prev + 0.15 * QoE_inst_legacy
                run_client.qoe_smooth_prev = QoE_smooth_legacy
                smart_enhancement.update_qoe_and_adjust_threshold(QoE_smooth_legacy)
            
            # --- rx_bytes ---
            # ✅ rx_bytes Bu
            # current_rx_bytes initial_rx_bytes
            if hasattr(run_client, 'initial_rx_bytes'):
                rx_bytes = int(current_rx_bytes - run_client.initial_rx_bytes)
            else:
                rx_bytes = int(current_rx_bytes)
            
            if a.strategy == "md2g":
                print(f"[DEBUG] h{a.host_id}: dly={dly:.2f}ms Bu={Bu:.2f}Mbps "
                      f"R_q={R_q:.4f} R_o={R_o:.4f} R_b={R_b:.4f} reward={reward_final:.4f} "
                      f"(dq={dq:.4f} sb={sb:.4f} dyn_th={dyn_th:.3f} MD2G )",
                      file=sys.stderr, flush=True)
            else:
                print(f"[DEBUG] h{a.host_id}: dly={dly:.2f}ms Bu={Bu:.2f}Mbps "
                      f"R_q={R_q:.4f} R_o={R_o:.4f} R_b={R_b:.4f} reward={reward_final:.4f}",
                      file=sys.stderr, flush=True)
            
            # ✅ TTFB DataDrainer None
            # Base TTFB
            ttfb_base = 0.0
            if reader_base and hasattr(reader_base, 'ttfb_ms') and reader_base.ttfb_ms is not None:
                ttfb_base = reader_base.ttfb_ms
            
            # Enhanced TTFB None
            ttfb_enh1 = 0.0
            if 1 in enh_readers and enh_readers[1] is not None:
                if hasattr(enh_readers[1], 'ttfb_ms') and enh_readers[1].ttfb_ms is not None:
                    ttfb_enh1 = enh_readers[1].ttfb_ms
            
            ttfb_enh2 = 0.0
            if 2 in enh_readers and enh_readers[2] is not None:
                if hasattr(enh_readers[2], 'ttfb_ms') and enh_readers[2].ttfb_ms is not None:
                    ttfb_enh2 = enh_readers[2].ttfb_ms
            
            # ✅ 9 enhanced3
            ttfb_enh3 = 0.0
            
            subscription_type = f"B{base_version}"
            if decision > 0:
                subscription_type += f"+E{decision}"
            
            MOQ_Q_MAPPING = {
                (1, 0): 3,
                (1, 1): 4,
                (1, 2): 4,
                (2, 0): 2,
                (2, 1): 2,
                (2, 2): 3,
                (3, 0): 1,
                (3, 1): 1,
                (3, 2): 1,
            }
            quality_level = MOQ_Q_MAPPING.get((base_version, decision), 1)
            if _use_eq9:
                # Paper path: quality_score is Q_s from final Rep ID (already computed above).
                quality_score = float(Q_s)
            else:
                # Legacy MM26 shortcut (inactive when SIGCOMM_QOE_EQ9=1).
                quality_score = float(min(1.0, 0.6 + 0.4 * (float(decision) / 2.0)))
            qoe = qoe_mcast_aware
            
            cpu_data = measure_cpu_usage()
            
            # ✅ CSV TTLB app_goodput_mbps rx_bytes
            # ✅ Phase 0 rep_id buffer_level_sec
            # ✅ MOQ moq-sub QUIC
            retransmission_count = 0
            
            csv_line = (
                f"{time.time():.2f},{a.host_id},{a.network_type},{dev_score:.3f},"
                f"{base_version},{int(decision)},{subscription_type},"
                f"{ttfb_base:.2f},{ttfb_enh1:.2f},{ttfb_enh2:.2f},{ttfb_enh3:.2f},"
                f"{dly:.2f},"
                f"{stall_count},{stall_count_inc},{stall_total_sec:.3f},"
                f"{rx_bytes},"
                f"{buffer_level_sec:.3f},"
                f"{rep_id},"
                f"{qoe:.4f},"
                f"{R_o:.4f},{R_q:.4f},{R_b:.4f},{reward_final:.4f},"
                f"{grouping_id},{grouping_efficiency:.4f},{load_balance_jfi:.4f},{iteration},"
                f"{quality_level},{quality_score:.2f},"
                f"{cpu_data['cpu_bottleneck_node_percent']:.2f},"
                f"{cpu_data['cpu_relay_process_percent']:.2f},"
                f"{cpu_data['cpu_controller_process_percent']:.2f},"
                f"{cpu_data['cpu_dash_server_process_percent']:.2f},"
                f"{cpu_data['cpu_system_percent']:.2f},"
                f"{retransmission_count}"
            )
            if _metric_v4:
                _pttfb = (
                    run_client.payload_ttfb_ms
                    if getattr(run_client, "payload_ttfb_ms", None) is not None
                    else 0.0
                )
                _mcov = float(getattr(run_client, "media_covered_sec", 0.0))
                csv_line += f",{_pttfb:.2f},{_mcov:.3f}"
            csv_line += "\n"
            
            # ✅ MD2G, Rolling, Heuristic, Clustering, Groot, Pano
            # perf.csv
            # {a.log_path}/client_h{a.host_id}_perf.csv
            perf_log_file.write(csv_line)
            perf_log_file.flush()
            perf_csv_file.write(csv_line)
            perf_csv_file.flush()

            # ✅ cell-scoped SIGCOMM_CELL_STATE_DIR / SIGCOMM_CELL_TMP / legacy
            # ✅ iteration 0
            _ensure_client_state_dir()
            client_state_file = _client_state_file(a.host_id)
            try:
                if os.path.exists(client_state_file):
                    os.chmod(client_state_file, 0o666)
            except (OSError, PermissionError) as e:
                if iteration % 10 == 0:
                    print(f"[WARN] h{a.host_id}: : {e}", file=sys.stderr, flush=True)
                pass
            
            current_state_payload = {
                "host_id": a.host_id,
                "network_type": a.network_type,
                "throughput_mbps": Bu,
                "delay_ms": dly,
                "device_score": dev_score,
                "last_decision_layer": decision,
                "reward_R_o": R_o,
                "reward_R_q": R_q,
                "reward_R_b": R_b,
                "reward_final": reward_final,
                "timestamp": time.time(),
                "viewpoint": "front_center"
            }
            # command124: FoV unavailable under scientific native9 same for all strategies
            if _sigcomm_native9rep_decision_enabled() or os.environ.get(
                "TON_FOV_UNAVAILABLE", ""
            ).strip().lower() in ("1", "true", "yes", "on"):
                current_state_payload["fov_available"] = False
                current_state_payload["fov_overlap"] = None
                current_state_payload["fov_status"] = "UNAVAILABLE_NOT_MEASURED"
            else:
                current_state_payload["fov_available"] = False
                current_state_payload["fov_overlap"] = None
                current_state_payload["fov_status"] = "UNAVAILABLE_NOT_WRITTEN_BY_DISPATCH"
            # command120: attach live playability + online capacity (never default buffer=5.0)
            try:
                _stall_now = bool(locals().get("in_stall") or (buffer_level_sec <= 0.0 and iteration > 0))
                if _stall_now:
                    if run_client._stall_started_ts is None:
                        run_client._stall_started_ts = current_time
                else:
                    run_client._stall_started_ts = None
                    run_client._last_playable_ts = current_time
                _stall_elapsed = (
                    (current_time - run_client._stall_started_ts)
                    if run_client._stall_started_ts is not None else 0.0
                )
                if run_client._last_rep_for_switch is None:
                    run_client._last_rep_for_switch = int(rep_id)
                elif int(rep_id) != int(run_client._last_rep_for_switch):
                    run_client._last_switch_ts = current_time
                    run_client._last_rep_for_switch = int(rep_id)
                _obj_s = 1.0
                _obj_bytes = max(1.0, float(total_mbps) * 1e6 / 8.0 * _obj_s)
                _covered = float(getattr(run_client, "media_covered_sec", 0.0) or buffer_level_sec)
                _frac = _covered - math.floor(_covered)
                _recv = _frac * _obj_bytes
                _by_rep = {}
                for _rid in range(1, 10):
                    try:
                        _br = float(resolve_rep_bitrate_mbps(_rid))
                    except Exception:
                        _br = 1.0
                    _by_rep[_rid] = max(0.0, _br * 1e6 / 8.0 * _obj_s * (1.0 - _frac))
                _oracle = None
                try:
                    _oracle_env = os.environ.get("TON_ORACLE_LAST_MILE_MBPS") or os.environ.get("TON_DIAG_CONFIGURED_MBPS")
                    if _oracle_env:
                        _oracle = float(_oracle_env)
                except Exception:
                    _oracle = None
                _out_bytes = _by_rep.get(int(rep_id), max(0.0, _obj_bytes - _recv))
                _cap_mbps = float(Bu) if Bu > 0 else 0.05
                _app_lim = False
                if getattr(run_client, "_gen3_cap_est", None) is not None:
                    _est = run_client._gen3_cap_est
                    _req_mbps = float(total_mbps) if total_mbps else 0.0
                    _prev_probe = float(getattr(run_client, "_c122_last_probe_rx", 0.0) or 0.0)
                    _got = 0
                    _hid = int(getattr(a, "host_id", 0) or 0)
                    if (
                        getattr(_est, "probe_active", False)
                        and os.environ.get("TON_C122_HEADROOM_PROBE", "1").strip().lower() not in ("0", "false", "no")
                        and _c122_probe_burst is not None
                    ):
                        _admit = True
                        if _c122_probe_admit is not None:
                            try:
                                # Scheduler already applied probe_slot_ok when it
                                # set probe_active. Re-checking the 0.50s slot on
                                # the next 1.0s dispatch tick never admits.
                                _admit = bool(_c122_probe_admit(
                                    _hid, float(current_time), require_slot=False,
                                ))
                            except Exception:
                                _admit = False
                        if _admit:
                            try:
                                _got = int(_c122_probe_burst())
                            except Exception:
                                _got = 0
                        elif not getattr(run_client, "_c122_probe_deny_logged", False):
                            print(
                                f"[C122] h{_hid}: probe_active but budget denied",
                                file=sys.stderr, flush=True,
                            )
                            run_client._c122_probe_deny_logged = True
                    _nic = float(delta_bytes if "delta_bytes" in locals() else 0.0)
                    _media = max(0.0, _nic - _prev_probe)
                    _cap_mbps, _app_lim = _est.update(
                        rx_bytes_delta=_media,
                        dt_s=float(time_diff if time_diff and time_diff > 0 else a.interval),
                        buffer_level_sec=float(buffer_level_sec),
                        buffer_cap_sec=12.0,
                        outstanding_bytes=_out_bytes,
                        requested_mbps=_req_mbps,
                        stall_active=bool(_stall_now),
                        now_s=float(current_time),
                        probe_rx_bytes=float(_got),
                        client_id=_hid,
                    )
                    run_client._c122_last_probe_rx = float(_got)
                    _snap = getattr(_est, "last_snapshot", None) or {}
                else:
                    _snap = {}
                _open_lat = 0.0
                if ttfb_base and ttfb_base > 0:
                    _open_lat = float(ttfb_base) / 1000.0
                _switch_lat = max(0.0, current_time - float(run_client._last_switch_ts or current_time))
                _streams = [[int(grouping_id), int(rep_id)]]
                _q_cur = float(R_q)
                _q_tgt = 0.70
                if _build_playability_payload is not None:
                    _play = _build_playability_payload(
                        buffer_level_sec=float(buffer_level_sec),
                        stall_active=_stall_now,
                        stall_elapsed_sec=float(_stall_elapsed),
                        last_playable_timestamp=run_client._last_playable_ts,
                        active_rep=int(rep_id),
                        object_bytes=_obj_bytes,
                        received_bytes=_recv,
                        bytes_remaining_by_rep=_by_rep,
                        recent_object_completion_s=float(actual_time_diff if "actual_time_diff" in locals() else a.interval),
                        stream_open_latency_s=_open_lat,
                        switch_latency_s=_switch_lat,
                        delivery_rate_mbps=float(Bu),
                        access_capacity_mbps=float(_cap_mbps),
                        app_limited=bool(_app_lim),
                        group_id=int(grouping_id),
                        active_group_rep_streams=_streams,
                        weak_user_quality_deficit=max(0.0, _q_tgt - _q_cur),
                        oracle_trace_sample_mbps=_oracle,
                    )
                    current_state_payload.update(_play)
                    current_state_payload["access_capacity_mbps"] = float(_cap_mbps)
                    current_state_payload["buffer_level_sec"] = float(buffer_level_sec)
                    current_state_payload["stall_sec"] = float(stall_total_sec)
                    if locals().get("_snap"):
                        current_state_payload["capacity_est_mbps"] = _snap.get("capacity_est_mbps", _cap_mbps)
                        current_state_payload["capacity_lower_bound_mbps"] = _snap.get("capacity_lower_bound_mbps")
                        current_state_payload["capacity_confidence"] = _snap.get("capacity_confidence")
                        current_state_payload["estimator_source"] = _snap.get("estimator_source")
                        current_state_payload["last_non_app_limited_sample_age"] = _snap.get("last_non_app_limited_sample_age")
                        current_state_payload["probe_active"] = _snap.get("probe_active")
                        current_state_payload["probe_bytes"] = _snap.get("probe_bytes")
                        current_state_payload["demand_limited"] = _snap.get("demand_limited")
                        if "_got" in locals():
                            current_state_payload["probe_rx_bytes_tick"] = int(_got)
                else:
                    current_state_payload["buffer_level_sec"] = float(buffer_level_sec)
                    current_state_payload["playability_module_missing"] = True
            except Exception as _play_exc:
                current_state_payload["playability_error"] = str(_play_exc)
                current_state_payload["buffer_level_sec"] = float(buffer_level_sec)
            try:
                _ensure_client_state_dir()

                temp_file = f"{client_state_file}.tmp"
                with open(temp_file, 'w') as sf:
                    json.dump(current_state_payload, sf)
                    sf.flush()
                    os.fsync(sf.fileno())
                
                os.rename(temp_file, client_state_file)
                
                os.chmod(client_state_file, 0o666)
                if os.environ.get("TON_GEN3_PLAYABILITY", "").strip() in ("1", "true", "yes", "on"):
                    try:
                        _pj = os.path.join(a.log_path, f"playability_h{a.host_id}.jsonl")
                        with open(_pj, "a") as _pf:
                            _pf.write(json.dumps({
                                "t": time.time(),
                                "iteration": iteration,
                                "buffer_level_sec": current_state_payload.get("buffer_level_sec"),
                                "playable_ahead_sec": current_state_payload.get("playable_ahead_sec"),
                                "stall_active": current_state_payload.get("stall_active"),
                                "time_to_playable_s": current_state_payload.get("time_to_playable_s"),
                                "access_capacity_mbps": current_state_payload.get("access_capacity_mbps"),
                                "delivery_rate_mbps": current_state_payload.get("delivery_rate_mbps"),
                                "app_limited": current_state_payload.get("app_limited"),
                                "estimator_source": current_state_payload.get("estimator_source"),
                                "demand_limited": current_state_payload.get("demand_limited"),
                                "probe_active": current_state_payload.get("probe_active"),
                                "probe_bytes": current_state_payload.get("probe_bytes"),
                                "probe_rx_bytes_tick": current_state_payload.get("probe_rx_bytes_tick"),
                                "capacity_confidence": current_state_payload.get("capacity_confidence"),
                                "active_rep": current_state_payload.get("active_rep"),
                                "group_id": current_state_payload.get("group_id"),
                                "active_group_rep_streams": current_state_payload.get("active_group_rep_streams"),
                                "rep_completion_frac": current_state_payload.get("rep_completion_frac"),
                            }) + "\n")
                    except Exception:
                        pass
                
                if iteration == 0 or iteration % 20 == 0:
                    print(f"[DEBUG] h{a.host_id}: ✅ : {client_state_file} (iteration={iteration})", file=sys.stderr, flush=True)
                    if os.path.exists(client_state_file):
                        file_size = os.path.getsize(client_state_file)
                        print(f"[DEBUG] h{a.host_id}: ✅ : {file_size} ", file=sys.stderr, flush=True)
            except (IOError, OSError, PermissionError) as e:
                if iteration % 10 == 0:
                    print(f"[WARN] h{a.host_id}: client_state_file: {e}", file=sys.stderr, flush=True)
                pass

            # --- Rolling ---
            # state_window Rolling DRL N
            # ✅ reward_final QoE_smooth
            state_window.append([Bu, dly, reward_final, Qr, decision])
            iteration += 1
            time.sleep(a.interval)
    
    finally:
        if instr_v2 is not None and instr_v2_jsonl is not None:
            try:
                instr_v2.flush_cell(instr_v2_jsonl)
            except Exception as exc:
                print(
                    f"[WARN] h{a.host_id}: instrumentation v2 flush failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        perf_log_file.close()
        perf_csv_file.close()
        print(f"[INFO] h{a.host_id}: CSV : {perf_csv}", file=sys.stderr, flush=True)

    print(f"[INFO] h{a.host_id}: Base Enhanced decision ", file=sys.stderr, flush=True)
    
    # ✅ DataDrainer
    if rep_lc_v2 and 'rep_subs' in locals() and rep_subs:
        for rid in list(rep_subs.keys()):
            _terminate_rep_sub(rid)
        print(f"[INFO] h{a.host_id}: REP-LC-V2 rep_subs ", file=sys.stderr, flush=True)
    else:
        if 'reader_base' in locals():
            reader_base.stop()
            print(f"[INFO] h{a.host_id}: Base DataDrainer {reader_base.bytes_read // 1024} KB ", file=sys.stderr, flush=True)
        
        # ✅ Enhanced DataDrainer
        if 'enh_readers' in locals():
            for version in [1, 2, 3]:
                if version in enh_readers and enh_readers[version] is not None:
                    enh_readers[version].stop()
                    print(f"[INFO] h{a.host_id}: Enhanced{version} DataDrainer {enh_readers[version].bytes_read // 1024} KB ", file=sys.stderr, flush=True)
    
    time.sleep(0.5)
    
    if not rep_lc_v2 and base_p:
        kill(base_p)
    
    # ✅ Enhanced legacy dual-sub path
    if not rep_lc_v2 and 'enh_processes' in locals():
        for version in [1, 2, 3]:
            if version in enh_processes and enh_processes[version] is not None:
                kill(enh_processes[version])
                print(f"[INFO] h{a.host_id}: Enhanced{version} ", file=sys.stderr, flush=True)



# ============================= CLI =============================
if __name__ == "__main__":
    p = argparse.ArgumentParser("MoQ dispatch client")
    p.add_argument("--duration", type=int, default=60)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--host_id", type=int, required=True)
    p.add_argument("--log_path", required=True)
    p.add_argument("--decision_file", required=True)
    p.add_argument("--strategy", choices=["md2g", "rolling", "heuristic", "clustering", "groot", "pano"], required=True)
    p.add_argument("--clients", type=int, required=True)
    p.add_argument("--relay_ip")
    p.add_argument("--gst_plugin_path", required=True)
    p.add_argument("--device_score", type=float, required=True)
    # command40: moq_cluster_Sigcomm passes --device_type; accept and record (env DEVICE_TYPE also set).
    p.add_argument("--device_type", type=str, default=None,
                   help="Device profile name (e.g. quest2_72); optional, also via DEVICE_TYPE env")
    p.add_argument("--network_type", required=True)
    p.add_argument("--model_path", required=True)
    p.add_argument("--federation", choices=["on", "off"], default="off")

    try:
        run_client(p.parse_args())
    except Exception:
        print("❌ :\n", traceback.format_exc())
        sys.exit(1)