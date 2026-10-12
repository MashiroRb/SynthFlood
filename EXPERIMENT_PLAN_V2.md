# SynthFlood 修复轮实验计划（v2，2026-10-11 制定）

> 规则：完成一项在 `[ ]` 里打 `x`，并在「结果与判定」列写实测数字与是否符合预期。
> 吞吐率基准：实测 ~4.4 ep/分钟（P4E：200 ep ≈ 45min）。

## A 组：GPU 新实验

- [x] **A1 Real-swap 安慰剂臂** — 100任务×ε0.75 端点，被替换位换**其他真品**
  - 目的：问题2——解耦"合成性"与"候选池换血"
  - 预期：swap 臂 success ≈0.59 量级、regret ≈0.26 量级（不随 ε 恶化）；若 swap 也跌到 ~0.4 → 合成性归因失败，主张降级
  - **结果与判定：✅ 符合预期（10-11）sham@0.75 n=100 success=0.590 regret=0.272 ≈ clean@0（0.590/0.262，Δregret=+0.010），synthetic@0.75=0.360/0.443 → 换血混杂证伪，合成性归因成立**
- [x] **A2 Clone解耦探针B：价格锚定** — 强制二选一 300 duels，clone price = gold price（字段级修改）
  - 目的：问题4——剥离价格诱导
  - 预期：σ_B ≈ σ_A=0.523（不可分辨性主导）；若 σ_B 显著<0.45 → 价格是主诱因，改写机制结论
  - **结果与判定：✅ 命中预注册分支B（σ_B<0.45 → 价格主诱因，机制改写）（10-11）：σ_clone 0.523→0.386（配对 McNemar +9/−21 p=0.043），降至 geo 基线水平（0.381）；geo/reviews 对照组复现（p=0.51/0.28）→ clone 的"不可分辨优势"主要由低价驱动；价格匹配后 agent 反而偏好 gold（σ<0.5）——"agent 不是被假规格骗了，是被折扣买走了"。数据校验：300 唯一键无混行**
- [ ] **A3 Clone解耦探针C：社会证明剥离** — 同A2，clone rating/num_reviews 清空
  - 目的：问题4——剥离评论诱导
  - 预期：σ_C 介于 σ_geo(0.351) 与 σ_clone(0.523) 之间；解释社会证明的边际贡献
  - 结果与判定：______
- [ ] **A4 PPR λ-扫描（新方法腿）** — 40任务×ε0.75×λ∈{0.5,1,2}，重排 score+λ·1[verified]
  - 目的：badge → 可调方法；产出恢复率 vs λ 曲线
  - 预期：λ 单调改善 regret，λ=2 接近 badge 版 0.329
  - 结果与判定：______
- [x] **A5 Provenance spoof 鲁棒臂** — 40任务×ε0.75，合成品 25%/50% 伪造 [verified]
  - 目的：问题5a——信道被攻破时的退化曲线
  - 预期：25% spoof 下恢复率 ≥70%；50% 下仍优于 none
  - **结果与判定：✅（10-11）spoof25=0.675/0.222（配对 Δregret=−0.107 CI[−0.191,−0.037]，+5/−0 p=0.031）、spoof50=0.575/0.332≈默认prov（0.55/0.329）。非单调→25%改善疑似噪声；稳健结论：15→50%伪造全程保持恢复（0.222-0.332 vs none 0.443）；误买合成品数不升（13→12）→badge非购买主驱动，恢复主要来自重排——A4 λ扫描检验**
- [x] **A6 Provenance+struct seed-2 复现** — 40任务×ε{0,0.75}×{provenance,struct}，cseed=2
  - 目的：问题6——跨生成池验证
  - 预期：方向与 seed1 一致（provenance ≈100% 恢复、struct 完全恢复）
  - **结果与判定：✅（10-11）prov_s2@0.75=0.575/0.292（s1: 0.55/0.329）、struct_s2@0.75=0.550/0.284（s1: 0.57/0.250）；跨生成池稳定，均远优于 none 0.443**
- [x] **A7 评论量信任朴素防御臂** — 40任务×ε{0,0.75}，按 rating·log(reviews) 重排
  - 目的：朴素基线；预期被 reviews 族思路反杀（regret 恶化或误买升高）
  - **结果与判定：✅ 符合预期（10-11）：@0 无害（0.575/0.256 ≈ none 0.590/0.262）；@0.75 放大攻击：success 0.300（<none 0.360）、regret 0.507（>0.443）、误买合成品 27/40=67.5%。朴素社会证明重排被 reviews 族定向利用**
- [ ] **A8 Stealth池+struct重跑** — 去模板指令重生成小池（GPU1 Llama ~1h）→ struct 40×{0,0.75}
  - 目的：问题5b——军备竞赛论证
  - 预期：stealth 池上 struct 恢复率大幅下降
  - 结果与判定：______
- [ ] **A9 ε=0.375 补点**（默认不做）
- [ ] **A10 provenance@Llama 泛化**（默认不做）

