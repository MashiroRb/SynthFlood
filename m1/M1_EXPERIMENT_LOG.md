# M1 实验日志：内化 vs 情境性诱导

本日志同步于三处：lab 机 `~/synthflood_repo/m1/`、GitHub 仓库 `m1/`、本地项目。
每次追加后由 m1_finalize.sh 提交推送。

## 2026-10-14 — 环境重建（lab 机再次重置）

- 开工检查发现 lab 机被再次重置：家目录全空（vLLM、仓库、数据、PAT 全部丢失），
  GPU 硬件完好（nvidia-smi 正常，1 MiB 占用 = 无进程）。
- 执行 provision_m1.sh 全量重配：apt（python3.10-dev/build-essential）、
  pip（vllm==0.31.0、huggingface_hub<2.0、hf_transfer、spacy+en_core_web_sm、
  prettytable）、princeton-nlp/WebShop 克隆、官方数据三件套
  （items_shuffle.json 5.48GB / items_ins_v2.json 186MB / items_human_ins.json
  5.1MB，HF 镜像 YWZBrandon/webshop-data，Xet 高速通道秒级完成）、
  SynthFlood 仓库克隆（HEAD=15be3cf，与远程一致）、harness 软链布局
  （~/synthflood → ~/synthflood_repo/synthflood，数据符号链接就位）。
- 补丁：huggingface-cli 在 hub 2.x 下不存在 → 改用 snapshot_download 下载
  Qwen2.5-7B-Instruct；补装 thefuzz/rapidfuzz（select_env 依赖）。
- 本次实验代码（m1/）与 agent_react.py 的 sys_extra 兼容性补丁（默认参数，
  不影响既有调用）在上传后提交推送。

## 预注册

判定标准与全部设计细节见 PRE_REG_M1.md（跑数前写定，含 Holm 校正族、
半衰期定义、泄漏防护、种子表）。

## 实验执行

（待补：prep、smoke、full 的逐段记录）

## 结果与判定（对照预注册第 7 节）

σ 表（clone 选择率；n=39/38，8 对克隆生成失败已记录）：

```
      @0    @2    @4    @6    @8   @10   @12   @14   @16   @18   @20
PRE  .692    -     -     -     -     -     -     -     -     -     -
B0    -    .718  .692  .718  .718  .718  .692  .667  .795  .795  .718
M0   .897  .872  .615  .769  .718  .692  .692  .692  .744  .769  .667
M2   .692  .718  .718  .718  .718  .667  .667  .744  .692  .667  .718
M3   .769  .769  .641  .744  .718  .744  .718  .667  .667  .821  .692
M4   .744  .744  .667  .718  .692  .718  .667  .744  .769  .744  .667
parity: M0 .789/.763/.842 (@0/10/20) | M2 .526/.526/.605 | M3 .658/.632/.684
        | B0  -  /.632/.579
```

1. 【主检验 1：H1 内化（折扣通道）→ 未命中】M0@20=.667 < B0@20=.718
   （z=−0.49, p=0.62）。20 集干净经验后，折扣驱动的克隆偏好完全回落。
2. 【主检验 2：H0 纯情境 → 未命中】M0@2=.872 > B0+0.05=.768——不是瞬时
   恢复，存在真实的、记忆介导的短暂 carryover。
3. 【主检验 3：部分衰减 → 命中】c0 carryover 显著（McNemar b=9/c=1,
   p=0.021；z vs B0=2.01, p=0.044），半衰期=4 集干净经验，@10 起≤B0
   （z=−0.25, p=0.80）。B0 自身 @16/@18=.795 属 n=39 噪声水平。
4. 【主检验 4：记忆因果 → 命中】M2（写而不读）@0=.692 ≈ B0（p=0.80），
   显著低于 M0@0（z=−2.24, p=0.025）→ 自写经验记忆是 carryover 的载体。
5. 【次级 M4 记忆手术 → 方向一致，未达显著】删除价格条目 σ@0 .897→.744
   （z=−1.77, p=0.077）；删除清单见 snapshot_M4_deleted.json。
6. 【次级 M3 纠错 → 方向一致，未达显著】纠错反馈 σ@0 .897→.769（p=0.13）。
7. 【次级平价通道 → 反转预期，本实验最重要发现】折扣通道衰减了，但属性
   权重漂移（f=1.00 平价考试）不衰减：M0 parity@20=.842 vs B0@20=.579
   （z=2.53, p=0.011），且高于其自身 @0（.789）。记忆介导：M2@0=.526 vs
   M0@0=.789（z=2.42, p=0.016）。
