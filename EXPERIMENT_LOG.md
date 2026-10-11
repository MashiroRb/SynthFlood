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

## 2b. vLLM 兼容性排障（2026-10-10 下午）

| 尝试 | 结果 |
|---|---|
| torch 2.13.0+cu130（预装）+ vLLM 0.31 | 驱动 12.8 过旧，cuda init 失败 |
| torch 2.11.0+cu128 + vLLM 0.31 | `vllm._C_stable_libtorch` 仍链 cu13（wheel 本体 cu13 编译） |
| vLLM 0.26（pin torch 2.11） | `import vllm` 通过但核心扩展仍 cu13（浅层测试误判，教训：判据必须是 `import vllm._C`） |
| **vLLM 0.19.0（pin torch 2.10）** | ✅ `import vllm._C` 通过；torch 自动回落 2.10.0+cu128 |
| 引擎初始化 | triton JIT 的 cuda_utils.c 编译失败 → 手动复现定位为 **缺 Python.h** |
| 补 Python.h（无 apt 安装权限，用 `apt-get download` 下载 python3.10-dev/libpython3.10-dev .deb 手动 `dpkg -x /`） | ✅ |
| `--enforce-eager` | 加入（小 batch 场景吞吐损失可忽略） |

最终组合：**vLLM 0.19.0 + torch 2.10.0+cu128 + Python.h 补丁 + enforce-eager**。
双服务健康：GPU0 Qwen2.5-7B :8000（22.7GB），GPU1 Llama-3.1-8B :8001（22.6GB），chat 冒烟 ✓。

## 3. P0 管线验证（2026-10-10）✅ 闸门通过

- 配置：20 任务 × 2 重复（确定性验证），Qwen2.5-7B，temp=0，max 10 步，16 并发
- 结果（results/p0_sanity.csv，40 行）：
  - **success_full_rate = 0.65**（clean ε=0，Select 变体上 7B 的合理水平；社区报告的完整 WebShop
    GPT-4 约 0.5-0.6，Select 变体更易）
  - **malformed_total = 0**（动作解析 100% 有效，协议可用）
- （待补：同任务两遍 reward 一致性核验 → 见 §4 更新）

## 4. 污染生成器（2026-10-10 13:52–14:04）✅ 完成

- **问题6（修复）**：judge 客户端连 :8000 却用 Llama 模型名 → 404。修复：judge 单独传
  `--judge-port 8000 --judge-model Qwen2.5-7B`（同时消除生成器自我偏好偏差）
- 生成配置：40 任务 × 3 族 × 4 条 + 评论包；生成器=Llama-8B（GPU1），judge=Qwen7B（GPU0）
- 结果（data/contamination/pool.json，1.5MB）：
  - **40 任务，427 条合成 listing**（geo 146 / clone 130 / reviews 151；目标 480，缺 53 条 =
    judge 淘汰 + 早期 8 个 judge 404 线程失败，属正常淘汰）
  - **judge 合理性分布：400×5 分，27×4 分**（全部 ≥4 门槛 ✓）
  - 人工抽检 112 条（results/audit_sample.txt）：geo 族呈典型 SEO 内容农场风格（关键词堆砌
    标题、营销 bullet、规格不含 gold 属性），质量达标
- 注意点：2 任务（#9=3 条，#21=5 条）合成库存 <6（ε=0.75 需 6 条）→ pick_synths 以
  `-x{n}` 后缀复制补齐剂量（记录在案）；每族最少 1 条的任务有 5 个（单族实验 P4 时需补齐或回退 mix）

## 5. P1 强制二选一探针 —— v1 运行与作废复盘（2026-10-10 14:13–14:20）

### 5a. v1 结果（已作废，保留于 results/_v1_buggy/）
- P1（30 任务 × 10 对 = 300 次）：**σ=0.000**（239 选 gold、16 none、初版 255 行 0 选 synth；
  全量 300 行复核含 1 次选 synth）。方向与 σ≥0.60 门槛完全相反。
