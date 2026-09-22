# Stall Time: 为何与 SIGCOMM 论文不一致（权威说明）

## 一句话结论

**不是画错了，而是两套科学口径不可直接对齐。**  
SIGCOMM `MD2G_Sigcomm_submit version4.pdf` 的 “zero stalls / MoQ≈0、DASH≈100s”  
与 ToN 冻结证据包中的 `stall_last` **不是同一指标、同一实验合同、同一基线集合。**

---

## 对照表

| 维度 | SIGCOMM 论文 / `paper_figures/Sigcomm/Stall Time` | ToN 冻结终态 (`COMMAND153`) |
|------|---------------------------------------------------|------------------------------|
| 数据源 | `logs_all_20260125` + `stall_total_sec` **max** | `final/.../dev.json` 的 `stall_last` |
| 指标语义 | 会话累计卡顿（旧 client perf 会计） | `DECODE_GAP_SECONDS_POST_WARMUP`（warmup 后解码间隙，**supporting only**） |
| MoQ 典型值 | MD2G/H/C ≈ **0.00 s** | MD2G DEV mean ≈ **0.88 s**（非零） |
| DASH/unicast | Rolling≈92s, DASH-PC≈114s（跨栈巨大差） | same-substrate 各策略 stall 同量级；**禁止**用 stall 证明 MoQ 完胜 |
| 终态合同 | 论文摘要写 “maintaining zero stalls” | `never_claim_zero_stall=true`（写进 PRIMARY_STATS / LIMITATIONS） |
| 是否进 U | QoE 公式里有 stall 惩罚项 | 主指标 \(U=\mathrm{clip}(0.25 R_o+0.60 R_q-0.15 R_b)\)，**stall 不进 U** |

---

## 根因（必须写进正文的科学理由）

1. **旧 DASH stall 会计曾被诊断为不可信**  
   `STALL_AND_BASELINE_TEXT.md` / ledger：P0 时代 `stall_total_sec_delta≈100s` 含 buffer accounting bug；不能再拿来支撑 “MoQ 消除卡顿 100%”。

2. **ToN 故意 fail-closed**  
   曾有 `stall_last=0 UNIMPLEMENTED_PLACEHOLDER` 被误读为零卡顿；修复后定义为 decode-gap supporting metric，并写入  
   `Never claim zero stall`。

3. **实验合同已换**  
   SIGCOMM：独立 full-rep + DASH-PC 槽位。  
   ToN：nested `b0/db1/db2/e1/e2` + same-substrate HV3/Clustering/Rule + Tier-B concurrency claim。  
   用旧 stall 图去对齐新合同，会制造虚假叙事。

4. **当前 Stall Time PDF 的正确角色**  
   `Figures/Stall Time/*.pdf` = **连续性旁证**，量级约亚秒～秒级 decode gap，**各 same-substrate 策略彼此接近**。  
   **不可**替换 SIGCOMM Fig.8 的 “MoQ near-zero vs DASH multi-second stall” 故事。

---

## 论文应如何表述（允许 / 禁止）

**允许：**  
“Under the nested-component contract, stall is reported only as a supporting continuity diagnostic; primary differentiation is via system utility \(U\) and decoded quality \(R_q\).”

**禁止：**  
- “maintaining zero stalls”  
- “MoQ completely eliminates stall”  
- 把 `Stall_Time_By_Strategy.pdf` 与 SIGCOMM Fig.8 并列为同一 claim
