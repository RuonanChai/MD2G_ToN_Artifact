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

"""Regression: wifi C28 exact replay must use trained_models dir (wifi student), not 4g.pth file."""
import importlib.util
from pathlib import Path

TON = ton_root()
REPO = artifact_root()
SCRIPT = TON / "scripts" / "command91_exact_cell_replay.py"
WIFI = REPO / "trained_models" / "deploy_student_128" / "ppo_actor_student_wifi.pth"


def _load():
    spec = importlib.util.spec_from_file_location("c91replay", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_model_path_is_trained_models_dir():
    mod = _load()
    mp = Path(mod.model_path_for_net("wifi"))
    assert mp.is_dir(), mp
    assert mp.name == "trained_models"
    assert WIFI.is_file()


def test_env_c28_does_not_point_at_4g_file_for_wifi():
    mod = _load()
    e = mod.env_c28(61, net="wifi")
    assert e["MM26_MD2G_COMPLETION_WEIGHT"] == "1.0"
    assert "4g.pth" not in e["MODEL_PATH"]
    assert Path(e["MODEL_PATH"]).is_dir()


if __name__ == "__main__":
    test_model_path_is_trained_models_dir()
    test_env_c28_does_not_point_at_4g_file_for_wifi()
    print("COMMAND92_MODEL_PATH_WIFI_OK")
