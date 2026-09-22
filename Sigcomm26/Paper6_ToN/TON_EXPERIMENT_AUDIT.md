# TON_EXPERIMENT_AUDIT

Phase 0 for `commands/MD2G_Cast_ToN_Fair_Live_MCG_Experiment_Command.txt`.
Generated before live MCG implementation. Does not modify frozen MD2G-Cast / PPO / U.

## Previous pack (keep)

`TON_EXTENSION_EXPERIMENT_REPORT.md` and `results/` tasks 2–5 stay valid.

| Artifact | Status |
|---|---|
| `results/mcg_baseline/` | **OFFLINE_TRACE_REPLAY only.** Not a paper baseline. Keep as supplementary. |
| `results/utility_sensitivity/` | Keep. Frozen U unchanged. |
| `results/controller_latency/` | Keep 60-user microbench (25.4 / 23.5 ms). |
| `results/completion_analysis/` | Keep live COMMAND153 completion. |
| `results/cross_content_generalization.tex` | Keep. No new Loot run. |

Offline MCG \(U\) (RB, 4G+WiFi+Fiber seed-mean): 0.423 / 0.414 / 0.417 at 20/60/100 users — **below** live MD2G and Clustering. Do not cite as fair.

Root cause (do not silently “fix” the offline files): `mcg_tick` labeled empty decoded as Rep1, so \(\Delta Q(b0)=0\) and the greedy admitted nothing. Live MCG uses undecoded \(R_q=0\), matching `cell_metrics`.

## 1. Live experiment launcher

| Item | Path |
|---|---|
| Cluster | `moq_cluster_Sigcomm.py` |
| Cell launcher | `Sigcomm26/Paper6_ToN/scripts/command148_canary_cell.py` |
| Injected continuation | `COMMAND148_SPEC_JSON` + `COMMAND148_ART_ROOT` + `COMMAND153_QUEUE_NAME` (same as `command153_continue.py` / `command148_main_dev.py`) |
| Duration | `--duration 120` `--interval 1.0` |
| Nested planner period | `time.sleep(1.0)` in cluster |
| Seed | `SIGCOMM_BASELINE_SEED` |
| Content | `TON_CONTENT_ID` / `MM26_CONTENT_ID` |
| Network | `--network_type` (`4g`, `wifi`, `fiber_optic`) |
| Strategy env | `COMMAND148_STRATEGY` (cluster always passes `--strategy heuristic`; policy is env-selected) |
| Student (MD2G only) | `models/command148_component/student_component_v1.pt` |
| Executor lock | `lib/command152_executor_lock.py` → `state/SCIENTIFIC_EXECUTOR.lock` |
| Pause | `lib/command151_pause.py` (HOLD released) |

Reuse this launcher. Do **not** edit MM26 `regional_relay_controller.py`.

COMMAND153 is terminal (`TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B`). `tmux:command152_orch` is dead. `moq_live=false`. Stale lock pid 3639645 is dead. Disk gate: ~341 GiB free, `pause_next_launch=false`. One Mininet: launch only via canary_cell + lock.

## 2. Baseline scheduler interface

`lib/command148_component_policy.py`:

- `schedule_strategy_targets(strategy, t, n_users, duration, log_path, content)` is the only live policy hook.
- MD2G: `md2g_student_targets` → student logits → `project_down` (missing-component \(\Delta R\times 1.05\)).
- HV3 / Clustering / Rule / MoQ-unicast: `_raw_policy_targets` then `_apply_shared_physics` (same `project_down`).
- Live state already used by MD2G: access from `client_h*_perf.csv` RX deltas, device from perf, active components from `COMPONENT_ACTUATION_PLAN_CURRENT.json`.
- **FoV:** listed in the command, but the frozen ToN student feature vector does **not** include FoV (access, device, \(t\), content, \(N\), active flags). Live MCG must not consume extra FoV; that would be an information advantage vs MD2G-Cast.

MCG will be `MCG_COMPONENT` in this same function. Action interface unchanged: `user_id → Rep{1–9}` → `build_plan` → shared publishers `b0,db1,db2,e1,e2`.

## 3. Metric collection path

`lib/command148_canary_metrics.py` → `cell_metrics` → `CELL_METRICS.json`.

Canonical \(U=\mathrm{clip}(0.25 R_o+0.60 R_q-0.15 R_b,0,1)\) via `ton_ro_component.paper_u`.
\(R_b\) from physical pressure (`PHYSICAL_PRESSURE_TIMESERIES.jsonl`), not \(0.7\times\)RX.
Completion from `component_completion_fraction`.
P99 delay is **not** in the COMMAND153 claim contract; secondary delay proxy is `stall_last` if present.

Warmup: live `cell_metrics` uses last-receipt / last-perf (same as frozen MD2G/HV3/Clustering). The 30 s cut exists only in the **offline** sidecar replay. Fair live comparison must use the same metric code, not a new warmup.

## 4. Artifact validation

`lib/command148_canary_audit.py` `audit_canary_cell`. Fail-closed: cluster `CELL_VALIDITY`, perf/receipts count, plan jsonl, no unauthorized dumps, finite headlines, Rb lineage, physical pressure timeseries. MD2G additionally requires `COMMAND148_STUDENT_INFERENCE.jsonl`. MCG will require `COMMAND148_MCG_DECISION.jsonl` (treatment fidelity), without changing the MD2G gate.

Exit code 0 is not VALID.

## 5. Existing live baselines for the 27-cell slice

COMMAND153 `final/COMMAND153_FIGURE_SOURCE_DATA/dev.json`, Red-and-Black × `{4g,wifi,fiber_optic}` × `{20,60,100}` × seeds `{151,152,153}`:

| Strategy | Cells |
|---|---:|
| MD2G_COMPONENT | 27 |
| HV3_COMPONENT (Heuristic) | 27 |
| CLUSTERING_COMPONENT | 27 |
| RULE_COMPONENT | 27 |
| MOQ_UNICAST_COMPONENT | 27 |

**Rolling:** no same-substrate live Rolling in this matrix. Rolling in ToN is Cast/DASH unicast. Launching DASH Rolling would violate “same MoQ relay and client.” Primary fair table = live MD2G / live MCG / live Heuristic / live Clustering. Rolling may appear only as `CAST_HANDBOOK_NOT_SAME_SUBSTRATE` (command82), never as a fair MoQ baseline.

## 6. Minimum missing experiment

27 live cells only:

`MCG_COMPONENT` × Red-and-Black × 20/60/100 × 4G/WiFi/Fiber × seeds 151/152/153.

Reuse frozen live MD2G/HV3/Clustering for the same slice. Do not rerun 945. Do not unseal Loot. Do not modify MD2G-Cast or U weights.

Art root (new): `artifacts/ton_live_mcg/`
Queue: `state/COMMAND_TON_LIVE_MCG_QUEUE.json`
Outputs: `results/live_mcg_baseline/`
