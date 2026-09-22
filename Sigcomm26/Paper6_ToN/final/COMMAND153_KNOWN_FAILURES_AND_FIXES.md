# COMMAND153 known failures and certified fixes

Immutable. Supervisor must read this ledger before every repair.

## E001_WRONG_MEDIA_CONTRACT

- status: `FROZEN_LESSON`
- symptom: Standalone Rep1–Rep9 treated as transport assets
- root_cause: command100–145 used independent full representations
- repair: Physical media is nested b0/db1/db2/e1/e2; Rep1–9 are decoded compositions
- recertification: COMMAND147_COMPONENT_ASSETS_FULLY_SCIENTIFICALLY_CERTIFIED
- do_not_repeat: Never put command100–145 numbers in final U/CI/headline

## E002_TEMPORAL_BITRATE_DURATION_FALLACY

- status: `FROZEN_LESSON`
- symptom: Bitrate inferred from 120s wall time or unique-clip bytes/120s
- root_cause: Wrong temporal contract
- repair: Use frozen command147 timing/bitrate contract only
- recertification: COMMAND147_TEMPORAL_BITRATE_FROZEN
- do_not_repeat: Never divide one-pass unique-clip bytes by 120s

## E003_REP_ID_AS_QUALITY

- status: `FROZEN_LESSON`
- symptom: Rq ranked by Rep ID
- root_cause: Rep ID is not Q
- repair: Rq from actually decoded state + frozen Q_norm
- recertification: COMMAND147_COMPONENT_QUALITY_FROZEN
- do_not_repeat: Never use Rep ID as quality

## E004_CUMULATIVE_MARGINAL_COST

- status: `FROZEN_LESSON`
- symptom: DeltaR counted full target prefix
- root_cause: Wrong missing-component cost
- repair: DeltaR(target|A_g)=sum rate of missing components only
- recertification: command149 missing-component semantics
- do_not_repeat: Never charge already-held components again

## E005_UNAUTHORIZED_OVERDELIVERY

- status: `FROZEN_LESSON`
- symptom: Clients subscribed outside receiver set / stale dumps after CLOSE
- root_cause: Missing component_receivers ∩ closure
- repair: Subscribe only closure∩receivers; CLOSE removes stale dump state
- recertification: fail-closed unauthorized=0
- do_not_repeat: Never leave dumps for components outside current receiver set

## E006_MISSING_PERF_CSV

- status: `FROZEN_LESSON`
- symptom: Canonical VALID without expected perf files
- root_cause: Incomplete expected-client artifacts
- repair: VALID requires complete expected perf.csv set
- recertification: command148_canary_audit perf_files
- do_not_repeat: Never promote a cell missing expected client perf files

## E007_MISSING_STUDENT_SIDECAR

- status: `FROZEN_LESSON`
- symptom: MD2G_COMPONENT without COMMAND148_STUDENT_INFERENCE.jsonl
- root_cause: Treatment not actually Student
- repair: Preflight must prove sidecar/model loaded; class INVALID_TREATMENT
- recertification: command148_canary_audit student_inference
- do_not_repeat: Never treat missing Student as a V2 controller problem

## E008_RB_PLACEHOLDER_ZERO

- status: `FROZEN_LESSON`
- symptom: U used Rb=0 projection / 1-Ro / B_shared as pressure
- root_cause: Placeholder Rb
- repair: Rb = clip(P95((u_t-idle_floor)/(1-idle_floor)),0,1) on r0-eth1 TX 1s protocol-inclusive
- recertification: COMMAND151_RB_LOWLOAD_NEARCAP_CERT_PASS
- do_not_repeat: Never use pre-Rb 56-cell U in final tables; Rb is not volume and not 1-Ro

## E009_NULL_HEADLINE_METRICS

