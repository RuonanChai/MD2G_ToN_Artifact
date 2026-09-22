# PAPER_REWRITE_INPUT_PACK

Read-only scientific fact package for rewriting the ToN manuscript from first principles.
Generated from FINAL/FROZEN canonical evidence only. No experiment launches. No retuning. No favorable inference beyond measured facts.

- **Terminal:** `TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B`
- **Epoch:** `C152_RBV1_88cabc20eb5d`
- **Claim tier:** **TIER_B**
- **Companion JSON:** `Sigcomm26/Paper6_ToN/final/PAPER_REWRITE_INPUT_PACK.json`

Evidence class labels: DEV | scaling | holdout | cross-stack | diagnostic | supporting | FINAL.

**Aggregation defaults** (unless a row states otherwise):
- Matched block key = `(content, network, users, seed)`
- \(\Delta U = U_{\mathrm{MD2G}} - \max(U_{\mathrm{HV3}}, U_{\mathrm{CLUSTERING}}, U_{\mathrm{RULE}})\)
- Bootstrap CI95: resample matched blocks with replacement; \(n_{\mathrm{boot}}=10000\); seed `153` (canary authority); pairing preserved
- W/T/L noise: \(\pm 0.03\) (`paired_U_noise_abs`); W if \(\Delta U>+0.03\); L if \(\Delta U<-0.03\); else T

---

## A. FINAL SCIENTIFIC AUTHORITY

### 1. Exact final terminal tokens

| Token | Scientific meaning | Path | Class |
|---|---|---|---|
| `TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B` | Campaign finished under Tier-B: concurrency-dependent same-substrate benefit with explicit low-concurrency limitation; evidence package complete. **Not** universal dominance / SUBMISSION_READY. | `state/TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B.json` | FINAL |
| `TON_COMPONENT_MD2G_EVIDENCE_PACKAGE_READY` | Final evidence package artifacts written; `terminal=TIER_B`. | `state/TON_COMPONENT_MD2G_EVIDENCE_PACKAGE_READY.json` | FINAL |
| `COMMAND148_MAINDEV_COMPLETE` | MAINDEV matrix finished `n=945`; Loot still sealed at that timestamp. | `state/COMMAND148_MAINDEV_COMPLETE.json` | FINAL |
| `COMMAND153_FINAL_DEV_FROZEN` | DEV controller/epoch frozen; authorizes Loot unseal (`loot_next=true`). | `state/COMMAND153_FINAL_DEV_FROZEN.json` | FINAL |
| `COMMAND153_LOOT_HOLDOUT_FROZEN` | Loot holdout 315 cells complete under frozen controller; no post-holdout tuning. | `state/COMMAND153_LOOT_HOLDOUT_FROZEN.json` | holdout |
| `COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE` | Scientific epoch `C152_RBV1_88cabc20eb5d` with contract/runtime hashes. | `state/COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE.json` | FINAL |
| `COMMAND148_DEV_CANDIDATE_FREEZE` | Controller version V1 accepted (`v1_pass=true`). | `state/COMMAND148_DEV_CANDIDATE_FREEZE.json` | FINAL |
| `PAPER_FINALIZATION_FIGURES_READY` | Final figure set generated from frozen evidence. | `Sigcomm26/Paper6_ToN/Figures/FINAL_FIGURE_MANIFEST.md` | supporting |

**Not emitted:** `TON_COMPONENT_MD2G_SUBMISSION_READY`, `COMMAND153_CLAIM_LIMITED`, `TON_SUBMISSION_READY`.

### 2. Frozen epoch / controller / hashes

| Field | Exact value | Source |
|---|---|---|
| epoch_id | `C152_RBV1_88cabc20eb5d` | `COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE.json` |
| epoch sha256 | `88cabc20eb5dfb3d46e37a24bdb7c92ce712791a19a32c4f0f99049b34d86f0f` | same |
| controller_identity | `MD2G_COMPONENT_V1` | `COMMAND146_MD2G_COMPONENT_POLICY_CONTRACT.json` |
| Teacher path | `Sigcomm26/Paper6_ToN/models/command148_component/teacher_component_v1.pt` | `COMMAND148_TEACHER_TRAINING_FREEZE.json` |
| Teacher sha256 | `74cbf3ac7c87d4b2648b6706feaf2c11f3bca739435d05d974be35481454354c` | same |
| Student path (live inference) | `.../student_component_v1.pt` | `COMMAND148_STUDENT_DISTILLATION.json` |
| Student sha256 | `41ed1170cc378b08c24e93d9cd92d6d600f6eedb9a94c4da3570ea972e83e6e1` | same |
| Architecture | `G2Native9RepController` | same + `controllers/g2_native9rep_model.py` |

Contract hashes frozen in epoch file include DAG `e127a8eb…`, quality `2da35117…`, bitrate `95447a9c…`, Rb `ce245715…`. Class: FINAL.

### 3. Final claim tier

- **Tier:** **B** (Tier A / C not emitted).
- **Frozen claim concept** (`COMMAND153_CLAIM_EVIDENCE_MATRIX.md` + `MANUSCRIPT_REVISION_TIERB.md`): concurrency-dependent same-substrate utility under nested incremental components; MD2G trails at low concurrency (u=20) and wins at medium/high concurrency (u≥60), including sealed unseen Loot; gain driven primarily by decoded \(R_q\); not zero-stall; not universal dominance.
- **Strongest scientifically defensible one-sentence claim:** Under the frozen nested-component MoQ substrate and \(U=\mathrm{clip}(0.25R_o+0.60R_q-0.15R_b,0,1)\), matched \(\Delta U\) versus the strongest of Heuristic/Clustering/Rule is negative at 20 users and positive with CI excluding zero at 60 and 100 users on MAINDEV and on unseen Loot.
- **Strongest claim explicitly NOT supported:** MD2G strictly dominates every same-substrate block; universal superiority; zero/near-zero stall as primary claim; 3–4× QoE; 99% TTFB reduction; 25–72% bandwidth reduction; nine independent full representations; DASH treated as same-substrate.

