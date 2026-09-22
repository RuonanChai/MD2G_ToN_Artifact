from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""In-host nested component subscriber for COMMAND147 fidelity smoke.

Follows ComponentActuationPlan targets written by the cluster planner.
Does not read heuristic/MD2G decision files.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from command151_stall_supporting import WARMUP_S, _empty_decoded

NESTED_CLOSURE = {
    "Rep1": ["b0"],
    "Rep2": ["b0", "db1"],
    "Rep3": ["b0", "db1", "db2"],
    "Rep4": ["b0", "e1"],
    "Rep5": ["b0", "e1", "e2"],
    "Rep6": ["b0", "db1", "e1"],
    "Rep7": ["b0", "db1", "e1", "e2"],
    "Rep8": ["b0", "db1", "db2", "e1"],
    "Rep9": ["b0", "db1", "db2", "e1", "e2"],
}
TRACKS = ["b0", "db1", "db2", "e1", "e2"]
B0_READY_BYTES = 64
B0_FIRST_WAIT_S = 8.0
INCR_STAGGER_S = 0.15


def ordered_open_batches(wanted: list[str]) -> tuple[list[str], list[str]]:
    """Open b0 alone first; incrementals only after the b0 dump gate.

    Concurrent same-tick moq-sub bursts can leave a live /anon/ subscribe
    with dump=0 (E014). This is start-order, not a quality/policy retune.
    """
    wanted_ordered = [c for c in TRACKS if c in set(wanted)]
    if "b0" in wanted_ordered:
        return ["b0"], [c for c in wanted_ordered if c != "b0"]
    return [], wanted_ordered


def b0_dump_ready(path: str | os.PathLike[str], min_bytes: int = B0_READY_BYTES) -> bool:
    try:
        p = Path(path)
        return p.is_file() and p.stat().st_size > int(min_bytes)
    except OSError:
        return False


def _qnorm() -> dict:
    p = os.environ.get("COMMAND147_QUALITY_CONTRACT") or ""
    if p and os.path.isfile(p):
        body = json.loads(Path(p).read_text())
        content = os.environ.get("TON_CONTENT_ID") or "redandblack"
        return dict((body.get("Q_norm") or {}).get(content) or {})
    return {}


def _highest(received: set[str]) -> str | None:
    best = None
    best_n = -1
    for sid, need in NESTED_CLOSURE.items():
        if set(need).issubset(received) and len(need) > best_n:
            best = sid
            best_n = len(need)
    return best


def wanted_components(uid: str, state: str, receivers: dict | None) -> list[str]:
    """Subscribe only to this user's dependency closure ∩ plan receiver set."""
    closure_c = list(NESTED_CLOSURE.get(state) or ["b0"])
    if not receivers:
        return closure_c
    hid = str(uid).replace("u", "")
    aliases = {str(uid), hid, f"u{hid}"}
    out = []
    for c in closure_c:
        rlist = receivers.get(c)
        if rlist is None:
            out.append(c)
        elif any(a in rlist for a in aliases):
            out.append(c)
    return out


