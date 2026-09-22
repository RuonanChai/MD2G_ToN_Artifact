# ======================================================================
#  dispatch_strategy.py – 最终完整功能版
# ======================================================================

import argparse, os, sys, json, time, subprocess, traceback, math, re, glob
import random
import pandas as pd
from collections import deque
import numpy as np
import threading

# ✅ 【CPU使用率测量】导入psutil库
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("[WARN] psutil未安装，CPU使用率测量功能不可用。请运行: pip install psutil", file=sys.stderr, flush=True)

# ✅ 【Federation OFF 模式】不需要导入用户到relay映射工具
# 在 Federation OFF 模式下，所有用户都连接到 r0，忽略映射表

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
# 窗口与迟滞（优化：减少迟滞，更快响应）
MD2G_TREND_WIN = 5          # 带宽/QoE 窗口长度
MD2G_ENABLE_GOOD_CNT = 1    # 从2降低到1，更快启用增强层
MD2G_DISABLE_BAD_CNT = 2    # 从3降低到2，更快响应网络恶化

# 阈值与趋势调节（优化：更积极启用增强层以提升带宽和QoE）
MD2G_ON_BASE_THRESHOLD = 1.02   # 从1.08进一步降低到1.02，更积极启用增强层
MD2G_OFF_BASE_THRESHOLD = 1.05  # 从1.12降低到1.05，提升OFF状态QoE
MD2G_TREND_UP_ADJ = 0.90        # 从0.93进一步降低到0.90，更积极响应上行趋势
MD2G_TREND_DOWN_ADJ = 1.01       # 从1.03降低到1.01，减少保守滞后

# 稳定性奖励
MD2G_STAB_BONUS_MAX = 0.15   # 最多 +0.15
MD2G_STAB_STD_CAP  = 0.10    # std 上限映射

# DecisionQuality 权重（优化：提高带宽权重以改善带宽性能）
MD2G_DQ_W_BW = 0.80  # 从0.75进一步提高到0.80，更重视带宽
MD2G_DQ_W_DLY = 0.20  # 从0.25降低到0.20


def _parse_qoe_weights_from_env():
    """与 MM26/dispatch_strategy_enhanced_unified_NOSSDAV.py::_parse_qoe_weights_from_env 一致。"""
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
    """与 MM26 默认 λ 一致，可通过 MM26_REWARD_LAMBDA_* 覆盖。"""
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
# ⚠️ 废弃：旧的MD2G权重配置（不再使用）
# ==============================================================================
# 注意：统一QoE公式后，所有策略（包括MD2G）都使用相同的权重配置
# 这些旧的权重定义已废弃，保留仅为历史参考，实际代码中不再使用
# ==============================================================================
# MD2G_W_ON  = dict(w_r=0.40, w_b=0.30, w_ln=0.20, w_d=0.07, w_f=0.03)  # 已废弃
# MD2G_W_OFF = dict(w_r=0.40, w_b=0.38, w_ln=0.14, w_d=0.06, w_f=0.02)  # 已废弃

# ---------------- 数据集加载 ----------------
# Fail-closed: SIGCOMM_DATASET_DIR or <repo>/datasets (no legacy home-directory fallback).
_REPO_ROOT_DS = os.path.dirname(os.path.abspath(__file__))
_ds_env = (os.environ.get("SIGCOMM_DATASET_DIR") or "").strip()
DATASET_DIR = _ds_env if _ds_env else os.path.join(_REPO_ROOT_DS, "datasets")
if not os.path.isdir(DATASET_DIR):
    raise FileNotFoundError(
        f"SIGCOMM dataset dir missing: {DATASET_DIR} "
        "(set SIGCOMM_DATASET_DIR; legacy home-directory fallbacks disabled)"
    )
print("[DEBUG] dispatch_strategy.py 正在运行，数据目录:", DATASET_DIR, file=sys.stderr)
df_wifi = pd.read_csv(os.path.join(DATASET_DIR, "wifi_clean.csv"))
df_4g   = pd.read_csv(os.path.join(DATASET_DIR, "4G-network-data_clean.csv"))
# ✅ 【修复】5G数据集文件名：实际是 5g_final_trace.csv，不是 5g_network_data_clean.csv
df_5g   = pd.read_csv(os.path.join(DATASET_DIR, "5g_final_trace.csv"))
df_opt  = pd.read_csv(os.path.join(DATASET_DIR, "Optic_Bandwidth_clean_2.csv"))
df_dev  = pd.read_csv(os.path.join(DATASET_DIR, "Headset device performance.csv"))

print(f"[DEBUG] Using datasets from: {DATASET_DIR}", file=sys.stderr)

# ✅ 【修复】数据集列名不统一：4G数据集使用 "DL_bitrate_Mbps"，其他使用 "bytes_sec (Mbps)"
# 统一列名处理
def get_bandwidth_column(df, default_col="bytes_sec (Mbps)"):
    """获取带宽列名，支持多种列名格式"""
    if default_col in df.columns:
        return default_col
    elif "DL_bitrate_Mbps" in df.columns:
        return "DL_bitrate_Mbps"
    elif "bitrate" in df.columns.str.lower().values:
        bitrate_cols = [c for c in df.columns if "bitrate" in c.lower()]
        return bitrate_cols[0] if bitrate_cols else None
    else:
        # 尝试找到第一个数值列
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        return numeric_cols[0] if len(numeric_cols) > 0 else None

bw_col_wifi = get_bandwidth_column(df_wifi)
bw_col_4g = get_bandwidth_column(df_4g, "DL_bitrate_Mbps")
bw_col_5g = get_bandwidth_column(df_5g)
bw_col_opt = get_bandwidth_column(df_opt)

print(f"[DEBUG] Bandwidth columns: wifi={bw_col_wifi}, 4g={bw_col_4g}, 5g={bw_col_5g}, opt={bw_col_opt}", file=sys.stderr)

# 按网络类型分组的B_MAX（P95值）
B_MAX_BY_NETWORK = {
    "wifi": np.percentile(df_wifi[bw_col_wifi], 95) if bw_col_wifi else 100.0,
    "4g": np.percentile(df_4g[bw_col_4g], 95) if bw_col_4g else 50.0,
    "5g": np.percentile(df_5g[bw_col_5g], 95) if bw_col_5g else 200.0,
    "fiber_optic": np.percentile(df_opt[bw_col_opt], 95) if bw_col_opt else 1000.0
}

# 全局B_MAX（保持向后兼容）
all_bw = pd.concat([
    df_wifi[bw_col_wifi] if bw_col_wifi else pd.Series([100.0]),
    df_4g[bw_col_4g] if bw_col_4g else pd.Series([50.0]),
    df_5g[bw_col_5g] if bw_col_5g else pd.Series([200.0]),
    df_opt[bw_col_opt] if bw_col_opt else pd.Series([1000.0])
])
B_MAX = np.percentile(all_bw, 95)
EPS = 1e-6

print(f"[DEBUG] 按网络类型B_MAX: {B_MAX_BY_NETWORK}", file=sys.stderr)
print(f"[DEBUG] 全局B_MAX: {B_MAX:.2f} Mbps", file=sys.stderr)

# ---------- Rolling-DRL ----------
try:
    from strategies.rolling_drl_strategy_v2_refined import RollingDRLStrategy
except ImportError:
    RollingDRLStrategy = None

# ---------- 智能增强层状态管理 ----------
class SmartEnhancementState:
    """智能增强层状态管理：双阈值+迟滞机制+动态调节"""
    def __init__(self):
        self.enh_enabled = False
        self.good_cnt = 0
        self.bad_cnt = 0
        self.bw_ema = 0.0
        self.bw_window = deque(maxlen=MD2G_TREND_WIN)  # 最近5次带宽记录
        self.alpha = 0.6  # EMA平滑系数 - 优化：从0.5提高到0.6，更快响应带宽变化
        self.qoe_window = deque(maxlen=MD2G_TREND_WIN)  # 最近5次QoE记录，用于动态调节
        self.bandwidth_trend = 0  # -1/0/+1
        self.qoe_trend = 0        # -1/0/+1
        self.dynamic_threshold_multiplier = 1.0  # 动态阈值乘数
        
        # 网络特化阈值 - ✅ 【WiFi特调】针对WiFi网络大幅提高准入门槛，强制预留20-30%带宽余量
        self.thresholds = {
            # ✅ WiFi 特调：大幅提高门槛，防止波动导致卡顿
            # "on": 1.25 -> 必须有 25% 的带宽余量才允许开启 Enhanced
            # "off": 1.10 -> 一旦余量低于 10%，立刻切回 Base（保命要紧）
            # "load_max": 0.70 -> 如果 Relay 负载超过 70%，WiFi 用户就别凑热闹了
            "wifi": {
                "on": 1.25,      # 提高门槛，防止波动导致卡顿
                "off": 1.10,     # 提前撤退，减少 Stall
                "jfi_min": 0.85, 
                "load_max": 0.70, # 拥塞时 WiFi 用户优先降级
                "load_off": 0.85
            },
            # 4G 保持激进（因为本来带宽就小，不激进没法看）
            "4g": {"on": 0.98, "off": 0.95, "jfi_min": 0.88, "load_max": 0.90, "load_off": 0.95},
            # 5G/光纤 保持激进（带宽稳，不怕）
            "5g": {"on": 1.00, "off": 0.98, "jfi_min": 0.90, "load_max": 0.85, "load_off": 0.93},
            "fiber_optic": {"on": 1.02, "off": 1.00, "jfi_min": 0.92, "load_max": 0.75, "load_off": 0.88},
            # 混合网络特化阈值 - 新增：针对混合网络优化
            "mixed_4g_heavy": {"on": 1.00, "off": 0.98, "jfi_min": 0.88, "load_max": 0.90, "load_off": 0.95},
            "mixed_balanced": {"on": 1.00, "off": 0.98, "jfi_min": 0.90, "load_max": 0.85, "load_off": 0.93},
            "mixed_wifi_heavy": {"on": 1.00, "off": 0.98, "jfi_min": 0.90, "load_max": 0.80, "load_off": 0.90}
        }
        
        # 用户分组管理 - 更精准的分组策略
        self.user_groups = {
            "high_performance": [],  # 高性能用户组
            "medium_performance": [],  # 中等性能用户组
            "low_performance": []  # 低性能用户组
        }
        
        # 网络适应性状态
        self.network_adaptation = {
            "bandwidth_trend": 0,  # 带宽趋势 (1=上升, 0=稳定, -1=下降)
            "stability_score": 1.0,  # 网络稳定性评分
            "adaptation_factor": 1.0  # 适应性因子
        }
    
    def _trend_from_window(self, seq, pos=0.05, neg=-0.05):
        """从窗口数据计算趋势"""
        if len(seq) < 3:
            return 0
        diffs = np.diff(np.array(seq, dtype=float))
        avg = np.mean(diffs)
        if avg > pos:  return 1
        if avg < neg:  return -1
        return 0

    def update_windows(self, bandwidth_mbps, qoe_smooth):
        """更新窗口和趋势"""
        self.bw_window.append(float(bandwidth_mbps))
        self.qoe_window.append(float(qoe_smooth))
        self.bandwidth_trend = self._trend_from_window(self.bw_window)
        self.qoe_trend = self._trend_from_window(self.qoe_window, pos=0.01, neg=-0.01)

    def update_bandwidth(self, inst_bw: float):
        """更新带宽EMA和窗口"""
        if self.bw_ema == 0:
            self.bw_ema = inst_bw
        else:
            self.bw_ema = self.alpha * self.bw_ema + (1 - self.alpha) * inst_bw
        
        self.bw_window.append(inst_bw)
    
    def get_pessimistic_bandwidth(self) -> float:
        """获取保守带宽估计（10分位数，更激进）"""
        if len(self.bw_window) < 3:
            return self.bw_ema
        return min(self.bw_ema, np.percentile(list(self.bw_window), 10))  # 从20%降低到10%，更激进
    
    def update_qoe_and_adjust_threshold(self, qoe_value: float):
        """更新QoE并动态调整阈值"""
        self.qoe_window.append(qoe_value)
        
        if len(self.qoe_window) >= 10:  # 有足够样本时进行动态调节
            qoe_std = np.std(list(self.qoe_window))
            
            # 动态阈值调节逻辑
            if qoe_std < 0.02:  # 稳态下更激进
                self.dynamic_threshold_multiplier = 0.95
            elif qoe_std > 0.05:  # 波动大时更保守
                self.dynamic_threshold_multiplier = 1.05
            else:  # 正常状态
                self.dynamic_threshold_multiplier = 1.0
    
    def should_enable_enhancement(self, network_type: str, base_rate: float, 
                                 relay_jfi: float, relay_load: float, federation_on: bool = False) -> tuple:
        """判断是否应该启用增强层"""
        if network_type not in self.thresholds:
            network_type = "wifi"  # 默认使用wifi阈值
        
        # ✅ 【关键修复】使用网络特定的阈值配置，而不是全局常量
        specific_th = self.thresholds[network_type]
        
        # 获取网络特定的on/off阈值
        threshold_val = specific_th["on"] if not self.enh_enabled else specific_th["off"]
        
        # 根据带宽趋势微调（可选，保持向后兼容）
        if self.bandwidth_trend > 0:
            threshold_val *= MD2G_TREND_UP_ADJ
        elif self.bandwidth_trend < 0:
            threshold_val *= MD2G_TREND_DOWN_ADJ
        
        # ✅ 【WiFi特调】获取保守带宽估计
        estimated_bw = self.get_pessimistic_bandwidth()
        
        # ✅ 【新增】针对 WiFi 的额外"恐惧因子"
        # WiFi 信号通常有突发丢包，测量值往往虚高，手动打折 15%
        if network_type == "wifi":
            estimated_bw *= 0.85
            # 核心判断逻辑：
            # (带宽 * 0.85) >= (base_rate * 1.25)
            # 这意味着真实带宽必须是 base_rate 的 1.47 倍 (1.25 / 0.85) 才能开启 Enhanced
            # 这是一个非常安全的"舒适区"

        # 使用网络特定的阈值进行判断
        ok_bw   = (estimated_bw >= base_rate * threshold_val)
        ok_jfi  = (relay_jfi >= specific_th["jfi_min"])
        ok_load = (relay_load <= (specific_th["load_max"] if not self.enh_enabled else specific_th["load_off"]))
        ok = ok_bw and ok_jfi and ok_load

        # 迟滞：需要连续满足/不满足
        if ok:
            self.good_cnt += 1
            self.bad_cnt = 0
        else:
            self.bad_cnt += 1
            self.good_cnt = 0

        if not self.enh_enabled and self.good_cnt >= MD2G_ENABLE_GOOD_CNT:
            self.enh_enabled = True
            print(f"[SmartEnhancement-Plus] 启用增强层: network={network_type}, bw_pess={estimated_bw:.2f}, jfi={relay_jfi:.3f}, load={relay_load:.3f}, threshold={threshold_val:.3f}")
            return True, threshold_val
        if self.enh_enabled and self.bad_cnt >= MD2G_DISABLE_BAD_CNT:
            self.enh_enabled = False
            print(f"[SmartEnhancement-Plus] 禁用增强层: network={network_type}, bw_pess={estimated_bw:.2f}, jfi={relay_jfi:.3f}, load={relay_load:.3f}, threshold={threshold_val:.3f}")
            return False, threshold_val
        # 保持现状
        return self.enh_enabled, threshold_val

# 全局智能增强层状态
smart_enhancement = SmartEnhancementState()

# ---------- 增强版决策质量和稳定性函数 ----------
def decision_quality_v2(Bu, base_rate, delay_penalty, network_type=None):
    """决策质量 2.0 - 包含延迟响应项，支持动态权重调整（优化：混合网络更重视带宽）"""
    # 根据网络类型动态调整权重（混合网络更重视带宽）
    if network_type and network_type in ['mixed_4g_heavy', 'mixed_balanced', 'mixed_wifi_heavy']:
        w_bw = 0.80  # 混合网络：更重视带宽
        w_dly = 0.20
    else:
        w_bw = MD2G_DQ_W_BW
        w_dly = MD2G_DQ_W_DLY
    
    # 带宽利用率项（缩紧系数 1.2，比原来 1.5 更敏感）
    util = min(1.0, float(Bu) / max(1e-6, base_rate * 1.2))
    # 延迟响应项（越低越好 → 1/(1+d) 映射）
    resp = 1.0 / (1.0 + max(0.0, float(delay_penalty)))
    return min(1.0, w_bw * util + w_dly * resp)

def stability_bonus(qoe_window):
    """稳定性奖励 - 基于QoE标准差"""
    if not qoe_window:
        return 0.0
    std = float(np.std(list(qoe_window)))
    # std=0 → 奖励最大；std>=cap → 奖励趋近 0
    factor = max(0.0, 1.0 - min(std, MD2G_STAB_STD_CAP) / MD2G_STAB_STD_CAP)
    return MD2G_STAB_BONUS_MAX * factor

# ---------- 工具函数 ----------
def sample_bandwidth(net_type: str) -> float:
    """从真实数据集中采样网络带宽。Gen3 DEV 只抽冻结行窗。"""
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
    """基于 GPU 性能调整 Qr"""
    gpu_vals = df_dev["GPU Clock (MHz)"]
    min_gpu, max_gpu = gpu_vals.min(), gpu_vals.max()
    scale = 0.8 + 0.4 * (device_score - min_gpu) / (max_gpu - min_gpu + 1e-6)
    return max(0.8, min(scale, 1.2))

def nic_name(host_id, retries=5):
    """获取主机网络接口名，优先使用h{host_id}-eth0"""
    # 优先尝试h{host_id}-eth0
    primary_iface = f"h{host_id}-eth0"
    if os.path.exists(f"/sys/class/net/{primary_iface}"):
        return primary_iface
    
    # 回退到动态检测
    for _ in range(retries):
        ifaces = glob.glob(f"/sys/class/net/h{host_id}-eth*")
        if ifaces:
            return os.path.basename(ifaces[0])
        time.sleep(1)
    
    # 最后回退到默认接口
    print(f"[WARN] h{host_id}: 无法检测到网络接口，使用默认h{host_id}-eth0", file=sys.stderr, flush=True)
    return primary_iface

def measure_bandwidth(server_ip, duration=10, parallel=5):
    """
    使用iperf3测量真实网络带宽（从client到server）
    
    Args:
        server_ip: 目标服务器IP（relay或源服务器）
        duration: 测量持续时间（秒）
        parallel: 并发流数量
    
    Returns:
        带宽值（Mbps），如果测量失败返回None
    """
    cmd = f"iperf3 -c {server_ip} -t {duration} -P {parallel} -J"
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=duration+5)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            # 提取总接收带宽
            bits_per_second = data.get('end', {}).get('sum_received', {}).get('bits_per_second', 0)
            if bits_per_second > 0:
                return bits_per_second / 1e6  # 转换为Mbps
    except Exception as e:
        # 静默失败，不打印错误（避免日志过多）
        pass
    return None


def ping_rtt(host, iface=None):
    """
    使用ping测量真实网络延迟（RTT）
    
    Args:
        host: 目标主机IP
        iface: 网络接口名（可选）
    
    Returns:
        延迟值（毫秒），如果测量失败返回-1
    """
    try:
        cmd = ["ping", "-c", "1", "-W", "1", host]
        if iface:
            cmd += ["-I", iface]  # 指定网卡
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, universal_newlines=True, timeout=3)
        match = re.search(r'time=(\d+\.\d+)', output)
        if match:
            return float(match.group(1))
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # ping失败，返回-1表示测量失败
        return -1
    except Exception:
        return -1
    return -1

