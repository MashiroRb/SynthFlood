# 污染40轮 → 干净40轮实验归档

本目录归档 Figure 6(a) 后续代码审计与实验。最新实验仅含 M0 / B0，八个种子2030–2037，干净购物第0、2、4、……、40轮各考固定452题（305个金品）。

## 最新实验

- 协议：[WASHOUT40_PROTOCOL.md](WASHOUT40_PROTOCOL.md)
- 执行与校验：[washout40.py](washout40.py)
- 分析：[washout40_summary.py](washout40_summary.py)
- 完整结果：[REPORT.md](../results_m1_washout40/REPORT.md)
- 机器可读结果：[summary.json](../results_m1_washout40/summary.json)、[cells.csv](../results_m1_washout40/cells.csv)
- 冻结环境及来源哈希：[manifest.json](../data/m1_washout40/manifest.json)、[context.json](../data/m1_washout40/context.json)

M0复用已完成的污染40轮末期完整记忆，再进行干净购物40轮；B0从空记忆直接进行相同干净40轮，没有前阶段。同seed两臂的干净目标、候选与展示顺序相同，跨seed仍抽样真实干扰商品。考试不写记忆。

Slurm准备145075、GPU数组145078_0–7、汇总145079均COMPLETED / 0:0。新增640集干净购物、151872次正式考试、256次服务哨兵；39次未购买保留分母。第0轮输入/结果与既有40轮及空记忆成绩逐题复核，相同输入的结果不一致为0。

平均clone选择率差（M0−B0）：clean0 +3.54pp，clean2 +5.37pp，clean4 +0.06pp；clean14–40全部seed逐题选择及实际注入文本相同。clean2差距扩大主要来自B0下降，不能称污染效应继续增强。clean4净差接近零也不等于逐题决策相同。
金品等权clean0差+3.65pp，95%轨迹区间[+2.85,+4.58]pp；clean0/2原始符号翻转p均0.0078125，按21节点Holm后均0.1640625。当前证据呈短期外部记忆情境偏移及后续收敛；没有权重更新，缺少同长度干净前经验辅助对照，不能单独证明污染特异的内在偏好改变或普遍消退。

## 一并保存的依赖实验

最新结果依赖原始购物轨迹和冻结输入，因此本次同时保存：

- `data/m1_v2/`、`results_m1_v2/`：修正仪器及最初轨迹。**其B0额外干净前阶段改变了用户定义，不作为原图B0**，见[V2_DESIGN_CLARIFICATION.md](V2_DESIGN_CLARIFICATION.md)。本次仅复用合适的M0来源状态。
- `data/m1_expanded/`、`results_m1_expanded/`：原B0时间线、452题考试与空记忆参考。
- `data/m1_exposure_length/`、`results_m1_exposure_length/`：20/40/80轮污染，最新实验从其中40轮快照继续。
- `audit_m1/`：历史结果、评分/options及复现问题的审计报告；原始历史结果目录保持原样。

各结果目录保留逐题CSV、购物CSV、检查点完整记忆、实际注入文本、lesson请求记录及环境元数据。模型服务`server.log`、逐请求运行日志`logs/`、本地源码压缩包、模型权重、虚拟环境和官方大数据未纳入Git；它们保留在原实验机。PAT不在仓库中。

## 验证及重新汇总

使用Python3.12。已有环境采用vLLM0.8.1、torch2.6.0+cu124、transformers4.50.0、numpy1.26.4、spacy3.7.5及en_core_web_sm3.7.1；汇总另需matplotlib。
校验依赖WebShop固定提交`64fa2a5c15c7daa698b9ac93f5bb5437b634c9bd`中的`web_agent_site/engine/goal.py`与`normalize.py`，放在`.runtime/WebShop/`下，文件SHA256由manifest核查。

```bash
python m1/washout40.py validate
python m1/washout40_summary.py
python m1/test_reproducibility.py
```

摘要、CSV和图已归档，不必重新调用模型即可查看结果。若在Slurm登录节点，验证和汇总也应通过CPU作业执行；仓库提供`m1/slurm/washout40_summary.sbatch`。

新推理需要恢复官方WebShop数据、上述环境与Qwen2.5-7B-Instruct固定revision `a09a35458c702b33eeacc393d103063234e8bc28`。脚本目前包含原集群的模型缓存绝对路径，迁移时需记录配置变更并使用新的实验版本。
当前冻结输入和结果有防覆盖检查；**不要直接对已有结果执行prepare/run，也不要运行旧的自动清空/推送pipeline**。新实验须复制到独立位置、调整输出目录并重新冻结来源，原文件不要覆盖。

## 资源

`m1/slurm/washout40_run.sbatch`：每任务一张RTX3090、4CPU、16GB，24小时时限；八种子最多4并发。实际每seed约13小时。全部计算通过Slurm执行。
