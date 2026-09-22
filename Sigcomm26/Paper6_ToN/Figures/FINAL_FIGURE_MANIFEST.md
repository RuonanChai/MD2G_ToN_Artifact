# FINAL_FIGURE_MANIFEST

Token: `PAPER_FINALIZATION_FIGURES_READY`
Visual redesign: `TON_FINAL_FIGURE_VISUAL_REDESIGN_READY`
Audit: `FIGURE_VISUAL_REDESIGN_AUDIT.md` (diagnostic contact sheet is not a paper figure)

Filenames are unchanged. Chart **family** changed in place; scientific values did not.

| PDF | Old family | New family | Uncertainty |
|---|---|---|---|
| `QoE/QoE_By_Strategy.pdf` | grouped bar mean±SD | box + mean (1.5 IQR) | distribution; diamond = mean |
| `Buffer Level/System_Utility_By_Users_scheme1.pdf` | grouped bar | multi-line point-range (u=10…100) | sample SD |
| `Buffer Level/System_Utility_By_Users_MainDev.pdf` | grouped bar | slope / point-range (u=20/60/100) | sample SD |
| `QoE/QoE_By_Content_DeltaU.pdf` | grouped bar | horizontal forest | **bootstrap 95% CI** (seed 153, n=10000) |
| `QoE/QoE_By_Network.pdf` | strategy bars | diverging heatmap net×load | mean ΔU; outline iff CI excludes 0 |
| `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | grouped bar | line + point-range ΔU | **bootstrap 95% CI** + W/T/L |
| `QoE/Mechanism_Decomposition_Loot.pdf` | independent bars | signed stacked utility decomposition | algebraic overlay of observed ΔU |
| `QoE/MoQ_Shared_vs_Unicast.pdf` | two U bars | dumbbell U/Rq/Ro/Rb | frozen strategy means |
| `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | grouped bar | two-point line (cross-stack diagnostic) | sample SD |
| `Throughput/System_Throughput_Bar_{4G,5G,Default_Mix}.pdf` | grouped bar | multi-line TX scaling (name keeps Bar) | sample SD |
| `QoE/Weak_User_Rq_Loot.pdf` | grouped bar | paired lines vs strongest same-substrate | sample SD |
| `User_Experience_Trade-off/TierB_Rb_vs_U_*.pdf` | scatter | polished trade-off scatter | N/A |

Plot scripts: 26
PDF refs listed: 62

## Emitting scripts

### `Buffer Level/plot_buffer_level_by_strategy.py`
- `Buffer Level/Buffer_Level_By_Strategy_scheme1.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme1.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme2.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme3.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme4.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme5.pdf`
- `Buffer Level/System_Utility_By_Users_MainDev.pdf`
- `Buffer Level/System_Utility_By_Users_scheme1.pdf`
- `Buffer Level/System_Utility_By_Users_scheme2.pdf`
- `Buffer Level/System_Utility_By_Users_scheme3.pdf`
- `Buffer Level/System_Utility_By_Users_scheme4.pdf`
- `Buffer Level/System_Utility_By_Users_scheme5.pdf`
- `Buffer Level/Buffer_Level_By_Users_scheme1.pdf`

### `Buffer Level/plot_buffer_level_by_users.py`
- `Buffer Level/Buffer_Level_By_Users_scheme1.pdf`
- `Buffer Level/System_Utility_By_Users_scheme1.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme1.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme2.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme3.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme4.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme5.pdf`
- `Buffer Level/System_Utility_By_Users_MainDev.pdf`
- `Buffer Level/System_Utility_By_Users_scheme2.pdf`
- `Buffer Level/System_Utility_By_Users_scheme3.pdf`
- `Buffer Level/System_Utility_By_Users_scheme4.pdf`
- `Buffer Level/System_Utility_By_Users_scheme5.pdf`
- `Buffer Level/Buffer_Level_By_Strategy_scheme1.pdf`

