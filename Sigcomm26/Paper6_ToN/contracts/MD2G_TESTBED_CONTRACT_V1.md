# MD2G_TESTBED_CONTRACT_V1

- Created: `2026-07-26T06:57:22.955610-05:00`
- Contract SHA256: `c918673b29bc1a3f9db8717b5950bab48c878b578680e4a35dd98ac0566259da`
- Runtime fingerprint SHA256: `2723b33f9519d31158812ec348a9304860936598da4d78fe1cd91f64c91c63de`

## Topology (MoQ shared)

- n0 publisher → r0 root relay → {r1,r2} leaf relays → users (≈half each)
- Access: per-user TCLink + network traces; HTB queues (max_queue_size 1000–2000)

## Topology (DASH unicast)

- Authentic Rolling/GROOT path via DASH HTTP (`run_authentic_unicast_baseline_cell.py`)
- MoQ shared-track Rolling/GROOT is INVALID for unicast claims

## Media

- Red and Black `video/redandblack_6_live` Rep1–9 H.264; duration 120s; interval 1.0s
- Q map: Q1={3,8,9}, Q2={2,6}, Q3={1,7}, Q4={4,5}

## Baseline taxonomy

- **md2g**: relay-coordinated shared delivery over MoQ
- **heuristic**: relay-coordinated shared delivery over same MoQ substrate
- **clustering**: relay-coordinated shared delivery over same MoQ substrate
- **rolling**: per-user DASH/HTTP unicast (TRANSPORT_ADAPTED / Rolling-inspired) — MoQ shared path INVALID
- **groot**: GROOT-inspired per-user DASH/HTTP unicast — MoQ shared path INVALID

## Cell validity

- `exit=0` is never sufficient
- strategy_fingerprint
- expected_processes
- launched_user_count
- per_user_perf_logs
- sustained_payload
- duration_coverage
- denominator_completeness
- no_cross_cell_reuse
- scoped_cleanup
- raw_summary_reproducibility
- correct_hashes

## Prohibited

- mn -c while other campaign cells live
- broad pkill/killall across unrelated moq/ton processes
- global OVS reset mid-cell
- deleting shared /tmp across cells
- changing trace/seed mid-campaign
- editing completed cell summaries
- excluding failed users from denominators
- changing metric weights after seeing holdout
- relabeling baseline without source evidence
- reusing contaminated holdout for final claims
- launching Rolling/GROOT via moq_cluster without SIGCOMM_ALLOW_MOQ_SHARED_BASELINES diagnostic override
- proceeding with runtime that differs from frozen testbed hash without new contract version