## B 组：CPU 分析（现有数据，零 GPU）

- [x] **B1 逐族配对 McNemar + CI**（p4b CSV）— ✅ 符合预期：mix Δregret +0.181 CI[0.099,0.268] p=2e-4，McNemar +5/-28 p=7e-5；clone +0.111 CI[-0.028,0.250] CI 跨零（诚实降级）；geo success 6↔6 p=1.0、regret +0.035 CI 跨零（静默损耗→方向性证据）
- [x] **B2 表1/2/3 全表补 95% CI**（p4a/p4b/p4c）— ✅ 符合预期：Qwen 0→0.25 success CI 无重叠（悬崖真实），0.5/0.75 与 0.25 重叠（非单调属噪声）；Llama 0.25 异常点 CI 重叠
- [x] **B3 防御臂两两配对检验**（p4c 同任务同seed）— ✅ 符合预期+加分（struct≈oracle 超出预期）：provenance vs struct Δ=+0.079 p=0.66（统计并列）；struct vs oracle Δ=+0.079 p=0.21（struct≈oracle！headline 升级）；provenance vs oracle p=0.039
- [x] **B4 检测器 AUC+gold误杀率**（struct 纯CPU；ppl 优先取日志）— ✅（10-11，lab CPU）AUC(synth vs real)=0.849；thresh 0.55：合成品捕获 811/1089=74.5%、真品干扰误杀 24/360=6.7%、**gold 误杀 3/40=7.5%（最高 0.719）**→ 量化 struct vs oracle 差距来源
- [ ] **B5 被删真品 reward 分布**（A1 前置保险：被删项应为低价值干扰）
- [x] **B6 误买 clone 价格偏好相关性**（P4A/B 轨迹）— ✅（10-11）轨迹重构 54/54 全匹配（n_synth=int(0.75·9)=6；replace 需按位置升序定 si）；clone 误买 35 条相对位置均值 **−0.148**（23 低于同任务 clone 均价 vs 12 高于）→ 误买时系统性挑更便宜的 clone，与 A2 因果证据闭合
- [x] **B7 struct@ε=0 行为分析**（对真品误伤率）— ✅ 反转预期（原预期有误伤成本，实测零成本，主张增强）：Δreward +0.078 CI[-0.030,0.195]，gold 购买 23/40 vs 22/40（p=0.55）→ 干净池零成本
- [x] **B8 侵蚀系数 κ = 配对 dE[regret]/dε**（p4a/p4d/p4f，按骨干分列+CI）— ✅ 符合预期：Qwen7B κ=0.242 CI[0.13,0.35]；Llama8B κ=0.208 CI[0.04,0.37]（跨骨干显著）；3B κ=0.141 CI 跨零；1.5B κ=-0.074（floor 效应，基线 regret 已 0.578）
- [x] **B9 误买合成品 reward 归因分解**（rinfo 字段）— ✅（10-11）54 次误买仅 2 次（3.7%）满分；clone 94% 部分匹配（均值 0.37）、geo 100% 部分但均值 0.14、reviews 20% 得 0；对照 gold 0.980 → "说服成功、履约失败"定量形态

## C 组：代码/资产准备

- [x] C0 本计划文件建立
- [x] C1 build_task() 加 sham 模式 + spoof_rate 参数（前缀性质保证 sham 臂与原臂基础候选完全一致）
- [x] C2 变体池构造 make_probe_variants.py（B: clone price=gold；C: clone rating/评论清空）
- [x] C3 PPR λ 重排实现（defenses.py defense=ppr，u=rating+λ·1[prov_ok]，稳定排序）
- [x] C4 spoof 参数化（run_sweep --spoof；defenses 加 reviewtrust 朴素信任重排）
- [ ] C5 stealth 生成 prompt（仅 A8，单卡 4090 需换模型，暂挂起）
- [x] C6 全文数字 vs CSV 校验脚本（verify_numbers.py：账本 numbers_ledger.json + tex 扫描；未入文数字=改写清单）
- [x] C7 sync 守护进程 sync_daemon.sh（10 分钟一轮 copy+commit+push，rebase 优先）
- [x] C8 实验队列脚本 run_fix.sh（A1→A2→A3→A5→A7→A4→A6，CSV 归档+顺序执行，预计 ~4.3h）

## 执行顺序
C1-C4+C7+C8 → 上传/push → vLLM 重启 → A1(端点)→A2→A3→A5→A7→A4→A6 → (余量→A8) ；B1-B9 与 GPU 并行。

## 环境状态
- 2026-10-11 lab 重置为全新单卡 4090；setup_lab.sh 后台重建中（代码 clone + WebShop 数据 gdown ~8GB + Qwen2.5-7B 权重 ~15GB + vllm 0.19.0）
- 自动化：sync_daemon.sh 常驻 10 分钟一轮（results_csv/ logs/ EXPERIMENT_* → GitHub）