- status: `FROZEN_LESSON`
- symptom: VALID row with null/nonfinite U/Ro/Rq/Rb/B_shared/B_unicast
- root_cause: Missing aggregator or placeholder JSON null
- repair: finite_headlines fail-closed
- recertification: INVALID_HEADLINE_NONFINITE
- do_not_repeat: Never keep numeric placeholders that look measured

## E010_STALL_DELAY_PLACEHOLDER

- status: `FROZEN_LESSON`
- symptom: stall_last=0 UNIMPLEMENTED_PLACEHOLDER read as zero stall; delay tails invented
- root_cause: Placeholder scientific fields
- repair: stall=DECODE_GAP_SECONDS_POST_WARMUP supporting not in U; delay NOT_IN_FINAL_CLAIM_CONTRACT
- recertification: COMMAND152_FINAL_METRIC_COMPLETENESS_PASS
- do_not_repeat: Never claim zero stall or delay tails unless a later frozen contract says so

## E011_S2_B0_RETRY_STRIPPED_ANON

- status: `FROZEN_LESSON`
- symptom: c147smoke_S2_B3_E1_E2_4g_s142 decode_validity=false; h1/h2 b0=0 while db1/db2 existed
- root_cause: First b0 subscription used /anon/; retry stripped path to / and failed auth
- repair: Every retry preserves the complete /anon/ path byte-for-byte via canonical_subscriber_url
- recertification: test_moq_sub_retry_preserves_anon; repaired exact key PASS 14/24 then continued S2
- do_not_repeat: Never misclassify this known runtime defect as physical/policy B/C; preserve attempt1 forever

## E012_EXECUTOR_DUPLICATION

- status: `FROZEN_LESSON`
- symptom: Second Mininet or command148_orch independent launch after SSH reconnect
- root_cause: Multiple orchestrators launching cells
- repair: tmux:command152_orch sole launcher; command148_orch yields; atomic SCIENTIFIC_EXECUTOR.lock
- recertification: COMMAND152_LAUNCH=1 required when COMMAND152_ACTIVE
- do_not_repeat: Never kill a healthy live cell to restart orchestration; never duplicate canonical keys

## E013_S3_RETRY_KILLS_LIVE_SUBSCRIBE

- status: `FROZEN_LESSON`
- symptom: c147smoke_S3_mixed_share_4g_s141 decode_validity=false; h2 b0=0/db2=0 while db1/e1 existed; retries kept /anon/
- root_cause: 5s empty-dump monitor terminated a live connected /anon/ subscribe; wrapper exited; nested client re-OPEN truncated gst log. Not lesson E011 path strip. Not 4g structural (command147 same key decoded Rep8).
- repair: should_restart_dead_subscriber: never kill a live process; retry only if subscriber already died; retry URL still /anon/ byte-for-byte
- recertification: test_moq_sub_retry_preserves_anon.test_never_kill_live_subscriber
- do_not_repeat: Do not reuse E011 as if /anon/ were stripped; do not label this B/C; preserve attempt1

## E014_S3_CONCURRENT_SUBSCRIBE_B0_DUMP_ZERO

- status: `FROZEN_LESSON`
- symptom: After E013 fix, S3 mixed_share 4g s141 still decode_validity=false; some user b0=0 while incrementals >0; gst subscribe started; RETRY=0; OPEN b0=1. Victim host is not stable (h2 then h1).
- root_cause: nested client opened all wanted components in the same tick; concurrent moq-sub burst left a live /anon/ subscribe with dump=0. Not E011 path strip. Not E013 live-kill. Not 4g/policy: peer users decode and incrementals arrive.
- repair: ordered_open_batches: start b0 first; wait until dump>64 or timeout; then stagger incrementals. Never kill a live b0 subscribe (E013).
- recertification: test_nested_client_b0_first; exact-key S3 rerun after E013 exhausted
- do_not_repeat: Do not reuse E013 after gst shows subscribe-started and zero RETRY; do not blind-retry a CONSUMED exact-key token; do not label this B/C

