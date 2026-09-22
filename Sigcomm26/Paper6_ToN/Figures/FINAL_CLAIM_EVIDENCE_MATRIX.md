# FINAL claim-evidence matrix

Terminal: `TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B`

## C001: SUPPORTED
- **Claim:** Nested incremental component contract is the scientific media contract.
- **Source:** `final/COMMAND153_CLAIM_EVIDENCE_MATRIX.json`
- **Value:** SUPPORTED
- **Figure:** N/A

## C002: UNSUPPORTED
- **Claim:** MD2G strictly dominates all same-substrate baselines on every block.
- **Source:** `final/COMMAND153_MATCHED_BLOCKS.csv`
- **Value:** u20 mean -0.137
- **Figure:** fig_maindev_utility_by_users.pdf
- **Limitation:** Low concurrency is an explicit limitation (Tier B).

## C003: LIMITED
- **Claim:** MD2G shows robust benefit at medium/high concurrency (u>=60).
- **Source:** `final/COMMAND153_FIGURE_SOURCE_DATA/loot.json`
- **Value:** u60 0.083, u100 0.111
- **Figure:** fig_loot_holdout_delta_u.pdf
- **Limitation:** Unseen Loot content; not universal dominance.

## C004: SUPPORTED
- **Claim:** Concurrency crossover: low u10/u20 unfavorable, u40 transition, u60/u100 favorable.
- **Source:** `final/COMMAND153_FIGURE_SOURCE_DATA/scaling.json`
- **Value:** u10 -0.069, u20 -0.049, u40 0.018, u60 0.088, u100 0.115
- **Figure:** fig_concurrency_crossover.pdf
- **Limitation:** 150 logical keys = 90 DEV reuse + 60 new launches.

## C005: LIMITED
- **Claim:** Benefit primarily associated with decoded-quality (Rq) gain at high concurrency.
- **Source:** `final/COMMAND153_HOLDOUT_STATS.json`
- **Value:** Loot MD2G Rq=0.760
- **Figure:** fig_mechanism_decomposition.pdf
- **Limitation:** Ro similar across strategies; Rb not bandwidth-saving claim.

## C006: SUPPORTED
- **Claim:** Shared MoQ MD2G vs MOQ unicast delivery-mode comparison.
- **Source:** `final/COMMAND153_PRIMARY_STATS.json`
- **Value:** MD2G 0.688 vs unicast 0.194
- **Figure:** fig_moq_shared_vs_unicast.pdf
- **Limitation:** Delivery-mode only; not same-substrate controller baseline.

## C007: LIMITED
- **Claim:** H2 GROOT/Rolling cross-stack secondary comparison.
- **Source:** `artifacts/command153_cross_stack_dash/*/CELL_DONE.json`
- **Value:** secondary cross-stack only
- **Figure:** fig_h2_cross_stack_dash.pdf
- **Limitation:** Not primary same-substrate evidence; do_not_use_as_primary_md2g_vs_baseline.

## C008: UNSUPPORTED
- **Claim:** A1-A5/A7 ablations and FoV validate controller mechanisms.
- **Source:** `final/COMMAND153_ABLATION_STATS.json`
- **Value:** NA
- **Figure:** none
- **Limitation:** Do not plot NA as experimental validation.
