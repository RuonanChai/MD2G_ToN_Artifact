# ToN 正文修订指南（Tier-B 冻结证据）

权威数值来源：`Figures/FINAL_LATEX_NUMBERS.tex` + `final/COMMAND153_*`  
终态：`TON_COMPONENT_MD2G_EXPERIMENTS_COMPLETE_TIER_B`  
图目录：`Sigcomm26/Paper6_ToN/Figures/`（风格对齐 `paper_figures/Sigcomm/`）

---

## A. 图是否按要求生成？

| 状态 | 说明 |
|------|------|
| **已完成** | 36+ PDF，按 Sigcomm 目录：QoE / Buffer Level / Stall Time / Throughput / User_Experience_Trade-off |
| **风格** | DejaVu Sans、figsize≈(12,7)、edgecolor black、linewidth 1.5、QoE 配色 `#FBF0C3/#54686F/#E57B7F/#9E3150/#87BBA4`；分组柱用 Buffer scheme1 `#0E606B/#1597A5/#FFC24B/#F66F69` |
| **数据** | 仅 `COMMAND153_FIGURE_SOURCE_DATA` + 冻结 token；fail-closed |
| **跳过** | TTFB / CPU / FoV（无冻结证据或 NOT_APPLICABLE）见 `SKIPPED_FIGURES.md` |
| **中心交叉图** | `Buffer Level/Buffer_Level_By_Users_scheme1.pdf`（实为 **System Utility U vs users**，布局复用 Buffer-by-users） |
| **Holdout** | `QoE/Loot_Holdout_DeltaU_By_Users.pdf` |
| **Stall 特别注意** | 已生成，但**不得**复用 SIGCOMM “zero stall” 叙事（见 `STALL_VS_SIGCOMM_PAPER.md`） |

### 与 SIGCOMM 论文图类型的映射（保持视觉语法，替换数值/合同）

| SIGCOMM 角色 | 论文 Fig | ToN 终稿建议用图 | 备注 |
|--------------|----------|------------------|------|
| Fluidity–QoE trade-off | Fig.5 | `User_Experience_Trade-off/*.pdf` | 同散点/权衡语法 |
| Buffer vs scale | Fig.7 | `Buffer Level/System_Utility_By_Users_scheme1.pdf` | **语义改为 U**（同布局） |
| Stall vs QoE | Fig.8 | **弱化/旁证** `Stall Time/*` + 主推 `QoE/Loot_*` | 勿再宣称 zero stall |
| Throughput bars | Fig.9 | `Throughput/System_Throughput_Bar_*.pdf` | 同柱状语法 |
| QoE by strategy | Fig.8b 类 | `QoE/QoE_By_Strategy.pdf` | QoE 配色锁定 |
| **新增** concurrency crossover | — | `Buffer_Level_By_Users_scheme1.pdf` | Tier-B 核心 |
| **新增** Loot holdout ΔU | — | `Loot_Holdout_DeltaU_By_Users.pdf` | 未见内容 |
| **新增** 机制分解 | — | `Mechanism_Decomposition_Loot.pdf` | Rq/Ro/Rb |
| H2 次级 | — | `H2_Cross_Stack_DASH.pdf` | 明确 secondary |

---

## B. 关键冻结数字（写作必须用这些）

```
MainDev mean ΔU vs strongest same-substrate: +0.016
MainDev MD2G U: 0.675
Loot MD2G U: 0.688
MainDev ΔU @u20/u60/u100: −0.137 / +0.079 / +0.106
Loot   ΔU @u20/u60/u100: −0.160 / +0.083 / +0.111
Scaling ΔU @u10/u20/u40/u60/u100: −0.069 / −0.049 / +0.018 / +0.088 / +0.115
U weights: Ro 0.25, Rq 0.60, Rb 0.15
```

Loot matched W/T/L：u20 **0/0/21**；u60 **21/0/0**；u100 **21/0/0**。

---

## C. 正文何处改 + 修改前后（EN / 中文）

以下针对 `Sigcomm26/Paper6/ToN_manuscript/sections/*.tex`。  
原则：**删掉 SIGCOMM 式 “zero stall / 3–4× QoE / 25–72% bandwidth” 作为 ToN 主结论**；改为 **Tier-B concurrency-dependent utility**，约可增 **2.5–3.5 页**（交叉图、holdout、机制分解、限制）。

---

### C1. Abstract（整段替换）