### `Buffer Level/plot_maindev_utility_by_users.py`
- `Buffer Level/System_Utility_By_Users_MainDev.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme1.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme2.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme3.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme4.pdf`
- `Buffer Level/System_Utility_By_Strategy_scheme5.pdf`
- `Buffer Level/System_Utility_By_Users_scheme1.pdf`
- `Buffer Level/System_Utility_By_Users_scheme2.pdf`
- `Buffer Level/System_Utility_By_Users_scheme3.pdf`
- `Buffer Level/System_Utility_By_Users_scheme4.pdf`
- `Buffer Level/System_Utility_By_Users_scheme5.pdf`
- `Buffer Level/Buffer_Level_By_Strategy_scheme1.pdf`
- `Buffer Level/Buffer_Level_By_Users_scheme1.pdf`

### `QoE/plot_loot_holdout_delta_u.py`
- `QoE/Loot_Holdout_DeltaU_By_Users.pdf`

### `QoE/plot_mechanism_decomposition_loot.py`
- `QoE/Mechanism_Decomposition_Loot.pdf`

### `QoE/plot_moq_shared_vs_unicast.py`
- `QoE/MoQ_Shared_vs_Unicast.pdf`

### `QoE/plot_qoe_by_content_delta.py`
- `QoE/QoE_By_Content_DeltaU.pdf`

### `QoE/plot_qoe_by_network.py`
- `QoE/QoE_By_Network.pdf`

### `QoE/plot_qoe_by_strategy.py`
- `QoE/QoE_By_Strategy.pdf`

### `QoE/plot_weak_user_rq_loot.py`
- `QoE/Weak_User_Rq_Loot.pdf`

### `Stall Time/plot_stall_time_by_network.py`
- `Stall Time/Stall_Time_By_Network.pdf`

### `Stall Time/plot_stall_time_by_strategy.py`
- `Stall Time/Stall_Time_By_Strategy.pdf`

### `Stall Time/plot_stall_time_by_users.py`
- `Stall Time/Stall_Time_By_Users.pdf`

### `Throughput/plot_throughput_4g.py`
- `Throughput/System_Throughput_Bar_4G.pdf`

### `Throughput/plot_throughput_5g.py`
- `Throughput/System_Throughput_Bar_5G.pdf`

### `Throughput/plot_throughput_5g_dominant.py`
- `Throughput/System_Throughput_Bar_5G_Dominant.pdf`

### `Throughput/plot_throughput_default_mix.py`
- `Throughput/System_Throughput_Bar_Default_Mix.pdf`

### `Throughput/plot_throughput_fiber_optic.py`
- `Throughput/System_Throughput_Bar_Fiber_Optic.pdf`

### `Throughput/plot_throughput_wifi.py`
- `Throughput/System_Throughput_Bar_Wifi.pdf`

### `Throughput/plot_throughput_wifi_dominant.py`
- `Throughput/System_Throughput_Bar_Wifi_Dominant.pdf`

### `User_Experience_Trade-off/plot_h2_cross_stack_dash.py`
- `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf`

### `User_Experience_Trade-off/plot_tradeoff_4g.py`
- `User_Experience_Trade-off/TierB_Rb_vs_U_4G.pdf`

### `User_Experience_Trade-off/plot_tradeoff_5g.py`
- `User_Experience_Trade-off/TierB_Rb_vs_U_5G.pdf`

### `User_Experience_Trade-off/plot_tradeoff_default_mix.py`
- `User_Experience_Trade-off/TierB_Rb_vs_U_Default_Mix.pdf`

### `User_Experience_Trade-off/plot_tradeoff_fiber_optic.py`
- `User_Experience_Trade-off/TierB_Rb_vs_U_Fiber_Optic.pdf`

### `User_Experience_Trade-off/plot_tradeoff_wifi.py`
- `User_Experience_Trade-off/TierB_Rb_vs_U_WiFi.pdf`

## Fail-closed audits

- `TTFB/EVIDENCE_GAP_TTFB.json`
- `Stall Time/EVIDENCE_GAP_CONTINUITY_TIMESERIES.json`
- `User_Experience_Trade-off/EVIDENCE_GAP_FIG4_TRADEOFF.json`
- `Buffer Level/README_METRIC_HONESTY.md`
