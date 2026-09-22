# BASELINE_TAXONOMY_CONTRACT — SIGCOMM (command36 binding)

Authority: `command36.txt` §1 (supersedes command35). Do not execute command35.

## MoQ multicast / relay-side methods

| Name | Role |
|------|------|
| MD2G (MD2G-Cast) | Learning-based relay-side grouping + representation selection |
| Heuristic | MoQ multicast controlled baseline (joint optimization) |
| Clustering | MoQ multicast controlled baseline (predictive clustering) |

These three share the MoQ relay/multicast substrate and are the **primary controlled comparisons** for relay-side design attribution.

## Unicast / independent-delivery system references

| Name | Role |
|------|------|
| Rolling | Unicast / independent-delivery DRL baseline (SC-DDQN) |
| GROOT | Unicast / independent-delivery volumetric baseline (replaces DASH-PC) |

Rolling and GROOT **must not** be described as MoQ multicast baselines.

MD2G vs Rolling/GROOT changes multiple system dimensions (transport, delivery model, controller). Treat as **system-level references**, not single-factor causal isolation.

## DASH-PC → GROOT replacement rules

- Remove DASH-PC / PCC-DASH from active SIGCOMM evaluation matrices, legends, captions, prose, and claims.
- Use the real available implementation: `strategies/groot_controller.py` (entry via `regional_relay_controller.py --strategy groot`), with `DASH/GROOT/groot_controller.py` retained as design reference only.
- **Never rename** historical DASH-PC / PCC-DASH result directories as GROOT.
- Do **not** invent a “GROOT integration contribution” in the paper.
- Runtime entry for this campaign: repo-root `moq_cluster_Sigcomm.py` + `dispatch_strategy_enhanced_unified_Sigcomm.py` with Red-and-Black Rep 1–9 (`SIGCOMM_VIDEO_DIR`, `SIGCOMM_REP_LADDER=1`).
- Do **not** contaminate ToN/ENH004: leave `Sigcomm26/moq_cluster_Sigcomm26.py` media and orchestrator alone.

## Fairness pointer

See `UNICAST_BASELINE_FAIRNESS_CONTRACT.json`.
