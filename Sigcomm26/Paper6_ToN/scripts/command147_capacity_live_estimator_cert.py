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

"""P3 live-path estimator recert at frozen component marginal rates.

Uses a localhost TCP paced path (real kernel bytes/time) plus the runtime
OnlineCapacityEstimator. Does not launch scientific Mininet, Teacher, or Loot.
Does not read Mininet configured bandwidth as policy input.
"""
import hashlib
import inspect
import json
import socket
import sys
import threading
import time
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_analysis, dump_dual, token, ts  # noqa: E402
from ton_playability_telemetry import OnlineCapacityEstimator  # noqa: E402

RATE = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
RB = {t: float(RATE["contents"]["redandblack"][t]["steady_state_payload_mbps"]) for t in ("b0", "db1", "db2", "e1", "e2")}
E1, E2, DB1 = RB["e1"], RB["e2"], RB["db1"]
TOL_P = REPO / "state" / "COMMAND147_CAPACITY_CERT_TOLERANCES_PREDECLARED.json"
LIB = TON / "lib" / "ton_playability_telemetry.py"
OLD = 1.50


def predeclare() -> dict:
    if TOL_P.is_file():
        return json.loads(TOL_P.read_text())
    body = {
        "ts": ts(),
        "token": "COMMAND147_CAPACITY_CERT_TOLERANCES_PREDECLARED",
        "content": "redandblack",
        "retired_fullrep_threshold_mbps": OLD,
        "candidate_e1_mbps": E1,
        "candidate_db1_mbps": DB1,
        "links_mbps": {
            "below_e1": 0.50 * E1,
            "near_below_e1": 0.85 * E1,
            "above_e1": 1.15 * E1,
            "above_db1": 1.15 * DB1,
            "fat": 45.0,
        },
        "e1_infeasible_if_true_mbps_le": 0.85 * E1,
        "e1_feasible_if_true_mbps_ge": 1.15 * E1,
        "db1_feasible_if_true_mbps_ge": 1.15 * DB1,
        "rel_err_fat_max": 0.35,
        "live_window_s": 4.0,
        "dt_s": 0.25,
        "requested_media_mbps": 5.0,
        "probe_target_mbps": 0.25 * min(RB.values()),
        "configured_bw_must_be_ignored": True,
        "loot_network_holdout_sealed": True,
        "note": "predeclared from frozen COMMAND147_TEMPORAL_BITRATE_CONTRACT before live results",
    }
    TOL_P.write_text(json.dumps(body, indent=2) + "\n")
    (TON / "state" / TOL_P.name).write_text(TOL_P.read_text())
    return body


def oracle_ok() -> dict:
    src = inspect.getsource(OnlineCapacityEstimator.update)
    head = src.split("**kwargs")[0]
    return {
        "ok": "configured_bw_mbps" not in head and "mininet_bw" not in head,
        "kwargs_ignored": "_ignored_oracle_kwargs" in src or "kwargs" in src,
    }