**Before (EN):**  
> … MD2G-Cast attains completion-adjusted quality of experience 0.609—improving by 25.2% over Rolling and 27.1% over GROOT-MoQ—while keeping playback near continuous among MoQ strategies. Ranking remains stable under QoE weight sensitivity, with primary gains from multi-dimensional grouping and object-granular Base-first admission rather than stall differentiation.

**After (EN):**  
> We extend MD2G-Cast to a nested incremental component contract on Media over QUIC, where logical service states are formed by complementary Base and enhancement layers rather than nine independent full encodings. Under a frozen utility \(U=\mathrm{clip}(0.25R_o+0.60R_q-0.15R_b,0,1)\), same-substrate evaluation against Heuristic, Clustering, and Rule shows a clear concurrency dependence: at low load (20 users) MD2G trails the strongest baseline (mean matched \(\Delta U\approx-0.14\) on DEV; \(\approx-0.16\) on unseen Loot), whereas at 60–100 users it wins consistently (Loot matched \(\Delta U\approx+0.08\) and \(+0.11\), 21/21 blocks). Scaling experiments place the transition near 40 users. The gain is driven primarily by decoded quality \(R_q\), not by claiming zero stall or universal dominance.

**修改前（中文）：**  
沿用相机就绪单内容 QoE=0.609、相对 Rolling/GROOT 提升 25%/27%、并强调“近乎连续播放”。

**修改后（中文）：**  
改为嵌套增量组件合同与冻结效用 \(U\)；明确 **低并发是已知局限、中高并发稳健获益**；Loot 未见内容证实同一交叉形态；收益主因是 \(R_q\)，**不宣称零卡顿或全面碾压**。

---

### C2. Introduction 末段贡献总结（替换末段数字句）

**Before (EN):**  
> … improves completion-adjusted QoE … +25.2% versus Rolling and +27.1% versus GROOT-MoQ … while keeping playback near continuous. Primary gains come from … rather than from a large stall gap …

**After (EN):**  
> On the nested-component substrate, MD2G-Cast does not dominate every regime. Its contribution is a concurrency-aware shared-delivery policy: under matched same-substrate comparison, utility is limited at 10–20 users, crosses over near 40 users, and becomes robust at 60–100 users—including on an unseen Loot holdout sealed until final DEV freeze. We therefore report Tier-B claims: medium/high-concurrency benefit with an explicit low-concurrency limitation, rather than a universal win or a stall-elimination narrative.

**中文要点：**  
贡献从“全面 QoE 提升”改为“**并发依赖的共享投递优势**”；低并发写进贡献边界，而不是藏在脚注。

---

### C3. Metrics 小节（必须改：与冻结 U 对齐）

**Before:** 五分量 \(R_q\) + completion-adjusted \(R_q^{\mathrm{adj}}\) 作主指标；cumulative stall “near-zero”。

**After (EN) — 建议整段替换:**  
> **System utility.** The primary metric is the frozen paper utility
> \[
> U=\mathrm{clip}\bigl(0.25\,R_o+0.60\,R_q-0.15\,R_b,\,0,1\bigr),
> \]
> where \(R_o\) is component-aware reuse (shared versus unicast byte accounting), \(R_q\) is decoded representation quality under the nested Base/enhancement contract, and \(R_b\) is physical bottleneck pressure (not “bandwidth saved”).  
> **Matched \(\Delta U\).** For each (content, network, users, seed) block we compare MD2G to the strongest among Heuristic, Clustering, and Rule. Positive \(\Delta U\) means MD2G wins that block.  
> **Stall (supporting only).** We report decode-gap stall diagnostics when useful, but stall is **not** part of \(U\) and we **never** claim zero stall under this contract.  
> **Cross-stack baselines.** GROOT/Rolling (DASH/HTTP unicast) are secondary system comparisons and are never mixed into same-substrate rankings.

**中文：**  
主指标改为冻结 \(U\)；\(\Delta U\) 为同底物配对差；stall 仅旁证；DASH 只作跨栈附录。

---

### C4. 新增 Evaluation 小节 ≈1.5–2 页：Concurrency Crossover（核心）

**建议位置：** `evaluation.tex` 在 RQ1 之后新增 `\subsection{RQ: Concurrency-dependent utility}`。

**After (EN) draft (可直接粘贴润色后使用):**