def get_real_trace_delay(network_type):
    """基于真实trace数据计算延迟"""
    try:
        import pickle
        with open('real_trace_delays.pkl', 'rb') as f:
            delay_distributions = pickle.load(f)
        
        if network_type in delay_distributions:
            delays = delay_distributions[network_type]
            # 随机选择一个延迟值
            return random.choice(delays)
        else:
            # 如果网络类型不存在，使用默认值
            return random.uniform(20, 120)
    except:
        # 如果文件不存在或读取失败，使用默认值
        return random.uniform(20, 120)

def kill(p: subprocess.Popen | None):
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(timeout=1)
        except subprocess.TimeoutExpired:
            p.kill()

# ==============================================================================
# ✅ 【DataDrainer 类】持续读取进程输出，防止缓冲区阻塞
# ==============================================================================
# 作用：持续读取进程输出，防止缓冲区阻塞，实现真正的 "Download & Discard"
# 核心原理：使用二进制块读取（read(4096)），不等待换行符，防止 Pipe 死锁
# 用于 Base 和 Enhanced 订阅进程（动态订阅模式：Enhanced 进程根据 decision 启动/停止）
# ==============================================================================
class DataDrainer(threading.Thread):
    """
    强力数据抽水机（二进制块读取器）
    
    功能：
    1. 持续读取进程的 stdout/stderr，防止缓冲区满导致进程阻塞
    2. 使用二进制块读取（read(4096)），不等待换行符，防止死锁
    3. 将读取的数据写入日志文件（如果需要）
    4. 解析日志中的关键指标（延迟、码率等）
    
    原理：
    - 不使用 readline()（会死等换行符导致死锁）
    - 使用 read(4096) 二进制块读取，只要有数据就立即读取
    - 读完直接丢弃或写入文件，不做耗时操作
    - 防止 Pipe 缓冲区（64KB）被填满导致进程挂起
    """
    def __init__(self, process, name, log_file_path=None, start_time_epoch=None):
        super().__init__()
        self.process = process
        self.name = name
        self.log_file_path = log_file_path
        self.start_time_epoch = start_time_epoch if start_time_epoch is not None else time.time()  # 进程启动的绝对时间 (T0)
        self.running = True
        self.daemon = True  # 设为守护线程，主程序退出它自动退出
        self._latest_line = ""  # 缓存最后一行文本用于调试
        self.bytes_read = 0  # 读取的字节数统计
        self.last_activity_time = time.time()  # 最后活动时间
        
        # ✅ 【TTFB/TTLB 测量】核心指标
        self.ttfb_ms = None  # 首包时延 (Time To First Byte)
        self.ttlb_ms = None  # 尾包时延 (Time To Last Byte) / 传输完成时间
        self.total_bytes = 0  # 总接收字节数
        
        # ✅ 【关键修复】用于实时延迟测量
        self.last_data_ts = None  # 最近一次读到任何数据的时间（time.time()）
        self.last_read_dt_ms = None  # 最近一次 read 循环的间隔（EWMA）
        
    def run(self):
        """持续读取进程输出（强力排水模式），同时测量 TTFB 和 TTLB"""
        print(f"[DataDrainer] {self.name}: 强力排水模式启动（二进制块读取，防止Pipe死锁）", file=sys.stderr, flush=True)
        
        # 如果指定了日志文件，打开文件用于写入
        log_file = None
        if self.log_file_path:
            try:
                log_file = open(self.log_file_path, 'ab')  # 二进制追加模式
            except Exception as e:
                print(f"[DataDrainer] {self.name}: 无法打开日志文件 {self.log_file_path}: {e}", file=sys.stderr, flush=True)
        
        # ✅ 【TTFB/TTLB 测量】初始化
        has_received_first_byte = False
        last_arrival_time = None  # 用于记录最后一次收到数据的时间
        
        try:
            # 循环读取，直到进程结束
            while self.running:
                # ✅ 【关键】直接读取二进制流，不等待换行符！
                # 每次读取 4096 字节 (4KB)，只要有数据就立即读取
                try:
                    data = self.process.stdout.read(4096)
                except Exception as e:
                    # 如果读取失败（例如进程已关闭），检查进程状态
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.01)  # 短暂休眠后重试
                    continue
                
                # 如果读到空，且进程已结束，说明流传输完毕
                if not data:
                    if self.process.poll() is not None:
                        break
                    # 如果进程还在运行但没有数据，短暂休眠后继续
                    time.sleep(0.01)
                    continue
                
                current_time = time.time()
                self.bytes_read += len(data)
                self.total_bytes += len(data)
                self.last_activity_time = current_time
                last_arrival_time = current_time  # 持续更新最后时刻
                
                # ✅ 【关键修复】更新最近数据到达时间（用于实时延迟测量）
                if self.last_data_ts is not None:
                    # 计算本次 read 的间隔（毫秒）
                    dt_ms = (current_time - self.last_data_ts) * 1000.0
                    # EWMA 平滑
                    if self.last_read_dt_ms is None:
                        self.last_read_dt_ms = dt_ms
                    else:
                        self.last_read_dt_ms = 0.8 * self.last_read_dt_ms + 0.2 * dt_ms
                self.last_data_ts = current_time
                
                # ✅ 【TTFB 测量】捕获首包时延（只记录第一次）
                if not has_received_first_byte:
                    self.ttfb_ms = (current_time - self.start_time_epoch) * 1000.0
                    print(f"⏱️  [{self.name}] TTFB (首包): {self.ttfb_ms:.2f} ms", file=sys.stderr, flush=True)
                    has_received_first_byte = True
                
                # ✅ 如果指定了日志文件，将数据写入文件
                if log_file:
                    try:
                        log_file.write(data)
                        log_file.flush()  # 立即刷新，确保数据写入
                    except Exception as e:
                        if self.bytes_read % (4096 * 100) == 0:  # 每100次读取打印一次错误
                            print(f"[DataDrainer] {self.name}: 写入日志文件异常: {e}", file=sys.stderr, flush=True)
                
                # ✅ 【关键】尝试解码文本用于调试（忽略错误，避免二进制数据导致崩溃）
                try:
                    text_chunk = data.decode('utf-8', errors='ignore')
                    # 简单粗暴：只保留最后一段看起来像文本的东西用于调试
                    if len(text_chunk.strip()) > 0:
                        # 提取最后一行（可能不完整）
                        lines = text_chunk.split('\n')
                        if lines:
                            self._latest_line = lines[-1]
                except:
                    pass
                
                # ✅ 读完直接丢弃，不做任何耗时操作！
                # 这是"抽水机"模式：只负责把 Pipe 里的"水"排干，防止阻塞
                
        except Exception as e:
            print(f"[DataDrainer] {self.name} 异常: {e}", file=sys.stderr, flush=True)
        finally:
            # ✅ 【TTLB 测量】计算尾包时延（循环结束后，用最后一次收到数据的时间计算）
            if last_arrival_time:
                self.ttlb_ms = (last_arrival_time - self.start_time_epoch) * 1000.0
                
                # 计算平均吞吐量 (Throughput)
                duration_sec = self.ttlb_ms / 1000.0
                avg_speed_mbps = (self.total_bytes * 8 / 1000000) / duration_sec if duration_sec > 0 else 0
                
                print(f"🏁 [{self.name}] 传输完成! TTLB (尾包): {self.ttlb_ms:.2f} ms | "
                      f"总大小: {self.total_bytes/1024/1024:.2f} MB | "
                      f"平均速度: {avg_speed_mbps:.2f} Mbps", file=sys.stderr, flush=True)
            else:
                print(f"⚠️  [{self.name}] 未收到任何数据 (TTLB 无效)", file=sys.stderr, flush=True)
            
            # 关闭日志文件
            if log_file:
                try:
                    log_file.close()
                except:
                    pass
        
        print(f"[DataDrainer] {self.name}: 线程退出（共读取 {self.bytes_read} 字节）", file=sys.stderr, flush=True)
    
    @property
    def latest_data(self):
        """兼容之前的调用接口"""
        return self._latest_line
    
    @property
    def lines_read(self):
        """兼容之前的调用接口（返回字节数）"""
        return self.bytes_read // 1024  # 转换为KB，用于显示
    
    def stop(self):
        """停止读取线程"""
        self.running = False

def assign_relay_ip(host_id: int, num_clients: int = 10) -> str:
    """
    ✅ 根据 host_id 分配用户到 r1 或 r2
    
    分配逻辑：
    - 前一半用户（h1-h5）连接到 r1
    - 后一半用户（h6-h10）连接到 r2
    
    Relay IP 地址：
    - r1-eth0: 10.0.2.2 (连接 r0，接收数据)
    - r2-eth0: 10.0.3.2 (连接 r0，接收数据)
    """
    r1_sub_count = num_clients // 2
    if host_id <= r1_sub_count:
        return "10.0.2.2"  # r1-eth0 的 IP 地址
    else:
        return "10.0.3.2"  # r2-eth0 的 IP 地址

def parse_rebuffer_from_debug(log_path, last_size=[0]):
    """解析GST_DEBUG日志中的rebuffer信息"""
    import os, re, time
    # 增量读取，避免每次从头扫描
    try:
        if not os.path.exists(log_path):
            return 0.0, 0
        
        cur = os.path.getsize(log_path)
        start = last_size[0]
        last_size[0] = cur
        if cur <= start:
            return 0.0, 0  # 无新内容
        
        with open(log_path, "r", errors="ignore") as fp:
            fp.seek(start)
            chunk = fp.read()

        # 解析buffering信息
        stall_time = 0.0
        stall_cnt = 0
        
        # 查找buffering相关的日志
        buffering_patterns = [
            r'buffering.*?(\d+)%',  # buffering 0% -> 100%
            r'buffering done',      # buffering完成
            r'underflow',           # 缓冲区下溢
            r'stall'                # 卡顿
        ]
        
        # 简化：每出现一次 "buffering done" 或 "underflow" 就认为发生过一次卡顿
        stall_cnt = len(re.findall(r'buffering done|underflow|stall', chunk, re.IGNORECASE))
        
        # 如果有时间戳格式，可进一步精确计算持续时间；这里先返回计数
        return stall_time, stall_cnt
    except Exception as e:
        print(f"[WARN] 解析rebuffer日志失败: {e}", file=sys.stderr, flush=True)
        return 0.0, 0

def calculate_jain_fairness_index(load_rates):
    """计算Jain's Fairness Index (JFI)"""
    if not load_rates or len(load_rates) == 0:
        return 1.0
    
    # 将负载率转换为可用裕量 (1 - load_rate)
    available_margins = [1.0 - rate for rate in load_rates]
    
    # 避免除零
    if sum(available_margins) == 0:
        return 0.0
    
    # JFI = (sum(x))^2 / (n * sum(x^2))
    n = len(available_margins)
    sum_x = sum(available_margins)
    sum_x_squared = sum(x * x for x in available_margins)
    
    if sum_x_squared == 0:
        return 1.0
    
    jfi = (sum_x * sum_x) / (n * sum_x_squared)
    return max(0.0, min(1.0, jfi))  # 限制在[0,1]范围内

