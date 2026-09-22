# SKIPPED figures (fail-closed after raw VALID audit)

Audited frozen VALID `client_*_perf.csv` under:
- `artifacts/command148_canary120_rbv1` (122 cells)
- `artifacts/command148_maindev` (sample 265–300 cells with perf)

Also checked `COMPONENT_RECEIPT.jsonl` (ts/dump_bytes only; no first-byte field) and
`final/COMMAND153_PRIMARY_STATS.json` (`delay=NOT_IN_FINAL_CLAIM_CONTRACT`,
`never_claim_zero_stall=true`).

| Target Sigcomm family | Why skipped | Audit artifact |
|---|---|---|
| **Fig.4-style fluidity–QoE trade-off** (arrival interval ms vs QoE scatter) | X-axis `delay_ms` is unimplemented **0** in audited VALID perf.csv; cannot ground Fig.4 axes. Y-axis U/Rq alone is insufficient. | `User_Experience_Trade-off/EVIDENCE_GAP_FIG4_TRADEOFF.json` |
| **Fig.5-style TTFB CDF** | `ttfb_*_ms` columns exist but are **0** across canary (122/122) and MAINDEV sample (265/265). Receipts lack first-byte timing. | `TTFB/EVIDENCE_GAP_TTFB.json` |
| **Fig.7/8-style Continuity vs Recovery timeseries** | `stall_total_sec` flat/zero; no truthful cumulative continuity curve. Only scalar `stall_last` (decode-gap). | `Stall Time/EVIDENCE_GAP_CONTINUITY_TIMESERIES.json` |
| **True Buffer Level (buffer_level_sec)** | `buffer_level_sec` identically 0 in audited VALID perf. | `Buffer Level/README_METRIC_HONESTY.md` |
| **CPU usage / FoV trap** | Outside frozen final claim package / NOT_APPLICABLE. | (prior SKIPPED note; not re-audited as required Fig.4/5/7) |

**Not skipped (supported):** Tier-B U distribution/crossover lines, matched ΔU forest/heatmap/point-range, utility decomposition, shared vs unicast dumbbell, shared-root TX scaling lines (filenames still `System_Throughput_Bar_*`), supporting scalar stall_last bars, Tier-B Rb–U scatters (explicitly *not* Fig.4).
