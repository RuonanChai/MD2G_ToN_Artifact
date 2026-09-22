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

"""Regression: owner detection must ignore bash -lc wrappers; repair targets window main only."""
import sys
from pathlib import Path
from unittest import mock

OUT = ton_root()
sys.path.insert(0, str(OUT / "scripts"))
import command51_audit_core as c  # noqa: E402


def test_owners_ignore_lc_wrapper():
    lines = [
        "111 bash -lc export FOO=1; bash /x/command49_orchestrator.sh >>log 2>&1",
        "222 bash /x/scripts/command49_orchestrator.sh",
        "333 bash /x/scripts/sigcomm_run_matrix.sh",
        "444 /venv/bin/python3 -u /x/command49_md2g_search_engine.py --search-art /a",
    ]
    with mock.patch.object(c, "_pgrep", side_effect=lambda pat: [ln for ln in lines if pat.split(".")[0] in ln or pat in ln]):
        # simpler: patch per call
        pass

    def fake_pgrep(pat):
        if "orchestrator" in pat:
            return [lines[0], lines[1]]
        if "search_engine" in pat:
            return [lines[3]]
        if "run_matrix" in pat:
            return [lines[2]]
        return []

    with mock.patch.object(c, "_pgrep", side_effect=fake_pgrep):
        o = c._owners()
        assert o["n_orchestrators"] == 1, o
        assert "222" in o["orchestrators"][0]
        assert o["n_matrix"] == 1
        assert o["n_engines"] == 1


def test_repair_uses_main_window_name():
    src = Path(c.__file__).read_text()
    assert "sigcomm-command49:main" in src or 'n", "main"' in src or '-n", "main"' in src
    assert "sigcomm-command49:0.0" not in src


def main():
    test_owners_ignore_lc_wrapper()
    test_repair_uses_main_window_name()
    print("COMMAND51_OWNER_REPAIR_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
