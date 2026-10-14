# 外部效度验证方案（真实攻击文档 + 环境规模）

**动因**：恶意文档全部由我们生成（geo/clone/review 标签自知），整个实验在自建沙盒内；
且检索面只有 10 条 top-k，撑不起"环境式污染"主张。本方案用**真实文档**与**更大环境面**
补外部效度。执行顺序：方案5 → 方案1 → 方案2 → 方案3 → 方案4。

**验收纪律**：每完成一项在下方打钩并追加"结果与分析"；实验代码同步到 lab computer 并推送
GitHub（https://github.com/MashiroRb/SynthFlood.git）；每完成一段实验即 push，最终核对远端。

---

## 方案 5：主张改口径（无需 GPU）— [x]

- 把"环境被虚假信息淹没"式措辞改为实验实际证明的命题："常驻检索环境中的商业噪声，
  无需定向注入、伴随常规浏览出现"。"环境式"= ambient presence，不指全网大规模淹没。
- 明确写出当前操作化范围（结果页 top-10 注入）与方案 2 的扩展。
- **结果与分析**：已改 4 处——①abstract：ambient 定义改为"占据常规浏览的检索语境，无需定向"；②problem.tex Setting 小节新增 scope note（ambient ≠ 全网饱和声明；主表面=10 槽结果页；后续规模实验扩展至 50 槽）；③conclusion 开头 "saturating the Web"→"common on the commercial Web"；④discussion Limitations 新增两句：表面范围声明 + 真实文档注入预告（clone=人工核验 lookalike 对、reviews=被标垃圾评论）。编译 12 页 0 错误。

## 方案 1：真实克隆注入实验（需 GPU，~30-45 分钟）— [ ]

- 污染文档 = 真实网页内容、零生成：ProMapEn 人工核验 close non-match（509 对）+
  WebShop 真实目录挖掘 lookalike 对（497 对，Jaccard∈[0.80,0.95)）。
- 任务：真实金品 vs 真实近似品（低价 f∈{0.9, 0.8}），与合成 clone 同折扣点对比 σ_真实 vs σ_合成。
- 判读（预注册）：同方向 → 机制不依赖我们的生成器；效应更弱 → 如实报告为生成器高估。
- **结果与分析**：（待填）

## 方案 2：环境规模实验（需 GPU，~1-1.5 小时）— [ ]

- harness 结果页 N=50 条（原 N=10）；固定绝对污染条数做剂量线（1/3/10/25 条污染）；
  加多页浏览条件。
- 输出：退化 vs 绝对污染量的反应函数；大表面积下效应是否存活。
- **结果与分析**：（待填）

## 方案 3：真实假评注入（需 GPU，~20 分钟，时间允许则做）— [ ]

- 注入 YelpNYC/YelpChi/YelpZIP（Rayana & Akoglu）被标注的真实垃圾评论文本。
- 声明：标签来自异常检测+人工核验，非作者自供；挂载方式由我们实现。
- **结果与分析**：（待填）

## 方案 4：真实环境噪声注入（需 GPU，~20 分钟，时间允许则做）— [ ]

- geo 的真实对应物 = 与查询无关的真实营销文案（跨品类真实商品文案错位摆放）。
- 局限：不存在按 geo/clone/review 标注真实攻击文档的权威语料（领域事实）；
  geo 通道最强验证 = "真实文档占据同一功能生态位"。
- **结果与分析**：（待填）

## 方案 6：真实站点镜像演练 — 不进正文，写为 future work / limitation — [ ]

---

## 工程约定

- 代码目录：`repo_clone/realattack/`（含运行脚本、数据准备脚本、结果 CSV），
  通过 lab_file_upload 同步到 lab computer 的 `~/realattack/`。
- 结果 CSV + 分析 JSON 每完成一段 push 一次；自动推送脚本 `repo_clone/push_auto.sh`。
- 论文变更同步 `初稿/ → repo_clone/paper/` 后一并 push。
- 最终核对：`git ls-remote` 与本地 HEAD 一致 + 远端存在结果文件。