### 4. Authoritative source-of-truth files

1. `state/TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B.json`
2. `state/TON_COMPONENT_MD2G_EVIDENCE_PACKAGE_READY.json`
3. `state/COMMAND152_POST_INSTRUMENTATION_EPOCH_FREEZE.json`
4. `state/COMMAND153_FINAL_DEV_FROZEN.json`
5. `state/COMMAND148_MAINDEV_COMPLETE.json`
6. `state/COMMAND153_LOOT_HOLDOUT_FROZEN.json`
7. `state/COMMAND151_PHYSICAL_PRESSURE_CONTRACT.json`
8. `state/COMMAND146_COMPONENT_DAG_CONTRACT.json`
9. `state/COMMAND147_COMPONENT_QUALITY_CONTRACT.json`
10. `state/COMMAND147_TEMPORAL_BITRATE_CONTRACT.json`
11. `state/COMMAND146_CORRECTED_EPOCH_SPLIT.json`
12. `state/COMMAND153_FINAL_METRIC_CONTRACT_CONFIRM.json`
13. `state/COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json`
14. `state/COMMAND153_CANARY_SIX_QUESTIONS.json`
15. `Sigcomm26/Paper6_ToN/final/COMMAND153_PRIMARY_STATS.json`
16. `Sigcomm26/Paper6_ToN/final/COMMAND153_MATCHED_BLOCKS.csv`
17. `Sigcomm26/Paper6_ToN/final/COMMAND153_SCALING_STATS.json`
18. `Sigcomm26/Paper6_ToN/final/COMMAND153_HOLDOUT_STATS.json`
19. `Sigcomm26/Paper6_ToN/final/COMMAND153_CROSS_STACK_DASH_STATS.json`
20. `Sigcomm26/Paper6_ToN/final/COMMAND153_OVERHEAD_STATS.json`
21. `Sigcomm26/Paper6_ToN/final/COMMAND153_CLAIM_EVIDENCE_MATRIX.md`
22. `Sigcomm26/Paper6_ToN/final/COMMAND153_LIMITATIONS_AND_UNFAVORABLE_RESULTS.md`
23. `Sigcomm26/Paper6_ToN/Figures/FINAL_LATEX_NUMBERS.tex`
24. `Sigcomm26/Paper6_ToN/Figures/FINAL_FIGURE_AUDIT.md`
25. `Sigcomm26/Paper6_ToN/Figures/SKIPPED_FIGURES.md`
26. `Sigcomm26/Paper6_ToN/Figures/MANUSCRIPT_REVISION_TIERB.md`
27. Conflict audit target: `Sigcomm26/Paper6/ToN_manuscript/sections/*.tex`

---

## B. MEDIA / REPRESENTATION CONTRACT

### 5. Physical media components

Names: **b0, db1, db2, e1, e2**.

| Component | Prerequisites |
|---|---|
| b0 | ∅ |
| db1 | {b0} |
| db2 | {b0, db1} |
| e1 | {b0} |
| e2 | {b0, e1} |

Base prefixes: B1={b0}, B2={b0,db1}, B3={b0,db1,db2}. Enh: E0=∅, E1={e1}, E2={e1,e2}.
Source: `state/COMMAND146_COMPONENT_DAG_CONTRACT.json`. Class: FINAL.

### 6. Logical states and closures

| Logical | Physical closure C |
|---|---|
| Rep1 | {b0} |
| Rep2 | {b0, db1} |
| Rep3 | {b0, db1, db2} |
| Rep4 | {b0, e1} |
| Rep5 | {b0, e1, e2} |
| Rep6 | {b0, db1, e1} |
| Rep7 | {b0, db1, e1, e2} |
| Rep8 | {b0, db1, db2, e1} |
| Rep9 | {b0, db1, db2, e1, e2} |

### 7. Explicit confirmations (MEASURED contract facts)

1. Logical representation ≠ independent full physical stream.
2. Rep ID must **not** be treated as quality (`rep_id_is_not_quality=true`).
3. A state is decodable iff the receiver has received the full component closure \(C(\mathrm{state})\); `highest_decodable` = largest \(|C|\) among states with \(C\subseteq\) received (`lib/component_actuation_plan.py`).

### 8. Frozen component bitrates

Unit: **Mbps**. Aggregation: `steady_state_payload_bps = looped_transport_bytes * 8 / 120s` under `UNIQUE_CLIP_LOOPED` (300 frames @ 30 fps → 10 s clip looped in 120 s). Source: `COMMAND147_TEMPORAL_BITRATE_CONTRACT.json`. Class: FINAL.

| Content | b0 | db1 | db2 | e1 | e2 |
|---|---:|---:|---:|---:|---:|
| Red-and-Black | 33.335512 | 25.018273 | 29.503006 | 17.695226 | 17.693916 |
| Longdress | 38.364247 | 28.693348 | 33.860242 | 20.327970 | 20.331945 |
| Soldier | 44.950541 | 33.724341 | 39.829227 | 23.865654 | 23.869837 |
| Loot | 34.841083 | 26.098450 | 30.818014 | 18.541156 | 18.548414 |

Do **not** divide one-pass unique-clip bytes by 120 s without the loop contract.

### 9. Frozen quality mapping

- **Method:** `nested_component_point_coverage_v1`: \(Q_{\mathrm{raw}}=\) mean over frames of \(|\cup_{c\in C(\mathrm{state})}\mathrm{point\_ids}(c)|/n_{\mathrm{source}}\); \(Q_{\mathrm{norm}}=\mathrm{clip}(Q_{\mathrm{raw}},0,1)\). No min-max across Rep IDs; no native-9 `paper_quality_score`.
- **Rq:** per user \(R_q=Q_{\mathrm{norm}}[\mathrm{decoded\_state}]\); cell \(R_q=\) mean over **launched** users; missing decode → 0. Uses **decoded** quality, not target. Stall/latency **not** in \(R_q\).
- Per-content tables exist; values nearly identical (≈ Rep1=0.30 … Rep9=1.0); quality order ≠ Rep ID order.
- Exact floats: `COMMAND147_COMPONENT_QUALITY_CONTRACT.json`. Class: FINAL.