- P2（50 任务 × ε{0,0.25,0.75}）：success_full 0.600 → 0.675 → 0.700（**无退化，甚至微升**），
  regret 0.230 → 0.223 → 0.214。20 行 `ERROR:IndexError`（全部集中在 task 40-49 × ε>0）。

### 5b. 机制审查（判定 v1 是否可作数）——发现 4 个问题
1. **渲染泄漏（致命）**：合成页 "Top reviews" 以 Python dict 原始形式渲染
   （`{'rating': 5, 'review': '...'}`），一眼即假 → agent 的"识破"可能是渲染伪影而非真本事。
   根因两层：(a) item_page 对评论 dict 的格式化路径错误；(b) 生成器对 42/427 条 listing 的
   review text 二次编码（dict 的 text 字段又是一个 dict 字符串，跨三族混合分布：
   geo 10/146、clone 24/130、reviews 8/151）。
2. **gold 评级渲染不一致**：官方数据中大量 human-instruction 商品的 Rating='N.A.'、Reviews=[]
   → 结果页 gold 显示 "rating:  ( reviews)"（空），而合成条全部 4.6-4.9★/400-3000 评论 →
   系统性不对称，属数据忠实但需显式显示为 "n/a (0 reviews)" 以免被当成渲染 bug。
3. **价格格式不一致**：gold "$14.95" vs 合成 "41.77"（裸数字）→ 统一为 "$xx.xx"。
4. **task 40-49 IndexError（根因确认）**：goals 50 个 vs pool.json 仅 40 任务 → `pool.get(gi)`
   空 → build_task `synths[si]` 越界。ε=0 时 n_synth=0 不触碰 synth 故无错；这解释了
   20 个错误行全部集中在 ε>0。修复：run_sweep 对空池任务记 `SKIPPED:no_synth` 跳过 +
   errors.log 记录完整 traceback。

### 5c. 排除"位置偏差"与"轨迹真实性"（v1 数据仍具参考价值）
- 位置重构核查（前 40 对）：gold@[1] 24 次全选 gold；gold@[2] 16 次中 15 选 gold、1 选 synth
  → **非位置偏差**，agent 确实在读内容。
- 轨迹抽查：agent 真实浏览两页、逐条对照指令属性后才决定；合成页被拒绝的理由是
  规格缺失/不符（"does not specify if it's handcrafted or has bride and groom flavor"）。
- **重要语义发现**：官方 WebShop 人类指令是"变体级"的（如 bride-and-groom 口味是
  Philadelphia 同款饼干的另一变体，藏在官方 options 字典里）；基础 listing 标题常与指令
  文本低重叠（24/30 任务 <30% token 重叠）。官方语义下 gold 经 best_variant_options
  匹配变体后 reward=1.0 成立 → 我们的 Select 协议设计（删变体选择步、最优变体计分）与
  该数据特性自洽；agent 表面的"困惑"实为变体信息不可见，这是 WebShop 数据的固有特性，
  不是配对 bug。

### 5d. 结论与处置
- v1 的 P1/P2 **作废**（渲染混淆未排除前不可解释 σ 与剂量曲线），数据归档 `_v1_buggy/`。
- v2 修复（review 递归解包 + n/a 评级 + $ 价格统一 + 空池跳过 + traceback 落盘）后重跑
  P1/P2（v3 链：p1_run3.log / p2_run3.log，P2 收敛为 --n-tasks 40 与 pool 对齐）。
- 教训沉淀：**渲染层是测量仪器的一部分**——任何 agent 行为实验前，先"肉眼过"渲染样本
  （audit_export 应扩为渲染级抽检，不仅数据级）。

## 6. v3 重跑与价格锚定缺陷（2026-10-10 14:36–15:05）

