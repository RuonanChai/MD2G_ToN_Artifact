#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cell-scoped Mininet topology cleanup (command123 A5).

Never routine ``mn -c``. Never touch foreign-workspace / unrelated Mininet.
Deletes only leftover interfaces/bridges of the MD2G tree topology when no
foreign owner is live.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Iterable

FORBIDDEN_CMD_SUBSTR = (
    "/srv/other-workspace",
    "foreign-ioa",
    "foreign-gateway",
    "foreign-controller",
    "moq_cluster_Sigcomm26",
)

# Exact iface/bridge names created by moq_cluster_Sigcomm.py tree topology.
MD2G_BRIDGES = ("s1", "s2")
MD2G_CORE_IFACES = (
    "n0-eth0", "r0-eth0", "r0-eth1", "r0-eth2",
    "r1-eth0", "r1-eth1", "r2-eth0", "r2-eth1",
    "s1-eth0", "s2-eth0",
)


def ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run(cmd: list[str], timeout: int = 8) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def pgrep(pattern: str) -> list[dict]:
    try:
        r = _run(["pgrep", "-af", pattern])
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    rows = []
    for line in (r.stdout or "").splitlines():
        if "pgrep" in line:
            continue
        parts = line.strip().split(None, 1)
        if not parts:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        rows.append({"pid": pid, "cmd": parts[1] if len(parts) > 1 else ""})
    return rows


def foreign_mininet_live(
    *,
    exclude_pids: Iterable[int] | None = None,
    own_fingerprints: Iterable[str] | None = None,
) -> dict:
    """True if an unrelated Mininet/MoQ experiment owns the machine."""
    excl = {int(p) for p in (exclude_pids or [])}
    excl.add(os.getpid())
    try:
        excl.add(os.getppid())
    except Exception:
        pass
    fps = [f for f in (own_fingerprints or []) if f and len(str(f)) >= 8]
    hits = []
    for pat in ("moq_cluster", "mininet", "mnexec"):
        for row in pgrep(pat):
            if row["pid"] in excl:
                continue
            cmd = row.get("cmd") or ""
            if any(fp in cmd for fp in fps):
                continue
            if any(x in cmd for x in FORBIDDEN_CMD_SUBSTR):
                hits.append({**row, "class": "unrelated_forbidden"})
            elif "moq_cluster_Sigcomm.py" in cmd:
                hits.append({**row, "class": "other_scientific_cell"})
            elif pat == "mnexec" and "moq_cluster_Sigcomm.py" not in cmd and not any(fp in cmd for fp in fps):
                # leftover mnexec without our fingerprint may still be ours after a crash;
                # do not treat generic mininet python as foreign unless forbidden path.
                continue
    unrelated = [h for h in hits if h.get("class") == "unrelated_forbidden"]
    other = [h for h in hits if h.get("class") == "other_scientific_cell"]
    return {
        "unrelated_live": bool(unrelated),
        "other_scientific_live": bool(other),
        "hits": hits[:20],
        "safe_to_reclaim_md2g_ifaces": (not unrelated) and (not other),
    }


def md2g_host_ifaces(num_subscribers: int) -> list[str]:
    names = list(MD2G_CORE_IFACES)
    r1_n = int(num_subscribers) // 2
    r2_n = int(num_subscribers) - r1_n
    for i in range(1, r1_n + 1):
        names.append(f"h{i}-eth0")
        names.append(f"s1-eth{i}")
    for j in range(1, r2_n + 1):
        hid = r1_n + j
        names.append(f"h{hid}-eth0")
        names.append(f"s2-eth{j}")
    return names


def topology_key(num_subscribers: int, tmp_prefix: str | None = None) -> str:
    return f"md2g_tree_u{int(num_subscribers)}:{tmp_prefix or ''}"


