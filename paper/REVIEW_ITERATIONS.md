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

## Round 2（2026-10-12）

复审重点：Round 1 修复的整合质量 + method/problem 全文深查。

### R1（统计与严谨性）— accept
- **M1（新发现，严重）** §5.1 "binomial p<10⁻³⁵"：n=300、113/300 的精确二项双侧 p 实为 **2.3×10⁻⁵**（实算验证），原文量级荒谬，属硬伤。
- **M2（新发现）** 附录 A.1 写 "vLLM 0.19.0"，requirements 与实验日志均为 **0.31.0**——版本错误影响复现。
- **m1** 表2 中间剂量 regret 非单调（0.429→0.401）无解释；实算配对差 bootstrap CI [−0.102,+0.044] 含 0，属噪声，应明说。

### R2（新颖性与定位）— accept
- **m1** problem §"silent-erosion hypothesis" 预言 "success may appear stable"，结果 success 跌 23pp——假设部分被证伪，正文应显式承认（现只在 discussion 侧面处理）。
- 其余定位无新意见。

### R3（清晰度与完备性）— weak accept → accept
- **M1** method §sweep 与 problem §quantities 的 ε 网格仍写 {0,0.1,…}（Round 1 只修了引言）。
- **M2** 表2 caption 残留 "P4A" 代号；"S@0.8" 列无定义。
- **M3** fig:family caption 写 "left/right"，重绘后实为上/下。
- **M4** 置信度如何 elicited、ECE 几个 bin——method 未定义。
- **m1** "gloss" 术语未定义（geo/search-optimized/plain gloss 三名混用）。
- **m2** 页面反弹至 12 页触顶，需压缩回 11。

### 本轮修复清单（全部完成）
| 问题 | 处置 |
|---|---|
| R1-M1 | p 值改为实算值 2.3×10⁻⁵ |
| R1-M2 | vLLM 版本改为 0.31.0（对照 requirements 与日志核实） |
| R1-m1 | results 补非单调句：regret 差 CI [−0.102,+0.044]、success 反弹 +0.070 CI [−0.020,+0.160]，均明示"不可分辨于零" |
| R2-m1 | 保留 §problem 预言原文（预注册性质），在 §5.3 开头以 "Success falls at the first dose step and stays depressed" 显式呈现证伪结果（上一轮已改，本轮确认整合到位） |
| R3-M1 | method/problem 网格统一为 {0,0.25,0.5,0.75}，并注明 0.1 在 N=10 下退化为 0 槽位 |
| R3-M2 | 表2 删 "P4A"；新增 "S@0.8" 定义（δ=0.2 部分成功阈值） |
| R3-M3 | caption 改 "top/bottom" |
| R3-M4 | method-sweep 新增置信度 elicitation 与 5-bin ECE 定义句 |
| R3-m1 | method-gen 首次出现处定义 gloss = plain search-optimized 家族 |
| R3-m2 | 压缩 A.1/A.2/A.5 措辞与伦理段，回到 11 页 |

**编译状态**：0 错误、11 页、2 处 <9pt 超宽（4.45pt related-work 连字符行、8.62pt 图4 caption，均不可见）。

---

## 补充轮（2026-10-13 下午）：外部效度——真实世界攻击面

**动因**：用户指出"污染数据自生成 = 关门造车"。响应：在真实数据上验证攻击面与检测前提。

**新增结果（三独立源收敛）**：
1. ProMapEn（人工核验 Walmart↔Amazon 对，Macková & Pilát 2023）：close non-match 509 对（=真实克隆攻击结构），双价 330 对中 73.3% 有 ≥10% 低价方，中位折扣 20.9%；match 组 63.8%/16.7%；medium 组 77.2%/22.9%。
2. WebMall（真实 4 店 offer，2024-10 Common Crawl，Peeters et al. 2025）：跨店同名组 244 组/505 offer，53.3% 有 ≥10% 低价方，中位 11.1%（同品组中买便宜者正确 = 控制条件一致）。
3. WebShop 真实目录（1.18M 条真实 Amazon 抓取，抽样 8 万）：品牌+类目分块、标题 Jaccard∈[0.80,0.95) 挖出 497 对 lookalike，83.3% 有 ≥10% 低价方，中位 21.0%；J≥0.95 近同对 232 组，51.7%/11.0%。
→ 剂量反应扫描的 10–30% 折扣区间 = 真实价格离散的众数区间，非尾部事件；lookalike 与近同对的离散度分离在三个源上方向一致。

