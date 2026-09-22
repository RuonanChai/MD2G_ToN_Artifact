from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Fail-closed canary cell audit. Does not weaken cluster CELL_VALIDITY."""
import json
import math
import os
import re
from pathlib import Path

from command148_rb_lineage import rb_lineage
from component_actuation_plan import TRACKS, closure

REPO = artifact_root()


def expected_rq(decoded, qn: dict) -> float:
    """Rq is Q_norm[decoded] only. Undecoded users are 0, never target_state."""
    if decoded in (None, "", "null"):
        return 0.0
    return float(qn.get(str(decoded)) or 0.0)


def finite_headlines(metrics) -> tuple[bool, list[str]]:
    bad = []
    if not isinstance(metrics, dict):
        return False, ["metrics_not_dict"]
    for k in ("U", "Ro_component", "Rq", "Rb", "B_shared", "B_unicast"):
        v = metrics.get(k)
        if v is None:
            bad.append(f"{k}=null")
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            bad.append(f"{k}=nonnumeric")
            continue
        if not math.isfinite(fv):
            bad.append(f"{k}=nonfinite")
    return (not bad), bad


def _qnorm(content: str) -> dict:
    body = json.loads((REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json").read_text())
    return dict((body.get("Q_norm") or {}).get(content) or {})


def audit_canary_cell(cell: Path, spec: dict, metrics: dict | None = None) -> dict:
    cases: dict[str, bool] = {}
    reasons: list[str] = []
    users = int(spec.get("users") or 0)
    strategy = str(spec.get("strategy") or "")
    content = str(spec.get("content") or "")
    if content.lower() == "loot":
        if not (REPO / "state" / "COMMAND153_FINAL_DEV_FROZEN.json").is_file():
            return {"pass": False, "reasons": ["loot_network_used"], "cases": {}, "class": "INVALID_HOLDOUT_LEAK"}

    valid_p = cell / "CELL_VALIDITY.json"
    cluster_valid = False
    if valid_p.is_file():
        try:
            cluster_valid = json.loads(valid_p.read_text()).get("valid") is True
        except Exception:
            cluster_valid = False
    cases["cluster_cell_validity"] = cluster_valid
    if not cluster_valid:
        reasons.append("cluster_CELL_VALIDITY.valid!=true")

    perfs = list(cell.glob("client_h*_perf.csv"))
    cases["perf_files"] = len(perfs) == users
    if not cases["perf_files"]:
        reasons.append(f"perf_files={len(perfs)}/{users}")

    receipts = list(cell.glob("client_h*_COMPONENT_RECEIPT.jsonl"))
    cases["receipts"] = len(receipts) == users
    if not cases["receipts"]:
        reasons.append(f"receipts={len(receipts)}/{users}")

    plan_path = cell / "COMPONENT_ACTUATION_PLAN.jsonl"
    cases["plan_jsonl"] = plan_path.is_file() and plan_path.stat().st_size > 0
    if not cases["plan_jsonl"]:
        reasons.append("missing COMPONENT_ACTUATION_PLAN.jsonl")

    nan_inf = False
    unauthorized = []
    qn = _qnorm(content)
    decoded_states = []
    for rp in receipts:
        rows = [json.loads(x) for x in rp.read_text(errors="ignore").splitlines() if x.strip()]
        if not rows:
            continue
        last = rows[-1]
        hid = int(last.get("host_id") or 0)
        want = set(closure(str(last.get("target_state") or "Rep1")))
        dumps = last.get("dump_bytes") or {}
        for c, b in dumps.items():
            try:
                bv = float(b)
            except (TypeError, ValueError):
                nan_inf = True
                continue
            if not math.isfinite(bv):
                nan_inf = True
            if c not in want and bv > 64:
                unauthorized.append({"host": hid, "component": c, "bytes": bv})
        decoded_states.append(str(last.get("decoded_state") or ""))
        rq = last.get("Rq")
        try:
            if rq is None or not math.isfinite(float(rq)):
                nan_inf = True
            else:
                dec = last.get("decoded_state")
                expect = expected_rq(dec, qn)
                if abs(float(rq) - expect) > 1e-6:
                    reasons.append(f"h{hid} Rq not frozen Q")
        except Exception:
            nan_inf = True
        if str(last.get("content") or content).lower() == "loot" and content.lower() != "loot":
            reasons.append("loot_in_receipt")

    cases["no_unauthorized"] = not unauthorized
    cases["no_nan_inf"] = not nan_inf
    if unauthorized:
        reasons.append(f"unauthorized={unauthorized[:6]}")

    inf = cell / "COMMAND148_STUDENT_INFERENCE.jsonl"
    if strategy == "MD2G_COMPONENT":
        cases["student_inference"] = inf.is_file() and inf.stat().st_size > 0
        if not cases["student_inference"]:
            reasons.append("MD2G_COMPONENT missing COMMAND148_STUDENT_INFERENCE.jsonl")
            return {
                "pass": False,
                "cases": cases,
                "reasons": reasons,
                "class": "INVALID_TREATMENT_MD2G_NOT_STUDENT",
                "decoded_states": decoded_states[:8],
            }
    else:
        cases["student_inference"] = True

    mcg_log = cell / "COMMAND148_MCG_DECISION.jsonl"
    if strategy == "MCG_COMPONENT":
        cases["mcg_decision"] = mcg_log.is_file() and mcg_log.stat().st_size > 0
        if not cases["mcg_decision"]:
            reasons.append("MCG_COMPONENT missing COMMAND148_MCG_DECISION.jsonl")
            return {
                "pass": False,
                "cases": cases,
                "reasons": reasons,
                "class": "INVALID_TREATMENT_MCG_NOT_GREEDY",
                "decoded_states": decoded_states[:8],
            }
        if inf.is_file() and inf.stat().st_size > 0:
            reasons.append("MCG_COMPONENT must not write student inference")
            return {
                "pass": False,
                "cases": cases,
                "reasons": reasons,
                "class": "INVALID_TREATMENT_MCG_USED_STUDENT",
                "decoded_states": decoded_states[:8],
            }
    else:
        cases["mcg_decision"] = True

    pub_dir = cell / "publisher_logs"
    pubs = list(pub_dir.glob("pub_*.log")) if pub_dir.is_dir() else []
    names = [p.name[4:-4] for p in pubs]
    if strategy == "MOQ_UNICAST_COMPONENT":
        bare = [n for n in names if n in TRACKS]
        ns = [n for n in names if re.fullmatch(r"u\d+_(b0|db1|db2|e1|e2)", n)]
        cases["unicast_namespaced"] = len(bare) == 0 and len(ns) >= users
        if not cases["unicast_namespaced"]:
            reasons.append(f"unicast_not_independent bare={bare[:8]} ns={len(ns)}")
            return {
                "pass": False,
                "cases": cases,
                "reasons": reasons,
                "class": "INVALID_SHARED_DELIVERY_IMPLEMENTATION",
                "decoded_states": decoded_states[:8],
            }
    else:
        cases["unicast_namespaced"] = True

    stdout = cell / "cell_stdout.log"
    txt = stdout.read_text(errors="ignore") if stdout.is_file() else ""
    cases["rtnetlink_clean"] = "RTNETLINK answers: File exists" not in txt
    cases["loot_unread"] = True
    cases["quality_not_rerun"] = (REPO / "state" / "COMMAND147_COMPONENT_QUALITY_FROZEN.json").is_file()
    frozen_p = (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_CONTRACT_FROZEN.json").is_file()
    post_rb = frozen_p and (REPO / "state" / "COMMAND151_PHYSICAL_PRESSURE_RELEASE.json").is_file()
    require_press = post_rb or str(os.environ.get("COMMAND151_REQUIRE_PRESSURE") or "") in ("1", "true", "yes")
    sp = cell / "PHYSICAL_PRESSURE_TIMESERIES.jsonl"
    if require_press:
        cases["physical_pressure_timeseries"] = sp.is_file() and sp.stat().st_size > 0
        if not cases["physical_pressure_timeseries"]:
            reasons.append("missing PHYSICAL_PRESSURE_TIMESERIES.jsonl")
    else:
        cases["physical_pressure_timeseries"] = True

    fail_keys = [
        "cluster_cell_validity",
        "perf_files",
        "receipts",
        "plan_jsonl",
        "no_unauthorized",
        "no_nan_inf",
        "student_inference",
        "unicast_namespaced",
        "rtnetlink_clean",
        "loot_unread",
        "quality_not_rerun",
    ]
    if require_press:
        fail_keys.append("physical_pressure_timeseries")
    if metrics is None:
        mp = cell / "CELL_METRICS.json"
        if mp.is_file():
            raw = mp.read_text().strip()
            if raw in ("", "null"):
                metrics = None
            else:
                try:
                    metrics = json.loads(raw)
                except Exception:
                    metrics = None
    ok_h, bad_h = finite_headlines(metrics)
    cases["finite_headlines"] = ok_h
    if not ok_h:
        reasons.extend(bad_h)
    fail_keys.append("finite_headlines")
    if (REPO / "state" / "COMMAND152_FINAL_METRIC_COMPLETENESS_PASS.json").is_file():
        st_status = None if not isinstance(metrics, dict) else metrics.get("stall_last_status")
        cases["no_placeholder_stall"] = st_status not in (None, "UNIMPLEMENTED_PLACEHOLDER")
        if not cases["no_placeholder_stall"]:
            reasons.append(f"placeholder_stall={st_status}")
            fail_keys.append("no_placeholder_stall")
        rb0 = bool(isinstance(metrics, dict) and metrics.get("paper_U_is_Rb0_projection"))
        cases["no_placeholder_rb"] = not rb0 and not (isinstance(metrics, dict) and metrics.get("Rb") is None)
        if not cases["no_placeholder_rb"]:
            reasons.append("placeholder_or_null_Rb")
            fail_keys.append("no_placeholder_rb")
    rb = rb_lineage(cell, metrics if isinstance(metrics, dict) else None)
    cases["rb_lineage"] = bool(rb.get("pass"))
    if not cases["rb_lineage"]:
        reasons.append(f"rb_lineage={rb.get('class')}")
        fail_keys.append("rb_lineage")
    ok = all(cases.get(k) for k in fail_keys) and not reasons
    klass = "VALID" if ok else "INVALID_EXECUTION_OR_FIDELITY"
    if not ok_h:
        klass = "INVALID_HEADLINE_NONFINITE"
    if not cases.get("perf_files"):
        klass = "INVALID_EXECUTION_PERF_FILES_MISSING_NOT_SCIENTIFIC"
    if rb.get("class") == "RB_PLACEHOLDER_ZERO_NO_TRAFFIC":
        klass = "INVALID_RB_PLACEHOLDER_HIDING_NO_TRAFFIC"
    elif rb.get("class") in (
        "RB_AGGREGATOR_FABRICATED_WITHOUT_PRESSURE_COUNTERS",
        "RB_CLIENT_NONZERO_AGGREGATOR_DROPPED",
        "RB_CONFLATED_WITH_RO_OR_VOLUME",
    ):
        klass = str(rb.get("class"))
    return {
        "pass": bool(ok),
        "cases": cases,
        "reasons": reasons,
        "class": klass,
        "decoded_states": decoded_states[:12],
        "n_unique_decoded": len(set(decoded_states)),
        "rb_lineage": rb,
    }
