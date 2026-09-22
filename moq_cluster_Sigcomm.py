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

import time
import os
import re
import json
import csv
import threading
import random
import shutil
import shlex
import glob
import sys
from pathlib import Path
from collections import deque, defaultdict
from mininet.net import Mininet
from mininet.node import Host, Controller, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error
from mininet.link import TCLink


def _command137_raw_4g() -> bool:
    return os.environ.get("COMMAND137_RATE_FEASIBILITY_RAW_4G", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _ton_gen3_stress_cap():
    raw = (os.environ.get("TON_GEN3_STRESS_LM_MBPS") or "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _ton_gen3_slice_series(series, net_type: str):
    key = {"wifi": "WIFI", "4g": "4G", "5g": "5G", "fiber_optic": "FIBER_OPTIC"}.get(net_type, "")
    a = os.environ.get(f"TON_GEN3_ROW_{key}_START")
    b = os.environ.get(f"TON_GEN3_ROW_{key}_END")
    if not a or not b or series is None:
        return series
    try:
        sub = series.iloc[int(a):int(b)]
        return sub if len(sub) else series
    except Exception:
        return series


def _ton_gen3_apply_last_mile(actual_bw: float, user_net_type: str) -> float:
    cap = _ton_gen3_stress_cap()
    if cap is not None and cap > 0:
        return max(0.5, min(float(actual_bw), cap))
    return actual_bw

# pandas
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    info("⚠️ pandas \n")

# Fail-closed: SIGCOMM_MOQ_BIN_DIR, else optional in-repo release tree.
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_LOCAL_BIN = os.path.join(_REPO_ROOT, "V-PCC", "MoQ", "moq-main_3", "moq-main", "target", "release")
_SRV_BIN = ""


def _resolve_moq_bin_dir():
    env = (os.environ.get("SIGCOMM_MOQ_BIN_DIR") or "").strip()
    if env:
        if not os.path.isdir(env):
            raise FileNotFoundError(
                f"SIGCOMM_MOQ_BIN_DIR={env} missing or not a directory (fail-closed)"
            )
        return env
    for cand in (_LOCAL_BIN, _SRV_BIN):
        if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "moq-relay")):
            return cand
    raise FileNotFoundError(
        "No valid MoQ bin dir: set SIGCOMM_MOQ_BIN_DIR or install a release under "
        f"{_LOCAL_BIN}"
    )


def _resolve_video_dir():
    env = (os.environ.get("SIGCOMM_VIDEO_DIR") or "").strip()
    if env:
        live = os.path.join(env, "redandblack_6_live")
        if not os.path.isdir(live):
            raise FileNotFoundError(
                f"SIGCOMM_VIDEO_DIR={env} lacks redandblack_6_live/ (fail-closed)"
            )
        return env
    local = os.path.join(_REPO_ROOT, "video")
    if os.path.isdir(os.path.join(local, "redandblack_6_live")):
        return local
    raise FileNotFoundError(
        f"SIGCOMM video dir missing under {local}; set SIGCOMM_VIDEO_DIR "
        "(legacy home-directory fallbacks disabled)"
    )


BASE_DIR = _resolve_moq_bin_dir()
VIDEO_DIR = _resolve_video_dir()

BIN_PATHS = {
    "relay": os.path.join(BASE_DIR, "moq-relay"),
    "sub":   os.path.join(BASE_DIR, "moq-sub"),
    "pub":   os.path.join(BASE_DIR, "hang"),
    "token": os.path.join(BASE_DIR, "moq-token")
}

# ✅ 100% hang mfra/fiel atom
OFFICIAL_VIDEO = os.path.join(os.path.dirname(os.path.dirname(VIDEO_DIR)), 
                               "V-PCC", "MoQ", "moq-main_3", "moq-main", "dev", "bbb.mp4")

# ✅ MoQ redandblack_6_live H.264 120
# Base rep1(base1), rep2(base2), rep3(base3) - base
# rep4-9 - base+enhanced rep1-9
# rep4-5: base1 (base1+enh1, base1+enh1+enh2)
# rep6-7: base2 (base2+enh1, base2+enh1+enh2)
# rep8-9: base3 (base3+enh1, base3+enh1+enh2)
# ✅ H.264 DASH MOQ redandblack_6 H.264
# ✅ redandblack_6_live 120
REDANDBLACK_6_DIR = os.path.join(VIDEO_DIR, "redandblack_6_live")
REDANDBLACK_6_ORIGINAL_DIR = os.path.join(VIDEO_DIR, "redandblack_6")
DASH_DIR = os.path.join(VIDEO_DIR, "redandblack_5", "dash")
VIDEO_PATHS = {
    # Base base redandblack_6_live H.264
    "base1": os.path.join(REDANDBLACK_6_DIR, "rep1_base1_h264.mp4"),  # rep1 = base1 only
    "base2": os.path.join(REDANDBLACK_6_DIR, "rep2_base2_h264.mp4"),  # rep2 = base2 only
    "base3": os.path.join(REDANDBLACK_6_DIR, "rep3_base3_h264.mp4"),  # rep3 = base3 only
    # base1 base1 MoQ /
    "base1_enhanced1": os.path.join(REDANDBLACK_6_DIR, "rep4_base1_enhanced1_h264.mp4"),      # rep4 = base1 + enhanced1
    "base1_enhanced2": os.path.join(REDANDBLACK_6_DIR, "rep5_base1_enhanced1_enhanced2_h264.mp4"),  # rep5 = base1 + enhanced1+2
    # base2 base2 MoQ /
    "base2_enhanced1": os.path.join(REDANDBLACK_6_DIR, "rep6_base2_enhanced1_h264.mp4"),      # rep6 = base2 + enhanced1
    "base2_enhanced2": os.path.join(REDANDBLACK_6_DIR, "rep7_base2_enhanced1_enhanced2_h264.mp4"),  # rep7 = base2 + enhanced1+2
    # base3 base3 MoQ /
    "base3_enhanced1": os.path.join(REDANDBLACK_6_DIR, "rep8_base3_enhanced1_h264.mp4"),     # rep8 = base3 + enhanced1
    "base3_enhanced2": os.path.join(REDANDBLACK_6_DIR, "rep9_base3_enhanced1_enhanced2_h264.mp4"),  # rep9 = base3 + enhanced1+2
    # DASH
    "enhanced1": os.path.join(DASH_DIR, "rep4_base1_enhanced1.mp4"),
    "enhanced2": os.path.join(DASH_DIR, "rep5_base1_enhanced1_enhanced2.mp4"),
}

