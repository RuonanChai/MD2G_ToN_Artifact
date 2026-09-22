#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COMMAND120 live playability telemetry + deployable online capacity estimator.

Fail-closed: missing required fields must not be filled with mean_buf=5.0.
Oracle/Mininet/trace-file bandwidth may be logged as diagnostic only and MUST
NOT be written to access_capacity_mbps for final Gen3 policy use.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

REQUIRED_PLAYABILITY_FIELDS = (
    "buffer_level_sec",
    "playable_ahead_sec",
    "stall_active",
    "stall_elapsed_sec",
    "last_playable_timestamp",
    "active_rep",
    "rep_completion_frac",
    "bytes_remaining_current_object",
    "bytes_remaining_by_rep",
    "recent_object_completion_s",
    "stream_open_latency_s",
    "switch_latency_s",
    "delivery_rate_mbps",
    "access_capacity_mbps",
    "app_limited",
    "group_id",
    "active_group_rep_streams",
    "weak_user_quality_deficit",
)

ORACLE_ONLY_KEYS = (
    "oracle_trace_sample_mbps",
    "oracle_mininet_configured_mbps",
    "oracle_tc_rate_mbps",
)


# command122 estimator identity. Mininet configured bandwidth is NEVER a
# scientific-runtime input (see ORACLE_ONLY_KEYS / ignored kwargs below).
CAPACITY_SIGNAL_PROVENANCE = "command122_hybrid_demand_limited_probe"
ESTIMATOR_VERSION = "command122_v1_hybrid_demand_limited_probe"
# Cheapest redandblack secondary in OPEN_IMMEDIATE search (rep8) × frozen 1.05.
CANDIDATE_SECONDARY_MBPS = 1.429187 * 1.05
# Level-3 probe is independent of H1/H2 arms. Predeclared before certification.
PROBE_TARGET_MBPS = 2.80
PROBE_MAX_S = 0.50
PROBE_PERIOD_S = 3.0
PROBE_MAX_BYTES = 163840  # 160 KiB; 2.80 Mbps × 0.50 s ≈ 175 KB, bounded below
PROBE_PORT = 18080
PROBE_ABORT_BUFFER_S = 0.30
PROBE_N_SLOTS = 10
PROBE_SLOT_S = 0.50
PROBE_MAX_CONCURRENT = 1
PROBE_REFRESH_S = 8.0  # feasible re-verify; 0.50/8.0 duty ≤ predeclared 0.08
DEMAND_LIMITED_SLACK = 0.20  # delivery <= requested*(1+slack)+0.08 → demand-limited
DEMAND_LIMITED_ABS = 0.08
NAL_AGE_CONFIDENCE_S = 8.0
ORACLE_RUNTIME_KWARGS = (
    "configured_bw_mbps", "configured_mbps", "mininet_bw_mbps",
    "oracle_mininet_configured_mbps", "oracle_trace_sample_mbps",
    "oracle_tc_rate_mbps", "TON_ORACLE_LAST_MILE_MBPS",
    "access_bw_mbps", "tc_rate_mbps",
)


def _ignored_oracle_kwargs(kwargs: Mapping[str, Any]) -> list[str]:
    return [k for k in kwargs if k in ORACLE_RUNTIME_KWARGS or k.lower().startswith("oracle_")]


def probe_slot_ok(client_id: int | None, now_s: float, *, n_slots: int = PROBE_N_SLOTS, slot_s: float = PROBE_SLOT_S) -> bool:
    """Arm-independent stagger. Does not read the causal-arm environment variable."""
    if client_id is None:
        return True
    return int(client_id) % int(n_slots) == int(float(now_s) / max(slot_s, 1e-6)) % int(n_slots)


