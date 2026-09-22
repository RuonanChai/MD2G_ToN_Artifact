# MD2G-Cast ToN Reproducibility Artifact

Reproducibility artifact for the current ToN nested-component implementation.
This is a new repository with a fresh Git history. It is not a fork of the conference-era public repository.

## 1. Artifact scope

This repository contains the **current ToN 9-logical-state** implementation:

- five **physical** media components: `b0`, `db1`, `db2`, `e1`, `e2`
- nine **logical** service states `Rep1`–`Rep9` (decoded unions, not nine standalone videos)
- same-substrate controllers: MD2G-Cast, MCG, Heuristic, Clustering, Rule
- frozen evaluation JSON used to reproduce paper tables and figures
- launchers and figure scripts

It does **not** contain:

- the 11 GB encoded media tree
- 48 GB raw Mininet cell dumps
- MoQ/Rust binaries (build or set `SIGCOMM_MOQ_BIN_DIR`)
- a Python virtualenv

Do not call the nine logical states "nine bitrates". Component rates are a property of the five physical tracks; a logical state is a composition.

## 2. Repository structure

```
artifact_paths.py
moq_cluster_Sigcomm.py
dispatch_strategy_enhanced_unified_Sigcomm.py
state/                         # DAG, quality, bitrate contracts
datasets/                      # 4G / Wi-Fi / fiber / 5G traces
strategies/                    # subscriber lifecycle helpers
Sigcomm26/Paper6_ToN/
  lib/                         # MD2G, MCG, feasibility, metrics
  controllers/                 # student/teacher network
  models/command148_component/ # frozen student weights
  scripts/                     # cell launchers, live MCG, figures
  tests/
  contracts/
  final/COMMAND153_FIGURE_SOURCE_DATA/
  results/                     # live MCG summary + extension analyses
  Figures/                     # figure scripts and paper PDFs
docs/
```

## 3. Environment requirements

- Linux, Python 3.11+, `numpy`, `pandas`, `matplotlib`, `scikit-learn`
- Live Mininet cells additionally need: Mininet, `sudo`, `ffmpeg`, and MoQ binaries `hang`, `moq-relay`, `moq-sub`
- Set `ARTIFACT_ROOT` to this repository root (optional if run from the root)
- Set `SIGCOMM_MOQ_BIN_DIR` to the directory that contains `hang` / `moq-relay` / `moq-sub`

Install figure/metrics dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## 4. Component contract

Physical components are complementary point subsets with prerequisites:

| Component | Prerequisites |
|-----------|---------------|
| `b0` | none |
| `db1` | `b0` |
| `db2` | `b0`, `db1` |
| `e1` | `b0` |
| `e2` | `b0`, `e1` |

Logical states (from `state/COMMAND146_COMPONENT_DAG_CONTRACT.json`):

| State | Physical closure |
|-------|------------------|
| Rep1 | b0 |
| Rep2 | b0, db1 |
| Rep3 | b0, db1, db2 |
| Rep4 | b0, e1 |
| Rep5 | b0, e1, e2 |
| Rep6 | b0, db1, e1 |
| Rep7 | b0, db1, e1, e2 |
| Rep8 | b0, db1, db2, e1 |
| Rep9 | b0, db1, db2, e1, e2 |

Sharing is decided at runtime from receiver demand and access. Encoded base/refinement labels are not a fixed sharing role.

## 5. Controller definitions

See `docs/BASELINE_CONTRACT.md` for inputs, decision rules, thresholds, and feasibility.

All same-substrate controllers emit per-user logical targets, then the **same** deterministic projector `project_down()` admits only the missing components whose extra shared rate fits `access × 1.05`.

## 6. Dynamic receiver-context formation

`component_receivers()` maps each physical component to the set of users whose current target closure needs it. The map is recomputed every control interval from demand, device capability, and access. Grouping is therefore time-varying.

## 7. Minimal smoke test

```bash
export ARTIFACT_ROOT="$PWD"
python3 -c "from artifact_paths import artifact_root; print(artifact_root())"
python3 -m pytest Sigcomm26/Paper6_ToN/tests/test_command148_mcg.py \
  Sigcomm26/Paper6_ToN/tests/test_command149_marginal_cost.py \
  Sigcomm26/Paper6_ToN/tests/test_command147_actuation_t0_t7.py -q
```

These tests do not launch Mininet.

## 8. Reproducing the main experiment matrices

Full live cells require media + MoQ binaries + Mininet:

```bash
export ARTIFACT_ROOT="$PWD"
export SIGCOMM_MOQ_BIN_DIR=/path/to/moq/release
# example single cell
python3 Sigcomm26/Paper6_ToN/scripts/command148_canary_cell.py --help
```

Authoritative completed-matrix numbers are already in `final/COMMAND153_FIGURE_SOURCE_DATA/`. Re-running the 945-cell development matrix is not required to regenerate paper figures.

## 9. Same-substrate controller study

Contract (Red-and-Black × {4G, Wi-Fi, fiber} × {20, 60, 100} × seeds {151, 152, 153}):

- 27 matched workload blocks
- 5 strategies × 27 = 135 strategy-specific runs
- MD2G / Heuristic / Clustering / Rule: frozen `dev.json` slice
- MCG: live cells summarized in `results/live_mcg_baseline/`

## 10. Reproducing paper figures

```bash
export ARTIFACT_ROOT="$PWD"
python3 Sigcomm26/Paper6_ToN/scripts/plot_live_mcg_maintext.py
# other figures: Sigcomm26/Paper6_ToN/Figures/generate_paper_artifacts.py
```

## 11. Metric definitions

\[
U=\mathrm{clip}(0.25 R_o+0.60 R_q-0.15 R_b,0,1)
\]

- \(R_q\): mean decoded-coverage quality over launched users (missing decode = 0)
- \(R_o\): component reuse `Ro_component`
- \(R_b\): physical shared-root pressure
- Control interval: 1 second
- Completion fraction: \(\sum n_{\mathrm{complete\_dump\_gt\_64}} / \sum n_{\mathrm{receivers}}\)

## 12. Expected outputs

- `results/live_mcg_maintext/live_mcg_maintext_summary.csv`
- `Figures/QoE/Live_MCG_Fair_Mechanism_1x3.pdf`
- development/holdout figure PDFs under `Figures/`

## 13. Runtime notes

- One scientific Mininet executor at a time
- Loot network evaluation stays sealed until the published controller freeze
- Offline MCG sidecar replay is supplementary, not a live baseline
- Rolling/GROOT are cross-stack DASH/HTTP, not same-substrate MoQ

## 14. Data provenance

Frozen table/figure numbers come from `final/COMMAND153_FIGURE_SOURCE_DATA/` and `results/live_mcg_baseline/`. Raw cell dumps are not shipped. Media can be regenerated from the nested-component pipeline documented in `state/COMMAND146_COMPONENT_DAG_CONTRACT.json` (see `scripts/command135_generate_layered_media.py` if present in a full checkout).

Evaluation contents: Red-and-Black, Longdress (development), Soldier (unseen in development), and the sealed holdout sequence.

## 15. Known limitations

- Live reruns need external MoQ binaries and ~11 GB media
- This artifact is sufficient to audit controllers, contracts, metrics, and to regenerate figures from frozen JSON
- It is not a bit-identical dump of every Mininet packet capture
