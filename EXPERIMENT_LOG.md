# SynthFlood — 实验运行日志（EXPERIMENT LOG）

> 项目：SynthFlood — Ambient Synthetic Content Silently Erodes Web-Agent Decision Quality
> 目标：WWW 2027 "Brave New Ideas for the Future of the Web" track
> 关键日期：摘要 2026-10-18 AoE ｜ 全文 2026-10-25 AoE
> 硬件：2× RTX 4090 (24GB)，Lab Compute
> 本文档记录：运行过程、日志路径、实验结果、问题与改进。每次实验后更新并推送 GitHub。

---

## 0. 时间线总览（门控协议）

| 阶段 | 内容 | 门槛 | 状态 |
|---|---|---|---|
| P0 | 管线连通（20 任务 clean×2 遍） | 动作解析零失败、success 落社区区间、同种子可复现 | ⏳ |
| GEN | 污染生成器（3 族×40 任务×4 档）+ judge 质检 | 合理率≥4/5 占比≥80%，人工抽检 10 条 | ⏳ |
| P1 | 强制二选一探针（30×10=300 选择） | Susceptibility ≥ 0.60，二项 p<0.01 | ⏳ |
| P2 | 剂量-反应（50 任务×ε{0,.25,.75}） | ε=.75 相对 ε=0：success 降≥5pp 或 regret 升≥10% | ⏳ |
| P3 | 统计功效分析（0 GPU） | 定稿主实验矩阵 | ⏳ |
| P4 | 压缩版主实验 | 主曲线 + 骨干×2 + 种子×2 + 消融 | ⏳ |
| P5 | 防御小试（7 防御×1 个 ε 档） | 至少一个防御恢复 ≥30% 退化 | ⏳ |

砍档顺序（若超时）：seeds → 次骨干 → ε 档 → 消融 → 跨域；主指标曲线不动。

---

## 1. 环境搭建（2026-10-10）

- Lab 机器：2×4090 / 512GB 盘 / 503GB RAM / 64 核 / Python 3.10.12 / root
- 依赖安装：vllm 0.31.0、transformers 5.17.0、datasets 5.1.0、Flask 3.1.3、
  sentence-transformers 6.1.0、gdown、spacy(+en_core_web_sm)、thefuzz、rich（logs/pip.log、logs/pip2.log）
- WebShop 官方仓库克隆至 `~/synthflood/webshop_repo`
- 数据（官方三件套）：Google Drive 配额拒绝 → 改用 HF 镜像 `YWZBrandon/webshop-data`
  （items_shuffle.json 5.5GB / items_ins_v2.json 186MB / items_human_ins.json 5.1MB）→ `logs/data_dl.log`
- 模型权重（HF snapshot_download）：Qwen2.5-7B/3B/1.5B-Instruct + Meta-Llama-3.1-8B-Instruct(NousResearch 镜像)
- vLLM：`scripts/serve_models.sh`（GPU0=Qwen7B :8000，GPU1=Llama8B :8001）
  - **问题1**：vLLM 0.31 不认 `--disable-log-requests` → 已删该参数（改进：改用 `--no-enable-log-requests` 亦不必）
- GitHub：`MashiroRb/SynthFlood`（PAT 配置于 Lab `~/.git-credentials`，仅本机使用；投稿后建议撤销换新）

## 2. 数据与环境冒烟（2026-10-10）

- 官方 loader 逐行移植为 `synthflood/ws_loader.py`（engine.py 的 load_products/clean_product_keys/
  generate_product_prices，仅参数化路径），首载 127s，pickle 缓存 `data/all_products.pkl`
- 数据规模：**1,181,430 商品**（去重后），1,181,430 价格，670 个属性键；人类指令 10,136 个 asin
- 官方 goals 构造（get_human_goals）：164 个零属性指令被跳过（官方语义），50 任务采样成功
- **问题2（发现并修复）**：人类 goal 的 `goal_options` 是 `"name: value"` **字符串列表**而非字典；
  `best_variant_options` 已适配两种格式（镜像官方 get_reward 的分支处理）
- **问题3（发现并修复）**：tar 覆盖解压产生 `synthflood/synthflood/` 嵌套导致 Lab 端代码陈旧
  → 改为显式 cp 单文件同步（改进：后续同步用 rsync 式覆盖）
- **设计决策**：选择协议无“选变体”步骤，故对被选商品按“最优变体匹配”计入 option 项，
  使 reward 差异只来自“选了哪个 listing”（处理变量）；合成商品继承 gold 的 options 字典（仅进 reward）
- 冒烟结果（smoke2）：数据缓存 34s 加载 ✓；GOLD reward=1.0（r_type/r_att/r_option/r_price 全中，
  列表格式 goal_options 的变体匹配正确）；随机干扰项 reward=0.0
- **问题4（发现并修复）**：同 `category` 干扰项在官方 r_type 判定下全为 0（官方按 `product_category`
  细分"›"匹配），会使 success 与 regret 完全反相关，“静默侵蚀”无法测 → **干扰项改为优先同
  `product_category` 采样，粗类回补**（改进 #4）
- 冒烟结果（smoke3）：10 任务中候选 reward 呈梯度 0–1.0（如 [1.0, 0.67, 0.67, 0.33]），
  gold=1.0 恒成立；个别任务存在多个 1.0 替代品（官方语义，配对设计可处理）
- **问题5（发现并修复）**：预装 torch 2.13.0+cu130，驱动仅 12.8 → vLLM 引擎初始化失败。
  装 torch 2.11.0+cu128（`--index-url download.pytorch.org/whl/cu128`）后 vLLM 0.31 仍报
  `libcudart.so.13`（0.31 wheel 本身按 cu13 编译）→ 查 PyPI 元数据发现 vLLM 0.20+ 均绑
  torch 2.11（cu130 编译），**降级到 cu12 编译的 vLLM 版本**（0.19/0.20/0.21 逐个测试，
  取能 import 的最高版）（改进 #5）

## 3. 待续

（P0 / GEN / P1 / P2 / P4 / P5 各节，随实验推进填写；含每次的门槛判定与数据）