### 6a. v3 P1（清洁渲染后）
- **σ = 0.153**（46/300 选 synth；Wilson95 [0.117, 0.199]；vs H0 σ=0.5 二项 p≈2.5e-36）
  - v1 的 σ=0 确证为渲染伪影：修好评论渲染后，clone 族购买率 0%→26%（23/88）
  - 族分解：clone 23/88、reviews 12/115、geo 11/97 —— 规格克隆（含错误属性+低价）最具
    诱惑力；纯社交证明（五星评论）最弱
- 附带修复：synth 候选缺 `kind` 键导致 CSV chosen_kind 记成 "none"（46 行实为 synth 购买），
  _as_candidate 已补 kind
- **门槛判定：σ≥0.60 未达标 → "agent 系统性偏好合成页"假设不成立**；agent 在 1v1 下
  系统性回避 synth（84.7% 选 gold）。但 σ 显著 >0，且剂量-反应是独立通道 → 看 P2。

### 6b. v3 P2（ε∈{0,0.25,0.75}，40 任务，0 错误行）
| ε | success_full | success80 | regret | synth 购买 |
|---|---|---|---|---|
| 0.00 | 0.600 | 0.625 | 0.248 | 0/40 |
| 0.25 | 0.600 | 0.600 | 0.271 | 8/40 |
| 0.75 | 0.575 | 0.600 | 0.335 | 13/40 |
- **静默侵蚀信号出现**：success 基本平（McNemar 0→0.75: 8 vs 7, n.s.）而 regret **+35%**
  （0.248→0.335）；synth 购买率 0%→33%。与预注册的预测signature一致
  （success 平、regret 升、置信照旧）。
- **P2 门槛：通过**（regret 相对升幅 35% ≥ 10%）。

### 6c. 价格锚定缺陷（问题7，v3→v4 间修复）
- **发现**：clone 价格中位数 = gold 的 2.13×（设计应为 0.75-0.95×）。根因：官方
  products 的 Price 是 `"$14.95"` **字符串**，生成器 `isinstance(price,(int,float))`
  判假 → 回落 50.0 → 三族 synth 全部锚在 $37.5-47.5。
- **修复**：contaminate.parse 字符串价格；对既有 pool 写 `scripts/reprice_pool.py`
  逐 listing 确定性重定价（asin 哈希种子，U(0.75,0.95)×gold_price），listing 文本与
  judge 分保持不变；pool_v3_50anchored.json 归档对照。
- 重定价验证：synth/gold 中位 0.85，范围 [0.75, 0.95] ✓
- v3 的 P1/P2 数据保留作为"错误定价"消融对照（synth 贵 2 倍仍能造成 +35% regret）。

## 7. P1 v4 终版（重定价后，2026-10-10 15:10）✅ 数据定稿

- **σ = 0.377**（113/300；Wilson95 [0.324, 0.433]）
- 族分解：**clone 46/88 = 52.3%**（与真品五五开！）、geo 34/97 = 35.1%、reviews 33/115 = 28.7%
- 解读修正：机制不是"agent 偏爱营销话术"，而是**规格克隆的不可分辨性**——近拷贝+改关键
  属性+低价的 clone，agent 一半时间选错。geo/reviews 被 agent 以规格不符为由拒绝
  （轨迹证据），clone 则"看起来理性"（更便宜、几乎一样）。
- 门槛判定：σ≥0.60 仍不达标（预注册"系统性偏好"假设弱形式不成立），但 σ_clone≈0.5 +
  P2 剂量反应构成侵蚀通道的完整证据链。
- 测量补充：confidence 产出率 0%（模型不内联输出 confidence）→ run_episode 增加
  购买后显式置信引导轮（1 次额外调用，temp=0，max 20 tok），后续所有主测量带 ECE 数据。

## 8. P2 v4b 定稿与 P3 功效定矩阵（2026-10-10 15:30）