8. 【迁移·同品类 → 无显著差异】M0 .718 vs B0 .744（p=0.80）。【迁移·跨品类
   → 无法执行】配对池剩余 137 对的品类全部落在暴露集 5 品类内（beauty/
   electronics/fashion/garden/grocery），如实记录为可行性限制。
9. 【迁移·跨域好评 → 显著但证据混合，标注 exploratory】M0 20/20 vs B0
   14/20（z=2.66, p=0.008）；但 M2=.85、M4=1.00 也高于 B0 → 不完全由记忆
   注入介导，n=20 谨慎解读。
10. 【奖励验尸 → 反转此前"弱惩罚"解释】38 次暴露集合成品购买中
    reward(克隆) ≥ reward(金品) 仅 2 次（5.3%），平均差 −0.632 → 官方教师
    几乎总是负反馈，carryover 在负反馈下仍发生 → 不是"环境奖励坏行为"，
    而是暴露诱导的偏好被写进自写记忆文本（价格/属性内容）并被复读。
11. 【解释边界】exam@0（+18pp）与 samecat@0（0pp）为不同题目集，集合构成
    存在差异，不作"carryover 任务特异"结论。

一句话结论：污染诱导的"买便宜克隆"行为快衰减（半衰期 4 集干净经验），
但更隐蔽的属性权重漂移（平价通道）在 20 集后仍持久且被自写记忆介导——
M1 把主实验的单一 σ 效应拆成了快通道与慢通道两个成分。

## 实验执行 (2026-10-14 19:26 UTC)

- prep/smoke/full 均由 m1_pipeline.sh + m1_finalize.sh 驱动。
- full 运行控制台日志：/tmp/m1_full.log（运行期），关键数字入 results_m1/。

### 分析输出（m1_run.py --mode analyze）

```
  arm            phase  ckpt   sigma n
   B0             exam     2   0.718 39
   B0             exam     4   0.692 39
   B0             exam     6   0.718 39
   B0             exam     8   0.718 39
   B0             exam    10   0.718 39
   B0             exam    12   0.692 39
   B0             exam    14   0.667 39
   B0             exam    16   0.795 39
   B0             exam    18   0.795 39
   B0             exam    20   0.718 39
   B0           parity    10   0.632 38
   B0           parity    20   0.579 38
   M0             exam     0   0.897 39
   M0             exam     2   0.872 39
   M0             exam     4   0.615 39
   M0             exam     6   0.769 39
   M0             exam     8   0.718 39
   M0             exam    10   0.692 39
   M0             exam    12   0.692 39
   M0             exam    14   0.692 39
   M0             exam    16   0.744 39
   M0             exam    18   0.769 39
   M0             exam    20   0.667 39
   M0           parity     0   0.789 38
   M0           parity    10   0.763 38
   M0           parity    20   0.842 38
   M2             exam     0   0.692 39
   M2             exam     2   0.718 39
   M2             exam     4   0.718 39
   M2             exam     6   0.718 39
   M2             exam     8   0.718 39
   M2             exam    10   0.667 39
   M2             exam    12   0.667 39
   M2             exam    14   0.744 39
   M2             exam    16   0.692 39
   M2             exam    18   0.667 39
   M2             exam    20   0.718 39
   M2           parity     0   0.526 38
   M2           parity    10   0.526 38
   M2           parity    20   0.605 38
   M3             exam     0   0.769 39
   M3             exam     2   0.769 39
   M3             exam     4   0.641 39
   M3             exam     6   0.744 39
   M3             exam     8   0.718 39
   M3             exam    10   0.744 39
   M3             exam    12   0.718 39
   M3             exam    14   0.667 39
   M3             exam    16   0.667 39
   M3             exam    18   0.821 39
   M3             exam    20   0.692 39
   M3           parity     0   0.658 38
   M3           parity    10   0.632 38
   M3           parity    20   0.684 38
   M4             exam     0   0.744 39
   M4             exam     2   0.744 39
   M4             exam     4   0.667 39
   M4             exam     6   0.718 39
   M4             exam     8   0.692 39
   M4             exam    10   0.718 39
   M4             exam    12   0.667 39
   M4             exam    14   0.744 39
   M4             exam    16   0.769 39
   M4             exam    18   0.744 39
   M4             exam    20   0.667 39
  PRE             exam    -1   0.692 39
Traceback (most recent call last):
  File "/root/synthflood_repo/m1/m1_run.py", line 875, in <module>
    analyze()
  File "/root/synthflood_repo/m1/m1_run.py", line 795, in analyze
    z, p = (two_prop_z(round(m0_20 * n20), n20,
  File "/root/synthflood_repo/m1/m1_run.py", line 740, in two_prop_z
    from scipy.stats import norm
ModuleNotFoundError: No module named 'scipy'
```

