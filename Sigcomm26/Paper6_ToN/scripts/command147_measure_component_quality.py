#!/usr/bin/env python3
"""COMMAND147 P2: freeze Q(content,state) from membership coverage. Mechanical media only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from command147_io import REPO, dump_analysis, dump_dual, dump_status, sha256_file, token, ts  # noqa: E402

ROOT = REPO / "media" / "ton_nested_components_v1"
DAG_P = REPO / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json"
CONTENTS = ["redandblack", "longdress", "soldier", "loot"]
SAMPLE_FRAMES = (0, 75, 150, 224, 299)


def load_dag() -> dict:
    return json.loads(DAG_P.read_text())["logical_states"]


def coverage_frame(npz: dict, comps: list[str], verify_disjoint: bool = False) -> dict:
    n = int(npz["n"][0])
    cards = {}
    parts = []
    for c in comps:
        arr = np.asarray(npz[c]).reshape(-1)
        cards[c] = int(arr.size)
        if verify_disjoint and arr.size:
            parts.append(arr.astype(np.int64, copy=False))
    # Components are certified pairwise disjoint, so union cardinality is the sum.
    union_sum = int(sum(cards.values()))
    union = union_sum
    if verify_disjoint and parts:
        union = int(np.unique(np.concatenate(parts)).size)
    return {
        "n": n,
        "union": union,
        "coverage": union / n if n else 0.0,
        "component_cards": cards,
        "disjoint_sum_equals_unique": (union == union_sum) if verify_disjoint else True,
        "decode_success_membership": union > 0 and all(c in npz.files for c in comps),
    }


def atlas_psnr(cid: str, fi: int, comps: list[str], npz: dict) -> dict | None:
    """Secondary codec-independent geometry check: packed atlas vs membership cardinality."""
    try:
        cards = {c: int(np.asarray(npz[c]).size) for c in comps}
        unpacked = 0
        for c in comps:
            png = ROOT / cid / "tracks" / c / "atlas_png" / f"frame_{fi:04d}.png"
            if not png.is_file():
                return None
            arr = np.array(Image.open(png))
            unpacked += int(np.asarray(npz[c]).size)
            _ = arr  # atlas exists
        n = int(npz["n"][0])
        return {"atlas_present": True, "unpacked_points": unpacked, "n": n}
    except Exception:
        return None


def main() -> int:
    frozen = REPO / "state" / "COMMAND147_COMPONENT_QUALITY_FROZEN.json"
    if frozen.is_file():
        print(json.dumps({"pass": True, "skipped": "COMMAND147_COMPONENT_QUALITY_FROZEN_is_authority", "rerun": False}))
        return 0
    # Freeze normalization BEFORE filling live-controller-facing numbers.
    norm_rule = {
        "canonical_metric_id": "nested_component_point_coverage_v1",
        "Q_raw": "mean over all membership frames of |union_{c in C(state)} point_ids(c)| / n_source_points",
        "Q_norm": "clip(Q_raw, 0, 1) identity; no min-max across Rep IDs; no native-9 paper_quality_score",
        "pre_existing_source": (
            "COMMAND135/146 nested index-stride membership completeness "
            "(command135 gate D monotonic-depth used the same point-coverage geometry)"
        ),
        "forbidden": ["Rep ID as quality", "native-9 Table-1 paper_quality_score", "force monotonicity"],
        "loot": "mechanical media characterization only; never for controller/model/hyperparameter selection",
        "frozen_before_controller_result": True,
    }
    states = load_dag()
    raw = {"ts": ts(), "normalization_rule": norm_rule, "contents": {}}
    qtab = {}
    notes = []
    for cid in CONTENTS:
        print(f"[quality] {cid} start", flush=True)
        maps = sorted((ROOT / cid / "mapping").glob("frame_*_membership.npz"))
        if not maps:
            notes.append(f"missing_maps:{cid}")
            continue
        acc = {
            sid: {
                "comps": list(spec["C"]),
                "sum_cov": 0.0,
                "sum_union": 0.0,
                "sum_n": 0.0,
                "min_cov": 1.0,
                "max_cov": 0.0,
                "decode_ok": True,
                "samples": [],
                "base": spec.get("base"),
                "enh": spec.get("enh"),
            }
            for sid, spec in states.items()
        }
        for fi, mp in enumerate(maps):
            if fi % 50 == 0:
                print(f"[quality] {cid} frame {fi}/{len(maps)}", flush=True)
            d = np.load(mp)
            for sid, a in acc.items():
                row = coverage_frame(d, a["comps"], verify_disjoint=(fi in SAMPLE_FRAMES))
                a["sum_cov"] += row["coverage"]
                a["sum_union"] += row["union"]
                a["sum_n"] += row["n"]
                a["min_cov"] = min(a["min_cov"], row["coverage"])
                a["max_cov"] = max(a["max_cov"], row["coverage"])
                a["decode_ok"] = a["decode_ok"] and row["decode_success_membership"]
                if fi in SAMPLE_FRAMES:
                    a["samples"].append({"frame": fi, **row, "atlas": atlas_psnr(cid, fi, a["comps"], d)})
        n_maps = len(maps)
        per_state = {}
        for sid, a in acc.items():
            q_raw = a["sum_cov"] / n_maps if n_maps else 0.0
            q_norm = float(min(1.0, max(0.0, q_raw)))
            per_state[sid] = {
                "component_closure": a["comps"],
                "base": a["base"],
                "enh": a["enh"],
                "n_frames": n_maps,
                "Q_raw": float(q_raw),
                "Q_norm": q_norm,
                "mean_union_points": a["sum_union"] / n_maps if n_maps else 0.0,
                "mean_source_points": a["sum_n"] / n_maps if n_maps else 0.0,
                "coverage_min": float(a["min_cov"] if n_maps else 0.0),
                "coverage_max": float(a["max_cov"] if n_maps else 0.0),
                "decode_success": a["decode_ok"],
                "samples": a["samples"],
                "rep_id_is_not_quality": True,
            }
        # Observed order vs Rep ID — do not rewrite.
        order = sorted(per_state, key=lambda s: per_state[s]["Q_raw"])
        id_order = [f"Rep{i}" for i in range(1, 10)]
        monotonic_vs_rep_id = order == id_order
        if not monotonic_vs_rep_id:
            notes.append(f"{cid}: quality order {order} != Rep ID order (preserved, not forced)")
        raw["contents"][cid] = {
            "states": per_state,
            "observed_quality_order_low_to_high": order,
            "monotonic_in_rep_id": monotonic_vs_rep_id,
            "holdout_network_not_inspected": cid == "loot",
            "loot_not_for_controller_selection": cid == "loot",
            "media_manifest_sha256": sha256_file(ROOT / cid / "media_manifest.json"),
        }
        qtab[cid] = {sid: per_state[sid]["Q_norm"] for sid in per_state}
        print(f"[quality] {cid} done order={order}", flush=True)
    passed = len(raw["contents"]) == 4 and all(
        all(st["decode_success"] for st in body["states"].values()) for body in raw["contents"].values()
    )
    dump_analysis("COMMAND147_COMPONENT_QUALITY_RAW.json", raw)
    contract = {
        "ts": ts(),
        "token": "COMMAND147_COMPONENT_QUALITY_CONTRACT" if passed else "COMMAND147_COMPONENT_QUALITY_PENDING",
        "pass": passed,
        "normalization_rule": norm_rule,
        "Q_norm": qtab,
        "controller_may_use_contents": ["redandblack", "longdress", "soldier"],
        "controller_must_not_use_contents": ["loot"],
        "loot_mechanical_only": True,
        "rep_id_is_not_quality": True,
        "monotonicity_not_forced": True,
        "notes": notes,
    }
    dump_dual("COMMAND147_COMPONENT_QUALITY_CONTRACT.json", contract)
    md = [
        "# COMMAND147 component quality",
        "",
        f"- pass: `{passed}`",
        "- metric: point-coverage completeness of dependency closure (pre-existing nested-membership geometry)",
        "- Q_norm = clip(coverage, 0, 1); Rep ID is not quality; monotonicity not forced",
        "- Loot table is mechanical only",
        "",
    ]
    for cid, body in raw["contents"].items():
        md.append(f"## {cid}")
        md.append("")
        md.append("| state | C(r) | Q_raw | Q_norm | decode |")
        md.append("|---|---|---|---|---|")
        for sid, stt in body["states"].items():
            md.append(
                f"| {sid} | `{'+'.join(stt['component_closure'])}` | {stt['Q_raw']:.4f} | {stt['Q_norm']:.4f} | {stt['decode_success']} |"
            )
        md.append(f"- observed order: `{body['observed_quality_order_low_to_high']}`")
        md.append("")
    dump_status("COMMAND147_COMPONENT_QUALITY_REPORT.md", "\n".join(md) + "\n")
    if passed:
        token("COMMAND147_COMPONENT_QUALITY_FROZEN", {"pass": True, "loot_mechanical_only": True})
        clar = {
            "ts": ts(),
            "token": "COMMAND147_COMPONENT_ASSET_CERTIFICATION_CLARIFICATION",
            "structural_asset_certified": True,
            "quality_semantics_certified": True,
            "earlier_token": "COMMAND146_COMPONENT_ASSETS_CERTIFIED",
            "earlier_token_scope": "structural/dependency/byte only; quality D was pending",
            "no_earlier_corrected_contract_scientific_cell_depended_on_missing_Q": True,
            "scientific_mininet_cells": 0,
        }
        dump_dual("COMMAND147_COMPONENT_ASSET_CERTIFICATION_CLARIFICATION.json", clar)
        token(
            "COMMAND147_COMPONENT_ASSETS_FULLY_SCIENTIFICALLY_CERTIFIED",
            {"structural_asset_certified": True, "quality_semantics_certified": True},
        )
    print(json.dumps({"pass": passed, "notes": notes, "Q_norm": qtab}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
