# Same-substrate controller contract

Extracted from the implementation in `Sigcomm26/Paper6_ToN/lib/command148_component_policy.py` and `command148_mcg.py`. All five controllers emit per-user logical states `Rep1`–`Rep9`. The **same** deterministic projector then maps targets to physical components.

Shared feasibility (`command149_marginal_cost.project_down`):

- Inputs: requested logical state, per-user access (Mbps), device score, content id, already-active component set
- Extra rate = sum of `steady_state_payload_mbps` over **missing** components in the requested closure
- Admit iff `access >= extra_rate * 1.05`
- Device gate in MCG: enhancement-like components require `device >= 0.15`
- Tie-break: first feasible downward projection that satisfies the missing-set test
- Learning: only MD2G-Cast uses a neural student; others do not

Control interval: 1 second.

## MD2G-Cast (`MD2G_COMPONENT`)

- Inputs: live access vector, device vector, time fraction, content id, currently active components
- Model: frozen student `models/command148_component/student_component_v1.pt`
- Decision: student `rep_logits` → raw Rep id, then `project_down`
- Stateful: yes. Features include which physical components are already open; logical selection is recomputed each interval
- Thresholds: feasibility margin 1.05; no additional score threshold
- Tie-break: argmax over 9 logits, then deterministic projection
- Learning: yes (offline teacher/student distillation). Live path does not train

## MCG (`MCG_COMPONENT`)

Implementation: `mcg_select()` in `command148_mcg.py`.

- Inputs: per-user access, device, content, current decoded component sets, already-active components
- Score for a candidate physical component \(c\):
  \[
  \mathrm{score}(c)=\frac{\sum_u \Delta Q_u(c)}{\mathrm{rate}(c)}
  \]
  where \(\Delta Q_u\) is the increase in frozen \(Q_{\mathrm{norm}}\) if \(c\) is added to user \(u\)'s decoded set
- Admission: repeatedly admit the highest-scoring component whose prerequisites are already admitted and that has \(\Delta Q>0\) for at least one feasible user
- Undecoded users have \(Q=0\) (not \(Q(\mathrm{Rep1})\))
- FoV is unused
- Does **not** load the student
- Feasibility: same missing-set \(\Delta R \times 1.05\) projector after greedy selection
- Tie-break: highest score; first component in `(b0, db1, db2, e1, e2)` order if scores tie
- Learning: no

## Heuristic (`HV3_COMPONENT`)

- Inputs: time \(t\) only (then shared physics)
- Rule: \(t<25\Rightarrow\mathrm{Rep1}\); \(t<70\Rightarrow\mathrm{Rep2}\); else \(\mathrm{Rep3}\)
- Same `project_down` after the raw target
- Learning: no
- Tie-break: none (deterministic time buckets)

## Clustering (`CLUSTERING_COMPONENT`)

- Inputs: user index and time
- Split users into two halves
- First half: \(\mathrm{Rep3}\) if \(t<40\) else \(\mathrm{Rep8}\)
- Second half: \(\mathrm{Rep2}\) if \(t<40\) else \(\mathrm{Rep6}\)
- Same projector
- Learning: no

## Rule (`RULE_COMPONENT`)

- Inputs: user index and time
- \(t<20\Rightarrow\mathrm{Rep1}\) for all
- Then three modulo-3 buckets:
  - bucket 0: Rep3 if \(t<70\) else Rep8
  - bucket 1: Rep2 if \(t<50\) else Rep6
  - bucket 2: Rep3 if \(t<80\) else Rep9
- Same projector
- Learning: no

## MoQ-Unicast (`MOQ_UNICAST_COMPONENT`)

Present in the policy hook. Uses the Rule raw schedule but **independent publisher keys** (`Ro=0` by construction). Same projector with per-user active sets. Cross-stack GROOT/Rolling are **not** included as MoQ controllers.

## Frozen utility

\(U=\mathrm{clip}(0.25 R_o+0.60 R_q-0.15 R_b,0,1)\). Weights are not tuned from holdout.
