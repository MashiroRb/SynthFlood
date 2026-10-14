# RA1 数据完整性说明（2026-10-14 关机前核查发现）

## 发现
`ra1_real_clone_probe.csv` 中 synth_f090 臂只有 248/250 行：task 88 和 task 175
的原始运行中，`synth_listing()` 返回 None（`_extract_json` 解析失败），工作线程
在 `b["price"]=...` 处抛 `TypeError` 死亡，未写行。

## 根因诊断（已复现确认，非瞬时故障）
对该 prompt 以 4 个不同 seed 重试生成均失败。失败原因：模型输出的 JSON 中
title 字段含**未转义双引号**（商品尺寸 `12.7" x 5.9"`），`json.loads` 必然报
`Expecting ',' delimiter`。max_tokens=1500 同样失败（不是截断）。这是 LLM 输出
格式错误（该商品规格含英寸符号），属生成器固有失败率，非 harness 缺陷。
clone 家族生成失败率：2/250 = 0.8%。

## 处置（预注册纪律：不改动生成参数，诚实排除）
- 不修改 max_tokens/temperature（保持预注册生成参数）。
- synth_f090 臂记 n=248；real 三臂 n=250 完好。
- 配对检验使用 248 个共同任务。

## 本地重算核验（2026-10-14，基于 GitHub 上的 CSV）
- σ_synth = 168/248 = 0.6774 ✓（与 ra1_summary 一致）
- 配对 McNemar（248 共同任务）：b=59（synth 赢 real 输），c=44（real 赢 synth 输），
  精确二项 p=0.1674 ✓（ra1_stats.json 的 b/c 标签顺序相反，p 相同；论文只引用 p）
- 论文相应位置已改为 "n=250 per arm; 248/250 in the synthetic arm"（正文）与
  附录协议段的完整排除说明。

## 与论文数字的关系
无任何已报告数值因此改变（所有统计本就基于可用的 248 行计算）。此说明仅为
数据完整性与排除规则留痕。
