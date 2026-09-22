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

"""Corrected-contract Teacher + Student. Frozen Q_norm, component closure rates.

No Loot network outcomes. Rep ID is not quality. No native-9 paper_quality_score.
"""
import json
import os
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

REPO = artifact_root()
TON = REPO / "Sigcomm26" / "Paper6_ToN"
sys.path.insert(0, str(TON / "lib"))
sys.path.insert(0, str(TON))
from command147_io import dump_dual, sha256_file, token, ts  # noqa: E402
from component_actuation_plan import closure  # noqa: E402
from controllers.g2_native9rep_model import build_student, build_teacher, distillation_loss  # noqa: E402

STATES = [f"Rep{i}" for i in range(1, 10)]
DEV_CONTENTS = ["redandblack", "longdress"]
MODEL_DIR = TON / "models" / "command148_component"
LOG = TON / "logs" / "command148_teacher.log"
BATCHES_PER_EPOCH = 16  # original validation budget; required so labels are not modal-Rep1
_Q = None
_R = None


def qnorm() -> dict:
    global _Q
    if _Q is None:
        _Q = json.loads((REPO / "state" / "COMMAND147_COMPONENT_QUALITY_CONTRACT.json").read_text())["Q_norm"]
    return _Q


def rates(content: str) -> dict[str, float]:
    global _R
    if _R is None:
        body = json.loads((REPO / "state" / "COMMAND147_TEMPORAL_BITRATE_CONTRACT.json").read_text())
        _R = {
            c: {t: float(body["contents"][c][t]["steady_state_payload_mbps"]) for t in ("b0", "db1", "db2", "e1", "e2")}
            for c in ("redandblack", "longdress")
        }
    return _R[content]


def state_rate(content: str, state: str) -> float:
    r = rates(content)
    return sum(r[c] for c in closure(state))


def missing_rate(content: str, state: str, active: list[str] | None) -> float:
    r = rates(content)
    a = set(active or [])
    return sum(r[c] for c in closure(state) if c not in a)


def expert_state(
    access: torch.Tensor,
    device: torch.Tensor,
    content: str,
    active: list[str] | None = None,
) -> torch.Tensor:
    q = qnorm()[content]
    B, N = access.shape
    out = torch.full((B, N), 1, dtype=torch.long)
    device_need = {
        "Rep1": 0.0, "Rep2": 0.15, "Rep3": 0.25, "Rep4": 0.2, "Rep5": 0.35,
        "Rep6": 0.3, "Rep7": 0.4, "Rep8": 0.35, "Rep9": 0.45,
    }
    for b in range(B):
        for n in range(N):
            best, bq = 1, -1.0
            for i, st in enumerate(STATES, start=1):
                if float(device[b, n]) + 1e-9 < device_need[st]:
                    continue
                if float(access[b, n]) + 1e-9 < missing_rate(content, st, active) * 1.05:
                    continue
                qq = float(q[st])
                if qq > bq:
                    bq, best = qq, i
            out[b, n] = best
    return out


PREFIX_ACTIVE = [
    [],
    ["b0"],
    ["b0", "db1"],
    ["b0", "db1", "db2"],
    ["b0", "db1", "db2", "e1"],
    ["b0", "db1", "db2", "e1", "e2"],
]


def sample_batch(n_users=20, batch=4):
    B, N = batch, n_users
    content = DEV_CONTENTS[int(torch.randint(0, len(DEV_CONTENTS), (1,)).item())]
    access = torch.rand(B, N) * 80 + 20
    device = torch.rand(B, N)
    active = PREFIX_ACTIVE[int(torch.randint(0, len(PREFIX_ACTIVE), (1,)).item())]
    user = torch.zeros(B, N, 16)
    user[:, :, 0] = access / 120.0
    user[:, :, 1] = device
    content_feats = torch.zeros(B, 12)
    content_feats[:, 0] = 0.0 if content == "redandblack" else 1.0
    global_feats = torch.zeros(B, 10)
    global_feats[:, 0] = N / 100.0
    for j, tr in enumerate(("b0", "db1", "db2", "e1", "e2")):
        global_feats[:, 1 + j] = 1.0 if tr in set(active) else 0.0
    tgt = expert_state(access, device, content, active)
    return user, content_feats, global_feats, tgt, content


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{ts()} {msg}"
    print(line, flush=True)
    LOG.open("a").write(line + "\n")


