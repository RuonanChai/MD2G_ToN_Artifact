#!/usr/bin/env python3
"""COMMAND147 P1: freeze true 300-frame / 10 s / 30 fps / 120 s loop semantics."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from command147_io import REPO, TON, dump_analysis, dump_dual, dump_status, sha256_file, token, ts  # noqa: E402

ROOT = REPO / "media" / "ton_nested_components_v1"
CONTENTS = ["redandblack", "longdress", "soldier", "loot"]
TRACKS = ["b0", "db1", "db2", "e1", "e2"]
TOL = 0.02
WARMUP_S = 30.0
EXPERIMENT_S = 120.0
MEASUREMENT_S = EXPERIMENT_S - WARMUP_S
GEN = TON / "scripts" / "command146_generate_nested_component_media.py"
PUB = REPO / "moq_cluster_Sigcomm.py"


def ffprobe(path: Path) -> dict:
    pr = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration,bit_rate,size",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    d = json.loads(pr.stdout)
    st, fmt = d["streams"][0], d["format"]
    num, den = (st.get("avg_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    duration_s = float(fmt.get("duration") or st.get("duration") or 0)
    raw_nb = st.get("nb_frames")
    try:
        nb_frames = int(float(raw_nb))
    except (TypeError, ValueError):
        nb_frames = int(round(duration_s * fps)) if fps else 0
    return {
        "path": str(path),
        "codec": st.get("codec_name"),
        "fps": fps,
        "nb_frames": nb_frames,
        "duration_s": duration_s,
        "bit_rate_bps": int(float(fmt.get("bit_rate") or 0)),
        "size_bytes": int(fmt.get("size") or path.stat().st_size),
    }


def cmaf_bytes(path: Path) -> int:
    """Publisher-like CMAF remux of the unique clip (not the 120 s loop) to avoid RAM blowup."""
    import os
    import tempfile

    fd, name = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    out = Path(name)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(path), "-c", "copy", "-an",
                "-f", "mp4",
                "-movflags", "cmaf+separate_moof+delay_moov+skip_trailer+frag_every_frame",
                str(out),
            ],
            check=True,
            capture_output=True,
        )
        return out.stat().st_size
    finally:
        out.unlink(missing_ok=True)()


def main() -> int:
    gen_hash = sha256_file(GEN)
    pub_hash = sha256_file(PUB)
    rows = {}
    blocks = []
    for cid in CONTENTS:
        man_p = ROOT / cid / "media_manifest.json"
        part_p = ROOT / cid / "partition_manifest.json"
        if not man_p.is_file():
            blocks.append(f"missing_manifest:{cid}")
            continue
        man = json.loads(man_p.read_text())
        part = json.loads(part_p.read_text())
        png_n = len(list((ROOT / cid / "tracks" / "b0" / "atlas_png").glob("frame_*.png")))
        map_n = len(list((ROOT / cid / "mapping").glob("frame_*_membership.npz")))
        unique_frames = int(man.get("n_source_frames") or part.get("n_frames") or png_n)
        comps = {}
        for t in TRACKS:
            short = ROOT / cid / "tracks" / t / "short.mp4"
            loop = ROOT / cid / "tracks" / t / "120s.mp4"
            sp = ffprobe(short)
            lp = ffprobe(loop)
            src_dur = unique_frames / (sp["fps"] or 30.0)
            one_pass = int(sp["size_bytes"])
            loop_bytes = int(lp["size_bytes"])
            derived_loop_bps = (loop_bytes * 8.0) / max(lp["duration_s"], 1e-9)
            derived_unique_bps = (one_pass * 8.0) / max(sp["duration_s"], 1e-9)
            naive_wrong_bps = (one_pass * 8.0) / EXPERIMENT_S
            probe_err = abs(derived_loop_bps - lp["bit_rate_bps"]) / max(derived_loop_bps, 1.0)
            try:
                cmaf = cmaf_bytes(short)
                cmaf_bps = (cmaf * 8.0) / max(sp["duration_s"], 1e-9)
                cmaf_err = abs(cmaf_bps - derived_unique_bps) / max(derived_unique_bps, 1.0)
            except Exception as exc:
                cmaf, cmaf_bps, cmaf_err = 0, 0.0, None
                comps_note = str(exc)
            else:
                comps_note = None
            # 2% applies to payload-vs-derived of the actual sent 120s asset (ffprobe vs size/time).
            payload_ok = probe_err <= TOL
            # CMAF remux of the unique clip reports publisher-like object overhead separately.
            if abs(sp["duration_s"] - src_dur) > 0.2:
                blocks.append(f"{cid}/{t}:short_duration_mismatch")
            if abs(lp["duration_s"] - EXPERIMENT_S) > 0.6:
                blocks.append(f"{cid}/{t}:loop_duration_not_120")
            if sp["nb_frames"] not in (unique_frames, unique_frames + 1, unique_frames - 1):
                blocks.append(f"{cid}/{t}:short_framecount {sp['nb_frames']}!={unique_frames}")
            expect_loop_frames = int(round(EXPERIMENT_S * (lp["fps"] or 30.0)))
            if abs(lp["nb_frames"] - expect_loop_frames) > 5:
                blocks.append(f"{cid}/{t}:loop_framecount {lp['nb_frames']}!={expect_loop_frames}")
            if not payload_ok:
                blocks.append(f"{cid}/{t}:probe_vs_derived {probe_err:.4f}>{TOL}")
            comps[t] = {
                "unique_frame_count": unique_frames,
                "source_fps": sp["fps"],
                "source_asset_duration_s": sp["duration_s"],
                "experiment_duration_s": lp["duration_s"],
                "warmup_s": WARMUP_S,
                "measurement_duration_s": MEASUREMENT_S,
                "playback_mode": (
                    "UNIQUE_CLIP_LOOPED: 300 unique frames at 30 fps form a 10 s source clip; "
                    "ffmpeg -stream_loop encodes a 120 s transport file; publisher "
                    "ffmpeg -re -stream_loop -1 -c copy reads 120s.mp4 (frag_every_frame)."
                ),
                "one_pass_asset_bytes": one_pass,
                "looped_transport_bytes": loop_bytes,
                "steady_state_payload_mbps": derived_loop_bps / 1e6,
                "unique_clip_payload_mbps": derived_unique_bps / 1e6,
                "forbidden_naive_one_pass_over_120s_mbps": naive_wrong_bps / 1e6,
                "derivation_formula": "steady_state_payload_bps = looped_transport_bytes * 8 / experiment_duration_s",
                "ffprobe_bit_rate_bps": lp["bit_rate_bps"],
                "ffprobe_vs_derived_rel_err": probe_err,
                "cmaf_unique_clip_bytes": cmaf,
                "cmaf_unique_clip_mbps": cmaf_bps / 1e6,
                "cmaf_vs_unique_file_rel_err": cmaf_err,
                "cmaf_note": comps_note,
                "short": sp,
                "loop": lp,
                "payload_match_pass": payload_ok,
            }
        rows[cid] = {
            "png_frames": png_n,
            "membership_frames": map_n,
            "unique_frame_count": unique_frames,
            "source_fps": 30.0,
            "source_asset_duration_s": unique_frames / 30.0,
            "experiment_duration_s": EXPERIMENT_S,
            "warmup_s": WARMUP_S,
            "measurement_duration_s": MEASUREMENT_S,
            "playback_mode": "loop_10s_unique_clip_inside_120s_transport_then_publisher_-re",
            "contradiction_resolved": "300/30=10s unique; 120s is looped experiment/transport, not 3600 unique frames",
            "holdout_network_not_inspected": cid == "loot",
            "media_manifest_sha256": sha256_file(man_p),
            "partition_manifest_sha256": sha256_file(part_p),
            "components": comps,
        }
    contradiction_ok = all(
        abs(rows[c]["source_asset_duration_s"] - 10.0) < 0.05 and rows[c]["experiment_duration_s"] == EXPERIMENT_S
        for c in CONTENTS
        if c in rows
    )
    if not contradiction_ok:
        blocks.append("unique_duration_not_10s")
    if len(rows) != 4:
        blocks.append("missing_content")
    passed = not blocks
    audit = {
        "ts": ts(),
        "token": "COMMAND147_TEMPORAL_BITRATE_AUDIT",
        "pass": passed,
        "blocks": blocks,
        "predeclared_payload_tolerance_frac": TOL,
        "warmup_s": WARMUP_S,
        "experiment_duration_s": EXPERIMENT_S,
        "measurement_duration_s": MEASUREMENT_S,
        "script_hash": gen_hash,
        "publisher_script_hash": pub_hash,
        "publisher_pacing": "ffmpeg -re -stream_loop -1 -c copy -movflags cmaf+frag_every_frame → ~30 objects/s/component",
        "canonical_rate": "looped 120s transport file bits / 120 s (NOT unique-clip bytes / 120 s)",
        "contents": rows,
        "loot_network_holdout_sealed": True,
    }
    dump_analysis("COMMAND147_TEMPORAL_BITRATE_AUDIT.json", audit)
    (REPO / "analysis" / "COMMAND147_TEMPORAL_BITRATE_AUDIT.json").write_text(
        json.dumps(audit, indent=2) + "\n"
    )
    md = [
        "# COMMAND147 temporal/bitrate audit",
        "",
        f"- pass: `{passed}`",
        f"- unique source: **300 frames @ 30 fps = 10.0 s**, looped to **120 s** experiment/transport",
        f"- warmup `{WARMUP_S}` s, measurement `{MEASUREMENT_S}` s",
        f"- canonical rate = `120s.mp4_bytes * 8 / duration_s` (publisher copy-sends this file)",
        f"- forbidden: unique-clip bytes / 120 s",
        f"- payload vs ffprobe tolerance `{TOL:.0%}`",
        f"- Loot: mechanical media only; network holdout sealed",
        "",
        "| content | b0 Mbps | db1 | db2 | e1 | e2 | unique s | loop s |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cid in CONTENTS:
        r = rows.get(cid) or {}
        c = r.get("components") or {}
        def m(t):
            return f"{(c.get(t) or {}).get('steady_state_payload_mbps', 0):.3f}"
        md.append(
            f"| {cid} | {m('b0')} | {m('db1')} | {m('db2')} | {m('e1')} | {m('e2')} | "
            f"{r.get('source_asset_duration_s')} | {r.get('experiment_duration_s')} |"
        )
    if blocks:
        md += ["", "## blocks", ""] + [f"- {b}" for b in blocks]
    dump_status("COMMAND147_TEMPORAL_BITRATE_AUDIT.md", "\n".join(md) + "\n")
    contract = {
        "ts": ts(),
        "token": "COMMAND147_TEMPORAL_BITRATE_CONTRACT" if passed else "COMMAND147_TEMPORAL_BITRATE_PENDING",
        "pass": passed,
        "unique_frame_count": 300,
        "source_fps": 30.0,
        "source_asset_duration_s": 10.0,
        "experiment_duration_s": EXPERIMENT_S,
        "warmup_s": WARMUP_S,
        "measurement_duration_s": MEASUREMENT_S,
        "playback_mode": "UNIQUE_CLIP_LOOPED_10s_IN_120s_TRANSPORT",
        "derivation_formula": "steady_state_payload_bps = looped_transport_bytes * 8 / experiment_duration_s",
        "script_hash": gen_hash,
        "publisher_script_hash": pub_hash,
        "payload_tolerance_frac": TOL,
        "loot_network_holdout_sealed": True,
        "contents": {
            cid: {
                t: {
                    "unique_frame_count": rows[cid]["components"][t]["unique_frame_count"],
                    "source_fps": rows[cid]["components"][t]["source_fps"],
                    "source_asset_duration_s": rows[cid]["components"][t]["source_asset_duration_s"],
                    "experiment_duration_s": rows[cid]["components"][t]["experiment_duration_s"],
                    "warmup_s": WARMUP_S,
                    "measurement_duration_s": MEASUREMENT_S,
                    "playback_mode": rows[cid]["components"][t]["playback_mode"],
                    "one_pass_asset_bytes": rows[cid]["components"][t]["one_pass_asset_bytes"],
                    "steady_state_payload_mbps": rows[cid]["components"][t]["steady_state_payload_mbps"],
                    "derivation_formula": rows[cid]["components"][t]["derivation_formula"],
                    "script_hash": gen_hash,
                    "manifest_hash": rows[cid]["media_manifest_sha256"],
                }
                for t in TRACKS
            }
            for cid in CONTENTS
            if cid in rows
        },
    }
    dump_dual("COMMAND147_TEMPORAL_BITRATE_CONTRACT.json", contract)
    if passed:
        token("COMMAND147_TEMPORAL_BITRATE_FROZEN", {"pass": True})
    print(json.dumps({"pass": passed, "blocks": blocks}, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