class ProbeAdmission:
    """Global concurrent probe budget (cell-scoped). Arm-independent."""

    def __init__(self, *, max_concurrent: int = PROBE_MAX_CONCURRENT, path: Any = None) -> None:
        import os
        from pathlib import Path as _P
        self.max_concurrent = int(max_concurrent)
        if path is None:
            d = os.environ.get("SIGCOMM_CELL_STATE_DIR") or "/tmp"
            path = _P(d) / "c122_probe_budget.json"
        self.path = _P(path)
        self._mem: dict[str, float] = {}

    def try_acquire(
        self,
        client_id: int,
        now_s: float,
        *,
        hold_s: float = PROBE_MAX_S,
        require_slot: bool = True,
    ) -> bool:
        # Slot stagger belongs to the scheduler. Once probe_active is set,
        # the burst tick (command120 interval=1.0s) must not re-filter the
        # 0.50s slot — that rotates +2 and starves every live probe.
        if require_slot and not probe_slot_ok(client_id, now_s):
            return False
        now = float(now_s)
        cid = str(int(client_id))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            import fcntl
            with self.path.open("a+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.seek(0)
                raw = f.read()
                try:
                    st = json.loads(raw) if raw.strip() else {"active": {}}
                except Exception:
                    st = {"active": {}}
                active = {k: float(v) for k, v in (st.get("active") or {}).items() if float(v) > now}
                if cid not in active and len(active) >= self.max_concurrent:
                    st["active"] = active
                    f.seek(0); f.truncate(); f.write(json.dumps(st))
                    return False
                active[cid] = now + float(hold_s)
                st["active"] = active
                f.seek(0); f.truncate(); f.write(json.dumps(st)); f.flush()
                return True
        except OSError:
            # In-memory fallback for unit tests / missing dir
            active = {k: v for k, v in self._mem.items() if v > now}
            if cid not in active and len(active) >= self.max_concurrent:
                self._mem = active
                return False
            active[cid] = now + float(hold_s)
            self._mem = active
            return True


_DEFAULT_ADMISSION: ProbeAdmission | None = None


def try_acquire_probe(
    client_id: int,
    now_s: float,
    *,
    hold_s: float = PROBE_MAX_S,
    require_slot: bool = True,
) -> bool:
    global _DEFAULT_ADMISSION
    if _DEFAULT_ADMISSION is None:
        _DEFAULT_ADMISSION = ProbeAdmission()
    return _DEFAULT_ADMISSION.try_acquire(
        int(client_id), float(now_s), hold_s=hold_s, require_slot=require_slot,
    )


class OnlineCapacityEstimator:
    """command122 deployable access-capacity estimator.

    Ladder (strongest available signal wins):
      L1 transport-native pacing/delivery/cwnd-rtt if the caller supplies it
         (this Mininet/MoQ Python stack has no QUIC/BBR API; L1 is unused unless
         a future transport exposes the fields).
      L2 hybrid passive: demand-limited freeze; keep recent non-app-limited
         samples; do not decay a valid higher estimate to common-stream goodput.
      L3 bounded safe headroom probe (predeclared) only to resolve feasibility
         when L1/L2 cannot discover unused headroom under app-limited media.

    Scientific runtime must never read Mininet configured bandwidth.
    """

    VERSION = ESTIMATOR_VERSION

    def __init__(
        self,
        *,
        alpha: float = 0.35,
        init_mbps: float = 1.0,
        probe_enabled: bool = True,
        probe_target_mbps: float = PROBE_TARGET_MBPS,
        probe_max_s: float = PROBE_MAX_S,
        probe_period_s: float = PROBE_PERIOD_S,
        probe_abort_buffer_s: float = PROBE_ABORT_BUFFER_S,
        probe_alpha: float = 0.55,
        candidate_demand_mbps: float | None = None,
    ) -> None:
        self.alpha = float(alpha)
        self.probe_alpha = float(probe_alpha)
        self.ema_mbps = float(init_mbps)
        self.initialized = False
        self.last_app_limited = False
        self.probe_enabled = bool(probe_enabled)
        self.probe_target_mbps = float(probe_target_mbps)
        self.probe_max_s = float(probe_max_s)
        self.probe_period_s = float(probe_period_s)
        self.probe_abort_buffer_s = float(probe_abort_buffer_s)
        self.candidate_demand_mbps = (
            float(candidate_demand_mbps) if candidate_demand_mbps is not None else float(CANDIDATE_SECONDARY_MBPS)
        )
        self.capacity_lower_bound_mbps = 0.05
        self.capacity_confidence = 0.15
        self.last_non_app_limited_ts: float | None = None
        self.last_probe_ts: float | None = None
        self.probe_active = False
        self.probe_started_ts: float | None = None
        self.probe_bytes_total = 0.0
        self.estimator_source = "init"
        self.last_snapshot: dict[str, Any] = {}
        self._now = 0.0
        self._feas_hist: list[bool] = []

    def snapshot(self) -> dict[str, Any]:
        return dict(self.last_snapshot)

    def update(
        self,
        *,
        rx_bytes_delta: float,
        dt_s: float,
        buffer_level_sec: float,
        buffer_cap_sec: float = 12.0,
        outstanding_bytes: float = 1.0,
        min_dt_s: float = 0.05,
        requested_mbps: float | None = None,
        stall_active: bool = False,
        now_s: float | None = None,
        transport_pacing_mbps: float | None = None,
        transport_delivery_mbps: float | None = None,
        transport_cwnd_bytes: float | None = None,
        transport_srtt_s: float | None = None,
        probe_rx_bytes: float = 0.0,
        client_id: int | None = None,
        **kwargs: Any,
    ) -> tuple[float, bool]:
        _ignored_oracle_kwargs(kwargs)  # never used in the decision path
        dt = max(float(dt_s), min_dt_s)
        now = float(now_s) if now_s is not None else (self._now + dt)
        self._now = now
        media_rx = max(0.0, float(rx_bytes_delta))
        probe_rx = max(0.0, float(probe_rx_bytes))
        total_rx = media_rx + probe_rx
        delivery = (8.0 * total_rx) / dt / 1e6
        media_delivery = (8.0 * media_rx) / dt / 1e6
        buf = float(buffer_level_sec)
        cap = max(float(buffer_cap_sec), 1e-6)
        outstanding = max(0.0, float(outstanding_bytes))
        stall = bool(stall_active)
        req = None if requested_mbps is None else max(0.0, float(requested_mbps))

        buffer_full = buf >= 0.90 * cap
        idle_outstanding = outstanding <= 1.0 and buf > 1.0
        if req is not None and req > 0.05:
            demand_limited = (
                (not stall)
                and (not buffer_full)
                and media_delivery <= req * (1.0 + DEMAND_LIMITED_SLACK) + DEMAND_LIMITED_ABS
            )
        else:
            # Legacy path (no requested_mbps): keep original buffer-full / idle freeze.
            demand_limited = False
        path_limited = stall or (not demand_limited and not buffer_full and not idle_outstanding)
        was_probing = bool(self.probe_active)
        if was_probing:
            self.probe_bytes_total += probe_rx
            # Extra delivery above media demand is a legitimate capacity sample.
            path_limited = (not stall) and buf >= self.probe_abort_buffer_s
            demand_limited = False

        app_limited = bool(buffer_full or idle_outstanding or (demand_limited and not was_probing))
        self.last_app_limited = app_limited

        l1 = None
        l1_src = None
        for val, src in (
            (transport_pacing_mbps, "l1_transport_pacing"),
            (transport_delivery_mbps, "l1_transport_delivery"),
        ):
            try:
                fv = float(val) if val is not None else None
            except (TypeError, ValueError):
                fv = None
            if fv is not None and fv > 0.05:
                l1 = fv
                l1_src = src
                break
        if l1 is None and transport_cwnd_bytes and transport_srtt_s:
            try:
                cwnd = float(transport_cwnd_bytes)
                srtt = float(transport_srtt_s)
                if cwnd > 0 and srtt > 1e-4:
                    l1 = (8.0 * cwnd) / srtt / 1e6
                    l1_src = "l1_cwnd_rtt"
            except (TypeError, ValueError):
                l1 = None

        prev = float(self.ema_mbps)
        source = "hold_app_limited"
        if l1 is not None:
            a = self.alpha
            self.ema_mbps = a * l1 + (1.0 - a) * self.ema_mbps if self.initialized else l1
            self.initialized = True
            self.last_non_app_limited_ts = now
            self.capacity_lower_bound_mbps = max(self.capacity_lower_bound_mbps, l1)
            source = l1_src or "l1_transport"
        elif was_probing and not stall and buf >= self.probe_abort_buffer_s:
            extra = (probe_rx > 0) or (req is None and delivery > 0.05) or (
                req is not None and delivery > req * 1.15 + 0.05
            )
            if extra:
                a = self.probe_alpha
                sample = max(delivery, 0.05)
                if not self.initialized:
                    self.ema_mbps = sample
                    self.initialized = True
                elif sample + 1e-9 < self.candidate_demand_mbps:
                    # Path cannot carry the cheapest secondary; do not over-admit.
                    self.ema_mbps = sample
                    self.capacity_lower_bound_mbps = sample
                elif sample < self.ema_mbps * 0.85:
                    self.ema_mbps = 0.50 * sample + 0.50 * self.ema_mbps
                    self.capacity_lower_bound_mbps = min(self.capacity_lower_bound_mbps, sample)
                else:
                    self.ema_mbps = a * sample + (1.0 - a) * self.ema_mbps
                    self.capacity_lower_bound_mbps = max(self.capacity_lower_bound_mbps, sample)
                if sample + 1e-9 >= self.candidate_demand_mbps:
                    self.capacity_lower_bound_mbps = max(self.capacity_lower_bound_mbps, sample)
                self.last_non_app_limited_ts = now
                source = "l3_bounded_headroom_probe"
            else:
                source = "l3_probe_no_extra_bytes"
        elif path_limited and not app_limited:
            sample = max(delivery, 0.05)
            if not self.initialized:
                self.ema_mbps = sample
                self.initialized = True
            else:
                a = self.alpha
                self.ema_mbps = a * sample + (1.0 - a) * self.ema_mbps
            self.last_non_app_limited_ts = now
            self.capacity_lower_bound_mbps = max(self.capacity_lower_bound_mbps, sample)
            source = "l2_non_app_limited_delivery"
        else:
            # Demand-limited / buffer-full: freeze. Do not track common-stream goodput down.
            source = "l2_freeze_demand_limited" if demand_limited else "l2_freeze_buffer_full"
            if not self.initialized:
                # Conservative: init is a prior, not a measurement. Do not treat as NAL.
                source = "l2_uninitialized_hold"

        age = None if self.last_non_app_limited_ts is None else max(0.0, now - self.last_non_app_limited_ts)
        if age is None:
            self.capacity_confidence = 0.15
        else:
            self.capacity_confidence = max(0.15, min(0.95, 1.0 - (age / max(NAL_AGE_CONFIDENCE_S, 1e-6)) * 0.6))

        # Probe scheduler for the *next* interval (independent of H1/H2).
        abort = stall or buf < self.probe_abort_buffer_s
        if self.probe_active:
            elapsed = 0.0 if self.probe_started_ts is None else (now - self.probe_started_ts)
            if abort or elapsed >= self.probe_max_s:
                self.probe_active = False
                self.probe_started_ts = None
                self.last_probe_ts = now
        need_probe = False
        if self.probe_enabled and not self.probe_active and not abort:
            feas = float(self.ema_mbps) + 1e-9 >= self.candidate_demand_mbps
            locked_near_media = req is not None and abs(float(self.ema_mbps) - req) <= 0.20
            since = 1e9 if self.last_probe_ts is None else (now - self.last_probe_ts)
            # Discover cheapest-secondary feasibility quickly; re-verify slowly
            # so last-mile duty stays inside predeclared non-interference bounds.
            min_gap = self.probe_period_s
            want = (not feas) or locked_near_media
            if feas and not locked_near_media:
                min_gap = max(float(PROBE_REFRESH_S), self.probe_period_s)
                want = True
            if want and since >= min_gap:
                need_probe = True
            if need_probe and client_id is not None and not probe_slot_ok(int(client_id), now):
                need_probe = False
        if need_probe:
            self.probe_active = True
            self.probe_started_ts = now

        self.estimator_source = source
        cap_est = float(self.ema_mbps)
        self._feas_hist.append(cap_est + 1e-9 >= self.candidate_demand_mbps)
        self._feas_hist = self._feas_hist[-8:]
        self.last_snapshot = {
            "capacity_est_mbps": cap_est,
            "capacity_lower_bound_mbps": float(self.capacity_lower_bound_mbps),
            "capacity_confidence": float(self.capacity_confidence),
            "app_limited": bool(app_limited),
            "demand_limited": bool(demand_limited),
            "path_limited": bool(path_limited),
            "estimator_source": source,
            "estimator_version": self.VERSION,
            "last_non_app_limited_sample_age": age,
            "probe_active": bool(self.probe_active),
            "probe_bytes": float(self.probe_bytes_total),
            "delivery_rate_mbps": float(delivery),
            "media_delivery_mbps": float(media_delivery),
            "requested_mbps": req,
            "previous_estimate_mbps": prev,
            "candidate_demand_mbps": float(self.candidate_demand_mbps),
            "feasibility_candidate": cap_est + 1e-9 >= self.candidate_demand_mbps,
            "l1_used": l1 is not None,
            "oracle_kwargs_ignored": _ignored_oracle_kwargs(kwargs),
        }
        return cap_est, bool(app_limited)


def run_bounded_headroom_probe(
    *,
    host: str | None = None,
    port: int = PROBE_PORT,
    max_bytes: int = PROBE_MAX_BYTES,
    timeout_s: float = PROBE_MAX_S,
) -> int:
    """Receive up to max_bytes from the access-gateway probe sink. Independent of H1/H2."""
    import socket

    if not host:
        host = default_access_gateway()
    if not host:
        return 0
    got = 0
    try:
        with socket.create_connection((host, int(port)), timeout=min(0.25, float(timeout_s))) as s:
            s.settimeout(max(0.05, float(timeout_s)))
            while got < int(max_bytes):
                chunk = s.recv(min(16384, int(max_bytes) - got))
                if not chunk:
                    break
                got += len(chunk)
    except OSError:
        return got
    return got


_GW_CACHE: str | None = None
_GW_CACHE_MONO = 0.0


def default_access_gateway() -> str | None:
    """Best-effort last-mile gateway (Mininet r1/r2 LAN). Not a bandwidth oracle."""
    import shutil
    import subprocess
    import time as _time

    global _GW_CACHE, _GW_CACHE_MONO
    now = _time.monotonic()
    if _GW_CACHE and (now - _GW_CACHE_MONO) < 5.0:
        return _GW_CACHE
    ip = shutil.which("ip") or "/sbin/ip"
    try:
        out = subprocess.check_output(
            [ip, "route", "show", "default"],
            text=True, timeout=0.4, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    parts = out.split()
    if "via" in parts:
        i = parts.index("via")
        if i + 1 < len(parts):
            _GW_CACHE = parts[i + 1]
            _GW_CACHE_MONO = now
            return _GW_CACHE
    return None


def missing_required(payload: Mapping[str, Any] | None) -> list[str]:
    if not payload:
        return list(REQUIRED_PLAYABILITY_FIELDS)
    miss = []
    for k in REQUIRED_PLAYABILITY_FIELDS:
        if k not in payload or payload[k] is None:
            miss.append(k)
    return miss


def fail_closed_or_raise(payload: Mapping[str, Any] | None, *, enabled: bool) -> list[str]:
    miss = missing_required(payload)
    if enabled and miss:
        raise RuntimeError(
            "PLAYABILITY_FAIL_CLOSED missing=" + ",".join(miss)
            + " (no default mean_buf=5.0)"
        )
    return miss


def bytes_remaining(object_bytes: float, received_bytes: float) -> float:
    return max(0.0, float(object_bytes) - max(0.0, float(received_bytes)))


def completion_frac(object_bytes: float, received_bytes: float) -> float:
    tot = max(1.0, float(object_bytes))
    return max(0.0, min(1.0, max(0.0, float(received_bytes)) / tot))


TTP_DEFINITION_ID = "command120_ttp_v1"
TTP_MIN_PLAYABLE_SEC = 1.0


def ttp_definition() -> dict[str, Any]:
    return {
        "id": TTP_DEFINITION_ID,
        "function": "ton_playability_telemetry.time_to_playable_s",
        "min_playable_sec": TTP_MIN_PLAYABLE_SEC,
        "playable_ahead_source": "buffer_level_sec",
        "start": "playable_ahead_sec < min_playable_sec",
        "end": "playable_ahead_sec >= min_playable_sec (TTP=0)",
        "aggregator": "mean_of_per_tick_TTP_after_WARM_S",
        "same_for_all_probe_arms": True,
    }


def time_to_playable_s(
    *,
    bytes_remaining: float,
    delivery_rate_mbps: float,
    playable_ahead_sec: float,
    min_playable_sec: float = TTP_MIN_PLAYABLE_SEC,
) -> float:
    """Seconds until playable_ahead reaches min_playable, ignoring already-buffered media."""
    if playable_ahead_sec >= min_playable_sec:
        return 0.0
    rate_Bps = max(1e-6, float(delivery_rate_mbps) * 1e6 / 8.0)
    return max(0.0, float(bytes_remaining) / rate_Bps)


def weak_user_quality_deficit(current_q: float, sustainable_target_q: float) -> float:
    return max(0.0, float(sustainable_target_q) - float(current_q))


def build_playability_payload(
    *,
    buffer_level_sec: float,
    stall_active: bool,
    stall_elapsed_sec: float,
    last_playable_timestamp: float | None,
    active_rep: int,
    object_bytes: float,
    received_bytes: float,
    bytes_remaining_by_rep: dict[int, float] | None,
    recent_object_completion_s: float,
    stream_open_latency_s: float,
    switch_latency_s: float,
    delivery_rate_mbps: float,
    access_capacity_mbps: float,
    app_limited: bool,
    group_id: int,
    active_group_rep_streams: list | tuple,
    weak_user_quality_deficit: float,
    oracle_trace_sample_mbps: float | None = None,
    oracle_mininet_configured_mbps: float | None = None,
) -> dict[str, Any]:
    br = bytes_remaining(object_bytes, received_bytes)
    playable = max(0.0, float(buffer_level_sec))
    payload = {
        "buffer_level_sec": float(buffer_level_sec),
        "playable_ahead_sec": playable,
        "stall_active": bool(stall_active),
        "stall_elapsed_sec": float(stall_elapsed_sec),
        "last_playable_timestamp": last_playable_timestamp,
        "active_rep": int(active_rep),
        "rep_completion_frac": completion_frac(object_bytes, received_bytes),
        "bytes_remaining_current_object": br,
        "bytes_remaining_by_rep": {
            int(k): float(v) for k, v in (bytes_remaining_by_rep or {int(active_rep): br}).items()
        },
        "recent_object_completion_s": float(recent_object_completion_s),
        "stream_open_latency_s": float(stream_open_latency_s),
        "switch_latency_s": float(switch_latency_s),
        "delivery_rate_mbps": float(delivery_rate_mbps),
        "access_capacity_mbps": float(access_capacity_mbps),
        "app_limited": bool(app_limited),
        "group_id": int(group_id),
        "active_group_rep_streams": list(active_group_rep_streams),
        "weak_user_quality_deficit": float(weak_user_quality_deficit),
        "time_to_playable_s": time_to_playable_s(
            bytes_remaining=br,
            delivery_rate_mbps=delivery_rate_mbps,
            playable_ahead_sec=playable,
        ),
        "capacity_signal_provenance": CAPACITY_SIGNAL_PROVENANCE,
    }
    if oracle_trace_sample_mbps is not None:
        payload["oracle_trace_sample_mbps"] = float(oracle_trace_sample_mbps)
    if oracle_mininet_configured_mbps is not None:
        payload["oracle_mininet_configured_mbps"] = float(oracle_mininet_configured_mbps)
    miss = missing_required(payload)
    if miss:
        raise RuntimeError("PLAYABILITY_BUILD_INCOMPLETE missing=" + ",".join(miss))
    return payload


def stamp_playability_into_decisions(
    decisions: dict,
    states_by_uid: Mapping[int, Mapping[str, Any]],
    *,
    fail_closed: bool,
) -> dict:
    """Copy live playability into controller decision dicts. Never default buffer=5.0."""
    n_ok = 0
    missing_users = []
    for uid_s, d in list(decisions.items()):
        if not isinstance(d, dict):
            continue
        try:
            uid = int(uid_s)
        except (TypeError, ValueError):
            continue
        st = states_by_uid.get(uid)
        miss = missing_required(st)
        if miss:
            missing_users.append({"uid": uid, "missing": miss})
            d["playability_missing"] = miss
            continue
        for k in REQUIRED_PLAYABILITY_FIELDS:
            d[k] = st[k]
        d["time_to_playable_s"] = st.get("time_to_playable_s")
        d["playability_ok"] = True
        n_ok += 1
    if fail_closed and missing_users:
        raise RuntimeError(
            f"PLAYABILITY_FAIL_CLOSED n_missing={len(missing_users)} "
            f"sample={missing_users[:3]} (no default mean_buf=5.0)"
        )
    return {
        "n_ok": n_ok,
        "n_missing": len(missing_users),
        "missing_users": missing_users[:12],
        "fail_closed": fail_closed,
    }