## E015_RQ_AUDIT_TARGET_FALLBACK

- status: `FROZEN_LESSON`
- symptom: HV3 rbv1 u20 4g s151 fail-closed INVALID_EXECUTION_OR_FIDELITY reason h6 Rq not frozen Q; h6 decoded_state=None all ticks with Rq=0
- root_cause: audit compared Rq against Q_norm[target] when decoded was None; nested client correctly sets Rq=0 for undecoded users. Not a controller retune. Weak-user non-decode is science, not execution failure.
- repair: Rq must match Q_norm[decoded] if decoded exists, else 0. Never fall back to target_state for expected Rq.
- recertification: audit_canary_cell Rq vs decoded-only; preserved HV3 attempt1
- do_not_repeat: Do not fail-close a cell because an undecoded user has Rq=0; do not credit target quality

## E016_FINITE_HEADLINES_SWALLOWED

- status: `FROZEN_LESSON`
- symptom: CLUSTERING rbv1 u20 4g s151 canary_cell rc=1 NameError finite_headlines at teardown audit
- root_cause: E015 expected_rq patch left finite_headlines body unreachable after return inside expected_rq; running process imported the broken module
- repair: Restore finite_headlines as its own function; unit-test that it is callable
- recertification: test_expected_rq_decoded_only.test_finite_headlines_is_a_real_function
- do_not_repeat: Never leave helper bodies after a return in expected_rq; recertify finite_headlines after any audit edit

## E017_SKIP_PING_ALL_WRONG_ENV_NAME

- status: `FROZEN_LESSON`
- symptom: rbv1 4g u60 MD2G s151 ran full Mininet pingAll despite MM26_SKIP_PING_ALL=1; O(N^2) ping on 60 hosts
- root_cause: moq_cluster_Sigcomm.py only read SKIP_PING_ALL; canary_cell set MM26_SKIP_PING_ALL and SIGCOMM_SKIP_PINGALL
- repair: Set SKIP_PING_ALL=1 in canary_cell; cluster honors MM26/SIGCOMM aliases. Do not kill the in-flight u60 cell.
- recertification: test_canary_skip_ping_all; next cell after live boundary must skip pingAll
- do_not_repeat: Never assume MM26_SKIP_PING_ALL is read by moq_cluster; command94 already recorded u60 pingAll hanging for days

## E018_FIVE_CELL_REPORT_READ_PRE_RB_ART

- status: `FROZEN_LESSON`
- symptom: command148_five_cell_report and canary_block_review still opened artifacts/command148_canary120 after rbv1 epoch, so orch n=25 means mixed pre-Rb diagnostic U
- root_cause: maybe_five_report still called command148 reporters whose ART was hardcoded to the pre-physical-pressure directory; overlapping keys exist in both trees
- repair: canary_rbv1_art() after COMMAND151_PHYSICAL_PRESSURE_RELEASE or epoch post_physical_pressure_rbv1; skip paper_U_is_Rb0_projection rows; command152_reports remains paper-facing
- recertification: test_canary_rbv1_art; next five-VALID report must include pre_rb_excluded and rbv1 art path
- do_not_repeat: Never read command148_canary120 for live rbv1 U/CI/headline or Level-2

## E019_GROOT_ROLLING_OMITTED_FROM_PRIMARY_CANARY

- status: `FROZEN_LESSON`
- symptom: GROOT_DASH and ROLLING_DASH are required secondary cross-stack baselines but were omitted from the command153 five-strategy primary V1/V2 matrix
- root_cause: command153 primary canary was frozen to MD2G/HV3/CLUSTERING/RULE/MOQ_UNICAST; DASH unicast baselines were not scheduled as a separate post-V1 branch
- repair: FUTURE-ONLY H2 CROSS_STACK_DASH_BASELINES after primary V1/V2 candidate freeze and before COMMAND153_FINAL_DEV_FROZEN / Loot unseal; freeze CROSS_STACK_DASH_MANIFEST first; authentic DASH/unicast only
- recertification: Do not add GROOT/ROLLING to the live rbv1 120; do not rerun current canary cells; primary claims remain vs strongest HV3/CLUSTERING/RULE
- do_not_repeat: Never inject GROOT/ROLLING into the current 120 V1/V2 gate; never treat them as same-substrate; never retrofit component-aware grouping/multicast/MD2G control into DASH; never fabricate DASH component reuse or a non-commensurate canonical U

