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

"""Consult COMMAND153_KNOWN_FAILURES_AND_FIXES before any repair. One exact-key rerun max per decision."""
import json
import re
import sys
from pathlib import Path

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON / "scripts"))
from command147_io import dump_dual, ts  # noqa: E402
from command153_ledger import load_ledger, match_lesson  # noqa: E402

ART = TON / "artifacts" / "command151_24cell_post_rb"
QUEUE = REPO / "state" / "COMMAND151_24CELL_QUEUE.json"
TRACKS = ["b0", "db1", "db2", "e1", "e2"]
FAIL_QUEUES = [
    ("COMMAND151_24CELL_QUEUE.json", TON / "artifacts" / "command151_24cell_post_rb"),
    ("COMMAND148_CANARY120_QUEUE.json", TON / "artifacts" / "command148_canary120_rbv1"),
    ("COMMAND148_MAINDEV_QUEUE.json", TON / "artifacts" / "command148_maindev"),
    ("COMMAND153_SCALING_QUEUE.json", TON / "artifacts" / "command153_scaling"),
    ("COMMAND153_CROSS_STACK_DASH_QUEUE.json", TON / "artifacts" / "command153_cross_stack_dash"),
    ("COMMAND153_LOOT_QUEUE.json", TON / "artifacts" / "command153_loot_holdout"),
]


def _gst_retry_stripped_anon(cell: Path) -> bool:
    saw_retry = False
    stripped = False
    for p in cell.glob("client_h*_gst_*.log"):
        txt = p.read_text(errors="ignore")
        if "RETRY" in txt:
            saw_retry = True
        if re.search(r'path:\s*"/"\s*,', txt):
            stripped = True
    return saw_retry and stripped


def _gst_retry_kept_anon(cell: Path) -> bool:
    kept = False
    stripped = False
    for p in cell.glob("client_h*_gst_*.log"):
        txt = p.read_text(errors="ignore")
        if "RETRY" not in txt:
            continue
        if 'path: "/anon/"' in txt or "path: \"/anon/\"" in txt:
            kept = True
        if ('path: "/"' in txt or 'path: \"/\"' in txt) and "/anon/" not in Path(txt).name:
            # path "/" on a retry line
            for ln in txt.splitlines():
                if "RETRY" in ln:
                    continue
                if 'path: "/"' in ln and "/anon/" not in ln:
                    stripped = True
    return kept and not stripped


def _last_dumps(cell: Path) -> list[dict]:
    out = []
    for i in range(1, 8):
        rp = cell / f"client_h{i}_COMPONENT_RECEIPT.jsonl"
        if not rp.is_file():
            continue
        rows = [json.loads(x) for x in rp.read_text(errors="ignore").splitlines() if x.strip()]
        if not rows:
            continue
        last = rows[-1]
        dumps = last.get("dump_bytes") or {}
        out.append(
            {
                "host": i,
                "decoded": last.get("decoded_state"),
                "dumps": {t: int(dumps.get(t) or 0) for t in TRACKS},
            }
        )
    return out


def _gst_has_retry(cell: Path) -> bool:
    for p in cell.glob("client_h*_gst_*.log"):
        if "RETRY" in p.read_text(errors="ignore"):
            return True
    return False


def _subscribe_started_no_retry(cell: Path) -> bool:
    saw_sub = False
    for p in cell.glob("client_h*_gst_*.log"):
        txt = p.read_text(errors="ignore")
        if "RETRY" in txt:
            return False
        if "subscribe started" in txt:
            saw_sub = True
    return saw_sub


def _open_b0_once(cell: Path) -> bool:
    n = 0
    for p in cell.glob("client_h*_dispatch_stdout.log"):
        n = max(n, p.read_text(errors="ignore").count("OPEN b0"))
    return n == 1