### 10. Marginal-cost formula

\[
\Delta R(\mathrm{state},\mathrm{active})=\sum_{c\in C(\mathrm{state})\setminus\mathrm{active}}\mathrm{rate\_mbps}(c),\quad
\mathrm{admit\ if\ } \mathrm{access}\ge \Delta R\times 1.05
\]

Concrete Red-and-Black examples (Mbps):
- B1→B2 (active={b0}): add db1 → **25.018273**
- B2→B3 (active={b0,db1}): add db2 → **29.503006**
- B3→B3+E1 (active={b0,db1,db2}): add e1 → **17.695226**
- E1 already active / reused by another receiver: incremental publish cost for e1 is **0** (missing-set excludes already-active components)

Source: `lib/command149_marginal_cost.py`. Class: FINAL.

---

## C. MD2G DESIGN

### 11. Controller inputs (final live)

| Name / slot | Meaning | Source | Normalization | Live in final experiments? |
|---|---|---|---|---|
| `user[:,:,0]` | access throughput (Mbps) | client `perf.csv` RX delta | `/120` | Yes |
| `user[:,:,1]` | device capability | perf col or default cycle 0.22/0.55/0.88 | [0,1] | Yes |
| `user[:,:,2]` | time progress | wall \(t/\mathrm{duration}\) | [0,1] | Yes |
| `user[:,:,3:16]` | unused | zeros | — | Present as zeros |
| `content[0]` | content bit | 0 if redandblack else 1 | — | Yes (Soldier/Loot share non-RB bit) |
| `content[1:12]` | unused | zeros | — | Present |
| `global[0]` | user scale | \(n_{\mathrm{users}}/100\) | — | Yes |
| `global[1:5]` | active flags b0..e2 | actuation plan | 0/1 | Yes |
| `global[6:10]` | unused | zeros | — | Present |

**Not live:** FoV overlap fraction knob (FoV ablation NOT_APPLICABLE). Source: `lib/command148_component_policy.py`.

### 12. Action space

| Layer | What |
|---|---|
| Grouping | Model emits group logits (3); **live frozen path uses single group `g0`** |
| Logical target | Per-user Rep1–Rep9 from student `argmax(rep_logits)`, then `project_down` |
| Physical actuation | Component open/close via `ComponentActuationPlan` |

### 13. ComponentActuationPlan

- `required_component_set` = \(\cup_u C(\mathrm{target}_u)\)
- `component_receivers[c]` = users whose target closure contains \(c\)
- Publisher: open only components in required set
- Subscriber: only users listed for that component receive it
- Overdelivery prevention: non-requesters not in receiver set; unauthorized opens held closed (`COMMAND150_REAL_COMPONENT_OVERDELIVERY_REPAIRED.json`)

Source: `lib/component_actuation_plan.py`. Class: FINAL.

### 14. Grouping / policy (frozen final only)

**Present:** live-RX headroom + device thresholds via `project_down` / missing-component \(\Delta R\); dump>64 completion diagnostic; plan open/close.
**Absent as live mechanisms:** FoV-overlap grouping knob; multi-group learned assignment (g0 only); certified on/off flags for device/completion/headroom ablations.

### 15. Teacher/Student architecture

| Item | Value |
|---|---|
| Class | `G2Native9RepController` |
| Teacher latent / hidden | **128** |
| Student latent / hidden | **64** (dropout 0) |
| Input dims | user 16, content 12, global 10 |
| Output used live | `rep_logits` size 9 (Rep1–9) |
| Distillation | Student CE to expert + `0.1 * KL(teacher‖student)` |
| Training | Adam 1e-3; 40 teacher + 40 student epochs; 16 batches/epoch; contents RB+LD only; Loot unread |
| Inference in final cells | **Student** only |

Old manuscript Teacher-512/Student-128 **does not match** this freeze. Source: `controllers/g2_native9rep_model.py`, training freeze JSONs.

### 16. Model/control overhead

| Field | Value |
|---|---|
| Metric | `student_infer_ms` |
| n | 56 (24 rbv1 + 32 maindev) |
| mean | **377.844 ms** |
| median | **373.417 ms** |
| P95/P99 | not reported in freeze |
| Nature | Offline replay of frozen student on sidecar inputs — **not** pure isolated NN microbench; **not** live perturbation cell |
| Method | `COMMAND155_offline_replay_frozen_student_on_sidecar_inputs` |
| Source | `final/COMMAND153_OVERHEAD_STATS.json` |
| Class | supporting |

---

## D. FINAL METRIC CONTRACT

### 17. Ro_component

\[
R_o=\mathrm{clip}\bigl(1-B_{\mathrm{shared}}/B_{\mathrm{unicast}},0,1\bigr)
\]

- \(B_{\mathrm{unicast}}\): sum over users of payload bytes of components in that user’s decoded closure
- \(B_{\mathrm{shared}}\): sum over **active** components once
- MOQ_UNICAST: force \(R_o=0\) (\(B_{\mathrm{shared}}:=B_{\mathrm{unicast}}\))
- **Does NOT mean:** bandwidth savings; \(1-R_b\); interface-RX efficiency

Source: `lib/ton_ro_component.py`. Class: FINAL.

### 18. Rq

Mean over launched users of \(Q_{\mathrm{norm}}[\mathrm{decoded\_state}]\).
- Stall: **not** included
- Latency: **not** included
- Quality: **decoded**, not target

### 19. Rb

- Observation: **r0-eth1 TX** kernel bytes (shared root)
- Sampling: **1.0 s**
- Utilization: \(u_t=\mathrm{clip}(8\Delta\mathrm{tx}/(C\Delta t),0,\infty)\); idle floor **0.02**
- \(R_b=\mathrm{clip}(P95(\max(0,u_t-0.02)/0.98),0,1)\)
- Protocol overhead: **included**
- **Not** equivalent to traffic volume or \(1-R_o\)

Source: `COMMAND151_PHYSICAL_PRESSURE_CONTRACT.json`.