## E020_TEARDOWN_R0_CMD_WAITING_SKIPS_CELL_VALIDITY

- status: `FROZEN_LESSON`
- symptom: cluster_CELL_VALIDITY.valid!=true / missing CELL_VALIDITY.json after a completed 120s nested window; stdout ends in Mininet AssertionError self.shell and not self.waiting on r0.cmd cat r0.log
- root_cause: command151 pressure sampler called r0.cmd from a daemon thread while the main thread also called r0.cmd after duration; Mininet node.cmd is not thread-safe; CELL_VALIDITY write is after post-run log cat so a teardown race skips the validity gate
- repair: Join the pressure thread after stop; use host_cmd_safe for post-run r0/r1/r2 log cat; exact-key retry the failed canary key once; do not skip the key or relabel as B/C
- recertification: exact-key retry writes CELL_VALIDITY.json; audit cluster_cell_validity true
- do_not_repeat: Never overlap Mininet node.cmd from the pressure thread with main-thread r0.cmd; never skip CELL_VALIDITY write because a post-run log cat asserted

## E021_DASH_H2_MISSING_COMMAND151_PRESSURE

- status: `FROZEN_LESSON`
- symptom: H2 GROOT/ROLLING cell has CELL_VALIDITY but PHYSICAL_PRESSURE_TIMESERIES.jsonl missing or <2 samples
- root_cause: DASH experiments had no command151 r0-eth1 sampler; a Python r0.cmd thread would also copy E020
- repair: In-netns r0.popen sampler writing PHYSICAL_PRESSURE_TIMESERIES.jsonl; H2 valid requires n_press>=2; summarize Rb separately; never r0.cmd from a DASH pressure thread
- recertification: H2 cell has >=2 pressure samples and PHYSICAL_PRESSURE_SUMMARY.json; CROSS_STACK stats do not enter primary U
- do_not_repeat: Never run H2 without frozen command151 r0-eth1 pressure; never sample DASH pressure via threaded r0.cmd; never treat DASH U as same-substrate

## E022_EXACT_KEY_REAUTHORIZE_INFINITE_RETRY

- status: `FROZEN_LESSON`
- symptom: After CONSUMED exact-key, classify rewrites AUTHORIZED for the same key+failure_id so H2/canary n_try grows past 3 without COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED
- root_cause: classify_and_repair dumped a fresh AUTHORIZED token on every failed-key tick; H2 treated auth as a bypass of n_try>=3
- repair: Refuse to re-AUTHORIZE the same key+failure_id after CONSUMED; a different failure_id on the same key may still authorize once; missing H2 media/ladder is fail-closed to COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED
- recertification: exact_key_already_consumed; n_try>=3 with no AUTHORIZED writes the terminal; H2 media missing writes the terminal
- do_not_repeat: Never let classify reset n_applied=0 on a CONSUMED same-key same-failure token; never retry an unchanged H2/canary key after three identical failures

## E023_DISK_FILL_FROM_RETAINED_DUMP_BINS