def current_link_names() -> set[str]:
    names: set[str] = set()
    try:
        r = _run(["ip", "-o", "link", "show"])
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return names
    for line in (r.stdout or "").splitlines():
        # 2: s1-eth0@if3: <BROADCAST,...>
        parts = line.split(":", 2)
        if len(parts) < 2:
            continue
        name = parts[1].strip().split("@", 1)[0].strip()
        if name:
            names.add(name)
    return names


def current_ovs_bridges() -> set[str]:
    try:
        r = _run(["ovs-vsctl", "list-br"])
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()
    return {ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()}


def record_inventory(
    *,
    log_path: str | Path,
    num_subscribers: int,
    tmp_prefix: str,
) -> dict:
    ifaces = md2g_host_ifaces(num_subscribers)
    present_if = sorted(n for n in ifaces if n in current_link_names())
    present_br = sorted(b for b in MD2G_BRIDGES if b in current_ovs_bridges())
    inv = {
        "ts": ts(),
        "authority": "command123",
        "topology_key": topology_key(num_subscribers, tmp_prefix),
        "tmp_prefix": tmp_prefix,
        "num_subscribers": int(num_subscribers),
        "ifaces_declared": ifaces,
        "ifaces_present_at_record": present_if,
        "bridges_declared": list(MD2G_BRIDGES),
        "bridges_present_at_record": present_br,
        "never_mn_c": True,
    }
    p = Path(log_path) / "CELL_NETWORK_INVENTORY.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(inv, indent=2) + "\n")
    return inv


def _del_iface(name: str) -> dict:
    rec = {"name": name, "op": "ip_link_delete"}
    try:
        r = _run(["ip", "link", "delete", name])
        rec["rc"] = r.returncode
        rec["stderr"] = (r.stderr or "")[-200:]
    except Exception as exc:
        rec["error"] = str(exc)
    return rec


def _del_bridge(name: str) -> dict:
    rec = {"name": name, "op": "ovs_del_br"}
    try:
        r = _run(["ovs-vsctl", "--if-exists", "del-br", name])
        rec["rc"] = r.returncode
        rec["stderr"] = (r.stderr or "")[-200:]
    except Exception as exc:
        rec["error"] = str(exc)
    return rec


def cleanup_owned(
    inv: dict,
    *,
    reason: str,
    exclude_pids: Iterable[int] | None = None,
    own_fingerprints: Iterable[str] | None = None,
) -> dict:
    """Remove only MD2G tree ifaces/bridges from *inv* when no foreign owner is live."""
    fps = list(own_fingerprints or [])
    if inv.get("tmp_prefix"):
        fps.append(str(inv["tmp_prefix"]))
    foreign = foreign_mininet_live(exclude_pids=exclude_pids, own_fingerprints=fps)
    out = {
        "ts": ts(),
        "reason": reason,
        "topology_key": inv.get("topology_key"),
        "never_mn_c": True,
        "foreign": foreign,
        "deleted_ifaces": [],
        "deleted_bridges": [],
        "skipped": False,
    }
    if not foreign.get("safe_to_reclaim_md2g_ifaces"):
        out["skipped"] = True
        out["skip_why"] = "foreign_or_other_scientific_mininet_live"
        return out
    live = current_link_names()
    brs = current_ovs_bridges()
    for name in inv.get("ifaces_declared") or md2g_host_ifaces(int(inv.get("num_subscribers") or 20)):
        if name in live:
            out["deleted_ifaces"].append(_del_iface(name))
    for br in inv.get("bridges_declared") or list(MD2G_BRIDGES):
        if br in brs:
            out["deleted_bridges"].append(_del_bridge(br))
    return out


def assert_clear(inv: dict) -> dict:
    live = current_link_names()
    brs = current_ovs_bridges()
    stale_if = [n for n in (inv.get("ifaces_declared") or []) if n in live]
    stale_br = [b for b in (inv.get("bridges_declared") or list(MD2G_BRIDGES)) if b in brs]
    return {
        "ts": ts(),
        "topology_key": inv.get("topology_key"),
        "stale_ifaces": stale_if,
        "stale_bridges": stale_br,
        "clear": not stale_if and not stale_br,
    }