### 20. Utility

\[
U=\mathrm{clip}(0.25\,R_o+0.60\,R_q-0.15\,R_b,\,0,1)
\]

### 21. Matched comparison

\(\Delta U\) as above. Key: `(content,network,users,seed)`. Strongest same-substrate max over **{HV3, CLUSTERING, RULE} only**.

### 22. W/T/L

Frozen noise threshold: **0.03** (`state/COMMAND153_CANARY_SIX_QUESTIONS.json`).

### 23. Bootstrap

Resampling unit: matched block; \(n_{\mathrm{boot}}=10000\); CI 95%; pairing preserved; canary authority seed **153**.

### 24. Other definitions

| Term | Definition | In final claims? |
|---|---|---|
| weak-user Rq | min per-launched-user decoded \(Q_{\mathrm{norm}}\) | supporting |
| target_q | occupancy-weighted Q of targets | diagnostic |
| decoded_q | occupancy-weighted Q of decoded | enters \(R_q\) |
| component completion | fraction receivers with dump_bytes>64 | diagnostic |

### 25. Metric classes

- **PRIMARY:** \(U\), \(\Delta U\), \(R_o\), \(R_q\), \(R_b\)
- **SECONDARY/SUPPORTING:** weak-user Rq, B_shared/B_unicast, mechanism deltas, throughput, stall_last
- **NOT_IN_FINAL_CLAIM_CONTRACT:** TTFB, delay/arrival interval, buffer_level_sec, CPU, FoV sweep, A1–A5/A7 deltas

### 26. Specific statuses

| Metric | Paper-facing evidence? | May claim? |
|---|---|---|
| TTFB | No (audited zeros) | **No** |
| Data Arrival Interval / delay | No (`NOT_IN_FINAL_CLAIM_CONTRACT`) | **No** |
| buffer level | No (buffer_level_sec zeros) | **No** as occupancy |
| stall | scalar `stall_last` supporting only | Supporting continuity only; **never zero stall** |
| CPU | No in final package | **No** |

Source: `COMMAND153_FINAL_METRIC_CONTRACT_CONFIRM.json`, `SKIPPED_FIGURES.md`.

---

## E. EXPERIMENTAL SETUP

### 27. Topology

Publisher → MoQ root relay **r0** → leaf/regional relays → clients. Rb interface: **r0-eth1 TX**. Access last-mile traces on client links. Same-substrate stack: MoQ/QUIC (`moq_lite`). H2: DASH/HTTP unicast. Runtime hashed in epoch freeze (`moq_cluster_Sigcomm.py`).

### 28. Timing parameters

| Parameter | Value |
|---|---|
| Run duration | 120 s |
| Warmup | 30 s |
| Measurement | 90 s |
| Control interval | 1.0 s |
| Frame cadence | 300 unique frames @ 30 fps |
| Loop semantics | 10 s unique clip looped in 120 s transport |

### 29. Network profiles (MAINDEV)

`4g`, `5g`, `wifi`, `fiber_optic`, `default_mix`, `wifi_dominant`, `5g_dominant`.
DEV vs holdout row windows frozen in `COMMAND146_CORRECTED_EPOCH_SPLIT.json` (e.g. 4g DEV `rows_0_634`, holdout `rows_634_906`). Mix/dominant = heterogeneous; named homogeneous otherwise. No 30 Mbps floor on cleaned 4G contract.

### 30. User scales

| Stage | Users |
|---|---|
| MAINDEV | 20, 60, 100 |
| Scaling | 10, 20, 40, 60, 100 |
| Holdout | 20, 60, 100 |

### 31. Seeds

| Stage | Seeds |
|---|---|
| DEV / MAINDEV / canary science | 151, 152, 153 |
| Smoke | 141, 142 |
| Loot holdout | **91, 92, 93** |

### 32. Content split

- Train/DEV: Red-and-Black, Longdress, Soldier
- Teacher/Student train contents: Red-and-Black, Longdress only
- Unseen holdout: **Loot**
- Loot unsealed after `COMMAND153_FINAL_DEV_FROZEN` (2026-08-26T14:53:27Z); MAINDEV complete still `loot_sealed=true`; Loot frozen 2026-08-27. Evidence Loot not used for controller selection: training freeze `loot_network_unread=true`; quality contract `controller_must_not_use_contents=["loot"]` until DEV freeze.

---

## F. BASELINES

### 33. What each baseline does (final code)

| Strategy | Exact behavior |
|---|---|
| HV3_COMPONENT | Time ladder Rep1 (<25s) → Rep2 (<70s) → Rep3; then shared `project_down` |
| CLUSTERING_COMPONENT | Split at mid users; low half Rep3/Rep8; high half Rep2/Rep6; then `project_down` |
| RULE_COMPONENT | 3-bucket timed Rep schedule; then `project_down` |
| MOQ_UNICAST_COMPONENT | Same raw schedule as RULE but per-user publisher keys; Ro forced 0 |
| GROOT | Authentic DASH/HTTP unicast baseline (H2) |
| Rolling | Authentic DASH/HTTP unicast baseline (H2) |

Source: `lib/command148_component_policy.py`, command146 plan §8.

### 34. HV3 naming

Implementation id: `HV3_COMPONENT` (“Heuristic-v3” port). Figure code label: **Heuristic**.
**Recommend one paper name: Heuristic** (mention HV3 once as implementation alias).

### 35–38. Baseline roles

- **SAME-SUBSTRATE primary:** Heuristic (HV3), Clustering, Rule (+ MD2G)
- **DELIVERY-MODE only:** MOQ_UNICAST
- **CROSS-STACK secondary only:** GROOT, Rolling
- **Why not mix into strongest comparator:** different delivery architecture (shared vs unicast) or different stack (MoQ vs DASH); would confound controller comparison within the nested-component MoQ substrate.

---

## G. FINAL MAINDEV RESULTS

Source: `final/COMMAND153_PRIMARY_STATS.json`, `COMMAND153_MATCHED_BLOCKS.csv`. Class: **DEV**. Aggregation: mean over cells/blocks as stated. Unit: unitless unless noted.