def _relay(a) -> tuple[str, str]:
    relay_ip = (getattr(a, "relay_ip", None) or "").strip()
    if relay_ip == "10.0.2.2":
        return relay_ip, "https://r1.local:4443/"
    if relay_ip == "10.0.3.2":
        return relay_ip, "https://r2.local:4443/"
    hid = int(a.host_id)
    n = int(getattr(a, "clients", 3) or 3)
    if hid <= max(1, n // 2):
        return "10.0.2.2", "https://r1.local:4443/"
    return "10.0.3.2", "https://r2.local:4443/"


def _moq_sub() -> str:
    env = (os.environ.get("SIGCOMM_MOQ_BIN_DIR") or "").strip()
    repo = os.path.dirname(os.path.abspath(__file__))
    # this file lives in TON/lib; repo is four parents up from lib? 
    # command147_nested_client.py is in Sigcomm26/Paper6_ToN/lib → repo is parents[3]
    root = Path(__file__).resolve().parents[3]
    candidates = []
    if env:
        candidates.append(os.path.join(env, "moq-sub"))
    candidates.extend(
        [
            str(root / "V-PCC" / "MoQ" / "moq-main_3" / "moq-main" / "target" / "release" / "moq-sub"),
        ]
    )
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return candidates[0]


def _wrapper(root: Path) -> str:
    for p in (root / "moq_sub_with_latency.py", root / "Sigcomm26" / "moq_sub_with_latency.py"):
        if p.is_file():
            return str(p)
    return str(root / "moq_sub_with_latency.py")


def run_nested_component_client(a) -> None:
    if str(os.environ.get("TON_CONTENT_ID") or "").lower() == "loot":
        frozen = Path("str(artifact_root())/state/COMMAND153_FINAL_DEV_FROZEN.json")
        if not frozen.is_file():
            print("[COMPONENT-SCRIPT] REFUSING loot network cell", file=sys.stderr, flush=True)
            sys.exit(2)
    qn = _qnorm()
    root = artifact_root()
    moq = _moq_sub()
    wrap = _wrapper(root)
    _, track_url = _relay(a)
    uid = f"u{int(a.host_id)}"
    log_path = Path(a.log_path)
    log_path.mkdir(parents=True, exist_ok=True)
    receipt_path = log_path / f"client_h{a.host_id}_COMPONENT_RECEIPT.jsonl"
    gst = log_path / f"client_h{a.host_id}_gst.log"
    perf_csv = log_path / f"client_h{a.host_id}_perf.csv"
    perf_log = log_path / f"client_h{a.host_id}_perf.log"
    csv_header = (
        "timestamp,user_id,network_type,device_score,base_version,enhanced_level,subscription_type,"
        "ttfb_base_ms,ttfb_enh1_ms,ttfb_enh2_ms,ttfb_enh3_ms,delay_ms,"
        "stall_count,stall_count_inc,stall_total_sec,rx_bytes,"
        "buffer_level_sec,rep_id,qoe,reward_R_o,reward_R_q,reward_R_b,reward_final,"
        "grouping_id,grouping_efficiency,load_balance_jfi,decision_step,"
        "quality_level,quality_score,"
        "cpu_bottleneck_node_percent,cpu_relay_process_percent,cpu_controller_process_percent,"
        "cpu_dash_server_process_percent,cpu_system_percent,retransmission_count\n"
    )
    if not perf_csv.is_file():
        perf_csv.write_text(csv_header)
        perf_log.write_text(csv_header)

    def _eth_rx() -> int:
        try:
            for line in Path("/proc/net/dev").read_text().splitlines():
                if "eth0:" in line:
                    return int(line.split()[1])
        except Exception:
            return 0
        return 0

    rx0 = _eth_rx()
    net_type = str(getattr(a, "network_type", None) or os.environ.get("COMMAND147_SMOKE_NETWORK") or "4g")
    plan_file = os.environ.get("COMMAND147_PLAN_FILE") or str(log_path / "COMPONENT_ACTUATION_PLAN_CURRENT.json")
    procs: dict[str, subprocess.Popen] = {}
    dumps: dict[str, str] = {}
    t0 = time.time()
    duration = float(getattr(a, "duration", 120) or 120)
    interval = float(getattr(a, "interval", 1.0) or 1.0)
    stall_total = 0.0
    first_tick_ts = None
    b0_gate_attempted = False

    def stop(comp: str, *, remove_dump: bool = True) -> None:
        p = procs.pop(comp, None)
        if p is not None:
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        # Mid-run CLOSE may remove unauthorized dumps; final teardown must KEEP dumps
        # so COMMAND153 retention can SHA256+gate before VALID delete (E025/E026).
        if not remove_dump:
            dumps.pop(comp, None)
            return
        dump = dumps.pop(comp, None) or str(log_path / f"dump_h{a.host_id}_{comp}.bin")
        try:
            if dump and os.path.isfile(dump):
                os.remove(dump)
        except OSError:
            pass

    def start(comp: str) -> None:
        if comp in procs and procs[comp].poll() is None:
            return
        dump = str(log_path / f"dump_h{a.host_id}_{comp}.bin")
        dumps[comp] = dump
        logf = str(gst).replace(".log", f"_{comp}.log")
        lat = f"/tmp/moq_latency_h{a.host_id}_{comp}.log"
        unicast = str(os.environ.get("COMMAND148_UNICAST") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        bcast = f"u{int(a.host_id)}_{comp}" if unicast else comp
        cmd = [
            sys.executable,
            wrap,
            moq,
            "video0",
            track_url,
            dump,
            logf,
            lat,
            str(time.time()),
            bcast,
        ]
        env = os.environ.copy()
        env["MOQ_TLS_DISABLE_VERIFY"] = "1"
        env["RUST_LOG"] = "info"
        procs[comp] = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
        print(
            f"[COMPONENT-SCRIPT] h{a.host_id}: OPEN {comp} pid={procs[comp].pid}",
            file=sys.stderr,
            flush=True,
        )

    def start_wanted(wanted: list[str]) -> None:
        nonlocal b0_gate_attempted
        first, rest = ordered_open_batches(wanted)
        for c in first:
            start(c)
        if first == ["b0"] and not b0_gate_attempted:
            dump = dumps.get("b0") or str(log_path / f"dump_h{a.host_id}_b0.bin")
            wait_s = float(os.environ.get("COMMAND147_B0_FIRST_WAIT_S") or B0_FIRST_WAIT_S)
            deadline = time.time() + max(0.0, wait_s)
            while time.time() < deadline and not b0_dump_ready(dump):
                p = procs.get("b0")
                if p is not None and p.poll() is not None:
                    start("b0")
                time.sleep(0.2)
            b0_gate_attempted = True
            print(
                f"[COMPONENT-SCRIPT] h{a.host_id}: B0_FIRST dump={os.path.getsize(dump) if os.path.isfile(dump) else 0}",
                file=sys.stderr,
                flush=True,
            )
        stagger = float(os.environ.get("COMMAND147_INCR_STAGGER_S") or INCR_STAGGER_S)
        for i, c in enumerate(rest):
            if i > 0 and stagger > 0:
                time.sleep(stagger)
            start(c)

    try:
        while time.time() - t0 < duration:
            targets = {}
            writer = ""
            decoded_plan = {}
            receivers = {}
            if os.path.isfile(plan_file):
                try:
                    body = json.loads(Path(plan_file).read_text())
                    targets = dict(body.get("user_target_states") or {})
                    writer = str(body.get("writer") or "")
                    decoded_plan = body
                    receivers = dict(body.get("component_receivers") or {})
                except Exception:
                    targets = {}
            state = str(targets.get(uid) or targets.get(str(a.host_id)) or "Rep1")
            wanted = wanted_components(uid, state, receivers)
            for c in list(procs):
                if c not in wanted:
                    stop(c)
                    print(
                        f"[COMPONENT-SCRIPT] h{a.host_id}: CLOSE {c}",
                        file=sys.stderr,
                        flush=True,
                    )
            # CLOSE may have already popped procs; leftover dump files must not remain
            # for components outside this user's current receiver set.
            for c in TRACKS:
                if c in wanted:
                    continue
                leftover = dumps.pop(c, None) or str(log_path / f"dump_h{a.host_id}_{c}.bin")
                try:
                    if leftover and os.path.isfile(leftover):
                        os.remove(leftover)
                except OSError:
                    pass
            start_wanted(wanted)
            dump_bytes = {}
            got = set()
            for c in TRACKS:
                p = dumps.get(c) or str(log_path / f"dump_h{a.host_id}_{c}.bin")
                n = os.path.getsize(p) if os.path.isfile(p) else 0
                dump_bytes[c] = int(n)
                if n > 64 and c in set(wanted):
                    got.add(c)
            decoded = _highest(got)
            # Rq from ACTUALLY DECODABLE state only. Never credit controller/target intent.
            if decoded and decoded in qn:
                rq = float(qn[decoded])
            else:
                rq = 0.0
            now = time.time()
            if first_tick_ts is None:
                first_tick_ts = now
            elif (now - first_tick_ts) >= WARMUP_S and _empty_decoded(decoded):
                stall_total += max(interval, 0.5)
            rec = {
                "ts": now,
                "host_id": int(a.host_id),
                "user": uid,
                "target_state": state,
                "wanted": wanted,
                "decoded_state": decoded,
                "dump_bytes": dump_bytes,
                "Rq": rq,
                "stall_total_sec": stall_total,
                "stall_last_status": "DECODE_GAP_SECONDS_POST_WARMUP",
                "writer": writer,
                "plan_hash": decoded_plan.get("plan_hash"),
                "content": os.environ.get("TON_CONTENT_ID") or "redandblack",
                "learned_md2g": str(os.environ.get("COMMAND148_STRATEGY") or "") == "MD2G_COMPONENT",
                "unicast": str(os.environ.get("COMMAND148_UNICAST") or "").strip().lower() in ("1", "true", "yes"),
            }
            with receipt_path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            rx_now = _eth_rx()
            rx_bytes = max(0, rx_now - rx0, sum(int(v or 0) for v in dump_bytes.values()))
            decoded_id = int(str(decoded or "0").replace("Rep", "") or "0")
            qscore = float(rq) if rq is not None else 0.0
            row = (
                f"{rec['ts']:.3f},{int(a.host_id)},{net_type},0.5,1,0,component,"
                f"0,0,0,0,0,0,0,{stall_total:.6f},{int(rx_bytes)},"
                f"0.0,{decoded_id},{qscore},0,{qscore},0,{qscore},"
                f"0,0,1,0,0,{qscore},"
                f"0,0,0,0,0,0\n"
            )
            with perf_csv.open("a") as f:
                f.write(row)
            with perf_log.open("a") as f:
                f.write(row)
            time.sleep(max(interval, 0.5))
    finally:
        for c in list(procs):
            stop(c, remove_dump=False)
        print(f"[COMPONENT-SCRIPT] h{a.host_id}: exit receipts={receipt_path}", file=sys.stderr, flush=True)
