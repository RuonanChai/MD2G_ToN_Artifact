# GROOT_EXECUTION_AUDIT — SIGCOMM offline (command36 §3.5)

**Status:** code path located; peak-rate bug gated; no Mininet run until exclusive gate.

## Source

| Item | Path |
|------|------|
| Runtime controller (used by regional_relay) | `strategies/groot_controller.py` |
| Design-reference / fuller DASH-oriented impl | `DASH/GROOT/groot_controller.py` |
| Historical DASH runner (legacy absolute paths) | `DASH/` runner scripts (**not** used for this campaign) |
| Entry | `regional_relay_controller.py` → `strategy == 'groot'` → `run_groot_controller` |
| Cluster launcher (this campaign) | repo-root `moq_cluster_Sigcomm.py --strategy groot` |

## Transport / architecture

- Classified as **unicast / independent-delivery** reference (command36 §1.2).
- In this testbed, GROOT decisions run on edge relays (r1/r2) with **per-user independent streams** (same unicast wiring as Rolling), not MoQ multicast grouping.
- Must **not** be labeled a MoQ multicast baseline in figures, captions, or prose.
- No “GROOT integration contribution” narrative.

## Decision semantics

- Output: `{decisions: {uid: {pull_enhanced: bool, debug_info: {...}}}}`
- Dispatch maps `pull_enhanced` → enhanced_level / Rep via `map_to_rep_id` (Rep1–9 ladder).
- FoV/distance LOD score is stochastic under a seeded RNG inside the controller; fairness requires matched seeds across trials.

## Critical capacity-model finding (pre-repair)

Default constants in `strategies/groot_controller.py` were `UNICAST_BASE_PEAK_MBPS=19.5` and `UNICAST_ENH_PEAK_MBPS=32.0` (aligned to **Sigcomm26 PC media**, not Red-and-Black Table 1).

Under Table 1 rates (Rep3≈0.87 … Rep5≈6.42 Mbps), those thresholds would make enhancement admission **scientifically invalid** for this paper.

**Repair (env-gated, ToN-safe):** set `SIGCOMM_REP_LADDER=1` so peaks become Table-1-aligned `(0.87, 6.42)` with margin `0.25`. Default remains 19.5/32 for ToN/ENH004 callers that omit the flag.

## Forbidden

- Renaming any DASH-PC / PCC-DASH artifact tree as GROOT.
- Using `Sigcomm26/moq_cluster_Sigcomm26.py` PC media for SIGCOMM paper Figs 5–14.
- Copying numerical results from `MM26/rebuttal` or historical Log_* groot folders into paper tables.

## Dependencies

- Python 3, no torch required for GROOT path.
- Needs `host_network_mapping.csv` / access-link bandwidth for fair admission.
- Shared media: `SIGCOMM_VIDEO_DIR/.../redandblack_6_live` Rep1–9.