### 39. Strategy-level means (n=189 each)

| Strategy | n | mean U | mean Rq | mean Ro | mean Rb | weak-user Rq |
|---|---:|---:|---:|---:|---:|---:|
| MD2G | 189 | 0.674987 | 0.739504 | 0.972788 | 0.079416 | 0.270106 |
| CLUSTERING | 189 | 0.648935 | 0.702431 | 0.971188 | 0.102135 | 0.221561 |
| RULE | 189 | 0.641052 | 0.689794 | 0.970451 | 0.102914 | 0.237169 |
| HV3 | 189 | 0.558666 | 0.543828 | 0.972445 | 0.071616 | 0.214550 |
| MOQ_UNICAST | 189 | 0.189213 | 0.415917 | 0.000000 | 0.402246 | 0.209656 |

### 40. Overall matched MD2G vs strongest same-substrate

| Field | Value |
|---|---|
| n matched blocks | 189 |
| mean ΔU | **+0.015849** |
| median ΔU | **+0.082871** |
| CI95 (seed 153) | **[−0.001892, +0.033033]** (includes 0) |
| W/T/L @0.03 | **125 / 0 / 64** |

### 41. MAINDEV matched by users

| users | n | mean ΔU | median | CI95 | W/T/L |
|---:|---:|---:|---:|---|---|
| 20 | 63 | −0.136772 | −0.158686 | [−0.153064, −0.118250] | 5/0/58 |
| 60 | 63 | +0.078507 | +0.086040 | [+0.065893, +0.088922] | 60/0/3 |
| 100 | 63 | +0.105812 | +0.115436 | [+0.093772, +0.115995] | 60/0/3 |

### 42. MAINDEV by content

| content | n | mean ΔU | CI95 | W/T/L | Important counterexample |
|---|---:|---:|---|---|---|
| Red-and-Black | 63 | +0.036043 | [+0.005320, +0.064456] | 47/0/16 | u20 mean −0.106 |
| Longdress | 63 | +0.010343 | [−0.020772, +0.040134] | 42/0/21 | u20 **21/21 losses** |
| Soldier | 63 | +0.001161 | [−0.029877, +0.030692] | 36/0/27 | overall ~0; u60/u100 still win (+0.064/+0.087) |

### 43. MAINDEV by network (summary)

Tier-B high-concurrency effect (u60/u100 wins) holds on 5g, 5g_dominant, default_mix, fiber_optic, wifi, wifi_dominant.
**4g** weakest: u20 all losses; u60 mean ΔU≈+0.013 (CI includes 0); u100≈+0.048 (CI includes 0). Exact per-net rows: recompute from `COMMAND153_MATCHED_BLOCKS.csv`.

### 44. Strongest negative slices

- `longdress_wifi_u20_s151` ΔU=**−0.215941** vs RULE
- `longdress_5g_u20_s151` ΔU=**−0.213697** vs RULE
- `soldier_fiber_optic_u20_s153` ΔU=**−0.213205** vs RULE
- Systematic: 64/189 blocks ΔU<0 (list in `COMMAND153_LIMITATIONS_AND_UNFAVORABLE_RESULTS.md`)

### 45. Strongest positive slices

- `redandblack_fiber_optic_u100_s152` ΔU=**+0.169967** vs CLUSTERING
- `soldier_5g_dominant_u100_s153` ΔU=**+0.162325** vs CLUSTERING
- Pattern: u100 high-capacity / dominant nets

---

## H. SCALING / CROSSOVER

Source: `COMMAND153_SCALING_STATS.json` + figure source matched. Class: **scaling**.

### 46. Scaling matched (n=6 blocks per load)

| users | MD2G mean U | strongest mean U | mean ΔU | CI95 | W/T/L |
|---:|---:|---:|---:|---|---|
| 10 | 0.606214 | 0.674792 | −0.068578 | [−0.162812, +0.025657] | 2/0/4 |
| 20 | 0.619805 | 0.669097 | −0.049292 | [−0.132334, +0.034309] | 3/0/3 |
| 40 | 0.694701 | 0.676439 | +0.018262 | [−0.070717, +0.104379] | 4/0/2 |
| 60 | 0.773474 | 0.685039 | +0.088435 | [+0.079885, +0.096882] | 6/0/0 |
| 100 | 0.772569 | 0.657786 | +0.114783 | [+0.106551, +0.123046] | 6/0/0 |

### 47. Crossover location

First scaled load with **positive mean ΔU** is **u=40**. “Near 40 users” is a **measured mean sign change**, but u40 CI **includes 0** → interpret as **estimated transition**, not a sharp proven threshold.

### 48. 150 logical keys

| Item | Count |
|---|---:|
| Logical keys | 150 |
| Exact DEV reuse (u20/60/100) | **90** |
| Newly launched (u10/40 only) | **60** |

Paper must describe: “150-key logical matrix = 90 DEV reuses + 60 new launches,” **not** “150 new Mininet executions.” Source: `COMMAND153_PAPER_CLAIM_COMPATIBILITY_NOTE.json`.

---

## I. LOOT UNSEEN HOLDOUT

Source: `COMMAND153_HOLDOUT_STATS.json`, loot matched blocks. Class: **holdout**.

### 49. Matrix

1 content (Loot) × 7 networks × 3 user scales × 3 seeds (91/92/93) × 5 strategies = **315** cells.

### 50. Strategy-level means (n=63)

| Strategy | U | Rq | Ro | Rb |
|---|---:|---:|---:|---:|
| MD2G | 0.688030 | 0.759753 | 0.973653 | 0.074895 |
| CLUSTERING | 0.669306 | 0.734566 | 0.972211 | 0.096577 |
| RULE | 0.663968 | 0.726313 | 0.971458 | 0.097896 |
| HV3 | 0.586976 | 0.589312 | 0.973212 | 0.066097 |
| MOQ_UNICAST | 0.194254 | 0.407233 | 0.000000 | 0.333906 |

### 51. Matched by users