def measure_cpu_usage():
    """
    测量CPU使用率（用于论文对比）
    
    Returns:
        dict: {
            'cpu_bottleneck_node_percent': float,  # 瓶颈节点CPU（当前节点）
            'cpu_relay_process_percent': float,    # moq-relay-ietf进程CPU（从共享文件读取）
            'cpu_controller_process_percent': float, # controller进程CPU（从共享文件读取）
            'cpu_dash_server_process_percent': float, # DASH server进程CPU（从共享文件读取）
            'cpu_system_percent': float            # 系统整体CPU
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
        # ✅ 测量系统整体CPU使用率（宿主机）
        # 使用interval=None获取非阻塞的瞬时CPU使用率（基于上次调用的数据）
        # 注意：第一次调用需要interval>0来初始化，后续调用可以使用interval=None
        if not hasattr(measure_cpu_usage, 'initialized'):
            # 第一次调用：初始化，使用短间隔（0.1秒）
            cpu_system = psutil.cpu_percent(interval=0.1)
            measure_cpu_usage.initialized = True
        else:
            # 后续调用：非阻塞，基于上次调用的数据（interval=None）
            cpu_system = psutil.cpu_percent(interval=None)
        
        cpu_data['cpu_system_percent'] = cpu_system
        
        # ✅ 测量当前节点CPU使用率（瓶颈节点）
        # 在Mininet中，每个host是一个独立的namespace，但CPU是共享的
        # 这里测量的是系统整体CPU（在Mininet中，host的CPU使用率等于系统CPU）
        # 注意：如果需要更精确的节点级CPU，可以使用psutil的per-cpu统计
        cpu_data['cpu_bottleneck_node_percent'] = cpu_system
        
        # ✅ 从共享文件读取其他进程的CPU使用率（由Controller或其他监控脚本写入）
        # ✅ 【多节点支持】每个节点写入不同的文件（cpu_stats_r0.json, cpu_stats_r1.json, cpu_stats_r2.json）
        # 客户端读取所有文件并合并数据
        SHARED_CPU_DIR = "/tmp/mininet_shared"
        cpu_stats_files = [
            f"{SHARED_CPU_DIR}/cpu_stats_r0.json",  # r0: moq-relay-ietf
            f"{SHARED_CPU_DIR}/cpu_stats_r1.json",  # r1: controller
            f"{SHARED_CPU_DIR}/cpu_stats_r2.json",  # r2: controller
        ]
        
        # 合并所有节点的CPU统计数据
        for cpu_stats_file in cpu_stats_files:
            if os.path.exists(cpu_stats_file):
                try:
                    with open(cpu_stats_file, 'r') as f:
                        cpu_stats = json.load(f)
                        # ✅ 累加所有节点的进程CPU（因为可能有多个节点运行相同进程）
                        cpu_data['cpu_relay_process_percent'] += cpu_stats.get('moq_relay_ietf_cpu', 0.0)
                        cpu_data['cpu_controller_process_percent'] += cpu_stats.get('controller_cpu', 0.0)
                        cpu_data['cpu_dash_server_process_percent'] += cpu_stats.get('dash_server_cpu', 0.0)
                except Exception as e:
                    if not hasattr(measure_cpu_usage, 'warn_count'):
                        measure_cpu_usage.warn_count = 0
                    if measure_cpu_usage.warn_count < 3:
                        print(f"[WARN] 读取CPU统计文件 {cpu_stats_file} 失败: {e}", file=sys.stderr, flush=True)
                        measure_cpu_usage.warn_count += 1
    except Exception as e:
        if not hasattr(measure_cpu_usage, 'error_count'):
            measure_cpu_usage.error_count = 0
        if measure_cpu_usage.error_count < 3:
            print(f"[WARN] CPU测量失败: {e}", file=sys.stderr, flush=True)
            measure_cpu_usage.error_count += 1
    
    return cpu_data

def calculate_system_load_balance(relay_loads):
    """计算系统级负载均衡度 L_net"""
    if not relay_loads:
        return 1.0
    
    # 使用Jain's Fairness Index计算负载均衡度
    return calculate_jain_fairness_index(relay_loads)

# ---------- 工具函数：版本映射和base版本选择 ----------
# map_to_rep_id imported from strategies.rep_lifecycle_v2 (FULL_INDEPENDENT_REPS ladder)

def select_base_version_by_group_minimum(host_id, group_id, total_clients, decision_data=None):
    """
    根据组内所有用户的最低水平选择base版本
    
    Args:
        host_id: 当前用户ID（用于日志）
        group_id: 组ID (1, 2, 或 3) - 注意：这是1-based的组ID
        total_clients: 总用户数
        decision_data: 决策文件数据（包含group_members字段），如果为None则尝试从文件读取
    
    Returns:
        base_version: 1, 2, 或 3 (对应 base1, base2, base3)
    """
    # command124: resolve via content/env map (fail-closed under scientific mode).
    # Hardcoded RB tables live only inside resolve_rep_bitrate_mbps fail-open.
    base_bitrates = {
        1: float(resolve_rep_bitrate_mbps(1)),
        2: float(resolve_rep_bitrate_mbps(2)),
        3: float(resolve_rep_bitrate_mbps(3)),
    }
    
    # ✅ 【单一事实来源】从Controller决策文件中读取真实的组内成员列表
    group_member_ids = []
    
    # 如果decision_data未提供，尝试从决策文件读取
    if decision_data is None:
        try:
            decision_file = os.environ.get('DECISION_FILE', '/tmp/r1_decisions.json')
            if os.path.exists(decision_file):
                with open(decision_file, 'r') as f:
                    decision_data = json.load(f)
        except Exception as e:
            print(f"[WARN] h{host_id}: 无法读取决策文件: {e}，使用fallback逻辑", file=sys.stderr, flush=True)
            decision_data = None
    
    # ✅ 从决策文件的 group_members 字段获取真实的组内成员
    if decision_data and "group_members" in decision_data:
        # group_id 是 1-based，转换为字符串作为key
        group_id_str = str(group_id - 1)  # Controller中使用0-based组ID
        if group_id_str in decision_data["group_members"]:
            group_member_ids = decision_data["group_members"][group_id_str]
            print(f"[DEBUG] h{host_id}: 从决策文件读取Group {group_id}的真实成员: {group_member_ids}", file=sys.stderr, flush=True)
        else:
            # 如果找不到，尝试从用户的决策中获取
            for user_id_str, user_decision in decision_data.get("decisions", {}).items():
                if user_decision.get("md2g_group_id") == (group_id - 1):  # Controller使用0-based
                    if "md2g_group_members" in user_decision:
                        group_member_ids = user_decision["md2g_group_members"]
                        print(f"[DEBUG] h{host_id}: 从用户决策中读取Group {group_id}的成员: {group_member_ids}", file=sys.stderr, flush=True)
                        break
    
    # ✅ Fallback：如果无法从决策文件获取，使用硬编码逻辑（向后兼容）
    if not group_member_ids:
        print(f"[WARN] h{host_id}: 无法从决策文件获取Group {group_id}的成员，使用fallback逻辑（硬编码）", file=sys.stderr, flush=True)
        for member_id in range(1, total_clients + 1):
            if (member_id - 1) % 3 + 1 == group_id:
                group_member_ids.append(member_id)

    # Fail-closed: ignore phantom members outside this cell's launched hosts.
    group_member_ids = [
        int(m) for m in group_member_ids
        if 1 <= int(m) <= int(total_clients)
    ]
    
    if not group_member_ids:
        # 如果组内没有成员，默认使用base3（最保守）
        print(f"[WARN] h{host_id}: Group {group_id} 没有成员，使用base3", file=sys.stderr, flush=True)
        return 3
    
    # 读取组内所有用户的状态文件，获取最低水平
    min_throughput = float('inf')
    min_device_score = float('inf')
    
    # ✅ 【关键修复】如果读取到的throughput太低（< 2 Mbps），可能是测量时机不对，使用初始估计值
    MIN_VALID_THROUGHPUT = 2.0  # 最小有效throughput：2 Mbps
    
    for member_id in group_member_ids:
        client_state_file = _client_state_file(member_id)
        try:
            if os.path.exists(client_state_file):
                with open(client_state_file, 'r') as f:
                    state = json.load(f)
                    throughput = state.get('throughput_mbps', 0.0)
                    device_score = state.get('device_score', 1.0)
                    
                    # ✅ 【关键修复】如果throughput太低，可能是初始测量值或测量时机不对
                    # 使用B_MAX_BY_NETWORK的30%作为fallback（与初始状态文件一致）
                    if throughput < MIN_VALID_THROUGHPUT:
                        network_type = state.get('network_type', 'wifi')
                        if network_type in B_MAX_BY_NETWORK:
                            throughput = max(B_MAX_BY_NETWORK[network_type] * 0.3, MIN_VALID_THROUGHPUT)
                        else:
                            throughput = max(10.0, MIN_VALID_THROUGHPUT)  # 默认至少10 Mbps
                        print(f"[DEBUG] h{host_id}: Group {group_id} 成员 h{member_id} throughput过低（{state.get('throughput_mbps', 0.0):.2f} Mbps），使用估计值 {throughput:.2f} Mbps", file=sys.stderr, flush=True)
                    
                    min_throughput = min(min_throughput, throughput)
                    min_device_score = min(min_device_score, device_score)
        except Exception as e:
            # 如果读取失败，跳过该用户
            if member_id == host_id:
                print(f"[WARN] h{host_id}: 无法读取自己的状态文件: {e}", file=sys.stderr, flush=True)
            continue
    
    # 如果组内没有有效数据，使用保守策略（base3）
    if min_throughput == float('inf'):
        print(f"[DEBUG] h{host_id}: Group {group_id} 无有效状态数据，使用保守策略 base3", file=sys.stderr, flush=True)
        return 3
    
    # ✅ 根据组内最低水平选择base版本（综合考虑带宽和设备性能）
    # 策略：确保组内最低带宽和最低设备性能都能支持选择的base版本
    # Bitrate floors come from resolve_rep_bitrate_mbps (content/env), not RB literals.
    
    # ✅ 【关键修复】定义base版本对设备性能的要求
    base_device_requirements = {1: 0.7, 2: 0.5, 3: 0.3}  # base版本对应的最小device_score要求
    
    available_bw = min_throughput * 0.8  # 保留20%余量
    
    # 从高到低尝试，选择组内最低水平（带宽和设备性能）能够支持的最高base版本
    for base_ver in [1, 2, 3]:
        required_bw = base_bitrates[base_ver]
        required_device_score = base_device_requirements[base_ver]
        
        # ✅ 同时检查带宽和设备性能
        bw_sufficient = available_bw >= required_bw
        device_sufficient = min_device_score >= required_device_score
        
        if bw_sufficient and device_sufficient:
            print(f"[DEBUG] h{host_id}: Group {group_id} 最低水平 - throughput={min_throughput:.2f}Mbps, device_score={min_device_score:.3f}, 选择 base{base_ver} (需要带宽{required_bw:.2f}Mbps, 设备性能{required_device_score:.2f})", file=sys.stderr, flush=True)
            return base_ver
        elif not bw_sufficient and not device_sufficient:
            if base_ver == 3:
                print(f"[WARN] h{host_id}: Group {group_id} 最低带宽{min_throughput:.2f}Mbps和设备性能{min_device_score:.3f}都不足以支持base3，但仍使用base3", file=sys.stderr, flush=True)
        elif not bw_sufficient:
            if base_ver == 3:
                print(f"[WARN] h{host_id}: Group {group_id} 最低带宽{min_throughput:.2f}Mbps不足以支持base3（需要{required_bw:.2f}Mbps），但仍使用base3", file=sys.stderr, flush=True)
        elif not device_sufficient:
            if base_ver == 3:
                print(f"[WARN] h{host_id}: Group {group_id} 最低设备性能{min_device_score:.3f}不足以支持base3（需要{required_device_score:.2f}），但仍使用base3", file=sys.stderr, flush=True)
    
    # 如果连base3都支持不了，仍然返回base3（最保守）
    print(f"[WARN] h{host_id}: Group {group_id} 最低水平（带宽{min_throughput:.2f}Mbps, 设备性能{min_device_score:.3f}）不足以支持base3，但仍使用base3", file=sys.stderr, flush=True)
    return 3

def calculate_multicast_saving(group_assignments, enh_levels, num_users, num_groups=3):
    """
    计算多播节省的带宽比例（全局函数）

    LEGACY / non-scientific two-track Ro (base + enhanced deltas).
    Scientific native-9 cells must use calculate_native9_multicast_saving via
    TON_NATIVE9REP_RO + _sigcomm_native9rep_decision_enabled(). RB hardcodes below
    are intentionally retained only for this legacy path.
    
    Args:
        group_assignments: [num_users] - 每个用户的组ID（0..K-1）
        enh_levels: [num_users] - 每个用户的enh_level（0/1/2），**不是pull_enhanced（0/1）**
        num_users: 用户总数
        num_groups: 组数K
    
    Returns:
        R_o: 多播节省比例 [0, 1]
    
    注意：
        - 必须传入enh_levels（0/1/2），不能传入pull_enhanced（0/1）
        - group_base[g]：用于multicast actual（组内最低水平）
        - user_base[u]：用于unicast baseline（每个用户单独选）
    """
    # LEGACY_NON_SCIENTIFIC_RB_HARDCODE: do not use on scientific native9 Ro path.
    base_bitrates = {1: 3.07, 2: 1.79, 3: 0.87}  # base版本码率（Mbps，实测值）
    # Enhanced码率通过实测值计算：rep4-rep1=4.54-3.07=1.47, rep5-rep1=6.42-3.07=3.35
    enhanced_bitrate = 1.47  # enhanced1码率（Mbps，实测值：rep4-rep1）
    enhanced_bitrate_level2 = 3.35  # enhanced1+enhanced2总码率（Mbps，实测值：rep5-rep1）
    
    # Step 1: 计算每组的base版本（group_base[g]）- 需要读取组内用户状态
    group_base_versions = {}  # {group_id: base_version}
    for g in range(num_groups):
        group_members = [u for u in range(num_users) if group_assignments[u] == g]
        if group_members:
            # 读取组内用户状态，计算组内最低水平
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
            
            # 根据组内最低水平选择base版本
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
                    group_base_versions[g] = 3  # 默认base3
            else:
                group_base_versions[g] = 3  # 默认base3
    
    # Step 2: 计算每个用户的base版本（user_base[u]）- 用于unicast baseline
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
    
    # Step 3: 计算Unicast Baseline（如果每个用户都单播）
    # 使用user_base[u]：每个用户单独选最适合自己的base
    unicast_bytes = 0.0
    for u in range(num_users):
        user_base = user_base_versions.get(u, 3)
        unicast_bytes += base_bitrates[user_base]
        
        # ✅ 【关键】使用enh_level（0/1/2），不是pull_enhanced（0/1）
        if enh_levels[u] == 1:
            unicast_bytes += enhanced_bitrate  # base+enh1
        elif enh_levels[u] == 2:
            unicast_bytes += enhanced_bitrate_level2  # base+enh1+enh2
        # enh_levels[u] == 0时，不增加enhanced码率
    
    # Step 4: 计算Multicast Actual（多播实际发送）
    # 使用group_base[g]：组内统一，只发一次
    multicast_bytes = 0.0
    for g in range(num_groups):
        group_members = [u for u in range(num_users) if group_assignments[u] == g]
        if group_members:
            # 该组的base版本（组内统一，只发一次）
            group_base = group_base_versions.get(g, 3)
            multicast_bytes += base_bitrates[group_base]
            
            # Enhanced是单播（每个用户独立）
            for u in group_members:
                # ✅ 【关键】使用enh_level（0/1/2），不是pull_enhanced（0/1）
                if enh_levels[u] == 1:
                    multicast_bytes += enhanced_bitrate
                elif enh_levels[u] == 2:
                    multicast_bytes += enhanced_bitrate_level2
    
    # Step 5: 计算R_o（多播节省比例）
    R_o = 1.0 - (multicast_bytes / (unicast_bytes + 1e-9))
    R_o = max(0.0, min(1.0, R_o))  # 防止极端值
    
    # ✅ 【验证日志】返回详细信息用于日志输出
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


# ---------- 主逻辑 ----------
def run_client(a):
    # ✅ 【修复】确保 os 模块可用（避免 UnboundLocalError）
    # 虽然 os 在文件开头已导入，但为了确保在所有情况下都可用，这里显式引用
    _ = os.path  # 确保 os 被识别为全局变量
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
    
    # 1) 策略加载
    # ✅ 【关键说明】只有Rolling策略需要加载RL模型，其他策略（MD2G, Heuristic, Clustering, Groot, Pano）不加载模型
    # 其他策略从决策文件读取决策（由各自的controller生成）
    # 这样设计的好处：
    # 1. 避免不必要的模型加载（节省内存和启动时间）
    # 2. 保持策略独立性（每个策略使用自己的controller）
    # 3. 统一的perf.csv生成逻辑（所有策略都经过同一个中间层）
    if a.strategy == "rolling":
        # ✅ 【关键修改】Rolling策略现在在服务端（r1/r2）使用SC-DDQN模型做决策
        # 客户端不再加载模型，而是从决策文件读取决策（与MD2G策略保持一致）
        strat = None
        print(f"[INFO] h{a.host_id}: Rolling策略 - 模型在服务端(regional_relay_controller)加载，客户端从决策文件读取决策", file=sys.stderr, flush=True)
    elif a.strategy == "md2g":
        # ✅ 【关键说明】MD2G策略的模型在regional_relay_controller.py中加载（服务端）
        # MD2G是服务端策略，模型在relay端加载，客户端不加载模型
        strat = None
        print(f"[INFO] h{a.host_id}: MD2G策略 - 模型在服务端(regional_relay_controller)加载，客户端从决策文件读取决策", file=sys.stderr, flush=True)
    else:
        # ✅ 【关键说明】其他策略（Heuristic, Clustering, Groot, Pano）不加载模型
        # 这些策略从决策文件读取决策（由各自的controller生成）
        strat = None
        print(f"[INFO] h{a.host_id}: {a.strategy}策略 - 不加载模型，从决策文件读取决策", file=sys.stderr, flush=True)

    state_window, qoe_window = deque(maxlen=3), deque(maxlen=15)

    # 2) 日志
    os.makedirs(a.log_path, exist_ok=True)
    perf_log = os.path.join(a.log_path, f"client_h{a.host_id}_perf.log")
    perf_csv = os.path.join(a.log_path, f"client_h{a.host_id}_perf.csv")  # ✅ 【CSV实时写入】同时生成CSV文件
    gst_log = os.path.join(a.log_path, f"client_h{a.host_id}_gst.log")
    
    # ✅ 【CSV实时写入】CSV文件头（扩展字段，包含所有需要的指标，已删除TTLB）
    # ✅ 【Phase 0诊断】添加rep_id和buffer_level_sec字段（buffer_level_sec已存在，rep_id新增）
    # ✅ 【CPU使用率测量】添加CPU相关字段（用于论文对比）
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
    
    # ✅ 【CSV实时写入】同时创建.log和.csv文件，写入相同的CSV头
    with open(perf_log, "w") as f:
        # ✅ 统一奖励函数日志格式（对应论文 Eq.(1)）
        # R_t = λ_o*R_o + λ_q*R_q - λ_b*R_b
        # ✅ 【新增】添加 Time to Last Byte (ttlb_ms) 延迟指标
        f.write(csv_header)
    
    with open(perf_csv, "w") as f:
        # ✅ 【CSV实时写入】CSV文件与.log文件内容完全相同（都是CSV格式）
        f.write(csv_header)
    
    print(f"[INFO] h{a.host_id}: ✅ CSV文件已创建: {perf_csv}", file=sys.stderr, flush=True)
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
                "QoE → qoe（= MM26 qoe_mcast_aware；md2g/clustering/heuristic 为 R_q·R_o，"
                "rolling/pcc-dash 等为 R_q）, reward_final, quality_score(MM26口径), delay_ms"
            )
        print(
            "[METRICS] Sigcomm 作图字段（写入 client_h*_perf.csv / perf.log，供 Buffer/QoE/Stall/TTFB/Throughput/CPU 图）：\n"
            "  Buffer Level → buffer_level_sec\n"
            f"  {qoe_note}\n"
            "  Stall Time → stall_count, stall_count_inc, stall_total_sec（时序图另需 timestamp）\n"
            "  Throughput → rx_bytes + timestamp + user_id（口径同 Throughput/plot_system_throughput.py）\n"
            "  TTFB → ttfb_base_ms, ttfb_enh1_ms, ttfb_enh2_ms, ttfb_enh3_ms\n"
            "  CPU usage → cpu_bottleneck_node_percent, cpu_relay_process_percent, "
            "cpu_controller_process_percent, cpu_dash_server_process_percent, cpu_system_percent\n",
            file=sys.stderr,
            flush=True,
        )

    # 3) GStreamer 基础流
    # ✅ 【关键修复】优先使用命令行传入的relay_ip（所有策略都连接到r1/r2）
    # 如果命令行未传入relay_ip，则根据host_id分配用户到r1或r2（组播策略）
    # ✅ 【关键修复】正确处理 relay_ip 参数（包括空字符串的情况）
    if a.relay_ip and a.relay_ip.strip():
        # ✅ 使用命令行传入的relay_ip（所有策略会传入r1或r2的IP）
        relay_ip = a.relay_ip.strip()
        if relay_ip == "10.0.2.1":
            relay_name = "r0"
        elif relay_ip == "10.0.2.2":
            relay_name = "r1"
        elif relay_ip == "10.0.3.2":
            relay_name = "r2"
        else:
            relay_name = "unknown"
            print(f"[WARN] h{a.host_id}: 未知的relay_ip={relay_ip}，将使用默认分配", file=sys.stderr, flush=True)
            # 如果 relay_ip 不是预期的值，回退到默认分配
            relay_ip = assign_relay_ip(a.host_id, a.clients)
            relay_name = "r1" if relay_ip == "10.0.2.2" else "r2"
    else:
        # 默认分配：前一半用户连接到r1，后一半用户连接到r2（组播策略）
        relay_ip = assign_relay_ip(a.host_id, a.clients)
        relay_name = "r1" if relay_ip == "10.0.2.2" else "r2"
    current_relay_ip = relay_ip  # 当前使用的 relay IP
    print(f"[DEBUG] h{a.host_id}: 初始relay_ip={relay_ip} (连接到 {relay_name})", file=sys.stderr, flush=True)
    # 强制IPv4和保守设置，避免hangsrc崩溃，并添加GST_DEBUG
    # 添加系统 GStreamer 插件路径，确保能找到 hangsrc
    # 注意：a.gst_plugin_path 已经是包含 libgsthang.so 的目录
    system_gst_path = "/usr/lib/x86_64-linux-gnu/gstreamer-1.0"
    # 确保插件路径正确：优先使用传入的路径，然后是系统路径
    GST_ENV = f"GST_PLUGIN_PATH={a.gst_plugin_path}:{system_gst_path} "
    GST_ENV += "RUST_BACKTRACE=1 RUST_LOG=info "
    GST_ENV += "MOQ_HANGSRC_FORCE_IPV4=1 MOQ_HANGSRC_DISABLE_ZERO_COPY=1 "
    GST_ENV += "GST_DEBUG=hangsrc:4,pipeline:3,queue:3,decodebin:3 "
    GST_ENV += f"GST_DEBUG_FILE=/tmp/client_logs/client_h{a.host_id}_gstdebug.log "
    
    # 改进的pipeline配置：使用更健壮的配置，避免decodebin自动检测失败
    # 尝试多种pipeline配置，如果一种失败，尝试下一种
    # 注意：hangsrc输出的是编码后的数据流，需要先等待数据流开始
    # 
    # 配置优先级：SIMPLE -> MEDIUM -> FULL
    # SIMPLE: 最简形式，只测试hangsrc本身是否工作
    # MEDIUM: 添加decodebin，测试能否解码
    # FULL: 完整pipeline，包含videoconvert
    #
    # 注意：async=false 只放在 fakesink 上，用于减少异步preroll问题
    # 但这不会让pipeline在NULL状态运行，pipeline仍需要进入PAUSED/PLAYING状态
    
    # ========== 替换hangsrc为moq-sub ==========
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
    
    # ✅ 使用 MoQ dump 文件路径（不再使用 hangsrc 命名）
    moq_dump_file = f"/tmp/moq_h{a.host_id}.bin"
    
    # 验证moq-sub是否可用
    def check_moq_sub():
        """检查moq-sub工具是否可用"""
        # ✅ 【修复】显式导入subprocess，避免作用域问题
        import subprocess as sp
        try:
            if not os.path.exists(MOQ_SUB_PATH):
                print(f"[WARN] h{a.host_id}: moq-sub不存在: {MOQ_SUB_PATH}", file=sys.stderr, flush=True)
                return False
            # 测试运行
            check_cmd = [MOQ_SUB_PATH, "--help"]
            result = sp.run(check_cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"[DEBUG] h{a.host_id}: moq-sub 工具验证成功", file=sys.stderr, flush=True)
                return True
            else:
                print(f"[WARN] h{a.host_id}: moq-sub 验证失败: {result.stderr}", file=sys.stderr, flush=True)
                return False
        except Exception as e:
            print(f"[WARN] h{a.host_id}: moq-sub 检查异常: {e}", file=sys.stderr, flush=True)
            return False
    
    def build_moq_sub_cmd(track_url: str, output_file: str):
        """构建moq-sub命令
        track_url: MoQ URL (完整track路径，如 https://relay:4443/track，hang 不支持 namespace)
        output_file: 输出文件路径
        """
        # moq-sub使用https://或moql://协议
        # 如果URL是https://，直接使用；如果是moq://，转换为https://
        if track_url.startswith("moq://"):
            track_url = track_url.replace("moq://", "https://", 1)
        elif not track_url.startswith("https://"):
            # 默认添加https://
            if not track_url.startswith("http"):
                track_url = f"https://{track_url}"
        
        # ✅ 使用完整的 track URL，不需要 --track 参数
        # ✅ 确保使用 --tls-disable-verify 参数（即使设置了环境变量，也显式指定）
        cmd = [
            MOQ_SUB_PATH,
            track_url,
            "--dump", output_file,
            "--tls-disable-verify"
        ]
        
        return cmd
    
    # 先验证moq-sub工具
    moq_sub_available = check_moq_sub()
    base_p = None
    
    if not moq_sub_available:
        print(f"[ERROR] h{a.host_id}: ❌ moq-sub 工具不可用，实验终止", file=sys.stderr, flush=True)
        sys.exit(1)
    else:
        print(f"[DEBUG] h{a.host_id}: 启动 base moq-sub 流程", file=sys.stderr, flush=True)
        
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
        
        # ✅ 【关键修复：参考 simple_moq_test.py 的成功经验】使用根路径 URL + --broadcast 参数
        # ✅ 根据 relay_ip 选择对应的 relay URL
        # ⚠️ 重要：根据 simple_moq_test.py 的成功经验，应该使用：
        # - URL: https://r1.local:4443/ 或 https://r2.local:4443/ (根路径，不是 /base)
        # - --broadcast base (通过参数指定)
        # - --track video0 (通过参数指定)
        # 
        # Relay 分配逻辑：
        # - 前一半用户连接到 r1.local:4443
        # - 后一半用户连接到 r2.local:4443
        # - r1 和 r2 都运行 moq-relay 服务，监听 4443 端口
        # - r1 和 r2 从 r0 订阅数据，然后分发给各自的用户（实现组播）
        # ✅ 【关键修复】根据 relay_ip 选择对应的 relay URL
        # ⚠️ 重要：必须使用外层已确定的 relay_ip 变量，确保连接到正确的 relay
        print(f"[DEBUG] h{a.host_id}: 选择relay URL，当前relay_ip={relay_ip}", file=sys.stderr, flush=True)
        if relay_ip == "10.0.2.2":  # r1
            track_url = f"https://r1.local:4443/"
            relay_domain = "r1.local"
            relay_name_for_url = "r1"
            print(f"[DEBUG] h{a.host_id}: ✅ 连接到 r1 (relay_ip={relay_ip})", file=sys.stderr, flush=True)
        elif relay_ip == "10.0.3.2":  # r2
            track_url = f"https://r2.local:4443/"
            relay_domain = "r2.local"
            relay_name_for_url = "r2"
            print(f"[DEBUG] h{a.host_id}: ✅ 连接到 r2 (relay_ip={relay_ip})", file=sys.stderr, flush=True)
        else:
            # ⚠️ 警告：如果 relay_ip 不是 r1/r2，说明配置有问题
            print(f"[ERROR] h{a.host_id}: ❌ relay_ip={relay_ip} 不是预期的 r1/r2，回退到 r0（这不应该发生！）", file=sys.stderr, flush=True)
            # 默认回退到 r0（向后兼容，但不应该发生）
            track_url = f"https://r0.local:4443/"
            relay_domain = "r0.local"
            relay_name_for_url = "r0"
        
        # ✅ 在启动moq-sub之前，验证网络连通性
        print(f"[DEBUG] h{a.host_id}: 验证网络连通性...", file=sys.stderr, flush=True)
        
        # ✅ 根据 relay_ip 选择对应的 ping 目标
        relay_ip_to_ping = relay_ip  # 使用分配的 relay IP
        
        # 检查域名解析
        try:
            import socket
            relay_ip_resolved = socket.gethostbyname(relay_domain)
            print(f"[DEBUG] h{a.host_id}: ✅ {relay_domain} 解析为 {relay_ip_resolved}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[ERROR] h{a.host_id}: ❌ 无法解析 {relay_domain}: {e}", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: 尝试检查 /etc/hosts...", file=sys.stderr, flush=True)
            try:
                with open('/etc/hosts', 'r') as f:
                    hosts_content = f.read()
                    if relay_domain in hosts_content:
                        print(f"[DEBUG] h{a.host_id}: /etc/hosts 中包含 {relay_domain} 条目", file=sys.stderr, flush=True)
                    else:
                        print(f"[ERROR] h{a.host_id}: /etc/hosts 中未找到 {relay_domain} 条目", file=sys.stderr, flush=True)
                        # 尝试添加
                        # ✅ 【修复】使用已导入的subprocess模块
                        import subprocess as sp_check
                        sp_check.run(['sh', '-c', f'echo "{relay_ip} {relay_domain}" >> /etc/hosts'], check=False)
                        print(f"[DEBUG] h{a.host_id}: 已尝试添加 {relay_domain} ({relay_ip}) 到 /etc/hosts", file=sys.stderr, flush=True)
            except Exception as e2:
                print(f"[WARN] h{a.host_id}: 检查 /etc/hosts 失败: {e2}", file=sys.stderr, flush=True)
        
        # 检查网络连通性（ping relay IP）
        # ✅ 【修复】显式导入subprocess，避免作用域问题
        import subprocess as sp_check
        try:
            ping_result = sp_check.run(['ping', '-c', '1', '-W', '1', relay_ip_to_ping], 
                                       capture_output=True, timeout=3)
            if ping_result.returncode == 0:
                print(f"[DEBUG] h{a.host_id}: ✅ 可以 ping 通 {relay_name} ({relay_ip_to_ping})", file=sys.stderr, flush=True)
            else:
                print(f"[WARN] h{a.host_id}: ⚠️ 无法 ping 通 {relay_name} ({relay_ip_to_ping})", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[WARN] h{a.host_id}: ping 检查失败: {e}", file=sys.stderr, flush=True)
        
        # 检查端口连通性（使用nc或telnet，检查 relay 的 4443 端口）
        try:
            nc_result = sp_check.run(['nc', '-z', '-w', '1', relay_ip_to_ping, '4443'], 
                                      capture_output=True, timeout=3)
            if nc_result.returncode == 0:
                print(f"[DEBUG] h{a.host_id}: ✅ {relay_name}:4443 端口可访问", file=sys.stderr, flush=True)
            else:
                print(f"[WARN] h{a.host_id}: ⚠️ {relay_name}:4443 端口不可访问", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[WARN] h{a.host_id}: 端口检查失败（可能没有nc工具）: {e}", file=sys.stderr, flush=True)
        
        # ✅ 【PPO分组学习】从Controller决策文件读取分组（不再硬编码）
        # 先等待一段时间，让Controller生成决策文件
        print(f"[DEBUG] h{a.host_id}: 等待Controller生成决策文件（5秒）...", file=sys.stderr, flush=True)
        time.sleep(5)
        
        # 从决策文件读取Controller分配的分组
        user_group = None
        max_retries = 10
        retry_interval = 0.5
        for retry in range(max_retries):
            try:
                if os.path.exists(a.decision_file):
                    with open(a.decision_file, 'r') as f:
                        decision_data = json.load(f)
                    
                    # 读取该用户的分组信息
                    if 'decisions' in decision_data and str(a.host_id) in decision_data['decisions']:
                        user_decision = decision_data['decisions'][str(a.host_id)]
                        user_group = user_decision.get('md2g_group_id')
                        if user_group is not None:
                            user_group = int(user_group) + 1  # 转换为1-based（向后兼容select_base_version_by_group_minimum）
                            break
            except Exception as e:
                if retry == 0:
                    print(f"[WARN] h{a.host_id}: 无法读取决策文件: {e}", file=sys.stderr, flush=True)
                time.sleep(retry_interval)
        
        # 如果无法读取分组，使用fallback（向后兼容）
        if user_group is None:
            print(f"[WARN] h{a.host_id}: 无法从决策文件读取分组，使用fallback（硬编码）", file=sys.stderr, flush=True)
            user_group = (a.host_id - 1) % 3 + 1  # Fallback: 1, 2, 或 3
        
        # ✅ 在启动时选择base版本（基于组内最低水平）
        # 先等待一段时间，让组内其他用户也写入状态文件
        print(f"[DEBUG] h{a.host_id}: 等待组内其他用户状态文件（5秒）...", file=sys.stderr, flush=True)
        time.sleep(5)
        
        # 根据组内最低水平选择base版本
        base_version = select_base_version_by_group_minimum(a.host_id, user_group, a.clients)
        base_broadcast_name = f"base{base_version}"  # base1, base2, 或 base3
        print(f"[INFO] h{a.host_id}: 用户分组: Group {user_group} (来自Controller), 根据组内最低水平选择Base版本: {base_broadcast_name}", file=sys.stderr, flush=True)
        
        # moq-sub启动逻辑（使用 latency wrapper 写入延迟日志）
        print(f"[DEBUG] h{a.host_id}: 启动moq-sub订阅base流", file=sys.stderr, flush=True)
        
        # ✅ 【关键修复】使用 latency wrapper 脚本写入延迟日志
        # Fail-closed: repo-local wrapper.
        _repo = os.path.dirname(os.path.abspath(__file__))
        latency_wrapper = os.path.join(_repo, "moq_sub_with_latency.py")
        if not os.path.isfile(latency_wrapper):
            latency_wrapper = os.path.join(_repo, "Sigcomm26", "moq_sub_with_latency.py")
        latency_log_file = f"/tmp/moq_latency_h{a.host_id}_base.log"  # ✅ 与读取端路径一致
        sub_start_time = time.time()  # 记录订阅开始时间
        
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
        print(f"[INFO] h{a.host_id}: 启动moq-sub订阅base流（使用latency wrapper）", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: Track名称: {track_name} (必须与Publisher一致)", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: URL: {track_url}", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: moq-sub dump文件路径: {moq_dump_file}", file=sys.stderr, flush=True)
        print(f"[DEBUG] h{a.host_id}: 延迟日志路径: {latency_log_file} (确保与读取端路径一致)", file=sys.stderr, flush=True)
        
        # ✅ 【关键修复：大幅增加超时时间】设置环境变量，确保 moq-sub 可以正常工作
        # 问题：即使设置了 300s 超时，在 Mininet 环境下仍然可能超时断开
        # 解决：大幅增加到 1800s（30分钟），与 Publisher 和 Relay 保持一致
        env = os.environ.copy()
        env['MOQ_TLS_DISABLE_VERIFY'] = '1'  # ✅ 禁用 TLS 证书验证（解决ApplicationClosed问题）
        env['MOQ_TRANSPORT_IDLE_TIMEOUT'] = '1800s'  # ✅ 【关键修复】增加到1800s（30分钟），与Publisher和Relay保持一致
        env['QUIC_IDLE_TIMEOUT'] = '1800s'  # ✅ 【关键修复】增加QUIC空闲超时到1800s
        env['RUST_LOG'] = 'info'  # 设置日志级别
        env['RUST_BACKTRACE'] = '1'  # 启用backtrace用于调试
        
        # ✅ 【关键修复】使用 PIPE 模式 + DataDrainer，防止 Pipe 死锁
        # 必须使用 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0
        # bufsize=0 表示二进制无缓冲模式，让数据直接流出
        base_p = subprocess.Popen(
            base_cmd_wrapper,
            stdout=subprocess.PIPE,  # ✅ 使用 PIPE，让 DataDrainer 读取
            stderr=subprocess.STDOUT,  # ✅ 合并 stderr 到 stdout
            bufsize=0,  # ✅ 关键：关闭系统级缓冲，让数据直接流出
            env=env  # ✅ 传递环境变量
        )
        
        # ✅ 启动 Base 流 DataDrainer 线程
        # 持续读取进程输出，防止缓冲区阻塞（二进制块读取，不等待换行符）
        # ✅ 【TTFB/TTLB 测量】传入启动时间，用于测量真实业务延迟
        base_start_time = time.time()  # 记录 Base 流启动时间
        reader_base = DataDrainer(base_p, "Base_Stream", gst_log, start_time_epoch=base_start_time)
        reader_base.start()
        run_client._llc_base = int(base_version)
        print(f"[INFO] h{a.host_id}: ✅ Base DataDrainer 线程已启动（强力排水模式，防止Pipe死锁）", file=sys.stderr, flush=True)
        
        # 等待moq-sub建立连接并开始接收数据
        print(f"[INFO] h{a.host_id}: moq-sub已启动（PID: {base_p.pid}），等待连接和数据流...", file=sys.stderr, flush=True)
        
        # ✅ 增加等待时间：等待 publisher 完全启动（最多30秒）
        connection_timeout = 30
        connection_start = time.time()
        session_started = False
        
        while time.time() - connection_start < connection_timeout:
            # 检查进程是否还在运行
            if base_p.poll() is not None:
                exit_code = base_p.returncode
                print(f"[WARN] h{a.host_id}: moq-sub进程退出（退出码: {exit_code}），检查日志", file=sys.stderr, flush=True)
                # ✅ 【关键诊断】检查日志中的错误信息
                try:
                    with open(gst_log, "r", errors="ignore") as f:
                        log_content = f.read()
                        # 检查常见错误
                        if "ApplicationClosed" in log_content:
                            print(f"[ERROR] h{a.host_id}: ❌ ApplicationClosed错误 - 可能是证书验证失败或Track名称不匹配", file=sys.stderr, flush=True)
                            print(f"[ERROR] h{a.host_id}: 建议检查: 1) TLS验证是否禁用 2) Track名称是否与Publisher一致", file=sys.stderr, flush=True)
                        elif "TimedOut" in log_content or "timeout" in log_content.lower():
                            print(f"[ERROR] h{a.host_id}: ❌ TimedOut错误 - 可能是网络问题或UDP丢包", file=sys.stderr, flush=True)
                            print(f"[ERROR] h{a.host_id}: 建议检查: 1) 网络连通性 2) 防火墙设置 3) 带宽限制", file=sys.stderr, flush=True)
                        elif "session started" in log_content.lower() or "Session started" in log_content:
                            session_started = True
                            print(f"[INFO] h{a.host_id}: ✅ moq-sub连接成功（在日志中发现session started）✓", file=sys.stderr, flush=True)
                            break
                        # 输出最后几行日志用于调试
                        log_lines = log_content.split('\n')
                        if len(log_lines) > 5:
                            print(f"[DEBUG] h{a.host_id}: 最后5行日志:", file=sys.stderr, flush=True)
                            for line in log_lines[-5:]:
                                if line.strip():
                                    print(f"[DEBUG] h{a.host_id}: {line}", file=sys.stderr, flush=True)
                except Exception as e:
                    print(f"[WARN] h{a.host_id}: 读取日志失败: {e}", file=sys.stderr, flush=True)
                break
            
            # 检查日志中是否有session started
            try:
                with open(gst_log, "r", errors="ignore") as f:
                    log_content = f.read()
                    if "session started" in log_content.lower() or "Session started" in log_content:
                        session_started = True
                        print(f"[INFO] h{a.host_id}: ✅ moq-sub连接成功（session started）✓", file=sys.stderr, flush=True)
                        break
            except Exception:
                pass
            
            time.sleep(0.5)  # 每0.5秒检查一次
        
        if not session_started:
            print(f"[ERROR] h{a.host_id}: ❌ moq-sub未能在{connection_timeout}秒内建立连接", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: ⚠️  可能原因: 1) Publisher未启动 2) Broadcast未注册 3) Track名称不匹配", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: 建议检查: 1) Publisher是否在n0节点上运行 2) Relay日志中是否有publish=base", file=sys.stderr, flush=True)
            # 打印moq-sub日志的最后几行
            try:
                with open(gst_log, "r", errors="ignore") as f:
                    log_lines = f.readlines()
                    if log_lines:
                        print(f"[ERROR] h{a.host_id}: moq-sub日志最后10行:", file=sys.stderr, flush=True)
                        for line in log_lines[-10:]:
                            print(f"  {line.rstrip()}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[WARN] h{a.host_id}: 无法读取moq-sub日志: {e}", file=sys.stderr, flush=True)
            if base_p.poll() is None:
                base_p.terminate()
                time.sleep(0.5)
                if base_p.poll() is None:
                    base_p.kill()
            # ✅ 不要立即退出，让主循环继续运行，以便topo脚本可以收集诊断信息
            print(f"[ERROR] h{a.host_id}: moq-sub连接失败，但继续运行以便诊断", file=sys.stderr, flush=True)
            # sys.exit(1)  # 暂时注释掉，让进程继续运行
        
        # ✅ 增加等待时间：等待数据流到达（最多30秒）
        print(f"[INFO] h{a.host_id}: moq-sub连接成功，等待数据流到达...", file=sys.stderr, flush=True)
        data_timeout = 30
        data_start = time.time()
        startup_success = False
        
        while time.time() - data_start < data_timeout:
            try:
                if os.path.exists(moq_dump_file):
                    file_size = os.path.getsize(moq_dump_file)
                    if file_size > 0:
                        print(f"[INFO] h{a.host_id}: ✅ 数据流已到达（文件大小: {file_size} bytes），moq-sub成功接收数据✓", file=sys.stderr, flush=True)
                        startup_success = True
                        # ✅ 【记录订阅开始时间】用于计算 Time to Last Byte
                        if not hasattr(run_client, 'sub_start_time'):
                            run_client.sub_start_time = time.time()
                        break
            except Exception as e:
                print(f"[WARN] h{a.host_id}: 检查数据文件时出错: {e}", file=sys.stderr, flush=True)
            
            # 检查进程是否还在运行
            if base_p.poll() is not None:
                print(f"[WARN] h{a.host_id}: moq-sub进程退出（退出码: {base_p.returncode}）", file=sys.stderr, flush=True)
                break
            
            time.sleep(1)  # 每秒检查一次
        
        if not startup_success:
            print(f"[ERROR] h{a.host_id}: ❌ moq-sub在{data_timeout}秒内未收到任何数据（文件仍为0字节）", file=sys.stderr, flush=True)
            # 打印moq-sub日志的最后几行
            try:
                with open(gst_log, "r", errors="ignore") as f:
                    log_lines = f.readlines()
                    if log_lines:
                        print(f"[ERROR] h{a.host_id}: moq-sub日志最后10行:", file=sys.stderr, flush=True)
                        for line in log_lines[-10:]:
                            print(f"  {line.rstrip()}", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[WARN] h{a.host_id}: 无法读取moq-sub日志: {e}", file=sys.stderr, flush=True)
            # 检查dump文件状态
            if os.path.exists(moq_dump_file):
                file_size = os.path.getsize(moq_dump_file)
                print(f"[ERROR] h{a.host_id}: dump文件存在但大小为 {file_size} bytes", file=sys.stderr, flush=True)
            else:
                print(f"[ERROR] h{a.host_id}: dump文件不存在: {moq_dump_file}", file=sys.stderr, flush=True)
            print(f"[ERROR] h{a.host_id}: 媒体流未打通，但继续运行以便诊断", file=sys.stderr, flush=True)
            # ✅ 不要立即退出，让主循环继续运行，以便topo脚本可以收集诊断信息
            # if base_p.poll() is None:
            #     base_p.terminate()
            #     time.sleep(0.5)
            #     if base_p.poll() is None:
            #         base_p.kill()
            # sys.exit(1)  # 暂时注释掉，让进程继续运行
        
        print(f"[INFO] h{a.host_id}: ✅ moq-sub启动成功，正在接收base流数据✓", file=sys.stderr, flush=True)
        
        # ✅ 【记录订阅开始时间】用于计算 Time to Last Byte
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


    # ✅ 【动态订阅模式】只启动 Base 订阅进程，Enhanced 根据 decision 动态订阅
    # 保持单连接/单握手，根据 decision 动态开关 Enhanced 对象的订阅
    # 这样网络流量会随 decision 变化，buffer/stall/奖励都能自洽
    print(f"[DEBUG] h{a.host_id}: [动态订阅模式] 启动 Base 订阅进程，Enhanced 将根据 decision 动态订阅...", file=sys.stderr, flush=True)
    
    # ✅ 【多版本支持】Enhanced 订阅相关变量（支持订阅1-2个enhanced版本，不再有enhanced3）
    # decision = 1: 订阅base{base_version}_enhanced1 (组合流总码率)
    # decision = 2: 订阅base{base_version}_enhanced2 (组合流总码率)
    # ✅ 【只有9个视频】不再有enhanced3，decision最大只能是2
    # ✅ 【关键修复】根据base_version构建正确的组合流broadcast name
    enh_dump_files = {}  # {1: dump_file1, 2: dump_file2}
    enh_log_files = {}   # {1: log_file1, 2: log_file2}
    enh_latency_log_files = {}  # {1: latency_log1, 2: latency_log2}
    enh_track_name = "video0"  # ✅ 与Publisher一致
    if (os.environ.get("TON_TRUE_CONTENT_LAYERING") or "").strip().lower() in ("1", "true", "yes", "on"):
        enh_broadcast_names = {1: f"base{base_version}_enh1_only", 2: f"base{base_version}_enh2_only"}
    else:
        enh_broadcast_names = {1: f"base{base_version}_enhanced1", 2: f"base{base_version}_enhanced2"}  # 组合流 archive
    enh_processes = {}  # {1: enh_p1, 2: enh_p2} - Enhanced 订阅进程（动态启动/停止）
    enh_readers = {}    # {1: reader1, 2: reader2} - Enhanced DataDrainer 线程
    enh_sub_start_times = {}  # {1: start_time1, 2: start_time2}
    enh_start_times = {}      # {1: start_time1, 2: start_time2}
    last_decision = 0  # 上一次的 decision，用于检测变化
    
    # 初始化enhanced相关文件路径
    for i in [1, 2, 3]:
        enh_dump_files[i] = f"/tmp/moq_h{a.host_id}_enh{i}.bin"
        enh_log_files[i] = gst_log.replace(".log", f"_enh{i}.log")
        enh_latency_log_files[i] = f"/tmp/moq_latency_h{a.host_id}_enhanced{i}.log"
    
    # 等待 Base 流连接建立（给一些时间完成握手）
    print(f"[DEBUG] h{a.host_id}: 等待 Base 流连接建立（2秒）...", file=sys.stderr, flush=True)
    time.sleep(2)
    
    # 4) 主循环
    start = time.time()
    enh_on = False  # ✅ 【动态订阅模式】逻辑标志：Enhanced 订阅进程是否正在运行（decision==1 时为 True）
    iteration = 0   # ✅ 修复：增加循环计数器
    
    # 初始化rebuffer统计
    stall_total_sec = 0.0
    stall_count = 0
    last_debug_size = [0]
    # ✅ 【修复：stall增量计算】保存上一次的累计值，用于计算增量
    last_stall_total_sec = 0.0
    stall_inc_smooth = 0.0  # EWMA平滑后的stall增量
    
    # ✅ 【Stall 状态跟踪】用于边沿检测
    prev_in_stall = False  # 上一轮是否处于 stall 状态
    
    # ✅ 【Buffer Level 计算初始化】
    buffer_level_sec = 0.0 if _metric_v4_timeline_enabled() else 5.0
    _metric_v4 = _metric_v4_timeline_enabled()
    if _metric_v4:
        run_client.media_events = []
        run_client.media_timeline_end_sec = 0.0
        run_client.payload_ttfb_ms = None
        run_client.media_covered_sec = 0.0
        run_client._v4_stall_interval_count = 0
    last_buffer_bytes = 0  # 上一次的累计接收字节数
    last_buffer_update_time = None  # 上一次更新 buffer 的时间戳
    last_total_bitrate_bps = None  # 上一次的总码率（用于层级切换时保持连续性）
    last_decision = 0  # 上一次的 decision（用于检测层级切换）
    
    # ✅ 【Delay EMA 平滑初始化】与 DASH 策略一致，用于公平对比
    last_delay_ms = None  # 上一次的 delay_ms 值（用于 EMA 平滑）
    
    # ✅ 【被动带宽估测初始化】替代 iperf
    # ✅ 【关键修复】将时间设为 0，强制触发循环内的初始化判断
    # ❌ 错误：last_check_time = time.time() 会导致初始化判断 if last_check_time <= 0: 永远不会成立
    # ✅ 正确：last_check_time = 0.0 才能触发初始化，避免第1秒的带宽尖峰
    # ✅ 【重构】不再使用 last_total_bytes（基于文件大小），改用 rx_bytes（基于物理网卡）
    last_check_time = 0.0  # 强制初始化为0，触发循环内的初始化判断
    Bu = 0.0  # 强制初始化为 0，不要 sample_bandwidth
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
    # ✅ 【改进】添加连续零带宽计数器，避免高并发下单次delta_bytes=0就归零
    zero_delta_count = 0  # 连续delta_bytes=0的计数
    MAX_ZERO_DELTA_COUNT = 3  # 连续3次delta_bytes=0才真正归零（约1.5秒）
    # ✅ 【动态订阅模式】enh_dump_file 已在初始化阶段定义（第921行），这里不需要重新定义
    
    # ✅ 【初始化订阅开始时间】如果没有记录，使用实验开始时间
    if not hasattr(run_client, 'sub_start_time'):
        run_client.sub_start_time = start
    
    # ✅ 【关键修复】在主循环开始前就写入初始状态文件，确保控制器能立即收集到用户信息
    # 这解决了"控制器收集不到host信息"的问题
    _ensure_client_state_dir()
    client_state_file = _client_state_file(a.host_id)
    try:
        # ✅ 【关键修复】初始throughput使用合理的估计值，而不是0.0
        # 使用sample_bandwidth从数据集中采样，或者使用B_MAX_BY_NETWORK的中位数作为初始估计
        if a.network_type in B_MAX_BY_NETWORK:
            # 使用该网络类型的B_MAX的30%作为初始估计（保守估计，避免过高）
            initial_throughput = B_MAX_BY_NETWORK[a.network_type] * 0.3
        else:
            # 如果网络类型未知，使用sample_bandwidth采样
            initial_throughput = sample_bandwidth(a.network_type) if a.network_type else 10.0
        # ✅ 【关键修复】确保初始throughput至少为1 Mbps（能支持base3的0.87Mbps，实测值）
        initial_throughput = max(initial_throughput, 1.0)
        
        # 写入初始状态文件（即使还没有数据，也要写入，确保控制器能收集到用户信息）
        initial_state = {
            "host_id": a.host_id,
            "network_type": a.network_type,
            "throughput_mbps": initial_throughput,  # ✅ 使用合理的初始带宽估计，而不是0.0
            "delay_ms": 50.0,  # 默认延迟（会在第一次迭代时更新）
            "device_score": float(a.device_score),
            "last_decision_layer": 0,  # 初始只订阅Base层
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
        print(f"[DEBUG] h{a.host_id}: ✅ 已写入初始状态文件: {client_state_file} (在主循环开始前)", file=sys.stderr, flush=True)
        # 验证文件确实已创建
        if os.path.exists(client_state_file):
            file_size = os.path.getsize(client_state_file)
            print(f"[DEBUG] h{a.host_id}: ✅ 初始状态文件验证: {file_size} 字节", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[WARN] h{a.host_id}: 无法写入初始状态文件: {e}", file=sys.stderr, flush=True)

    # ✅ 【CSV实时写入】同时打开.log和.csv文件，确保实时写入
    perf_log_file = open(perf_log, "a", buffering=1)  # ✅ line buffered
    perf_csv_file = open(perf_csv, "a", buffering=1)  # ✅ line buffered，实时写入CSV
    
    try:
        print(f"[DEBUG] h{a.host_id}: 进入主循环", file=sys.stderr, flush=True)
        while time.time() - start < a.duration - 5:

            # --- 基础码率定义（所有策略通用，支持多版本） ---
            # ✅ 【动态分组支持】根据用户分组和组内最低水平动态选择base版本
            # 分组逻辑：将用户分为3组（根据 host_id % 3）
            # Base版本选择：根据组内所有用户的最低水平（带宽、设备性能）动态选择
            # - 如果组内某个用户带宽很低，整个组订阅base3（最保守）
            # - 如果组内所有用户带宽都很好，整个组订阅base1（最高质量）
            # ✅ 【PPO分组学习】从Controller决策文件读取分组（不再硬编码）
            # ✅ 【单一事实来源】读取决策文件，作为分组和组内成员的唯一来源
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
                            user_group = int(group_id_from_controller) + 1  # 转换为1-based
            except Exception as e:
                print(f"[WARN] h{a.host_id}: 读取决策文件失败: {e}", file=sys.stderr, flush=True)
            
            # Fallback：如果无法读取，使用硬编码（向后兼容）
            if user_group is None:
                user_group = (a.host_id - 1) % 3 + 1  # 1, 2, 或 3
                print(f"[WARN] h{a.host_id}: 无法从决策文件读取分组，使用fallback逻辑: group={user_group}", file=sys.stderr, flush=True)
            
            # ✅ 在主循环中定期更新base版本（每10次迭代检查一次，用于记录和日志）
            # 注意：由于base订阅已经在启动时确定，这里的检查主要用于记录和日志
            # 实际切换base版本需要重新启动订阅进程，比较复杂，暂不实现
            if not _ton_gen3_probe_arm() and iteration % 10 == 0:
                # 检查组内最低水平，确定应该使用的base版本（用于记录）
                # ✅ 【单一事实来源】传入decision_data，从真实的组内成员列表计算
                recommended_base_version = select_base_version_by_group_minimum(a.host_id, user_group, a.clients, decision_data)
                if not hasattr(run_client, 'current_base_version'):
                    run_client.current_base_version = recommended_base_version
                elif recommended_base_version != run_client.current_base_version:
                    # 如果推荐的base版本与当前不同，记录日志（但不实际切换）
                    print(f"[INFO] h{a.host_id}: Group {user_group} 组内最低水平变化，推荐base版本: base{recommended_base_version} (当前: base{run_client.current_base_version})", file=sys.stderr, flush=True)
                    # 注意：这里不实际切换，因为需要重新启动订阅进程
            elif not _ton_gen3_probe_arm():
                # 使用上一次的base_version（从全局变量获取）
                if not hasattr(run_client, 'current_base_version'):
                    # ✅ 【单一事实来源】传入decision_data，从真实的组内成员列表计算
                    run_client.current_base_version = select_base_version_by_group_minimum(a.host_id, user_group, a.clients, decision_data)
            elif not hasattr(run_client, 'current_base_version'):
                run_client.current_base_version = 3

            # ✅ 【缓冲区保护机制】buffer<threshold 时强制降级到 Base3
            # Metric V4：首个 media object 且 media_covered_sec>=1s 后才启用保护
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
            
            # 使用当前base版本（启动时确定的版本）
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
                            f"{BUFFER_PROTECTION_THRESHOLD}s, 强制降级到Base3"
                            f"（原版本: base{old_base_version}; legacy_pre_decision）",
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
            
            # ✅ 【多版本支持】根据带宽选择enhanced版本数量
            # 决策逻辑：
            # - decision = 0: 不订阅enhanced
            # - decision = 1: 订阅1个enhanced（enhanced1, 1.0 Mbps）
            # - decision = 2: 订阅2个enhanced（enhanced1 + enhanced2, 1.8 Mbps）
            # ✅ 【只有9个视频】不再有enhanced3，decision最大只能是2
            decision = 0  # 默认决策为0（不订阅enhanced）
            # ✅ 【关键修复：所有策略统一架构】所有策略（MD2G, Rolling, Heuristic, Clustering, GROOT）都连接到r1/r2
            # 这样所有策略的controller都部署在r1/r2上，与DASH实验对齐
            target_relay_ip = relay_ip  # 使用已确定的 relay_ip（r1或r2）
            base_bitrate_level = base_version - 1  # 0=base1, 1=base2, 2=base3

            # ✅ 【方案3：主动探测+初始预设】在初始阶段（前20秒）强制所有用户只订阅Base层
            # 目的：解决"鸡生蛋"问题，确保用户能跑通Base层后再优化Enhanced层
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
                # ✅ 【动态订阅模式】初始阶段：decision=0，只订阅 Base 层
                # Enhanced 订阅进程（enh_p）尚未启动，等待 decision=1 时启动
                decision = 0  # 强制不订阅 enhanced（动态订阅：不启动 Enhanced 进程）
                if iteration % 10 == 0:  # 每10次打印一次
                    print(f"[方案3] h{a.host_id}: 初始探测阶段（{elapsed_time:.1f}s/{INITIAL_PROBE_DURATION}s），强制只订阅 Base 层（Enhanced 进程未启动）", 
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
                # 正常阶段：使用策略决策
                pass  # 继续执行下面的决策逻辑

            # ✅ 【关键修改】所有策略（包括Rolling）都从共享决策文件中读取决策
            # Rolling策略现在在服务端（r1/r2）使用SC-DDQN模型做决策，客户端从决策文件读取
            decision_data = None
            # ==============================================================================
            # ✅ 支持所有策略读取决策文件
            # 
            # 决策文件格式支持：
            # 1. 新格式（优先）：{"decisions": {"1": {"pull_enhanced": bool, ...}, ...}}
            # 2. 旧格式（向后兼容）：{"layers": [0, 1, 0, ...]}
            # 
            # Controller对应关系：
            # - MD2G: regional_relay_controller.py → /tmp/r1_decisions.json 或 /tmp/r2_decisions.json
            # - Rolling: regional_relay_controller.py → /tmp/r1_decisions.json 或 /tmp/r2_decisions.json (服务端SC-DDQN决策)
            # - Heuristic: heuristic_controller_v2_refined.py → /tmp/r0_decisions.json (layers格式)
            # - Clustering: predictive_controller_v2_refined.py → /tmp/r0_decisions.json (layers格式)
            # - Groot: groot_controller.py → /tmp/r1_decisions.json 或 /tmp/r2_decisions.json (decisions格式)
            # - Pano: pano_controller.py → /tmp/r0_decisions.json (decisions格式)
            # ==============================================================================
            if a.strategy in ["md2g", "rolling", "heuristic", "clustering", "groot", "pano"]:
                # 如果文件不存在，等待并重试（最多等待5秒）
                max_retries = 10
                retry_interval = 0.5
                for retry in range(max_retries):
                    try:
                        if os.path.exists(a.decision_file):
                            # 修复：使用不同的变量名，避免与外层f冲突
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
                
                # 如果成功读取决策数据，解析决策
                if decision_data and not _scripted_mt and not _b3_only:
                    try:
                        # ==============================================================================
                        # ✅ 支持新的决策格式（按用户建议）
                        # ==============================================================================
                        # 新格式包含：decisions[user_id] = {
                        #   "pull_enhanced": bool,
                        #   "target_relay_ip": str,
                        #   "base_bitrate_level": int
                        # }
                        # ==============================================================================
                        # ✅ 【方案3：主动探测+初始预设】只有在正常阶段才使用Controller决策
                        # 初始阶段强制decision=0（已在上面设置）
                        if elapsed_time >= INITIAL_PROBE_DURATION:
                            if 'decisions' in decision_data and str(a.host_id) in decision_data['decisions']:
                                # 使用新格式
                                user_decision = decision_data['decisions'][str(a.host_id)]
                                # ✅ 【语义统一】PPO输出pull_enhanced（0/1），规则决定enh_level（0/1/2）
                                # pull_enhanced[u]: PPO的0/1输出（只要不要增强）
                                # enh_level[u]: 运行时0/1/2（由规则把pull_enhanced映射出来）
                                # rep_id[u]: 最终订阅的1..9
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
                                    
                                    # ✅ 【缓冲区保护机制】buffer 过低时强制不订阅 enhanced
                                    current_buffer = buffer_level_sec if iteration > 0 else 5.0
                                    _payload_ttfb = getattr(run_client, "payload_ttfb_ms", None)
                                    _media_covered = float(getattr(run_client, "media_covered_sec", 0.0))
                                    _buf_block, BUFFER_PROTECTION_THRESHOLD = _buffer_protection_blocks_enhanced(
                                        current_buffer,
                                        payload_ttfb_ms=_payload_ttfb,
                                        media_covered_sec=_media_covered,
                                    )
                                    
                                    if _buf_block:
                                        # 缓冲区过低，强制不订阅enhanced
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
                                                  f"强制不订阅enhanced（原决策: pull_enhanced={user_decision.get('pull_enhanced', False)}）", 
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
                                        # ✅ 【规则决定enh_level】当pull_enhanced=1时，根据bandwidth_headroom决定level
                                        enh_level = 0
                                        if pull_enhanced == 1:
                                            bandwidth_headroom = max(0, Bu - base_rate) if Bu > 0 else 0
                                            THRESHOLD_LEVEL2 = 2.0  # Mbps
                                            MIN_BUFFER_LEVEL2 = 3.0  # 秒
                                            
                                            if bandwidth_headroom >= THRESHOLD_LEVEL2 and current_buffer >= MIN_BUFFER_LEVEL2:
                                                enh_level = 2  # base+enh1+enh2
                                            else:
                                                enh_level = 1  # base+enh1
                                        # pull_enhanced=0时，enh_level=0（只base）
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
                                    
                                    # decision映射到enh_level（用于后续rep_id计算）
                                    decision = int(enh_level)
                                    
                                    # ✅ 【验证日志】输出关键决策信息
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

                                # ✅ 【关键修复：所有策略统一架构】所有策略都连接到r1/r2（忽略决策中的target_relay_ip）
                                target_relay_ip = relay_ip  # 使用已确定的 relay_ip（r1或r2）
                                base_bitrate_level = user_decision.get('base_bitrate_level', 0)
                            elif 'layers' in decision_data:
                                # 向后兼容：使用旧格式（只有 layers）
                                # command60/61: robust coerce — avoid KeyError on enh=3 and
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
                # ⚠️ 旧版本 fallback 智能增强逻辑已移除
                # ==============================================================================
                # 原因：
                # 1. 使用了未定义的 Bu 变量（Bu 在后面才测量）
                # 2. 现在 MD2G 的行为完全由 PPO 决策控制（通过 regional_relay_controller）
                # 3. 如果决策文件不存在或格式错误，decision 会保持默认值 0（不拉 enhanced）
                # ==============================================================================
                # 如果需要在决策文件缺失时使用 fallback，可以在这里添加，但需要确保 Bu 已定义
                # 当前实现：依赖 PPO 控制器生成决策，客户端只执行决策，不做二次判断
                # ==============================================================================

            # ==============================================================================
            # ✅ 【关键修改】Rolling策略现在从决策文件读取决策（服务端SC-DDQN模型决策）
            # 不再使用客户端本地模型决策，与MD2G策略保持一致
            # ==============================================================================
            # Rolling策略的决策已在上面从决策文件读取（与其他策略统一处理）

            # ==============================================================================
            # ✅ 执行决策：真正控制行为（按用户建议）
            # ==============================================================================
            # ✅ 【关键修复：所有策略统一架构】所有策略（MD2G, Rolling, Heuristic, Clustering, GROOT）都连接到r1/r2
            # relay_ip 已经在初始化时正确设置（r1或r2）
            target_relay_ip = relay_ip  # 使用已确定的 relay_ip（r1或r2）
            current_relay_ip = relay_ip  # 使用已确定的 relay_ip（r1或r2）
            print(f"[DEBUG] h{a.host_id}: {a.strategy}策略连接到 {relay_name} (relay_ip={relay_ip})", file=sys.stderr, flush=True)
            
            # 2. 根据 base_bitrate_level 调整 base 码率（如果需要）
            # base_bitrate_level: 0=low, 1=medium, 2=high
            # 这里可以根据 level 选择不同的 manifest 或 representation
            # 当前实现中，base_rate 已经根据 network_type 设置，这里可以进一步细化
            
            # ==============================================================================
            # ✅ 添加客户端行为调试打印（按用户建议）
            # ==============================================================================
            if iteration % 10 == 0:  # 每10次打印一次
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
                # 确定需要订阅的enhanced版本列表
                target_enhanced_versions = list(range(1, decision + 1)) if decision > 0 else []
                current_enhanced_versions = [v for v in [1, 2] if v in enh_processes and enh_processes[v] is not None]  # 不再有enhanced3
                
                # 停止不需要的enhanced订阅
                for version in current_enhanced_versions:
                    if version not in target_enhanced_versions:
                        print(f"[INFO] h{a.host_id}: 停止 Enhanced{version} 订阅进程...", file=sys.stderr, flush=True)
                        try:
                            if version in enh_readers and enh_readers[version]:
                                enh_readers[version].stop()
                            if version in enh_processes and enh_processes[version]:
                                enh_processes[version].terminate()
                                enh_processes[version].wait(timeout=2)
                        except Exception as e:
                            print(f"[WARN] h{a.host_id}: 停止 Enhanced{version} 订阅进程时出错: {e}", file=sys.stderr, flush=True)
                            try:
                                if version in enh_processes and enh_processes[version]:
                                    enh_processes[version].kill()
                            except:
                                pass
                        enh_processes[version] = None
                        if version in enh_readers:
                            enh_readers[version] = None
                
                # 启动需要的enhanced订阅
                for version in target_enhanced_versions:
                    if version not in enh_processes or enh_processes.get(version) is None:
                        enh_broadcast_name = enh_broadcast_names.get(
                            version, f"base{base_version}_enhanced{version}"
                        )
                        print(f"[INFO] h{a.host_id}: Decision={decision}，启动 Enhanced{version} 订阅进程（{enh_broadcast_name}）...", file=sys.stderr, flush=True)
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
                            enh_log.write(f"\n=== moq-sub {enh_broadcast_name} stream started at {time.strftime('%Y-%m-%d %H:%M:%S')} (动态订阅模式) ===\n")
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
                        print(f"[INFO] h{a.host_id}: ✅ Enhanced{version} moq-sub已启动（PID: {enh_p.pid}，动态订阅模式）", file=sys.stderr, flush=True)
                
                last_decision = decision
                enh_on = (decision > 0 and any(enh_processes.get(v) is not None for v in [1, 2]))

            # V2: maintain overlap/cancel even when decision unchanged
            if rep_lc_v2:
                _rep_lc_maintain()
            if instr_v2 is not None:
                _instr_v2_tick()

            # ==============================================================================
            # ✅ 【核心修改】被动带宽估测 (替代 iperf)
            # ==============================================================================
            # 原理：基于 dump 文件增长速率计算带宽，零干扰，完全反映真实应用层吞吐量
            # 公式：带宽 = (Δ文件大小 * 8) / (Δ时间 * 1e6) Mbps
            # ==============================================================================
            current_time = time.time()
            time_diff = current_time - last_check_time
            
            # ✅ 【关键重构】使用 rx_bytes（来自 /proc/net/dev）作为唯一数据源
            # 原因：Linux 文件系统有写入缓存，os.path.getsize() 读取的文件大小不会实时更新
            # /proc/net/dev 记录的是内核收到的每一个比特，不存在缓存延迟，绝对准确
            def get_real_rx_bytes():
                """从/proc/net/dev读取真实的累计接收字节数（Namespace隔离）"""
                try:
                    with open('/proc/net/dev', 'r') as f:
                        for line in f:
                            if 'eth0:' in line:
                                return int(line.split()[1])
                except (FileNotFoundError, IOError, ValueError, IndexError):
                    return 0
            
            # ✅ 【初始化】在第一次迭代时记录初始 rx_bytes 值
            if iteration == 0:
                if not hasattr(run_client, 'initial_rx_bytes'):
                    run_client.initial_rx_bytes = get_real_rx_bytes()
                    last_rx_bytes = run_client.initial_rx_bytes
                else:
                    last_rx_bytes = run_client.initial_rx_bytes
            else:
                # 使用上次保存的值
                if not hasattr(run_client, 'last_rx_bytes'):
                    run_client.last_rx_bytes = run_client.initial_rx_bytes if hasattr(run_client, 'initial_rx_bytes') else get_real_rx_bytes()
                last_rx_bytes = run_client.last_rx_bytes
            
            # ✅ 【获取当前 rx_bytes】
            current_rx_bytes = get_real_rx_bytes()
            
            # ✅ 【计算增量】delta_bytes = 当前累计值 - 上次累计值
            if iteration == 0:
                delta_bytes = 0  # 第一次迭代，不计算增量
                # ✅ 【Phase 0诊断】初始化历史值
                if not hasattr(run_client, 'prev_rx_bytes'):
                    run_client.prev_rx_bytes = current_rx_bytes
                if not hasattr(run_client, 'prev_buffer_level'):
                    run_client.prev_buffer_level = 5.0  # 初始buffer
                if not hasattr(run_client, 'prev_rep_id'):
                    run_client.prev_rep_id = None
                if not hasattr(run_client, 'rx_bytes_stall_count'):
                    run_client.rx_bytes_stall_count = 0  # rx_bytes不增长的连续次数
            else:
                delta_bytes = current_rx_bytes - last_rx_bytes
                # ✅ 【安全检查】如果 delta_bytes < 0，说明网卡被重置或读取错误，使用 0
                if delta_bytes < 0:
                    if iteration % 20 == 0:
                        print(f"[WARN] h{a.host_id}: delta_bytes < 0 ({delta_bytes}), 可能是网卡重置，使用 0", file=sys.stderr, flush=True)
                    delta_bytes = 0
            
            # ✅ 【Phase 0诊断】检测rx_bytes是否持续增长
            rx_bytes_growing = current_rx_bytes > run_client.prev_rx_bytes if hasattr(run_client, 'prev_rx_bytes') else True
            if not rx_bytes_growing:
                run_client.rx_bytes_stall_count += 1
            else:
                run_client.rx_bytes_stall_count = 0
            
            # ✅ 【调试】每10次迭代打印一次带宽计算信息
            if iteration % 10 == 0:
                print(f"[DEBUG] h{a.host_id}: 带宽计算 - time_diff={time_diff:.3f}s, delta_bytes={delta_bytes}, "
                      f"current_rx_bytes={current_rx_bytes}, last_rx_bytes={last_rx_bytes}, Bu={Bu:.4f}Mbps", file=sys.stderr, flush=True)
            
            # ✅ 【计算带宽 (Bu)】基于 rx_bytes 增量
            # 公式：Bu = (delta_bytes * 8) / (time_diff * 1e6) (Mbps)
            if last_check_time <= 0:
                # 第一次循环，初始化，不计算带宽
                run_client.last_rx_bytes = current_rx_bytes
                last_check_time = current_time
                Bu = 0.0  # 保持带宽为 0
            elif time_diff > 0.001:  # ✅ 降低阈值到0.001秒（1ms），确保每次迭代都能更新
                if delta_bytes > 0:
                    # 瞬时吞吐量
                    inst_bw = (delta_bytes * 8.0) / time_diff / 1e6
                    
                    # ✅ 【物理约束】单用户带宽不可能超过链路设定的 100M（或 5G 的 600M）
                    # 如果 inst_bw 超过 60M，说明是中继缓存回冲（Cache Catch-up），将其修正为 Bu
                    if inst_bw > 60.0:
                        inst_bw = Bu if Bu > 0 else 5.0  # 如果 Bu 为 0，使用保守值 5.0 Mbps
                        if iteration % 10 == 0:
                            print(f"[DEBUG] h{a.host_id}: ⚠️ 检测到带宽尖峰 {inst_bw:.2f} Mbps，已修正为中继缓存回冲", file=sys.stderr, flush=True)
                    
                    # ✅ 【EMA 平滑】与 DASH 策略一致，使用 0.3 和 0.7 的权重
                    # 首次初始化时直接使用 inst_bw，后续使用 EMA 平滑
                    # 与 DASH 完全一致，确保公平对比
                    Bu = 0.3 * Bu + 0.7 * inst_bw if Bu > 0 else inst_bw
                    # ✅ 【改进】有数据到达时，重置零带宽计数器
                    zero_delta_count = 0
                elif delta_bytes == 0:
                    # ✅ 【改进】如果 delta_bytes == 0，使用衰减策略而不是立即归零
                    # 原因：高并发下数据包到达不连续，单次delta_bytes=0不代表带宽真的为0
                    zero_delta_count += 1
                    if zero_delta_count >= MAX_ZERO_DELTA_COUNT:
                        # 连续多次无数据，真正归零
                        Bu = 0.0
                        if iteration % 10 == 0:
                            print(f"[DEBUG] h{a.host_id}: 连续{zero_delta_count}次delta_bytes=0，带宽已归零", file=sys.stderr, flush=True)
                    else:
                        # 使用衰减策略，保持历史带宽值（避免高并发下误判）
                        Bu = 0.95 * Bu
                        if iteration % 20 == 0:
                            print(f"[DEBUG] h{a.host_id}: delta_bytes=0 (连续{zero_delta_count}次)，带宽衰减至{Bu:.2f}Mbps", file=sys.stderr, flush=True)
                else:
                    # delta_bytes < 0（已在上面的安全检查中处理为0）
                    Bu = 0.0
                    zero_delta_count = 0
                
                # ✅ 【关键修复】更新状态（必须在每次迭代都更新，确保下次能正确计算delta_bytes）
                run_client.last_rx_bytes = current_rx_bytes
                last_check_time = current_time
            else:
                # ✅ 【关键修复】即使time_diff <= 0.001，也要更新last_check_time，避免累积误差
                if time_diff > 0:
                    last_check_time = current_time
                    # 也要更新 last_rx_bytes，避免下次计算时 delta_bytes 异常
                    run_client.last_rx_bytes = current_rx_bytes
            
            # ✅ 【Buffer Level 计算】基于真实下载量和视频码率
            # 原理：buffer = buffer_prev + (下载量 - 消耗量) / 码率
            # 消耗量 = 时间间隔 * 视频码率
            if last_buffer_update_time is not None:
                dt = current_time - last_buffer_update_time
            else:
                dt = a.interval  # 第一次迭代，使用默认间隔
                last_buffer_update_time = current_time
            
            # ✅ 【关键修复】使用真实接收字节数（rx_bytes）计算 buffer
            # ✅ 【关键修复】统一使用上面已经计算好的 delta_bytes，避免重复计算导致不一致
            # 注意：delta_bytes 已经在第2022行计算过了，这里直接使用，避免重复计算
            if not hasattr(run_client, 'last_buffer_rx_bytes'):
                run_client.last_buffer_rx_bytes = run_client.initial_rx_bytes if hasattr(run_client, 'initial_rx_bytes') else current_rx_bytes
            
            if iteration == 0:
                # 第一次迭代，delta_rx_bytes = 0（不更新buffer）
                delta_rx_bytes = 0
                run_client.last_buffer_rx_bytes = current_rx_bytes  # 初始化 last_buffer_rx_bytes
            else:
                # ✅ 【关键修复】统一使用 delta_bytes（已在第2022行计算），避免重复计算导致不一致
                # 这样可以确保 buffer 计算和带宽计算使用相同的增量值
                delta_rx_bytes = delta_bytes  # 直接使用上面计算好的 delta_bytes
                # ✅ 【安全检查】如果 delta_rx_bytes < 0，说明网卡被重置或读取错误，使用 0
                if delta_rx_bytes < 0:
                    if iteration % 20 == 0:
                        print(f"[WARN] h{a.host_id}: buffer计算中 delta_rx_bytes < 0 ({delta_rx_bytes}), 使用 0", file=sys.stderr, flush=True)
                    delta_rx_bytes = 0
            
            # ✅ 【码率配置】根据Relay实际供出带宽调整
            # Relay实际供出分析（从实验数据）:
            #   - r1发送给5个用户: 27.86 Mbps → 平均每个用户: 5.57 Mbps
            #   - r2发送给5个用户: 22.57 Mbps → 平均每个用户: 4.51 Mbps
            #   - 平均每个用户: 5.04 Mbps
            # 考虑到网络波动和测量误差，实际可用带宽约4.0-4.5 Mbps
            # 设置base_rate_mbps=3.5 Mbps，确保 delivery (4.0-4.5M) > consumption (3.5M)，保持buffer稳定
            base_rate_mbps = 3.5  # 3.5 Mbps，基于Relay实际供出带宽（5.04M平均）的70%余量设置
            enh_rate_mbps = 1.0
            # ✅ 【关键修复】检查enhanced是否真的在本 interval 接收数据
            # 原理：size>0 只能说明"历史上写过"，不能说明"本 interval 在收"
            # 修复：使用本 interval 的增量字节数判断
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
                # ✅ 动态订阅模式：只有 decision==1 时，enh_p 才不为 None，enh_on 才为 True
                # ✅ 记录上次 enhanced 字节数（如果不存在则初始化）
                # ✅ 【多版本支持】检查所有活跃的enhanced dump文件
                enh_bytes_total = 0
                last_enh_bytes = None
                for version in [1, 2, 3]:
                    if version in enh_processes and enh_processes[version] is not None:
                        attr_name_prev = f'enh{version}_bytes_prev'
                        if not hasattr(run_client, attr_name_prev):
                            setattr(run_client, attr_name_prev, 0)
                        # 检查enhanced{version} dump文件是否存在
                        if os.path.exists(enh_dump_files[version]):
                            enh_bytes_now = os.path.getsize(enh_dump_files[version])
                            # ✅ 计算本 interval 的增量字节数
                            enh_bytes_prev = getattr(run_client, attr_name_prev)
                            enh_delta_bytes = max(0, enh_bytes_now - enh_bytes_prev)
                            enh_bytes_total += enh_delta_bytes
                            # ✅ 只有本 interval 有增量（>0）才算真正在接收
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
                # Enhanced 订阅停止时，清除记录
                if hasattr(run_client, 'enh_bytes_prev'):
                    delattr(run_client, 'enh_bytes_prev')
            
            # ✅ 【关键修复】只有当enhanced真正在接收数据时，才使用增强码率
            # 这样可以避免在enhanced订阅刚启动但还没收到数据时，错误地增加消耗量
            current_bitrate_bps = (base_rate_mbps + (enh_rate_mbps if enh_receiving_data else 0)) * 1e6
            
            # ✅ 【Buffer 更新】使用一致的、可解释的定义（播放器常用的"秒缓冲"近似）
            # (A) 本轮下载带来的可播放时长
            # (B) buffer 更新（消费 time_diff，补充 downloaded_play_sec）
            # (C) stall 判定（当 buffer 从 >0 掉到 0）
            prev_buffer_level_sec = buffer_level_sec  # 保存更新前的buffer值，用于stall计算
            
            # ✅ 【PPO分组学习】根据base_version和enhanced_level映射到rep_id
            # 版本映射规则（按实际文件名编号：rep1-9连续）：
            # rep1-3: base only (base1, base2, base3)
            # rep4-6: base + enhanced1 (base1+enh1, base2+enh1, base3+enh1)
            # rep7-9: base + enhanced1+enhanced2 (base1+enh1+enh2, base2+enh1+enh2, base3+enh1+enh2)
            # 
            # 决策顺序（必须严格遵循）：
            # Step 1: 分组（PPO学习）→ group_id[u]
            # Step 2: Base版本（规则，基于组内最低水平）→ base_group[g]
            # Step 3: Enhanced level（PPO学习或规则）→ enhanced_level[u] ∈ {0,1,2}
            # Step 4: 映射到rep_id（V2: rendered rep; legacy: decision ladder）
            if rep_lc_v2 and rep_lc is not None and rep_lc.rendered_rep is not None:
                rep_id = current_rep_id
            else:
                rep_id = map_to_rep_id(base_version, decision)
            
            # ✅ 从环境变量 / 分 content 码率表获取 rep 总码率；科学模式 fail-closed（command110）
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
            
            # ✅ 【关键修复】使用实际的时间间隔（time_diff），而不是固定的interval
            # 如果time_diff为0或无效，使用interval作为回退
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
                    # (A) 本轮下载带来的可播放时长（legacy RX 增量 — SIGCOMM_METRIC_V4_TIMELINE=0）
                    downloaded_play_sec = (
                        (delta_rx_bytes * 8.0) / max(1.0, total_bps) if delta_rx_bytes > 0 else 0.0
                    )

                    # (B) buffer 更新（消费 actual_time_diff，补充 downloaded_play_sec）
                    buffer_level_sec = max(
                        0.0, buffer_level_sec + downloaded_play_sec - actual_time_diff
                    )

                    # ✅ 【Buffer上限限制】防止buffer无限增长，工业界公认的平衡点是30-60秒
                    MAX_BUFFER_LIMIT = 60.0
                    buffer_level_sec = min(buffer_level_sec, MAX_BUFFER_LIMIT)
                    # ✅ 保存到 run_client 对象中，确保限制生效
                    run_client.buffer_level_sec = buffer_level_sec

                    # (C) stall 判定（当 buffer 从 >0 掉到 0）
                    if prev_buffer_level_sec > 0.0 and buffer_level_sec == 0.0:
                        # 从正数变为0，判定为一次stall事件
                        if not hasattr(run_client, "stall_count_from_buffer"):
                            run_client.stall_count_from_buffer = 0
                        run_client.stall_count_from_buffer += 1
                        if iteration % 10 == 0:
                            print(
                                f"[DEBUG] h{a.host_id}: ⚠️ Buffer耗尽事件（buffer模型）！"
                                f"buffer从 {prev_buffer_level_sec:.3f}s 降至 0.0s",
                                file=sys.stderr,
                                flush=True,
                            )
            elif iteration == 0:
                # 第一次迭代，保持 buffer 初始值
                pass
            
            # ✅ 【更新状态】
            run_client.last_buffer_rx_bytes = current_rx_bytes
            last_buffer_update_time = current_time
            
            # ✅ 【已删除TTLB测量】根据用户要求，不再测量和记录TTLB

            # --- 真实延迟测量（实时测量每个 interval 的延迟） ---
            # ✅ 【关键修复】delay_ms 应该是"最近一个窗口内的端到端业务时延"
            # 原理：使用当前时间与最近一次收到数据的时间差（last_data_ts）
            # TTFB 只能作为连接建立/首帧启动延迟指标，不该当作 steady-state delay
            # ✅ 【健壮性】当 last_data_ts 未初始化时，delay_ms 不应该触发 stall
            dly = None  # 初始化为 None，表示未计算或无效
            dly_valid = False  # 标记 delay_ms 是否有效（可用于 stall 判定）
            
            if hasattr(reader_base, 'last_data_ts') and reader_base.last_data_ts is not None:
                # ✅ 使用最近数据到达时间计算实时延迟
                data_arrival_interval_ms = (current_time - reader_base.last_data_ts) * 1000.0
                # ✅ 限制延迟范围：如果超过 500ms，说明可能数据流中断，使用 EWMA 间隔作为估计
                if data_arrival_interval_ms > 500.0 and hasattr(reader_base, 'last_read_dt_ms') and reader_base.last_read_dt_ms is not None:
                    data_arrival_interval_ms = reader_base.last_read_dt_ms  # 使用最近一次 read 间隔作为估计
                # ✅ 限制延迟范围：最小 1ms，最大 500ms（与 DASH 一致）
                data_arrival_interval_ms = max(1.0, min(500.0, data_arrival_interval_ms))
                
                # ✅ 【EMA 平滑】与 DASH 策略一致，使用 0.3 和 0.7 的权重（公平对比）
                # 理由：delay_ms 是到达间隔类信号，本身会有抖动；平滑属于"测量滤波"，不是策略优势
                if iteration == 1 or last_delay_ms is None:
                    dly = data_arrival_interval_ms
                else:
                    # ✅ EMA 平滑：delay_ms = 0.3 * last_delay_ms + 0.7 * data_arrival_interval_ms
                    dly = 0.3 * last_delay_ms + 0.7 * data_arrival_interval_ms
                
                # ✅ 更新 last_delay_ms 用于下次迭代的 EMA 平滑
                last_delay_ms = dly
                dly_valid = True  # delay_ms 有效，可用于 stall 判定
            elif hasattr(reader_base, 'ttfb_ms') and reader_base.ttfb_ms is not None:
                # ✅ 回退：如果还没有收到数据，使用 TTFB 作为初始延迟
                dly = reader_base.ttfb_ms
                # ✅ 更新 last_delay_ms（首次初始化）
                if last_delay_ms is None:
                    last_delay_ms = dly
                dly_valid = False  # TTFB 不能用于 stall 判定（启动时延迟）
            elif current_rx_bytes > (run_client.initial_rx_bytes if hasattr(run_client, 'initial_rx_bytes') else 0) and hasattr(run_client, 'sub_start_time'):
                # ✅ 回退：使用当前时间与订阅开始时间的差值作为近似
                data_arrival_interval_ms = (current_time - run_client.sub_start_time) * 1000.0
                data_arrival_interval_ms = max(1.0, min(500.0, data_arrival_interval_ms))  # 限制范围
                
                # ✅ 【EMA 平滑】与 DASH 策略一致
                if iteration == 1 or last_delay_ms is None:
                    dly = data_arrival_interval_ms
                else:
                    dly = 0.3 * last_delay_ms + 0.7 * data_arrival_interval_ms
                
                # ✅ 更新 last_delay_ms
                last_delay_ms = dly
                dly_valid = False  # 回退值不能用于 stall 判定
            else:
                # 还没收到首包（启动瞬间），给一个合理的初始值
                dly = 50.0
                # ✅ 更新 last_delay_ms（首次初始化）
                if last_delay_ms is None:
                    last_delay_ms = dly
                dly_valid = False  # 初始值不能用于 stall 判定
                if iteration % 10 == 0:  # 每10次打印一次
                    print(f"[DEBUG] h{a.host_id}: ⏳ 等待首包到达，使用初始延迟值: {dly:.2f} ms", file=sys.stderr, flush=True)
            
            # ✅ 【Stall 检测】使用边沿检测，只在从 not in_stall 进入 in_stall 时触发 stall_count_inc
            # ✅ 【Stall 判定条件】delay_ms > 500 或 buffer_level_sec <= 0（与 delay_ms 定义强一致）
            # ✅ 【健壮性】只有当累计 rx_bytes > 0 后才启用 stall 判定（避免启动时误判）
            stall_count_inc = 0  # 本轮的stall增量（边沿检测：只在进入stall时=1）
            stall_sec_inc = 0.0  # 本轮的stall时长增量（持续stall时每轮累加）

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
                # ✅ 【健壮性检查】只有当累计 rx_bytes > 0 后才启用 stall 判定
                has_received_data = current_rx_bytes > (
                    run_client.initial_rx_bytes if hasattr(run_client, "initial_rx_bytes") else 0
                )

                if iteration > 0 and actual_time_diff > 0 and has_received_data:
                    # ✅ 【Stall 判定】delay_ms > 500 或 buffer_level_sec <= 0
                    in_stall = False

                    # 条件1：buffer_level_sec <= 0
                    if buffer_level_sec <= 0.0:
                        in_stall = True

                    # 条件2：delay_ms > 500（表示断流），但只有当 delay_ms 有效时才使用
                    if dly_valid and dly is not None and dly > 500.0:
                        in_stall = True

                    # ✅ 【边沿检测】只有当从 not in_stall 进入 in_stall 时才触发 stall_count_inc
                    if not prev_in_stall and in_stall:
                        # 从非stall状态进入stall状态，触发一次stall事件
                        stall_count_inc = 1
                        stall_count += stall_count_inc
                        if iteration % 10 == 0:
                            stall_reason = []
                            if buffer_level_sec <= 0.0:
                                stall_reason.append(f"buffer={buffer_level_sec:.3f}s")
                            if dly_valid and dly is not None and dly > 500.0:
                                stall_reason.append(f"delay={dly:.2f}ms")
                            print(
                                f"[DEBUG] h{a.host_id}: ⚠️ 进入Stall状态！{' & '.join(stall_reason)}, "
                                f"stall_count_inc={stall_count_inc}, stall_count={stall_count}",
                                file=sys.stderr,
                                flush=True,
                            )
                    elif prev_in_stall and not in_stall:
                        # 从stall状态恢复到非stall状态
                        if iteration % 10 == 0:
                            print(
                                f"[DEBUG] h{a.host_id}: ✅ 退出Stall状态！"
                                f"buffer={buffer_level_sec:.3f}s, delay={dly:.2f}ms",
                                file=sys.stderr,
                                flush=True,
                            )

                    # ✅ 【Stall 时长累加】如果处于 stall 状态，每轮累加 actual_time_diff
                    if in_stall:
                        stall_sec_inc = actual_time_diff
                        stall_total_sec += stall_sec_inc

                    # ✅ 【更新 prev_in_stall 状态】
                    prev_in_stall = in_stall

                    # ✅ 【Phase 0诊断】打印每个client的关键指标，判断是"没流"还是"带宽不够"
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
                                    f"⚠️ rx_bytes不增长(连续{run_client.rx_bytes_stall_count}次)"
                                )
                            else:
                                diagnosis_status.append(f"✅ rx_bytes增长+{rx_bytes_delta}字节")
                            if buffer_stuck_at_zero:
                                diagnosis_status.append("⚠️ buffer长期卡在0")
                            elif buffer_level_sec <= 0.0:
                                diagnosis_status.append("⚠️ buffer=0(刚耗尽)")
                            else:
                                diagnosis_status.append(f"✅ buffer={buffer_level_sec:.3f}s")
                            if in_stall_now:
                                diagnosis_status.append("⚠️ 处于stall状态")
                            if rep_id_changed:
                                diagnosis_status.append(
                                    f"🔄 rep_id变化: {run_client.prev_rep_id}→{rep_id}"
                                )
                            else:
                                diagnosis_status.append(f"rep_id={rep_id}")
                            if not rx_bytes_changed and run_client.rx_bytes_stall_count >= 3:
                                conclusion = "🔴 数据面断流：rx_bytes长时间不增长"
                            elif buffer_stuck_at_zero and not rx_bytes_changed:
                                conclusion = (
                                    "🔴 数据面断流+保护机制失效：buffer卡在0且rx_bytes不增长"
                                )
                            elif buffer_stuck_at_zero:
                                conclusion = "🟡 保护机制失效：buffer卡在0但rx_bytes仍在增长"
                            elif in_stall_now and Bu < 1.0:
                                conclusion = "🟡 带宽不足：stall且Bu<1Mbps"
                            elif in_stall_now:
                                conclusion = "🟡 可能带宽不足：stall但Bu正常"
                            else:
                                conclusion = "✅ 正常"
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
                                        f"[DEBUG] h{a.host_id}: ⚠️ GStreamer日志检测到额外rebuffer！"
                                        f"stall_sec_inc={stall_sec_inc_gst:.3f}s, "
                                        f"stall_count_inc={stall_cnt_inc_gst}, stall_count={stall_count}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                else:
                    # 第一次迭代或未收到数据，不计算stall，但保持 prev_in_stall 状态
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
                            f"rep_id={rep_id}, 状态: 等待首包到达",
                            file=sys.stderr,
                            flush=True,
                        )

                    run_client.prev_rx_bytes = current_rx_bytes
                    run_client.prev_buffer_level = buffer_level_sec
                    run_client.prev_rep_id = rep_id
            
            # ✅ 【确保 dly 有值】如果 dly 为 None，使用默认值（用于日志记录）
            if dly is None:
                dly = 50.0
            
            # ✅ 保存当前 buffer 用于下次 RTT 估计
            if not hasattr(run_client, 'last_buffer_level'):
                run_client.last_buffer_level = buffer_level_sec
            run_client.last_buffer_level = buffer_level_sec
            
            # ✅ 【已删除】不再使用 Ping 测量延迟，因为：
            # 1. Ping 在 Mininet 环境下经常失败（路由问题、CPU 忙）
            # 2. Ping 只能测量网络层延迟，无法反映应用层处理延迟
            # 3. TTFB 是真实业务延迟，包含所有耗时，更适合 QoE 评估
            # 
            # 旧代码（已删除）：
            # iface = nic_name(a.host_id)
            # server_ip = "10.0.1.100"  # n0 的 IP
            # dly = ping_rtt(server_ip, iface=iface)
            # if dly < 0 or dly > 500:
            #     dly = 50.0  # 使用默认值
            # print(f"[DEBUG] h{a.host_id} measured end-to-end delay (client→n0): {dly:.2f}ms for {a.network_type}", file=sys.stderr, flush=True)

            # --- 设备性能 ---
            dev_score = float(a.device_score)
            dev = df_dev.sample(1).iloc[0]
            gpu = dev['GPU Clock (MHz)'] / df_dev['GPU Clock (MHz)'].max()
            ram = dev['RAM(GB)'] / df_dev['RAM(GB)'].max()
            refresh = dev['Refresh Rate (Hz)'] / df_dev['Refresh Rate (Hz)'].max()
            # 修复列名解析Bug：使用正确的列名
            resolution_str = str(dev['Resolution (per eye)'])
            res_w = int(resolution_str.split('×')[0]) if '×' in resolution_str else 1920
            res = res_w / df_dev['Resolution (per eye)'].apply(
                lambda x: int(str(x).split('×')[0]) if '×' in str(x) else 1920
            ).max()

            # --- 渲染质量 (Qr) ---
            Qr = min(1.2, max(0.2,
                (0.4 * dev_score + 0.3 * gpu + 0.2 * ram + 0.1 * refresh + 0.2 * res)
                * gpu_boost(gpu)
            ))

            # --- 解析rebuffer信息 ---
            debug_log_path = f"/tmp/client_logs/client_h{a.host_id}_gstdebug.log"
            stall_sec_inc, stall_cnt_inc = parse_rebuffer_from_debug(debug_log_path, last_debug_size)
            stall_total_sec += stall_sec_inc
            stall_count += stall_cnt_inc
            
            # --- 系统级负载均衡计算 ---
            # 从真实relay监控获取负载率（如果可用），否则使用默认值
            # ⚠️ 注意：默认值仅用于调试/fallback，正式实验应从 /tmp/relay_loads.json 读取真实负载
            # 默认值故意设置得明显（便于识别fallback情况）
            DEFAULT_OFF_LOADS = [0.9]  # 单relay高负载（仅用于debug/图表，不参与QoE计算）
            DEFAULT_ON_LOADS = [0.2, 0.5, 0.8, 0.3]  # 仅占位，不代表真实负载
            
            def read_relay_loads_from_json():
                """
                从 /tmp/relay_loads.json 读取真实 relay 负载
                
                Returns:
                    list: relay 负载列表，如果读取失败返回 None
                """
                try:
                    with open("/tmp/relay_loads.json", "r") as f:
                        data = json.load(f)
                        loads = data.get("loads", None)
                        
                        # 验证数据格式
                        if not loads or not isinstance(loads, list) or len(loads) == 0:
                            raise ValueError("Invalid loads in JSON: empty or not a list")
                        
                        # 验证负载值范围
                        if not all(0.0 <= load <= 1.0 for load in loads):
                            raise ValueError("Invalid loads in JSON: values not in [0, 1]")
                        
                        return loads
                        
                except (IOError, json.JSONDecodeError, KeyError, ValueError) as e:
                    # 读取失败，返回 None（由调用者决定是否使用 fallback）
                    if iteration % 20 == 0:  # 减少打印频率
                        print(f"[WARN] h{a.host_id}: Failed to read relay_loads.json: {e}", 
                              file=sys.stderr, flush=True)
                    return None
            
            # ==============================================================================
            # ✅ 修复 JFI 计算：ON 模式从 relay_loads.json 读取真实负载并计算 JFI
            # ==============================================================================
            if a.federation == 'on':
                # Federation ON: 从真实监控读取，计算真实 JFI
                relay_loads = read_relay_loads_from_json()
                
                if relay_loads and len(relay_loads) > 0:
                    # 成功读取真实负载，计算真实 JFI
                    # 过滤掉过小的负载值（可能是测量误差）
                    valid_loads = [l for l in relay_loads if l >= 0.001]  # 至少0.1%的负载才有效
                    if len(valid_loads) > 0:
                        load_balance_jfi = calculate_system_load_balance(valid_loads)
                        # 每次迭代都打印（用于验证JFI是否真的在变化）
                        print(f"[JFI] h{a.host_id}: ON模式真实JFI={load_balance_jfi:.4f}, relay_loads={valid_loads}", 
                              file=sys.stderr, flush=True)
                    else:
                        # 所有负载值都太小，使用fallback
                        load_balance_jfi = 1.0
                        if iteration % 20 == 0:
                            print(f"[WARN] h{a.host_id}: ON模式所有负载值过小，使用fallback JFI=1.0", 
                                  file=sys.stderr, flush=True)
                else:
                    # 读取失败，使用 fallback（但应该很少发生）
                    load_balance_jfi = 1.0
                    if iteration % 20 == 0:  # 减少打印频率
                        print(f"[WARN] h{a.host_id}: ON模式使用fallback JFI=1.0 (relay_loads.json读取失败)", 
                              file=sys.stderr, flush=True)
            else:
                # Federation OFF: 单relay，负载集中，JFI=1.0（不参与QoE计算，因为w_ln=0）
                relay_loads = [0.8]  # 单relay高负载（仅用于占位）
                load_balance_jfi = 1.0  # OFF模式固定为1.0
            
            # --- 方案B: 系统级负载均衡QoE公式 ---
            # QoE = w_r*Qr + w_b*Rb + w_ln*L_net - w_d*D - w_f*F
            Rq = 5.0 * (math.log1p(Qr) / math.log(2.5))
            
            # 使用按网络类型分组的B_MAX进行Rb归一化
            network_b_max = B_MAX_BY_NETWORK.get(a.network_type, B_MAX)
            Rb = math.log1p(Bu) / math.log1p(network_b_max + EPS)
            delay_penalty = dly / 200.0
            rebuffer_penalty = min(1.0, stall_count * 0.1)  # 基于stall次数
            
            # ==============================================================================
            # ✅ 统一奖励函数：R_t = λ_o*R_o + λ_q*R_q - λ_b*R_b
            # ==============================================================================
            # 根据论文 Eq.(1)，所有策略使用相同的统一奖励函数
            # 其中：
            #   R_o: Grouping Efficiency（分组效率）
            #   R_q: User Perceived Quality（用户感知质量）
            #   R_b: Bandwidth Efficiency Penalty（带宽效率惩罚）
            # ==============================================================================
            
            lambda_o, lambda_q, lambda_b = _parse_reward_lambdas_from_env()
            
            # --- R_q ---
            # SIGCOMM paper Eq.9: R_q = α·Q_s − β·D_n − γ·S_n with α=1, β=γ=0.5,
            # Q_s ∈ {0.4,0.6,0.8,1.0} ↔ Q1–Q4. Enable with SIGCOMM_QOE_EQ9=1.
            # Default remains MM26 five-component for legacy callers.
            _use_eq9 = os.environ.get("SIGCOMM_QOE_EQ9", "").strip().lower() in ("1", "true", "yes", "on")
            if _use_eq9:
                # Table 1: final executed Rep ID → Q_s (Q1=0.4 … Q4=1.0). Never MM26 shortcut.
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
                # MM26 五分量 QoE（与 MM26/dispatch_strategy_enhanced_unified_NOSSDAV.py 一致）
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
            # ✅ 【关键修复】连接到真实的分组逻辑，而不是使用固定值
            # 尝试从控制器决策文件中读取真实的分组信息
            grouping_id = a.host_id  # 默认使用 host_id
            grouping_size = 1  # 默认单用户组
            
            # ✅ 【强制分组优化】如果FOV分组未启用，按relay分组（至少共享Base层）
            # 前一半用户（r1）共享grouping_id=1，后一半用户（r2）共享grouping_id=2
            # 这样可以实现Base层的组播共享，减少带宽消耗
            r1_sub_count = a.clients // 2
            if a.host_id <= r1_sub_count:
                # r1分支：所有用户共享grouping_id=1
                default_grouping_id = 1
                default_grouping_size = r1_sub_count
            else:
                # r2分支：所有用户共享grouping_id=2
                default_grouping_id = 2
                default_grouping_size = a.clients - r1_sub_count
            
            try:
                # 尝试读取控制器决策文件，获取真实的分组信息
                # 优先使用r1/r2的决策文件（根据用户连接的relay）
                # ✅ 【关键修复】使用已确定的relay_ip（可能来自命令行参数或默认分配）
                # 注意：这里使用外层已确定的relay_ip变量，而不是重新调用assign_relay_ip
                if relay_ip == "10.0.2.2":  # r1
                    decision_file = "/tmp/r1_decisions.json"
                elif relay_ip == "10.0.3.2":  # r2
                    decision_file = "/tmp/r2_decisions.json"
                else:
                    # 所有策略都连接到r1/r2，使用对应的决策文件
                    decision_file = "/tmp/r1_decisions.json"
                
                if os.path.exists(decision_file):
                    with open(decision_file, 'r') as f:
                        decisions_data = json.load(f)
                    # ✅ 【关键修复】决策文件格式可能是 {"decisions": {"1": {...}, "2": {...}}} 或 {"h1": {...}, "h2": {...}}
                    # 需要兼容两种格式
                    if "decisions" in decisions_data:
                        # 格式1：{"decisions": {"1": {...}, "2": {...}}}
                        decisions_dict = decisions_data["decisions"]
                        user_key = str(a.host_id)  # 使用数字字符串作为键
                    else:
                        # 格式2：{"h1": {...}, "h2": {...}}
                        decisions_dict = decisions_data
                        user_key = f"h{a.host_id}"  # 使用 "h1", "h2" 格式
                    
                    if user_key in decisions_dict:
                        user_decision = decisions_dict[user_key]
                        # ✅ 【关键修复】优先使用md2g_group_id（Controller实际使用的字段）
                        # Controller使用0-based组ID，需要转换为1-based
                        if "md2g_group_id" in user_decision:
                            grouping_id = user_decision["md2g_group_id"] + 1  # 转换为1-based
                            if "md2g_group_size" in user_decision:
                                grouping_size = user_decision["md2g_group_size"]
                            else:
                                grouping_size = len(user_decision.get("md2g_group_members", []))
                            print(f"[DEBUG] h{a.host_id}: 从决策文件读取MD2G分组信息: group_id={grouping_id}, size={grouping_size}", file=sys.stderr, flush=True)
                        # ✅ 兼容FOV分组（如果存在）
                        elif "fov_group_id" in user_decision:
                            grouping_id = user_decision["fov_group_id"]
                            if "fov_group_size" in user_decision:
                                grouping_size = user_decision["fov_group_size"]
                            else:
                                grouping_size = 1
                        # ✅ 如果决策中没有分组信息，使用按relay分组的默认值
                        else:
                            grouping_id = default_grouping_id
                            grouping_size = default_grouping_size
                    else:
                        # 用户不在决策文件中，使用按relay分组的默认值
                        grouping_id = default_grouping_id
                        grouping_size = default_grouping_size
                else:
                    # 决策文件不存在，使用按relay分组的默认值
                    grouping_id = default_grouping_id
                    grouping_size = default_grouping_size
            except Exception as e:
                # 如果读取失败，使用按relay分组的默认值
                grouping_id = default_grouping_id
                grouping_size = default_grouping_size
                if iteration % 20 == 0:  # 每20次打印一次，避免日志过多
                    print(f"[DEBUG] h{a.host_id}: 无法读取分组信息: {e}，使用按relay分组（grouping_id={grouping_id}, size={grouping_size}）", file=sys.stderr, flush=True)
            
            # ✅ 【PPO分组学习】计算R_o：基于显式多播节省计算
            # 使用calculate_multicast_saving函数计算多播节省的带宽比例
            
            # ✅ 【修复】计算当前用户订阅的rep_id（V2: rendered; legacy: ladder）
            if not (rep_lc_v2 and rep_lc is not None and rep_lc.rendered_rep is not None):
                current_rep_id = map_to_rep_id(base_version, decision)
            
            # ✅ 【PPO分组学习】计算R_o：基于显式多播节省计算
            # 使用全局函数calculate_multicast_saving（定义在文件开头）
            
            # ✅ 【PPO分组学习】从决策文件读取所有用户的分组和enh_level（0/1/2）
            total_users = a.clients
            group_assignments = np.zeros(total_users, dtype=np.int32)
            enh_levels = np.zeros(total_users, dtype=np.int32)  # ✅ 【语义统一】使用enh_levels，不是enhanced_decisions
            selected_reps = np.zeros(total_users, dtype=np.int32)
            
            try:
                # 使用a.decision_file（已在前面确定）
                decision_file = a.decision_file
                if os.path.exists(decision_file):
                    with open(decision_file, 'r') as f:
                        all_decisions = json.load(f)
                    
                    # ✅ 【语义统一】读取所有用户的分组和enh_level（0/1/2，不是pull_enhanced）
                    # 注意：R_o计算必须用enh_level，不能用pull_enhanced
                    for user_id_str, user_decision in all_decisions.get('decisions', {}).items():
                        user_id = int(user_id_str)
                        if 1 <= user_id <= total_users:
                            user_idx = user_id - 1
                            # 读取分组（范围[0..K-1]）
                            group_id = user_decision.get('md2g_group_id', (user_id - 1) % 3)
                            group_assignments[user_idx] = int(group_id)
                            
                            # ✅ 【关键修复】读取enh_level（0/1/2），不是pull_enhanced（0/1）
                            # 如果Controller提供了enhanced_level，直接使用
                            # 否则从pull_enhanced推导（但这是fallback，正常应该由Controller计算好）
                            enh_level = user_decision.get('enhanced_level', None)
                            if enh_level is None:
                                # Fallback：从pull_enhanced推导（假设level=1）
                                pull_enhanced = user_decision.get('pull_enhanced', False)
                                enh_level = 1 if pull_enhanced else 0
                            enh_levels[user_idx] = int(enh_level)  # 确保是0/1/2
                            try:
                                srep = user_decision.get("selected_rep", user_decision.get("rep_id"))
                                selected_reps[user_idx] = int(srep) if srep is not None else 0
                            except Exception:
                                selected_reps[user_idx] = 0
            except Exception as e:
                # 读取失败，使用fallback（硬编码分组）
                if iteration % 20 == 0:
                    print(f"[DEBUG] h{a.host_id}: 无法读取决策文件计算R_o: {e}，使用fallback", file=sys.stderr, flush=True)
                for u in range(total_users):
                    group_assignments[u] = u % 3
                    enh_levels[u] = 0
                    selected_reps[u] = 0
            
            # ✅ 计算R_o（多播节省比例）
            # command115/124: native-9 Ro when TON_NATIVE9REP_RO=1 and scientific
            # decision gate (SIGCOMM_NATIVE9REP_DECISION or MD2G alias) — not MD2G-only.
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
                
                # ✅ 【验证日志】输出R_o计算的详细信息（每20次迭代）
                if iteration % 20 == 0:
                    print(f"[Client] h{a.host_id}: R_o计算 - unicast_baseline={unicast_baseline:.2f}Mbps, "
                          f"multicast_actual={multicast_actual:.2f}Mbps, R_o={R_o:.4f}", 
                          file=sys.stderr, flush=True)
            except Exception as e:
                # 如果计算失败，使用fallback（基于rep订阅人数）
                if iteration % 20 == 0:
                    print(f"[DEBUG] h{a.host_id}: calculate_multicast_saving失败: {e}，使用fallback R_o", file=sys.stderr, flush=True)
                # Fallback: 简单的rep订阅人数比例
                same_rep_users = 1
                try:
                    decision_file = a.decision_file
                    if os.path.exists(decision_file):
                        with open(decision_file, 'r') as f:
                            all_decisions = json.load(f)
                        rep_subscription_count = {}
                        for user_id_str, user_decision in all_decisions.get('decisions', {}).items():
                            user_base = user_decision.get('base_version', base_version)
                            # ✅ 【语义统一】读取enh_level（0/1/2），不是pull_enhanced（0/1）
                            user_enh_level = user_decision.get('enhanced_level', decision)
                            if user_enh_level is None:
                                # Fallback：从pull_enhanced推导
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
                print(f"[DEBUG] h{a.host_id}: R_o={R_o:.4f} (多播节省比例)", file=sys.stderr, flush=True)
            
            # --- R_b: Bandwidth Efficiency Penalty ---
            # ✅ 【统一对齐】与 DASH 完全一致：R_b = 1.0 - (Bu / Target_Bitrate)
            # ✅ 【对齐DASH】直接使用rep_id对应的总码率，不单独计算base+enhanced
            # ✅ 【PPO分组学习】使用新的映射函数计算rep_id
            if rep_lc_v2 and rep_lc is not None and rep_lc.rendered_rep is not None:
                rep_id = current_rep_id
            else:
                rep_id = map_to_rep_id(base_version, decision)
            
            # ✅ 分 content 码率；科学模式缺 map/env 则 abort（command110）
            TARGET_BITRATE = resolve_rep_bitrate_mbps(rep_id)
            
            if Bu > 0 and TARGET_BITRATE > 0:
                bandwidth_utilization = min(1.0, Bu / TARGET_BITRATE)
                # R_b: 利用率越高，惩罚越小（连续值：0.0 到 1.0）
                # 例如：Bu=1.0 Mbps, Target=4.5 Mbps → util=0.22 → R_b=0.78（高惩罚，带宽浪费）
                #      Bu=3.5 Mbps, Target=4.5 Mbps → util=0.78 → R_b=0.22（低惩罚，带宽充分利用）
                R_b = 1.0 - bandwidth_utilization
                # ✅ 确保 R_b 在合理范围内（0.0 到 1.0）
                R_b = max(0.0, min(1.0, R_b))
            else:
                # ✅ 当Bu=0时，给一个中等惩罚（与DASH一致）
                R_b = 0.5  # 中等惩罚，表示"带宽未充分利用但也不完全浪费"
            
            # --- Load Balance JFI（仅用于记录，不用于 reward 计算）---
            # ✅ 【关键修复】确保 load_balance_jfi 连接到真实的分组逻辑
            # 初始化 load_balance_jfi（确保在所有分支中都有定义）
            if 'load_balance_jfi' not in locals():
                load_balance_jfi = 1.0  # 默认值
            
            if a.federation == 'off':
                # ✅ 【关键修复】确保 load_balance_jfi 实时更新，而不是固定值
                # OFF模式下，如果没有分组，JFI 应该接近 1.0（单播，负载均衡）
                # 如果有分组，应该基于分组大小计算 JFI
                if grouping_size > 1:
                    # 多播组内负载均衡：假设组内用户负载均匀分布
                    load_balance_jfi = 0.9 + 0.1 * (1.0 / grouping_size)  # 分组越大，JFI 越接近 1.0
                else:
                    load_balance_jfi = 1.0  # 单播，完美负载均衡
            else:
                # ✅ load_balance_jfi 已经在上面从真实relay监控读取（第1794行）
                # 如果未读取到，保持默认值 1.0
                # ✅ 【关键修复】确保 load_balance_jfi 在每个 iteration 都重新计算
                if 'load_balance_jfi' not in locals() or load_balance_jfi is None:
                    load_balance_jfi = 1.0  # 默认值
            
            # --- 统一奖励函数计算（移除 R_l 项）---
            reward_final = lambda_o * R_o + lambda_q * R_q - lambda_b * R_b
            reward_final = max(0.0, reward_final)  # ✅ 确保非负
            
            strategy_key = str(getattr(a, "strategy", "")).strip().lower()
            if strategy_key in ("md2g", "clustering", "heuristic"):
                qoe_mcast_aware = R_q * R_o
            else:
                qoe_mcast_aware = R_q
            
            # 保持向后兼容：用于MD2G内部决策（不影响奖励计算）
            # 使用旧的QoE计算作为内部参考（仅用于MD2G策略的内部决策）
            Rq_legacy = 5.0 * (math.log1p(Qr) / math.log(2.5))
            Rb_legacy = math.log1p(Bu) / math.log1p(network_b_max + EPS)
            delay_penalty = dly / 200.0
            rebuffer_penalty = min(1.0, stall_count * 0.1)
            # Legacy QoE 也移除负载均衡项：把原来的 0.15*jfi 正权重等分回 Rq/Rb
            QoE_inst_legacy = max(0.0,
                                    0.425 * Rq_legacy + 0.425 * Rb_legacy
                                    - 0.10 * delay_penalty - 0.05 * rebuffer_penalty)
            
            # MD2G策略的特殊处理（仅用于内部决策，不影响奖励计算）
            # 注意：dq, sb, dyn_th等指标仅用于MD2G的内部决策逻辑（如是否启用增强层），
            # 但不用于奖励计算，确保所有策略使用相同的奖励函数进行公平比较
            if a.strategy == "md2g":
                # 先更新窗口与趋势（用于MD2G内部决策，使用legacy QoE作为参考）
                smart_enhancement.update_windows(bandwidth_mbps=Bu, qoe_smooth=QoE_inst_legacy)
                
                # 获取网络类型（用于动态权重调整）
                network_type = getattr(a, 'network_type', None) or getattr(a, 'network', None)
                
                # 计算决策质量与稳定性（仅用于MD2G内部决策，不用于QoE计算）
                dq = decision_quality_v2(Bu, base_rate, delay_penalty, network_type=network_type)
                sb = stability_bonus(smart_enhancement.qoe_window)
                
                # 启停判定（迟滞 + 趋势）
                # 计算当前负载率（使用relay_loads的平均值）
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
                # 其他策略不需要这些内部决策指标
                dq, sb, dyn_th = 0.0, 0.0, 0.0
            
            # --- MD2G-Plus动态调节（仅用于MD2G内部决策，不影响奖励计算） ---
            if a.strategy == "md2g" and iteration > 10:  # 等待足够样本
                # 使用legacy QoE进行内部决策
                if not hasattr(run_client, 'qoe_smooth_prev'):
                    run_client.qoe_smooth_prev = QoE_inst_legacy
                QoE_smooth_legacy = 0.85 * run_client.qoe_smooth_prev + 0.15 * QoE_inst_legacy
                run_client.qoe_smooth_prev = QoE_smooth_legacy
                smart_enhancement.update_qoe_and_adjust_threshold(QoE_smooth_legacy)
            
            # --- 计算rx_bytes（用于日志）---
            # ✅ 【关键修复】使用真实的累计接收字节数（rx_bytes），而不是从文件大小或Bu反推
            # ✅ 【关键修复】使用相对于实验开始时的物理网卡累计值，确保单调递增
            # 注意：这里使用上面已经计算好的 current_rx_bytes 和 initial_rx_bytes
            if hasattr(run_client, 'initial_rx_bytes'):
                rx_bytes = int(current_rx_bytes - run_client.initial_rx_bytes)  # 本次实验的净增长
            else:
                # 兼容性：如果第一次迭代没执行到，使用当前值
                rx_bytes = int(current_rx_bytes)
            
            # --- 写日志（统一奖励函数格式）---
            if a.strategy == "md2g":
                print(f"[DEBUG] h{a.host_id}: 写入日志 dly={dly:.2f}ms Bu={Bu:.2f}Mbps "
                      f"R_q={R_q:.4f} R_o={R_o:.4f} R_b={R_b:.4f} reward={reward_final:.4f} "
                      f"(dq={dq:.4f} sb={sb:.4f} dyn_th={dyn_th:.3f}仅用于MD2G内部决策)",
                      file=sys.stderr, flush=True)
            else:
                print(f"[DEBUG] h{a.host_id}: 写入日志 dly={dly:.2f}ms Bu={Bu:.2f}Mbps "
                      f"R_q={R_q:.4f} R_o={R_o:.4f} R_b={R_b:.4f} reward={reward_final:.4f}",
                      file=sys.stderr, flush=True)
            
            # ✅ 【提取 TTFB】从 DataDrainer 读取（安全处理 None 值）
            # Base TTFB
            ttfb_base = 0.0
            if reader_base and hasattr(reader_base, 'ttfb_ms') and reader_base.ttfb_ms is not None:
                ttfb_base = reader_base.ttfb_ms
            
            # Enhanced TTFB（安全处理 None 值）
            ttfb_enh1 = 0.0
            if 1 in enh_readers and enh_readers[1] is not None:
                if hasattr(enh_readers[1], 'ttfb_ms') and enh_readers[1].ttfb_ms is not None:
                    ttfb_enh1 = enh_readers[1].ttfb_ms
            
            ttfb_enh2 = 0.0
            if 2 in enh_readers and enh_readers[2] is not None:
                if hasattr(enh_readers[2], 'ttfb_ms') and enh_readers[2].ttfb_ms is not None:
                    ttfb_enh2 = enh_readers[2].ttfb_ms
            
            # ✅ 【只有9个视频】不再有enhanced3
            ttfb_enh3 = 0.0  # 保留字段，但不再使用
            
            # ✅ 【格式化订阅类型】
            subscription_type = f"B{base_version}"
            if decision > 0:
                subscription_type += f"+E{decision}"
            
            # Rep 档位对应的 Q1–Q4（报表列）
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
            
            # ✅ 【CPU使用率测量】在主循环中测量CPU使用率
            cpu_data = measure_cpu_usage()
            
            # ✅ 【构建最终 CSV 行】包含所有需要的指标（已删除TTLB和app_goodput_mbps，只保留rx_bytes）
            # ✅ 【Phase 0诊断】添加rep_id字段（在buffer_level_sec之后）
            # ✅ 【CPU使用率测量】添加CPU相关字段
            # ✅ 【重传计数】MOQ架构使用moq-sub，重传由QUIC协议层处理
            # 暂时记录为0，未来可以通过监控moq-sub日志来检测重传
            retransmission_count = 0  # MOQ架构：QUIC层自动重传，应用层不直接控制
            
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
            
            # ✅ 【CSV实时写入】同时写入.log和.csv文件，确保实时刷新
            # ✅ 【关键保证】此逻辑对所有策略都有效（MD2G, Rolling, Heuristic, Clustering, Groot, Pano）
            # 不依赖策略类型，所有策略都会生成统一格式的perf.csv
            # 文件路径：{a.log_path}/client_h{a.host_id}_perf.csv
            perf_log_file.write(csv_line)
            perf_log_file.flush()
            perf_csv_file.write(csv_line)
            perf_csv_file.flush()

            # --- 写出自身状态，供全局控制器读取 ---
            # ✅ 【cell-scoped 状态目录】SIGCOMM_CELL_STATE_DIR / SIGCOMM_CELL_TMP / legacy
            # ✅ 【关键修复】确保在第一次迭代时也写入状态文件（iteration从0开始）
            _ensure_client_state_dir()
            client_state_file = _client_state_file(a.host_id)
            # ✅ 确保共享目录存在且可写
            try:
                # ✅ 确保文件可写（如果文件已存在，先检查权限）
                if os.path.exists(client_state_file):
                    os.chmod(client_state_file, 0o666)  # 确保所有用户可读写
            except (OSError, PermissionError) as e:
                if iteration % 10 == 0:  # 每10次打印一次错误，避免日志过多
                    print(f"[WARN] h{a.host_id}: 无法创建共享目录: {e}", file=sys.stderr, flush=True)
                pass  # 如果无法设置权限，继续尝试写入
            
            current_state_payload = {
                "host_id": a.host_id,
                "network_type": a.network_type,
                "throughput_mbps": Bu,  # ✅ 单位：Mbps（已统一）
                "delay_ms": dly,
                "device_score": dev_score,
                "last_decision_layer": decision,
                "reward_R_o": R_o,  # 分组效率奖励
                "reward_R_q": R_q,  # 用户感知质量奖励
                "reward_R_b": R_b,  # 带宽效率惩罚
                "reward_final": reward_final,  # 最终奖励
                "timestamp": time.time(),
                "viewpoint": "front_center"  # 可以根据需要动态改变
            }
            # command124: FoV unavailable under scientific native9 — same for all strategies
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
                # ✅ 【修复】确保目录存在且可写
                _ensure_client_state_dir()

                # ✅ 【修复】使用原子写入：先写入临时文件，再重命名
                temp_file = f"{client_state_file}.tmp"
                with open(temp_file, 'w') as sf:
                    json.dump(current_state_payload, sf)
                    sf.flush()
                    os.fsync(sf.fileno())  # 强制刷新到磁盘
                
                # 原子重命名
                os.rename(temp_file, client_state_file)
                
                # ✅ 设置文件权限，确保控制器可以读取
                os.chmod(client_state_file, 0o666)  # 所有用户可读写
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
                
                # ✅ 【关键修复】在第一次迭代时也输出日志，确保状态文件被写入
                if iteration == 0 or iteration % 20 == 0:  # 第一次和每20次打印一次成功信息
                    print(f"[DEBUG] h{a.host_id}: ✅ 已写入状态文件: {client_state_file} (iteration={iteration})", file=sys.stderr, flush=True)
                    # ✅ 验证文件确实已创建
                    if os.path.exists(client_state_file):
                        file_size = os.path.getsize(client_state_file)
                        print(f"[DEBUG] h{a.host_id}: ✅ 状态文件验证: {file_size} 字节", file=sys.stderr, flush=True)
            except (IOError, OSError, PermissionError) as e:
                if iteration % 10 == 0:  # 每10次打印一次错误，避免日志过多
                    print(f"[WARN] h{a.host_id}: 无法写入client_state_file: {e}", file=sys.stderr, flush=True)
                pass  # 写入失败不应使客户端崩溃

            # --- 更新状态窗口（用于Rolling策略） ---
            # 注意：state_window用于Rolling DRL策略，包含最近N步的状态
            # ✅ 使用统一奖励函数的最终值 reward_final 替代旧的 QoE_smooth
            state_window.append([Bu, dly, reward_final, Qr, decision])
            iteration += 1   # ✅ 计数器 +1
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
        # ✅ 【CSV实时写入】确保文件正确关闭
        perf_log_file.close()
        perf_csv_file.close()
        print(f"[INFO] h{a.host_id}: CSV文件已保存到: {perf_csv}", file=sys.stderr, flush=True)

    print(f"[INFO] h{a.host_id}: 实验结束，清理进程（动态订阅模式：Base 流始终运行，Enhanced 流根据 decision 可能运行）", file=sys.stderr, flush=True)
    
    # ✅ 停止 DataDrainer 线程
    if rep_lc_v2 and 'rep_subs' in locals() and rep_subs:
        for rid in list(rep_subs.keys()):
            _terminate_rep_sub(rid)
        print(f"[INFO] h{a.host_id}: REP-LC-V2 rep_subs 已清理", file=sys.stderr, flush=True)
    else:
        if 'reader_base' in locals():
            reader_base.stop()
            print(f"[INFO] h{a.host_id}: Base DataDrainer 线程已停止（共读取 {reader_base.bytes_read // 1024} KB）", file=sys.stderr, flush=True)
        
        # ✅ 【多版本支持】停止所有 Enhanced DataDrainer 线程
        if 'enh_readers' in locals():
            for version in [1, 2, 3]:
                if version in enh_readers and enh_readers[version] is not None:
                    enh_readers[version].stop()
                    print(f"[INFO] h{a.host_id}: Enhanced{version} DataDrainer 线程已停止（共读取 {enh_readers[version].bytes_read // 1024} KB）", file=sys.stderr, flush=True)
    
    # 等待线程结束
    time.sleep(0.5)
    
    # 清理进程
    if not rep_lc_v2 and base_p:
        kill(base_p)
    
    # ✅ 【多版本支持】清理所有 Enhanced 订阅进程（legacy dual-sub path）
    if not rep_lc_v2 and 'enh_processes' in locals():
        for version in [1, 2, 3]:
            if version in enh_processes and enh_processes[version] is not None:
                kill(enh_processes[version])
                print(f"[INFO] h{a.host_id}: Enhanced{version} 订阅进程已清理", file=sys.stderr, flush=True)



# ============================= CLI =============================
if __name__ == "__main__":
    p = argparse.ArgumentParser("MoQ dispatch client")
    p.add_argument("--duration", type=int, default=60)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--host_id", type=int, required=True)
    p.add_argument("--log_path", required=True)
    p.add_argument("--decision_file", required=True)
    p.add_argument("--strategy", choices=["md2g", "rolling", "heuristic", "clustering", "groot", "pano"], required=True)
    p.add_argument("--clients", type=int, required=True)   # 改为 clients
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
        print("❌ 未处理异常:\n", traceback.format_exc())
        sys.exit(1)