# TON_FINAL_EXPERIMENT_STATUS

Fair live MCG completion for `MD2G_Cast_ToN_Fair_Live_MCG_Experiment_Command.txt`.

## 1. Live and fair

- MD2G-Cast, Heuristic, Clustering: frozen COMMAND153 live Mininet/MoQ (`dev.json`, Red-and-Black × 4G/WiFi/Fiber × 20/60/100 × seeds 151–153).
- MCG: **live** Mininet/MoQ, same launcher/metrics/validators, `27/27` VALID cells under `artifacts/ton_live_mcg/`.
- Fairness gate: **PASS**.

## 2. Offline / not fair as paper baselines

- `results/mcg_baseline/`: offline sidecar replay. Supplementary only.
- Rolling in this pack: Cast command82 handbook. **Not** same MoQ substrate. Do not claim a fair Rolling bake-off.
- Utility sensitivity, controller latency (60-user), completion, four-content tables: kept from the previous offline pack.

## 3. Exact commands

```bash
PY=./Sigcomm26/.venv_sigcomm/bin/python3
EXT=./Sigcomm26/Paper6_ToN/scripts/ton_cast_extension
# live 27-cell owner (tmux:ton_live_mcg):
$PY -u $EXT/live_mcg_harness.py
# after 27 VALID:
$PY -u $EXT/live_mcg_aggregate.py
# previous pack (do not treat MCG as live):
$PY $EXT/run_all.py
```

## 4. Artifact paths

- `live_cells`: `./Sigcomm26/Paper6_ToN/results/live_mcg_baseline/live_mcg_cells.csv`
- `summary`: `./Sigcomm26/Paper6_ToN/results/live_mcg_baseline/live_mcg_summary.csv`
- `table`: `./Sigcomm26/Paper6_ToN/results/live_mcg_baseline/live_mcg_table.tex`
- `figure`: `./Sigcomm26/Paper6_ToN/results/live_mcg_baseline/live_mcg_utility_vs_users.pdf`
- `provenance`: `./Sigcomm26/Paper6_ToN/results/live_mcg_baseline/provenance.json`
- `fairness`: `./Sigcomm26/Paper6_ToN/results/live_mcg_baseline/fairness_check.json`
- `mcg_art`: `./Sigcomm26/Paper6_ToN/artifacts/ton_live_mcg`
- `offline_mcg`: `./Sigcomm26/Paper6_ToN/results/mcg_baseline`
- `audit`: `./Sigcomm26/Paper6_ToN/TON_EXPERIMENT_AUDIT.md`

## 5. Claims supported

- Same-substrate live comparison of MD2G-Cast vs MCG vs Heuristic vs Clustering on the 27-cell RB slice, using frozen U.
- Previous completion / weight-sensitivity / 25.4 ms latency / four-content analyses remain valid on frozen COMMAND153 evidence.

## 6. Claims forbidden

- Do not call offline MCG a live baseline.
- Do not call Cast-handbook Rolling a same-substrate MoQ baseline.
- Do not change frozen U weights or MD2G-Cast because of these numbers.
- Do not cite P99 delay as a COMMAND153 paper metric (not in contract); use stall_last if needed.
- Do not unseal Loot or claim a new holdout run.

