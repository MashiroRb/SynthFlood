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

---

## 决定记录（2026-10-15）：RA2 从论文整体剔除（作者决定）

**决定**：用户裁定 RA2（50 槽规模实验）从论文中剔除，并要求淘汰其"密度驱动"解释。

**动因（作者核查会上的复算）**：同密度配对对比（10 槽 ε=0.25，2 条，密度 22.2% vs 50 槽 k=11，11 条，密度 22.4%，同一批 100 任务）显示买假货率 53.1% vs 24.0%——**密度不是驱动变量**；两页面内部买假货率均随条数立即饱和（10 槽 2→6 条：53/42/54%；50 槽 3→11 条：25/28/24%）；购买位置数据（10 槽假货 51/53 落在第 3 位 vs 50 槽平均第 14 位）指向"AI 实际查看的位置带构成"才是作用面。原 RA2 段落（results.tex:402-414）同时含 78% 与 same-absolute-count（6 vs 7）两处已核实错误（R1-B5），修复成本高于删除价值。

**执行（全部完成）**：
1. results.tex 删除整段 "\paragraph{Ambient scale: dilution attenuates the harm.}"（原 402-418 行）
2. appendix.tex 删除 "\emph{RA2 (scale).}" 句（RA3 保留）
3. 三处下游"density"论断改写为有支撑表述（RA2 是其唯一实验支撑，不删话即成无据声称）：
   - abstract.tex：删 "and a fifty-slot surface experiment localizes the strong harm to contamination density"
   - introduction.tex 贡献条目：删 fifty-slot 分句，RA1 与 RA3 直接衔接
   - discussion.tex：real-document 句改为 "close the self-generation gap for the clone channel and narrow it for reviews"
4. 干净重建：清陈旧 bbl（曾复用 repo_clone/paper/main.bbl 致 5 个未解析引用）后 latexmk 全重跑 → **0 未解析引用、12 页、无错误**；refs.bib 全部键在（mackov2023promap/rayana2015collective/radford2019gpt2/steiner2026billigerde 已对账）

**数据保留**：RA2 原始数据与分析脚本留在仓库（results_realattack/ra2_*.{csv,json,py}），不进论文；同密度配对复算脚本逻辑记录于本轮会话。

**修复清单状态更新**：BLOCKER 5 关闭（以剔除方式解决）；行动顺序 B 中的 "5（RA2 相对化）" 作废。

**遗留提示（供 B 阶段重构时处理）**：RA2 删除后，标题与叙事的 "dose–response" 框架仅由主曲线承载；主曲线污染档内 regret 实为平台（0.429/0.401/0.443，台账已对账），即"阈值+平台"而非渐变剂量反应。B 阶段重构时应将叙事校准为 threshold-and-plateau（或仅在补跑低剂量点后保留 dose-response 措辞）。此点与 R1-M4/R2-m1 的非单调披露一脉相承。

---

## 更新记录（2026-10-15）：数据一致性全面核对 + teaser 图（作者指令）

**指令**：更新初稿——①图/表/文字/实验结果必须匹配；②新增概括全文的 teaser figure；③检查逻辑表述；④实验结果不许夸大。

### 一、全量数字核对（对原始 CSV 逐项复算）

**核实无误 ✓**：表2全列（含 ECE 0.249/0.498/0.453/0.496，success_full 为 outcome、5 bins）；表4全部8行；λ 扫描6值；naive p4k；Llama-8B（p4d_llama_sweep.csv：0.475→0.300 成功、0.346→0.502 regret、bought 0.550）；3B/1.5B；池化购买 reward synth 0.345/real 0.801；CA 趋势 z=6.984 精确复现；p4b 家族臂；RA3 干净基线 0.294；stealth Wilcoxon p=0.022；p4m/p4h/p2 任务集对齐（40=40）。

**发现并修复的实质错误**：
1. **stealth recovery 混口径**（正文+图+讨论三处）：原文用 100 任务基线 0.443 与 40 任务防御值混算出"恢复 0.193→0.138、损失 28%、保留 72%"。统一 40 任务口径后：struct recovery 0.148→0.139（**保留 94%，无侵蚀**）、provenance 0.069→0.153；stealth 攻击并不更温和（0.425 vs 0.398，n.s.）。make_figs.py stealth 面板 on=0.443→0.398、标题改 "(c) Stealth pool: defenses intact"、λ 面板参考线同步改 0.398，图已重生成。
2. **random 防御动词反了**：0.172<0.338 是**改善**干净页（均匀丢弃两成候选可提高金品排名）；污染下 0.431 不优于不设防 0.398。原句 "raises" 已改。
3. **RA1 附录无据数字**："0.624 vs 0.588" 无任何数据来源 → 替换为 real_f080 0.636 vs real_nat 0.600 配对 McNemar p=0.093（16 vs 7，n=250）。
4. **RA3 幅度错误**："roughly half the magnitude" 实为 +11% vs +54%；21 非平局对（11 worse/10 better, p=1.0）——只声称方向。
5. **3 处 "300 duels"** → "n=88 clone duels"（克隆比较的承载量）；A.3 池大小 480→1200 生成/1089 可用。
6. **p=0.003 归属**：59% vs 39% parity 对比的配对检验，非 vs 随机。
7. 删除死浮动图 fig:family、fig:defenses；problem.tex "fifty slots" 句删除。