| users | n | mean ΔU | median | CI95 | W/T/L |
|---:|---:|---:|---:|---|---|
| 20 | 21 | −0.160214 | −0.176046 | [−0.175190, −0.142821] | **0/0/21** |
| 60 | 21 | +0.083108 | +0.081707 | [+0.077500, +0.088506] | **21/0/0** |
| 100 | 21 | +0.111350 | +0.112896 | [+0.100969, +0.120536] | **21/0/0** |

### 52. By network × user tier

Every network: u20 all losses (3/3); u60 and u100 all wins (3/3). No favorable exception at u20.

### 53. Does Tier-B generalize to Loot?

**Yes (measured):** same concurrency-dependent pattern; u60/u100 unanimous wins; u20 unanimous losses.

### 54. Strengthened vs limitation

- **Strengthened:** unseen-content confirmation of concurrency-dependent claim without retuning.
- **Limitation:** low-concurrency underperformance remains systematic; overall Loot mean ΔU CI includes 0 if pooling loads.

---

## J. MECHANISM EVIDENCE

### 55. ΔU decomposition (MAINDEV matched; means)

| Slice | mean ΔRo | mean ΔRq | mean ΔRb | 0.25ΔRo | 0.60ΔRq | −0.15ΔRb |
|---|---:|---:|---:|---:|---:|---:|
| u20 | +0.002139 | −0.244940 | −0.064385 | +0.000535 | **−0.146964** | +0.009658 |
| u60 | +0.001300 | +0.130529 | +0.000904 | +0.000325 | **+0.078317** | −0.000136 |
| u100 | +0.000907 | +0.172190 | −0.015141 | +0.000227 | **+0.103314** | +0.002271 |

### 56. “Gain mainly driven by Rq”?

**Yes for u60/u100 (measured):** \(0.60\Delta R_q\) dominates contribution; \(0.25\Delta R_o\approx 0\).
**Not** for pooled overall (u20 Rq losses cancel).

### 57. Wins by driving shared root harder?

**No.** At u60/u100, mean ΔRb ≈ 0 / slightly negative (MD2G often **lower** pressure).

### 58. Wins by favorable Ro accounting?

**No.** mean ΔRo ≈ 0.001.

### 59. Target-to-decoded (MD2G MAINDEV matched n=189)

- mean (target_q − decoded_q) ≈ **0.089370**
- e1 completion mean ≈ **0.607** overall; ≈ **0.881** at u60; ≈ **0.869** at u100; ≈ **0.071** at u20
- e2 completion mean ≈ **0.562** overall; ≈ **0.876** at u60; ≈ **0.746** at u100

### 60. Weak-user

| users | MD2G weak Rq | strongest weak Rq | Δ |
|---:|---:|---:|---:|
| 20 | 0.253968 | 0.347222 | **−0.093254** |
| 60 | 0.286508 | 0.230952 | **+0.055556** |
| 100 | 0.269841 | 0.225794 | **+0.044048** |

High-concurrency gains **do not** sacrifice weak users vs strongest baseline.

### 61. Measured vs inferred

**Measured:** load-conditioned ΔU; Rq-driven high-concurrency contribution; shared vs unicast gap; Loot concurrency pattern; weak-user deltas.
**Inferred only (no live ablation):** FoV/device/completion/grouping/marginal-cost as separable causal contributions.

### 62. NOT_APPLICABLE ablations

A1 (no FoV overlap), A2 (no device), A3 (no headroom), A4 (no completion), A5 (fixed grouping), A7 (naive cumulative cost), FoV 20/40/60/80.
**Must NOT** attribute mechanism claims to ablation deltas for these. A0/A6 = DEV reuse only.

---

## K. SHARED VS UNICAST / CROSS-STACK

### 63. MD2G vs MOQ_UNICAST (MAINDEV means)

| | U | Rq | Ro | Rb |
|---|---:|---:|---:|---:|
| MD2G | 0.674987 | 0.739504 | 0.972788 | 0.079416 |
| MOQ_UNICAST | 0.189213 | 0.415917 | 0.000000 | 0.402246 |

Architectural claim supported: **shared component delivery vs independent unicast** on same MoQ/component assets — **not** same-substrate controller skill.

### 64. H2 DASH (n=48; cross-stack)

| Series | n | mean U | notes |
|---|---:|---:|---|
| GROOT | 24 | 0.058625 | std≈0.0208 |
| Rolling | 24 | 0.081451 | std≈0.0384 |
| MD2G matched on H2 keys u20 | 24 | 0.514702 | |
| MD2G matched on H2 keys u60 | 24 | 0.757176 | |

Rb often null; `canonical_U_not_primary=true`. Source: figure loader over DASH CELL_DONE + `COMMAND153_CROSS_STACK_DASH_STATS.json`.

### 65. Strongest allowed DASH wording

Secondary cross-stack system comparison under different protocol stack; large observed U gap; does **not** isolate the MD2G controller within the MoQ substrate.

### 66. Scientifically incorrect DASH wording

Treating GROOT/Rolling as same-substrate peers in strongest-baseline max; claiming the DASH gap proves MD2G algorithmic superiority alone; pooling DASH into MAINDEV rankings.

---

## L. THROUGHPUT / NETWORK COST

### 67. What final throughput figures measure

- Interface: **r0-eth1** TX (physical pressure ledger)
- Formula: `raw_protocol_inclusive_tx_bytes * 8 / (n_intervals * 1e6)` → **Mbps**
- Averaging window: 1 s intervals over cell
- Protocol overhead: **included**
Source: `Figures/_fig_evidence.py::throughput_mbps`.

### 68. Key throughput results

Paper-valid as **supporting** bars per network (`Throughput/System_Throughput_Bar_*.pdf`). Do not elevate to primary efficiency claim. Strategy mean_rx in figure source is cumulative client RX bytes — distinct from shared-root TX Mbps plots.

### 69. Lower throughput = higher efficiency?

**No.** Must caveat: efficiency uses \(R_o\)/byte accounting; pressure uses \(R_b\); utility is \(U\). Lower TX can mean under-delivery.

### 70. Relationship

