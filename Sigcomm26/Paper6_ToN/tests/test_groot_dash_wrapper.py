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

from pathlib import Path
src = Path("str(artifact_root())/DASH/groot_dash_experiment.py").read_text()
assert "from rolling_dash_experiment import main" not in src
assert "run_rolling_dash_experiment" in src
print("PASS: groot_dash_wrapper")