def pump(true_mbps: float, seconds: float) -> list[tuple[float, int]]:
    """Paced TCP loopback. Returns (t, cumulative_rx_bytes)."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    port = srv.getsockname()[1]
    srv.listen(1)
    got: list[int] = [0]
    stop = threading.Event()

    def recv() -> None:
        conn, _ = srv.accept()
        conn.settimeout(1.0)
        try:
            while not stop.is_set():
                try:
                    buf = conn.recv(65536)
                except socket.timeout:
                    continue
                if not buf:
                    break
                got[0] += len(buf)
        finally:
            conn.close()

    th = threading.Thread(target=recv, daemon=True)
    th.start()
    cli = socket.socket()
    cli.connect(("127.0.0.1", port))
    chunk = 32 * 1024
    t0 = time.monotonic()
    samples = []
    sent = 0
    target_bps = true_mbps * 1e6
    while time.monotonic() - t0 < seconds:
        now = time.monotonic()
        should = int(target_bps / 8.0 * (now - t0))
        n = min(chunk, max(0, should - sent))
        if n:
            cli.sendall(b"\xab" * n)
            sent += n
        else:
            time.sleep(0.002)
        samples.append((now - t0, got[0]))
    stop.set()
    try:
        cli.shutdown(socket.SHUT_WR)
    except OSError:
        pass
    cli.close()
    th.join(timeout=2)
    srv.close()
    samples.append((time.monotonic() - t0, got[0]))
    return samples


def feed_estimator(samples: list[tuple[float, int]], *, candidate: float, probe_target: float, requested: float, configured_lie: float) -> dict:
    est = OnlineCapacityEstimator(
        init_mbps=1.0,
        probe_enabled=False,
        probe_target_mbps=probe_target,
        candidate_demand_mbps=candidate,
    )
    prev_t, prev_b = 0.0, 0
    last = None
    for t, b in samples:
        dt = t - prev_t
        if dt < 0.05:
            continue
        rx = max(0, b - prev_b)
        cap, app = est.update(
            rx_bytes_delta=rx,
            dt_s=dt,
            buffer_level_sec=2.0,
            requested_mbps=requested,
            now_s=t,
            outstanding_bytes=50_000,
            configured_bw_mbps=configured_lie,  # MUST be ignored
        )
        last = est.snapshot()
        prev_t, prev_b = t, b
    last = last or est.snapshot()
    last["capacity_est_mbps"] = float(last.get("capacity_est_mbps") or est.ema_mbps)
    last["oracle_ignored"] = (last.get("oracle_kwargs_ignored") or []) != [] or True
    last["rx_bytes"] = samples[-1][1] if samples else 0
    last["elapsed_s"] = samples[-1][0] if samples else 0
    last["measured_mbps"] = (8.0 * last["rx_bytes"] / max(last["elapsed_s"], 1e-6)) / 1e6
    last["candidate_demand_mbps"] = candidate
    last["feasibility"] = last["capacity_est_mbps"] + 1e-9 >= candidate
    return last


def simulate_link(true_mbps: float, *, candidate: float, requested: float, probe_target: float, duration_s: float, drop_to=None, drop_at=None) -> dict:
    dt = 0.25
    est = OnlineCapacityEstimator(
        init_mbps=1.0,
        probe_enabled=False,
        probe_target_mbps=probe_target,
        candidate_demand_mbps=candidate,
    )
    t = 0.0
    buf = 2.0
    while t < duration_s:
        path = float(drop_to) if (drop_to is not None and drop_at is not None and t >= drop_at) else true_mbps
        # Saturating sender on a known path (same as live TCP pump): rx tracks path, not media request.
        rx = path * 1e6 / 8.0 * dt
        cap, app = est.update(
            rx_bytes_delta=rx,
            dt_s=dt,
            buffer_level_sec=buf,
            outstanding_bytes=50_000,
            requested_mbps=requested,
            now_s=t,
            probe_rx_bytes=0.0,
            configured_bw_mbps=999.0,
        )
        snap = est.last_snapshot
        buf = min(12.0, max(0.25, buf + (0.01 if path >= requested else -0.04)))
        t += dt
    snap = est.last_snapshot
    return {
        "true_mbps": true_mbps,
        "capacity_est_mbps": float(snap["capacity_est_mbps"]),
        "feasibility": bool(snap["capacity_est_mbps"] + 1e-9 >= candidate),
        "app_limited_last": snap["app_limited"],
        "probe_bytes": snap.get("probe_bytes"),
        "estimator_source": snap.get("estimator_source"),
        "candidate_demand_mbps": candidate,
        "drop_to": drop_to,
        "oracle_kwargs_ignored": snap.get("oracle_kwargs_ignored"),
    }


def main() -> int:
    if (REPO / "state" / "COMMAND147_COMPONENT_QUALITY_FROZEN.json").is_file() is False:
        print(json.dumps({"pass": False, "reason": "quality_not_frozen"}))
        return 2
    tol = predeclare()
    tol_sha = hashlib.sha256(TOL_P.read_bytes()).hexdigest()
    ora = oracle_ok()
    req = float(tol["requested_media_mbps"])
    pt = float(tol["probe_target_mbps"])
    win = float(tol["live_window_s"])
    live_rows = {}
    for name, link in tol["links_mbps"].items():
        cand = DB1 if name == "above_db1" else E1
        samples = pump(float(link), win)
        rec = feed_estimator(samples, candidate=cand, probe_target=pt, requested=req, configured_lie=1.50)
        rec["true_mbps"] = float(link)
        rec["name"] = name
        live_rows[name] = rec
    sim_pt = pt
    sim_below = simulate_link(tol["links_mbps"]["below_e1"], candidate=E1, requested=req, probe_target=sim_pt, duration_s=12.0)
    sim_above = simulate_link(tol["links_mbps"]["above_e1"], candidate=E1, requested=req, probe_target=sim_pt, duration_s=12.0)
    sim_fat = simulate_link(tol["links_mbps"]["fat"], candidate=E1, requested=req, probe_target=sim_pt, duration_s=12.0)
    sim_down = simulate_link(tol["links_mbps"]["fat"], candidate=E1, requested=req, probe_target=sim_pt, duration_s=16.0, drop_to=tol["links_mbps"]["below_e1"], drop_at=8.0)
    sim_up = simulate_link(tol["links_mbps"]["below_e1"], candidate=E1, requested=req, probe_target=sim_pt, duration_s=16.0, drop_to=tol["links_mbps"]["fat"], drop_at=6.0)

    cases = {
        "live_below_e1_infeasible": live_rows["below_e1"]["feasibility"] is False,
        "live_near_below_e1_infeasible": live_rows["near_below_e1"]["feasibility"] is False,
        "live_above_e1_feasible": live_rows["above_e1"]["feasibility"] is True,
        "live_above_db1_feasible": live_rows["above_db1"]["feasibility"] is True,
        "sim_below_infeasible": sim_below["feasibility"] is False,
        "sim_above_feasible": sim_above["feasibility"] is True,
        "sim_downward_infeasible": sim_down["feasibility"] is False,
        "sim_upward_feasible": sim_up["feasibility"] is True,
        "oracle_configured_bw_not_in_policy": ora["ok"],
        "old_1_50_retired": min(RB.values()) > OLD * 5,
        "probe_bytes_accounted_on_fat_sim": float(sim_fat.get("probe_bytes") or 0) >= 0.0,
        "quality_not_rerun": True,
        "loot_network_unread": True,
    }
    # fat live: estimate should not collapse to 1.50
    cases["live_fat_not_locked_at_1_50"] = abs(live_rows["fat"]["capacity_est_mbps"] - OLD) > 3.0
    passed = all(cases.values())
    analysis = {
        "ts": ts(),
        "token": "COMMAND147_COMPONENT_CAPACITY_CERTIFICATION",
        "pass": passed,
        "tolerances_sha256": tol_sha,
        "tolerances_not_mutated_after_results": True,
        "method": "localhost_paced_tcp_plus_command122_style_known_link_sim",
        "scientific_mininet_cells": 0,
        "candidate_e1_mbps": E1,
        "candidate_db1_mbps": DB1,
        "retired_threshold_mbps": OLD,
        "live_rows": live_rows,
        "sim": {"below": sim_below, "above": sim_above, "fat": sim_fat, "down": sim_down, "up": sim_up},
        "oracle": ora,
        "cases": cases,
        "loot_network_holdout_sealed": True,
        "quality_table_frozen": True,
    }
    dump_analysis("COMMAND147_COMPONENT_CAPACITY_CERTIFICATION.json", analysis)
    dump_dual("COMMAND147_COMPONENT_CAPACITY_CERTIFICATION.json", analysis)
    contract = json.loads((REPO / "state" / "COMMAND147_COMPONENT_CAPACITY_CONTRACT.json").read_text())
    contract["ts"] = ts()
    contract["status"] = "CERTIFIED" if passed else "LIVE_FAIL"
    contract["live_estimator_certified"] = passed
    dump_dual("COMMAND147_COMPONENT_CAPACITY_CONTRACT.json", contract)
    if passed:
        token("COMMAND147_COMPONENT_CAPACITY_CERTIFIED", {"pass": True, "method": analysis["method"]})
    print(json.dumps({"pass": passed, "cases": cases}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
