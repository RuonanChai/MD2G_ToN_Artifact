# User_Experience_Trade-off folder — figure-family honesty

## Fig.4-style fluidity–QoE trade-off (arrival interval vs QoE)

**FAIL CLOSED.** Evidence gap: `EVIDENCE_GAP_FIG4_TRADEOFF.json`.

Original Sigcomm grammar requires:
- X = Average Data Arrival Interval (ms)
- Y = Average QoE

Frozen VALID `delay_ms` in perf.csv is unimplemented zero; final contract marks delay as
`NOT_IN_FINAL_CLAIM_CONTRACT`. Emitting a Fig.4-lookalike with substituted axes is forbidden.

## What *is* in this folder

1. **Tier-B mechanism scatters** (`User_Experience_Trade-off_*.pdf` from `plot_tradeoff_*.py`):
   Rb vs \(U\) per network — **scatter grammar**, grounded in frozen Rb/U, **not** Fig.4.
2. **H2 cross-stack** (`H2_Cross_Stack_DASH.pdf`): secondary only.

Do not caption the Rb–U scatters as “Fluidity–QoE Trade-off”.