def _apply_true_content_layering_video_paths():
    """COMMAND135: nine physical content tracks from frozen manifest. Not composites."""
    nest = (os.environ.get("TON_NESTED_COMPONENTS") or "").strip().lower()
    if nest in ("1", "true", "yes", "on"):
        return False
    flag = (os.environ.get("TON_TRUE_CONTENT_LAYERING") or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    root = Path(__file__).resolve().parent
    paths_file = os.environ.get("COMMAND135_PATHS") or str(root / "state" / "COMMAND135_PATHS.json")
    body = json.loads(Path(paths_file).read_text())
    content = (
        os.environ.get("TON_CONTENT_ID")
        or os.environ.get("MM26_CONTENT_ID")
        or "redandblack"
    )
    tracks = Path(body["layered_media_root"]) / content / "tracks"
    names = [
        "base1", "base2", "base3",
        "base1_enh1_only", "base1_enh2_only",
        "base2_enh1_only", "base2_enh2_only",
        "base3_enh1_only", "base3_enh2_only",
    ]
    out = {}
    for n in names:
        p = tracks / n / "120s.mp4"
        if not p.is_file():
            raise FileNotFoundError(f"TON_TRUE_CONTENT_LAYERING missing {p}")
        out[n] = str(p)
    VIDEO_PATHS.clear()
    VIDEO_PATHS.update(out)
    os.environ["TON_TRUE_CONTENT_LAYER_KEYS"] = "1"
    return True


_TRUE_CONTENT_LAYERING = _apply_true_content_layering_video_paths()


def _apply_nested_component_video_paths():
    """COMMAND146/147: incremental b0/db1/db2/e1/e2, not nine composites."""
    flag = (os.environ.get("TON_NESTED_COMPONENTS") or "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return False
    content = (
        os.environ.get("TON_CONTENT_ID")
        or os.environ.get("MM26_CONTENT_ID")
        or "redandblack"
    )
    if str(content).lower() == "loot":
        _frozen = Path("str(artifact_root())/state/COMMAND153_FINAL_DEV_FROZEN.json")
        if not _frozen.is_file():
            raise RuntimeError("Loot network holdout sealed: nested smoke must not use loot")
    root = Path(__file__).resolve().parent
    tracks = root / "media" / "ton_nested_components_v1" / content / "tracks"
    out = {}
    for n in ("b0", "db1", "db2", "e1", "e2"):
        p = tracks / n / "120s.mp4"
        if not p.is_file():
            raise FileNotFoundError(f"TON_NESTED_COMPONENTS missing {p}")
        out[n] = str(p)
    VIDEO_PATHS.clear()
    VIDEO_PATHS.update(out)
    os.environ["TON_NESTED_COMPONENT_KEYS"] = "1"
    return True


_NESTED_COMPONENTS = _apply_nested_component_video_paths()

for key in ["base1", "base2", "base3", "enhanced1", "enhanced2"]:
    if key in VIDEO_PATHS:
        os.makedirs(os.path.dirname(VIDEO_PATHS[key]), exist_ok=True)

# ✅ topo_moq_eval_OFF.py
CERT_DIR = "/tmp/moq_certs_test2"
TMP_PREFIX = "test2_"  # default; overridden per-cell in run_moq_experiment
AUTH_DIR = f"/tmp/{TMP_PREFIX}auth"
# Per-cell tracked PIDs for scoped cleanup (never kill ToN / unrelated moq).
CELL_RECORDED_PIDS = set()
# ===========================================


def resolve_sigcomm_python():
    """Absolute Python for dispatch/controllers/cpu monitor (command40 §4/D)."""
    env = (os.environ.get("SIGCOMM_PYTHON") or "").strip()
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env
    venv_py = os.path.join(_REPO_ROOT, "Sigcomm26", ".venv_sigcomm", "bin", "python3")
    if os.path.isfile(venv_py) and os.access(venv_py, os.X_OK):
        return venv_py
    return "/usr/bin/python3"


SIGCOMM_PYTHON = resolve_sigcomm_python()


def sigcomm_campaign_env_dict():
    """Campaign env vars to forward into Mininet host namespaces (command60/61).

    command113: also forward TON_* (native9rep gate/candidate/content/bitrate map).
    Mininet host.cmd does not inherit the parent shell env; without this, live
    controllers never see TON_NATIVE9REP_MD2G even when the campaign launcher set it.
    """
    out = {
        "SIGCOMM_REP_LIFECYCLE_V2": os.environ.get("SIGCOMM_REP_LIFECYCLE_V2", "1"),
        "SIGCOMM_METRIC_V4_TIMELINE": os.environ.get("SIGCOMM_METRIC_V4_TIMELINE", "1"),
        "SIGCOMM_INSTRUMENTATION_V2": os.environ.get("SIGCOMM_INSTRUMENTATION_V2", "1"),
    }
    for key in (
        "SIGCOMM_BASELINE_SEED",
        "SIGCOMM_INITIAL_PROBE_S",
        "SIGCOMM_BUFFER_PROTECTION_S",
        "SIGCOMM_REP_MAX_OVERLAP_S",
        "SIGCOMM_REP_LADDER",
        "SIGCOMM_QOE_EQ9",
        "SIGCOMM_REP_MIN_DWELL_S",
    ):
        val = os.environ.get(key)
        if val is not None and str(val).strip() != "":
            out[key] = str(val)
    for key, val in os.environ.items():
        if key.startswith(("MM26_", "TON_", "COMMAND147_")):
            out[key] = str(val)
        elif key.startswith("REP") and key.endswith("_BITRATE_MBPS"):
            out[key] = str(val)
    return out


def write_sigcomm_controller_env_file(path=None):
    """Persist MM26_/SIGCOMM_/TON_ into the controller hydrate file (command113).

    Prevents a stale /tmp/mm26_controller_c28.env (e.g. unrelated content/seed)
    from overwriting the current cell's campaign contract at controller import.
    Falls back to a user-writable path if the legacy root-owned file is not writable.
    """
    candidates = []
    if path:
        candidates.append(path)
    env_path = (os.environ.get("MM26_CONTROLLER_ENV_FILE") or "").strip()
    if env_path:
        candidates.append(env_path)
    candidates.extend(
        [
            "/tmp/mm26_controller_c28.env",
            f"/tmp/mm26_controller_c28_{os.getuid()}.env",
        ]
    )
    lines = []
    for k, v in sorted(sigcomm_campaign_env_dict().items()):
        if not k.startswith(("MM26_", "SIGCOMM_", "TON_")) and not (
            k.startswith("REP") and k.endswith("_BITRATE_MBPS")
        ):
            continue
        if v is None or str(v).strip() == "":
            continue
        lines.append(f"{k}={v}")
    payload = "\n".join(lines) + ("\n" if lines else "")
    last_err = None
    chosen = None
    for cand in candidates:
        try:
            with open(cand, "w", encoding="utf-8") as fh:
                fh.write(payload)
            try:
                os.chmod(cand, 0o644)
            except OSError:
                pass
            chosen = cand
            break
        except OSError as exc:
            last_err = exc
            continue
    if chosen is None:
        raise OSError(f"unable to write controller env file; last_err={last_err}")
    os.environ["MM26_CONTROLLER_ENV_FILE"] = chosen
    info(
        f"✅ Wrote Sigcomm controller env file: {chosen} "
        f"(n={len(lines)}, TON_NATIVE9REP_MD2G={os.environ.get('TON_NATIVE9REP_MD2G')}, "
        f"TON_MD2G_CANDIDATE={os.environ.get('TON_MD2G_CANDIDATE')}, "
        f"MM26_MD2G_TP_SIGNAL={os.environ.get('MM26_MD2G_TP_SIGNAL')})\n"
    )
    return chosen


def sigcomm_campaign_env_prefix():
    """Shell KEY=quoted_value prefix for Mininet host.cmd strings."""
    parts = [f"{k}={shlex.quote(str(v))}" for k, v in sigcomm_campaign_env_dict().items()]
    return (" ".join(parts) + " ") if parts else ""


def derive_cell_tmp_prefix(log_path=None):
    """
    Unique TMP_PREFIX / work dir so cells do not share /tmp/test2_*.
    Prefer SIGCOMM_CELL_TMP, else fingerprint from log_path.
    """
    env = (os.environ.get("SIGCOMM_CELL_TMP") or "").strip()
    if env:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", env).strip("_")
        if not safe.endswith("_"):
            safe = safe + "_"
        return safe[:80]
    if log_path:
        abs_lp = os.path.abspath(log_path)
        digest = re.sub(r"[^A-Za-z0-9]+", "", abs_lp.replace("/", "_"))[-48:]
        if not digest:
            digest = str(abs(hash(abs_lp)) % (10**10))
        return f"sigcell_{digest}_"
    return f"sigcell_{os.getpid()}_"


def _ton_lib_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "Sigcomm26", "Paper6_ToN", "lib")


def cell_scoped_pre_start_cleanup(log_path, num_subscribers, tmp_prefix):
    """Reclaim leftover MD2G tree ifaces for THIS topology only. Never mn -c."""
    ton_lib = _ton_lib_dir()
    if ton_lib not in sys.path:
        sys.path.insert(0, ton_lib)
    from ton_cell_scoped_net import (  # noqa: E402
        assert_clear, cleanup_owned, record_inventory,
    )
    inv = record_inventory(
        log_path=log_path, num_subscribers=num_subscribers, tmp_prefix=tmp_prefix,
    )
    fps = [tmp_prefix, str(log_path)]
    cleaned = cleanup_owned(
        inv, reason="pre_start_stale", exclude_pids=[os.getpid()], own_fingerprints=fps,
    )
    chk = assert_clear(inv)
    rec = {"inventory": inv, "cleanup": cleaned, "assert_clear": chk}
    try:
        with open(os.path.join(log_path, "CELL_SCOPED_NET_PRESTART.json"), "w") as f:
            json.dump(rec, f, indent=2)
            f.write("\n")
    except Exception:
        pass
    if cleaned.get("skipped"):
        info(f"⚠️  cell-scoped pre-start cleanup skipped: {cleaned.get('skip_why')}\n")
    else:
        info(
            f"🧹 cell-scoped pre-start: deleted_ifaces={len(cleaned.get('deleted_ifaces') or [])} "
            f"deleted_bridges={len(cleaned.get('deleted_bridges') or [])} "
            f"clear={chk.get('clear')} never_mn_c\n"
        )
        if not chk.get("clear") and not cleaned.get("skipped"):
            # Retry once after a short wait (udev/ovs settle).
            time.sleep(0.4)
            cleanup_owned(inv, reason="pre_start_retry", exclude_pids=[os.getpid()])
            chk = assert_clear(inv)
            info(f"🧹 cell-scoped pre-start retry clear={chk.get('clear')} stale={chk.get('stale_ifaces')}\n")
    if not chk.get("clear") and not cleaned.get("skipped"):
        stale = (chk.get("stale_ifaces") or []) + (chk.get("stale_bridges") or [])
        raise RuntimeError(f"CELL_SCOPED_STALE_TOPOLOGY: {stale[:12]}")
    return inv


def cell_scoped_exit_cleanup(log_path, num_subscribers, tmp_prefix, net=None):
    """net.stop plus owned leftover reclaim. Never mn -c."""
    if net is not None:
        try:
            net.stop()
        except Exception as exc:
            info(f"⚠️  net.stop failed (will still scoped-clean): {exc}\n")
    ton_lib = _ton_lib_dir()
    if ton_lib not in sys.path:
        sys.path.insert(0, ton_lib)
    from ton_cell_scoped_net import cleanup_owned, record_inventory, assert_clear  # noqa: E402
    inv = record_inventory(
        log_path=log_path, num_subscribers=num_subscribers, tmp_prefix=tmp_prefix,
    )
    cleaned = cleanup_owned(
        inv, reason="cell_exit", exclude_pids=[os.getpid()],
        own_fingerprints=[tmp_prefix, str(log_path)],
    )
    chk = assert_clear(inv)
    try:
        with open(os.path.join(log_path, "CELL_SCOPED_NET_EXIT.json"), "w") as f:
            json.dump({"cleanup": cleaned, "assert_clear": chk}, f, indent=2)
            f.write("\n")
    except Exception:
        pass
    info(
        f"🧹 cell-scoped exit cleanup clear={chk.get('clear')} "
        f"deleted_ifaces={len(cleaned.get('deleted_ifaces') or [])} never_mn_c\n"
    )
    return chk


def hang_announce_pattern(broadcast_name):
    """Match hang DEBUG/INFO: announce broadcast=<name> (NO anon/ prefix)."""
    return re.compile(
        rf"announce\s+broadcast={re.escape(broadcast_name)}(?:\s|$|[^\w/])",
        re.IGNORECASE,
    )


def publisher_registered_in_hang_log(log_text, broadcast_name, alive=False):
    """True iff hang publisher log shows announce for bare broadcast name (no anon/)."""
    if not log_text:
        return False
    if hang_announce_pattern(broadcast_name).search(log_text):
        return True
    # Fallback: alive PID + hang log contains connected/announce (command40 B)
    if alive:
        low = log_text.lower()
        if "announce" in low or "connected" in low:
            return True
    return False


def write_publisher_launch_contract(log_path, contract):
    """Dump per-cell PUBLISHER_LAUNCH_CONTRACT.json under log_path."""
    out = os.path.join(log_path, "PUBLISHER_LAUNCH_CONTRACT.json")
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(contract, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        error(f"⚠️  write PUBLISHER_LAUNCH_CONTRACT.json failed: {e}\n")
    _echo_command137_run_contract(log_path)
    return out


def _echo_command137_run_contract(log_path):
    sha = os.environ.get("COMMAND137_RUN_CONTRACT_SHA", "").strip()
    if not sha:
        return
    prof = os.environ.get("COMMAND137_TRANSPORT_PROFILE_ID", "").strip()
    b3 = os.environ.get("COMMAND137_B3_SHA256", "").strip()
    echo = {
        "run_contract_sha256": sha,
        "transport_profile_id": prof,
        "b3_sha256": b3,
        "source": "publisher",
    }
    try:
        with open(os.path.join(log_path, "RUN_CONTRACT_ECHO_PUBLISHER.json"), "w", encoding="utf-8") as f:
            json.dump(echo, f, indent=2)
            f.write("\n")
    except Exception as e:
        error(f"COMMAND137 run-contract publisher echo failed: {e}\n")
    info(f"COMMAND137_RUN_CONTRACT sha={sha} profile={prof} b3={b3}\n")


def subscriber_pid_ok(pid_str):
    """Hard gate: N/A / empty / non-digit PID is failure."""
    if pid_str is None:
        return False
    s = str(pid_str).strip()
    if not s or s.upper() == "N/A" or s.lower() == "none":
        return False
    # pgrep may return multiple; take first token
    first = s.split()[0].split("\n")[0].strip()
    return first.isdigit() and int(first) > 1


def copy_cell_tmp_logs(log_path, tmp_prefix):
    """Copy critical relay/pub/dispatch logs from /tmp into log_path before cleanup."""
    if not log_path or not tmp_prefix:
        return
    os.makedirs(log_path, exist_ok=True)
    names = [
        "r0.log", "r1.log", "r2.log",
        "r0_controller.log", "r1_controller.log", "r2_controller.log",
        "r0_cpu_monitor.log", "r1_cpu_monitor.log", "r2_cpu_monitor.log",
    ]
    for key in (
        "base1", "base2", "base3",
        "base1_enhanced1", "base1_enhanced2",
        "base2_enhanced1", "base2_enhanced2",
        "base3_enhanced1", "base3_enhanced2",
        "base1_enh1_only", "base1_enh2_only",
        "base2_enh1_only", "base2_enh2_only",
        "base3_enh1_only", "base3_enh2_only",
        "b0", "db1", "db2", "e1", "e2",
    ):
        names.append(f"pub_{key}.log")
    for i in range(1, 201):
        names.append(f"h{i}_dispatch.log")
    for name in names:
        src = f"/tmp/{tmp_prefix}{name}"
        if os.path.isfile(src):
            try:
                shutil.copy2(src, os.path.join(log_path, f"tmp_{name}"))
            except Exception:
                pass


def host_cmd_safe(host, command, default=""):
    """Mininet node.cmd is not thread-safe. Never raise into the CELL_VALIDITY path."""
    if host is None:
        return default
    try:
        if getattr(host, "waiting", False):
            try:
                host.monitor(timeoutms=1000)
            except Exception:
                pass
        return host.cmd(command)
    except AssertionError:
        return default
    except Exception:
        return default


def compute_and_write_cell_validity(
    log_path,
    *,
    strategy,
    num_subscribers,
    registered_publishers,
    expected_publishers,
    subscriber_pids,
    leaf_egress_bytes=0,
    leaf_egress_threshold=50_000,
    min_rx_bytes=10_000,
):
    """Write CELL_VALIDITY.json; return (valid: bool, payload: dict)."""
    reasons = []
    pub_ok = len(registered_publishers) >= len(expected_publishers) and len(expected_publishers) > 0
    if not pub_ok:
        reasons.append(
            f"publishers_registered={len(registered_publishers)}/{len(expected_publishers)}"
        )

    started = [(i, p) for i, p, *_ in subscriber_pids if subscriber_pid_ok(p)]
    sub_ok = len(started) >= num_subscribers and num_subscribers > 0
    if not sub_ok:
        reasons.append(f"subscribers_with_pid={len(started)}/{num_subscribers}")

    perf_count = 0
    rx_ok_count = 0
    for i in range(1, num_subscribers + 1):
        perf = os.path.join(log_path, f"client_h{i}_perf.csv")
        if os.path.isfile(perf):
            perf_count += 1
            try:
                with open(perf, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                if len(lines) > 1:
                    header = lines[0].strip().split(",")
                    if "rx_bytes" in header:
                        idx = header.index("rx_bytes")
                        last = lines[-1].strip().split(",")
                        if len(last) > idx and last[idx].isdigit() and int(last[idx]) >= min_rx_bytes:
                            rx_ok_count += 1
            except Exception:
                pass
    perf_ok = perf_count >= num_subscribers
    if not perf_ok:
        reasons.append(f"perf_files={perf_count}/{num_subscribers}")
    rx_ok = rx_ok_count >= max(1, num_subscribers // 2) if num_subscribers else False
    if not rx_ok:
        reasons.append(f"rx_sustained={rx_ok_count}/{num_subscribers} (need >= half, min_rx={min_rx_bytes})")

    egress_ok = int(leaf_egress_bytes or 0) >= int(leaf_egress_threshold)
    if not egress_ok:
        reasons.append(
            f"leaf_egress={leaf_egress_bytes} < threshold={leaf_egress_threshold}"
        )

    # command40: uncaught Traceback / UnboundLocalError / KeyError in client or controller = hard fail
    traceback_hits = []
    fatal_re = re.compile(
        r"(Traceback \(most recent call last\):|UnboundLocalError:|KeyError:)",
        re.M,
    )
    scan_globs = (
        "client_h*_dispatch_stdout.log",
        "client_h*_dispatch_stderr.log",
        "tmp_r*_controller.log",
        "controller_*.log",
    )
    try:
        for pattern in scan_globs:
            for path in sorted(glob.glob(os.path.join(log_path, pattern))):
                try:
                    text = open(path, "r", encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                if fatal_re.search(text):
                    traceback_hits.append(os.path.basename(path))
    except Exception as e:
        reasons.append(f"traceback_scan_error={e}")
    no_fatal_logs = len(traceback_hits) == 0
    if not no_fatal_logs:
        reasons.append(
            "fatal_exceptions_in_logs=" + ",".join(traceback_hits[:12])
            + (f"+{len(traceback_hits)-12}more" if len(traceback_hits) > 12 else "")
        )

    # Unicast baselines: still require clients+perf+rx; publisher gate may be N/A
    strat = (strategy or "").lower()
    if strat in ("rolling", "groot"):
        # Publishers still required for MoQ unicast path in this runner
        valid = pub_ok and sub_ok and perf_ok and rx_ok and egress_ok and no_fatal_logs
    else:
        valid = pub_ok and sub_ok and perf_ok and rx_ok and egress_ok and no_fatal_logs

    payload = {
        "valid": bool(valid),
        "strategy": strategy,
        "num_subscribers": num_subscribers,
        "publishers_registered": sorted(list(registered_publishers)),
        "publishers_expected": sorted(list(expected_publishers)),
        "subscriber_pids_ok": len(started),
        "perf_file_count": perf_count,
        "rx_sustained_count": rx_ok_count,
        "leaf_egress_bytes": int(leaf_egress_bytes or 0),
        "leaf_egress_threshold": int(leaf_egress_threshold),
        "fatal_exception_logs": traceback_hits,
        "failure_reasons": reasons,
    }
    out = os.path.join(log_path, "CELL_VALIDITY.json")
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        error(f"⚠️  write CELL_VALIDITY.json failed: {e}\n")
    return valid, payload

# ✅ 5 md2g, rolling, heuristic, clustering, groot
# ✅ 7 wifi, 4g, 5g, fiber_optic, default_mix, wifi_dominant, 5g_dominant
STRATEGIES = ["md2g", "rolling", "heuristic", "clustering", "groot"]
NETWORKS = ["wifi", "4g", "5g", "fiber_optic", "default_mix", "wifi_dominant", "5g_dominant"]

# ================= Device profile configuration =================
DEVICE_PROFILES = {
    "quest2_72":  {"cpu": 8, "gpu": 587,  "ram": 6,  "refresh": 72,  "res_w": 1832, "res_h": 1920},
    "quest2_90":  {"cpu": 8, "gpu": 587,  "ram": 6,  "refresh": 90,  "res_w": 1832, "res_h": 1920},
    "quest2_120": {"cpu": 8, "gpu": 587,  "ram": 6,  "refresh": 120, "res_w": 1832, "res_h": 1920},
    "quest3_90":  {"cpu": 8, "gpu": 903,  "ram": 8,  "refresh": 90,  "res_w": 2064, "res_h": 2208},
    "quest3_120": {"cpu": 8, "gpu": 903,  "ram": 8,  "refresh": 120, "res_w": 2064, "res_h": 2208},
    "quest3s_90": {"cpu": 8, "gpu": 903,  "ram": 8,  "refresh": 90,  "res_w": 1832, "res_h": 1920},
    "quest3s_120":{"cpu": 8, "gpu": 903,  "ram": 8,  "refresh": 120, "res_w": 1832, "res_h": 1920},
    "avp_90":     {"cpu": 8, "gpu": 1398, "ram": 16, "refresh": 90,  "res_w": 3660, "res_h": 3200},
}

MAX_CPU = 8
MAX_GPU = 1398
MAX_RAM = 16
MAX_REFRESH = 120
MAX_PIXELS = 3660 * 3200

# Device score weights (keep together for easy tuning).
BETA_C = 0.05
BETA_G = 0.45
BETA_M = 0.30
BETA_R = 0.20


def compute_device_score(profile):
    c_norm = profile["cpu"] / MAX_CPU
    g_norm = profile["gpu"] / MAX_GPU
    m_norm = profile["ram"] / MAX_RAM

    refresh_norm = profile["refresh"] / MAX_REFRESH
    pixels = profile["res_w"] * profile["res_h"]
    res_norm = pixels / MAX_PIXELS

    # Display term combines refresh rate and per-eye resolution.
    display_term = 0.5 * refresh_norm + 0.5 * res_norm

    score = (
        BETA_C * c_norm +
        BETA_G * g_norm +
        BETA_M * m_norm +
        BETA_R * display_term
    )
    return round(score, 4)


def _load_client_device_map(device_map_path):
    if not device_map_path:
        return {}
    if not os.path.exists(device_map_path):
        info(f"⚠️ device_map : {device_map_path} \n")
        return {}
    try:
        with open(device_map_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        parsed = {}
        for k, v in raw.items():
            # {"1":"quest2_72"} {"h1":"quest2_72"}
            key = str(k).strip().lower().replace("client_", "")
            if key.startswith("h"):
                key = key[1:]
            if key.isdigit() and str(v) in DEVICE_PROFILES:
                parsed[int(key)] = str(v)
        return parsed
    except Exception as e:
        info(f"⚠️ device_map : {e} \n")
        return {}


def assign_device_type(client_id, client_device_map=None):
    if client_device_map and client_id in client_device_map:
        return client_device_map[client_id]
    profile_names = sorted(DEVICE_PROFILES.keys())
    return profile_names[(client_id - 1) % len(profile_names)]

# ================= topo_moq_eval_OFF.py =================
# ✅ /DC (Core <-> Root Relay)
BW_N0_R0 = 1000

def get_video_bitrate(video_path):
    """
     ffprobe 
    
    Args:
        video_path: 
    
    Returns:
        float: Mbps 
    """
    try:
        import subprocess
        # ffprobe bps
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            bitrate_bps = float(result.stdout.strip())
            bitrate_mbps = bitrate_bps / 1e6
            return bitrate_mbps
    except Exception as e:
        info(f"⚠️ {video_path}: {e} \n")
    
    # fallback
    return None

# ✅ run_moq_experiment
def init_video_bitrates():
    """
     
     9 3 base + 6 

    Wire design: each of base1..3 and baseN_enhancedM is an independently
    decodable representation (one selected Rep at a time for unicast sizing).
    enh_bitrate records the composite stream total (base1_enhanced1), not a delta.
    TOTAL_BITRATE is the per-user peak selected Rep rate (max over ladder),
    NOT base + composite (that would double-count base content already inside
    the composite file).

    Returns:
        (base_bitrate, enh_bitrate, total_bitrate): Mbps 
    """
    # COMMAND135: additive physical-track peak, never Table-1 composite fallbacks.
    if (os.environ.get("TON_TRUE_CONTENT_LAYERING") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        rates = {}
        for key, path in VIDEO_PATHS.items():
            if os.path.exists(path):
                br = get_video_bitrate(path)
                if br is not None:
                    rates[key] = float(br)
        if "base1" not in rates:
            raise RuntimeError("TON_TRUE_CONTENT_LAYERING missing base1 bitrate; refuse Table-1 fallback")
        base_bitrate = rates["base1"]
        e1 = rates.get("base1_enh1_only")
        e2 = rates.get("base1_enh2_only")
        if e1 is None or e2 is None:
            raise RuntimeError("TON_TRUE_CONTENT_LAYERING missing enhancement-only bitrates")
        enh_bitrate = float(e1)  # residual E1, not a composite
        peak_bitrate = base_bitrate + float(e1) + float(e2)
        print(f"✅ Layered Base1: {base_bitrate:.3f} Mbps")
        print(f"✅ Layered E1-only: {e1:.3f} Mbps  E2-only: {e2:.3f} Mbps")
        print(f"✅ Layered peak B1+E1+E2: {peak_bitrate:.3f} Mbps (additive, not composite)")
        return base_bitrate, enh_bitrate, float(peak_bitrate)

    if (os.environ.get("TON_NESTED_COMPONENTS") or "").strip().lower() in (
        "1", "true", "yes", "on",
    ):
        rates = {}
        for key, path in VIDEO_PATHS.items():
            if os.path.exists(path):
                br = get_video_bitrate(path)
                if br is not None:
                    rates[key] = float(br)
        if "b0" not in rates:
            raise RuntimeError("TON_NESTED_COMPONENTS missing b0 bitrate; refuse Table-1 fallback")
        base_bitrate = rates["b0"]
        enh_bitrate = float(rates.get("e1") or 0.0)
        peak_bitrate = sum(rates.get(k, 0.0) for k in ("b0", "db1", "db2", "e1", "e2"))
        print(f"✅ Nested b0: {base_bitrate:.3f} Mbps  peak union: {peak_bitrate:.3f} Mbps")
        return base_bitrate, enh_bitrate, float(peak_bitrate)

    base_bitrate = None
    enh_bitrate = None
    peak_bitrate = None

    # ✅ base1 base
    if "base1" in VIDEO_PATHS and os.path.exists(VIDEO_PATHS["base1"]):
        base_bitrate = get_video_bitrate(VIDEO_PATHS["base1"])

    # ✅ base1_enhanced1
    if "base1_enhanced1" in VIDEO_PATHS and os.path.exists(VIDEO_PATHS["base1_enhanced1"]):
        enh_bitrate = get_video_bitrate(VIDEO_PATHS["base1_enhanced1"])

    # Peak ladder rate: prefer highest composite (rep5 / base1_enhanced2 ≈ 6.42)
    for peak_key in ("base1_enhanced2", "base1_enhanced1", "base1"):
        if peak_key in VIDEO_PATHS and os.path.exists(VIDEO_PATHS[peak_key]):
            br = get_video_bitrate(VIDEO_PATHS[peak_key])
            if br is not None:
                peak_bitrate = br if peak_bitrate is None else max(peak_bitrate, br)

    # Table-1 aligned fallbacks
    if base_bitrate is None:
        base_bitrate = 3.07
        print("⚠️ Base : 3.07 Mbps")
    else:
        print(f"✅ Base : {base_bitrate:.2f} Mbps ")

    if enh_bitrate is None:
        enh_bitrate = 4.54  # base1_enhanced1 composite total
        print("⚠️ Enhanced : 4.54 Mbps")
    else:
        print(f"✅ Enhanced base1_enhanced1 : {enh_bitrate:.2f} Mbps ")

    if peak_bitrate is None:
        peak_bitrate = max(base_bitrate, enh_bitrate, 6.42)
        print(f"⚠️ : {peak_bitrate:.2f} Mbps")
    else:
        peak_bitrate = max(peak_bitrate, base_bitrate, enh_bitrate)

    # CRITICAL: do not add base + composite composite already includes base content.
    total_bitrate = float(peak_bitrate)
    print(
        f"✅ max( Rep/composite): {total_bitrate:.2f} Mbps"
        f" Base+ Base={base_bitrate:.2f}, composite_rep4={enh_bitrate:.2f} "
    )

    return base_bitrate, enh_bitrate, total_bitrate

BASE_BITRATE_MBPS = None
ENH_BITRATE_MBPS = None
TOTAL_BITRATE_MBPS = None

# ✅ -> (Root Relay <-> Regional Relay)
# BW = max(350, num_users_per_relay * TOTAL_BITRATE * 1.5)
# 1.5 Unicast 150% Multicast
def calculate_regional_bandwidth(num_users, total_bitrate_mbps=None):
    """
     MD2G-10 -4g 
    
    ⚠️ 
     " " " " 
     Base 
    
     MD2G-10 -4g 120 
    - 479.71 Mbps Base 
    - ≈ =479.71 Mbps
    - 575 Mbps (120% )
    
    Args:
        num_users: 10-100 
        total_bitrate_mbps: Mbps None 
    
    Returns:
        (bw_r0_r1, bw_r0_r2): Mbps 
    
     
    - 10 479.71 Mbps 
    - 10 479.71 Mbps ≈ 
    - 575 Mbps (120% )
      - 10 479.71Mbps < 575Mbps ✅ 
      - 100 4797.1Mbps > 575Mbps ❌ 
      - 10 479.71Mbps < 575Mbps ✅ 
      - 100 600Mbps ≈ 575Mbps ⚠️ 
    """
    # - NETWORK_BW_CONFIG host -> switch -> relay
    # 
    # ✅ ffprobe
    # - Base base1=3.07 Mbps, base2=1.79 Mbps, base3=0.87 Mbps
    # - rep5 = 6.42 Mbps
    # - Enhanced enh1=1.47 Mbps, enh1+2=3.35 Mbps
    # 
    # ✅ relay num_users/2
    # - users_per_relay × = users_per_relay × 6.42 Mbps
    # - Base1 × 1 + Enhanced × users_per_relay = 3.07 + users_per_relay × 3.35 Mbps
    # 
    # - 10 5 × 6.42 = 32.1 Mbps 3.07 + 5 × 3.35 = 19.82 Mbps
    # - 20 10 × 6.42 = 64.2 Mbps 3.07 + 10 × 3.35 = 36.57 Mbps
    # - 50 25 × 6.42 = 160.5 Mbps 3.07 + 25 × 3.35 = 86.82 Mbps
    # - 100 50 × 6.42 = 321 Mbps 3.07 + 50 × 3.35 = 170.57 Mbps
    # 
    users_per_relay = num_users / 2
    # Prefer runtime peak Rep (TOTAL_BITRATE after repair = max selected composite/base).
    if total_bitrate_mbps is None:
        total_bitrate_mbps = TOTAL_BITRATE_MBPS
    MAX_BITRATE_MBPS = float(total_bitrate_mbps) if total_bitrate_mbps else 6.42
    BASE1_BITRATE_MBPS = 3.07
    # Incremental-enhancement idealization for multicast lower-bound estimate only.
    # Wire files are full composites; do NOT add base onto a composite for unicast peak.
    ENHANCED_TOTAL_MBPS = max(0.0, MAX_BITRATE_MBPS - BASE1_BITRATE_MBPS)

    unicast_bw = users_per_relay * MAX_BITRATE_MBPS
    multicast_bw = BASE1_BITRATE_MBPS + users_per_relay * ENHANCED_TOTAL_MBPS
    required_bw = max(unicast_bw, multicast_bw) * 1.2
    FIXED_BOTTLENECK_BW = max(100, int(required_bw))
    
    return FIXED_BOTTLENECK_BW, FIXED_BOTTLENECK_BW

# 10 5 × 6.42 × 1.2 = 38.5 Mbps (3.07 + 5 × 3.35) × 1.2 = 23.8 Mbps
# 100 50 × 6.42 × 1.2 = 385 Mbps (3.07 + 50 × 3.35) × 1.2 = 204.7 Mbps
# calculate_regional_bandwidth()
BW_R0_R1 = 1000
BW_R0_R2 = 1000

# ✅ (Edge Relay <-> Host)
# 
# ✅ > 10 Mbps
# = 15-20 Mbps 1.5-2 Buffer 5-10
# 1.5-1.7 Mbps 10 Mbps Buffer
# ✅ 12M Buffer 30s 5G
# 5G 600Mbps 100Mbps
NETWORK_BW_CONFIG = {
    'wifi': {'bw': 300, 'delay': '5ms', 'loss': 0},
    '4g': {'bw': 40, 'delay': '10ms', 'loss': 0},        # 4G: 40 Mbps
    '5g': {'bw': 800, 'delay': '5ms', 'loss': 0},       # 5G: 800 Mbps
    'fiber_optic': {'bw': 800, 'delay': '5ms', 'loss': 0},  # Fiber: 800 Mbps
}

# ✅ rep5 6.42 Mbps
# Base2 1.79 Mbps + 20% = 2.15 Mbps
# 6.42 Mbps + 20% = 7.7 Mbps
NETWORK_MIN_BW_RECOMMENDED = {
    'wifi': 50.0,
    '4g': 30.0,
    '5g': 50.0,
    'fiber_optic': 80.0,
    'default_mix': 60.0,
    'wifi_dominant': 50.0,
    '5g_dominant': 50.0,
}

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")
NETWORK_DATASETS = {
    'wifi': os.path.join(DATASET_DIR, "wifi_clean.csv"),
    '4g': os.path.join(DATASET_DIR, "4G-network-data_clean.csv"),
    '5g': os.path.join(DATASET_DIR, "5g_final_trace.csv"),
    'fiber_optic': os.path.join(DATASET_DIR, "Optic_Bandwidth_clean_2.csv"),
}
# ===========================================

def read_interface_bytes(host, interface_name):
    """
     RX/TX shell 
    
    Args:
        host: Mininet Host 
        interface_name: 'h1-eth0' 
    
    Returns:
        (rx_bytes, tx_bytes): 
    """
    try:
        # 1 /sys/class/net
        rx_path = f"/sys/class/net/{interface_name}/statistics/rx_bytes"
        tx_path = f"/sys/class/net/{interface_name}/statistics/tx_bytes"
        
        rx_bytes_str = host.cmd(f'cat {rx_path} 2>/dev/null || echo "0"').strip()
        tx_bytes_str = host.cmd(f'cat {tx_path} 2>/dev/null || echo "0"').strip()
        
        if rx_bytes_str.isdigit() and tx_bytes_str.isdigit():
            return int(rx_bytes_str), int(tx_bytes_str)
        
        # 2 fallback /proc/net/dev
        stats_line = host.cmd(f'cat /proc/net/dev 2>/dev/null | grep "{interface_name}:"').strip()
        if stats_line:
            parts = stats_line.split()
            if len(parts) >= 10:
                rx = int(parts[1])  # RX bytes
                tx = int(parts[9])  # TX bytes
                return rx, tx
        
        return 0, 0
    except Exception as e:
        error(f"⚠️ {interface_name} : {e}\n")
        return 0, 0

def load_network_bandwidth_data(network_type, num_users):
    """
     
    
    Args:
        network_type: wifi, 4g, 5g, fiber_optic, default_mix, wifi_dominant, 5g_dominant 
        num_users: 
    
    Returns:
        list: Mbps 
    """
    if not HAS_PANDAS:
        # pandas
        if network_type in ['default_mix', 'wifi_dominant', '5g_dominant']:
            avg_bw = sum(cfg['bw'] for cfg in NETWORK_BW_CONFIG.values()) / len(NETWORK_BW_CONFIG)
            return [avg_bw] * num_users
        else:
            return [NETWORK_BW_CONFIG.get(network_type, NETWORK_BW_CONFIG['wifi'])['bw']] * num_users
    
    bandwidths = []
    
    if network_type in ['default_mix', 'wifi_dominant', '5g_dominant']:
        if network_type == 'wifi_dominant':
            # WiFi 70% 4G 30%
            wifi_count = int(num_users * 0.7)
            g4_count = num_users - wifi_count
            net_types = ['wifi'] * wifi_count + ['4g'] * g4_count
        elif network_type == '5g_dominant':
            g5_count = int(num_users * 0.7)
            g4_count = num_users - g5_count
            net_types = ['5g'] * g5_count + ['4g'] * g4_count
        else:  # default_mix
            # WiFi 30%, 4G 30%, 5G 20%, Fiber 20%
            wifi_count = int(num_users * 0.3)
            g4_count = int(num_users * 0.3)
            g5_count = int(num_users * 0.2)
            fiber_count = num_users - wifi_count - g4_count - g5_count
            net_types = (['wifi'] * wifi_count + ['4g'] * g4_count + 
                        ['5g'] * g5_count + ['fiber_optic'] * fiber_count)
        
        random.shuffle(net_types)
        
        for net_type in net_types:
            if net_type in NETWORK_DATASETS and os.path.exists(NETWORK_DATASETS[net_type]):
                try:
                    df = pd.read_csv(NETWORK_DATASETS[net_type])
                    if 'DL_bitrate_Mbps' in df.columns:
                        bw_col = 'DL_bitrate_Mbps'
                    elif 'bytes_sec (Mbps)' in df.columns:
                        bw_col = 'bytes_sec (Mbps)'
                    elif 'bandwidth_mbps' in df.columns:
                        bw_col = 'bandwidth_mbps'
                    else:
                        bw_col = df.columns[0]
                    
                    valid_bws = df[bw_col].dropna()
                    valid_bws = valid_bws[valid_bws > 0]
                    valid_bws = _ton_gen3_slice_series(valid_bws, net_type)
                    # ✅ 2.15 Mbps Base2 = 1.79 Mbps + 20%
                    # 7.7-10 Mbps 6.42 Mbps
                    MIN_BW_THRESHOLD_BASE = 6.5
                    recommended_min = NETWORK_MIN_BW_RECOMMENDED.get(net_type, MIN_BW_THRESHOLD_BASE)
                    MIN_BW_THRESHOLD = max(MIN_BW_THRESHOLD_BASE, recommended_min)
                    if _ton_gen3_stress_cap() is None and not _command137_raw_4g():
                        valid_bws = valid_bws[valid_bws >= MIN_BW_THRESHOLD]
                    if len(valid_bws) == 0:
                        bw_value = recommended_min
                    else:
                        bw_value = float(valid_bws.sample(1).values[0])
                    max_bw = NETWORK_BW_CONFIG[net_type]['bw']
                    bandwidths.append(max(recommended_min, min(bw_value, max_bw)))
                except Exception as e:
                    bandwidths.append(NETWORK_BW_CONFIG[net_type]['bw'])
            else:
                bandwidths.append(NETWORK_BW_CONFIG[net_type]['bw'])
    else:
        if network_type in NETWORK_DATASETS and os.path.exists(NETWORK_DATASETS[network_type]):
            try:
                df = pd.read_csv(NETWORK_DATASETS[network_type])
                if 'DL_bitrate_Mbps' in df.columns:
                    bw_col = 'DL_bitrate_Mbps'
                elif 'bytes_sec (Mbps)' in df.columns:
                    bw_col = 'bytes_sec (Mbps)'
                elif 'bandwidth_mbps' in df.columns:
                    bw_col = 'bandwidth_mbps'
                else:
                    bw_col = df.columns[0]
                
                valid_bws = df[bw_col].dropna()
                valid_bws = valid_bws[valid_bws > 0]
                valid_bws = _ton_gen3_slice_series(valid_bws, network_type)
                # 6.5 Mbps Base2 = 5.4 Mbps + 20%
                # 12-20 Mbps
                MIN_BW_THRESHOLD_BASE = 6.5
                recommended_min = NETWORK_MIN_BW_RECOMMENDED.get(network_type, MIN_BW_THRESHOLD_BASE)
                MIN_BW_THRESHOLD = max(MIN_BW_THRESHOLD_BASE, recommended_min)
                if _ton_gen3_stress_cap() is None and not _command137_raw_4g():
                    valid_bws = valid_bws[valid_bws >= MIN_BW_THRESHOLD]
                if len(valid_bws) == 0:
                    bandwidths = [recommended_min] * num_users
                else:
                    sampled_bws = valid_bws.sample(num_users, replace=True).values
                    max_bw = NETWORK_BW_CONFIG[network_type]['bw']
                    bandwidths = [max(recommended_min, min(float(bw), max_bw)) for bw in sampled_bws]
            except Exception as e:
                bandwidths = [NETWORK_BW_CONFIG[network_type]['bw']] * num_users
        else:
            bandwidths = [NETWORK_BW_CONFIG[network_type]['bw']] * num_users
    
    return bandwidths

def get_host_network_types(network_type, num_users):
    """
     
    
    Args:
        network_type: wifi, 4g, 5g, fiber_optic, default_mix, wifi_dominant, 5g_dominant 
        num_users: 
    
    Returns:
        list: 
    """
    
    if network_type in ['default_mix', 'wifi_dominant', '5g_dominant']:
        if network_type == 'wifi_dominant':
            # WiFi 70% 4G 30%
            wifi_count = int(num_users * 0.7)
            g4_count = num_users - wifi_count
            net_types = ['wifi'] * wifi_count + ['4g'] * g4_count
        elif network_type == '5g_dominant':
            g5_count = int(num_users * 0.7)
            g4_count = num_users - g5_count
            net_types = ['5g'] * g5_count + ['4g'] * g4_count
        else:  # default_mix
            # WiFi 30%, 4G 30%, 5G 20%, Fiber 20%
            wifi_count = int(num_users * 0.3)
            g4_count = int(num_users * 0.3)
            g5_count = int(num_users * 0.2)
            fiber_count = num_users - wifi_count - g4_count - g5_count
            net_types = (['wifi'] * wifi_count + ['4g'] * g4_count + 
                        ['5g'] * g5_count + ['fiber_optic'] * fiber_count)
        
        random.shuffle(net_types)
        return net_types
    else:
        return [network_type] * num_users

def calculate_jfi(loads):
    """
     Jain's Fairness Index (JFI)
    
    Args:
        loads: [x1, x2, ..., xK] 
    
    Returns:
        JFI 0-1 
    """
    if not loads or len(loads) == 0:
        return 1.0
    
    loads = [float(x) for x in loads if x > 0]
    if not loads:
        return 1.0
    
    n = len(loads)
    sum_x = sum(loads)
    sum_x_squared = sum(x * x for x in loads)
    
    if sum_x_squared == 0:
        return 1.0
    
    jfi = (sum_x * sum_x) / (n * sum_x_squared)
    return max(0.0, min(1.0, jfi))

# ================= Buffer =================
class BufferModel:
    """
     
    
     
    - 1.0x
    - fragment dur_frag 30fps 1/30 
    - fragment → buffer += dur_frag * received_fragments
    - wall-clock buffer -= Δt 0 
    """
    def __init__(self, fps=30.0):
        self.fps = fps
        self.dur_frag = 1.0 / fps
        self.buffer_sec = 0.0
        self.received_fragments = 0
        self.last_update_time = time.monotonic()
        self.state = "STARTUP"  # STARTUP, PLAYING, REBUFFER
        self.stall_count = 0
        self.stall_total_sec = 0.0
        self.stall_start_time = None
    
    def update_received(self, fragment_count):
        """ fragment """
        self.received_fragments = fragment_count
        # buffer = fragment_count * dur_frag
        self.buffer_sec = fragment_count * self.dur_frag
    
    def update_playback(self, current_time=None):
        """
         
        
        Args:
            current_time: time.monotonic() 
        
        Returns:
            (buffer_level_sec, stall_count, stall_total_sec): 
        """
        if current_time is None:
            current_time = time.monotonic()
        
        dt = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # STARTUP -> PLAYING -> REBUFFER
        if self.state == "STARTUP":
            # 2 PLAYING
            if self.buffer_sec >= 2.0:
                self.state = "PLAYING"
        elif self.state == "PLAYING":
            self.buffer_sec = max(0.0, self.buffer_sec - dt)
            
            # REBUFFER
            if self.buffer_sec <= 0.0:
                self.state = "REBUFFER"
                self.stall_start_time = current_time
                self.stall_count += 1
        elif self.state == "REBUFFER":
            # buffer 0
            self.buffer_sec = 0.0
            if self.stall_start_time:
                self.stall_total_sec += dt
            
            # >0 REBUFFER
            if self.buffer_sec > 0.0:
                self.state = "PLAYING"
                self.stall_start_time = None
        
        return self.buffer_sec, self.stall_count, self.stall_total_sec
    
    def get_state(self):
        return {
            "buffer_level_sec": self.buffer_sec,
            "stall_count": self.stall_count,
            "stall_total_sec": self.stall_total_sec,
            "state": self.state
        }
# ===========================================

def check_files():
    missing = []
    for name, path in BIN_PATHS.items():
        if not os.path.exists(path): missing.append(f"Bin: {name} -> {path}")
    
    if missing:
        error("❌ :\n" + "\n".join(missing) + "\n")
        return False
    return True

def prepare_layered_videos():
    """
     bbb.mp4 ( )
    
     9 redandblack_6_live 
    Base: 10Mbps, 2 -> 150MB
    Enhanced: 1Mbps, 2 -> 15MB
    """
    info("⚠️ prepare_layered_videos() 9 redandblack_6_live \n")
    return True

def generate_certs():
    """ relay SAN"""
    import shutil
    import stat
    import tempfile
    
    cert_dir = CERT_DIR
    
    if os.path.exists(cert_dir):
        try:
            shutil.rmtree(cert_dir)
        except PermissionError:
            try:
                os.chmod(cert_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                shutil.rmtree(cert_dir)
            except:
                os.system(f"rm -rf {cert_dir} 2>/dev/null || true")
    
    try:
        os.makedirs(cert_dir, mode=0o755, exist_ok=True)
    except PermissionError:
        os.system(f"mkdir -p {cert_dir} && chmod 755 {cert_dir} 2>/dev/null || true")
        if not os.path.exists(cert_dir):
            cert_dir = os.path.join(tempfile.gettempdir(), f"moq_certs_{os.getpid()}")
            os.makedirs(cert_dir, mode=0o755, exist_ok=True)
            try:
                info(f"⚠️ : {cert_dir}\n")
            except:
                print(f"⚠️ : {cert_dir}")
    
    cert, key = f"{cert_dir}/cert.pem", f"{cert_dir}/key.pem"
    config_path = f"{cert_dir}/cert.conf"
    
    # OpenSSL relay SAN
    config_content = """[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = localhost

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = r0.local
DNS.3 = r0
DNS.4 = r1.local
DNS.5 = r1
DNS.6 = r2.local
DNS.7 = r2
IP.1 = 127.0.0.1
IP.2 = ::1
IP.3 = 10.0.1.1
IP.4 = 10.0.2.2
IP.5 = 10.0.3.2
"""
    try:
        with open(config_path, 'w') as f:
            f.write(config_content)
        os.chmod(config_path, 0o644)
    except PermissionError:
        error(f"❌ : {config_path}\n")
        error(" sudo \n")
        raise
    
    cmd = (f"openssl req -newkey rsa:2048 -nodes -keyout {key} "
           f"-x509 -days 365 -out {cert} "
           f"-config {config_path} -extensions v3_req >/dev/null 2>&1")
    result = os.system(cmd)
    if result != 0:
        error(f"❌ : {result}\n")
        error(f" openssl \n")
        raise RuntimeError(" ")
    
    return cert, key

def generate_auth_keys():
    """ JWT key cluster token """
    import os
    import subprocess
    
    # auth
    os.makedirs(AUTH_DIR, mode=0o755, exist_ok=True)
    
    key_file = os.path.join(AUTH_DIR, "root.jwk")
    token_file = os.path.join(AUTH_DIR, "cluster.jwt")
    
    if not os.path.exists(key_file):
        info("🔑 JWT key...\n")
        cmd = f"{BIN_PATHS['token']} --key {key_file} generate"
        result = os.system(cmd)
        if result != 0:
            error(f"❌ JWT key : {result}\n")
            raise RuntimeError("JWT key ")
        info(f"✅ JWT key : {key_file}\n")
    else:
        info(f"✅ JWT key: {key_file}\n")
    
    # cluster token
    if not os.path.exists(token_file):
        info("🎫 cluster token...\n")
        # cluster token
        cmd = (f"{BIN_PATHS['token']} --key {key_file} sign "
               f"--root \"\" --subscribe \"\" --publish \"\" --cluster "
               f"> {token_file}")
        result = os.system(cmd)
        if result != 0:
            error(f"❌ Cluster token : {result}\n")
            raise RuntimeError("Cluster token ")
        info(f"✅ Cluster token : {token_file}\n")
    else:
        info(f"✅ cluster token: {token_file}\n")
    
    return key_file, token_file

def generate_relay_config(node_name, cert, key, auth_key_file):
    """ relay auth public = "anon" """
    config_path = f"/tmp/{TMP_PREFIX}{node_name}.toml"
    # ✅ auth public = "anon" /anon
    config = f"""
[log]
level = "info"

[server]
# ✅ listen bind
listen = "0.0.0.0:4443"

[auth]
# ✅ auth public = "anon" /anon
# /anon/** token
key = "{auth_key_file}"
public = "anon"

[client]
# leaf nodes root node
tls.disable_verify = true
"""
    with open(config_path, "w") as f: f.write(config)
    return config_path

def setup_routing(net, num_subscribers=10):
    n0 = net.get('n0')
    r0 = net.get('r0')
    r1 = net.get('r1')
    r2 = net.get('r2')
    subscribers = [net.get(f'h{i}') for i in range(1, num_subscribers + 1)]
    
    info(" (Fix: Explicit Host Routes)...\n")
    for n in net.hosts: n.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
    
    r0.cmd("sysctl -w net.ipv4.ip_forward=1")
    r1.cmd("sysctl -w net.ipv4.ip_forward=1")
    r2.cmd("sysctl -w net.ipv4.ip_forward=1")
    
    # --- Core ---
    r0.cmd("ifconfig r0-eth0 10.0.1.1/24 up")
    r0.cmd("ifconfig r0-eth1 10.0.2.1/24 up")
    r0.cmd("ifconfig r0-eth2 10.0.3.1/24 up")
    
    r1.cmd("ifconfig r1-eth0 10.0.2.2/24 up")
    r2.cmd("ifconfig r2-eth0 10.0.3.2/24 up")

    # --- ✅ Switch ---
    r1_sub_count = num_subscribers // 2
    
    r1.cmd("ifconfig r1-eth1 10.0.4.1/24 up")
    info(" ✅ r1 LAN (r1-eth1) 10.0.4.1/24\n")
    
    r2.cmd("ifconfig r2-eth1 10.0.5.1/24 up")
    info(" ✅ r2 LAN (r2-eth1) 10.0.5.1/24\n")
    
    # 1. Subscriber IP
    for i, host in enumerate(subscribers, 1):
        # host
        host.cmd(f"ifconfig h{i}-eth0 0.0.0.0 2>/dev/null || true")
        
        if i <= r1_sub_count:
            host_ip = f"10.0.4.{i+1}"
            gateway = "10.0.4.1"
            
            # Host
            host.cmd(f"ifconfig h{i}-eth0 {host_ip}/24 up")
            host.cmd(f"route add default gw {gateway} 2>/dev/null || ip route add default via {gateway}")
            
            info(f" ✅ h{i} : {host_ip}/24, : {gateway}\n")
            
        else:
            idx = i - r1_sub_count
            host_ip = f"10.0.5.{idx+1}"
            gateway = "10.0.5.1"
            
            # Host
            host.cmd(f"ifconfig h{i}-eth0 {host_ip}/24 up")
            host.cmd(f"route add default gw {gateway} 2>/dev/null || ip route add default via {gateway}")
            
            info(f" ✅ h{i} : {host_ip}/24, : {gateway}\n")

    # n0 -> r0
    n0.cmd("ip route del default 2>/dev/null || true")
    n0.cmd("ip route add default via 10.0.1.1")
    
    r0.cmd("ip route del 10.0.4.0/24 2>/dev/null || true")
    r0.cmd("ip route add 10.0.4.0/24 via 10.0.2.2")
    r0.cmd("ip route del 10.0.5.0/24 2>/dev/null || true")
    r0.cmd("ip route add 10.0.5.0/24 via 10.0.3.2")
    
    r1.cmd("ip route del default 2>/dev/null || true")
    r1.cmd("ip route add default via 10.0.2.1")
    r1.cmd("ip route del 10.0.1.0/24 2>/dev/null || true")
    r1.cmd("ip route add 10.0.1.0/24 via 10.0.2.1")
    r1.cmd("ip route del 10.0.3.0/24 2>/dev/null || true")
    r1.cmd("ip route add 10.0.3.0/24 via 10.0.2.1")
    r1.cmd("ip route del 10.0.5.0/24 2>/dev/null || true")
    r1.cmd("ip route add 10.0.5.0/24 via 10.0.2.1")
    
    r2.cmd("ip route del default 2>/dev/null || true")
    r2.cmd("ip route add default via 10.0.3.1")
    r2.cmd("ip route del 10.0.1.0/24 2>/dev/null || true")
    r2.cmd("ip route add 10.0.1.0/24 via 10.0.3.1")
    r2.cmd("ip route del 10.0.2.0/24 2>/dev/null || true")
    r2.cmd("ip route add 10.0.2.0/24 via 10.0.3.1")
    r2.cmd("ip route del 10.0.4.0/24 2>/dev/null || true")
    r2.cmd("ip route add 10.0.4.0/24 via 10.0.3.1")

    info(" ARP ...\n")
    time.sleep(1)
    n0.cmd("ping -c 1 -W 1 10.0.1.1 >/dev/null 2>&1 || true")
    r0.cmd("ping -c 1 -W 1 10.0.2.2 >/dev/null 2>&1 || true")
    r0.cmd("ping -c 1 -W 1 10.0.3.2 >/dev/null 2>&1 || true")
    
    info(" ...\n")
    for i in range(1, num_subscribers + 1):
        h = net.get(f'h{i}')
        gw = "10.0.4.1" if i <= r1_sub_count else "10.0.5.1"
        result = h.cmd(f"ping -c 1 -W 1 {gw} >/dev/null 2>&1 && echo OK || echo FAIL").strip()
        if result == "OK":
            info(f" ✅ h{i} -> ({gw}) \n")
        else:
            error(f" ❌ h{i} -> ({gw}) ! \n")
    
    # Hosts relay
    # ✅ r0.local r0-eth1 (10.0.2.1) r0
    # r0-eth0 (10.0.1.1) n0 (publisher) r0-eth1 (10.0.2.1)
    hosts_mapping = """
10.0.2.1 r0.local r0
10.0.2.2 r1.local r1
10.0.3.2 r2.local r2
"""
    # ✅ n0 (publisher) r0 r0-eth0 (10.0.1.1)
    # n0 r0.local r0 0.0.0.0:4443
    n0_hosts_mapping = """
10.0.1.1 r0.local r0
10.0.2.2 r1.local r1
10.0.3.2 r2.local r2
"""
    
    # n0 hosts r0-eth0 IP
    n0 = net.get('n0')
    n0.cmd("sed -i '/ r0\\.local/d' /etc/hosts 2>/dev/null || true")
    n0.cmd("sed -i '/ r1\\.local/d' /etc/hosts 2>/dev/null || true")
    n0.cmd("sed -i '/ r2\\.local/d' /etc/hosts 2>/dev/null || true")
    n0.cmd(f"echo '{n0_hosts_mapping}' >> /etc/hosts")
    
    # hosts r0-eth1 IP
    for node in net.hosts:
        if node.name == 'n0':
            continue
        node.cmd("sed -i '/ r0\\.local/d' /etc/hosts 2>/dev/null || true")
        node.cmd("sed -i '/ r1\\.local/d' /etc/hosts 2>/dev/null || true")
        node.cmd("sed -i '/ r2\\.local/d' /etc/hosts 2>/dev/null || true")
        node.cmd(f"echo '{hosts_mapping}' >> /etc/hosts")
    
    # hosts
    info(" hosts ...\n")
    # ✅ r0.local 10.0.2.1 (r0-eth1)
    for relay_name, relay_ip in [("r0", "10.0.2.1"), ("r1", "10.0.2.2"), ("r2", "10.0.3.2")]:
        relay = net.get(relay_name)
        result = relay.cmd(f"getent hosts {relay_name}.local 2>&1 | head -1 || echo 'FAILED'").strip()
        if "FAILED" not in result and result:
            ip = result.split()[0] if result else "unknown"
            info(f"✅ {relay_name} {relay_name}.local -> {ip}\n")
        else:
            error(f"❌ {relay_name} {relay_name}.local\n")

def cleanup_all_processes(tmp_prefix=None, recorded_pids=None, log_path=None):
    """
    Cell-scoped cleanup (command40 §8.5).
    Only kill recorded PIDs and processes whose cmdline contains this cell's
    TMP_PREFIX / log_path fingerprint. Never kill ToN (moq_cluster_Sigcomm26) or
    globally match all moq-*/hang processes.
    """
    import subprocess

    current_pid = os.getpid()
    prefix = tmp_prefix if tmp_prefix is not None else TMP_PREFIX
    pids_to_kill = set()
    if recorded_pids:
        for p in recorded_pids:
            s = str(p).strip().split()[0] if p else ""
            if s.isdigit() and s != str(current_pid):
                pids_to_kill.add(s)
    for p in CELL_RECORDED_PIDS:
        s = str(p).strip().split()[0] if p else ""
        if s.isdigit() and s != str(current_pid):
            pids_to_kill.add(s)

    fingerprints = []
    if prefix and prefix != "test2_":
        fingerprints.append(prefix)
    if log_path:
        lp = str(log_path).rstrip("/")
        fingerprints.append(lp)
        # Also match decision-feature CSV basename unique to this cell
        fingerprints.append(os.path.basename(lp))

    info("🧹 [scoped cleanup] cell-fingerprint / recorded-PID only (never global moq kill)\n")
    info(f"   TMP_PREFIX={prefix!r} log_path={log_path!r} recorded={len(pids_to_kill)}\n")

    for fp in fingerprints:
        if not fp or len(fp) < 8:
            continue
        try:
            result = subprocess.run(
                ["pgrep", "-af", fp],
                capture_output=True, text=True, timeout=2,
            )
            for line in (result.stdout or "").splitlines():
                parts = line.strip().split(None, 1)
                if not parts:
                    continue
                pid = parts[0]
                cmd = parts[1] if len(parts) > 1 else ""
                if pid == str(current_pid):
                    continue
                if "moq_cluster_Sigcomm26" in cmd:
                    continue
                if "moq_cluster_Sigcomm.py" in cmd:
                    # Never kill the active cell runner (cmdline contains --log_path=this cell).
                    continue
                if "command40_resume_supervisor" in cmd or "sigcomm_run_matrix" in cmd:
                    continue
                if "command40_watchdog" in cmd or "command40_health" in cmd:
                    continue
                if fp in cmd:
                    pids_to_kill.add(pid)
        except Exception:
            pass

    def _safe_kill(pid, sig="-TERM"):
        try:
            cmdline = ""
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            if "moq_cluster_Sigcomm26" in cmdline:
                return
            subprocess.run(["kill", sig, pid], capture_output=True, timeout=1)
        except Exception:
            pass

    for pid in list(pids_to_kill):
        _safe_kill(pid, "-TERM")
    time.sleep(0.5)
    for pid in list(pids_to_kill):
        if os.path.exists(f"/proc/{pid}"):
            _safe_kill(pid, "-9")
    # Best-effort: remove this cell's decision files so orphans cannot keep writing shared paths
    if prefix:
        for name in ("r0_decisions.json", "r1_decisions.json", "r2_decisions.json"):
            try:
                os.remove(f"/tmp/{prefix}{name}")
            except OSError:
                pass
    CELL_RECORDED_PIDS.clear()
    info("✅ scoped cleanup done\n\n")

def diagnose_zero_rx_clients(net, num_subscribers, log_path, r0, r1, r2, TMP_PREFIX):
    """
     rx_bytes 0 A1/A2/A3 
    
    A1: / 
    A2: TLS/QUIC/ /URL 
    A3: /track/catalog/ 
    """
    info("\n" + "="*80 + "\n")
    info("🔍 rx_bytes 0 \n")
    info("="*80 + "\n\n")
    
    # perf.csv rx_bytes 0
    zero_rx_clients = []
    for i in range(1, num_subscribers + 1):
        perf_csv = os.path.join(log_path, f"client_h{i}_perf.csv")
        if os.path.exists(perf_csv):
            try:
                import pandas as pd
                df = pd.read_csv(perf_csv)
                if len(df) > 0:
                    max_rx = df['rx_bytes'].max()
                    if max_rx == 0:
                        zero_rx_clients.append(i)
            except:
                zero_rx_clients.append(i)
        else:
            zero_rx_clients.append(i)
    
    if not zero_rx_clients:
        info("✅ rx_bytes \n")
        return
    
    info(f"📊 {len(zero_rx_clients)} rx_bytes 0 : {zero_rx_clients}\n\n")
    
    a1_clients = []
    a2_clients = []
    a3_clients = []
    
    for client_id in zero_rx_clients:
        host = net.get(f'h{client_id}')
        if not host:
            a1_clients.append(client_id)
            continue
        
        info(f"🔍 h{client_id}...\n")
        
        # Exact PID tracking only never treat stale other_procs as success (command40).
        dispatch_pid = host.cmd(f"pgrep -f 'dispatch_strategy.*--host_id {client_id}' || echo ''").strip()
        moq_sub_pid = host.cmd(f"pgrep -f 'moq-sub' || echo ''").strip()
        launch_json = os.path.join(log_path, f"subscriber_h{client_id}_launch.json")
        recorded_pid = ""
        if os.path.isfile(launch_json):
            try:
                with open(launch_json, "r", encoding="utf-8") as lf:
                    recorded_pid = str(json.load(lf).get("pid") or "").strip()
            except Exception:
                recorded_pid = ""

        has_process = subscriber_pid_ok(dispatch_pid) or subscriber_pid_ok(recorded_pid)
        if not has_process:
            a1_clients.append(client_id)
            info(f" ❌ A1: h{client_id} (dispatch/recorded PID missing)\n")
            continue

        show_d = dispatch_pid if subscriber_pid_ok(dispatch_pid) else (
            recorded_pid if subscriber_pid_ok(recorded_pid) else None
        )
        show_m = moq_sub_pid if subscriber_pid_ok(moq_sub_pid) else None
        if show_d is None and show_m is None:
            a1_clients.append(client_id)
            info(f"  ❌ A1: h{client_id} PID N/A — not counting as running\n")
            continue
        info(f" ✅ (dispatch PID: {show_d}, moq-sub PID: {show_m or 'none'})\n")
        
        info(f" 🔍 DNS ...\n")
        
        # relay
        if client_id <= num_subscribers // 2:
            target_relay = "r1"
            relay_ip = "10.0.2.2"
            relay_domain = "r1.local"
        else:
            target_relay = "r2"
            relay_ip = "10.0.3.2"
            relay_domain = "r2.local"
        
        r0_dns = host.cmd(f"getent hosts r0.local || echo 'FAILED'").strip()
        # relay
        relay_dns = host.cmd(f"getent hosts {relay_domain} || echo 'FAILED'").strip()
        # ping
        ping_result = host.cmd(f"ping -c 1 {relay_ip} 2>&1 | grep '1 received' || echo 'FAILED'").strip()
        
        dns_ok = "FAILED" not in r0_dns and "FAILED" not in relay_dns
        ping_ok = "FAILED" not in ping_result
        
        if not dns_ok or not ping_ok:
            a2_clients.append(client_id)
            info(f" ❌ A2: h{client_id} DNS \n")
            info(f"     r0.local DNS: {'✅' if 'FAILED' not in r0_dns else '❌'} {r0_dns}\n")
            info(f"     {relay_domain} DNS: {'✅' if 'FAILED' not in relay_dns else '❌'} {relay_dns}\n")
            info(f"     Ping {relay_ip}: {'✅' if ping_ok else '❌'}\n")
            info(f" : /etc/hosts \n")
            continue
        
        info(f" ✅ DNS \n")
        
        dispatch_log = os.path.join(log_path, f"client_h{client_id}_gst.log")
        old_log = f"/tmp/{TMP_PREFIX}h{client_id}_dispatch.log"
        log_file = dispatch_log if os.path.exists(dispatch_log) else old_log
        
        log_content = ""
        if os.path.exists(log_file):
            try:
                with open(log_file, 'rb') as f:
                    log_bytes = f.read()
                    log_content = ''.join(chr(b) if 32 <= b < 127 or b in [9, 10, 13] else ' ' for b in log_bytes[-10000:])
            except:
                pass
        
        connection_errors = [
            "handshake failed", "cert verify", "401", "404", "track not found",
            "opening handshake failed", "connection refused", "timeout",
            "TLS", "QUIC", "authentication", "unauthorized"
        ]
        
        has_connection_error = any(err.lower() in log_content.lower() for err in connection_errors)
        
        if has_connection_error:
            a2_clients.append(client_id)
            info(f" ❌ A2: h{client_id} \n")
            info(f" : {log_file}\n")
            error_lines = [line for line in log_content.split('\n') if any(err.lower() in line.lower() for err in connection_errors)]
            for line in error_lines[-5:]:
                if line.strip():
                    info(f"     {line[:100]}\n")
            continue
        
        # B3: relay /
        info(f" 🔍 relay ...\n")
        
        r0_log_path = f"/tmp/{TMP_PREFIX}r0.log"
        r0_log_content = ""
        if r0:
            try:
                r0_log_content = r0.cmd(f"cat {r0_log_path} 2>&1 | tail -1000").strip()
            except:
                pass
        
        # IP host_id
        has_relay_connection = False
        if r0_log_content:
            # IP hostname
            client_patterns = [f"h{client_id}", f"10.0.2.{client_id}", f"10.0.3.{client_id}"]
            has_relay_connection = any(pattern in r0_log_content for pattern in client_patterns)
        
        if not has_relay_connection:
            # A2: relay
            a2_clients.append(client_id)
            info(f" ❌ A2: h{client_id} relay \n")
            info(f" : r0 cat {r0_log_path} | grep -i 'h{client_id}'\n")
            continue
        
        subscribe_pattern = r'subscribe.*started|subscribe.*success|track.*subscribed'
        has_subscribe = bool(re.search(subscribe_pattern, log_content, re.IGNORECASE))
        
        if has_subscribe:
            a3_clients.append(client_id)
            info(f" ❌ A3: h{client_id} \n")
            info(f" : /track/catalog/ \n")
            info(f" : r0 cat {r0_log_path} | grep -i 'catalog\\|track\\|subscribe'\n")
        else:
            a2_clients.append(client_id)
            info(f" ❌ A2: h{client_id} \n")
    
    info("\n" + "="*80 + "\n")
    info("📊 \n")
    info("="*80 + "\n\n")
    
    info(f"A1 ( ): {len(a1_clients)} - {a1_clients}\n")
    info(f"A2 ( ): {len(a2_clients)} - {a2_clients}\n")
    info(f"A3 ( ): {len(a3_clients)} - {a3_clients}\n\n")
    
    info("="*80 + "\n")
    info("💡 \n")
    info("="*80 + "\n\n")
    
    if a1_clients:
        info(f"🔧 A1 ( - {len(a1_clients)} ):\n")
        info(f" 1. host \n")
        info(f" 2. host / / \n")
        info(f" 3. : h{a1_clients[0]} python3 dispatch_strategy_enhanced_unified_Sigcomm.py --host_id {a1_clients[0]} ...\n\n")
    
    if a2_clients:
        info(f"🔧 A2 ( - {len(a2_clients)} ):\n")
        info(f" 1. DNS : h{a2_clients[0]} getent hosts r0.local\n")
        info(f" 2. /etc/hosts \n")
        info(f" 3. URL/public /token \n")
        info(f" 4. : '5 users / 2s' '2 users / 2s' '5 users / 5s'\n")
        info(f" 5. \n\n")
    
    if a3_clients:
        info(f"🔧 A3 ( - {len(a3_clients)} ):\n")
        info(f" 1. /track/catalog \n")
        info(f" 2. relay catalog: r0 cat {r0_log_path} | grep -i catalog\n")
        info(f" 3. publish/subscribe \n\n")
    
    if len(a2_clients) + len(a1_clients) > len(zero_rx_clients) * 0.5:
        info("="*80 + "\n")
        info("⚠️ D1 \n")
        info("="*80 + "\n\n")
        info(" :\n")
        info("1. batch + :\n")
        info(" '5 users / 2s' '2 users / 2s' '5 users / 5s'\n")
        info(" : run_moq_experiment() time.sleep()\n\n")
        info("2. :\n")
        info(" moq-sub N rx_bytes handshake failed \n")
        info(" kill 3 \n\n")
        info("3. :\n")
        info(" semaphore/ K K=3~5 \n\n")
    
    # D2: URL/ /token
    info("="*80 + "\n")
    info("💡 D2 URL/public /token \n")
    info("="*80 + "\n\n")
    info("1. client :\n")
    info("   - relay URL\n")
    info(" - subscribe track \n")
    info(" - jwt \n")
    info(" : dispatch_strategy_enhanced_unified_Sigcomm.py \n\n")
    info("2. client client user_id \n\n")
    
    return {
        'a1': a1_clients,
        'a2': a2_clients,
        'a3': a3_clients,
        'total_zero': zero_rx_clients
    }

def perform_hard_checks(net, num_subscribers, r0, r1, r2, zero_client_ids=None):
    """
     B1/B2/B3 
    
    B1: host 
    B2: host relay DNS+ 
    B3: host /relay 
    """
    if zero_client_ids is None:
        zero_client_ids = list(range(1, min(4, num_subscribers + 1))) + \
                         list(range(max(1, num_subscribers - 2), num_subscribers + 1))
    
    info("\n" + "="*80 + "\n")
    info(f"🔍 (B1/B2/B3) - {len(zero_client_ids)} \n")
    info("="*80 + "\n\n")
    
    for client_id in zero_client_ids[:10]:
        host = net.get(f'h{client_id}')
        if not host:
            info(f"❌ h{client_id} \n\n")
            continue
        
        info(f"📋 h{client_id}:\n")
        
        info(f" B1. ...\n")
        procs = host.cmd(f"ps aux | egrep 'moq-sub|chrome|node|gst|python.*dispatch' | grep -v grep || echo ''").strip()
        if procs:
            info(f" ✅ :\n")
            for line in procs.split('\n')[:3]:
                if line.strip():
                    info(f"        {line[:80]}\n")
        else:
            info(f" ❌ \n")
        info(f"\n")
        
        info(f" B2. DNS ...\n")
        
        # relay
        if client_id <= num_subscribers // 2:
            relay_domain = "r1.local"
            relay_ip = "10.0.2.2"
        else:
            relay_domain = "r2.local"
            relay_ip = "10.0.3.2"
        
        r0_dns = host.cmd(f"getent hosts r0.local 2>&1").strip()
        relay_dns = host.cmd(f"getent hosts {relay_domain} 2>&1").strip()
        
        info(f"     r0.local DNS: {r0_dns}\n")
        info(f"     {relay_domain} DNS: {relay_dns}\n")
        
        # ping
        ping_result = host.cmd(f"ping -c 1 {relay_ip} 2>&1").strip()
        if "1 received" in ping_result:
            info(f" ✅ Ping {relay_ip}: \n")
        else:
            info(f" ❌ Ping {relay_ip}: \n")
            info(f"        {ping_result[:200]}\n")
        info(f"\n")
        
        # B3: relay
        info(f" B3. relay ...\n")
        if r0:
            r0_log_path = f"/tmp/{TMP_PREFIX}r0.log"
            r0_connections = r0.cmd(f"cat {r0_log_path} 2>&1 | grep -i 'h{client_id}\\|10.0' | tail -5 || echo ' '").strip()
            if r0_connections and " " not in r0_connections:
                info(f" ✅ r0 :\n")
                for line in r0_connections.split('\n')[:3]:
                    if line.strip():
                        info(f"        {line[:100]}\n")
            else:
                info(f" ❌ r0 \n")
            
            target_relay = r1 if client_id <= num_subscribers // 2 else r2
            relay_name = "r1" if client_id <= num_subscribers // 2 else "r2"
            if target_relay:
                relay_log_path = f"/tmp/{TMP_PREFIX}{relay_name}.log"
                relay_connections = target_relay.cmd(f"cat {relay_log_path} 2>&1 | grep -i 'h{client_id}\\|subscribe' | tail -5 || echo ' '").strip()
                if relay_connections and " " not in relay_connections:
                    info(f" ✅ {relay_name} :\n")
                    for line in relay_connections.split('\n')[:3]:
                        if line.strip():
                            info(f"        {line[:100]}\n")
                else:
                    info(f" ❌ {relay_name} \n")
        info(f"\n")
        
        info("-" * 80 + "\n\n")


def run_moq_experiment(num_subscribers=10, strategy="md2g", network_type="4g", 
                       log_path=None, duration=120, interval=1.0, model_path=None,
                       device_map_path=None):
    """
     MoQ + Clustering + perf.csv 
    
    Args:
        num_subscribers: Subscriber 10 
        strategy: md2g, rolling, heuristic, clustering, groot 
        network_type: wifi, 4g, 5g, fiber_optic, default_mix, wifi_dominant, 5g_dominant 
        log_path: None 
        duration: 
        interval: 
        model_path: rolling md2g 
    """
    setLogLevel('info')
    
    global BASE_BITRATE_MBPS, ENH_BITRATE_MBPS, TOTAL_BITRATE_MBPS
    global TMP_PREFIX, AUTH_DIR, SIGCOMM_PYTHON, CELL_RECORDED_PIDS
    BASE_BITRATE_MBPS, ENH_BITRATE_MBPS, TOTAL_BITRATE_MBPS = init_video_bitrates()
    info(
        f"📊 : Base={BASE_BITRATE_MBPS:.2f} Mbps, "
        f"Enhanced(composite)={ENH_BITRATE_MBPS:.2f} Mbps, "
        f"PeakRep/Total={TOTAL_BITRATE_MBPS:.2f} Mbps "
        f"(peak selected Rep; not Base+composite)\n"
    )
    
    # ✅ log_path
    if log_path is None:
        # log_path
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = f"test_logs_{timestamp}/{network_type}/{strategy}/users_{num_subscribers}"
    # else: log_path
    
    os.makedirs(log_path, exist_ok=True)
    # Cell-scoped TMP so /tmp/test2_* is never shared across cells (command40 A).
    TMP_PREFIX = derive_cell_tmp_prefix(log_path)
    AUTH_DIR = f"/tmp/{TMP_PREFIX}auth"
    os.makedirs(AUTH_DIR, exist_ok=True)
    os.environ["SIGCOMM_CELL_TMP"] = TMP_PREFIX
    CELL_STATE_DIR = f"/tmp/{TMP_PREFIX}client_state"
    os.makedirs(CELL_STATE_DIR, exist_ok=True)
    os.environ["SIGCOMM_CELL_STATE_DIR"] = CELL_STATE_DIR
    os.environ["SIGCOMM_CELL_LOG_PATH"] = log_path
    SIGCOMM_PYTHON = resolve_sigcomm_python()
    os.environ["SIGCOMM_PYTHON"] = SIGCOMM_PYTHON
    CELL_RECORDED_PIDS.clear()
    # Track validity inputs across the run
    registered_publishers = set()
    expected_publishers = set()
    subscriber_pids = []
    leaf_egress_delta = 0
    cell_valid = False

    info(f"📁 : {log_path}\n")
    info(f"📁 TMP_PREFIX={TMP_PREFIX} SIGCOMM_PYTHON={SIGCOMM_PYTHON}\n")
    info(f"📊 : ={strategy}, ={network_type}, ={num_subscribers}, ={duration} \n")
    
    # ✅ cell-scoped
    cleanup_all_processes(tmp_prefix=TMP_PREFIX, recorded_pids=None, log_path=log_path)
    
    if not check_files():
        raise SystemExit(2)
    
    if not prepare_layered_videos():
        error("❌ \n")
        raise SystemExit(2)    
    cert, key = generate_certs()
    
    # ✅ JWT key cluster token
    auth_key_file, cluster_token_file = generate_auth_keys()

    net = Mininet(controller=Controller, switch=OVSKernelSwitch, link=TCLink)
    info(f" (Root Relay + Leaf Relays + {num_subscribers} Subscriber)...\n")
    
    # n0 (Publisher) -> r0 (Root Relay) -> r1, r2 (Leaf Relays) -> h1-hN (Subscribers)
    
    n0 = net.addHost('n0', ip='10.0.1.2/24')
    r0 = net.addHost('r0', ip='10.0.1.1/24')  # Root Relay
    r1 = net.addHost('r1', ip='10.0.2.2/24')  # Leaf Relay 1
    r2 = net.addHost('r2', ip='10.0.3.2/24')  # Leaf Relay 2
    
    # Subscriber
    subscribers = []
    r1_sub_count = num_subscribers // 2
    r2_sub_count = num_subscribers - r1_sub_count
    
    # host CPU CPU
    # ≤30 host 10% CPU
    # >30 host 20% CPU CPU
    if num_subscribers <= 30:
        cpu_limit = 0.1
    else:
        cpu_limit = 0.2
    
    for i in range(1, num_subscribers + 1):
        if i <= r1_sub_count:
            host = net.addHost(f'h{i}', ip=f'10.0.4.{i+1}/24', cpu=cpu_limit)
            subscribers.append(host)
        else:
            idx = i - r1_sub_count
            host = net.addHost(f'h{i}', ip=f'10.0.5.{idx+1}/24', cpu=cpu_limit)
            subscribers.append(host)
    
    # ✅ Switch ping loss
    # Switch
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    
    host_net_types = get_host_network_types(network_type, num_subscribers)
    host_bandwidths = load_network_bandwidth_data(network_type, num_subscribers)
    info(f"📊 : {network_type}, : {min(host_bandwidths):.2f}-{max(host_bandwidths):.2f} Mbps\n")
    info(f"📊 : {[f'{bw:.2f}' for bw in host_bandwidths]} Mbps\n")
    
    bw_r0_r1, bw_r0_r2 = calculate_regional_bandwidth(num_subscribers, TOTAL_BITRATE_MBPS)
    users_per_relay = num_subscribers / 2
    # Unicast worst case: every user independently selects the peak Rep (not base+composite).
    worst_case_bw = users_per_relay * TOTAL_BITRATE_MBPS
    info(f"📊 :\n")
    info(f" : {num_subscribers}\n")
    info(f" Relay : {users_per_relay:.0f}\n")
    info(f" Rep/unicast : {worst_case_bw:.2f} Mbps\n")
    info(f" : r0→r1={bw_r0_r1} Mbps, r0→r2={bw_r0_r2} Mbps\n")
    info(f" : {worst_case_bw / bw_r0_r1 * 100:.1f}% (Unicast), Multicast \n")
    
    # command123 A5: reclaim leftover MD2G tree ifaces from a crashed prior cell.
    # Never mn -c; skip if unrelated Mininet is live.
    cell_scoped_pre_start_cleanup(log_path, num_subscribers, TMP_PREFIX)

    def add_link_retry(*args, **kwargs):
        try:
            return net.addLink(*args, **kwargs)
        except Exception as exc:
            msg = str(exc)
            if "File exists" in msg or "RTNETLINK" in msg:
                info(f"⚠️  addLink RTNETLINK ({exc}); cell-scoped reclaim then retry once\n")
                cell_scoped_pre_start_cleanup(log_path, num_subscribers, TMP_PREFIX)
                time.sleep(0.3)
                return net.addLink(*args, **kwargs)
            raise

    # ✅ B1 max_queue_size=1000 QUIC Burst
    # n0 -> r0 ( 1 Gbps)
    add_link_retry(n0, r0, intfName1='n0-eth0', intfName2='r0-eth0', 
                bw=BW_N0_R0, delay='1ms', loss=0, max_queue_size=2000, cls=TCLink)
    # ✅ Mininet 0-1000 Mbps
    bw_r0_r1_limited = min(bw_r0_r1, 1000.0)
    add_link_retry(r0, r1, intfName1='r0-eth1', intfName2='r1-eth0',
                bw=bw_r0_r1_limited, delay='5ms', loss=0, max_queue_size=1000, cls=TCLink)
    # ✅ Mininet 0-1000 Mbps
    bw_r0_r2_limited = min(bw_r0_r2, 1000.0)
    add_link_retry(r0, r2, intfName1='r0-eth2', intfName2='r2-eth0',
                bw=bw_r0_r2_limited, delay='5ms', loss=0, max_queue_size=1000, cls=TCLink)
    
    # ✅ B1 max_queue_size
    # ✅ bw TCLink "rate" is required
    # 1000 Mbps
    add_link_retry(r1, s1, intfName1='r1-eth1', intfName2='s1-eth0', 
                bw=1000, delay='1ms', loss=0, max_queue_size=1000, cls=TCLink)
    # s1 r1 hosts
    for i, host in enumerate(subscribers[:r1_sub_count], 1):
        user_net_type = host_net_types[i-1]
        user_bw = host_bandwidths[i-1]
        net_config = NETWORK_BW_CONFIG.get(user_net_type, NETWORK_BW_CONFIG['wifi'])
        actual_bw = min(user_bw, net_config['bw'])
        # 6.5 Mbps Base2 = 5.4 Mbps + 20%
        # 12-20 Mbps
        if _ton_gen3_stress_cap() is None and not _command137_raw_4g():
            MIN_REQUIRED_BW_BASE = 6.5
            recommended_min = NETWORK_MIN_BW_RECOMMENDED.get(user_net_type, MIN_REQUIRED_BW_BASE)
            MIN_REQUIRED_BW = max(MIN_REQUIRED_BW_BASE, recommended_min)
            if actual_bw < MIN_REQUIRED_BW:
                actual_bw = max(MIN_REQUIRED_BW, net_config['bw'] * 0.2)
                info(f" ⚠️ h{i}: {user_bw:.2f} Mbps {actual_bw:.2f} Mbps : {recommended_min:.1f} Mbps \n")
        actual_bw = _ton_gen3_apply_last_mile(actual_bw, user_net_type)
        # ✅ Mininet 0-1000 Mbps
        actual_bw = min(actual_bw, 1000.0)
        add_link_retry(host, s1, intfName1=f'h{i}-eth0', intfName2=f's1-eth{i}',
                   bw=actual_bw, delay=net_config['delay'], loss=net_config['loss'], max_queue_size=1000, cls=TCLink)
        info(f" ✅ h{i}: {user_net_type}, ={user_bw:.2f} Mbps, ={net_config['bw']:.2f} Mbps, ={actual_bw:.2f} Mbps, ={net_config['delay']}\n")
    
    # ✅ B1 max_queue_size
    # ✅ bw TCLink "rate" is required
    # 1000 Mbps
    add_link_retry(r2, s2, intfName1='r2-eth1', intfName2='s2-eth0', 
                bw=1000, delay='1ms', loss=0, max_queue_size=1000, cls=TCLink)
    # s2 r2 hosts
    for i, host in enumerate(subscribers[r1_sub_count:], r1_sub_count + 1):
        user_net_type = host_net_types[i-1]
        user_bw = host_bandwidths[i-1]
        net_config = NETWORK_BW_CONFIG.get(user_net_type, NETWORK_BW_CONFIG['wifi'])
        actual_bw = min(user_bw, net_config['bw'])
        # 6.5 Mbps Base2 = 5.4 Mbps + 20%
        # 12-20 Mbps
        if _ton_gen3_stress_cap() is None and not _command137_raw_4g():
            MIN_REQUIRED_BW_BASE = 6.5
            recommended_min = NETWORK_MIN_BW_RECOMMENDED.get(user_net_type, MIN_REQUIRED_BW_BASE)
            MIN_REQUIRED_BW = max(MIN_REQUIRED_BW_BASE, recommended_min)
            if actual_bw < MIN_REQUIRED_BW:
                actual_bw = max(MIN_REQUIRED_BW, net_config['bw'] * 0.2)
                info(f" ⚠️ h{i}: {user_bw:.2f} Mbps {actual_bw:.2f} Mbps : {recommended_min:.1f} Mbps \n")
        actual_bw = _ton_gen3_apply_last_mile(actual_bw, user_net_type)
        # ✅ Mininet 0-1000 Mbps
        actual_bw = min(actual_bw, 1000.0)
        add_link_retry(host, s2, intfName1=f'h{i}-eth0', intfName2=f's2-eth{i-r1_sub_count}',
                   bw=actual_bw, delay=net_config['delay'], loss=net_config['loss'], max_queue_size=1000, cls=TCLink)
        info(f" ✅ h{i}: {user_net_type}, ={user_bw:.2f} Mbps, ={net_config['bw']:.2f} Mbps, ={actual_bw:.2f} Mbps, ={net_config['delay']}\n")

    net.start()
    
    # ✅ Switch standalone ping loss
    info("🔧 Switch standalone ping loss ...\n")
    try:
        import subprocess
        # s1 s2 standalone
        for switch_name in ['s1', 's2']:
            try:
                switch = net.get(switch_name)
                subprocess.run(['ovs-vsctl', 'set-controller', switch_name, 'none'], 
                             check=False, capture_output=True, timeout=5)
                subprocess.run(['ovs-vsctl', 'set', 'bridge', switch_name, 'fail-mode=standalone'], 
                             check=False, capture_output=True, timeout=5)
                info(f" ✅ Switch {switch_name} standalone \n")
            except Exception as e:
                info(f" ⚠️ Switch {switch_name} : {e} \n")
        info("✅ Switch \n")
    except Exception as e:
        info(f"⚠️ Switch : {e} \n")
    
    info(" ...\n")
    for host in net.hosts:
        for intf in host.intfList():
            try:
                # ip link set
                host.cmd(f'ip link set {intf.name} up 2>/dev/null || true')
                # ifconfig
                host.cmd(f'ifconfig {intf.name} up 2>/dev/null || true')
                time.sleep(0.1)
                status = host.cmd(f'ip link show {intf.name} 2>/dev/null | grep -q "state UP" && echo "UP" || echo "DOWN"').strip()
                if status != "UP":
                    host.cmd(f'ip link set {intf.name} up 2>/dev/null || true')
                    time.sleep(0.1)
                    status = host.cmd(f'ip link show {intf.name} 2>/dev/null | grep -q "state UP" && echo "UP" || echo "DOWN"').strip()
                    if status != "UP":
                        info(f" ⚠️ {host.name}:{intf.name} \n")
            except Exception as e:
                info(f" ⚠️ {host.name}:{intf.name} : {e}\n")
    
    setup_routing(net, num_subscribers)
    
    info(" MTU...\n")
    target_mtu = 1500
    for host in net.hosts:
        for intf in host.intfList():
            try:
                current_mtu = host.cmd(f"cat /sys/class/net/{intf.name}/mtu 2>/dev/null || echo '1500'").strip()
                try:
                    current_mtu_int = int(current_mtu)
                except:
                    current_mtu_int = 1500
                
                if current_mtu_int < target_mtu:
                    host.cmd(f"ip link set {intf.name} mtu {target_mtu} 2>/dev/null || true")
            except:
                pass
    
    info("✅ MTU \n")
    
    info("Testing Ping (expect 0% loss)...\n")
    # Honor SKIP_PING_ALL and the historical MM26/SIGCOMM aliases.
    # Full pingAll is O(N^2) and hung u60 cells for days (command94).
    _skip_ping = any(
        str(os.environ.get(k) or "0").strip().lower() in ("1", "true", "yes")
        for k in ("SKIP_PING_ALL", "MM26_SKIP_PING_ALL", "SIGCOMM_SKIP_PINGALL")
    )
    if _skip_ping:
        info("⚠️ SKIP_PING_ALL=1 net.pingAll() \n")
    else:
        net.pingAll()
    
    info(" ...\n")
    ping_failed = []
    
    result = n0.cmd("ping -c 1 -W 1 10.0.1.1 >/dev/null 2>&1 && echo 'OK' || echo 'FAIL'").strip()
    if result != "OK":
        ping_failed.append("n0 -> r0")
    
    result = r0.cmd("ping -c 1 -W 1 10.0.2.2 >/dev/null 2>&1 && echo 'OK' || echo 'FAIL'").strip()
    if result != "OK":
        ping_failed.append("r0 -> r1")
    result = r0.cmd("ping -c 1 -W 1 10.0.3.2 >/dev/null 2>&1 && echo 'OK' || echo 'FAIL'").strip()
    if result != "OK":
        ping_failed.append("r0 -> r2")
    
    # hosts ->
    subscribers = [net.get(f'h{i}') for i in range(1, num_subscribers + 1)]
    r1_sub_count = num_subscribers // 2
    for i, host in enumerate(subscribers, 1):
        if i <= r1_sub_count:
            gateway = "10.0.4.1"
        else:
            gateway = "10.0.5.1"
        result = host.cmd(f"ping -c 1 -W 1 {gateway} >/dev/null 2>&1 && echo 'OK' || echo 'FAIL'").strip()
        if result != "OK":
            ping_failed.append(f"h{i} -> {gateway}")
    
    if ping_failed:
        error(f"⚠️ ping : {', '.join(ping_failed)}\n")
        error(" \n")
    else:
        info("✅ \n")

    # --- Relays (Clustering) ---
    info(" Relays (Clustering )...\n")
    
    # ✅ r0: Root Relay --cluster-root
    info(" Root Relay (r0)...\n")
    port_check = r0.cmd("netstat -tuln 2>/dev/null | grep ':4443' || ss -tuln 2>/dev/null | grep ':4443' || echo ' '").strip()
    if "4443" in port_check and " " not in port_check:
        r0.cmd("fuser -k 4443/tcp 2>/dev/null || pkill -f 'moq-relay' 2>/dev/null || true")
        time.sleep(1)
    
    r0.cmd(f"cp {cert} /tmp/{TMP_PREFIX}r0_cert.pem && cp {key} /tmp/{TMP_PREFIX}r0_key.pem")
    r0.cmd(f"cp {auth_key_file} /tmp/{TMP_PREFIX}r0_key.jwk")
    # ✅ auth public = "anon"
    r0_config = generate_relay_config("r0", cert, key, f"/tmp/{TMP_PREFIX}r0_key.jwk")
    r0.cmd(f"cp {r0_config} /tmp/{TMP_PREFIX}r0.toml")
    # ✅ r0.local IP TLS SNI
    # ✅ 3 Relay nice taskset
    # 12Mbps CPU
    r0.cmd(f"RUST_LOG=info {BIN_PATHS['relay']} "
           f"--cluster-node r0.local "
           f"--tls-cert /tmp/{TMP_PREFIX}r0_cert.pem "
           f"--tls-key /tmp/{TMP_PREFIX}r0_key.pem "
           f"/tmp/{TMP_PREFIX}r0.toml "
           f"> /tmp/{TMP_PREFIX}r0.log 2>&1 &")
    time.sleep(3)
    
    def start_cpu_monitor(relay_node, relay_name):
        """ relay CPU """
        # ✅ CURRENT_DIR
        current_dir = os.path.dirname(os.path.abspath(__file__))
        monitor_script = os.path.join(current_dir, "monitor_cpu_stats.py")
        if os.path.exists(monitor_script):
            info(f"🚀 {relay_name} CPU ...\n")
            # ✅ relay_name
            relay_node.cmd(f"{SIGCOMM_PYTHON} -u {monitor_script} {relay_name} > /tmp/{TMP_PREFIX}{relay_name}_cpu_monitor.log 2>&1 &")
            time.sleep(0.5)
            monitor_pid = relay_node.cmd(f"pgrep -f 'monitor_cpu_stats.*{relay_name}' || echo ''").strip()
            if monitor_pid:
                info(f"✅ {relay_name} CPU (PID: {monitor_pid})\n")
                return monitor_pid
            else:
                info(f"⚠️ {relay_name} CPU ID \n")
        else:
            info(f"⚠️ CPU : {monitor_script}\n")
        return None
    
    r0_listening = r0.cmd("netstat -tuln 2>/dev/null | grep ':4443' || ss -tuln 2>/dev/null | grep ':4443' || echo ''").strip()
    if r0_listening:
        info(f"✅ r0 (Root Relay) 4443 \n")
        # ✅ CPU r0 CPU moq-relay-ietf CPU
        # r0 moq-relay-ietf r0 CPU
        start_cpu_monitor(r0, "r0")
    else:
        error("❌ r0 4443 \n")
        r0_log = r0.cmd(f"tail -20 /tmp/{TMP_PREFIX}r0.log 2>&1")
        error(f"{r0_log}\n")
    
    # ✅ r1: Leaf Relay --cluster-root=r0.local --cluster-node=r1.local
    info(" Leaf Relay (r1)...\n")
    port_check = r1.cmd("netstat -tuln 2>/dev/null | grep ':4443' || ss -tuln 2>/dev/null | grep ':4443' || echo ' '").strip()
    if "4443" in port_check and " " not in port_check:
        r1.cmd("fuser -k 4443/tcp 2>/dev/null || pkill -f 'moq-relay' 2>/dev/null || true")
        time.sleep(1)
    
    r1.cmd(f"cp {cert} /tmp/{TMP_PREFIX}r1_cert.pem && cp {key} /tmp/{TMP_PREFIX}r1_key.pem")
    r1.cmd(f"cp {auth_key_file} /tmp/{TMP_PREFIX}r1_key.jwk")
    r1.cmd(f"cp {cluster_token_file} /tmp/{TMP_PREFIX}r1_cluster.jwt")
    # ✅ auth public = "anon"
    r1_config = generate_relay_config("r1", cert, key, f"/tmp/{TMP_PREFIX}r1_key.jwk")
    r1.cmd(f"cp {r1_config} /tmp/{TMP_PREFIX}r1.toml")
    # ✅ cluster token root
    # r0.local TLS SNI
    # ⚠️ moq-relay https:// hostname:port https://
    cluster_root_url = "r0.local:4443"
    # ✅ nice taskset
    # ✅ RUST_LOG=debug
    # ✅ 3 Relay nice taskset
    r1.cmd(f"RUST_LOG=info {BIN_PATHS['relay']} "
           f"--cluster-node r1.local "
           f"--cluster-root {cluster_root_url} "
           f"--cluster-token /tmp/{TMP_PREFIX}r1_cluster.jwt "
           f"--tls-cert /tmp/{TMP_PREFIX}r1_cert.pem "
           f"--tls-key /tmp/{TMP_PREFIX}r1_key.pem "
           f"--tls-disable-verify "
           f"/tmp/{TMP_PREFIX}r1.toml "
           f"> /tmp/{TMP_PREFIX}r1.log 2>&1 &")
    time.sleep(3)
    
    r1_listening = r1.cmd("netstat -tuln 2>/dev/null | grep ':4443' || ss -tuln 2>/dev/null | grep ':4443' || echo ''").strip()
    if r1_listening:
        info(f"✅ r1 (Leaf Relay) 4443 \n")
    else:
        error("❌ r1 4443 \n")
        r1_log = r1.cmd(f"tail -20 /tmp/{TMP_PREFIX}r1.log 2>&1")
        error(f"{r1_log}\n")
    
    # ✅ r2: Leaf Relay --cluster-root=r0.local --cluster-node=r2.local
    info(" Leaf Relay (r2)...\n")
    port_check = r2.cmd("netstat -tuln 2>/dev/null | grep ':4443' || ss -tuln 2>/dev/null | grep ':4443' || echo ' '").strip()
    if "4443" in port_check and " " not in port_check:
        r2.cmd("fuser -k 4443/tcp 2>/dev/null || pkill -f 'moq-relay' 2>/dev/null || true")
        time.sleep(1)
    
    r2.cmd(f"cp {cert} /tmp/{TMP_PREFIX}r2_cert.pem && cp {key} /tmp/{TMP_PREFIX}r2_key.pem")
    r2.cmd(f"cp {auth_key_file} /tmp/{TMP_PREFIX}r2_key.jwk")
    r2.cmd(f"cp {cluster_token_file} /tmp/{TMP_PREFIX}r2_cluster.jwt")
    # ✅ auth public = "anon"
    r2_config = generate_relay_config("r2", cert, key, f"/tmp/{TMP_PREFIX}r2_key.jwk")
    r2.cmd(f"cp {r2_config} /tmp/{TMP_PREFIX}r2.toml")
    # ✅ cluster token root
    # r0.local TLS SNI
    # ⚠️ moq-relay https:// hostname:port https://
    cluster_root_url = "r0.local:4443"
    # ✅ nice taskset
    # ✅ RUST_LOG=debug
    # ✅ 3 Relay nice taskset
    r2.cmd(f"RUST_LOG=info {BIN_PATHS['relay']} "
           f"--cluster-node r2.local "
           f"--cluster-root {cluster_root_url} "
           f"--cluster-token /tmp/{TMP_PREFIX}r2_cluster.jwt "
           f"--tls-cert /tmp/{TMP_PREFIX}r2_cert.pem "
           f"--tls-key /tmp/{TMP_PREFIX}r2_key.pem "
           f"--tls-disable-verify "
           f"/tmp/{TMP_PREFIX}r2.toml "
           f"> /tmp/{TMP_PREFIX}r2.log 2>&1 &")
    time.sleep(3)
    
    r2_listening = r2.cmd("netstat -tuln 2>/dev/null | grep ':4443' || ss -tuln 2>/dev/null | grep ':4443' || echo ''").strip()
    if r2_listening:
        info(f"✅ r2 (Leaf Relay) 4443 \n")
    else:
        error("❌ r2 4443 \n")
        r2_log = r2.cmd(f"tail -20 /tmp/{TMP_PREFIX}r2.log 2>&1")
        error(f"{r2_log}\n")
    
    # clustering
    info(" Clustering ...\n")
    time.sleep(5)
    
    # command122 Level-3: bounded last-mile probe sink on access gateways.
    # Independent of H1/H2; never used as a configured-bandwidth oracle.
    if os.environ.get("TON_C122_HEADROOM_PROBE", "1").strip().lower() not in ("0", "false", "no"):
        _c122_sink = (
            "str(artifact_root())"
            "/Sigcomm26/Paper6_ToN/scripts/command122_headroom_probe_sink.py"
        )
        r1.cmd(
            f"python3 {_c122_sink} --bind 10.0.4.1 --port 18080 "
            f"> /tmp/{TMP_PREFIX}c122_probe_r1.log 2>&1 &"
        )
        r2.cmd(
            f"python3 {_c122_sink} --bind 10.0.5.1 --port 18080 "
            f"> /tmp/{TMP_PREFIX}c122_probe_r2.log 2>&1 &"
        )
        info("command122 headroom probe sink started on r1:18080 and r2:18080\n")

    # clustering
    r0_log = r0.cmd(f"tail -50 /tmp/{TMP_PREFIX}r0.log 2>&1")
    r1_log = r1.cmd(f"tail -50 /tmp/{TMP_PREFIX}r1.log 2>&1")
    r2_log = r2.cmd(f"tail -50 /tmp/{TMP_PREFIX}r2.log 2>&1")
    
    if "cluster" in r0_log.lower() or "connect" in r0_log.lower():
        info("✅ r0 clustering \n")
    if "cluster" in r1_log.lower() or "root" in r1_log.lower():
        info("✅ r1 root\n")
    if "cluster" in r2_log.lower() or "root" in r2_log.lower():
        info("✅ r2 root\n")

    # ✅ Publisher Publisher
    info(f"📊 Publisher ...\n")
    initial_traffic = {}
    
    try:
        r0_eth1_tx_initial = int(r0.cmd(f'cat /sys/class/net/r0-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r0_eth1_tx'] = r0_eth1_tx_initial
        
        r0_eth2_tx_initial = int(r0.cmd(f'cat /sys/class/net/r0-eth2/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r0_eth2_tx'] = r0_eth2_tx_initial
        
        # ✅ Rolling r0 n0 r0 fan-out
        r0_eth0_rx_initial = int(r0.cmd(f'cat /sys/class/net/r0-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r0_eth0_rx'] = r0_eth0_rx_initial
        
        r1_eth0_rx_initial = int(r1.cmd(f'cat /sys/class/net/r1-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r1_eth0_rx'] = r1_eth0_rx_initial
        
        r1_eth1_tx_initial = int(r1.cmd(f'cat /sys/class/net/r1-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r1_eth1_tx'] = r1_eth1_tx_initial
        
        r2_eth0_rx_initial = int(r2.cmd(f'cat /sys/class/net/r2-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r2_eth0_rx'] = r2_eth0_rx_initial
        
        r2_eth1_tx_initial = int(r2.cmd(f'cat /sys/class/net/r2-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r2_eth1_tx'] = r2_eth1_tx_initial
        
        info(f" ✅ Publisher :\n")
        info(f"      r0→r1 (r0-eth1 TX): {r0_eth1_tx_initial:,} bytes\n")
        info(f"      r0→r2 (r0-eth2 TX): {r0_eth2_tx_initial:,} bytes\n")
        info(f" r1 r0 (r1-eth0 RX): {r1_eth0_rx_initial:,} bytes\n")
        info(f" r1 (r1-eth1 TX): {r1_eth1_tx_initial:,} bytes\n")
        info(f" r2 r0 (r2-eth0 RX): {r2_eth0_rx_initial:,} bytes\n")
        info(f" r2 (r2-eth1 TX): {r2_eth1_tx_initial:,} bytes\n")
    except Exception as e:
        error(f" ⚠️ : {e} 0 \n")
        initial_traffic = {
            'r0_eth1_tx': 0, 'r0_eth2_tx': 0, 'r0_eth0_rx': 0,
            'r1_eth0_rx': 0, 'r1_eth1_tx': 0,
            'r2_eth0_rx': 0, 'r2_eth1_tx': 0
        }

    # --- Publisher 9 3 base + 6 ---
    info(" Publishers (fMP4 Video Files - )...\n")
    
    # ✅ base base1-3 base+enhanced
    video_files = {}
    if _NESTED_COMPONENTS:
        for key in ("b0", "db1", "db2", "e1", "e2"):
            video_path = VIDEO_PATHS[key]
            if os.path.exists(video_path):
                video_files[key] = video_path
                info(f"✅ nested component {key}: {video_path}\n")
            else:
                error(f"❌ {key} : {video_path}\n")
                raise SystemExit(2)
    else:
        # Base base
        for i in [1, 2, 3]:
            key = f"base{i}"
            if key in VIDEO_PATHS:
                video_path = VIDEO_PATHS[key]
                if os.path.exists(video_path):
                    video_files[key] = video_path
                    info(f"✅ Base {key}: {video_path}\n")
                else:
                    error(f"❌ {key} : {video_path}\n")
                    raise SystemExit(2)
    
    # base+enhanced full-rep archive) OR enhancement-only tracks (COMMAND135)
    if _NESTED_COMPONENTS:
        pass
    elif _TRUE_CONTENT_LAYERING:
        for base_idx in [1, 2, 3]:
            for enh_idx in [1, 2]:
                key = f"base{base_idx}_enh{enh_idx}_only"
                if key in VIDEO_PATHS:
                    video_path = VIDEO_PATHS[key]
                    if os.path.exists(video_path):
                        video_files[key] = video_path
                        info(f"✅ enh-only {key}: {video_path}\n")
                    else:
                        error(f"❌ {key} : {video_path}\n")
                        raise SystemExit(2)
    else:
        for base_idx in [1, 2, 3]:
            for enh_idx in [1, 2]:
                key = f"base{base_idx}_enhanced{enh_idx}"
                if key in VIDEO_PATHS:
                    video_path = VIDEO_PATHS[key]
                    if os.path.exists(video_path):
                        video_files[key] = video_path
                        info(f"✅ {key}: {video_path}\n")
                    else:
                        error(f"❌ {key} : {video_path}\n")
                        raise SystemExit(2)

    expected_publishers = set(video_files.keys())
    
    # ✅ cell TMP_PREFIX publisher cell PID
    info("🔍 Publisher cell-scoped ...\n")
    pub_log_dir = os.path.join(log_path, "publisher_logs")
    os.makedirs(pub_log_dir, exist_ok=True)
    
    time.sleep(0.5)
    
    # ✅ Publishers 3 base 6
    info("🚀 Publishers 3 base 6 ...\n")
    pub_pids = {}
    publisher_contracts = {}

    def _launch_one_publisher(key, video_path, broadcast_name):
        """Launch ffmpeg|hang with -map 0:v:0, capture PID via echo $!, log under log_path."""
        hang_log = os.path.join(pub_log_dir, f"pub_{key}.log")
        tmp_log = f"/tmp/{TMP_PREFIX}pub_{key}.log"
        pid_file = f"/tmp/{TMP_PREFIX}pub_{key}.pid"
        inner = (
            # announce is emitted at DEBUG by moq_lite::lite::publisher must enable it
            f"export QUIC_MTU=1200 QUIC_MAX_UDP_PAYLOAD_SIZE=1200 "
            f"RUST_LOG=info,moq_lite=debug,hang=info; "
            f"( ffmpeg -re -stream_loop -1 -i {shlex.quote(video_path)} "
            f"-hide_banner -loglevel error "
            f"-map 0:v:0 -c copy -an -f mp4 "
            f"-bitexact -map_metadata -1 "
            f"-movflags cmaf+separate_moof+delay_moov+skip_trailer+frag_every_frame "
            f"- 2>>{shlex.quote(hang_log)} | "
            f"{shlex.quote(BIN_PATHS['pub'])} publish --url https://r0.local:4443/anon/ "
            f"--name {broadcast_name} --tls-disable-verify fmp4 "
            f">>{shlex.quote(hang_log)} 2>&1 ) & "
            f"echo $! > {shlex.quote(pid_file)}; "
            f"cp -f {shlex.quote(hang_log)} {shlex.quote(tmp_log)} 2>/dev/null || true"
        )
        cmd_pub = f"bash -c {shlex.quote(inner)}"
        n0.cmd(cmd_pub)
        time.sleep(0.4)
        pid = n0.cmd(f"cat {shlex.quote(pid_file)} 2>/dev/null || echo ''").strip().split("\n")[0].strip()
        if not subscriber_pid_ok(pid):
            pid = n0.cmd(
                f"pgrep -f 'hang.*publish.*--name {broadcast_name}' || echo ''"
            ).strip().split("\n")[0].strip()
        alive = False
        cmdline = ""
        if subscriber_pid_ok(pid):
            CELL_RECORDED_PIDS.add(pid.split()[0])
            cmdline = n0.cmd(
                f"tr '\\0' ' ' < /proc/{pid.split()[0]}/cmdline 2>/dev/null || echo ''"
            ).strip()
            alive = bool(cmdline)
        contract = {
            "broadcast_name": broadcast_name,
            "video_path": video_path,
            "pub_binary": BIN_PATHS["pub"],
            "hang_log": hang_log,
            "tmp_log": tmp_log,
            "pid": pid if subscriber_pid_ok(pid) else None,
            "alive": alive,
            "cmdline": cmdline,
            "cmd": cmd_pub,
            "rust_log": "info",
            "map": "0:v:0",
        }
        publisher_contracts[key] = contract
        pub_pids[key] = pid if subscriber_pid_ok(pid) else None
        if subscriber_pid_ok(pid) and alive:
            info(f"✅ {key} Publisher (PID: {pid})\n")
        else:
            error(f"❌ {key} Publisher (PID={pid!r})\n")
        return contract

    nested_live = set()
    nested_plan_current = os.path.join(log_path, "COMPONENT_ACTUATION_PLAN_CURRENT.json")
    nested_plan_jsonl = os.path.join(log_path, "COMPONENT_ACTUATION_PLAN.jsonl")
    os.environ["COMMAND147_PLAN_FILE"] = nested_plan_current

    def _kill_one_publisher(key):
        pid_file = f"/tmp/{TMP_PREFIX}pub_{key}.pid"
        pid = n0.cmd(f"cat {shlex.quote(pid_file)} 2>/dev/null || echo ''").strip().split("\n")[0].strip()
        if subscriber_pid_ok(pid):
            n0.cmd(f"kill {pid} 2>/dev/null || true")
        n0.cmd(f"pkill -f 'hang.*publish.*--name {key}' 2>/dev/null || true")
        nested_live.discard(key)
        pub_pids[key] = None

    if _NESTED_COMPONENTS:
        _ton_lib = str(Path(__file__).resolve().parent / "Sigcomm26" / "Paper6_ToN" / "lib")
        if _ton_lib not in sys.path:
            sys.path.insert(0, _ton_lib)
        from command147_nested_runtime import schedule_targets  # noqa: E402
        from component_actuation_plan import build_plan  # noqa: E402

        pattern = os.environ.get("COMMAND147_SMOKE_PATTERN") or "S0_B1_only"
        n_users = int(num_subscribers)
        _init_strat = (os.environ.get("COMMAND148_STRATEGY") or "").strip()
        if _init_strat:
            from command148_component_policy import schedule_strategy_targets as _st0  # noqa: E402
            t0_targets = _st0(
                _init_strat,
                0.0,
                n_users,
                float(duration),
                log_path=log_path,
                content=os.environ.get("TON_CONTENT_ID") or "redandblack",
            )
        else:
            t0_targets = schedule_targets(pattern, 0.0, duration=float(duration), n_users=n_users)
        plan0 = build_plan(
            decision_seq=0,
            group="g0",
            user_target_states=t0_targets,
            currently_active=[],
            reason=f"nested_init:{pattern}",
        )
        _uni = str(os.environ.get("COMMAND148_UNICAST") or "").strip().lower() in (
            "1", "true", "yes",
        ) or (_init_strat == "MOQ_UNICAST_COMPONENT")
        if _init_strat:
            from command148_component_policy import physical_publisher_keys as _phys0  # noqa: E402
            init_pairs = _phys0(t0_targets, _uni)
        else:
            init_pairs = [(c, c) for c in plan0.open_components]
        info(f"🚀 nested ComponentActuationPlan init {pattern} open={[k for k,_ in init_pairs]} unicast={_uni}\n")
        for key, comp in init_pairs:
            _launch_one_publisher(key, video_files[comp], key)
            nested_live.add(key)
        Path(nested_plan_current).write_text(
            json.dumps(
                {
                    **{k: getattr(plan0, k) for k in plan0.__dataclass_fields__},
                    "writer": "ComponentActuationPlan.apply",
                },
                default=str,
            )
            + "\n"
        )
        with open(nested_plan_jsonl, "a") as jf:
            jf.write(Path(nested_plan_current).read_text())
        expected_publishers = set(k for k,_c in init_pairs)
    else:
        for i in [1, 2, 3]:
            key = f"base{i}"
            _launch_one_publisher(key, video_files[key], key)

        for base_idx in [1, 2, 3]:
            for enh_idx in [1, 2]:
                if _TRUE_CONTENT_LAYERING:
                    key = f"base{base_idx}_enh{enh_idx}_only"
                else:
                    key = f"base{base_idx}_enhanced{enh_idx}"
                _launch_one_publisher(key, video_files[key], key)
        expected_publishers = set(video_files.keys())

    write_publisher_launch_contract(log_path, {
        "tmp_prefix": TMP_PREFIX,
        "publishers": publisher_contracts,
        "gate": "hang_log_announce_broadcast=<name> (no anon/ prefix)",
    })
    
    info("")
    time.sleep(3)
    
    # PUBLISHER_REGISTRATION_GATE: hang logs announce broadcast=<name> (NOT r0 anon/)
    info("PUBLISHER_REGISTRATION_GATE: hang announce broadcast=<name>...\n")
    registered_publishers = set()
    max_wait = 45

    _gate_keys = set(expected_publishers) if expected_publishers else set(video_files.keys())
    for wait_count in range(max_wait):
        for key in list(_gate_keys):
            if key in registered_publishers:
                continue
            hang_log = os.path.join(pub_log_dir, f"pub_{key}.log")
            log_text = ""
            try:
                if os.path.isfile(hang_log):
                    with open(hang_log, "r", encoding="utf-8", errors="ignore") as hf:
                        log_text = hf.read()
            except Exception:
                log_text = ""
            # also refresh from n0 filesystem view
            if not log_text:
                log_text = n0.cmd(f"cat {shlex.quote(hang_log)} 2>/dev/null || true")
            pid = pub_pids.get(key)
            alive = False
            if subscriber_pid_ok(pid):
                alive = os.path.exists(f"/proc/{str(pid).split()[0]}")
            if publisher_registered_in_hang_log(log_text, key, alive=alive):
                registered_publishers.add(key)
                info(f"✅ {key} registered via hang log (t={wait_count}s)\n")
        if _gate_keys and set(_gate_keys) <= registered_publishers:
            break
        if wait_count % 5 == 0 and wait_count > 0:
            missing = [k for k in _gate_keys if k not in registered_publishers]
            info(f"   … waiting publishers: missing={missing}\n")
        time.sleep(1)

    # Refresh contract with gate result
    write_publisher_launch_contract(log_path, {
        "tmp_prefix": TMP_PREFIX,
        "publishers": publisher_contracts,
        "registered": sorted(registered_publishers),
        "expected": sorted(expected_publishers),
        "gate_pass": len(registered_publishers) == len(expected_publishers),
    })

    if len(registered_publishers) != len(expected_publishers):
        unregistered = [k for k in expected_publishers if k not in registered_publishers]
        error(f"❌ PUBLISHER_REGISTRATION_GATE FAILED: missing {unregistered}\n")
        copy_cell_tmp_logs(log_path, TMP_PREFIX)
        compute_and_write_cell_validity(
            log_path,
            strategy=strategy,
            num_subscribers=num_subscribers,
            registered_publishers=registered_publishers,
            expected_publishers=expected_publishers,
            subscriber_pids=[],
            leaf_egress_bytes=0,
        )
        cleanup_all_processes(tmp_prefix=TMP_PREFIX, recorded_pids=CELL_RECORDED_PIDS, log_path=log_path)
        cell_scoped_exit_cleanup(log_path, num_subscribers, TMP_PREFIX, net=net)
        raise SystemExit(2)

    info(f"✅ PUBLISHER_REGISTRATION_GATE PASS ({len(registered_publishers)}/{len(expected_publishers)})\n")

    # command40 canary 1: publishers-only probe with moq-sub (eth rx alone is
    # control-plane sized until a subscriber pulls media).
    if os.environ.get("SIGCOMM_PUBLISHERS_ONLY", "").strip() in ("1", "true", "TRUE"):
        info("SIGCOMM_PUBLISHERS_ONLY: skipping subscribers; probing broadcasts via moq-sub...\n")
        time.sleep(max(3, int(os.environ.get("SIGCOMM_PUBLISHERS_ONLY_WAIT", "8"))))
        try:
            r0_rx = int(r0.cmd('cat /sys/class/net/r0-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        except Exception:
            r0_rx = 0
        probe_ok = []
        probe_fail = []
        moq_sub = BIN_PATHS.get("sub") or os.path.join(os.path.dirname(BIN_PATHS["pub"]), "moq-sub")
        for key in sorted(expected_publishers):
            dump_sz = 0
            online = False
            log_txt = ""
            for track in ("video0", "video"):
                dump = f"/tmp/{TMP_PREFIX}probe_{key}_{track}.bin"
                probe_cmd = (
                    f"timeout 6 env RUST_LOG=info {shlex.quote(moq_sub)} "
                    f"--url https://r0.local:4443/anon/ --broadcast {shlex.quote(key)} "
                    f"--track {track} --tls-disable-verify "
                    f"--dump {shlex.quote(dump)} > /tmp/{TMP_PREFIX}probe_{key}.log 2>&1 || true"
                )
                n0.cmd(probe_cmd)
                log_txt = n0.cmd(f"cat /tmp/{TMP_PREFIX}probe_{key}.log 2>/dev/null || true")
                try:
                    dump_sz = int(n0.cmd(f"wc -c < {shlex.quote(dump)} 2>/dev/null || echo 0").strip() or "0")
                except Exception:
                    dump_sz = 0
                online = ("broadcast " in log_txt) or ("subscribe started" in log_txt.lower())
                if online or dump_sz > 0:
                    break
            if not online and "unrecognized" in log_txt.lower():
                hang_log = os.path.join(pub_log_dir, f"pub_{key}.log")
                try:
                    with open(hang_log, "r", encoding="utf-8", errors="ignore") as hf:
                        online = "announce broadcast=" in hf.read()
                except Exception:
                    online = key in registered_publishers
            if online or dump_sz > 0:
                probe_ok.append({"name": key, "dump_bytes": dump_sz, "online": online or dump_sz > 0})
            else:
                probe_fail.append({"name": key, "log_tail": log_txt[-400:], "dump_bytes": dump_sz})
        bytes_ok = sum(p["dump_bytes"] for p in probe_ok) >= 5_000
        all_online = len(probe_ok) == len(expected_publishers)
        eth_delta = r0_rx - int(initial_traffic.get("r0_eth0_rx", 0))
        # Require real dump bytes OR (all online AND eth growth past handshake floor)
        payload_ok = all_online and (bytes_ok or eth_delta >= 200_000)
        write_publisher_launch_contract(log_path, {
            "tmp_prefix": TMP_PREFIX,
            "registered": sorted(registered_publishers),
            "expected": sorted(expected_publishers),
            "gate_pass": True,
            "publishers_only": True,
            "r0_eth0_rx": r0_rx,
            "r0_eth0_rx_initial": initial_traffic.get("r0_eth0_rx", 0),
            "eth_delta": eth_delta,
            "probe_ok": probe_ok,
            "probe_fail": probe_fail,
            "payload_ok": payload_ok,
            "moq_sub": moq_sub,
        })
        copy_cell_tmp_logs(log_path, TMP_PREFIX)
        if not payload_ok:
            error(f"❌ PUBLISHERS_ONLY probe gate failed online={len(probe_ok)}/{len(expected_publishers)}\n")
            cleanup_all_processes(tmp_prefix=TMP_PREFIX, recorded_pids=CELL_RECORDED_PIDS, log_path=log_path)
            try:
                net.stop()
            except Exception:
                pass
            os._exit(2)
        info(f"✅ PUBLISHERS_ONLY PASS online={len(probe_ok)} eth_delta={eth_delta}\n")
        cleanup_all_processes(tmp_prefix=TMP_PREFIX, recorded_pids=CELL_RECORDED_PIDS, log_path=log_path)
        cell_scoped_exit_cleanup(log_path, num_subscribers, TMP_PREFIX, net=net)
        os._exit(0)

    # --- Subscriber dispatch_strategy_enhanced_unified_Sigcomm.py ---
    info(f" {num_subscribers} Subscriber dispatch_strategy ={strategy} ...\n")
    info("⚠️ Subscriber Relay (r1/r2) Relay \n")
    info(f" 📊 : {strategy}, : {network_type}, : {log_path}\n")
    
    # ✅ dispatch_strategy
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    dispatch_script = os.path.join(CURRENT_DIR, "dispatch_strategy_enhanced_unified_Sigcomm.py")
    
    if not os.path.exists(dispatch_script):
        error(f"❌ dispatch_strategy : {dispatch_script}\n")
        raise SystemExit(2)
    
    # ✅ Per-cell decision files (never share /tmp/r1_decisions.json across cells)
    # Cross-cell reuse caused orphan controllers to corrupt the next trial.
    r1_decisions_file = f"/tmp/{TMP_PREFIX}r1_decisions.json"
    r2_decisions_file = f"/tmp/{TMP_PREFIX}r2_decisions.json"
    r0_decisions_file = f"/tmp/{TMP_PREFIX}r0_decisions.json"
    _campaign_env = sigcomm_campaign_env_prefix()
    _campaign_env_dict = sigcomm_campaign_env_dict()
    # command113 fidelity: refresh hydrate file so controllers see TON_* / current MM26_*.
    try:
        _env_file = write_sigcomm_controller_env_file()
        _campaign_env = (
            f"MM26_CONTROLLER_ENV_FILE={shlex.quote(_env_file)} " + _campaign_env
        )
        _campaign_env_dict["MM26_CONTROLLER_ENV_FILE"] = _env_file
    except Exception as _env_exc:
        error(f"⚠️ controller env file write failed: {_env_exc}\n")

    # Cell-scoped user↔relay mapping (prevents stale N=100 mapping from polluting N=10).
    try:
        from user_relay_mapping import assign_users_to_relays, save_mapping_to_file

        _map = assign_users_to_relays(int(num_subscribers), relay_list=["r1", "r2"])
        _map_path = f"/tmp/{TMP_PREFIX}user_relay_mapping.json"
        save_mapping_to_file(_map, _map_path)
        # Also refresh the legacy path controllers still read by default.
        save_mapping_to_file(_map, "/tmp/user_relay_mapping.json")
        os.environ["SIGCOMM_USER_RELAY_MAPPING"] = _map_path
        _campaign_env += f"SIGCOMM_USER_RELAY_MAPPING={shlex.quote(_map_path)} "
        info(
            f"✅ wrote user_relay_mapping N={num_subscribers} "
            f"r1={len(_map.get('r1', []))} r2={len(_map.get('r2', []))} → {_map_path}\n"
        )
    except Exception as _map_exc:
        error(f"⚠️ user_relay_mapping write failed: {_map_exc}\n")
    
    # ✅ Relay (r1/r2) Controller
    # MD2G Rolling Relay
    # ✅ Rolling/PCC-DASH DASH/MoQ
    # Rolling PCC-DASH r1/r2 controller DASH
    # MD2G, Rolling, Heuristic, Clustering, PCC-DASH r1/r2 controller
    controller_processes = []
    
    # ✅ start_cpu_monitor 1682
    
    # ✅ Rolling/PCC-DASH r1/r2 controller DASH
    if strategy.lower() in ["rolling", "groot"]:
        # r1 Controller r1_sub_count
        if r1_sub_count > 0:
            controller_script = os.path.join(CURRENT_DIR, "regional_relay_controller.py")
            if os.path.exists(controller_script):
                info(f"🚀 r1 {strategy} Controller ( {r1_sub_count} )...\n")
                
                # Rolling: trained_models/sc_ddqn_rolling.pth
                if model_path is None:
                    model_path = os.path.join(CURRENT_DIR, "trained_models")
                
                # ✅ Mininet
                model_path = os.path.abspath(model_path)
                
                trace_csv_path = None
                trace_csv_candidates = [
                    os.path.join(CURRENT_DIR, "datasets", "processed", "train_tiles.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "processed", "test_tiles.csv"),
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "5g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "wifi_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "4g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "fiber_optic_final_trace.csv"),
                ]
                for candidate in trace_csv_candidates:
                    if os.path.exists(candidate):
                        trace_csv_path = candidate
                        info(f"✅ trace CSV : {trace_csv_path}\n")
                        break
                
                controller_cmd = (
                    f'{_campaign_env}{SIGCOMM_PYTHON} -u {controller_script} '
                    f'--relay_ip 10.0.2.2 '
                    f'--relay_name r1 '
                    f'--decision_file {r1_decisions_file} '
                    f'--max_users {r1_sub_count} '
                    f'--user_offset 1 '
                    f'--network_type {network_type} '
                    f'--strategy {strategy} '
                    f'--model_path {model_path} '
                    f'--interval {interval} '
                    f'--federation off'
                )
                relay_features_csv = os.path.join(log_path, "md2g_decision_features_r1.csv")
                controller_cmd += f' --md2g_features_csv {shlex.quote(relay_features_csv)}'
                # relay relay
                relay_features_csv = os.path.join(log_path, "md2g_decision_features_r1.csv")
                controller_cmd += f' --md2g_features_csv {shlex.quote(relay_features_csv)}'
                # ✅ trace CSV FOV
                if trace_csv_path:
                    controller_cmd += (
                        f' --use_fov_grouping '
                        f'--trace_csv {trace_csv_path} '
                        f'--fov_overlap_threshold 0.5'
                    )
                    info(f"✅ FOV trace_csv={trace_csv_path} \n")
                else:
                    info(f"⚠️ trace CSV \n")
                if strategy.lower() == "md2g":
                    md2g_steps = max(2, int(duration / max(interval, 0.1)) + 1)
                    loop_cmd = (
                        f"/bin/bash -lc \"for ((step=0; step<{md2g_steps}; step++)); do "
                        f"MD2G_DECISION_STEP=\\$step {controller_cmd} --decision_step \\$step --frame_id \\$((step*30)); "
                        f"sleep {interval}; done\""
                    )
                    r1.cmd(f"{loop_cmd} > /tmp/{TMP_PREFIX}r1_controller.log 2>&1 &")
                else:
                    r1.cmd(f"{controller_cmd} > /tmp/{TMP_PREFIX}r1_controller.log 2>&1 &")
                time.sleep(2)
                controller_pid = r1.cmd(f"pgrep -f 'regional_relay_controller.*r1' || echo ''").strip()
                if controller_pid:
                    info(f"✅ r1 Controller (PID: {controller_pid})\n")
                    controller_processes.append(("r1", controller_pid))
                    # ✅ CPU r1 CPU Rolling/PCC-DASH
                    start_cpu_monitor(r1, "r1")
                else:
                    info(f"⚠️ r1 Controller ID \n")
            else:
                info(f"⚠️ Controller : {controller_script} \n")
        
        # r2 Controller r2_sub_count
        if r2_sub_count > 0:
            controller_script = os.path.join(CURRENT_DIR, "regional_relay_controller.py")
            if os.path.exists(controller_script):
                info(f"🚀 r2 {strategy} Controller ( {r2_sub_count} )...\n")
                
                if model_path is None:
                    model_path = os.path.join(CURRENT_DIR, "trained_models")
                
                # ✅ Mininet
                model_path = os.path.abspath(model_path)
                
                # ✅ FOV r1 trace CSV
                trace_csv_path = None
                trace_csv_candidates = [
                    os.path.join(CURRENT_DIR, "datasets", "processed", "train_tiles.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "processed", "test_tiles.csv"),
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "5g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "wifi_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "4g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "fiber_optic_final_trace.csv"),
                ]
                for candidate in trace_csv_candidates:
                    if os.path.exists(candidate):
                        trace_csv_path = candidate
                        break
                
                controller_cmd = (
                    f'{_campaign_env}{SIGCOMM_PYTHON} -u {controller_script} '
                    f'--relay_ip 10.0.3.2 '
                    f'--relay_name r2 '
                    f'--decision_file {r2_decisions_file} '
                    f'--max_users {r2_sub_count} '
                    f'--user_offset {r1_sub_count + 1} '
                    f'--network_type {network_type} '
                    f'--strategy {strategy} '
                    f'--model_path {model_path} '
                    f'--interval {interval} '
                    f'--federation off'
                )
                relay_features_csv = os.path.join(log_path, "md2g_decision_features_r2.csv")
                controller_cmd += f' --md2g_features_csv {shlex.quote(relay_features_csv)}'
                # ✅ trace CSV FOV
                if trace_csv_path:
                    controller_cmd += (
                        f' --use_fov_grouping '
                        f'--trace_csv {trace_csv_path} '
                        f'--fov_overlap_threshold 0.5'
                    )
                if strategy.lower() == "md2g":
                    md2g_steps = max(2, int(duration / max(interval, 0.1)) + 1)
                    loop_cmd = (
                        f"/bin/bash -lc \"for ((step=0; step<{md2g_steps}; step++)); do "
                        f"MD2G_DECISION_STEP=\\$step {controller_cmd} --decision_step \\$step --frame_id \\$((step*30)); "
                        f"sleep {interval}; done\""
                    )
                    r2.cmd(f"{loop_cmd} > /tmp/{TMP_PREFIX}r2_controller.log 2>&1 &")
                else:
                    r2.cmd(f"{controller_cmd} > /tmp/{TMP_PREFIX}r2_controller.log 2>&1 &")
                time.sleep(2)
                controller_pid = r2.cmd(f"pgrep -f 'regional_relay_controller.*r2' || echo ''").strip()
                if controller_pid:
                    info(f"✅ r2 Controller (PID: {controller_pid})\n")
                    controller_processes.append(("r2", controller_pid))
                    # ✅ CPU r2 CPU Rolling/PCC-DASH
                    start_cpu_monitor(r2, "r2")
                else:
                    info(f"⚠️ r2 Controller ID \n")
            else:
                info(f"⚠️ Controller : {controller_script} \n")
    # ✅ Rolling/PCC-DASH r0 r1/r2
    # if strategy.lower() in ["rolling", "groot"]:
        controller_script = os.path.join(CURRENT_DIR, "regional_relay_controller.py")
        if os.path.exists(controller_script):
            info(f"🚀 r0 {strategy} Controller ( {num_subscribers} )...\n")
            
            if model_path is None:
                model_path = os.path.join(CURRENT_DIR, "trained_models")
            
            # ✅ Mininet
            model_path = os.path.abspath(model_path)
            
            trace_csv_path = None
            trace_csv_candidates = [
                os.path.join(CURRENT_DIR, "datasets", "processed", "train_tiles.csv"),
                os.path.join(CURRENT_DIR, "datasets", "processed", "test_tiles.csv"),
                os.path.join(CURRENT_DIR, "datasets", f"{network_type}_final_trace.csv"),
                os.path.join(CURRENT_DIR, "datasets", f"{network_type}_trace.csv"),
                os.path.join(CURRENT_DIR, "datasets", "5g_final_trace.csv"),
                os.path.join(CURRENT_DIR, "datasets", "wifi_final_trace.csv"),
                os.path.join(CURRENT_DIR, "datasets", "4g_final_trace.csv"),
                os.path.join(CURRENT_DIR, "datasets", "fiber_optic_final_trace.csv"),
            ]
            for candidate in trace_csv_candidates:
                if os.path.exists(candidate):
                    trace_csv_path = candidate
                    info(f"✅ trace CSV : {trace_csv_path}\n")
                    break
            
            controller_cmd = (
                f'{_campaign_env}{SIGCOMM_PYTHON} -u {controller_script} '
                f'--relay_ip 10.0.2.1 '
                f'--relay_name r0 '
                f'--decision_file {r0_decisions_file} '
                f'--max_users {num_subscribers} '
                f'--user_offset 1 '
                f'--network_type {network_type} '
                f'--strategy {strategy} '
                f'--model_path {model_path} '
                f'--interval {interval} '
                f'--federation off'
            )
            # ✅ trace CSV FOV
            if trace_csv_path:
                controller_cmd += (
                    f' --use_fov_grouping '
                    f'--trace_csv {trace_csv_path} '
                    f'--fov_overlap_threshold 0.5'
                )
                info(f"✅ FOV trace_csv={trace_csv_path} \n")
            else:
                info(f"⚠️ trace CSV \n")
            r0.cmd(f"{controller_cmd} > /tmp/{TMP_PREFIX}r0_controller.log 2>&1 &")
            time.sleep(2)
            controller_pid = r0.cmd(f"pgrep -f 'regional_relay_controller.*r0' || echo ''").strip()
            if controller_pid:
                info(f"✅ r0 Controller (PID: {controller_pid})\n")
                controller_processes.append(("r0", controller_pid))
                start_cpu_monitor(r0, "r0")
            else:
                info(f"⚠️ r0 Controller ID \n")
        else:
            info(f"⚠️ Controller : {controller_script} \n")
    
    # ✅ MD2G/Heuristic/Clustering r1/r2 controller
    elif (not _NESTED_COMPONENTS) and strategy in ["md2g", "heuristic", "clustering"]:
        # command106: when C28/MM26 admission flags are set, use MM26 controller
        # that actually implements MU/admission/completion (root controller ignored them).
        def _resolve_controller_script():
            root_ctrl = os.path.join(CURRENT_DIR, "regional_relay_controller.py")
            mm26_ctrl = os.path.join(CURRENT_DIR, "MM26", "regional_relay_controller.py")
            want_mm26 = os.environ.get("MM26_ADAPTIVE_ADMISSION", "").strip().lower() in (
                "1", "true", "yes", "on",
            )
            if want_mm26 and strategy.lower() == "md2g" and os.path.isfile(mm26_ctrl):
                info(f"🧭 command106: using MM26 controller for md2g: {mm26_ctrl}\n")
                return mm26_ctrl
            return root_ctrl

        # r1 Controller r1_sub_count
        if r1_sub_count > 0:
            controller_script = _resolve_controller_script()
            if os.path.exists(controller_script):
                info(f"🚀 r1 {strategy} Controller ( {r1_sub_count} )...\n")
                
                # MD2G: trained_models/deploy_student_128/ppo_actor_student_{network_type}.pth
                # Rolling: trained_models/sc_ddqn_rolling.pth
                if model_path is None:
                    model_path = os.path.join(CURRENT_DIR, "trained_models")
                
                # ✅ Mininet
                model_path = os.path.abspath(model_path)
                
                # trace CSV tiles
                # ✅ trace 5g
                trace_csv_path = None
                trace_csv_candidates = [
                    # tiles
                    os.path.join(CURRENT_DIR, "datasets", "processed", "train_tiles.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "processed", "test_tiles.csv"),
                    # trace
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_trace.csv"),
                    # trace
                    os.path.join(CURRENT_DIR, "datasets", "5g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "wifi_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "4g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "fiber_optic_final_trace.csv"),
                ]
                for candidate in trace_csv_candidates:
                    if os.path.exists(candidate):
                        trace_csv_path = candidate
                        info(f"✅ trace CSV : {trace_csv_path}\n")
                        break
                
                # Controller dominant network
                controller_cmd = (
                    f'{_campaign_env}{SIGCOMM_PYTHON} -u {controller_script} '
                    f'--relay_ip 10.0.2.2 '
                    f'--relay_name r1 '
                    f'--decision_file {r1_decisions_file} '
                    f'--max_users {r1_sub_count} '
                    f'--user_offset 1 '
                    f'--network_type {network_type} '
                    f'--strategy {strategy} '
                    f'--model_path {model_path} '
                    f'--interval {interval} '
                    f'--federation off'
                )
                relay_features_csv = os.path.join(log_path, "md2g_decision_features_r1.csv")
                controller_cmd += f' --md2g_features_csv {shlex.quote(relay_features_csv)}'
                # ✅ trace CSV FOV
                if trace_csv_path:
                    controller_cmd += (
                        f' --use_fov_grouping '
                        f'--trace_csv {trace_csv_path} '
                        f'--fov_overlap_threshold 0.5'
                    )
                    info(f"✅ FOV trace_csv={trace_csv_path} \n")
                else:
                    info(f"⚠️ trace CSV \n")
                if strategy.lower() == "md2g":
                    md2g_steps = max(2, int(duration / max(interval, 0.1)) + 1)
                    loop_cmd = (
                        f"/bin/bash -lc \"for ((step=0; step<{md2g_steps}; step++)); do "
                        f"MD2G_DECISION_STEP=\\$step {controller_cmd} --decision_step \\$step --frame_id \\$((step*30)); "
                        f"sleep {interval}; done\""
                    )
                    r1.cmd(f"{loop_cmd} > /tmp/{TMP_PREFIX}r1_controller.log 2>&1 &")
                else:
                    r1.cmd(f"{controller_cmd} > /tmp/{TMP_PREFIX}r1_controller.log 2>&1 &")
                time.sleep(2)
                controller_pid = r1.cmd(f"pgrep -f 'regional_relay_controller.*r1' || echo ''").strip()
                if controller_pid:
                    info(f"✅ r1 Controller (PID: {controller_pid})\n")
                    controller_processes.append(("r1", controller_pid))
                    start_cpu_monitor(r1, "r1")
                else:
                    info(f"⚠️ r1 Controller ID \n")
            else:
                info(f"⚠️ Controller : {controller_script} \n")
        
        # r2 Controller r2_sub_count
        if r2_sub_count > 0:
            controller_script = _resolve_controller_script()
            if os.path.exists(controller_script):
                info(f"🚀 r2 {strategy} Controller ( {r2_sub_count} )...\n")
                
                if model_path is None:
                    model_path = os.path.join(CURRENT_DIR, "trained_models")
                
                # ✅ Mininet
                model_path = os.path.abspath(model_path)
                
                # ✅ FOV r1 trace CSV
                # trace CSV tiles
                # ✅ trace 5g
                trace_csv_path = None
                trace_csv_candidates = [
                    # tiles
                    os.path.join(CURRENT_DIR, "datasets", "processed", "train_tiles.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "processed", "test_tiles.csv"),
                    # trace
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", f"{network_type}_trace.csv"),
                    # trace
                    os.path.join(CURRENT_DIR, "datasets", "5g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "wifi_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "4g_final_trace.csv"),
                    os.path.join(CURRENT_DIR, "datasets", "fiber_optic_final_trace.csv"),
                ]
                for candidate in trace_csv_candidates:
                    if os.path.exists(candidate):
                        trace_csv_path = candidate
                        break
                
                controller_cmd = (
                    f'{_campaign_env}{SIGCOMM_PYTHON} -u {controller_script} '
                    f'--relay_ip 10.0.3.2 '
                    f'--relay_name r2 '
                    f'--decision_file {r2_decisions_file} '
                    f'--max_users {r2_sub_count} '
                    f'--user_offset {r1_sub_count + 1} '
                    f'--network_type {network_type} '
                    f'--strategy {strategy} '
                    f'--model_path {model_path} '
                    f'--interval {interval} '
                    f'--federation off'
                )
                relay_features_csv = os.path.join(log_path, "md2g_decision_features_r2.csv")
                controller_cmd += f' --md2g_features_csv {shlex.quote(relay_features_csv)}'
                # ✅ trace CSV FOV
                if trace_csv_path:
                    controller_cmd += (
                        f' --use_fov_grouping '
                        f'--trace_csv {trace_csv_path} '
                        f'--fov_overlap_threshold 0.5'
                    )
                if strategy.lower() == "md2g":
                    md2g_steps = max(2, int(duration / max(interval, 0.1)) + 1)
                    loop_cmd = (
                        f"/bin/bash -lc \"for ((step=0; step<{md2g_steps}; step++)); do "
                        f"MD2G_DECISION_STEP=\\$step {controller_cmd} --decision_step \\$step --frame_id \\$((step*30)); "
                        f"sleep {interval}; done\""
                    )
                    r2.cmd(f"{loop_cmd} > /tmp/{TMP_PREFIX}r2_controller.log 2>&1 &")
                else:
                    r2.cmd(f"{controller_cmd} > /tmp/{TMP_PREFIX}r2_controller.log 2>&1 &")
                time.sleep(2)
                controller_pid = r2.cmd(f"pgrep -f 'regional_relay_controller.*r2' || echo ''").strip()
                if controller_pid:
                    info(f"✅ r2 Controller (PID: {controller_pid})\n")
                    controller_processes.append(("r2", controller_pid))
                    start_cpu_monitor(r2, "r2")
                else:
                    info(f"⚠️ r2 Controller ID \n")
            else:
                info(f"⚠️ Controller : {controller_script} \n")
    
    # ✅ Relay
    # ✅ MD2G, Rolling, Heuristic, Clustering, PCC-DASH r1/r2
    # ✅ Rolling/PCC-DASH r1/r2 DASH
    if strategy.lower() in ["rolling", "groot"]:
        # r1 r1_sub_count
        if not os.path.exists(r1_decisions_file) and r1_sub_count > 0:
            default_decisions_r1 = {
                "decisions": {
                    str(i): {
                        "pull_enhanced": False,
                        "target_relay_ip": "10.0.2.2",
                        "base_bitrate_level": 0
                    }
                    for i in range(1, r1_sub_count + 1)
                }
            }
            with open(r1_decisions_file, 'w') as f:
                json.dump(default_decisions_r1, f)
            info(f"✅ r1 : {r1_decisions_file} ( 1-{r1_sub_count})\n")
        
        # r2 r2_sub_count
        if not os.path.exists(r2_decisions_file) and r2_sub_count > 0:
            default_decisions_r2 = {
                "decisions": {
                    str(i): {
                        "pull_enhanced": False,
                        "target_relay_ip": "10.0.3.2",
                        "base_bitrate_level": 0
                    }
                    for i in range(r1_sub_count + 1, num_subscribers + 1)
                }
            }
            with open(r2_decisions_file, 'w') as f:
                json.dump(default_decisions_r2, f)
            info(f"✅ r2 : {r2_decisions_file} ( {r1_sub_count+1}-{num_subscribers})\n")
    
    # ✅ MD2G/Heuristic/Clustering r1/r2
    # r1 r1_sub_count
    elif not os.path.exists(r1_decisions_file) and r1_sub_count > 0:
        default_decisions_r1 = {
            "decisions": {
                str(i): {
                    "pull_enhanced": False,
                    "target_relay_ip": "10.0.2.2",
                    "base_bitrate_level": 0
                }
                for i in range(1, r1_sub_count + 1)
            }
        }
        with open(r1_decisions_file, 'w') as f:
            json.dump(default_decisions_r1, f)
        info(f"✅ r1 : {r1_decisions_file} ( 1-{r1_sub_count})\n")
    
    # r2 r2_sub_count
    if not os.path.exists(r2_decisions_file) and r2_sub_count > 0:
        default_decisions_r2 = {
            "decisions": {
                str(i): {
                    "pull_enhanced": False,
                    "target_relay_ip": "10.0.3.2",
                    "base_bitrate_level": 0
                }
                for i in range(r1_sub_count + 1, num_subscribers + 1)
            }
        }
        with open(r2_decisions_file, 'w') as f:
            json.dump(default_decisions_r2, f)
        info(f"✅ r2 : {r2_decisions_file} ( {r1_sub_count+1}-{num_subscribers})\n")
    
    client_device_map = _load_client_device_map(device_map_path)
    client_device_meta = {}
    for client_id in range(1, num_subscribers + 1):
        device_type = assign_device_type(client_id, client_device_map=client_device_map)
        profile = DEVICE_PROFILES[device_type]
        device_score = compute_device_score(profile)
        client_device_meta[client_id] = {
            "device_type": device_type,
            "device_score": device_score,
            "device_cpu": profile["cpu"],
            "device_gpu": profile["gpu"],
            "device_ram": profile["ram"],
            "device_refresh": profile["refresh"],
            "device_res_w": profile["res_w"],
            "device_res_h": profile["res_h"],
        }
        info(f"[device-profile] client={client_id} type={device_type} score={device_score:.4f}\n")

    unique_scores = {meta["device_score"] for meta in client_device_meta.values()}
    if len(unique_scores) < 2:
        info("[warning] device heterogeneity is inactive: all clients received the same device_score\n")

    device_meta_json = os.path.join(log_path, "device_profile_assignments.json")
    with open(device_meta_json, "w", encoding="utf-8") as f:
        json.dump(client_device_meta, f, indent=2)
    device_meta_csv = os.path.join(log_path, "device_profile_assignments.csv")
    with open(device_meta_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "client_id", "device_type", "device_score",
            "device_cpu", "device_gpu", "device_ram",
            "device_refresh", "device_res_w", "device_res_h",
        ])
        for client_id in sorted(client_device_meta.keys()):
            m = client_device_meta[client_id]
            writer.writerow([
                client_id, m["device_type"], f'{m["device_score"]:.4f}',
                m["device_cpu"], m["device_gpu"], m["device_ram"],
                m["device_refresh"], m["device_res_w"], m["device_res_h"],
            ])
    
    # ✅ rolling md2g
    if model_path is None:
        model_path = os.path.join(CURRENT_DIR, "trained_models")
    
    # ✅ Mininet
    model_path = os.path.abspath(model_path)
    
    # ✅ gst_plugin_path moq-sub dispatch_strategy
    gst_plugin_path = "/usr/lib/x86_64-linux-gnu/gstreamer-1.0"
    
    def gen_dispatch_cmd(host_id: int):
        """
         dispatch_strategy 
        
        ✅ vs - 
        - Multicast MD2G/Heuristic/Clustering Edge Relay (r1/r2) r1/r2 r0 r1/r2 
           Publisher -> r0 --(1 stream)--> r1/r2 --(Fan-out)--> Users
        - Unicast Rolling/PCC-DASH Edge Relay (r1/r2) 
           Publisher -> r0 --(N streams)--> [r1/r2 IP ] --> Users
        
        ✅ 
        - Mininet h1 r0 h1 <-> s1 <-> r1 <-> r0
        - h1 r0 TCP/QUIC r0 -> r1 575Mbps 
        - 
        """
        # ✅ MD2G, Rolling, Heuristic, Clustering, PCC-DASH r1/r2
        # controller r1/r2 DASH
        # Relay
        if host_id <= r1_sub_count:
            target_relay_ip = "10.0.2.2"
            decisions_file_for_user = r1_decisions_file
            relay_name = "r1"
        else:
            target_relay_ip = "10.0.3.2"
            decisions_file_for_user = r2_decisions_file
            relay_name = "r2"
        
        # ✅ dispatch_strategy
        # dispatch_strategy buffer_level
        dev = client_device_meta[host_id]
        # Forward campaign QoE/ladder contract into Mininet host namespaces.
        _eq9 = str(os.environ.get("SIGCOMM_QOE_EQ9", "")).strip() or "0"
        _ladder = str(os.environ.get("SIGCOMM_REP_LADDER", "")).strip() or "0"
        _cell_state = os.environ.get("SIGCOMM_CELL_STATE_DIR", "")
        _cell_log = os.environ.get("SIGCOMM_CELL_LOG_PATH", log_path)
        env_vars = (
            f'{_campaign_env}'
            f'SIGCOMM_CELL_TMP={TMP_PREFIX} '
            f'SIGCOMM_CELL_STATE_DIR={shlex.quote(_cell_state)} '
            f'SIGCOMM_CELL_LOG_PATH={shlex.quote(_cell_log)} '
            f'SIGCOMM_QOE_EQ9={_eq9} '
            f'SIGCOMM_REP_LADDER={_ladder} '
            f'BASE_BITRATE_MBPS={BASE_BITRATE_MBPS:.2f} '
            f'ENH_BITRATE_MBPS={ENH_BITRATE_MBPS:.2f} '
            f'DEVICE_TYPE={dev["device_type"]} '
            f'DEVICE_SCORE={dev["device_score"]:.4f} '
            f'DEVICE_CPU={dev["device_cpu"]} '
            f'DEVICE_GPU={dev["device_gpu"]} '
            f'DEVICE_RAM={dev["device_ram"]} '
            f'DEVICE_REFRESH={dev["device_refresh"]} '
            f'DEVICE_RES_W={dev["device_res_w"]} '
            f'DEVICE_RES_H={dev["device_res_h"]} '
        )
        
        return (
            f'{env_vars} {SIGCOMM_PYTHON} -u {shlex.quote(dispatch_script)} '
            f'--host_id {host_id} '
            f'--log_path {shlex.quote(log_path)} '
            f'--strategy {strategy} '
            f'--decision_file {shlex.quote(decisions_file_for_user)} '
            f'--clients {num_subscribers} '
            f'--relay_ip {target_relay_ip} '
            f'--gst_plugin_path {shlex.quote(gst_plugin_path)} '
            f'--device_score {dev["device_score"]:.4f} '
            f'--device_type {dev["device_type"]} '
            f'--network_type {network_type} '
            f'--model_path {shlex.quote(model_path)} '
            f'--duration {duration} '
            f'--interval {interval} '
            f'--federation off'
        )
    
    subscribers = [net.get(f'h{i}') for i in range(1, num_subscribers + 1)]
    subscriber_pids = []
    subscriber_launch_failures = []
    
    BATCH_SIZE = 2
    BATCH_INTERVAL = 1.0
    PROCESS_CHECK_DELAY = 0.5
    
    info(f" 📊 {BATCH_SIZE} {BATCH_INTERVAL} \n")
    
    for batch_start in range(0, num_subscribers, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, num_subscribers)
        batch_clients = list(range(batch_start + 1, batch_end + 1))
        
        info(f" 🚀 {batch_start//BATCH_SIZE + 1} h{batch_clients[0]} h{batch_clients[-1]} ({len(batch_clients)} )...\n")
        
        for i in batch_clients:
            host = subscribers[i - 1]
            cmd = gen_dispatch_cmd(i)
            
            if i <= r1_sub_count:
                relay_name = "r1"
                target_relay_ip = "10.0.2.2"
            else:
                relay_name = "r2"
                target_relay_ip = "10.0.3.2"

            stdout_log = os.path.join(log_path, f"client_h{i}_dispatch_stdout.log")
            pid_file = f"/tmp/{TMP_PREFIX}h{i}_dispatch.pid"
            launch_json = os.path.join(log_path, f"subscriber_h{i}_launch.json")
            launch_rec = {
                "host_id": i,
                "relay": relay_name,
                "relay_ip": target_relay_ip,
                "interpreter": SIGCOMM_PYTHON,
                "dispatch_script": dispatch_script,
                "strategy": strategy,
                "network_type": network_type,
                "log_path": log_path,
                "stdout_log": stdout_log,
                "cmd": cmd,
                "env": {
                    "SIGCOMM_CELL_TMP": TMP_PREFIX,
                    "SIGCOMM_CELL_STATE_DIR": os.environ.get("SIGCOMM_CELL_STATE_DIR", ""),
                    "SIGCOMM_CELL_LOG_PATH": os.environ.get("SIGCOMM_CELL_LOG_PATH", log_path),
                    "SIGCOMM_QOE_EQ9": os.environ.get("SIGCOMM_QOE_EQ9", ""),
                    "SIGCOMM_REP_LADDER": os.environ.get("SIGCOMM_REP_LADDER", ""),
                    "SIGCOMM_PYTHON": SIGCOMM_PYTHON,
                    **_campaign_env_dict,
                },
            }
            with open(launch_json, "w", encoding="utf-8") as jf:
                json.dump(launch_rec, jf, indent=2, ensure_ascii=False)
                jf.write("\n")

            # Background start + capture real PID via echo $! (no nested-quote bash -c)
            host.cmd(
                f"{cmd} > {shlex.quote(stdout_log)} 2>&1 & echo $! > {shlex.quote(pid_file)}"
            )
        
        time.sleep(PROCESS_CHECK_DELAY)
        
        for i in batch_clients:
            host = subscribers[i - 1]
            if i <= r1_sub_count:
                relay_name = "r1"
            else:
                relay_name = "r2"
            pid_file = f"/tmp/{TMP_PREFIX}h{i}_dispatch.pid"
            launch_json = os.path.join(log_path, f"subscriber_h{i}_launch.json")
            pid = host.cmd(f"cat {shlex.quote(pid_file)} 2>/dev/null || echo ''").strip().split("\n")[0].strip()
            cmdline = ""
            if subscriber_pid_ok(pid):
                cmdline = host.cmd(
                    f"tr '\\0' ' ' < /proc/{pid}/cmdline 2>/dev/null || echo ''"
                ).strip()
            ok = (
                subscriber_pid_ok(pid)
                and os.path.isfile(launch_json)
                and bool(cmdline)
                and ("dispatch" in cmdline or "python" in cmdline)
            )
            # persist pid into launch json
            try:
                with open(launch_json, "r", encoding="utf-8") as jf:
                    rec = json.load(jf)
                rec["pid"] = pid if subscriber_pid_ok(pid) else None
                rec["cmdline"] = cmdline
                rec["launch_ok"] = bool(ok)
                with open(launch_json, "w", encoding="utf-8") as jf:
                    json.dump(rec, jf, indent=2, ensure_ascii=False)
                    jf.write("\n")
            except Exception:
                pass

            if ok:
                CELL_RECORDED_PIDS.add(pid.split()[0])
                subscriber_pids.append((i, pid.split()[0], relay_name))
                info(f" ✅ h{i} (PID: {pid}, {relay_name})\n")
            else:
                subscriber_launch_failures.append(i)
                error(f"      ❌ h{i} SUBSCRIBER_LAUNCH_GATE FAIL (PID={pid!r}, cmdline={cmdline[:80]!r})\n")
        
        if batch_end < num_subscribers:
            time.sleep(BATCH_INTERVAL)

    if subscriber_launch_failures or len(subscriber_pids) < num_subscribers:
        error(
            f"❌ SUBSCRIBER_LAUNCH_GATE FAILED: "
            f"ok={len(subscriber_pids)}/{num_subscribers} fail_ids={subscriber_launch_failures}\n"
        )
        copy_cell_tmp_logs(log_path, TMP_PREFIX)
        compute_and_write_cell_validity(
            log_path,
            strategy=strategy,
            num_subscribers=num_subscribers,
            registered_publishers=registered_publishers,
            expected_publishers=expected_publishers,
            subscriber_pids=subscriber_pids,
            leaf_egress_bytes=0,
        )
        cleanup_all_processes(tmp_prefix=TMP_PREFIX, recorded_pids=CELL_RECORDED_PIDS, log_path=log_path)
        cell_scoped_exit_cleanup(log_path, num_subscribers, TMP_PREFIX, net=net)
        raise SystemExit(2)
    
    info(f"📊 ...\n")
    initial_traffic = {}
    
    try:
        r0_eth1_tx_initial = int(r0.cmd(f'cat /sys/class/net/r0-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r0_eth1_tx'] = r0_eth1_tx_initial
        
        r0_eth2_tx_initial = int(r0.cmd(f'cat /sys/class/net/r0-eth2/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r0_eth2_tx'] = r0_eth2_tx_initial
        
        # ✅ Rolling r0 n0 r0 fan-out
        r0_eth0_rx_initial = int(r0.cmd(f'cat /sys/class/net/r0-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r0_eth0_rx'] = r0_eth0_rx_initial
        
        r1_eth0_rx_initial = int(r1.cmd(f'cat /sys/class/net/r1-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r1_eth0_rx'] = r1_eth0_rx_initial
        
        r1_eth1_tx_initial = int(r1.cmd(f'cat /sys/class/net/r1-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r1_eth1_tx'] = r1_eth1_tx_initial
        
        r2_eth0_rx_initial = int(r2.cmd(f'cat /sys/class/net/r2-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r2_eth0_rx'] = r2_eth0_rx_initial
        
        r2_eth1_tx_initial = int(r2.cmd(f'cat /sys/class/net/r2-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        initial_traffic['r2_eth1_tx'] = r2_eth1_tx_initial
        
        info(f" ✅ :\n")
        info(f"      r0→r1 (r0-eth1 TX): {r0_eth1_tx_initial:,} bytes\n")
        info(f"      r0→r2 (r0-eth2 TX): {r0_eth2_tx_initial:,} bytes\n")
        info(f" r1 r0 (r1-eth0 RX): {r1_eth0_rx_initial:,} bytes\n")
        info(f" r1 (r1-eth1 TX): {r1_eth1_tx_initial:,} bytes\n")
        info(f" r2 r0 (r2-eth0 RX): {r2_eth0_rx_initial:,} bytes\n")
        info(f" r2 (r2-eth1 TX): {r2_eth1_tx_initial:,} bytes\n")
    except Exception as e:
        error(f" ⚠️ : {e} 0 \n")
        initial_traffic = {
            'r0_eth1_tx': 0, 'r0_eth2_tx': 0, 'r0_eth0_rx': 0,
            'r1_eth0_rx': 0, 'r1_eth1_tx': 0,
            'r2_eth0_rx': 0, 'r2_eth1_tx': 0
        }
    
    info(f" ✅ {num_subscribers} Subscriber dispatch_strategy \n")
    info(f" 📊 : {strategy}, : {network_type}, : {log_path}\n")
    
    info(f"\n⏳ 20 ...\n")
    time.sleep(20)
    
    # Nested b0/db1/db2/e1/e2 publishers are not hang publish.*base / *enhanced.
    if not _NESTED_COMPONENTS:
        info(f"🔍 Publisher ...\n")
        pub_base_running = n0.cmd("pgrep -f 'hang.*publish.*base' || echo ''").strip()
        pub_enh_running = n0.cmd("pgrep -f 'hang.*publish.*enhanced' || echo ''").strip()
        if not pub_base_running:
            error("❌ Base Publisher \n")
        if not pub_enh_running:
            error("❌ Enhanced Publisher \n")
    else:
        info("🔍 nested component publishers: skip 2-track base/enhanced pgrep\n")
    
    # E028: full u60/u100 per-host host.cmd verify can hang for hours (defunct bash /
    # unreaped namespaces). Nested campaigns already score dumps/receipts later
    # keep this check best-effort with cmd timeout + wall budget; sample-only at scale.
    info(f"🔍 ...\n")
    client_connected_count = 0
    verify_budget = float(os.environ.get("MOQ_CLIENT_VERIFY_BUDGET_S", "60"))
    verify_cmd_to = int(float(os.environ.get("MOQ_CLIENT_VERIFY_CMD_TIMEOUT_S", "5")))
    verify_cmd_to = max(1, min(verify_cmd_to, 30))
    t_verify0 = time.time()
    max_verify_hosts = num_subscribers
    if _NESTED_COMPONENTS and num_subscribers >= 60:
        max_verify_hosts = min(5, num_subscribers)
        info(
            f"   E028: nested u>={60}: sample-verify first {max_verify_hosts} hosts "
            f"(cmd_timeout={verify_cmd_to}s, budget={verify_budget}s)\n"
        )
    for i in range(1, max_verify_hosts + 1):
        if time.time() - t_verify0 > verify_budget:
            info(f"⚠️ client verify budget exhausted at h{i}; continuing experiment\n")
            break
        host = net.get(f'h{i}')
        if host is None:
            continue
        # ✅ pgrep --host_id {i} h{i}
        try:
            client_pid = host.cmd(
                f"timeout {verify_cmd_to} pgrep -f 'dispatch_strategy.*--host_id {i}' || echo ''"
            ).strip()
            if client_pid:
                dump_file = f"/tmp/moq_h{i}.bin"
                if host.cmd(
                    f"timeout {verify_cmd_to} test -f {dump_file} && echo 'yes' || echo 'no'"
                ).strip() == 'yes':
                    dump_size = int(
                        host.cmd(
                            f"timeout {verify_cmd_to} stat -c%s {dump_file} 2>/dev/null || echo '0'"
                        ).strip()
                        or "0"
                    )
                    if dump_size > 0:
                        client_connected_count += 1
                        if i <= 3:
                            info(f" ✅ h{i} (dump : {dump_size:,} bytes)\n")
        except Exception as _verify_exc:
            info(f"   ⚠️ h{i} verify skipped: {_verify_exc}\n")
            continue
    
    if client_connected_count == 0:
        error(f"⚠️ \n")
        error(f" : /tmp/{TMP_PREFIX}h*_dispatch.log\n")
    else:
        info(f"✅ {client_connected_count}/{max_verify_hosts} sampled clients connected (of {num_subscribers})\n")
    
    r0_eth1_tx_check = int(r0.cmd(f'cat /sys/class/net/r0-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
    r1_eth1_tx_check = int(r1.cmd(f'cat /sys/class/net/r1-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
    r2_eth1_tx_check = int(r2.cmd(f'cat /sys/class/net/r2-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
    
    if r0_eth1_tx_check < 10000:
        error(f"⚠️ r0→r1 ({r0_eth1_tx_check:,} bytes) \n")
        error(f" Publisher : /tmp/{TMP_PREFIX}pub_base.log\n")
    else:
        info(f"✅ r0→r1 {r0_eth1_tx_check:,} bytes \n")
    
    r1_eth1_tx_check_delta = r1_eth1_tx_check - initial_traffic.get('r1_eth1_tx', 0)
    r2_eth1_tx_check_delta = r2_eth1_tx_check - initial_traffic.get('r2_eth1_tx', 0)
    
    if r1_eth1_tx_check_delta == 0 and r2_eth1_tx_check_delta == 0:
        error(f"⚠️ r1 r2 =0 \n")
        error(f" r1→ : ={initial_traffic.get('r1_eth1_tx', 0):,} bytes, ={r1_eth1_tx_check:,} bytes, ={r1_eth1_tx_check_delta:,} bytes\n")
        error(f" r2→ : ={initial_traffic.get('r2_eth1_tx', 0):,} bytes, ={r2_eth1_tx_check:,} bytes, ={r2_eth1_tx_check_delta:,} bytes\n")
        error(f" \n")
        error(f" 1. r1/r2 \n")
        error(f" 2. track r1/r2 \n")
        error(f" 3. Relay r1/r2 cluster \n")
    else:
        info(f"✅ Relay r1→ : {r1_eth1_tx_check_delta:,} bytes, r2→ : {r2_eth1_tx_check_delta:,} bytes\n")
    
    info(f"\n {duration} perf.csv ...\n")
    if _command137_raw_4g() and subscribers:
        try:
            _p4 = NETWORK_DATASETS.get("4g")
            _xs = []
            if _p4 and os.path.isfile(_p4):
                import pandas as _pd

                _df = _pd.read_csv(_p4)
                _col = "DL_bitrate_Mbps" if "DL_bitrate_Mbps" in _df.columns else _df.columns[0]
                _xs = [float(x) for x in _df[_col].dropna().tolist() if float(x) >= 0]
            _h0 = subscribers[0]

            def _drive_raw_4g():
                for _i in range(int(duration)):
                    _bw = max(0.05, _xs[_i % len(_xs)]) if _xs else 0.4
                    try:
                        _h0.intf(f"{_h0.name}-eth0").config(bw=_bw)
                    except Exception:
                        pass
                    time.sleep(1)

            threading.Thread(target=_drive_raw_4g, daemon=True).start()
            info("COMMAND137 raw 4G time-series last-mile driver started (no 6.5/30 floor)\n")
        except Exception as _e:
            error(f"COMMAND137 raw 4G driver failed: {_e}\n")
    if _NESTED_COMPONENTS:
        try:
            _ton_lib = str(Path(__file__).resolve().parent / "Sigcomm26" / "Paper6_ToN" / "lib")
            if _ton_lib not in sys.path:
                sys.path.insert(0, _ton_lib)
            from command147_nested_runtime import schedule_targets as _sched  # noqa: E402
            from component_actuation_plan import build_plan as _bplan  # noqa: E402
            from dataclasses import asdict as _asdict

            _pattern = os.environ.get("COMMAND147_SMOKE_PATTERN") or "S0_B1_only"
            _n_users = int(num_subscribers)
            _seq = {"n": 0}
            _active = {"s": list(nested_live)}

            def _nested_planner():
                t_start = time.time()
                last_targets = None
                while time.time() - t_start < float(duration):
                    t = time.time() - t_start
                    _strat = (os.environ.get("COMMAND148_STRATEGY") or "").strip()
                    if _strat:
                        from command148_component_policy import (  # noqa: E402
                            physical_publisher_keys as _phys,
                            schedule_strategy_targets as _stargets,
                        )
                        targets = _stargets(
                            _strat,
                            t,
                            _n_users,
                            float(duration),
                            log_path=log_path,
                            content=os.environ.get("TON_CONTENT_ID") or "redandblack",
                        )
                    else:
                        targets = _sched(
                            _pattern, t, duration=float(duration), n_users=_n_users
                        )
                        _phys = None
                    unicast = str(os.environ.get("COMMAND148_UNICAST") or "").strip().lower() in (
                        "1",
                        "true",
                        "yes",
                    ) or (_strat == "MOQ_UNICAST_COMPONENT")
                    plan = _bplan(
                        decision_seq=_seq["n"],
                        group="g0",
                        user_target_states=targets,
                        currently_active=list(
                            [c for c in _active["s"] if c in ("b0", "db1", "db2", "e1", "e2")]
                        ),
                        reason=f"nested_tick:{_pattern or _strat}:t={t:.1f}",
                    )
                    if _phys is not None:
                        need = _phys(targets, unicast)
                    else:
                        need = [(c, c) for c in plan.required_component_set]
                    need_keys = [k for k, _c in need]
                    open_p = [(k, c) for k, c in need if k not in nested_live]
                    close_p = [k for k in list(nested_live) if k not in need_keys]
                    targets_changed = targets != last_targets
                    if open_p or close_p or targets_changed:
                        for k in close_p:
                            try:
                                _kill_one_publisher(k)
                            except Exception as exc:
                                error(f"nested close {k} failed: {exc}\n")
                        for k, c in open_p:
                            try:
                                _launch_one_publisher(k, video_files[c], k)
                                nested_live.add(k)
                            except Exception as exc:
                                error(f"nested open {k}/{c} failed: {exc}\n")
                        _active["s"] = list(plan.required_component_set)
                        _seq["n"] += 1
                        body = _asdict(plan)
                        body["writer"] = "ComponentActuationPlan.apply"
                        body["unicast_independent_copies"] = bool(unicast)
                        body["physical_publisher_keys"] = need_keys
                        Path(nested_plan_current).write_text(json.dumps(body, default=str) + "\n")
                        with open(nested_plan_jsonl, "a") as jf:
                            jf.write(json.dumps(body, default=str) + "\n")
                        last_targets = dict(targets)
                        info(
                            f"[COMPONENT-PLAN] seq={plan.decision_seq} open={[k for k,_ in open_p]} "
                            f"close={close_p} required={plan.required_component_set} unicast={unicast}\n"
                        )
                    time.sleep(1.0)

            threading.Thread(target=_nested_planner, daemon=True).start()
            info(f"COMMAND147 nested planner started pattern={_pattern}\n")
        except Exception as _ne:
            error(f"COMMAND147 nested planner failed to start: {_ne}\n")
            raise
    # command151: sample shared-root r0-eth1 TX (protocol-inclusive). Do not derive Rb from Ro/B_shared.
    _press_stop = threading.Event()
    _press_path = None
    _press_thread = None
    try:
        if log_path:
            _press_path = str(Path(log_path) / "PHYSICAL_PRESSURE_TIMESERIES.jsonl")
            _cap_mbps = float(min(bw_r0_r1, 1000.0))
            _cap_bps = _cap_mbps * 1e6
            ident = {
                "identity": "shared_regional_root_r0_eth1_tx",
                "iface": "r0-eth1",
                "node": "r0",
                "capacity_mbps": _cap_mbps,
                "capacity_bps": _cap_bps,
                "sample_interval_s": 1.0,
            }
            Path(log_path).mkdir(parents=True, exist_ok=True)
            (Path(log_path) / "BOTTLENECK_IDENTITY.json").write_text(json.dumps(ident, indent=2) + "\n")

            def _pressure_loop():
                while not _press_stop.is_set():
                    raw_tx = host_cmd_safe(r0, "cat /sys/class/net/r0-eth1/statistics/tx_bytes 2>/dev/null || echo 0").strip().split()
                    raw_rx = host_cmd_safe(r0, "cat /sys/class/net/r0-eth1/statistics/rx_bytes 2>/dev/null || echo 0").strip().split()
                    try:
                        tx = int(raw_tx[-1] if raw_tx else 0)
                        rx = int(raw_rx[-1] if raw_rx else 0)
                    except Exception:
                        tx, rx = 0, 0
                    rec = {
                        "t": time.time(),
                        "iface": "r0-eth1",
                        "tx_bytes": tx,
                        "rx_bytes": rx,
                        "capacity_mbps": _cap_mbps,
                        "capacity_bps": _cap_bps,
                    }
                    with open(_press_path, "a") as pf:
                        pf.write(json.dumps(rec) + "\n")
                    _press_stop.wait(1.0)

            _press_thread = threading.Thread(target=_pressure_loop, daemon=True, name="command151_pressure")
            _press_thread.start()
    except Exception as _pe:
        error(f"COMMAND151 pressure sampler failed to start: {_pe}\n")
    time.sleep(duration)
    _press_stop.set()
    if _press_thread is not None:
        _press_thread.join(timeout=5.0)

    r1_eth1_tx_delta = 0
    r2_eth1_tx_delta = 0
    info("-" * 60 + "\n")
    info(" :\n")
    
    # 1. Relay
    info("\n📊 Relay :\n")
    
    # r0 (Root Relay) host_cmd_safe: pressure thread must not leave r0.waiting
    r0_log = host_cmd_safe(r0, f"cat /tmp/{TMP_PREFIX}r0.log 2>&1")
    if "listening addr" in r0_log or "listening" in r0_log.lower():
        info("✅ r0 (Root Relay) \n")
        r0_publish_lines = [line for line in r0_log.split('\n') if 'publish=' in line and 'publish= ' not in line]
        if r0_publish_lines:
            info(f"✅ r0 {len(r0_publish_lines)} publisher \n")
        else:
            error("❌ r0 publisher \n")
    else:
        error("❌ r0 \n")
    
    # r1 (Leaf Relay)
    r1_log = host_cmd_safe(r1, f"cat /tmp/{TMP_PREFIX}r1.log 2>&1")
    if "listening addr" in r1_log or "listening" in r1_log.lower():
        info("✅ r1 (Leaf Relay) \n")
        if "cluster" in r1_log.lower() or "root" in r1_log.lower():
            info("✅ r1 root (cluster root link ok)\n")
        r1_subscribe_lines = [line for line in r1_log.split('\n') if 'subscribe=' in line and 'subscribe= ' not in line]
        if r1_subscribe_lines:
            info(f"✅ r1 {len(r1_subscribe_lines)} subscriber \n")
        else:
            info("ℹ️ r1 subscriber \n")
    else:
        error("❌ r1 \n")
    
    # r2 (Leaf Relay)
    r2_log = host_cmd_safe(r2, f"cat /tmp/{TMP_PREFIX}r2.log 2>&1")
    if "listening addr" in r2_log or "listening" in r2_log.lower():
        info("✅ r2 (Leaf Relay) \n")
        if "cluster" in r2_log.lower() or "root" in r2_log.lower():
            info("✅ r2 root (cluster root link ok)\n")
        r2_subscribe_lines = [line for line in r2_log.split('\n') if 'subscribe=' in line and 'subscribe= ' not in line]
        if r2_subscribe_lines:
            info(f"✅ r2 {len(r2_subscribe_lines)} subscriber \n")
        else:
            info("ℹ️ r2 subscriber \n")
    else:
        error("❌ r2 \n")
    
    # 2. Publisher
    info("\n📊 Publisher :\n")
    if not _NESTED_COMPONENTS:
        pub_base_pid = n0.cmd("pgrep -f 'hang.*publish.*base' || echo ''").strip()
        pub_enh_pid = n0.cmd("pgrep -f 'hang.*publish.*enhanced' || echo ''").strip()
        
        if pub_base_pid:
            info(f"✅ Base Publisher (PID: {pub_base_pid})\n")
        else:
            error("❌ Base Publisher \n")
        
        if pub_enh_pid:
            info(f"✅ Enhanced Publisher (PID: {pub_enh_pid})\n")
        else:
            error("❌ Enhanced Publisher \n")
    else:
        info("ℹ️  nested component publishers: skip 2-track base/enhanced PID check\n")
    
    # 3. Subscriber
    info(f"\n📊 Subscriber ({num_subscribers} ):\n")
    successful_count = 0
    failed_count = 0
    r1_success = 0
    r2_success = 0
    
    for i, host in enumerate(subscribers, 1):
        # ✅ dispatch_strategy moq-sub
        # dispatch_strategy {log_path}/client_h{i}_gst.log
        # moq-sub /tmp/{TMP_PREFIX}h{i}_base.log
        # dispatch_strategy
        dispatch_log = os.path.join(log_path, f"client_h{i}_gst.log")
        old_log = f"/tmp/{TMP_PREFIX}h{i}_base.log"
        
        # perf.csv
        perf_csv = os.path.join(log_path, f"client_h{i}_perf.csv")
        perf_csv_exists = os.path.exists(perf_csv)
        perf_csv_size = 0
        if perf_csv_exists:
            try:
                perf_csv_size = os.path.getsize(perf_csv)
            except:
                pass
        
        name = f"h{i}"
        
        # relay
        if i <= r1_sub_count:
            relay_name = "r1"
        else:
            relay_name = "r2"
        
        # ✅ dispatch_strategy
        # dispatch_log old_log
        log_to_check = dispatch_log if os.path.exists(dispatch_log) else old_log
        
        if os.path.exists(log_to_check):
            try:
                size_int = os.path.getsize(log_to_check)
            except:
                size_int = 0
        else:
            size_int = 0
        
        try:
            if os.path.exists(log_to_check):
                with open(log_to_check, 'rb') as f:
                    log_bytes = f.read()
                    log_content = ''.join(chr(b) if 32 <= b < 127 or b in [9, 10, 13] else ' ' for b in log_bytes[-5000:])
                    log_content = log_content[-500:]
            else:
                log_content = f"[ : {log_to_check}]"
        except Exception as e:
            log_content = f"[ : {e}]"
        
        # ✅ r0 subscriber
        # moq_lite::lite::subscriber: subscribe started .* broadcast=anon/(base|enhanced) .* track=(video0|catalog.json)
        r0_log_path = f"/tmp/{TMP_PREFIX}r0.log"
        r0_log = host_cmd_safe(r0, f"cat {r0_log_path} 2>&1")
        subscribe_pattern = r'moq_lite::lite::subscriber:\s*subscribe\s+started.*broadcast=anon/(base|enhanced).*track=(video0|catalog\.json)'
        has_subscribe = bool(re.search(subscribe_pattern, r0_log, re.IGNORECASE))
        
        has_error = ("error" in log_content.lower() or "failed" in log_content.lower()) if log_content else False
        
        # ✅ "Receiving data" r0 10 publisher: serving group .* track=video0 sequence=
        has_receiving = False
        
        # 1 r0 serving group 10
        r0_log_recent = host_cmd_safe(r0, f"tail -500 {r0_log_path} 2>&1")
        serving_pattern = r'publisher:\s*serving\s+group.*track=video0\s+sequence='
        serving_matches = re.findall(serving_pattern, r0_log_recent, re.IGNORECASE)
        if len(serving_matches) >= 2:
            has_receiving = True
        
        if not has_receiving and size_int > 0:
            MIN_SUCCESS_SIZE = 500 * 1024  # 500KB
            if size_int >= MIN_SUCCESS_SIZE:
                has_receiving = True
        
        # ✅ 3 perf.csv
        # perf.csv > 1KB dispatch_strategy
        if not has_receiving and perf_csv_exists and perf_csv_size > 1024:
            # perf.csv header
            try:
                with open(perf_csv, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        has_receiving = True
                        has_subscribe = True
            except:
                pass
        
        # ✅ perf.csv
        MIN_SUCCESS_SIZE = 500 * 1024  # 500KB
        size_kb = size_int / 1024.0
        size_mb = size_int / (1024.0 * 1024.0)
        
        # perf.csv > 1
        is_success = False
        perf_csv_lines = 0
        if perf_csv_exists:
            try:
                with open(perf_csv, 'r') as f:
                    perf_csv_lines = len(f.readlines())
                    if perf_csv_lines > 1:
                        is_success = True
            except:
                pass
        
        # perf.csv
        if not is_success:
            if size_int >= MIN_SUCCESS_SIZE:
                is_success = True
            elif size_int > 0:
                is_success = False
            else:
                is_success = False
        
        if is_success:
            successful_count += 1
            if relay_name == "r1":
                r1_success += 1
            else:
                r2_success += 1
            status = "✅"
            if perf_csv_exists and perf_csv_lines > 1:
                size_status = f"✅ Perf CSV: {perf_csv_lines-1} "
            else:
                size_status = f"✅ ({size_mb:.2f} MB)"
        elif size_int > 0:
            failed_count += 1
            status = "⚠️"
            size_status = f"⚠️ ({size_kb:.1f} KB) - "
        else:
            failed_count += 1
            status = "❌"
            size_status = f"❌ ({size_kb:.1f} KB) - "
        
        # 10 Subscriber
        if i <= 10 or not is_success:
            info(f" {name} ( {relay_name}): {status}\n")
            # ✅ perf.csv
            if perf_csv_exists:
                info(f" Perf CSV: ✅ ({perf_csv_size/1024:.1f} KB, {perf_csv_lines-1 if perf_csv_lines > 0 else 0} )\n")
            else:
                info(f" Perf CSV: ❌ ( )\n")
            info(f"    Log size: {size_status}\n")
            info(f"    Subscribe: {'✅' if has_subscribe else '❌'}\n")
            info(f"    Receiving data: {'✅' if has_receiving else '❌'}\n")
            info(f"    Errors: {'❌' if has_error else '✅'}\n")
            
            if size_int < MIN_SUCCESS_SIZE and log_content and "[ " not in log_content:
                info(f"    Last log lines:\n")
                for line in log_content.split('\n')[-3:]:
                    if line.strip():
                        info(f"      {line}\n")
    
    success_pct = (successful_count * 100 // num_subscribers) if num_subscribers > 0 else 0
    info(f"\n📈 :\n")
    info(f" Subscriber : {num_subscribers}\n")
    info(f" ✅ (Log size > 500KB): {successful_count} ({success_pct}%)\n")
    info(f" ❌ (Log size < 500KB): {failed_count} ({failed_count*100//num_subscribers if num_subscribers > 0 else 0}%)\n")
    info(f"\n 📊 Relay :\n")
    info(f" r1 (Leaf Relay): {r1_success}/{r1_sub_count} ({r1_success*100//r1_sub_count if r1_sub_count > 0 else 0}%)\n")
    info(f" r2 (Leaf Relay): {r2_success}/{r2_sub_count} ({r2_success*100//r2_sub_count if r2_sub_count > 0 else 0}%)\n")
    info(f"\n 📊 : Log size > 500KB \n")
    if successful_count > 0:
        info(f"   ✅ Subscriber delivery through leaf relays: {successful_count}/{num_subscribers} with data\n")
    else:
        info(f"   ❌ Subscriber delivery through leaf relays FAILED (success rate 0%) — cluster root link ≠ delivery\n")

    # ✅ multicast/unicast
    info(f"\n📊 multicast/unicast ...\n")
    # ✅ relay try
    r0_eth0_rx_mbps = 0.0
    r0_eth1_tx_mbps = 0.0
    r0_eth2_tx_mbps = 0.0
    r0_total_tx_mbps = 0.0
    r1_eth0_rx_mbps = 0.0
    r1_eth1_tx_mbps = 0.0
    r2_eth0_rx_mbps = 0.0
    r2_eth1_tx_mbps = 0.0
    r0_eth0_rx_delta = 0
    r0_eth1_tx_delta = 0
    r0_eth2_tx_delta = 0
    r1_eth0_rx_delta = 0
    r1_eth1_tx_delta = 0
    r2_eth0_rx_delta = 0
    r2_eth1_tx_delta = 0
    
    try:
        r0_eth0_rx_final = int(r0.cmd(f'cat /sys/class/net/r0-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        r0_eth1_tx_final = int(r0.cmd(f'cat /sys/class/net/r0-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        r0_eth2_tx_final = int(r0.cmd(f'cat /sys/class/net/r0-eth2/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        r1_eth0_rx_final = int(r1.cmd(f'cat /sys/class/net/r1-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        r1_eth1_tx_final = int(r1.cmd(f'cat /sys/class/net/r1-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        r2_eth0_rx_final = int(r2.cmd(f'cat /sys/class/net/r2-eth0/statistics/rx_bytes 2>/dev/null || echo "0"').strip() or "0")
        r2_eth1_tx_final = int(r2.cmd(f'cat /sys/class/net/r2-eth1/statistics/tx_bytes 2>/dev/null || echo "0"').strip() or "0")
        
        r0_eth0_rx_delta = r0_eth0_rx_final - initial_traffic.get('r0_eth0_rx', 0)
        r0_eth1_tx_delta = r0_eth1_tx_final - initial_traffic.get('r0_eth1_tx', 0)
        r0_eth2_tx_delta = r0_eth2_tx_final - initial_traffic.get('r0_eth2_tx', 0)
        r1_eth0_rx_delta = r1_eth0_rx_final - initial_traffic.get('r1_eth0_rx', 0)
        r1_eth1_tx_delta = r1_eth1_tx_final - initial_traffic.get('r1_eth1_tx', 0)
        r2_eth0_rx_delta = r2_eth0_rx_final - initial_traffic.get('r2_eth0_rx', 0)
        r2_eth1_tx_delta = r2_eth1_tx_final - initial_traffic.get('r2_eth1_tx', 0)
        
        if r1_eth1_tx_delta == 0 or r2_eth1_tx_delta == 0:
            info(f"\n 🔍 r1/r2 0 ...\n")
            info(f" r1-eth1 TX : {r1_eth1_tx_final:,} bytes, : {initial_traffic.get('r1_eth1_tx', 0):,} bytes, : {r1_eth1_tx_delta:,} bytes\n")
            info(f" r2-eth1 TX : {r2_eth1_tx_final:,} bytes, : {initial_traffic.get('r2_eth1_tx', 0):,} bytes, : {r2_eth1_tx_delta:,} bytes\n")
            info(f" r1-eth0 RX : {r1_eth0_rx_delta:,} bytes r1 r0 \n")
            info(f" r2-eth0 RX : {r2_eth0_rx_delta:,} bytes r2 r0 \n")
            # perf.csv
            total_client_rx = 0
            clients_with_data = 0
            for i in range(1, num_subscribers + 1):
                perf_csv = os.path.join(log_path, f"client_h{i}_perf.csv")
                if os.path.exists(perf_csv):
                    try:
                        with open(perf_csv, 'r') as f:
                            lines = f.readlines()
                            if len(lines) > 1:
                                # rx_bytes
                                header = lines[0].strip().split(',')
                                if 'rx_bytes' in header:
                                    rx_idx = header.index('rx_bytes')
                                    last_line = lines[-1].strip().split(',')
                                    if len(last_line) > rx_idx:
                                        client_rx = int(last_line[rx_idx]) if last_line[rx_idx] else 0
                                        if client_rx > 0:
                                            clients_with_data += 1
                                        total_client_rx += client_rx
                    except:
                        pass
            info(f" perf.csv : {total_client_rx:,} bytes {clients_with_data}/{num_subscribers} \n")
            if total_client_rx > 0 and (r1_eth1_tx_delta == 0 and r2_eth1_tx_delta == 0):
                info(f" ⚠️ r1/r2 0 \n")
                info(f" 1. r0 Rolling/PCC-DASH \n")
                info(f" 2. Publisher \n")
                info(f" 3. \n")
            elif r1_eth0_rx_delta > 0 and r1_eth1_tx_delta == 0:
                info(f" ⚠️ r1 r0 {r1_eth0_rx_delta:,} bytes r1\n")
            elif r2_eth0_rx_delta > 0 and r2_eth1_tx_delta == 0:
                info(f" ⚠️ r2 r0 {r2_eth0_rx_delta:,} bytes r2\n")
        
        # Mbps duration
        r0_eth0_rx_mbps = (r0_eth0_rx_delta * 8.0) / duration / 1e6 if duration > 0 else 0.0
        r0_eth1_tx_mbps = (r0_eth1_tx_delta * 8.0) / duration / 1e6 if duration > 0 else 0.0
        r0_eth2_tx_mbps = (r0_eth2_tx_delta * 8.0) / duration / 1e6 if duration > 0 else 0.0
        r0_total_tx_mbps = r0_eth1_tx_mbps + r0_eth2_tx_mbps
        r1_eth0_rx_mbps = (r1_eth0_rx_delta * 8.0) / duration / 1e6 if duration > 0 else 0.0
        r1_eth1_tx_mbps = (r1_eth1_tx_delta * 8.0) / duration / 1e6 if duration > 0 else 0.0
        r2_eth0_rx_mbps = (r2_eth0_rx_delta * 8.0) / duration / 1e6 if duration > 0 else 0.0
        r2_eth1_tx_mbps = (r2_eth1_tx_delta * 8.0) / duration / 1e6 if duration > 0 else 0.0
        
        info(f" 📊 {duration} :\n")
        info(f" 📡 Relay / :\n")
        info(f" r0 (r0-eth0 RX): {r0_eth0_rx_delta:,} bytes = {r0_eth0_rx_mbps:.4f} Mbps\n")
        info(f" r0 (r0-eth1 TX): {r0_eth1_tx_delta:,} bytes = {r0_eth1_tx_mbps:.4f} Mbps\n")
        info(f" r0 (r0-eth2 TX): {r0_eth2_tx_delta:,} bytes = {r0_eth2_tx_mbps:.4f} Mbps\n")
        info(f" r0 : {r0_total_tx_mbps:.4f} Mbps\n")
        info(f" r1 (r1-eth0 RX): {r1_eth0_rx_delta:,} bytes = {r1_eth0_rx_mbps:.4f} Mbps\n")
        info(f" r1 (r1-eth1 TX): {r1_eth1_tx_delta:,} bytes = {r1_eth1_tx_mbps:.4f} Mbps\n")
        info(f" r2 (r2-eth0 RX): {r2_eth0_rx_delta:,} bytes = {r2_eth0_rx_mbps:.4f} Mbps\n")
        info(f" r2 (r2-eth1 TX): {r2_eth1_tx_delta:,} bytes = {r2_eth1_tx_mbps:.4f} Mbps\n")
        
        # ✅ Multicast
        info(f"\n 📊 Multicast :\n")
        
        # r1 Multicast r1 /r1
        # Multicast r1 1 → r1 /r1 > 1.0
        # Unicast r1 N → r1 /r1 ≈ 1.0
        r1_fanout_ratio = None
        r1_fanout_status = "N/A"
        if r1_eth0_rx_delta > 0:
            if r1_eth1_tx_delta > 0:
                r1_fanout_ratio = r1_eth1_tx_delta / r1_eth0_rx_delta
                if r1_fanout_ratio > 1.0:
                    info(f" ✅ r1: r1 /r1 = {r1_fanout_ratio:.2f}x > 1.0x multicast r1 1 \n")
                elif abs(r1_fanout_ratio - 1.0) < 0.1:
                    info(f" ⚠️ r1: r1 /r1 = {r1_fanout_ratio:.2f}x ≈ 1.0x unicast r1 N \n")
                else:
                    info(f" ⚠️ r1: r1 /r1 = {r1_fanout_ratio:.2f}x < 1.0x \n")
                r1_fanout_status = f"{r1_fanout_ratio:.2f}x"
            else:
                info(f" ❌ r1: r1 = 0 bytes r1 = {r1_eth0_rx_delta:,} bytes r1 \n")
                r1_fanout_status = "0.00x ( )"
        
        # r2 Multicast r2 /r2
        # Multicast r2 1 → r2 /r2 > 1.0
        # Unicast r2 N → r2 /r2 ≈ 1.0
        r2_fanout_ratio = None
        r2_fanout_status = "N/A"
        if r2_eth0_rx_delta > 0:
            if r2_eth1_tx_delta > 0:
                r2_fanout_ratio = r2_eth1_tx_delta / r2_eth0_rx_delta
                if r2_fanout_ratio > 1.0:
                    info(f" ✅ r2: r2 /r2 = {r2_fanout_ratio:.2f}x > 1.0x multicast r2 1 \n")
                elif abs(r2_fanout_ratio - 1.0) < 0.1:
                    info(f" ⚠️ r2: r2 /r2 = {r2_fanout_ratio:.2f}x ≈ 1.0x unicast r2 N \n")
                else:
                    info(f" ⚠️ r2: r2 /r2 = {r2_fanout_ratio:.2f}x < 1.0x \n")
                r2_fanout_status = f"{r2_fanout_ratio:.2f}x"
            else:
                info(f" ❌ r2: r2 = 0 bytes r2 = {r2_eth0_rx_delta:,} bytes r2 \n")
                r2_fanout_status = "0.00x ( )"
        
        if r0_eth1_tx_delta > 0 and r1_eth0_rx_delta > 0:
            r0_r1_ratio = r1_eth0_rx_delta / r0_eth1_tx_delta
            if abs(r0_r1_ratio - 1.0) < 0.1:
                info(f" ✅ r0→r1 : r1 /r0 = {r0_r1_ratio:.2f}x ≈ 1.0x \n")
            else:
                info(f" ⚠️ r0→r1 : r1 /r0 = {r0_r1_ratio:.2f}x ≠ 1.0x \n")
        
        if r0_eth2_tx_delta > 0 and r2_eth0_rx_delta > 0:
            r0_r2_ratio = r2_eth0_rx_delta / r0_eth2_tx_delta
            if abs(r0_r2_ratio - 1.0) < 0.1:
                info(f" ✅ r0→r2 : r2 /r0 = {r0_r2_ratio:.2f}x ≈ 1.0x \n")
            else:
                info(f" ⚠️ r0→r2 : r2 /r0 = {r0_r2_ratio:.2f}x ≠ 1.0x \n")
        
        # ✅ Rolling r0 fan-out r0
        # r0_eth0_rx_delta r0_eth0_rx_mbps
        r0_fanout_ratio = None
        r0_fanout_status = "N/A"
        if strategy.lower() in ["rolling", "groot"]:
            # rolling r0
            r0_total_tx_delta = r0_eth1_tx_delta + r0_eth2_tx_delta
            if r0_eth0_rx_delta > 0 and r0_total_tx_delta > 0:
                r0_fanout_ratio = r0_total_tx_delta / r0_eth0_rx_delta
                info(f" 📊 r0 fan-out (Rolling): r0 /r0 = {r0_fanout_ratio:.2f}x \n")
                r0_fanout_status = f"{r0_fanout_ratio:.2f}x"
        
    except Exception as e:
        error(f" ⚠️ : {e}\n")
        r1_fanout_ratio = None
        r1_fanout_status = " "
        r2_fanout_ratio = None
        r2_fanout_status = " "
        r0_fanout_ratio = None
        r0_fanout_status = " "

    # ✅ decision_mode
    info(f"\n📊 decision_mode ...\n")
    try:
        # perf.csv
        base_only_count = 0
        base_enhanced_count = 0
        user_subscription_stats = {}  # {user_id: "base" or "base+enhanced"}
        
        for i in range(1, num_subscribers + 1):
            perf_csv = os.path.join(log_path, f"client_h{i}_perf.csv")
            if os.path.exists(perf_csv):
                try:
                    # CSV subscription_type
                    with open(perf_csv, 'r') as f:
                        lines = f.readlines()
                        if len(lines) > 1:
                            # subscription_type
                            header = lines[0].strip().split(',')
                            try:
                                subscription_type_idx = header.index('subscription_type')
                                last_lines = lines[-10:] if len(lines) > 10 else lines[1:]
                                subscription_types = []
                                for line in last_lines:
                                    parts = line.strip().split(',')
                                    if len(parts) > subscription_type_idx:
                                        subscription_types.append(parts[subscription_type_idx])
                                
                                # 'base'/'base+enhanced' 'B2'/'B2+E2'/'B1+E1'
                                if subscription_types:
                                    # base only enhanced
                                    base_count = sum(1 for st in subscription_types 
                                                   if st.lower() == 'base' or 
                                                   (st and '+' not in st and st.upper().startswith('B')))
                                    # base+enhanced enhanced
                                    base_enh_count = sum(1 for st in subscription_types 
                                                       if st.lower() == 'base+enhanced' or 
                                                       (st and '+' in st and 'E' in st.upper()))
                                    
                                    if base_enh_count > base_count:
                                        user_subscription_stats[i] = "base+enhanced"
                                        base_enhanced_count += 1
                                    else:
                                        user_subscription_stats[i] = "base"
                                        base_only_count += 1
                                else:
                                    # subscription_type selected_layer
                                    selected_layer_idx = header.index('selected_layer')
                                    last_decision = int(last_lines[-1].strip().split(',')[selected_layer_idx]) if last_lines else 0
                                    if last_decision == 1:
                                        user_subscription_stats[i] = "base+enhanced"
                                        base_enhanced_count += 1
                                    else:
                                        user_subscription_stats[i] = "base"
                                        base_only_count += 1
                            except ValueError:
                                # subscription_type selected_layer
                                selected_layer_idx = header.index('selected_layer')
                                last_line = lines[-1] if len(lines) > 1 else None
                                if last_line:
                                    parts = last_line.strip().split(',')
                                    if len(parts) > selected_layer_idx:
                                        last_decision = int(parts[selected_layer_idx])
                                        if last_decision == 1:
                                            user_subscription_stats[i] = "base+enhanced"
                                            base_enhanced_count += 1
                                        else:
                                            user_subscription_stats[i] = "base"
                                            base_only_count += 1
                except Exception as e:
                    info(f" ⚠️ {i} perf.csv : {e}\n")
        
        # decision_mode_summary.txt
        summary_file = os.path.join(log_path, "decision_mode_summary.txt")
        strategy_display = {
            "md2g": "MD2G",
            "rolling": "ROLLING",
            "heuristic": "HEURISTIC",
            "clustering": "CLUSTERING",
            "groot": "GROOT"
        }.get(strategy.lower(), strategy.upper())
        
        decision_mode_desc = {
            "md2g": "PPO ",
            "rolling": "SC-DDQN ",
            "heuristic": " (Joint Optimization)",
            "clustering": " (Predictive Clustering)",
            "groot": "GROOT view/distance LOD "
        }.get(strategy.lower(), " ")
        
        decision_method_desc = {
            "md2g": "✅ PPO \n ",
            "rolling": "✅ SC-DDQN \n Q r1/r2 ",
            "heuristic": "✅ \n TwoStageHeuristic (Zhang et al., TCOM 2021)\n ",
            "clustering": "✅ QoE \n PredictiveClustering (Perfecto et al., TCOM 2020)\n FoV ",
            "groot": "✅ strategies/groot_controller.py available GROOT \n / MoQ "
        }.get(strategy.lower(), " ")
        
        with open(summary_file, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write(f"📊 {strategy_display} Controller \n")
            f.write("=" * 60 + "\n")
            f.write(f" : {decision_mode_desc}\n")
            f.write("\n")
            f.write("📈 :\n")
            f.write(f" : {num_subscribers}\n")
            f.write(f" ✅ Base \n")
            f.write(f" - Base : {base_only_count} ({base_only_count*100//num_subscribers if num_subscribers > 0 else 0}%) - Base\n")
            f.write(f" - Base+Enhanced : {base_enhanced_count} ({base_enhanced_count*100//num_subscribers if num_subscribers > 0 else 0}%) - Base Enhanced \n")
            f.write("\n")
            f.write("📡 :\n")
            f.write(f"   r0→r1 (r0-eth1 TX): {initial_traffic.get('r0_eth1_tx', 0):,} bytes\n")
            f.write(f"   r0→r2 (r0-eth2 TX): {initial_traffic.get('r0_eth2_tx', 0):,} bytes\n")
            f.write(f" r1 r0 (r1-eth0 RX): {initial_traffic.get('r1_eth0_rx', 0):,} bytes\n")
            f.write(f" r1 (r1-eth1 TX): {initial_traffic.get('r1_eth1_tx', 0):,} bytes\n")
            f.write(f" r2 r0 (r2-eth0 RX): {initial_traffic.get('r2_eth0_rx', 0):,} bytes\n")
            f.write(f" r2 (r2-eth1 TX): {initial_traffic.get('r2_eth1_tx', 0):,} bytes\n")
            f.write("\n")
            f.write("📡 Relay / {duration} :\n".format(duration=duration))
            # relay / try
            f.write(f" r0 (r0-eth0 RX): {r0_eth0_rx_mbps:.2f} Mbps\n")
            f.write(f" r0 (r0-eth1 TX): {r0_eth1_tx_mbps:.2f} Mbps\n")
            f.write(f" r0 (r0-eth2 TX): {r0_eth2_tx_mbps:.2f} Mbps\n")
            f.write(f" r0 : {r0_total_tx_mbps:.2f} Mbps\n")
            f.write(f" r1 (r1-eth0 RX): {r1_eth0_rx_mbps:.2f} Mbps\n")
            f.write(f" r1 (r1-eth1 TX): {r1_eth1_tx_mbps:.2f} Mbps\n")
            f.write(f" r2 (r2-eth0 RX): {r2_eth0_rx_mbps:.2f} Mbps\n")
            f.write(f" r2 (r2-eth1 TX): {r2_eth1_tx_mbps:.2f} Mbps\n")
            f.write("\n")
            f.write("📡 Relay Fan-out :\n")
            if strategy.lower() in ["rolling", "groot"]:
                # Rolling/PCC-DASH r0
                f.write(f"   r0 Fan-out: {r0_fanout_status}\n")
                f.write(f" : r0 / r0 = (r0-eth1 TX + r0-eth2 TX) / r0-eth0 RX\n")
                f.write(f" : Rolling r1/r2 \n")
            else:
                # MD2G/Heuristic/Clustering r1/r2
                if r1_sub_count > 0:
                    f.write(f"   r1 Fan-out: {r1_fanout_status}\n")
                    f.write(f" : r1 / r1 = r1-eth1 TX / r1-eth0 RX\n")
                    f.write(f" : r1 r0 {r1_sub_count} \n")
                if r2_sub_count > 0:
                    f.write(f"   r2 Fan-out: {r2_fanout_status}\n")
                    f.write(f" : r2 / r2 = r2-eth1 TX / r2-eth0 RX\n")
                    f.write(f" : r2 r0 {r2_sub_count} \n")
            f.write("\n")
            f.write(f"🔍 {decision_mode_desc.split('(')[0].strip()}:\n")
            f.write(f"   {decision_method_desc}\n")
            f.write("=" * 60 + "\n")
        
        info(f" ✅ decision_mode_summary.txt : {summary_file}\n")
        
        # controller
        controller_log_files = []
        if strategy in ["md2g", "rolling", "heuristic", "clustering", "groot"]:
            if r1_sub_count > 0:
                r1_controller_log = f"/tmp/{TMP_PREFIX}r1_controller.log"
                if os.path.exists(r1_controller_log):
                    dst_r1_log = os.path.join(log_path, "controller_decision_mode.log")
                    try:
                        shutil.copy2(r1_controller_log, dst_r1_log)
                        controller_log_files.append(dst_r1_log)
                        info(f" ✅ r1 controller : {dst_r1_log}\n")
                    except Exception as e:
                        info(f" ⚠️ r1 controller : {e}\n")
            
            if r2_sub_count > 0:
                r2_controller_log = f"/tmp/{TMP_PREFIX}r2_controller.log"
                if os.path.exists(r2_controller_log):
                    dst_log = os.path.join(log_path, "controller_decision_mode.log")
                    try:
                        with open(dst_log, 'a') as f:
                            f.write(f"\n{'='*60}\n")
                            f.write(f"r2 Controller :\n")
                            f.write(f"{'='*60}\n")
                            with open(r2_controller_log, 'r') as src:
                                f.write(src.read())
                        info(f" ✅ r2 controller : {dst_log}\n")
                    except Exception as e:
                        info(f" ⚠️ r2 controller : {e}\n")
        
        if not controller_log_files:
            info(f" ⚠️ controller \n")
            
    except Exception as e:
        error(f" ⚠️ decision_mode : {e}\n")
        import traceback
        traceback.print_exc()

    info("-" * 60 + "\n")
    
    info("\n" + "="*80 + "\n")
    info("🔍 \n")
    info("="*80 + "\n\n")
    
    try:
        diagnosis_result = diagnose_zero_rx_clients(net, num_subscribers, log_path, r0, r1, r2, TMP_PREFIX)
        
        if diagnosis_result and diagnosis_result['total_zero']:
            info("\n" + "="*80 + "\n")
            info(" (B1/B2/B3)\n")
            info("="*80 + "\n\n")
            zero_ids = diagnosis_result['total_zero']
            check_ids = zero_ids[:3] + zero_ids[-3:] if len(zero_ids) > 6 else zero_ids
            perform_hard_checks(net, num_subscribers, r0, r1, r2, check_ids)
        
        info("\n" + "="*80 + "\n")
        info("📊 \n")
        info("="*80 + "\n\n")
        
        client_rx_stats = []
        for i in range(1, num_subscribers + 1):
            perf_csv = os.path.join(log_path, f"client_h{i}_perf.csv")
            if os.path.exists(perf_csv):
                try:
                    import pandas as pd
                    df = pd.read_csv(perf_csv)
                    if len(df) > 0:
                        max_rx = df['rx_bytes'].max()
                        client_rx_stats.append({'id': i, 'rx': max_rx})
                except:
                    pass
        
        if client_rx_stats:
            valid_clients = [s for s in client_rx_stats if s['rx'] > 0]
            if len(valid_clients) >= 20:
                early_avg = sum(s['rx'] for s in valid_clients[:10]) / 10
                late_avg = sum(s['rx'] for s in valid_clients[-10:]) / 10
                info(f" 10 : {early_avg:,.0f} bytes ({early_avg/1024/1024:.2f} MB)\n")
                info(f" 10 : {late_avg:,.0f} bytes ({late_avg/1024/1024:.2f} MB)\n")
                if late_avg > early_avg * 1.2:
                    info(f"⚠️ 10 10 {late_avg/early_avg:.2f}x \n")
                    info(f" ' / / ' \n")
                    info(f" \n")
                    info(f" 'h1/h2/h3/h6/h7/h8 ' 0 rx_bytes \n\n")
                    info(f"💡 D1 \n\n")
    except Exception as e:
        error(f"❌ : {e}\n")
        import traceback
        traceback.print_exc()

    # CELL_VALIDITY hard gate (command40 §11)
    leaf_egress_delta = int(r1_eth1_tx_delta or 0) + int(r2_eth1_tx_delta or 0)
    # Threshold: allow warmup but require sustained payload (~50KB aggregate egress)
    egress_thresh = max(50_000, int(0.05 * 1e6 / 8 * max(duration, 1) * 0.01))
    cell_valid, validity_payload = compute_and_write_cell_validity(
        log_path,
        strategy=strategy,
        num_subscribers=num_subscribers,
        registered_publishers=registered_publishers,
        expected_publishers=expected_publishers,
        subscriber_pids=subscriber_pids,
        leaf_egress_bytes=leaf_egress_delta,
        leaf_egress_threshold=egress_thresh,
    )
    copy_cell_tmp_logs(log_path, TMP_PREFIX)

    if cell_valid:
        info("✅ CELL_VALIDITY PASS — experiment complete\n")
    else:
        error(f"❌ CELL_VALIDITY FAIL: {validity_payload.get('failure_reasons')}\n")
        error("❌ experiment INVALID — not reporting success\n")
    
    # Interactive CLI only when explicitly requested
    if str(os.environ.get("SIGCOMM_INTERACTIVE_CLI", "")).strip() == "1":
        info("*** Mininet CLI ( 'exit' ) ***\n")
        CLI(net)
    
    # Cell-scoped cleanup (never global moq kill / never ToN)
    cleanup_all_processes(tmp_prefix=TMP_PREFIX, recorded_pids=CELL_RECORDED_PIDS, log_path=log_path)
    info(" Mininet (cell-scoped; never mn -c)...\n")
    cell_scoped_exit_cleanup(log_path, num_subscribers, TMP_PREFIX, net=net)
    
    if cell_valid:
        info("✅ (valid)\n")
        return 0
    info("❌ (INVALID)\n")
    raise SystemExit(2)

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='MoQ Cluster dispatch_strategy ')
    parser.add_argument('--clients', type=int, default=10, help=' 10 ')
    parser.add_argument('--strategy', type=str, default='md2g', 
                       choices=['md2g', 'rolling', 'heuristic', 'clustering', 'groot'],
                       help=' md2g ')
    parser.add_argument('--network_type', type=str, default='4g',
                       choices=['wifi', '4g', '5g', 'fiber_optic', 'default_mix', 'wifi_dominant', '5g_dominant'],
                       help=' 4g ')
    parser.add_argument('--log_path', type=str, default=None, help=' ')
    parser.add_argument('--duration', type=int, default=120, help=' 120 ')
    parser.add_argument('--interval', type=float, default=1.0, help=' 1.0 ')
    parser.add_argument('--model_path', type=str, default=None, help=' rolling md2g ')
    parser.add_argument('--device_map_path', type=str, default=None,
                       help=' client_id->device_type JSON {"1":"quest2_72"} ')
    
    args = parser.parse_args()
    # command55: refuse Rolling/GROOT on MoQ shared-delivery path unless explicitly overridden
    if str(args.strategy).lower() in ("rolling", "groot") and os.environ.get(
        "SIGCOMM_ALLOW_MOQ_SHARED_BASELINES", ""
    ).strip() not in ("1", "true", "TRUE"):
        error(
            "REFUSING MoQ launch for rolling/groot (command55 INVALID_SHARED_DELIVERY). "
            "Use run_authentic_unicast_baseline_cell.py\n"
        )
        raise SystemExit(55)

    # command110: scientific bitrate fail-closed + provenance before launch
    _sci = any(
        os.environ.get(k, "").strip().lower() in ("1", "true", "yes", "on")
        for k in ("TON_BITRATE_FAIL_CLOSED", "TON_COMMAND108_DEV", "TON_SCIENTIFIC_MODE")
    )
    if _sci:
        import hashlib as _hashlib
        import json as _json
        _content = os.environ.get("TON_CONTENT_ID", "").strip()
        _map_path = os.environ.get("TON_CONTENT_REP_BITRATES_JSON", "").strip()
        _rates = {}
        _src = "env"
        for _rid in range(1, 10):
            _ev = os.environ.get(f"REP{_rid}_BITRATE_MBPS")
            if _ev not in (None, ""):
                _rates[_rid] = float(_ev)
        if len(_rates) < 9 and _map_path and _content and os.path.isfile(_map_path):
            try:
                _blob = _json.load(open(_map_path, "r"))
                for _rid_s, _mbps in (_blob.get(_content) or {}).items():
                    _rates[int(_rid_s)] = float(_mbps)
                _src = "env+map" if any(os.environ.get(f"REP{i}_BITRATE_MBPS") for i in range(1, 10)) else "map"
            except Exception as _e:
                error(f"BITRATE_FAIL_CLOSED: cannot read map {_map_path}: {_e}\n")
                raise SystemExit(110)
        if len(_rates) < 9:
            error(
                f"BITRATE_FAIL_CLOSED: need Rep1–9 bitrates for content={_content!r}; "
                f"got {sorted(_rates)} (refusing hardcoded RB fallback)\n"
            )
            raise SystemExit(110)
        _map_sha = None
        if _map_path and os.path.isfile(_map_path):
            _h = _hashlib.sha256()
            with open(_map_path, "rb") as _f:
                for _ch in iter(lambda: _f.read(1 << 20), b""):
                    _h.update(_ch)
            _map_sha = _h.hexdigest()
        _prov = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "content_id": _content,
            "bitrate_source": _src,
            "bitrate_map_path": _map_path or None,
            "bitrate_map_sha256": _map_sha,
            "rep_bitrate_mbps": {str(k): v for k, v in sorted(_rates.items())},
            "TON_BITRATE_FAIL_CLOSED": True,
        }
        if args.log_path:
            try:
                os.makedirs(args.log_path, exist_ok=True)
                with open(os.path.join(args.log_path, "BITRATE_PROVENANCE.json"), "w") as _pf:
                    _json.dump(_prov, _pf, indent=2)
                    _pf.write("\n")
            except Exception as _e:
                error(f"BITRATE_FAIL_CLOSED: cannot write BITRATE_PROVENANCE.json: {_e}\n")
                raise SystemExit(110)
        info(f"🔒 BITRATE_FAIL_CLOSED content={_content} src={_src} map_sha={(_map_sha or '')[:16]}\n")

    
    info(f"📝 :\n")
    info(f" : {args.clients}\n")
    info(f" : {args.strategy}\n")
    info(f" : {args.network_type}\n")
    info(f" : {args.duration} \n")
    info(f" : {args.interval} \n")
    if args.log_path:
        info(f" : {args.log_path}\n")
    if args.model_path:
        info(f" : {args.model_path}\n")
    if args.device_map_path:
        info(f" : {args.device_map_path}\n")
    
    rc = run_moq_experiment(
        num_subscribers=args.clients,
        strategy=args.strategy,
        network_type=args.network_type,
        log_path=args.log_path,
        duration=args.duration,
        interval=args.interval,
        model_path=args.model_path,
        device_map_path=args.device_map_path
    )
    # Hard gates raise SystemExit(2); normal pass returns 0
    sys.exit(0 if rc in (0, None) else int(rc))
       