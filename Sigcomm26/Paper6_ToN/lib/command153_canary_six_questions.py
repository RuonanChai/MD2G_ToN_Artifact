from __future__ import annotations
import sys
from pathlib import Path as _ArtifactPath
_r = _ArtifactPath(__file__).resolve()
for _c in [_r.parent, *_r.parents]:
    if (_c / 'artifact_paths.py').is_file():
        sys.path.insert(0, str(_c))
        break
from artifact_paths import artifact_root, ton_root  # portable artifact root

"""Mechanical six-question canary report + E020 post-repair audit.

Does not retune. Does not rank from mean U alone. MOQ_UNICAST is diagnostic only.
Primary comparison is MD2G vs strongest same-substrate (HV3 / CLUSTERING / RULE).
"""
import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

from command147_io import dump_dual, dump_status, token, ts

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
ART_DEFAULT = TON / "artifacts" / "command148_canary120_rbv1"
OUT = TON / "reports" / "command152"
REV = TON / "reviews" / "command152"

SAME = ["HV3_COMPONENT", "CLUSTERING_COMPONENT", "RULE_COMPONENT"]
UNICAST = "MOQ_UNICAST_COMPONENT"
MD2G = "MD2G_COMPONENT"
STATES = [f"Rep{i}" for i in range(1, 10)]
NOISE = 0.03
WEAK_CATASTROPHIC = 0.15
N_BOOT = 10000
BOOT_SEED = 153
POST_E020_CUTOFF = datetime(2026, 8, 20, 13, 40, 25, tzinfo=timezone.utc)
PRESSURE_MIN_INTERVALS = 10
WAITING_NEEDLE = "self.shell and not self.waiting"
E020_MIN_POST_CELLS_TO_CLOSE = 25


def _mean(xs: list[float]) -> float | None:
    return statistics.mean(xs) if xs else None


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _sign(x: float | None, eps: float = 1e-12) -> str | None:
    if x is None:
        return None
    if x > eps:
        return "+"
    if x < -eps:
        return "-"
    return "0"


def _blk(r: dict) -> str:
    return f"{r.get('content')}_{r.get('network')}_u{r.get('users')}_s{r.get('seed')}"


def _art(q: dict | None = None) -> Path:
    if q is None:
        qp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
        q = json.loads(qp.read_text()) if qp.is_file() else {}
    raw = (q or {}).get("art")
    if raw:
        return Path(raw)
    if str((q or {}).get("epoch") or "") == "post_physical_pressure_rbv1":
        return ART_DEFAULT
    return ART_DEFAULT


def load_completed_rows(q: dict | None = None) -> tuple[dict, list[dict]]:
    qp = REPO / "state" / "COMMAND148_CANARY120_QUEUE.json"
    if q is None:
        q = json.loads(qp.read_text()) if qp.is_file() else {}
    art = _art(q)
    out: list[dict] = []
    for key in q.get("completed") or []:
        cell = art / key
        if not (cell / "CELL_DONE.json").is_file():
            continue
        mp = cell / "CELL_METRICS.json"
        if not mp.is_file():
            continue
        raw = mp.read_text().strip()
        if raw in ("", "null"):
            continue
        m = json.loads(raw)
        if not isinstance(m, dict) or m.get("U") is None:
            continue
        if m.get("paper_U_is_Rb0_projection"):
            continue
        m["key"] = key
        out.append(m)
    return q, out


