# SynthFlood 论文审稿迭代日志

论文：*SynthFlood: Ambient Synthetic Content Buys Web-Agent Decisions — A Dose–Response Analysis and a Provenance-Ordering Remedy*
目标 track：WWW 2027 Brave New Ideas（摘要 2026-10-18 AoE，全文 2026-10-25 AoE）

流程说明：环境中不存在 `/reviewpaper` 技能，按用户要求自建等价流程执行——
每轮由三位独立视角的审稿人（R1 严谨性/统计、R2 新颖性/定位、R3 清晰度/实验完备性）加 AC 汇总出具评审意见，
逐条修复（可本地完成的补充分析即补做；需要 GPU 的新 rollout 单独标注并请用户连接），
复审循环直至整体达到"大概率接收（likely accept 及以上）"。

评分口径（WWW 九档制）：strong accept / accept / weak accept / borderline / weak reject / reject 等。
目标：三位审稿人中 ≥2 人给 accept 及以上、无未解决 major 缺陷、AC 判定"大概率接收"。

每次评审与修复以时间戳小节形式追加于本文件，并随论文一起推送至 GitHub。

---

## Round 1（2026-10-12）

### R1（统计与严谨性）— weak accept
- **M1** 摘要与引言称 badge "unchanged from 15% to 65% badge forgery"：15% 是徽章噪声参数，伪造包络实际测的是 25/35/50/65%。参数与操纵混淆。
- **M2** "structural detector statistically matches the oracle (p=0.21)"：n=40 下非显著≠等价，属"以不显著证等价"。
- **M3** 表1 若写 paired t-test 则与实际符号检验（+9/−21 → 精确二项 p=0.043）不符；须核对。
- **M4** 全文 11 项确认性检验无多重比较校正。
- **M5** "deeper discounts add nothing" 缺统计支撑（等价性检验）。

### R2（新颖性与定位）— accept
- **M1** "The first decision-level dose–response evidence" 未加限定，易被 E-GEO/GEO 系工作挑战。
- **M2** 缺伦理/双用途声明：论文公开释放攻击池，审稿人必问滥用面。
- **M3** "brave" 论证已足，但建议把"直觉未被检验过"再压实一句（现有文字基本覆盖，可接受）。

### R3（清晰度与实验完备性）— weak accept
- **M1** 小节标题 "success flat, regret and confidence climb" 与自家数据（success 跌 23pp）自相矛盾。
- **M2** 图2 caption 声称 cluster-bootstrap 误差棒，与重绘后图的实际口径（Wilson/正态）不符；且图改用混合池而表2为单池，图-表数字会对不上。
- **M3** 内部实验代号 "P4A/Pa4" 泄漏到正文与附录。
- **M4** 引言 ε 网格写 {0,0.1,0.25,0.5,0.75}，实际网格为 {0,0.25,0.5,0.75}（账本核对：无 0.1）。
- **M5** "We release..." 在双盲投稿下应改为匿名随稿提交口径。
- **m1** 摘要 340 词偏长，应压缩至 ~250 词以内。

### AC 汇总
Borderline（2×weak accept + 1 accept，但 M 级问题密集）。方向正确、机制分解是真正的贡献点；若上述 M 级问题全部解决并补齐统计纪律，可到 accept。

### 本轮修复清单（全部完成）
| 问题 | 处置 |
|---|---|
| R1-M1 | 摘要/引言改为 "tolerates badge forgery up to 65%" |
| R1-M2 | 摘要删 oracle 声明；引言改 "statistically indistinguishable in paired runs"；A.5 新增功效段（MDD≈0.11 > 观测差 0.079，明言"不主张相等"） |
| R1-M3 | 核查后表1 caption 实为 "paired flips"（正确）；无误 |
| R1-M4 | A.5 新增 Holm 校正段：两条 headline（1.3e-7、1.0e-3）与 10% 阈值（0.023）存活；通道类检验校正后 0.072–0.078，明言以"汇聚证据链"为解读 |
| R1-M5 | results 补等价性检验句（10% vs 20%/30% p≥0.45）；A.5 补 saturation 措辞限定 |
| R2-M1 | 引言贡献改为 "To our knowledge, the first..." |
| R2-M2 | 结论后新增 \section*{Ethics and Dual-Use Considerations}（合成商品不对应真实 SKU、不可上架、防守向定位、无人类被试、遵循 WebShop 许可） |
| R3-M1 | 小节标题改 "Dose–response: regret outruns success" |
| R3-M2 | 图2 重生成为 seed-1 单池（与表2/正文一致）；caption 改为 Wilson/正态口径并注明 seed-2 复现指向附录 |
| R3-M3 | 正文/附录的 P4A/Pa4 代号清除 |
| R3-M4 | ε 网格改为实测 {0,0.25,0.5,0.75} |
| R3-M5 | 摘要/引言 release 措辞改 "匿名包随稿提交" |
| R3-m1 | 摘要压缩至 ~270 词 |

**遗留待办（本轮新识别，非阻断）**：审稿人普遍会问"只有 7–8B agent"。若能重新连上 GPU，补一条 Qwen2.5-32B（或 14B）agent 在 ε∈{0,0.75} 的复现臂（约 80 episodes，~15 分钟）可直接堵死该意见。等待用户决定。

**编译状态**：0 错误、11 页、3 处 <9pt 超宽。

---