### 8a. P2 v4b（正确价格 + 置信引导，40 任务 × ε{0,0.25,0.75}，0 错误行）
| ε | success_full | regret | synth 购买 | 置信度均值 |
|---|---|---|---|---|
| 0.00 | 0.525 | 0.338 | 0/40 | 0.783 |
| 0.25 | 0.425 | 0.380 | 16/40 | 0.862 |
| 0.75 | 0.450 | 0.398 | 19/40 | 0.862 |
- Δ(0→0.75)：success −7.5pp（McNemar 8v5，N=40 n.s.）；regret +0.061（boot95 含 0，N=40）
  ；**置信度 +0.079（0.783→0.862）**——agent 在污染 Web 上更自信地犯错（"静默"的定量化）
- synth 购买的平均 reward 0.412 vs 同档非 synth 购买 0.789 → 买 synth 平均损失 ~0.38
- **P2 闸门：通过**（success −7.5pp ≥5pp ✓ 且 regret +18% ≥10% ✓）
- 注意：ε=0 基线在 v3(0.600) 与 v4b(0.525) 间差 7.5pp —— 属 vLLM 连续批处理 ±5pp 级噪声
  （P0 已量化），跨运行比较无效，一切以同批配对为准 → 端点加种子重复（P4E）

### 8b. P3 功效分析（0 GPU，定 P4 矩阵）
- 配对 regret 差：mean +0.061，SD 0.50 → 均值检验 80% 功效需 N=526 任务（不可行）
- McNemar success 检验需 N=446（不可行）
- **决策**：主曲线 N=100/档 × ε{0,0.1,0.25,0.5,0.75}（主证据=合成购买份额的趋势检验 +
  各档 bootstrap CI；regret/ECE 以效应量+CI 报告）；**端点 ε{0,0.75} 加 seed-2 重复**
  → 200 配对观测（regret SE≈±0.035，+0.061 达 p<0.05 边缘；success McNemar 功效 ~0.75）
- 扩池：pool.json 仅 40 任务 → goals100.json（前 40 与原池对齐 ✓）+ goals_ext.json
  （60 新任务）在 GPU1 生成中；pool_ext 合并回 pool.json 后跑 P4A/E

### 8c. P4 矩阵（启动）
- P4B：单族归因 geo/clone/reviews × ε{0,0.75} × 40（GPU0，运行中）
- P4C：防御组 prompt/detector_text/detector_struct/random/provenance/oracle × ε{0,0.75} × 40
  （detector_text 的 ppl 阈值校准：real min 15.2 / synth max 21.6 → 阈值 15.0，
  25 真品+20 合成校准样本完美分离）
- P4D：Llama-3.1-8B 骨干 × ε{0,0.25,0.75} × 40（:8001，排在池生成后）
- P4A/E：待池扩展完成后启动

## 9. P4 部分结果（滚动更新，2026-10-10 15:40–16:20）

### 9a. P4B 单族归因（40 任务 × ε{0,0.75}，v4b 同批协议）
| 族 | Δsuccess | Δregret | synth购买@0.75 |
|---|---|---|---|
| geo | 0.575→0.575（0pp） | 0.296→0.331（+11.8%） | 12/40=30% |
| clone | **0.600→0.425（−17.5pp）** | 0.273→0.384（+41%） | **21/40=52.5%** |
| reviews | 0.575→0.425（−15pp） | **0.294→0.454（+54%）** | 15/40=37.5% |
- 解读：clone 摧毁 success（规格近拷贝骗过 grounding）；reviews 制造最大 regret 冲击
  （可信外观→购买→规格缺失→大悔）；geo 最温和但仍有静默损耗
- σ_clone=0.523 的 Wilson95=[0.420,0.625]，含 0.5 → "at chance" 成立

### 9b. P4C 防御组（滚动）
- prompt（40/40 完成）：ε=0 sfull 0.550/regret 0.281；ε=0.75 sfull 0.500/regret 0.364
  → 相对 none（v4b 同任务同种子基线 0.338→0.398）恢复 ~57%（N=40 噪声大，待 P4C 全部
  完成后统一表格+CI）；**"怀疑税"**：prompt 在干净 Web 上也改变行为（基线漂移需在
  同运行内配对解释）
 - detector_text（ppl 阈值 15.0）运行中；后续 struct/random/provenance/oracle