def classify_cell(key: str, cell: Path) -> dict:
    ledger = load_ledger()
    dumps = _last_dumps(cell)
    stripped = _gst_retry_stripped_anon(cell)
    retry = _gst_has_retry(cell)
    b0_zero_incr = any(
        (r["dumps"].get("b0") or 0) <= 64
        and r.get("decoded") in (None, "", "null")
        and any(int(r["dumps"].get(t) or 0) > 64 for t in ("db1", "db2", "e1", "e2"))
        for r in dumps
    )
    reopen = False
    disp = cell / "client_h2_dispatch_stdout.log"
    if disp.is_file():
        n_open_b0 = disp.read_text(errors="ignore").count("OPEN b0")
        reopen = n_open_b0 >= 2
    if stripped and b0_zero_incr:
        L = match_lesson("E011_S2_B0_RETRY_STRIPPED_ANON") or {}
        return {
            "class": "A_RUNTIME_INSTRUMENTATION_DEFECT",
            "failure_id": "E011_S2_B0_RETRY_STRIPPED_ANON",
            "reuse_certified_fix": True,
            "repair": L.get("repair"),
            "preserve_as": f"{key}_attempt1_decode_none_b0_retry",
            "ledger_consulted": True,
            "n_lessons": len(ledger.get("lessons") or []),
        }
    if b0_zero_incr and retry and not stripped:
        L = match_lesson("E013_S3_RETRY_KILLS_LIVE_SUBSCRIBE") or {}
        return {
            "class": "A_RUNTIME_INSTRUMENTATION_DEFECT",
            "failure_id": "E013_S3_RETRY_KILLS_LIVE_SUBSCRIBE",
            "reuse_certified_fix": True,
            "repair": L.get("repair"),
            "preserve_as": f"{key}_attempt1_decode_none_live_retry_kill",
            "reopen_wrapper": reopen,
            "ledger_consulted": True,
            "not_e011": True,
            "not_class_B": "incrementals arrived; original 147 same key decoded",
            "not_class_C": "scripted pattern, not learned MD2G",
        }
    if b0_zero_incr and (not retry) and _subscribe_started_no_retry(cell):
        L = match_lesson("E014_S3_CONCURRENT_SUBSCRIBE_B0_DUMP_ZERO") or {}
        return {
            "class": "A_RUNTIME_INSTRUMENTATION_DEFECT",
            "failure_id": "E014_S3_CONCURRENT_SUBSCRIBE_B0_DUMP_ZERO",
            "reuse_certified_fix": True,
            "repair": L.get("repair"),
            "preserve_as": f"{key}_e014_b0_burst_miss",
            "open_b0_once": _open_b0_once(cell),
            "ledger_consulted": True,
            "not_e011": True,
            "not_e013": True,
            "not_class_B": "incrementals arrived; peer users decoded; victim host not stable",
            "not_class_C": "scripted pattern, not learned MD2G",
        }
    audit_p = cell / "CELL_AUDIT.json"
    reasons = []
    if audit_p.is_file():
        try:
            body = json.loads(audit_p.read_text())
            reasons = list((body.get("audit") or body).get("reasons") or [])
        except Exception:
            reasons = []
    if any("Rq not frozen Q" in str(x) for x in reasons):
        L = match_lesson("E015_RQ_AUDIT_TARGET_FALLBACK") or {}
        return {
            "class": "A_RUNTIME_INSTRUMENTATION_DEFECT",
            "failure_id": "E015_RQ_AUDIT_TARGET_FALLBACK",
            "reuse_certified_fix": True,
            "repair": L.get("repair"),
            "preserve_as": f"{key}_e015_rq_target_fallback",
            "ledger_consulted": True,
            "not_class_B": "Rq=0 with decoded=None is consistent; target Q must not be expected",
            "not_class_C": "audit compared target_state Q, not a controller change",
        }
    stdout = cell / "cell_stdout.log"
    txt = stdout.read_text(errors="ignore") if stdout.is_file() else ""
    missing_validity = not (cell / "CELL_VALIDITY.json").is_file()
    audit_gap = any("cluster_CELL_VALIDITY.valid!=true" in str(x) for x in reasons)
    waiting_assert = "AssertionError" in txt and "self.shell and not self.waiting" in txt
    ran_window = "  120  " in txt or "[COMPONENT-PLAN]" in txt
    if (missing_validity or audit_gap) and waiting_assert and ran_window:
        L = match_lesson("E020_TEARDOWN_R0_CMD_WAITING_SKIPS_CELL_VALIDITY") or {}
        return {
            "class": "A_RUNTIME_INSTRUMENTATION_DEFECT",
            "failure_id": "E020_TEARDOWN_R0_CMD_WAITING_SKIPS_CELL_VALIDITY",
            "reuse_certified_fix": True,
            "repair": L.get("repair"),
            "preserve_as": f"{key}_e020_teardown_waiting_no_cell_validity",
            "ledger_consulted": True,
            "not_class_B": "120s nested window ran; dumps/decoded present; validity file skipped after r0.cmd assert",
            "not_class_C": "teardown race is not a controller quality outcome",
        }
    if str(key).startswith("c153dash_"):
        n_press = 0
        sp = cell / "PHYSICAL_PRESSURE_TIMESERIES.jsonl"
        if sp.is_file():
            try:
                n_press = sum(1 for ln in sp.read_text().splitlines() if ln.strip())
            except Exception:
                n_press = 0
        if n_press < 2:
            L = match_lesson("E021_DASH_H2_MISSING_COMMAND151_PRESSURE") or {}
            return {
                "class": "A_RUNTIME_INSTRUMENTATION_DEFECT",
                "failure_id": "E021_DASH_H2_MISSING_COMMAND151_PRESSURE",
                "reuse_certified_fix": True,
                "repair": L.get("repair"),
                "preserve_as": f"{key}_e021_missing_dash_pressure",
                "ledger_consulted": True,
                "n_press": n_press,
                "not_class_B": "unicast authenticity is separate from missing r0-eth1 pressure sidecar",
                "not_class_C": "DASH native strategy unchanged; instrumentation only",
            }
    return {
        "class": "UNCLASSIFIED_PRESERVE",
        "failure_id": None,
        "reuse_certified_fix": False,
        "ledger_consulted": True,
        "dumps": dumps,
    }