### 数据完整性

```
  161 results_m1/m1_episodes.csv
 2759 results_m1/m1_exams.csv
  101 results_m1/m1_rank.csv
  101 results_m1/m1_xdom.csv
 3122 total
60 results_m1/m1_reward_autopsy.jsonl
```

## 实验执行 (2026-10-14 19:27 UTC)

- prep/smoke/full 均由 m1_pipeline.sh + m1_finalize.sh 驱动。
- full 运行控制台日志：/tmp/m1_full.log（运行期），关键数字入 results_m1/。

### 分析输出（m1_run.py --mode analyze）

```
  arm            phase  ckpt   sigma n
   B0             exam     2   0.718 39
   B0             exam     4   0.692 39
   B0             exam     6   0.718 39
   B0             exam     8   0.718 39
   B0             exam    10   0.718 39
   B0             exam    12   0.692 39
   B0             exam    14   0.667 39
   B0             exam    16   0.795 39
   B0             exam    18   0.795 39
   B0             exam    20   0.718 39
   B0           parity    10   0.632 38
   B0           parity    20   0.579 38
   M0             exam     0   0.897 39
   M0             exam     2   0.872 39
   M0             exam     4   0.615 39
   M0             exam     6   0.769 39
   M0             exam     8   0.718 39
   M0             exam    10   0.692 39
   M0             exam    12   0.692 39
   M0             exam    14   0.692 39
   M0             exam    16   0.744 39
   M0             exam    18   0.769 39
   M0             exam    20   0.667 39
   M0           parity     0   0.789 38
   M0           parity    10   0.763 38
   M0           parity    20   0.842 38
   M2             exam     0   0.692 39
   M2             exam     2   0.718 39
   M2             exam     4   0.718 39
   M2             exam     6   0.718 39
   M2             exam     8   0.718 39
   M2             exam    10   0.667 39
   M2             exam    12   0.667 39
   M2             exam    14   0.744 39
   M2             exam    16   0.692 39
   M2             exam    18   0.667 39
   M2             exam    20   0.718 39
   M2           parity     0   0.526 38
   M2           parity    10   0.526 38
   M2           parity    20   0.605 38
   M3             exam     0   0.769 39
   M3             exam     2   0.769 39
   M3             exam     4   0.641 39
   M3             exam     6   0.744 39
   M3             exam     8   0.718 39
   M3             exam    10   0.744 39
   M3             exam    12   0.718 39
   M3             exam    14   0.667 39
   M3             exam    16   0.667 39
   M3             exam    18   0.821 39
   M3             exam    20   0.692 39
   M3           parity     0   0.658 38
   M3           parity    10   0.632 38
   M3           parity    20   0.684 38
   M4             exam     0   0.744 39
   M4             exam     2   0.744 39
   M4             exam     4   0.667 39
   M4             exam     6   0.718 39
   M4             exam     8   0.692 39
   M4             exam    10   0.718 39
   M4             exam    12   0.667 39
   M4             exam    14   0.744 39
   M4             exam    16   0.769 39
   M4             exam    18   0.744 39
   M4             exam    20   0.667 39
  PRE             exam    -1   0.692 39
{
 "M0_clean20_vs_B0": {
  "z": -0.49,
  "p": 0.6237
 },
 "M0_c0_vs_PRE_mcnemar": {
  "b": 9,
  "c": 1,
  "p": 0.02148
 },
 "half_life_checkpoint": 4,
 "M0_sigma0": 0.8974,
 "B0_sigma20": 0.7179,
```

### 数据完整性

```
  161 results_m1/m1_episodes.csv
 2759 results_m1/m1_exams.csv
  101 results_m1/m1_rank.csv
  101 results_m1/m1_xdom.csv
 3122 total
60 results_m1/m1_reward_autopsy.jsonl
```