> Shared delivery creates a structural trade-off with concurrency. At low fan-out, simpler multicast heuristics can allocate a high-fidelity Base with little contention, so a learned policy that reserves headroom for enhancements may under-deliver relative to rule-based baselines. As the number of receivers grows, overlapping demand and link heterogeneity make uncoordinated upgrades fragile: the shared Base must remain feasible for the weak tail, while refinements should be admitted only when group headroom allows.  
>
> Fig.~X reports mean \(U\) for MD2G, Heuristic, Clustering, and Rule across \(u\in\{10,20,40,60,100\}\) on the scaling matrix. At \(u{=}10\) and \(u{=}20\), MD2G’s matched \(\Delta U\) is negative (\(\approx-0.069\) and \(-0.049\)). Near \(u{=}40\), the sign flips (\(\approx+0.018\)). At \(u{=}60\) and \(u{=}100\), MD2G leads robustly (\(\approx+0.088\) and \(+0.115\)). The same crossover appears on the full MAINDEV grid (\(u{=}20/60/100\): \(\Delta U\approx-0.137/+0.079/+0.106\)).  
>
> This pattern is not an artifact of averaging away failures: matched block counts show systematic losses at low concurrency and systematic wins at high concurrency. We therefore state the claim carefully—**MD2G’s advantage is concurrency-dependent**—and treat the low-concurrency regime as an explicit limitation rather than an anomaly to be tuned away after seeing holdout.

**中文润色版：**  
> 共享投递与并发之间存在结构性张力。低扇出时，简单启发式即可稳定高保真 Base，学习策略若为增强层预留余量，反而可能落后于规则基线。随接收者增多，视点重叠与链路异质使“各自升级”变脆：共享 Base 必须对弱用户可行，增强层只能在组内余量允许时准入。  
> 扩展矩阵上，\(u{=}10/20\) 的配对 \(\Delta U\) 为负，约在 \(u{=}40\) 变号，\(u{=}60/100\) 稳健为正。MAINDEV 网格呈现同一交叉。这不是把失败平均掉的结果，而是分块计数上的系统模式。因此我们把主张写成：**MD2G 的优势依赖并发度**；低并发是明确局限，而非 holdout 之后再调参抹平的异常点。

**配图：** `Buffer Level/System_Utility_By_Users_scheme1.pdf`（或 `Buffer_Level_By_Users_scheme1.pdf` 别名）。

---

### C5. 新增 ≈1 页：Unseen Loot Holdout

**After (EN):**  
> To test content generalization, Loot remained network-sealed until FINAL DEV freeze and was then evaluated as a 315-cell holdout under the same epoch and controller. Matched same-substrate results reproduce the concurrency story without retuning: at 20 users MD2G loses all 21 blocks (\(\Delta U\approx-0.160\)); at 60 and 100 users it wins all 21 blocks each (\(\Delta U\approx+0.083\) and \(+0.111\)). Aggregate MD2G utility on Loot is \(U\approx0.688\), above Clustering (\(0.669\)) and Rule (\(0.664\)), but the headline is the **matched, load-conditioned** comparison—not a claim that MD2G dominates every slice.

**中文：**  
> Loot 在 FINAL DEV 冻结前网络密封，解封后 315 cell 未见内容评估。配对结果复现同一交叉：u20 全负，u60/u100 全胜。总体 \(U\) 有利，但主叙事必须是**按负载条件化的配对比较**，而不是“全面领先”。

**配图：** `QoE/Loot_Holdout_DeltaU_By_Users.pdf`。

---

### C5b. Throughput (supporting; main-text 1×3)

**Caption (EN):**  
> Shared-root TX under 4G, 5G, and Default Mix. Supporting load evidence only: lower TX is not higher efficiency.

**Paragraph (EN):**  
> Shared-root TX (Fig.~\ref{fig:ton-throughput-main}) is protocol-inclusive supporting evidence of delivered load on the MoQ root interface, not a primary efficiency metric and not a substitute for \(R_o\), \(R_b\), or \(U\). At higher concurrency, MD2G’s TX often sits between Heuristic and Clustering rather than minimizing bytes; the same-substrate utility gain at \(u{\ge}60\) therefore cannot be read as “lower TX equals better.” Cross-stack DASH/HTTP comparisons (GROOT/Rolling) remain separate end-to-end system results and must not be mixed into this same-substrate TX reading.

**配图：** `Throughput/System_Throughput_MainText_1x3.pdf`。

---