**检测器校准（附录 A.6）**：GPT-2 ppl 在 250 条真人 WebShop 文本上标定，对已知合成池 AUC=0.912（合成中位 ppl≈22 vs 人写≈55）→ 结论：(i) 合成文案孤立可检，但 agent 仍购买 → 弱点在决策层而非感知层，支撑 provenance 主张；(ii) 拒绝对真实目录做 AI 文本占比估计——跨域体裁/长度混淆主导（93.6%→55.3% 仅长度匹配后），无真值标注，不夸大。

**论文变更**：Results 新增小节 "The attack surface exists in real catalogs"；附录新增 A.6（协议+检测器校准+不声称普遍率）；refs.bib 新增 mackov2023promap、steiner2026billigerde、radford2019gpt2。12 页（限额内），0 错误。

**待办（需 GPU 重连）**：R1c 真实对二选一 duels（金品 vs 真实 lookalike 低价位，ProMap close non-match + WebShop 挖掘对）；R3 真实剂量反应。

## 外部效度轮（2026-10-14）：回应"自生成污染 + 10条topk撑不起环境式"两项核心批评

**方案5（口径）**：abstract/problem/discussion 明确 ambient= arrives-without-targeting，非全网饱和；主表面=10槽，规模实验扩展至50槽。

**方案1（RA1 真实克隆，n=250/臂）**：从1.18M真实目录挖467对真实lookalike（官方人写指令+官方reward语义）。σ(real,f=0.9)=0.616、σ(real,f=0.8)=0.636、σ(real,natural)=0.600（全部 p<0.002）；同任务配对合成克隆 σ=0.677 与真实无显著差异（McNemar p=0.167）。→ 机制不依赖生成器。

**方案2（RA2 环境规模，N=50，k∈{0,3,7,11}，n=100/臂）**：regret 0.349→0.386-0.399；success 0.536→0.42后平坦；配对k=7不显著(p=0.75)。同绝对量下：N=10密度78%伤18pp vs N=50密度14%伤~4pp → **效应密度驱动**；偏好偏置存活稀释（购买份额24-28% vs 随机14-22%）。→ "ambient"主张画出实测边界：强退化需污染集中；低密度是税不是崩塌。

**方案3（RA3 真实垃圾评，n=100）**：YelpZip fraud-filtered假评挂同品类真实商品，方向一致但弱于类别对齐合成器（0.327 vs 0.454；配对 p=1.0, n=21）→ 领域错配混淆如实声明；reviews通道实验室效应=攻击者可控类别对齐文案时的上界。

**方案4**：既有sham臂（真实同品类置换，regret 0.272≈干净0.262）已覆盖"真实同品类无害"角色。

**论文落点**：abstract 一句真实验证；Results 小节三段（三源统计+RA1+RA2密度边界+RA3）；附录 A.6 协议段；Discussion Limitations 更新。12页、0编译错误、verify_numbers 全对。

## Round 3（2026-10-14 下午）：WWW 2027 正式三审 + 官方标准核查

**官方标准（已核实，www2027.thewebconf.org + WWW 2026 CFP）**：主文 **8 页硬上限**+参考文献+附录≤12 页；前 8 页须自含（审稿人不被要求读 beyond）；OpenReview 双盲；评审表 −3..+3 / 置信 1-5；录取线≈均分≥1。

