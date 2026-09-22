# METRIC_DEFINITION_CONTRACT — SIGCOMM MD2G-Cast (paper v4)

Source: `Sigcomm26/MD2G_Sigcomm_submit version4.pdf`  
Binding: command33 + command34 + command36 (command35 superseded).

## Baseline labels in metrics/plots

- MoQ multicast: MD2G, Heuristic, Clustering  
- Unicast/system references: Rolling, **GROOT** (replaces DASH-PC; never relabel DASH-PC data)

## QoE (reported)

Paper Eq.9: `R_q = α·Q_s − β·D_n − γ·S_n` with `α=1`, `β=γ=0.5`,
`Q_s ∈ {0.4,0.6,0.8,1.0}` ↔ Q1–Q4 from **final executed Rep ID** (Table 1).

Unified reward Eq.7: `R_t = λ_o R_o + λ_q R_q − λ_b R_b` (grouping / quality / bandwidth).

**Implementation:** set `SIGCOMM_QOE_EQ9=1` on `dispatch_strategy_enhanced_unified_Sigcomm.py`. Do not use ENH004/ToN BaseGuard admission ratios as correctness criteria. Do not use MM26 `0.6+0.4*enh/2` as paper QoE.

## TTFB

Subscription/init request → first media payload. CDFs include failed initialization attempts in the denominator (Fig.6/13).

## Data Arrival Interval

Receiver-side media-object arrival spacing (fluidity axis of Fig.5/12).

## Buffer

Seconds of playable media; Fig.7 averages across users/trials.

## Stall

Fig.8a stall evolution over 0–120 s. Cumulative stall cannot decrease; if a curve decreases, it is mislabeled instantaneous/backlog and must be corrected.

## Throughput

System aggregate Mbps at a single agreed boundary for all five strategies.

## CPU

Percent CPU; values >100% are multi-core sums and must be labeled consistently.

## PSNR/SSIM (Table 4 / Fig.11)

Rep 3 (base) vs Rep 5 (refinement) on Red and Black.

## Representation selection

Action `A_t = {G_{t+1}, r_{b,t}, q_{e,t}(u)}`. Higher-fidelity Rep 4–9 share emerges from policy + feasibility; **no fixed enh_admit target**.