### 二、去夸大改写（摘要/引言/结论/结果/讨论 12 处）

- "eliminates the regret excess" / "full loss of the excess" → "recovers in point estimate (significant uncorrected, marginal after family-wise correction)"
- "regret rises 69%" → "rises 69% and plateaus"（阈值+平台校准，中间档 CI [−0.102,+0.044] 为噪声）
- "flip the majority"（4 处）→ "restores majority-level clone preference (0.591 vs 0.386 parity, paired p=0.003)"
- oracle "statistically indistinguishable from struct (p=0.21)" → "gap 0.079 below MDE ≈0.11，不作等价声明"
- RA1 "close to real clones" → 附 95% CI [−2.3,+14.5]pp 界定
- RA3 "reproduce the direction (not its significance)"
- 骨干比较 "27% more regret" → "rises by a further 27% in relative terms"

### 三、teaser 图（Figure 1，页2顶跨栏）

- 新建 repo_clone/paper/make_teaser.py（4 面板：(a) 污染结果页示意 9 行含 6 条 synthetic；(b) 通道分解条形图 0.523/0.386/0.386/0.250+Wilson CI+机会线+gloss 基线；(c) 剂量 regret 0.262→0.429/0.401/0.443±95%CI 标注 jump-then-plateau；(d) 防御条形图 0.398/0.364/0.329/0.250/0.171+clean 虚线 0.338）
- 迭代 4 版修排版：面板标题互相重叠→缩短+wspace 0.52；示意图文字/价格列碰撞→列定位+字号；"6 of 9"标注与行数不符→9 行 6 synthetic；(b) 轴标签挤压→单词化；(c) 标注出界→移位。全部数字来自 p1_*/p4a_sweep/p2_sweep/p4c_* CSV
- introduction.tex 插入 figure*[t] + 逐面板 caption + \Description 无障碍文本 + 正文引用句；teaser.pdf 入 figures/
- 干净重建：**0 未解析引用、12 页、无大溢出**；pdftoppm 目检页2版面正常；模板字段（WWW '27, April 2027 / Anon.）正常显示

### 四、同步与一致性

- 初稿/ ↔ repo_clone/paper/ 双向补齐（make_figs.py、make_teaser.py、4 张再生成的图、全部 tex）后 **TEX-IDENTICAL + FIGS-IDENTICAL**（排除构建产物）
- **未提交/未推送 GitHub**（待作者指令）

### 修复清单状态
2✓(模板字段) 3✓(n=88) 4✓(RA3) 5✓(RA2剔除) 6✓(Llama) 7✓(stealth口径) 8b✓ 10✓(死图)；**待办：1（8页重构，B阶段）9（新颖性引文，需 paper_search 核实后加入）8a（GPU 重跑，需作者决策）**

---

## 更新记录（2026-10-15）：M1 洗脱实验写入论文（作者指令）

**指令**：作者确认 RA2 已删干净后，要求把已完成的 M1（洗脱/内化）实验写入论文替换其位置。

**RA2 残留核查**：逐模式精确检索 fifty/50-slot/RA2/ambient scale/dilution/absolute count → 仅 related.tex:11 的引文键 `bara2026epistemic` 含子串 "ra2"（误报），内容零残留 ✓。

**写入内容（全部数字先对 m1_summary.json / M1_EXPERIMENT_LOG.md / PRE_REG_M1.md 核账）**：
1. **results.tex §5.8 "Exposure leaves a memory-carried residue"** + 表5（5臂×4检查点 σ）：
   - 快通道：exam@0 0.897 vs 空记忆 0.692（McNemar 9/1 p=0.021），半衰期 4 集，@20 归零（0.667 vs 0.718 p=0.62）——**预注册内化检验如实报"未命中"**；M2 写而不读无抬升（0.692 vs 0.897, p=0.025，预注册主检验4命中）
   - 慢通道（本实验最重要）：平价考试 0.790→0.763→0.842 不降反升 vs 等经验对照 0.579（z=2.53 p=0.011，预注册次级检验）；"泡过脏水的 agent 看全价仿冒品 = 新手看 9 折品"
   - 载体/干预（方向性）：M4 删价格条目 0.897→0.744（p=0.077）、M3 纠错 0.769（p=0.13）；平价考试 M2 0.526 vs M0 0.790（未校正 p=0.016）
   - 验尸：38 次买假货仅 2 次不亏（反事实 gap −0.63）→ 非环境奖励；同品类迁移无抬升（0.718 vs 0.744 p=0.80）