Throughput (root TX) ≠ \(R_o\) ≠ \(R_b\) ≠ \(U\). Report each with its definition; do not substitute.

---

## M. FIGURES AND TABLES

### 71. Scientifically valid FINAL figures

Authority: `Figures/FINAL_FIGURE_MANIFEST.md`, `FINAL_FIGURE_AUDIT.md`. Data: `final/COMMAND153_FIGURE_SOURCE_DATA/*`.

| Filename | Role | Source | Axes | Error bars | Placement |
|---|---|---|---|---|---|
| `QoE/QoE_By_Strategy.pdf` | strategy U | `dev.json` | strategy / U | sample std | MAIN |
| `Buffer Level/System_Utility_By_Users_scheme1.pdf` | crossover | `scaling.json` | users / U | sample std | MAIN |
| `Buffer Level/System_Utility_By_Users_MainDev.pdf` | MAINDEV by users | `dev.json` | users / U | sample std | MAIN |
| `QoE/QoE_By_Network.pdf` | ΔU by net | matched | network / ΔU | sample std | MAIN |
| `QoE/QoE_By_Content_DeltaU.pdf` | ΔU by content | matched | content / ΔU | sample std | MAIN |
| `QoE/Loot_Holdout_DeltaU_By_Users.pdf` | holdout | `loot.json` | users / ΔU | sample std | MAIN |
| `QoE/Mechanism_Decomposition_Loot.pdf` | Rq/Ro/Rb | loot | component / contrib | sample std | MAIN |
| `QoE/MoQ_Shared_vs_Unicast.pdf` | delivery mode | PRIMARY_STATS | strategy / U | sample std | MAIN/APP |
| `QoE/Weak_User_Rq_Loot.pdf` | weak user | loot | users / weak Rq | sample std | APPENDIX |
| `Throughput/System_Throughput_Bar_*.pdf` | TX Mbps | physical_pressure | users / Mbps | sample std | APPENDIX |
| `Stall Time/Stall_Time_By_*.pdf` | stall_last | stall_last | category / s | sample std | APPENDIX (supporting) |
| `User_Experience_Trade-off/H2_Cross_Stack_DASH.pdf` | H2 | DASH U | users / U | sample std | APPENDIX |
| `User_Experience_Trade-off/TierB_Rb_vs_U_*.pdf` | Rb–U scatter | dev | Rb / U | N/A scatter | APPENDIX |

### 72. Three strongest for final claim

1. `System_Utility_By_Users_scheme1.pdf`
2. `Loot_Holdout_DeltaU_By_Users.pdf`
3. `Mechanism_Decomposition_Loot.pdf` (or MAINDEV ΔU-by-users)

### 73. Error-bar semantics

Main bar figures: **sample standard deviation** across cells/blocks in the bin (`statistics.stdev`), **not** bootstrap CI, unless a caption explicitly states otherwise.

### 74. Legacy SIGCOMM families that cannot be reproduced

| Family | Reason |
|---|---|
| TTFB CDF | `ttfb_*_ms` audited 0 |
| Fluidity–QoE (arrival interval) | `delay_ms` audited 0 |
| Buffer occupancy curves | `buffer_level_sec` audited 0 |
| Continuity/recovery timeseries | no evolving stall_total; scalar stall_last only |
| CPU | not in final claim package |
| FoV sensitivity | NOT_APPLICABLE |

### 75. Final tables from frozen evidence

Strategy means; matched ΔU by users/content/network; scaling; Loot; mechanism decomposition; W/T/L; H2 secondary; unfavorable block list; reproducibility hashes (`COMMAND153_ALL_HASHES.json`).

---

## N. OLD MANUSCRIPT CONFLICT AUDIT

Manuscript: `Sigcomm26/Paper6/ToN_manuscript/sections/`.

### 76. Major conflicting statements

| File | Current wording (essence) | Why inconsistent | Replace with |
|---|---|---|---|
| `abstract.tex` | QoE 0.609; +25.2% Rolling; +27.1% GROOT; near continuous | Old numbers; DASH mixed as peer; stall narrative | Tier-B concurrency ΔU; frozen U |
| `introduction.tex` L43–47 | same +25.2/+27.1; near continuous | same | concurrency-dependent contribution + limitation |
| `evaluation.tex` | \(R_q^{\mathrm{adj}}\) primary; TTFB; near-zero stall; table U=0.609; FoV/device ablations | Wrong primary metric; TTFB zeros; stall not in U; FoV NA | U/ΔU; supporting stall only; remove NA ablations |
| `conclusion.tex` | +25.2/+27.1; near-continuous | outdated | Tier-B conclusion |
| `appendix.tex` | TTFB CDFs; arrival-interval trade-off | no frozen nonzero evidence | remove/unavailable |
| `design.tex` | Rb as inefficient bandwidth | Rb ≠ bandwidth saving | Ro/Rq/Rb definitions |
| Ablation tables MD2G-V/D/B | online FoV/device deltas | NOT_APPLICABLE | structural facts only |

### 77. Equations to remove/rewrite

Primary completion-adjusted multi-term QoE; Rb-as-bandwidth-saving; any Rep-ID-as-Q mapping; old weight tables claiming universal rank-1 under obsolete metric.

### 78. Tables to remove/rewrite

Adj-QoE headline 0.609; FoV/device ablation; old weight sensitivity as primary; CPU tables.

### 79. Figures to remove/replace

TTFB CDFs; Fig.4-style delay–QoE; buffer occupancy; continuity timeseries; FoV F9; any zero-stall narrative plots.

### 80. Terminology standardization

| Old / ambiguous | Standard |
|---|---|
| HV3 alone | **Heuristic** (HV3 alias once) |
| Nine representations as files | Logical component states / compositions |
| Bandwidth savings via Rb | Reuse \(R_o\) / B_shared vs B_unicast; Rb = pressure |
| QoE (ambiguous) | System utility \(U\) (+ supporting Rq) |
| GROOT-MoQ as MoQ peer | GROOT (DASH) cross-stack secondary |

---

