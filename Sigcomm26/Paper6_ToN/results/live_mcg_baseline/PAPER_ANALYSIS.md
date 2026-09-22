# Live MCG paper-facing analysis

Status: 27/27 VALID, fairness PASS, 2026-09-09. Same Mininet/MoQ/metrics/validators as COMMAND153. Frozen U `clip(0.25 Ro + 0.60 Rq - 0.15 Rb, 0, 1)`. MD2G-Cast / PPO unmodified.

## Headline (Red-and-Black × 4G/WiFi/Fiber × 20/60/100 × seeds 151–153)

| Strategy | U@20 | U@60 | U@100 | Grand U (n=27) | Cell 1sts |
|---|---:|---:|---:|---:|---:|
| MD2G-Cast | 0.506 | 0.760 | 0.766 | 0.677 | 18 |
| Clustering | 0.636 | 0.672 | 0.641 | 0.650 | 6 |
| MCG live | 0.604 | 0.588 | 0.463 | 0.552 | 3 |
| Heuristic | 0.582 | 0.573 | 0.497 | 0.551 | 0 |

Paired MD2G wins vs MCG / Heuristic / Clustering: 2/9 / 1/9 / 0/9 at 20 users; **9/9 / 9/9 / 9/9 at 60 and 100**.

Rolling handbook U 0.007 / 0.027 / 0.020 is **not** same-substrate.

Offline MCG (~0.42) is **not** a baseline (empty decoded labeled Rep1). Cite live numbers only.

Figure: `live_mcg_utility_vs_users.pdf`.
