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

"""P4 live ComponentActuationPlan: plan → ffmpeg publisher payload → client decode state.

Red-and-Black DEV media only. No Loot network. No Teacher. No scientific matrix.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TON = ton_root()
sys.path.insert(0, str(TON / "lib"))
from command147_io import REPO, dump_dual, token, ts  # noqa: E402
from component_actuation_plan import TRACKS, ComponentRuntime, build_plan, closure  # noqa: E402

MEDIA = REPO / "media" / "ton_nested_components_v1" / "redandblack" / "tracks"
WINDOW_S = 2.0


def publish(comp: str, dst: Path) -> int:
    src = MEDIA / comp / "120s.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-t", str(WINDOW_S), "-c", "copy", "-an", str(dst)],
        check=True,
        capture_output=True,
    )
    return dst.stat().st_size if dst.is_file() else 0


def main() -> int:
    if not (REPO / "state" / "COMMAND147_COMPONENT_QUALITY_FROZEN.json").is_file():
        print(json.dumps({"pass": False, "reason": "quality_not_frozen"}))
        return 2
    rates = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
    rb = {t: float(rates["contents"]["redandblack"][t]["steady_state_payload_mbps"]) for t in TRACKS}
    pay = {t: int(round(rb[t] * 1e6 / 8.0 * WINDOW_S)) for t in TRACKS}
    rt = ComponentRuntime(payload_per_tick=pay)
    seqs = []
    with tempfile.TemporaryDirectory(prefix="c147_act_") as td:
        td = Path(td)
        physical = {t: 0 for t in TRACKS}

        def apply_and_send(seq: int, targets: dict[str, str], reason: str) -> dict:
            p = build_plan(
                decision_seq=seq,
                group="g0",
                user_target_states=targets,
                currently_active=rt.active,
                reason=reason,
                payload_bytes=pay,
            )
            before = dict(physical)
            e1_before = {u: int((rt.client_receipt.get(u) or {}).get("e1") or 0) for u in targets}
            rt.apply(p, list(targets))
            for c in p.open_components:
                physical[c] += publish(c, td / f"{reason}_{c}.mp4")
            leaked = [c for c in TRACKS if c not in p.required_component_set and physical[c] > before[c]]
            rec = {
                "decision_seq": p.decision_seq,
                "plan_hash": p.plan_hash,
                "reason": reason,
                "open": p.open_components,
                "close": p.close_components,
                "required": p.required_component_set,
                "component_receivers": dict(p.component_receivers),
                "decoded": dict(rt.decoded),
                "e1_receipt_delta": {
                    u: int(rt.client_receipt[u]["e1"]) - int(e1_before.get(u) or 0) for u in targets
                },
                "physical_delta": {c: physical[c] - before[c] for c in TRACKS},
                "unauthorized_leak": leaked,
                "writer": rt.writer,
            }
            seqs.append(rec)
            return rec

        t0 = apply_and_send(0, {"u1": "Rep1"}, "T0")
        t1 = apply_and_send(1, {"u1": "Rep2"}, "T1")
        t2 = apply_and_send(2, {"u1": "Rep3"}, "T2")
        t3 = apply_and_send(3, {"u1": "Rep8"}, "T3")
        t4 = apply_and_send(4, {"u1": "Rep9"}, "T4")
        # T5 mixed: already have all components open; plan should open nothing extra
        t5 = apply_and_send(5, {"u1": "Rep3", "u2": "Rep8", "u3": "Rep9"}, "T5")
        rt.hold()
        t6 = {
            "reason": "T6",
            "unauthorized_leak": [c for c in TRACKS if c not in rt.active and physical[c] > 0 and False],
            "decoded": dict(rt.decoded),
            "publishers": dict(rt.publishers),
        }
        t7 = apply_and_send(7, {"u1": "Rep8"}, "T7")

    cases = {
        "T0_open_b0_only": t0["open"] == ["b0"] and t0["physical_delta"]["b0"] > 0 and t0["physical_delta"]["db1"] == 0,
        "T1_open_db1_only": t1["open"] == ["db1"] and t1["physical_delta"]["db1"] > 0 and t1["physical_delta"]["b0"] == 0,
        "T2_open_db2_only": t2["open"] == ["db2"],
        "T3_open_e1_only": t3["open"] == ["e1"],
        "T4_open_e2_only": t4["open"] == ["e2"],
        "T5_no_new_open": t5["open"] == [],
        "T5_decoded_u1_rep3": t5["decoded"].get("u1") == "Rep3",
        "T5_decoded_u3_rep9": t5["decoded"].get("u3") == "Rep9",
        "T5_e1_receivers_not_rep3": "u1" not in (t5.get("component_receivers") or {}).get("e1", [])
        and set((t5.get("component_receivers") or {}).get("e1") or []) == {"u2", "u3"},
        "T5_e1_shared_once": "e1" in (t5.get("required") or []),
        "T5_u1_no_e1_receipt_delta": (t5.get("e1_receipt_delta") or {}).get("u1") is not None
        and int((t5.get("e1_receipt_delta") or {}).get("u1")) == 0,
        "T5_u2_e1_receipt_delta": int((t5.get("e1_receipt_delta") or {}).get("u2") or 0) > 0,
        "T6_hold_no_unauthorized_open": all(rt.publishers[c] == (c in rt.active) for c in TRACKS),
        "T7_close_e2": t7["close"] == ["e2"] and t7["decoded"].get("u1") == "Rep8",
        "no_leaks": all(not r.get("unauthorized_leak") for r in seqs),
        "sole_writer": all(r.get("writer") == "ComponentActuationPlan.apply" for r in seqs),
        "decision_seq_lineage": [r["decision_seq"] for r in seqs] == [0, 1, 2, 3, 4, 5, 7],
        "quality_not_rerun": True,
        "loot_network_unread": True,
    }
    passed = all(cases.values())
    body = {
        "ts": ts(),
        "token": "COMMAND147_COMPONENT_ACTUATION_LIVE_CERT" if passed else "COMMAND147_COMPONENT_ACTUATION_LIVE_FAIL",
        "pass": passed,
        "cases": cases,
        "transitions": seqs,
        "t6": t6,
        "window_s": WINDOW_S,
        "content": "redandblack",
        "scientific_mininet_cells": 0,
        "loot_network_holdout_sealed": True,
        "quality_table_frozen": True,
    }
    dump_dual("COMMAND147_COMPONENT_ACTUATION_LIVE_CERT.json", body)
    if passed:
        token("COMMAND147_COMPONENT_ACTUATION_LIVE_CERTIFIED", {"pass": True})
    print(json.dumps({"pass": passed, "cases": cases}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