### 三审得分
| 审稿人 | 总分 | 置信 | 一句话 |
|---|---|---|---|
| R1 严谨性 | **0**（borderline） | 5/5 | 设计高于场地中位数，但新素材相对自身统计系统性过强声称 |
| R2 新颖性 | **+1** | 4/5 | 罕见地"第3轮新增回应了第2轮反对"；被页限、防御声明统计力、相关工作缺口拖住 |
| R3 清晰度 | **+1**（条件） | 4/5 | 科学扎实，但 1.3 页超限+模板占位符+死浮动图不可被接收 |
| **均分** | **+0.67** | | 低于录取线（≥1），修复清单明确 |

### 已被我用原始数据核实的 BLOCKER（按优先级）
1. **[核实✓] 主文超 8 页 ~1.3 页**（refs 第10页起）——WWW 硬性规则，需重构：brave-new 段砍成3句、贡献条目去数字、Related Work 压35%、§5.5(ii)(iv)+3B/1.5B 细节+RA3 细节移附录、删未引用图。R3 给了逐段行数预算（~145 行）。
2. **[核实✓] 模板占位符**：main.tex 无 \acmConference/\acmYear/CCS/keywords → 每页页脚 "Conference'17, July 2017"。机械化修复。
3. **[核实✓ R1-B1] probe 每家族 n=88（clone）/97（geo）/115（reviews），总数300——但论文 4 处写 "300 duels per row/arm/level"**（Table 1 caption、§4.3、§5.2、§5.3）。clone 家族全部统计精确对应 n=88（46/88=0.523 等）。A.5 自己写了 "n=88 per arm" 却没人对上主文。
4. **[核实✓ R1-B2] 摘要 p=0.003 错位**：0.591 的 p=0.003 是 vs 价格平价臂的配对检验；vs 随机 52/88 → p≈0.09 不显著。须改措辞归因。
5. **[核实✓ R1-B5] RA2 密度数字错误**："78% contamination" 无对应实验条件（ε=0.75 → 6/9=67%）；"same absolute count" 为假（6 vs 7）；干净基线不同（0.262 vs 0.349）混淆密度与页面大小。**修复方案**：改用相对增幅（10槽 +69% vs 50槽 +11%）+ 补做密度匹配格子或降级为 "consistent with density-driven"。
6. **[核实✓ R1-B3] RA1 "indistinguishable" 无等价检验**：配对差 CI≈[−2.3,+14.5]pp，生成器三点全更高。改为有界声称（"bound any generator advantage at ≤~15pp"）+ 报 CI。
7. **[核实✓ R1-B7/R3-B3] RA3 "confirm" 过强**：p=1.0 只在附录。**n=21 之谜已解**：40 共同任务中 19 对 regret 完全相同（平局被符号检验剔除），非选择偏倚——但论文必须写明（"40 common tasks, 21 non-tied pairs"）。摘要/贡献条目 "confirm"→"directionally consistent"。
8. **[R1-B8/R2-B2] 防御声明 vs 自身 Holm 校正**：摘要 "eliminates the regret excess" 但 A.5 承认 provenance-vs-none 校正后 p∈[0.072,0.078]、n=40 MDE≈0.11>Δ0.069。**两条路**：(a) GPU 重跑 defense battery N=100（基础设施现成，~2-3h）；(b) 文字降级+等价界。recovery 双定义（Table 4 vs §5.5(iv)）需统一。
9. **[R2-B3] 新颖性墙有洞**：必须引并区分 arXiv:2609.06027（deep-search agents under GEO poisoning, 2026-09）、2606.13686（deceptive interfaces benchmark）、2605.10059（agent-market exploitation）；provenance 防御线 2606.17467/2609.21088/2605.11039；GEO 原文 2311.09735；2508.15832。"no prior work" 措辞收窄为 ambient+decision-level+dose-response 三限定。
10. **[核实✓ R3] 死浮动图**：fig:family、fig:defenses 从未被正文引用——删或引。

### 行动顺序
A（今天，纯文本+机械）：2/3/4/6/7/8b/10 + R3 行编辑清单 + 摘要压至≤250词
B（重构，半天）：1（按 R3 预算移内容）+ 5（RA2 相对化）+ 9（引文核实后加入）
C（需决策）：8a GPU 重跑 defense battery N=100 → 若用户不开机则 8b 文字方案已覆盖