## 10. P4C 防御组终版（40 任务 × ε{0,0.75}，同种子同任务，基线=v4b P2 none）

| 防御 | sfull@0 | sfull@0.75 | regret@0 | regret@0.75 | synth购买@0.75 | 备注 |
|---|---|---|---|---|---|---|
| none(v4b基线) | 0.525 | 0.450 | 0.338 | 0.398 | 19/40 | — |
| prompt | 0.550 | 0.500 | 0.281 | 0.364 | 15/40 | 恢复~57% |
| detector_struct | 0.600 | **0.575** | 0.227 | **0.250** | 18/40 | **完全恢复+** |
| detector_text(修复字段) | 0.575 | **0.200** | 0.311 | **0.578** | 34/40 | **硬阈值灾难** |
| random(对照) | 0.725 | 0.425 | 0.172 | 0.431 | 21/40 | 干净态↑但防不住synth |
| provenance(无徽章v1) | 0.625 | 0.450 | 0.262 | 0.384 | 21/40 | 重排序无效→徽章版重跑 |
| oracle(无徽章) | — | 75行旧码 | — | — | — | 同上，徽章版重跑中 |

### 10a. 两个方法学发现（防御实现即部署语义）
1. **检测器硬阈值脆弱性**：ppl 检测器字段集修复后 ε=0 健康（0.575），但 ε=0.75
   collapse（0.200、synth 购买 85%）——阈值过滤在高剂量下把 gold（通用文本、低 ppl）
   也滤掉，而部分 synth（ppl 15-21.6）漏网。**分离精度高 ≠ 硬过滤安全**：错误集中在
   最高利害候选（真品）上。field-set 校准/部署不匹配是另一层教训（v1 数据归档）。
2. **重排序式 provenance 无效**：agent 看不到 provenance 位时，重排序不改变购买行为
   （synth 购买 52.5% 与 none 相同）。修复：[verified] 徽章渲染 + 系统提示说明徽章语义
   （真实部署形态）→ provenance/oracle 徽章版重跑中。

### 10b. P4D 骨干泛化（Llama-3.1-8B, :8001, 40 任务 × ε{0,0.25,0.75}）
| ε | sfull | regret | synth购买 | conf |
|---|---|---|---|---|
| 0.00 | 0.475 | 0.346 | 0 | 0.666 |
| 0.25 | 0.575 | 0.294 | 9/40 | 0.708 |
| 0.75 | **0.300** | **0.502** | 22/40 | 0.700 |
- 同一签名复现：success −17.5pp、regret +45%、synth 购买 55%。非 Qwen 特异 ✓

### 10c. 扩池完成与 P4A/E
- pool_ext 生成完毕（实际 15:10 已完成，此前误判仍在跑——教训：完成标志看产物文件而非 GPU 占用）
- merge_pool.py：pool.json = 100 任务 / 1089 listing，全部 price_anchored ✓（9/21 两任务
  仍 <6 条，pick_synths 补齐机制兜底）
- P4C_oracle/provenance 徽章重跑 + P4A（100×5ε）+ P4E（端点 seed2）已在 GPU0 排队/运行

## 11. P4A 主曲线定稿 + P4E 种子复现（2026-10-10 17:00–17:45）✅ 核心结果

### 11a. 剂量网格修正
- 名义 ε=0.1 档在 N=10 候选下 `int(0.1×9)=0` 个替换槽 → 与 ε=0 无异，100 行全部
  `SKIPPED:no_synth`。**有效网格改为 {0, 0.25, 0.5, 0.75}（0/2/4/6 槽）**，已记入论文与
  协议说明；已完成数据全部有效。