def bootstrap_mean_ci(
    xs: list[float], n_boot: int = N_BOOT, seed: int = BOOT_SEED
) -> dict:
    n = len(xs)
    mu = _mean(xs)
    if mu is None:
        return {"n": 0, "mean": None, "ci95_lo": None, "ci95_hi": None, "n_boot": n_boot, "seed": seed}
    if n < 2:
        return {"n": n, "mean": mu, "ci95_lo": None, "ci95_hi": None, "n_boot": n_boot, "seed": seed}
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        samp = [xs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(samp) / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[min(n_boot - 1, int(0.975 * n_boot))]
    return {"n": n, "mean": mu, "ci95_lo": lo, "ci95_hi": hi, "n_boot": n_boot, "seed": seed}


def wtl(dus: list[float], noise: float = NOISE) -> dict:
    w = t = l = 0
    for d in dus:
        if d > noise:
            w += 1
        elif d < -noise:
            l += 1
        else:
            t += 1
    return {"W": w, "T": t, "L": l, "noise_abs": noise, "n": len(dus)}


def strongest_same(recs: dict[str, dict]) -> tuple[str | None, dict]:
    best_s, best_u, best = None, None, {}
    for s in SAME:
        r = recs.get(s) or {}
        if r.get("U") is None:
            continue
        u = float(r["U"])
        if best_u is None or u > best_u:
            best_s, best_u, best = s, u, r
    return best_s, best


def occ_q(occ: dict | None, qmap: dict | None) -> float:
    occ = occ or {}
    qmap = qmap or {}
    return sum(float(occ.get(st) or 0.0) * float(qmap.get(st) or 0.0) for st in STATES)


def paired_blocks(blocks: dict[str, dict[str, dict]]) -> list[dict]:
    out = []
    for blk, recs in sorted(blocks.items()):
        md = recs.get(MD2G) or {}
        if md.get("U") is None:
            continue
        if any((recs.get(s) or {}).get("U") is None for s in SAME):
            continue
        name, best = strongest_same(recs)
        if name is None or best.get("U") is None:
            continue
        dU = float(md["U"]) - float(best["U"])
        dRq = float(md.get("Rq") or 0.0) - float(best.get("Rq") or 0.0)
        dRo = float(md.get("Ro_component") or 0.0) - float(best.get("Ro_component") or 0.0)
        dRb = float(md.get("Rb") or 0.0) - float(best.get("Rb") or 0.0)
        dW = float(md.get("weak_user_Rq") or 0.0) - float(best.get("weak_user_Rq") or 0.0)
        qmap = md.get("Q_norm_frozen") or {}
        tgt_q = occ_q(md.get("target_state_occupancy"), qmap)
        dec_q = occ_q(md.get("actual_decoded_state_occupancy") or md.get("component_occupancy"), qmap)
        cc = md.get("component_completion_fraction") or {}
        enh = []
        for k in ("e1", "e2"):
            frac = (cc.get(k) or {}).get("fraction")
            if frac is not None:
                enh.append(float(frac))
        uni = recs.get(UNICAST) or {}
        out.append(
            {
                "block": blk,
                "content": md.get("content"),
                "network": md.get("network"),
                "users": int(md.get("users") or 0),
                "seed": md.get("seed"),
                "strongest_same_substrate": name,
                "U_md2g": float(md["U"]),
                "U_strongest": float(best["U"]),
                "delta_U": dU,
                "delta_Rq": dRq,
                "delta_Ro": dRo,
                "delta_Rb": dRb,
                "delta_weak_user_Rq": dW,
                "target_minus_decoded_q": tgt_q - dec_q,
                "enh_e1_e2_completion": _mean(enh),
                "unicast_U": None if uni.get("U") is None else float(uni["U"]),
                "md2g": md,
            }
        )
    return out


def _slice_pack(pairs: list[dict], n_boot: int = N_BOOT) -> dict:
    dus = [p["delta_U"] for p in pairs]
    drq = [p["delta_Rq"] for p in pairs]
    dro = [p["delta_Ro"] for p in pairs]
    drb = [p["delta_Rb"] for p in pairs]
    dw = [p["delta_weak_user_Rq"] for p in pairs]
    ci = bootstrap_mean_ci(dus, n_boot=n_boot)
    return {
        "n_matched_blocks": len(pairs),
        "delta_U": ci,
        "WTL": wtl(dus),
        "mean_delta_Rq": _mean(drq),
        "mean_delta_Ro": _mean(dro),
        "mean_delta_Rb": _mean(drb),
        "mean_delta_weak_user_Rq": _mean(dw),
        "strongest_names": sorted({str(p["strongest_same_substrate"]) for p in pairs}),
        "blocks": [p["block"] for p in pairs],
    }


def advantage_source(pack: dict) -> dict:
    dRq = pack.get("mean_delta_Rq")
    dRo = pack.get("mean_delta_Ro")
    dRb = pack.get("mean_delta_Rb")
    if dRq is None:
        return {"label": "INSUFFICIENT", "contrib": {}}
    contrib = {
        "Rq": 0.60 * float(dRq),
        "Ro": 0.25 * float(dRo or 0.0),
        "Rb": -0.15 * float(dRb or 0.0),
    }
    primary = max(contrib, key=lambda k: contrib[k])
    rb_paid = float(dRb or 0.0) > NOISE
    dU = (pack.get("delta_U") or {}).get("mean")
    if dU is None:
        label = "INSUFFICIENT"
    elif dU > NOISE and primary == "Rq" and rb_paid:
        label = "Rq_GAIN_PAYING_HIGHER_Rb"
    elif dU > NOISE and primary == "Rq":
        label = "Rq_GAIN"
    elif dU > NOISE and primary == "Ro":
        label = "Ro_GAIN"
    elif dU > NOISE and primary == "Rb":
        label = "LOWER_Rb"
    elif dU < -NOISE:
        label = f"DEFICIT_PRIMARY_{primary}"
    else:
        label = "WITHIN_NOISE_OR_MIXED"
    return {
        "label": label,
        "U_weights": {"Ro": 0.25, "Rq": 0.60, "Rb": 0.15},
        "contrib_to_delta_U": contrib,
        "primary_positive_term": primary,
        "higher_Rb_than_strongest": rb_paid,
        "note": "contrib_Rb = -0.15*delta_Rb; higher Rb reduces U",
    }


def completion_label(mean_gap: float | None, mean_enh: float | None) -> str:
    if mean_gap is None:
        return "INSUFFICIENT"
    if mean_gap > 0.10 and (mean_enh is not None and mean_enh < 0.60):
        return "SYSTEMATIC_OVER_AGGRESSIVE"
    if mean_gap > 0.10 and (mean_enh is not None and mean_enh >= 0.85):
        return "AMBITIOUS_BUT_MOSTLY_COMPLETED"
    if mean_gap > 0.10:
        return "TARGET_ABOVE_DECODED_MIXED_COMPLETION"
    if mean_gap < -0.05:
        return "CONSERVATIVE_OR_DECODE_ABOVE_TARGET"
    return "NO_SYSTEMATIC_BIAS_DETECTED"


def _fmt(x: float | None, nd: int = 4) -> str:
    if x is None:
        return "NA"
    return f"{x:.{nd}f}"


def _ci_line(ci: dict) -> str:
    return (
        f"mean={_fmt(ci.get('mean'))}  CI95=[{_fmt(ci.get('ci95_lo'))}, {_fmt(ci.get('ci95_hi'))}]  "
        f"n={ci.get('n')}  bootstrap_seed={ci.get('seed')}"
    )


def _wtl_line(w: dict) -> str:
    return f"W={w.get('W')} T={w.get('T')} L={w.get('L')}  (W if dU>+{w.get('noise_abs')}, L if dU<-{w.get('noise_abs')})"


def e020_audit_cells(art: Path, keys: list[str], cutoff: datetime = POST_E020_CUTOFF) -> dict:
    waiting_keys: list[str] = []
    pressure_keys: list[str] = []
    validity_keys: list[str] = []
    scanned: list[str] = []
    skipped_live: list[str] = []
    skipped_pre: list[str] = []
    for key in keys:
        cell = art / key
        done_p = cell / "CELL_DONE.json"
        if not done_p.is_file():
            skipped_live.append(key)
            continue
        try:
            done = json.loads(done_p.read_text())
        except Exception:
            skipped_live.append(key)
            continue
        dt = _parse_ts(done.get("ts"))
        if dt is None or dt < cutoff:
            skipped_pre.append(key)
            continue
        scanned.append(key)
        stdout = cell / "cell_stdout.log"
        if stdout.is_file():
            try:
                txt = stdout.read_text(errors="ignore")
            except Exception:
                txt = ""
            if WAITING_NEEDLE in txt:
                waiting_keys.append(key)
        ts_p = cell / "PHYSICAL_PRESSURE_TIMESERIES.jsonl"
        n_int = None
        mp = cell / "CELL_METRICS.json"
        if mp.is_file():
            try:
                m = json.loads(mp.read_text())
                n_int = ((m.get("physical_pressure") or {}) or {}).get("n_intervals")
            except Exception:
                n_int = None
        missing_press = (not ts_p.is_file()) or (n_int is None) or (int(n_int) < PRESSURE_MIN_INTERVALS)
        if missing_press:
            pressure_keys.append(key)
        if not (cell / "CELL_VALIDITY.json").is_file():
            validity_keys.append(key)
    return {
        "cutoff_ts": cutoff.isoformat(),
        "n_post_E020_completed": len(scanned),
        "n_skipped_no_CELL_DONE_live_or_incomplete": len(skipped_live),
        "n_skipped_pre_E020": len(skipped_pre),
        "mininet_waiting_assertion_count_post_E020": len(waiting_keys),
        "pressure_samples_missing_post_E020": len(pressure_keys),
        "CELL_VALIDITY_missing_post_E020": len(validity_keys),
        "waiting_keys": waiting_keys,
        "pressure_missing_keys": pressure_keys,
        "validity_missing_keys": validity_keys,
        "scanned_keys": scanned,
        "note": "CELL_VALIDITY_missing counts absent file only, not valid=false. Live cells without CELL_DONE are skipped.",
    }


def build_report(
    rows: list[dict],
    pairs: list[dict],
    e020: dict,
    n_completed: int,
    final: bool,
    n_boot: int = N_BOOT,
) -> dict:
    all_pack = _slice_pack(pairs, n_boot=n_boot)
    u20 = [p for p in pairs if int(p["users"]) <= 20]
    u60 = [p for p in pairs if int(p["users"]) >= 60]
    u20_pack = _slice_pack(u20, n_boot=n_boot)
    u60_pack = _slice_pack(u60, n_boot=n_boot)
    rb = [p for p in pairs if str(p.get("content") or "") == "redandblack"]
    ld = [p for p in pairs if str(p.get("content") or "") == "longdress"]
    rb_pack = _slice_pack(rb, n_boot=n_boot)
    ld_pack = _slice_pack(ld, n_boot=n_boot)
    rb_u60 = _slice_pack([p for p in rb if int(p["users"]) >= 60], n_boot=n_boot)
    ld_u60 = _slice_pack([p for p in ld if int(p["users"]) >= 60], n_boot=n_boot)
    rb_u20 = _slice_pack([p for p in rb if int(p["users"]) <= 20], n_boot=n_boot)
    ld_u20 = _slice_pack([p for p in ld if int(p["users"]) <= 20], n_boot=n_boot)
    mu20 = (u20_pack["delta_U"] or {}).get("mean")
    mu60 = (u60_pack["delta_U"] or {}).get("mean")
    crossover = bool(u20 and u60) and (mu60 is not None and mu20 is not None) and (mu60 > 0) and (mu20 < 0)
    m_rb60 = (rb_u60["delta_U"] or {}).get("mean")
    m_ld60 = (ld_u60["delta_U"] or {}).get("mean")
    ld_u60_ok = int(ld_u60["n_matched_blocks"] or 0) > 0
    direction_u60 = (
        ld_u60_ok
        and _sign(m_rb60) is not None
        and _sign(m_rb60) == _sign(m_ld60)
        and _sign(m_rb60) != "0"
    )
    rb_u60_special = (
        ld_u60_ok
        and m_rb60 is not None
        and m_ld60 is not None
        and m_rb60 > NOISE
        and m_ld60 <= NOISE
    )
    src_all = advantage_source(all_pack)
    src_u60 = advantage_source(u60_pack)
    src_ld_u60 = advantage_source(ld_u60)
    d_weak = all_pack.get("mean_delta_weak_user_Rq")
    dU = (all_pack["delta_U"] or {}).get("mean")
    weak_cat = d_weak is not None and d_weak < -WEAK_CATASTROPHIC
    weak_notice = (
        d_weak is not None and dU is not None and d_weak < -NOISE and dU > NOISE
    )
    gaps = [p["target_minus_decoded_q"] for p in pairs]
    enhs = [p["enh_e1_e2_completion"] for p in pairs if p.get("enh_e1_e2_completion") is not None]
    mean_gap = _mean(gaps)
    mean_enh = _mean(enhs)
    uni_us = [float(r["U"]) for r in rows if str(r.get("strategy")) == UNICAST and r.get("U") is not None]
    n_post = int(e020.get("n_post_E020_completed") or 0)
    zeros = (
        int(e020.get("mininet_waiting_assertion_count_post_E020") or 0) == 0
        and int(e020.get("pressure_samples_missing_post_E020") or 0) == 0
        and int(e020.get("CELL_VALIDITY_missing_post_E020") or 0) == 0
    )
    e020_close = bool(final and n_completed >= 120 and n_post >= E020_MIN_POST_CELLS_TO_CLOSE and zeros)
    e020_status = (
        "REPAIRED_EXECUTION_ISSUE_CLOSED"
        if e020_close
        else (
            "OPEN_PENDING_REMAINING_CELLS"
            if n_completed < 120
            else ("OPEN_REGRESSION" if not zeros else "OPEN_INSUFFICIENT_POST_CELLS")
        )
    )
    return {
        "ts": ts(),
        "status": "FINAL_120" if (final and n_completed >= 120) else "PRELIMINARY_UNTIL_120",
        "n_completed_queue": n_completed,
        "n_metric_rows": len(rows),
        "n_matched_same_substrate_blocks": len(pairs),
        "do_not_rank_from_mean_U_alone": True,
        "primary_comparison": "MD2G vs strongest of HV3_COMPONENT / CLUSTERING_COMPONENT / RULE_COMPONENT",
        "MOQ_UNICAST_is_not_primary_algorithm_evidence": True,
        "loot_sealed": True,
        "pre_rb_excluded": True,
        "noise": {"paired_U_noise_abs": NOISE, "token": "COMMAND148_CANARY_NOISE_MARGINS_PREDECLARED"},
        "Q1_matched_delta_U_vs_strongest_same_substrate": all_pack,
        "Q2_u20_vs_u60_crossover": {
            "u20": u20_pack,
            "u60": u60_pack,
            "high_concurrency_crossover_still_holds_under_real_Rb": crossover,
            "rule": "holds iff mean(dU|u>=60)>0 and mean(dU|u<=20)<0 vs strongest same-substrate",
        },
        "Q3_content_direction": {
            "redandblack": rb_pack,
            "longdress": ld_pack,
            "redandblack_u20": rb_u20,
            "redandblack_u60": rb_u60,
            "longdress_u20": ld_u20,
            "longdress_u60": ld_u60,
            "u60_direction_consistent": direction_u60,
            "rb_u60_advantage_is_content_special_case": rb_u60_special,
            "longdress_u60_insufficient": not ld_u60_ok,
            "note": "Longdress rbv1 answers whether RB u60 advantage is content-specific; pre-Rb 56 is diagnostic only",
        },
        "Q4_advantage_source": {
            "all_matched": src_all,
            "u60": src_u60,
            "longdress_u60": src_ld_u60,
        },
        "Q5_weak_user_Rq": {
            "mean_delta_weak_user_Rq_vs_strongest": d_weak,
            "catastrophic_sacrifice_lt_minus_0.15": weak_cat,
            "noticeable_sacrifice_while_winning_U": weak_notice,
            "margin_catastrophic": WEAK_CATASTROPHIC,
        },
        "Q6_target_decoded_completion": {
            "mean_target_minus_decoded_q": mean_gap,
            "mean_e1_e2_completion": mean_enh,
            "label": completion_label(mean_gap, mean_enh),
        },
        "unicast_delivery_diagnostic": {
            "n": len(uni_us),
            "mean_U": _mean(uni_us),
            "not_primary_MD2G_vs_baseline_evidence": True,
            "use": "post-Rb delivery-mode contrast only",
        },
        "E020": {**e020, "status": e020_status, "closed": e020_close},
    }


def render_md(body: dict) -> str:
    q1 = body["Q1_matched_delta_U_vs_strongest_same_substrate"]
    q2 = body["Q2_u20_vs_u60_crossover"]
    q3 = body["Q3_content_direction"]
    q4 = body["Q4_advantage_source"]
    q5 = body["Q5_weak_user_Rq"]
    q6 = body["Q6_target_decoded_completion"]
    uni = body["unicast_delivery_diagnostic"]
    e = body["E020"]
    lines = [
        "# COMMAND153 canary six questions (mechanical)",
        "",
        f"- status: `{body['status']}`",
        f"- ts: `{body['ts']}`",
        f"- completed: `{body['n_completed_queue']}`  matched same-substrate blocks: `{body['n_matched_same_substrate_blocks']}`",
        "- : MD2G vs HV3 / CLUSTERING / RULE ；** mean U**",
        "- MOQ_UNICAST ， baseline ",
        "- pre-Rb 56 ",
        "",
        "## Q1  matched ΔU vs strongest same-substrate",
        "",
        f"- {_ci_line(q1['delta_U'])}",
        f"- {_wtl_line(q1['WTL'])}",
        f"- strongest names seen: `{', '.join(q1.get('strongest_names') or [])}`",
        "",
        "## Q2 u20 vs u60（ Rb high-concurrency crossover）",
        "",
        f"- u20: {_ci_line(q2['u20']['delta_U'])}  {_wtl_line(q2['u20']['WTL'])}",
        f"- u60: {_ci_line(q2['u60']['delta_U'])}  {_wtl_line(q2['u60']['WTL'])}",
        f"- crossover still holds: `{q2['high_concurrency_crossover_still_holds_under_real_Rb']}`",
        f"- rule: `{q2['rule']}`",
        "",
        "## Q3  Red-and-Black vs Longdress",
        "",
        f"- RB all: {_ci_line(q3['redandblack']['delta_U'])}  {_wtl_line(q3['redandblack']['WTL'])}",
        f"- LD all: {_ci_line(q3['longdress']['delta_U'])}  {_wtl_line(q3['longdress']['WTL'])}",
        f"- RB u60: {_ci_line(q3['redandblack_u60']['delta_U'])}  {_wtl_line(q3['redandblack_u60']['WTL'])}",
        f"- LD u60: {_ci_line(q3['longdress_u60']['delta_U'])}  {_wtl_line(q3['longdress_u60']['WTL'])}",
        f"- u60 direction consistent: `{q3['u60_direction_consistent']}`",
        f"- RB u60 advantage is content special case: `{q3['rb_u60_advantage_is_content_special_case']}`",
        f"- Longdress u60 insufficient: `{q3['longdress_u60_insufficient']}`",
        "",
        "## Q4 （U 0.25/0.60/0.15）",
        "",
        f"- all: `{q4['all_matched']['label']}` contrib=`{q4['all_matched'].get('contrib_to_delta_U')}`",
        f"- u60: `{q4['u60']['label']}` contrib=`{q4['u60'].get('contrib_to_delta_U')}`",
        f"- Longdress u60: `{q4['longdress_u60']['label']}` contrib=`{q4['longdress_u60'].get('contrib_to_delta_U')}`",
        "",
        "## Q5  weak-user Rq",
        "",
        f"- mean Δ weak_user_Rq vs strongest: `{_fmt(q5['mean_delta_weak_user_Rq_vs_strongest'])}`",
        f"- catastrophic sacrifice (< -0.15): `{q5['catastrophic_sacrifice_lt_minus_0.15']}`",
        f"- noticeable sacrifice while winning U: `{q5['noticeable_sacrifice_while_winning_U']}`",
        "",
        "## Q6  target→decoded completion",
        "",
        f"- mean (target_q - decoded_q): `{_fmt(q6['mean_target_minus_decoded_q'])}`",
        f"- mean e1/e2 completion: `{_fmt(q6['mean_e1_e2_completion'])}`",
        f"- label: `{q6['label']}`",
        "",
        "## UNICAST diagnostic (not primary)",
        "",
        f"- n={uni['n']} mean_U=`{_fmt(uni['mean_U'])}`",
        f"- `{uni['use']}`",
        "",
        "## E020 post-repair audit",
        "",
        f"- status: `{e['status']}` closed=`{e['closed']}`",
        f"- mininet_waiting_assertion_count_post_E020 = `{e.get('mininet_waiting_assertion_count_post_E020')}`",
        f"- pressure_samples_missing_post_E020 = `{e.get('pressure_samples_missing_post_E020')}`",
        f"- CELL_VALIDITY_missing_post_E020 = `{e.get('CELL_VALIDITY_missing_post_E020')}`",
        f"- n_post_E020_completed = `{e.get('n_post_E020_completed')}` cutoff=`{e.get('cutoff_ts')}`",
        "",
    ]
    return "\n".join(lines)


def write_reports(final: bool = False, n_boot: int = N_BOOT, q: dict | None = None) -> dict:
    q, rows = load_completed_rows(q)
    blocks: dict[str, dict[str, dict]] = {}
    for r in rows:
        blocks.setdefault(_blk(r), {})[str(r.get("strategy") or "")] = r
    pairs = paired_blocks(blocks)
    n_completed = len(q.get("completed") or [])
    if final is False:
        final = n_completed >= 120
    art = _art(q)
    e020 = e020_audit_cells(art, list(q.get("completed") or []))
    body = build_report(rows, pairs, e020, n_completed, final=final, n_boot=n_boot)
    OUT.mkdir(parents=True, exist_ok=True)
    (REPO / "reports" / "command152").mkdir(parents=True, exist_ok=True)
    (REV).mkdir(parents=True, exist_ok=True)
    text = json.dumps(body, indent=2) + "\n"
    md = render_md(body)
    for root in (OUT, REPO / "reports" / "command152", REV, REPO / "reviews" / "command152"):
        root.mkdir(parents=True, exist_ok=True)
        (root / "COMMAND153_CANARY_SIX_QUESTIONS.json").write_text(text)
        (root / "COMMAND153_CANARY_SIX_QUESTIONS.md").write_text(md if md.endswith("\n") else md + "\n")
    dump_dual("COMMAND153_CANARY_SIX_QUESTIONS.json", body)
    dump_dual("COMMAND153_E020_POST_REPAIR_AUDIT.json", body["E020"])
    dump_status("COMMAND153_CANARY_SIX_QUESTIONS.md", md)
    if body["E020"].get("closed"):
        token(
            "COMMAND153_E020_CLOSED",
            {
                "mininet_waiting_assertion_count_post_E020": 0,
                "pressure_samples_missing_post_E020": 0,
                "CELL_VALIDITY_missing_post_E020": 0,
                "n_post_E020_completed": body["E020"].get("n_post_E020_completed"),
                "status": "REPAIRED_EXECUTION_ISSUE_CLOSED",
            },
        )
        dump_status(
            "COMMAND153_E020_CLOSED.md",
            "E020 closed: post-E020 waiting/pressure/CELL_VALIDITY missing counts are all 0.\n",
        )
    return body