**After (EN):**  
> Decomposing Loot outcomes at \(u{\ge}60\) shows that MD2G’s utility edge is associated primarily with higher decoded quality \(R_q\), while \(R_o\) remains high and similar across shared MoQ strategies. \(R_b\) captures bottleneck pressure and must not be narrated as “bandwidth savings.” Relative to MOQ unicast, shared MD2G retains a large delivery-mode gap (\(U\approx0.688\) vs.\ \(0.194\)), but that contrast isolates architecture (shared vs.\ unicast), not controller skill within the shared substrate.

**中文：**  
> 在 \(u{\ge}60\) 分解可见：优势主要来自更高 \(R_q\)；共享 MoQ 策略的 \(R_o\) 普遍偏高且接近；\(R_b\) 是瓶颈压力，**不得写成省带宽**。相对 MOQ 单播的差距属于投递架构对比，不能冒充同底物控制器胜负。

**配图：** `Mechanism_Decomposition_Loot.pdf` + `MoQ_Shared_vs_Unicast.pdf`。

---

### C7. Stall 段落（evaluation Fig.stall 处）— 关键改写

**Before (EN):**  
> End-of-session means are approximately 0 s for MD2G, H, R, and G … near continuous …

**After (EN):**  
> Under the nested-component contract we do **not** reuse the SIGCOMM-era “zero stall versus multi-second DASH stall” comparison. Stall is retained only as a supporting decode-gap diagnostic; primary claims rest on \(U\) and matched \(\Delta U\). Where stall series are shown, they must be captioned as continuity checks and must not imply stall elimination as the source of MD2G’s gain.

**中文：**  
> 嵌套组件合同下，**不再沿用** SIGCOMM“MoQ 零卡顿 / DASH 数十秒卡顿”的对比。Stall 仅作连续性旁证；主结论建立在 \(U\) 与配对 \(\Delta U\) 上。图注必须写明 continuity check，禁止把“消除卡顿”写成 MD2G 收益来源。

---

### C8. Conclusion（替换）

**After (EN):**  
> MD2G-Cast on nested incremental components delivers a concurrency-dependent shared-delivery benefit under a frozen utility contract. Same-substrate evidence—from MAINDEV, scaling, and sealed Loot holdout—supports medium/high-concurrency gains driven mainly by decoded quality, together with an explicit low-concurrency limitation. We reject universal-dominance and zero-stall narratives for this contract. Cross-stack DASH baselines remain secondary. Future work includes hierarchical multi-relay coordination and broadening content beyond the evaluated sequences—without post-holdout retuning.

**中文：**  
> 嵌套增量组件上的 MD2G-Cast，在冻结效用合同下呈现**并发依赖的共享投递收益**：MAINDEV、扩展与密封 Loot 共同支持中高并发增益（主因解码质量），并显式承认低并发局限。本拒绝“全面碾压”与“零卡顿”叙事；DASH 仅为跨栈次级证据。未来工作在不触碰 holdout 后调参的前提下，扩展多中继与内容多样性。

---

### C9. Limitations（补强，半页）

应明确列出：  
1. u10/u20 same-substrate 劣势是**接受的科学结果**；  
2. Scaling 150 keys = 90 DEV reuse + 60 new launches（勿称 150 次全新实验）；  
3. A1–A5/A7、FoV 为 NOT_APPLICABLE，不作机制验证图；  
4. Stall/delay 不进最终 claim 合同；  
5. H2 GROOT/Rolling 不可写入主表与 MD2G 并列。

---

## D. 建议增页结构（≈3 页）

| 页量 | 内容 | 图 |
|------|------|----|
| ~1.0 | Concurrency crossover 叙事 + 机制解释 | System_Utility_By_Users_scheme1 |
| ~1.0 | Loot holdout matched ΔU + 内容/网络稳健性 | Loot_Holdout_DeltaU + QoE_By_Content/Network |
| ~0.75 | Rq/Ro/Rb 分解 + shared vs unicast（架构） | Mechanism + MoQ_Shared_vs_Unicast |
| ~0.25 | 限制与 claim 边界（Tier-B） | 无或小表 |

---

## E. 写作禁令（solid 检查清单）

- [ ] 全文无 “zero stall / Goal achieved / 日志口吻 / 堆砌 PASS token”  
- [ ] 无 universal MD2G dominance  
- [ ] u20 负面结果出现在摘要或贡献边界（不是只藏 limitation）  
- [ ] 主对比 = MD2G vs HV3/Clustering/Rule  
- [ ] GROOT/Rolling 仅 secondary  
- [ ] 每个 headline 数字可追溯到 `FINAL_LATEX_NUMBERS.tex`  
- [ ] Stall 图若保留，caption 含 “supporting only / not in U”