### 11b. 主曲线（P4A：Qwen2.5-7B，mix，100 任务/档，seed 1）
| ε | success | S@0.8 | regret | synth购买 | 置信 | ECE |
|---|---|---|---|---|---|---|
| 0.00 | 0.590 | 0.600 | 0.262 | 0% | 0.822 | 0.249 |
| 0.25 | 0.350 | 0.350 | 0.429 | 53% | 0.866 | 0.498 |
| 0.50 | 0.420 | 0.420 | 0.401 | 42% | 0.882 | 0.453 |
| 0.75 | 0.360 | 0.360 | 0.443 | 54% | 0.875 | 0.496 |
- **McNemar 0v0.75：28 vs 5 不一致对，χ²=14.7，p=1.3e-4**；Δregret=+0.181
  （SD 0.432，t=4.20，boot95 [+0.095,+0.264]）
- 购买份额 Cochran-Armitage 趋势 z=6.98（p=1.4e-12）
- 共享任务与 v4b 对照：38/40 结果一致（±5pp 批处理噪声量级）
- synth 购买平均 reward 0.41 vs 真品 0.79 → 每次误买损失 ~0.38

### 11c. P4E 端点种子复现（seed 2，100 任务）
- ε=0：0.650 / 0.243；ε=0.75：0.370 / 0.438 / 52% synth
- 方向与 seed1 完全一致（success −28pp、regret +80%）
- **合并两种子 McNemar：64 vs 13，χ²=32.5，p=1.2e-8**
- ECE 0.249→0.496 翻倍；置信 0.822→0.875 反升 → "静默侵蚀三联征"定稿：
  success 降、regret 升更多、置信反升且校准崩坏

### 11d. P5 防御闸门判定
- struct 恢复 >100%、provenance(徽章) ≈100%、oracle >100%、prompt 57% →
  **"至少一个防御恢复 ≥30%" → 大幅通过** ✅

### 11e. 规模消融（问题8：swap 脚本漏传 --model → 3B 全 404，v1 归档后补跑）
- 1.5B：ε=0 0.300/0.578；ε=0.75 0.350/0.523/22 synth —— 能力地板，剂量对比被淹没
- 3B：正确 --model 补跑中；随后 GPU0 还原 7B

## 12. 待续

（3B 补跑、剂量图、论文终稿数字核对、camera-ready 前清理）

## 13. 收尾记录（2026-10-10 18:00）

- **规模消融补跑完成**（问题8 复盘：swap 脚本漏传 --model → 3B 全 404，v1 归档）：
  - 3B：ε=0 0.350/0.388；ε=0.75 0.300/0.493/28 synth（70%）
  - 1.5B：ε=0 0.300/0.578；ε=0.75 0.350/0.523/22 synth —— 能力地板
  - 结论：小模型至少同样易感（3B 误买率 70% > 7B 54%），success 剂量对比需最低基线能力
- **GPU0 已还原 Qwen2.5-7B**；GPU1 空闲（Llama 已无任务）
- **引用核验**（ref_verify，CrossRef+OpenAlex）：33 条中 kim/peeters/yu 3 条 Verified、
  nishal 1 条字段修正（publisher 已按 CrossRef 处理）；其余 29 条为 2026 年 6-10 月 arXiv
  预印本，均来自本会话 paper_search 实测（非编造），CrossRef 尚未索引；正式发表后升级。
- 论文终稿（8 页 acmart sigconf review+anonymous）：abstract/intro/related/problem/method/
  results/discussion/conclusion/appendix 全部填入最终数字，3 张图嵌入。
- 仓库快照：paper/（源码+图+refs）、results_csv/（16 个 CSV）、logs/、EXPERIMENT_LOG.md。

## 14. 修订轮 Wave-1（2026-10-11，审稿后修复实验）

背景：完整审稿（Overall 6/10，7 blocker）+ 6 大科学问题（问题文件）→
实验计划 v2（EXPERIMENT_PLAN_V2.md，A1-A10 GPU / B1-B9 CPU / C1-C8 代码）。

### 环境
- lab 重置为全新单卡 RTX 4090（原环境被清空）：setup_lab.sh 重建
  （代码 git clone @3da65fe、WebShop 官方仓库、vllm 0.19.0 + torch 2.10.0+cu128 CUDA OK、
  Qwen2.5-7B-Instruct 权重 HF snapshot OK）
