# METRIC_CONTRACT_GATE — SIGCOMM offline sign-off draft (command34 §6 / command36 §3.4)

Status: **SIGNED_OFF** for pre-launch contract definitions. Runtime validation still required per cell after Mininet exclusive lock.

## Resolved definitions (paper campaign)

| Metric | Definition | Notes |
|--------|------------|-------|
| QoE `R_q` | Eq.9: `Q_s - 0.5 D_n - 0.5 S_n`, `Q_s` from **final Rep ID** via Table 1 | Enable `SIGCOMM_QOE_EQ9=1`. MM26 five-component is **not** paper QoE. |
| `Q_s` | Rep→{0.4,0.6,0.8,1.0} | See `test_qoe_eq9_rep_map.py` |
| Data Arrival Interval | Receiver media-object inter-arrival (fluidity) | Fig.5/12 x-axis |
| TTFB | Request→first payload; **failed inits stay in CDF denominator** | Fig.6/13 |
| Buffer | Playable media seconds | Fig.7 |
| Stall (Fig.8) | Must be a **non-decreasing cumulative** stall-time series **or** explicitly labeled instantaneous/backlog; never plot a decreasing “cumulative stall” | Audit plot script before acceptance |
| Throughput | Single agreed aggregation boundary for all five strategies | Same boundary MD2G/Heuristic/Clustering/Rolling/GROOT |
| CPU | Multi-core sum may exceed 100%; label as such | Fig.10 |
| Object looping | 1s Rep files looped for 120s live; no repeated TTFB accounting per loop | Live assets under `redandblack_6_live` |

## Open runtime checks (post-cell)

- Confirm Fig.8 series monotonicity or rename metric.
- Confirm throughput NIC/process boundary identical across strategies.
- Confirm GROOT/Rolling failure rows retained in TTFB denominators.

SIGNED_OFF: 2026-07-22 (definitions only; does not certify experimental numbers)
