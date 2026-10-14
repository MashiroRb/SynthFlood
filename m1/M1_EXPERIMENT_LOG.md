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

## 结果与判定

（待补：m1_summary.json 摘录 + 对照第 7 节判定分支的结论，措辞遵循
【符合预期】【反转预期】【无显著差异】精确判定语）

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