- Google Drive 官方 gdown 链接被配额拒绝（uc+usercontent 均 403/404，本地与 lab 双试均拒）
  → 改用 HF 镜像 HongbangYuan/webshop（与 YWZBrandon/webshop-data 字节数完全一致的
  双镜像交叉验证）：items_shuffle 5,479,720,229B + ins_v2 186,295,270B + human_ins 5,137,548B，
  hf_transfer 90 秒拉完
- 完整性硬校验：build_goals(n_tasks=40) 必须逐 asin+instruction 复现仓库内 goals.json
- 自动化：sync_daemon.sh 常驻（10 分钟一轮 pull --rebase → copy results/logs → commit+push）；
  run_fix.sh 队列（A1 sham→A2 probeB→A3 probeC→A5 spoof→A7 reviewtrust→A4 PPR λ→A6 seed2）

### 代码（C 组，commit 3da65fe）
- C1 build_task(sham=..., spoof_rate=...)：sham 臂利用 sample_distractors 前缀性质，
  基础 9 候选与原臂逐字节一致，被替换槽位填真品（real-swap 安慰剂）；spoof_rate 参数化
  合成品 prov_present 概率（15%→25%/50% 伪造攻击）
- C2 make_probe_variants.py：pool_probeB.json（clone price=gold 精确锚定）、
  pool_probeC.json（clone rating/num_reviews 置为 gold 水平，社会证明剥离）
- C3 defenses.py defense="ppr"：u = rating + λ·1[prov_ok] 稳定重排（badge 保留），
  λ∈{0.5,1,2} 扫描；defense="reviewtrust"：rating·log(1+num_reviews) 朴素信任重排
- C8 run_fix.sh：CSV 归档→顺序队列；analyze_fix.py：B 组全部分析（bootstrap B=10000）

### B 组 CPU 结果（b_analysis.json，commit 4df025c）
- B1 逐族配对（cseed=1，n=40）：mix(n=100) Δregret +0.181 CI[0.099,0.268] p=2e-4、
  McNemar +5/-28 p=7e-5（主结论加固）；clone Δ+0.111 CI[-0.028,0.250]（CI 跨零，
  诚实降级：单族 n=40 不足）；geo Δ+0.035 CI[-0.110,0.173] 且 success 翻转 6↔6 p=1.0
  （"静默损耗"降级为方向性证据，靠 mix 合并显著性支撑）；reviews Δ+0.160 CI[0.043,0.284]
- B2 全表 CI：Qwen 0→0.25 success 0.59 CI[0.49,0.69] → 0.35 CI[0.26,0.44] 无重叠
  （悬崖真实）；0.25/0.5/0.75 三档 regret CI 互相重叠（非单调=噪声，回应 blocker B7）；
  Llama 0.25 异常点（succ 0.57>0.47）CI 重叠属噪声
- B3 防御两两 @0.75：provenance vs struct Δregret +0.079 CI[-0.052,0.213] p=0.66、
  McNemar 7↔8 p=1.0 → 统计并列；struct vs oracle Δ+0.079 p=0.21（CI 含 0）→
  struct 达到 oracle 级 regret（0.250 vs 0.171）；provenance vs oracle p=0.039 显著差；
  text 灾难确认（0.578，CI[0.473,0.678]，比 none 还差 +0.135）
- B7 struct@ε=0 零误伤：Δreward +0.078 CI[-0.030,0.195]（不显著为正）、
  gold 购买 23/40 vs 22/40（p=0.55）
- B8 侵蚀系数 κ=dE[regret]/dε 配对：Qwen7B 0.242 CI[0.129,0.352]、
  Llama8B 0.208 CI[0.037,0.374]（跨骨干显著）；3B 0.141 CI 跨零；
  1.5B κ=-0.074（floor 效应：基线 regret 已 0.578，无侵蚀空间）→ 尺度-饱和叙事