- status: `FROZEN_LESSON`
- symptom: /srv fills during long DEV/H2/holdout because VALID cells keep dump_*.bin after metrics/audit
- root_cause: dump bins are recomputable media captures retained after CELL_METRICS/CELL_AUDIT; not needed for final U/CI
- repair: After VALID CELL_DONE, unlink dump_*.bin in that cell; strip dumps from INVALID/diagnostic trees while keeping CELL_*/receipts/pressure/stdout; never delete live-cell files
- recertification: CELL_DONE+CELL_METRICS+audit remain; dumps absent post-VALID
- do_not_repeat: Never keep multi-GB dumps on completed VALID cells during a 945+ campaign; never delete evidence required for audit (receipts/perf/metrics)

## E024_MIXED_EPOCH_IN_CANONICAL_MATCHED_BLOCKS

- status: `FROZEN_LESSON`
- symptom: Final evidence package would mix cells stamped with different post-instrumentation epoch_id
- root_cause: No fail-closed check on epoch_id when assembling canary/DEV/scaling/loot rows
- repair: Stamp CELL_DONE with frozen epoch_id; evidence attaches freeze epoch and fail-closes COMMAND153_SCIENTIFIC_CONTRACT_BLOCKED on conflicts
- recertification: PRIMARY_STATS.epoch_id equals freeze; zero epoch_conflicts
- do_not_repeat: Never merge pre-Rb/diagnostic cells or foreign-epoch rows into final matched blocks

## E025_RAW_DUMP_RETENTION_CONTRACT

- status: `FROZEN_LESSON`
- symptom: Ad-hoc dump cleanup (incl. INVALID strip) risks unrecomputable decoded occupancy / component completion / B_shared lineage at final six-review
- root_cause: E023 reclaim treated dumps as disposable without a frozen retention contract or sentinel subset
- repair: Freeze retention contract: INVALID permanent; VALID hash+derived then delete; retain sentinel keys; launch-time free-space pause only (never interrupt live); supersedes E023 INVALID strip
- recertification: contract immutable; canary_cell uses reclaim_valid_dumps_if_allowed; main_dev launch_free_space_ok; no INVALID dump deletion scripts
- do_not_repeat: Never strip INVALID dumps; never delete VALID dumps without RAW_DUMP_MANIFEST; never interrupt live for yellow disk; never wait until 945 to discover raw dumps are required

## E026_NESTED_CLIENT_FINALLY_WIPES_DUMPS_BEFORE_RETENTION_GATE

- status: `FROZEN_LESSON`
- symptom: VALID cell finishes with RAW_DUMP_MANIFEST reason=NO_DUMPS even though dump_h*_*.bin existed mid-run; retention cannot hash raw payloads
- root_cause: command147_nested_client.stop() always os.remove(dump) and finally calls stop() for all comps, wiping dumps before canary_cell reclaim gate
- repair: stop(comp, remove_dump=False) on final teardown; mid-run CLOSE still removes unauthorized dumps; canary_cell retention hashes then deletes per E025
- recertification: Post-fix VALID non-sentinel cells write RAW_DUMP_MANIFEST with n_dumps>0 when components were subscribed; sentinel keys retain dump_h*_*.bin
- do_not_repeat: Never delete end-of-cell dumps in nested_client finally; never weaken mid-run unauthorized CLOSE cleanup

## E027_SENTINEL_REUSE_WITHOUT_RAW_DUMPS

- status: `FROZEN_LESSON`
- symptom: Retention sentinel keys land in MAINDEV completed via canary reuse with maindev_dumps=0 and twin also dump-empty
- root_cause: command148_main_dev reused CELL_DONE metrics from canary twins whose dump_*.bin were already reclaimed; SENTINEL_KEEP cannot recover absent bytes
- repair: Refuse canary reuse for sentinel keys when twin has no dump_*.bin (force live); copy twin dumps when present; schedule exact-key live rerun for already-reused zero-dump sentinels before FINAL_DEV
- recertification: Pending sentinels live-run retain dumps; zero-dump reused sentinels listed in COMMAND153_SENTINEL_RERUN_REQUIRED and cleared only after live dumps exist
- do_not_repeat: Never mark a dump-less canary twin as satisfying a retention sentinel