def _find_failed() -> tuple[str, Path | None]:
    for qname, art in FAIL_QUEUES:
        qp = REPO / "state" / qname
        if not qp.is_file():
            continue
        try:
            q = json.loads(qp.read_text())
        except Exception:
            continue
        failed = q.get("failed") or {}
        key = str(failed.get("key") or "")
        if not key:
            continue
        cell = art / key
        if not cell.is_dir() and art.is_dir():
            matches = sorted(art.glob(f"{key}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                cell = matches[0]
        return key, cell
    return "", None


def _already_consumed_exact_key(key: str, failure_id: str | None) -> bool:
    """Do not re-AUTHORIZE the same key+failure_id after CONSUMED (no infinite E021 loops)."""
    p = REPO / "state" / "COMMAND153_EXACT_KEY_RERUN.json"
    if not key or not p.is_file():
        return False
    try:
        prev = json.loads(p.read_text())
    except Exception:
        return False
    if str(prev.get("status") or "").upper() != "CONSUMED":
        return False
    if str(prev.get("affected_key") or "") != key:
        return False
    prev_fid = str(prev.get("failure_id") or "")
    new_fid = str(failure_id or "")
    if prev_fid and new_fid and prev_fid != new_fid:
        return False
    return True


def main() -> int:
    load_ledger()
    key, cell = _find_failed()
    if not key:
        print(json.dumps({"pass": True, "reason": "no_failed_key"}))
        return 0
    rec = classify_cell(key, cell if cell is not None else ART / key)
    rec["ts"] = ts()
    rec["key"] = key
    dump_dual(f"COMMAND153_{key}_CLASSIFICATION.json", rec)
    if rec.get("class") == "A_RUNTIME_INSTRUMENTATION_DEFECT" and rec.get("reuse_certified_fix"):
        if _already_consumed_exact_key(key, rec.get("failure_id")):
            print(
                json.dumps(
                    {
                        "pass": True,
                        "rerun": False,
                        "reason": "exact_key_already_consumed",
                        "key": key,
                        "failure_id": rec.get("failure_id"),
                    }
                )
            )
            return 0
        dump_dual(
            "COMMAND153_EXACT_KEY_RERUN.json",
            {
                "ts": ts(),
                "token": "COMMAND153_EXACT_KEY_RERUN",
                "status": "AUTHORIZED",
                "n_applied": 0,
                "affected_key": key,
                "class": "A",
                "failure_id": rec.get("failure_id"),
                "preserve_as": rec.get("preserve_as"),
                "ledger_consulted": True,
                "do_not_relabel_as_physical_or_policy": True,
            },
        )
        print(json.dumps({"pass": True, "rerun": True, **{k: rec[k] for k in ("key", "failure_id", "class")}}))
        return 0
    print(json.dumps({"pass": True, "rerun": False, **rec}, default=str)[:2000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
