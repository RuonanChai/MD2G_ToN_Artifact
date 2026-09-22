# ROLLING_EXECUTION_AUDIT — SIGCOMM offline (command36 §3.5)

**Status:** code path located; model dependency recorded; no Mininet run until exclusive gate.

## Source

| Item | Path |
|------|------|
| Strategy class | `DASH/Rolling/rolling_drl_strategy_v2_refined.py` (also imported from repo patterns) |
| Weights | `DASH/Rolling/sc_ddqn_rolling.pth` / `trained_models/sc_ddqn_rolling.pth` |
| Entry | `regional_relay_controller.py` → `strategy == 'rolling'` → SC-DDQN server-side inference |
| Cluster launcher (this campaign) | `moq_cluster_Sigcomm.py --strategy rolling` |

## Transport / architecture

- Classified as **unicast / independent-delivery** reference.
- Per-user streams via r1/r2; not MoQ multicast grouping.
- Must not be described as isolating “only PPO” or “only multicast” when compared to MD2G.

## Adaptation logic

- SC-DDQN Q-value enhanced-level decisions on the shared Rep ladder.
- Requires valid `.pth` under `--model_path` / `trained_models`; missing weights is a hard failure for acceptance cells (no silent random fallback in final evidence).

## Outputs / failure modes

- Decision JSON on `/tmp/r{1,2}_decisions.json`.
- Failure modes: missing model, cold-start throughput collapse, excluded TTFB attempts (must remain in denominator).

## Fairness

See `UNICAST_BASELINE_FAIRNESS_CONTRACT.json`. Match duration, users, traces, FoV, seeds, and Table-1 quality mapping with MD2G/Heuristic/Clustering/GROOT cells.
