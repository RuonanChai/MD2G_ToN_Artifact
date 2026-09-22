"""Portable repository root. No host-specific paths."""
from __future__ import annotations

import os
from pathlib import Path


def artifact_root() -> Path:
    env = os.environ.get("ARTIFACT_ROOT") or os.environ.get("MD2G_TON_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve().parent
    markers = (
        here / "moq_cluster_Sigcomm.py",
        here / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json",
    )
    if all(p.is_file() for p in markers):
        return here
    for cand in Path(__file__).resolve().parents:
        if (cand / "moq_cluster_Sigcomm.py").is_file() and (
            cand / "state" / "COMMAND146_COMPONENT_DAG_CONTRACT.json"
        ).is_file():
            return cand
    raise RuntimeError("Set ARTIFACT_ROOT to the artifact repository root")


def ton_root() -> Path:
    return artifact_root() / "Sigcomm26" / "Paper6_ToN"