## O. CLAIM BOUNDARIES / REVIEWER RISKS

### 81. Five strongest evidences for MD2G

1. MAINDEV u60/u100 ΔU CI excludes 0; W/L 60/3
2. Loot u60/u100 21/21 wins; u20 0/21
3. Scaling u60/u100 CI excludes 0; mean sign flip by u40
4. High-concurrency ΔU dominated by \(0.60\Delta R_q\)
5. Shared vs unicast architectural gap (Ro≈0 on unicast)

### 82. Five strongest weaknesses

1. Systematic u20 losses (MAINDEV 58/63 L; Loot 21/21 L)
2. Overall MAINDEV mean ΔU CI includes 0
3. Soldier overall ΔU ≈ 0
4. 4g high-concurrency CI fragile / includes 0
5. No live mechanism ablations (A1–A5/A7/FoV NA)

### 83. Likely skeptical challenges

Cherry-picking high concurrency; overall nonsignificance; Soldier failure; DASH overclaim; missing ablations; overhead vs 1 s control loop; buffer/TTFB omissions.

### 84. Per-challenge response pattern

- Evidence already answers concurrency cherry-pick: predeclared loads + Loot + scaling.
- Must admit: u20 limitation; overall CI includes 0; NA ablations; no TTFB/buffer claims.
- Must NOT overclaim: universal win; zero stall; DASH as same-substrate; ablation deltas.

### 85. Low-concurrency underperformance

**Measured operating-regime boundary** (systematic across contents/nets/Loot). Not proven as mere instrumentation artifact. Design-limitation interpretation is plausible but **not ablation-proven**.

### 86. Is Soldier a generalization failure?

**Nuanced measured answer:** content-level mean ΔU ≈ 0, but load-conditioned: u20 losses, u60/u100 wins. Not a blanket failure; not a blanket success.

### 87. “High concurrency” definition

Conservative wording: **medium-to-high concurrency (60–100 users)**; scaling transition **near 40** as estimate. Do not claim u≥40 as proven win threshold.

### 88. Statistical significance

CI excludes 0: MAINDEV u60, u100; Loot u60, u100; Scaling u60, u100; MAINDEV Red-and-Black overall.
CI includes 0: MAINDEV overall; Longdress/Soldier overall; Scaling u10/20/40; Loot overall.

### 89. Generalization

- Contents: RB/LD/Soldier DEV; Loot unseen confirms concurrency pattern
- Networks: 7 profiles; weakest on 4g
- Scales: robust at 60–100; not at 20
- Holdout: Loot sealed until FINAL_DEV freeze; no post-holdout tuning

---

## P. PAPER REWRITE RECOMMENDATION

### 90. Thesis (2–3 sentences)

MD2G-Cast under a nested incremental component MoQ contract yields a **concurrency-dependent** same-substrate utility gain versus Heuristic, Clustering, and Rule. At 20 users it underperforms; at 60–100 users it wins consistently on DEV and on sealed unseen Loot, driven mainly by decoded quality \(R_q\). The contribution is this operating-regime characterization under frozen \(U\)—not universal dominance or stall elimination.

### 91. Final three RQs

1. Does nested component sharing improve system utility vs same-substrate baselines, and under which concurrency?
2. Does the concurrency-dependent pattern generalize to unseen Loot without retuning?
3. Is the gain explained by decoded quality, reuse, or root pressure?

### 92. Final three contributions

1. Nested incremental component media/control contract for multi-user MoQ volumetric delivery.
2. Empirical Tier-B result: concurrency-dependent matched ΔU with explicit low-concurrency limitation.
3. Metric discipline separating \(R_o\), decoded \(R_q\), physical \(R_b\), delivery-mode, and cross-stack comparisons.

### 93. Evaluation subsection structure

Setup → Primary U/ΔU MAINDEV → Concurrency crossover (scaling) → Loot holdout → Mechanism decomposition → Shared vs unicast → Cross-stack secondary → Limitations.

### 94. Main-text Figure 1..N

1 Topology/system · 2 U-by-strategy · 3 Scaling crossover · 4 MAINDEV by users · 5 By network · 6 By content · 7 Loot ΔU · 8 Mechanism · 9 Shared vs unicast.

### 95. Appendix

Throughput; stall_last; H2 DASH; weak-user; unfavorable lists; hashes; overhead.

### 96. Abstract headline

Under a nested-component MoQ substrate, MD2G improves matched system utility at 60–100 users—including on unseen Loot—while underperforming at 20 users, yielding a concurrency-dependent rather than universal advantage.

### 97. Conclusion headline

Frozen evidence supports a Tier-B, concurrency-dependent shared-delivery benefit driven mainly by decoded quality, with an explicit low-concurrency limitation and no zero-stall claim.

---

## Q. FINAL GAP CHECK

### 98. Missing for technically complete rewrite?

- Typesetting should pull exact per-network tables from `COMMAND153_MATCHED_BLOCKS.csv`.
- H2 DASH rows lack canonical Rb in stats JSON (U available via figure loader).
- Live end-to-end control-path latency beyond offline `student_infer_ms` is limited.
- FoV/device ablations absent by contract (narrate as N/A; do not invent).

### 99. New experiment necessary for Tier-B?

**NO.** Remaining gaps are claim-boundary / instrumentation-retention limits, not missing primary Tier-B matched U/ΔU evidence.

### 100. Unresolved ambiguities

1. Overall MAINDEV mean ΔU CI includes 0 — headline must be load-conditioned.
2. Scaling 150 ≠ 150 new runs (90 reuse + 60 new).
3. “Buffer Level” folder crossover plot metric is **U**, not buffer.
4. Teacher/Student latent sizes are **128/64**, not 512/128.
5. W/T/L noise is **0.03**.
6. Final epoch is C152; pre-Rb diagnostic cells excluded.
7. Content feature bit collapses all non-RB contents.
8. NN group head exists but live grouping is g0.
9. DASH U is secondary only.
10. `ToN_manuscript` still contains SIGCOMM-era claims — full rewrite required.

---

PAPER_REWRITE_INPUT_PACK_READY