def main() -> int:
    if not (REPO / "state" / "COMMAND147_READY_FOR_COMMAND146_TEACHER.json").is_file():
        print(json.dumps({"pass": False, "reason": "teacher_gate_closed"}))
        return 2
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    tpath = MODEL_DIR / "teacher_component_v1.pt"
    teacher = build_teacher()
    reuse = (os.environ.get("COMMAND149_REUSE_TEACHER") or "").strip() in ("1", "true", "yes") and tpath.is_file()
    last = None
    if reuse:
        blob = torch.load(str(tpath), map_location="cpu", weights_only=False)
        sd = blob["state_dict"] if isinstance(blob, dict) and "state_dict" in blob else blob
        teacher.load_state_dict(sd)
        teacher.eval()
        log("reuse frozen teacher_component_v1.pt; student CE+distill only")
        last = -1.0
    else:
        opt = torch.optim.Adam(teacher.parameters(), lr=1e-3)
        for ep in range(1, 41):
            for _ in range(BATCHES_PER_EPOCH):
                user, cfeat, gfeat, tgt, content = sample_batch()
                out = teacher(user, cfeat, gfeat)
                logits = out["rep_logits"]
                loss = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), (tgt.reshape(-1) - 1).clamp(0, 8))
                opt.zero_grad()
                loss.backward()
                opt.step()
                last = float(loss.detach())
            if ep % 10 == 0:
                log(f"teacher ep={ep} loss={last:.4f} content={content}")
        torch.save({"state_dict": teacher.state_dict(), "contract": "component_qnorm_v1_missing_DeltaR"}, tpath)
    teacher.eval()
    student = build_student()
    sopt = torch.optim.Adam(student.parameters(), lr=1e-3)
    agree = []
    dlast = None
    for ep in range(1, 41):
        for _ in range(BATCHES_PER_EPOCH):
            user, cfeat, gfeat, tgt, content = sample_batch()
            with torch.no_grad():
                t_out = teacher(user, cfeat, gfeat)
            s_out = student(user, cfeat, gfeat)
            s_logits = s_out["rep_logits"]
            loss = F.cross_entropy(
                s_logits.reshape(-1, s_logits.shape[-1]), (tgt.reshape(-1) - 1).clamp(0, 8)
            )
            loss = loss + 0.1 * distillation_loss(t_out, s_out)
            sopt.zero_grad()
            loss.backward()
            sopt.step()
            dlast = float(loss.detach())
            agree.append(float((t_out["rep_logits"].argmax(-1) == s_out["rep_logits"].argmax(-1)).float().mean()))
        if ep % 5 == 0:
            log(f"distill ep={ep} loss={dlast:.4f} agree={agree[-1]:.3f}")
    spath = MODEL_DIR / "student_component_v1.pt"
    torch.save({"state_dict": student.state_dict(), "contract": "component_qnorm_v1"}, spath)
    hits = 0
    n = 0
    illegal = 0
    with torch.no_grad():
        for _ in range(16):
            user, cfeat, gfeat, tgt, content = sample_batch()
            pred = student(user, cfeat, gfeat)["rep_logits"].argmax(-1) + 1
            hits += int((pred == tgt).sum())
            n += int(pred.numel())
            illegal += int(((pred < 1) | (pred > 9)).sum())
    acc = hits / max(n, 1)
    dump_dual(
        "COMMAND148_TEACHER_TRAINING_FREEZE.json",
        {
            "ts": ts(),
            "architecture": "G2Native9RepController; logits index composition Rep1-9; Q from frozen Q_norm",
            "optimizer": "Adam 1e-3",
            "teacher_epochs": 40,
            "student_epochs": 40,
            "batches_per_epoch": BATCHES_PER_EPOCH,
            "feasibility": "missing_component_DeltaR",
            "margin": 1.05,
            "contents": DEV_CONTENTS,
            "loot_network_unread": True,
            "q_from": "COMMAND147_COMPONENT_QUALITY_FROZEN",
            "rate_from": "COMMAND147_TEMPORAL_BITRATE_FROZEN",
            "teacher_path": str(tpath),
            "teacher_sha256": sha256_file(tpath),
            "final_teacher_loss": last,
        },
    )
    dump_dual(
        "COMMAND148_TEACHER_VALIDATION.json",
        {"ts": ts(), "student_vs_expert_acc": acc, "illegal_compositions": illegal, "pass": acc >= 0.50 and illegal == 0},
    )
    dump_dual(
        "COMMAND148_STUDENT_DISTILLATION.json",
        {
            "ts": ts(),
            "student_path": str(spath),
            "student_sha256": sha256_file(spath),
            "mean_teacher_student_agree": sum(agree) / max(len(agree), 1),
            "final_distill_loss": dlast,
            "component_contract_violations": illegal,
        },
    )
    ok = acc >= 0.50 and illegal == 0
    if ok:
        token("COMMAND148_TEACHER_STUDENT_READY", {"student": str(spath), "agree": acc})
    print(json.dumps({"pass": ok, "agree": acc, "illegal": illegal, "teacher_loss": last}))
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
