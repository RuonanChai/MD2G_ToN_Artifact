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

"""command40: N/A / missing subscriber PID is hard failure."""
import sys
from pathlib import Path

REPO = artifact_root()
sys.path.insert(0, str(REPO))

import moq_cluster_Sigcomm as m


def test_na_pid_is_failure():
    assert m.subscriber_pid_ok(None) is False
    assert m.subscriber_pid_ok("") is False
    assert m.subscriber_pid_ok("N/A") is False
    assert m.subscriber_pid_ok("n/a") is False
    assert m.subscriber_pid_ok("none") is False


def test_numeric_pid_ok():
    assert m.subscriber_pid_ok("12345") is True
    assert m.subscriber_pid_ok(" 99 ") is True


def test_source_never_prints_success_for_na():
    src = (REPO / "moq_cluster_Sigcomm.py").read_text(encoding="utf-8")
    assert "dispatch PID: {dispatch_pid or 'N/A'}" not in src
    assert "SUBSCRIBER_LAUNCH_GATE" in src
    assert "subscriber_h{i}_launch.json" in src or "subscriber_h{" in src


def test_cell_validity_fails_without_subscriber_pids(tmp_path):
    valid, payload = m.compute_and_write_cell_validity(
        str(tmp_path),
        strategy="md2g",
        num_subscribers=2,
        registered_publishers=set(),
        expected_publishers={"base1"},
        subscriber_pids=[(1, "N/A", "r1"), (2, "", "r2")],
        leaf_egress_bytes=0,
    )
    assert valid is False
    assert payload["subscriber_pids_ok"] == 0
    assert (tmp_path / "CELL_VALIDITY.json").is_file()


if __name__ == "__main__":
    test_na_pid_is_failure()
    test_numeric_pid_ok()
    test_source_never_prints_success_for_na()
    import tempfile
    from pathlib import Path as P
    with tempfile.TemporaryDirectory() as d:
        test_cell_validity_fails_without_subscriber_pids(P(d))
    print("OK test_subscriber_launch_gate")
