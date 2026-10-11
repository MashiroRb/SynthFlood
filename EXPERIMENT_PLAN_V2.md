# SynthFlood 修复轮实验计划（v2，2026-10-11 制定）

> 规则：完成一项在 `[ ]` 里打 `x`，并在「结果与判定」列写实测数字与是否符合预期。
> 吞吐率基准：实测 ~4.4 ep/分钟（P4E：200 ep ≈ 45min）。

## A 组：GPU 新实验

- [ ] **A1 Real-swap 安慰剂臂** — 100任务×ε{0.25,0.5,0.75}（可先端点0.75），被替换位换**其他真品**
  - 目的：问题2——解耦"合成性"与"候选池换血"
  - 预期：swap 臂 success ≈0.59 量级、regret ≈0.26 量级（不随 ε 恶化）；若 swap 也跌到 ~0.4 → 合成性归因失败，主张降级
  - 结果与判定：______
- [ ] **A2 Clone解耦探针B：价格锚定** — 强制二选一 300 duels，clone price = gold price（字段级修改）
  - 目的：问题4——剥离价格诱导
  - 预期：σ_B ≈ σ_A=0.523（不可分辨性主导）；若 σ_B 显著<0.45 → 价格是主诱因，改写机制结论
  - 结果与判定：______
- [ ] **A3 Clone解耦探针C：社会证明剥离** — 同A2，clone rating/num_reviews 清空
  - 目的：问题4——剥离评论诱导
  - 预期：σ_C 介于 σ_geo(0.351) 与 σ_clone(0.523) 之间；解释社会证明的边际贡献
  - 结果与判定：______
- [ ] **A4 PPR λ-扫描（新方法腿）** — 40任务×ε0.75×λ∈{0.5,1,2}，重排 score+λ·1[verified]
  - 目的：badge → 可调方法；产出恢复率 vs λ 曲线
  - 预期：λ 单调改善 regret，λ=2 接近 badge 版 0.329
  - 结果与判定：______
- [ ] **A5 Provenance spoof 鲁棒臂** — 40任务×ε0.75，合成品 25% 伪造 [verified]（可加 50% 档）
  - 目的：问题5a——信道被攻破时的退化曲线
  - 预期：25% spoof 下恢复率 ≥70%；50% 下仍优于 none
  - 结果与判定：______
- [ ] **A6 Provenance+struct seed-2 复现** — 40任务×ε{0,0.75}×{provenance,struct}，cseed=2
  - 目的：问题6——跨生成池验证
  - 预期：方向与 seed1 一致（provenance ≈100% 恢复、struct 完全恢复）
  - 结果与判定：______
- [ ] **A7 评论量信任朴素防御臂** — 40任务×ε{0,0.75}，按 rating·log(reviews) 重排
  - 目的：朴素基线；预期被 reviews 族思路反杀（regret 恶化或误买升高）
  - 结果与判定：______
- [ ] **A8 Stealth池+struct重跑** — 去模板指令重生成小池（GPU1 Llama ~1h）→ struct 40×{0,0.75}
  - 目的：问题5b——军备竞赛论证
  - 预期：stealth 池上 struct 恢复率大幅下降
  - 结果与判定：______
- [ ] **A9 ε=0.375 补点**（默认不做）
- [ ] **A10 provenance@Llama 泛化**（默认不做）

## B 组：CPU 分析（现有数据，零 GPU）

- [x] **B1 逐族配对 McNemar + CI**（p4b CSV）— ✅ 符合预期：mix Δregret +0.181 CI[0.099,0.268] p=2e-4，McNemar +5/-28 p=7e-5；clone +0.111 CI[-0.028,0.250] CI 跨零（诚实降级）；geo success 6↔6 p=1.0、regret +0.035 CI 跨零（静默损耗→方向性证据）
- [x] **B2 表1/2/3 全表补 95% CI**（p4a/p4b/p4c）— ✅ 符合预期：Qwen 0→0.25 success CI 无重叠（悬崖真实），0.5/0.75 与 0.25 重叠（非单调属噪声）；Llama 0.25 异常点 CI 重叠
- [x] **B3 防御臂两两配对检验**（p4c 同任务同seed）— ✅ 超预期：provenance vs struct Δ=+0.079 p=0.66（统计并列）；struct vs oracle Δ=+0.079 p=0.21（struct≈oracle！headline 升级）；provenance vs oracle p=0.039
- [ ] **B4 检测器 AUC+gold误杀率**（struct 纯CPU；ppl 优先取日志）
- [ ] **B5 被删真品 reward 分布**（A1 前置保险：被删项应为低价值干扰）
- [ ] **B6 误买 clone 价格偏好相关性**（P4A/B 轨迹）
- [ ] **B7 struct@ε=0 行为分析**（对真品误伤率）
- [x] **B8 侵蚀系数 κ = 配对 dE[regret]/dε**（p4a/p4d/p4f，按骨干分列+CI）— ✅ 符合预期：Qwen7B κ=0.242 CI[0.13,0.35]；Llama8B κ=0.208 CI[0.04,0.37]（跨骨干显著）；3B κ=0.141 CI 跨零；1.5B κ=-0.074（floor 效应，基线 regret 已 0.578）
- [ ] **B9 误买合成品 reward 归因分解**（rinfo 字段）

## C 组：代码/资产准备

- [x] C0 本计划文件建立
- [x] C1 build_task() 加 sham 模式 + spoof_rate 参数（前缀性质保证 sham 臂与原臂基础候选完全一致）
- [x] C2 变体池构造 make_probe_variants.py（B: clone price=gold；C: clone rating/评论清空）
- [x] C3 PPR λ 重排实现（defenses.py defense=ppr，u=rating+λ·1[prov_ok]，稳定排序）
- [x] C4 spoof 参数化（run_sweep --spoof；defenses 加 reviewtrust 朴素信任重排）
- [ ] C5 stealth 生成 prompt（仅 A8，单卡 4090 需换模型，暂挂起）
- [ ] C6 全文数字 vs CSV 校验脚本
- [x] C7 sync 守护进程 sync_daemon.sh（10 分钟一轮 copy+commit+push，rebase 优先）
- [x] C8 实验队列脚本 run_fix.sh（A1→A2→A3→A5→A7→A4→A6，CSV 归档+顺序执行，预计 ~4.3h）

## 执行顺序
C1-C4+C7+C8 → 上传/push → vLLM 重启 → A1(端点)→A2→A3→A5→A7→A4→A6 → (余量→A8) ；B1-B9 与 GPU 并行。

## 环境状态
- 2026-10-11 lab 重置为全新单卡 4090；setup_lab.sh 后台重建中（代码 clone + WebShop 数据 gdown ~8GB + Qwen2.5-7B 权重 ~15GB + vllm 0.19.0）
- 自动化：sync_daemon.sh 常驻 10 分钟一轮（results_csv/ logs/ EXPERIMENT_* → GitHub）