2. **abstract**：Three→Four findings + 第四发现句（~55 词）
3. **introduction**：测量清单 3→4（补 washout experiment 分句）+ 第 6 条贡献条目
4. **discussion**：新段 "Memory as the attack surface."（记忆作为攻击面：curation/过滤成为防御原语）
5. **conclusion**：补一句记忆残留
6. **appendix A.7**（app:m1）：五臂定义、检查点/考试池出处（pairs[250:290)/[290:330)，与他实验零重叠）、8 次生成失败已记录（n=39/38 固定剔除）、种子表、预注册主检验四分支的命中情况（H1 未命中/部分衰减命中/记忆因果命中）、平价持久化为预注册次级、迁移矩阵如实记录（同品类 n.s.；**跨品类无法执行**——剩余配对全落在暴露 5 品类内，记为可行性限制；xdom 1.00 vs 0.70 p=0.008 但 M2/M4 也高→exploratory 证据混合）、验尸协议

**纪律要点**：跨品类迁移不写"无差异"（实验没跑成）；xdom 标 exploratory 且披露 M2/M4 也高；快通道的"内化"预注册失败如实写；平价持久化标注"预注册次级检验、降格表述"。

**状态**：干净重建 0 未解析引用；**总页数 13（超 WWW ≤12 上限 1 页）**，正文到 p10（超 8 页红线 2 页）——8 页重构从"待办"升级为**投稿前必做**；M1 小节在 p9、附录 A.7 在 p11-13。初稿 ↔ repo_clone/paper 再次逐字节一致（TEX/FIGS-IDENTICAL）。未提交 GitHub。

## Round R3 — 按第二轮模拟评审意见修改（2026-10-16）

### B1 页数（最高优先，desk-reject 风险）
- 结果：**正文（含 Ethics）恰好收在第 8 页内**，References 从第 9 页顶部开始；总页数 12 ≤ 12 ✓（WWW 规则：正文 8 页 + 参考文献/附录 ≤12 总页）
- 手术清单：Fig.3（dose_response 五联图）整体删除（数字全部在表2/正文）；Fig.4（defense_stress）删除（与表4/正文重复）；§5.4 family 表下沉附录 A（sec:app-family）；§5.6 backbone 下沉附录（sec:app-backbone，正文留 §5.5 尾 \paragraph{Backbone generality.}）；§5.8 M1 压成 ~19 行摘要版、表5 与两通道完整叙事归并附录 A.7（A.7 本就有完整实验描述与结果叙事，无重复成本）；§5.7 real-docs 压成 1 段（细节+Headline mining numbers 补进 A.6）；Related 第4段（shopping-agent benchmarks）并入 Method §4.1；"What is brave and new" 整段删除；摘要 409→~250 词、编号 (1)-(4)；brave 定轨注释改为 Research Track；全文 ~40 处微压缩（intro/related/problem/method/§5.1-§5.8/discussion/conclusion/ethics）
- 顺带：Fig.2 宽度 0.92→0.88\textwidth

### B2 引文（已完成）
- refs.bib +2：bi2026evaluating（arXiv:2609.06027）、zhang2026deepresearch（arXiv:2605.24245），逐字来自本会话 paper_search 结果
- related.tex 两句区分："Both measure the quality of retrieved evidence and synthesized answers; neither measures what a purchasing agent chooses on a single results page, and neither varies contamination dose."
- GEO 原始论文（arXiv:2311.09735）三次检索均不可得 → 按零编造规则放弃添加，wu2025what 引用保持

### B3 聚类（已完成）
- scripts/cluster_probe.py：30 任务簇、20k 次重采样、seed 2027；88 clone duels 跨 27/30 簇
- 全部 probe 统计改任务级 cluster bootstrap CI；duel 级 McNemar 保留为预注册检验；Holm 不变
- §5.2 诚实降级：price parity 单通道任务级 p=0.097 方向性；结论挂 full parity（Δ=+0.273, CI [+0.176,+0.390], p<0.001）+ 阈值律（+0.205, CI [+0.050,+0.365], p=0.011）
- A.5 新增 "Cluster robustness" 段；表2 题注补 S@0.8≡Success 解释（400 场仅 1 个 reward∈[0.8,1)）；表3/4/5 题注补 Wilson 半宽注

