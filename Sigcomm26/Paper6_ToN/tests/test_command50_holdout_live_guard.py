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

"""Regression: live-holdout guard must not FP on quarantine/stale/canary/pre-release."""
import json
import sys
from pathlib import Path
from unittest import mock

OUT = ton_root()
sys.path.insert(0, str(OUT / "scripts"))
import command50_live_holdout_guard as g  # noqa: E402

STATE = OUT / "state"
REPL = (STATE / "SIGCOMM_REPLACEMENT_HOLDOUT_ROOT.txt").read_text().strip()
ART = (STATE / "SIGCOMM_ARTIFACT_ROOT.txt").read_text().strip()


def _ps(lines: list[str]):
    return mock.patch.object(g, "_ps_moq_lines", return_value=lines)


def _alive(val: bool = True):
    return mock.patch.object(g, "_pid_alive", return_value=val)


def test_quarantined_files_no_process():
    with _ps([]), mock.patch.object(g, "_read") as rd:
        def side(p):
            s = str(p)
            if s.endswith("HOLDOUT_RELEASE_APPROVED"):
                return "false"
            if "REPLACEMENT" in s:
                return REPL
            if "ARTIFACT" in s:
                return ART
            return ""

        rd.side_effect = side
        cls = g.classify_live_processes()
        assert cls["status"] == "CLEAR"
        assert any(p["verdict"] == "IGNORE_DIRECTORY_ONLY" for p in cls["predicates"])


def test_stale_pid_file():
    line = f"999999 Mon Jul 1 00:00:00 2026 python moq_cluster_Sigcomm.py --network_type default_mix --log_path {REPL}/default_mix/users_10/md2g/trial_0"
    with _ps([line]), mock.patch.object(g, "_pid_alive", return_value=False):
        cls = g.classify_live_processes()
        assert cls["status"] == "CLEAR"
        assert cls["true_holdout"] == []
        assert any(i.get("reason") == "stale_pid_not_alive" for i in cls["ignored"])


def test_active_development_canary():
    line = (
        "12345 Sat Jul 25 09:43:18 2026 python /repo/moq_cluster_Sigcomm.py "
        "--network_type 5g --log_path /tmp/canary2_md2g_one_20260725_094319"
    )
    with _ps([line]), _alive(True):
        cls = g.classify_live_processes()
        assert cls["status"] == "DEFER_LIVE_CANARY"
        assert cls["true_holdout"] == []


def test_true_live_holdout():
    line = (
        f"4242 Sat Jul 25 10:00:00 2026 python /repo/moq_cluster_Sigcomm.py "
        f"--network_type default_mix --log_path {REPL}/default_mix/users_10/md2g/trial_0"
    )
    with _ps([line]), _alive(True), mock.patch.object(g, "_read") as rd, mock.patch.object(
        g, "_release_mtime", return_value=1.0
    ), mock.patch.object(g, "_proc_start_epoch", return_value=100.0), mock.patch.object(
        g, "_lock_owned", return_value=True
    ):

        def side(p):
            s = str(p)
            if s.endswith("HOLDOUT_RELEASE_APPROVED"):
                return "true"
            if "REPLACEMENT" in s:
                return REPL
            if "ARTIFACT" in s:
                return ART
            return ""

        rd.side_effect = side
        cls = g.classify_live_processes()
        assert cls["status"] == "HOLDOUT_LIVE"
        assert len(cls["true_holdout"]) == 1


def test_mismatched_freeze_hash_not_approved_root():
    # Holdout net but log under ART not replacement → not approved live
    line = (
        f"4242 Sat Jul 25 10:00:00 2026 python /repo/moq_cluster_Sigcomm.py "
        f"--network_type default_mix --log_path {ART}/default_mix/users_10/md2g/trial_0"
    )
    with _ps([line]), _alive(True), mock.patch.object(g, "_read") as rd:

        def side(p):
            s = str(p)
            if s.endswith("HOLDOUT_RELEASE_APPROVED"):
                return "true"
            if "REPLACEMENT" in s:
                return REPL
            if "ARTIFACT" in s:
                return ART
            return ""

        rd.side_effect = side
        cls = g.classify_live_processes()
        assert cls["status"] == "CLEAR"
        assert cls["true_holdout"] == []


def test_pre_release_launch_not_holdout_live():
    line = (
        f"4242 Sat Jul 25 10:00:00 2026 python /repo/moq_cluster_Sigcomm.py "
        f"--network_type default_mix --log_path {REPL}/default_mix/users_10/md2g/trial_0"
    )
    with _ps([line]), _alive(True), mock.patch.object(g, "_read") as rd:

        def side(p):
            s = str(p)
            if s.endswith("HOLDOUT_RELEASE_APPROVED"):
                return "false"
            if "REPLACEMENT" in s:
                return REPL
            if "ARTIFACT" in s:
                return ART
            return ""

        rd.side_effect = side
        cls = g.classify_live_processes()
        assert cls["status"] == "CLEAR"
        assert cls["true_holdout"] == []
        assert any(i.get("reason") == "pre_release_replacement_process" for i in cls["ignored"])


def main():
    test_quarantined_files_no_process()
    test_stale_pid_file()
    test_active_development_canary()
    test_true_live_holdout()
    test_mismatched_freeze_hash_not_approved_root()
    test_pre_release_launch_not_holdout_live()
    print("COMMAND50_HOLDOUT_LIVE_GUARD_REGRESSION_PASS")
    print("FALSE_HOLDOUT_LIVE_GUARD_REPAIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