### 其他 SHOULD-FIX
- §5.2 "almost twice"→"three times as often as chosen"（3:1 算术修正）
- §5.8 "does not decay — it ends higher than it started"
- 摘要残句修复；intro bullets 阈值改 cluster-robust p=0.011、删单种子 p
- conclusion 阈值 p 改 0.011 与正文一致
- conclusion.tex "measurable, not anecdotal"

### 验证
- 干净重建 0 未解析引用；verify_numbers.py 0 失配；初稿 ↔ repo_clone/paper TEX-IDENTICAL + FIGS-OK
- 遗留：Fig.2(b) 标注精简（低优先）；M1 第二种子 rebuttal 实验（需 GPU，未决）；防御电池 N=100（未决）

---

## ⏸ 待拍板事项（等待用户决定，2026-10-16 状态快照）

新对话接手时读本节即可恢复上下文。三件事均已向用户详细解释过原理，等用户点头：

### ① M1 第二种子 rebuttal 实验（用户未决定）
- **是什么**：M1 = 洗脱/残留实验（附录 A.7，`m1/PRE_REG_M1.md` 预注册 + `m1/M1_EXPERIMENT_LOG.md`）。5 臂（B0 干净基线 / M0 暴露主条件 / M2 写而不读 / M3 纠错 / M4 记忆手术）+ 共享前测 PRE。暴露 20 轮 ε=0.75 → 干净洗脱 20 轮，检查点 [0,2,...,20] 每次重考整份 39 道打折卷（f=0.90 克隆）+ 平价卷（f=1.00）在 {0,10,20}。
- **为什么跑**：现在只有 seed=2027 单种子；Limitations 已承认 single-model, single-seed。审稿人可攻击"慢通道残留 σ=0.842 vs 0.579 (p=0.011) 是不是这一个种子的运气"。换 seed（如 2028）重跑全流程：复现 → 论文加"第二种子复现"；不复现 → 降级表述。
- **成本**：代码/预注册/流水线现成（`m1_pipeline.sh`），4090 后台约几小时。
- **注意**：本会话 Lab Compute 未连接；开跑前需确认 lab_exec 可用。

### ② 防御电池补到 N=100（用户未决定）
- **是什么**：§5.5 表 4 防御臂（prov/struct/ppr λ 扫描/spoof25/50/reviewtrust/流行度/text/oracle/sham）。现状：ppr 等扫描臂各 40 任务、provenance 主臂 80（results_csv/p4*_sweep.csv）。
- **为什么跑**：发现#3 两条次级结论（provenance 恢复 regret 超额、Holm 后边缘显著；流行度防御放大攻击、方向性）建立在 40 任务小样本上。补到 100 任务/臂，让边缘结论过线或诚实确认为弱效应。
- **成本**：4090 约半天到一天，可后台。

### ③ GitHub 推送（用户未决定；改动未提交）
- repo_clone（= lab ~/synthflood_repo = GitHub MashiroRb/SynthFlood）：**22 个文件未提交**（19 modified：paper 全部章节+main.tex+refs.bib+图+make_figs.py；3 untracked：paper/figures/teaser.pdf、paper/make_teaser.py、scripts/cluster_probe.py）。
- 最后 3 个 commit 是 M1 实验自动推送（m1_finalize.sh）；论文 R1–R3 改稿 + 聚类脚本只在本地。
- 推送命令：`cd repo_clone && ./push_auto.sh`（**必须用户点头**）。
- 建议：先推一版固化改稿，实验出结果后再推第二版。

### 当前论文状态（新对话直接可用）
- 正文（含 Ethics）恰好收在第 8 页，References 从第 9 页顶开始；总 12 页 ≤12；0 未解析引用；verify_numbers.py 0 失配；初稿 ↔ repo_clone/paper TEX-IDENTICAL + FIGS-OK。
- 页面测量方法：pdftotext 字符位置在双栏下不可靠，用 `pdftoppm -f 8 -l 9 -r 60 -png` 渲染目检。

### 用户沟通规矩（务必延续）
1. 说人话/大白话；每个统计量给定义（McNemar=配对显著性检验、Holm=多重比较校正等）；
2. 判定语精确：命中预注册 / 反转预期 / 方向性未达显著，分开写，不夸大；
3. **主语必须用臂编号**（M0/B0/M2/M3/M4/PRE），禁止"带记忆的 agent""空记忆对照"这类别名（用户已两次因此批评）；
4. 用户会追问实验设计细节（环境 vs 考试、选题随机性、种子），回答要引预注册/代码原文佐证，不凭记忆；
5. 中文回复；结论先行，证据随后。
